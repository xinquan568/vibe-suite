#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// The Codex dispatch engine (E1.1 / vibe-11, implements F2.1).
//
// Every external-engine call in the suite flows through here: `/vibe-suite:delegate`,
// `/vibe-suite:bug-analyze`, `/vibe-suite:continue`, `/vibe-suite:jobs`, the stop-review gate, and
// the agy runner, which mirrors this contract surface. Six consumers inherit whatever this file
// decides, so the decisions are written down rather than left to be inferred.
//
// Canonical call:
//
//   node scripts/codex-runner.mjs --kind <k> [--model <m>] --effort <e> --sandbox <s>
//        [--timeout-ms <t>] [--wait | --background | --resume <jobId>] [--confirm-danger]
//        -- "<prompt>"
//
// `--timeout-ms` defaults to 600000 (10 min). Zero, negative and non-numeric are **rejected**: a
// deadline-bounded runner that reads those as "unbounded" is not deadline-bounded.
//
// **Node floor: 18.** No top-level await — `main()` is invoked, not awaited at module scope
// (cc-suite W7 class). `tests/node/no-top-level-await.mjs` enforces that with a checker that reports
// or refuses on any ambiguity, because `node --check` accepts top-level await and is not an oracle.
//
// **The result contract is one line of JSON with exactly four keys** — `jobId`, `status`, `threadId`,
// `rawOutput` — in every mode. A background launch returns the same shape with `status: "running"`
// and nulls: the acknowledgement is a *launch receipt*, so a worker that finished early cannot make
// it lie about the shape. Callers branch on `status`, never on shape.
//
// **Success is decided by the event stream, never the exit code.** codex-cli 0.144.6 exits 0 on an
// upstream failure while emitting `turn.failed`.
//
// **The danger gate reads the EFFECTIVE sandbox**, resolved from config and resume state, not the raw
// flag. Checking the flag while a different value reaches the spawn is how round 1 shipped a
// confirmation gate that did not gate.
//
// **Testing seam:** `VIBE_SUITE_CODEX_BIN` overrides the executable so the suite runs hermetically
// against fixtures. It selects the binary only — it does not relax sandbox arguments — and anyone who
// can set it already controls the process environment.

import { spawn } from "node:child_process";
import { mkdir, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { billableTokens, readEventStream } from "./lib/events.mjs";
import { loadConfig, resolveDefaults } from "./lib/config-bridge.mjs";
import {
  DEFAULT_TIMEOUT_MS, heartbeatInterval, runWithDeadline, signalGroup,
} from "./lib/process.mjs";
import {
  claimWith, createRecord, finaliseRecord, hashToken, newClaimToken, newJobId, newRecord,
  readRecord, resultLine, TERMINAL_STATUSES, updateRecord,
} from "./lib/jobs.mjs";

const SELF = fileURLToPath(import.meta.url);
const SANDBOXES = new Set(["read-only", "workspace-write", "danger-full-access"]);
const WORKER_FLAG = "--__worker";
const CLAIM_FLAG = "--__claim";

class UsageError extends Error {}

// --------------------------------------------------------------------------- test latches
// File latches make race tests deterministic: a party signals by creating a file and waits by
// polling for one. Nothing here depends on elapsed time. Inert unless VIBE_SUITE_TEST_LATCH_DIR is
// set, which only the test suite does.

function latchDir() {
  return process.env.VIBE_SUITE_TEST_LATCH_DIR || null;
}

async function signalLatch(name) {
  const dir = latchDir();
  if (!dir) return;
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, `${name}.signal`), "1", "utf8").catch(() => {});
}

async function awaitLatch(name, { timeoutMs = 30_000 } = {}) {
  const dir = latchDir();
  if (!dir) return;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const names = await readdir(dir).catch(() => []);
    if (names.includes(`${name}.release`)) return;
    await new Promise((resolve) => { setTimeout(resolve, 10); });
  }
}

// --------------------------------------------------------------------------- argument handling

function parseArgs(argv) {
  const options = {
    kind: null, model: null, effort: null, sandbox: null, timeoutMs: null,
    background: false, wait: false, resume: null, confirmDanger: false,
    worker: null, claim: null, prompt: null,
  };
  const rest = [];
  let index = 0;

  for (; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--") { rest.push(...argv.slice(index + 1)); break; }
    const next = () => {
      const value = argv[index + 1];
      if (value === undefined) throw new UsageError(`${arg} expects a value`);
      index += 1;
      return value;
    };
    switch (arg) {
      case "--kind": options.kind = next(); break;
      case "--model": options.model = next(); break;
      case "--effort": options.effort = next(); break;
      case "--sandbox": options.sandbox = next(); break;
      case "--timeout-ms": options.timeoutMs = next(); break;
      case "--resume": options.resume = next(); break;
      case "--background": options.background = true; break;
      case "--wait": options.wait = true; break;
      case "--confirm-danger": options.confirmDanger = true; break;
      case WORKER_FLAG: options.worker = next(); break;
      case CLAIM_FLAG: options.claim = next(); break;
      default:
        if (arg.startsWith("-")) throw new UsageError(`unknown option ${arg}`);
        rest.push(arg);
    }
  }

  options.prompt = rest.join(" ").trim() || null;
  return options;
}

function resolveTimeout(raw) {
  if (raw === null) return DEFAULT_TIMEOUT_MS;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) {
    throw new UsageError(
      `--timeout-ms expects a positive number of milliseconds (default ${DEFAULT_TIMEOUT_MS}), got '${raw}'`);
  }
  return value;
}

function validateShape(options) {
  if (options.worker) return;
  if (!options.prompt) throw new UsageError("a prompt is required after `--`");
  if (options.sandbox !== null && !SANDBOXES.has(options.sandbox)) {
    throw new UsageError(`--sandbox expects one of ${[...SANDBOXES].join("|")}`);
  }
  if (options.background && options.wait) {
    throw new UsageError("--wait and --background are mutually exclusive");
  }
  if (options.background && options.resume) {
    throw new UsageError("--background and --resume are mutually exclusive");
  }
}

/**
 * The one place a sandbox is authorised, called immediately before anything is spawned on every path.
 *
 * It takes the **effective** sandbox — after config defaults and resume inheritance — because the
 * value that reaches `codex` is the only one worth checking.
 */
function assertSandboxAllowed(effective, { confirmDanger }) {
  if (!SANDBOXES.has(effective)) {
    throw new UsageError(`resolved sandbox '${effective}' is not one of ${[...SANDBOXES].join("|")}`);
  }
  if (effective === "danger-full-access" && !confirmDanger) {
    throw new UsageError(
      "sandbox 'danger-full-access' requires --confirm-danger (refusing to run unconfirmed). " +
      "It resolved from your --sandbox flag, .vibe-suite.md, or the resumed job.");
  }
  if (effective !== "danger-full-access" && confirmDanger) {
    throw new UsageError(
      `--confirm-danger is only meaningful when the resolved sandbox is danger-full-access (it is '${effective}')`);
  }
}

/** Build the `codex exec` argument vector. No model flag unless one was explicitly chosen (P9). */
function codexArgs({ sandbox, effort, model, threadId, prompt }) {
  const args = ["exec"];
  if (threadId) {
    // `codex exec resume` accepts no -s/--sandbox — verified against codex-cli 0.144.6, where plain
    // `codex exec` does. Omitting it is also how "resume inherits the original sandbox" is actually
    // achieved: the session already carries it. The recorded sandbox is policy metadata, not an arg.
    args.push("resume", threadId);
  } else {
    args.push("-s", sandbox);
  }
  args.push("--skip-git-repo-check", "--json");
  if (effort) args.push("-c", `reasoning.effort=${effort}`);
  if (model) args.push("-m", model);
  args.push(prompt);
  return args;
}

function codexBinary(env = process.env) {
  return env.VIBE_SUITE_CODEX_BIN || "codex";
}

// --------------------------------------------------------------------------- execution

async function execute(workspace, record, prompt) {
  const heartbeatMs = heartbeatInterval();
  const outcome = await runWithDeadline({
    command: codexBinary(),
    args: codexArgs({
      sandbox: record.sandbox, effort: record.effort, model: record.model,
      threadId: record.threadId, prompt,
    }),
    cwd: workspace,
    timeoutMs: record.timeoutMs,
    heartbeatMs,
    onSpawned: () => { signalLatch("post-child-spawn"); },
    onHeartbeat: record.background
      ? () => {
          updateRecord(workspace, record.jobId, { heartbeatAt: new Date().toISOString() })
            .catch(() => { /* a missed beat must never kill the job */ });
        }
      : null,
  });

  const events = readEventStream(outcome.stdout);
  let status;
  if (outcome.timedOut) status = "timed_out";
  else if (events.terminal === "completed") status = "completed";
  else status = "failed";                            // includes "no terminal event at all"

  const finished = await finaliseRecord(workspace, record.jobId, {
    status,
    threadId: events.threadId ?? record.threadId ?? null,
    rawOutput: outcome.stdout,
    exitCode: outcome.exitCode,
    error: status === "completed"
      ? null
      : events.errorMessage
        ?? (outcome.timedOut ? `deadline of ${record.timeoutMs}ms exceeded` : "no terminal event"),
    tokens: billableTokens(events.usage),
  });
  return finished ?? readRecord(workspace, record.jobId);
}

/** Resolve the record to run, asserting the effective sandbox before anything can be spawned. */
async function prepareRecord(workspace, options, timeoutMs, claimDigest) {
  if (!options.resume) {
    const defaults = resolveDefaults(loadConfig(workspace), {
      sandbox: options.sandbox, effort: options.effort, model: options.model,
    });
    assertSandboxAllowed(defaults.sandbox, { confirmDanger: options.confirmDanger });
    return createRecord(workspace, newRecord({
      jobId: newJobId(), kind: options.kind ?? "exec", background: options.background,
      timeoutMs, claimDigest, ...defaults,
    }));
  }

  // Resume inherits the original sandbox — but inheriting a confirmed sandbox is not inheriting the
  // confirmation, so it is re-asserted here.
  const prior = await readRecord(workspace, options.resume);
  if (!prior.threadId) throw new UsageError(`job ${options.resume} has no thread id to resume`);
  assertSandboxAllowed(prior.sandbox, { confirmDanger: options.confirmDanger });
  return createRecord(workspace, {
    ...newRecord({
      jobId: newJobId(), kind: prior.kind, sandbox: prior.sandbox, effort: prior.effort,
      model: prior.model, background: options.background, timeoutMs, claimDigest,
    }),
    threadId: prior.threadId,
  });
}

async function runForeground(workspace, options, timeoutMs) {
  const record = await prepareRecord(workspace, options, timeoutMs, null);
  // Foreground records no pgid: this process inherits the invoking shell's group, so a number here
  // would name someone else's group and #12 is told to trust it. `pgid` non-null ⟺ background.
  const claimed = await updateRecord(workspace, record.jobId, {
    workerPid: process.pid, pgid: null, startedAt: new Date().toISOString(),
  });
  try {
    const finished = await execute(workspace, claimed ?? record, options.prompt);
    process.stdout.write(resultLine(finished) + "\n");
    return finished.status === "completed" ? 0 : 1;
  } catch (error) {
    // A spawn failure must still finalise and still emit the contract line — this is the path a
    // misconfigured VIBE_SUITE_CODEX_BIN reaches first.
    const failed = await finaliseRecord(workspace, record.jobId, {
      status: "failed", error: String(error?.message ?? error),
    }).catch(() => null);
    process.stdout.write(resultLine(failed ?? { ...record, status: "failed" }) + "\n");
    return 1;
  }
}

/**
 * Background launch: create the record, hand off to a detached worker, acknowledge, leave.
 *
 * A single process cannot both hold the child's pipes, deadline timer and heartbeat *and* return
 * promptly — Node will not exit while those handles are live. So the launcher supervises nothing.
 * `detached: true` puts the worker in its own process group, which is what makes the recorded `pgid`
 * a usable cancellation handle for #12 and what lets a kill reach the Codex grandchild.
 */
async function runBackground(workspace, options, timeoutMs) {
  const token = newClaimToken();
  const record = await prepareRecord(workspace, options, timeoutMs, hashToken(token));

  const child = spawn(process.execPath,
    [SELF, WORKER_FLAG, record.jobId, CLAIM_FLAG, token, "--", options.prompt], {
      cwd: workspace, env: process.env, detached: true, stdio: ["ignore", "ignore", "ignore"],
    });
  child.unref();

  const claimed = await awaitWorkerClaim(workspace, record.jobId);
  if (claimed === null) {
    await signalLatch("final-poll");
    await awaitLatch("pre-kill");
    // Group-signal, because the worker may already have spawned Codex; killing only the worker would
    // orphan it. Then reap before touching the record, so nothing outlives the verdict.
    signalGroup(child.pid, "SIGTERM");
    signalGroup(child.pid, "SIGKILL");
    // Confirm the reap rather than trusting a timer: poll until the group is gone. A timer that
    // merely expires proves nothing, and the record decision below depends on the worker being dead.
    const reaped = await new Promise((resolve) => {
      let done = false;
      const finish = (value) => { if (!done) { done = true; resolve(value); } };
      child.on("exit", () => finish(true));
      const deadline = Date.now() + 15_000;
      const poll = setInterval(() => {
        if (!signalGroup(child.pid, 0)) { clearInterval(poll); finish(true); }
        else if (Date.now() > deadline) { clearInterval(poll); finish(false); }
      }, 50);
    });

    // **Always** attempt the guarded finalisation. A worker killed immediately after claiming would
    // otherwise leave the record `running` forever with nobody alive to finish it. The guard means a
    // job that genuinely completed before the kill keeps its verdict: the transition simply rejects.
    let finaliseError = null;
    await finaliseRecord(workspace, record.jobId, {
      status: "failed",
      error: reaped
        ? "worker did not start, or was terminated before claiming"
        : "worker did not start and could not be confirmed reaped",
    }).catch((error) => { finaliseError = error; });

    const after = await readRecord(workspace, record.jobId).catch(() => null);
    const terminal = after && TERMINAL_STATUSES.has(after.status);

    // A record we just killed must never be acknowledged as `running`. The consumed digest chooses
    // the acknowledgement *shape* only once the record is settled; if finalisation failed and the
    // record is still non-terminal, saying "running" would report a live job that is dead.
    if (!terminal) {
      process.stderr.write(
        `codex-runner: could not finalise ${record.jobId}` +
        `${finaliseError ? `: ${finaliseError.message}` : ""}\n`);
      process.stdout.write(resultLine({ ...(after ?? record), status: "failed" }) + "\n");
      return 1;
    }
    if (after.claimDigest === null) {
      // A claim did happen, so D-B still owes a launch receipt for the acknowledgement shape.
      process.stdout.write(resultLine({ ...after, status: "running", threadId: null, rawOutput: null }) + "\n");
      return 0;
    }
    process.stdout.write(resultLine(after) + "\n");
    return 1;
  }

  await awaitLatch("pre-ack");
  // Always the synthesised receipt: the ack reports that the job was launched, not what it has since
  // become, so a worker that finished early cannot violate the contract.
  process.stdout.write(resultLine({ ...claimed, status: "running", threadId: null, rawOutput: null }) + "\n");
  return 0;
}

async function awaitWorkerClaim(workspace, jobId, { timeoutMs = 5000, pollMs = 25 } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const record = await readRecord(workspace, jobId).catch(() => null);
    if (record && record.workerPid !== null) return record;
    await new Promise((resolve) => { setTimeout(resolve, pollMs); });
  }
  return null;
}

/** The worker owns the whole lifecycle and speaks to nobody: its output is the record. */
async function runWorker(workspace, jobId, token, prompt) {
  await signalLatch("pre-claim");
  await awaitLatch("pre-claim");

  const claimed = await claimWith(workspace, jobId, token);
  if (claimed === null) {
    // No valid one-time token, or already claimed, or already terminal. Spawn nothing.
    process.stderr.write(`codex-runner: worker claim refused for ${jobId}\n`);
    return 1;
  }
  await signalLatch("post-claim");

  try {
    await execute(workspace, claimed, prompt);
    return 0;
  } catch (error) {
    await finaliseRecord(workspace, jobId, {
      status: "failed", error: String(error?.message ?? error),
    }).catch(() => {});
    return 1;
  }
}

async function main() {
  const workspace = process.cwd();
  let options;
  let timeoutMs;
  try {
    options = parseArgs(process.argv.slice(2));
    validateShape(options);
    timeoutMs = options.worker ? null : resolveTimeout(options.timeoutMs);
  } catch (error) {
    if (!(error instanceof UsageError)) throw error;
    process.stderr.write(`codex-runner: ${error.message}\n`);
    return 2;
  }

  try {
    if (options.worker) return await runWorker(workspace, options.worker, options.claim, options.prompt);
    if (options.background) return await runBackground(workspace, options, timeoutMs);
    return await runForeground(workspace, options, timeoutMs);
  } catch (error) {
    if (error instanceof UsageError) {
      process.stderr.write(`codex-runner: ${error.message}\n`);
      return 2;
    }
    throw error;
  }
}

main()
  .then((code) => { process.exitCode = code; })
  .catch((error) => {
    process.stderr.write(`codex-runner: ${error?.stack ?? error}\n`);
    process.exitCode = 1;
  });
