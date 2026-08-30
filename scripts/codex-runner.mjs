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
// **The result contract is one line of JSON with exactly five keys** — `jobId`, `status`, `threadId`,
// `rawOutput`, `verdictState` — in every mode. A background launch returns the same shape with `status: "running"`
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
// **Nothing secret travels on a worker's argv, and nothing secret is left at rest** (vibe-193 /
// grill S7+S15). `ps` and `/proc/<pid>/cmdline` are readable by every local user, and the detached
// worker lives for the whole job. The one-time claim token and the prompt both go down an inherited
// pipe (fd 3: the token on the first line, the prompt after it) that the launcher ends right after
// writing; the worker argv carries the fd NUMBER. A pipe dies with its two processes, so no ending
// path — a refused claim, a crash on either side, a timeout, a launcher throw after the record exists —
// leaves a file carrying the prompt or a live token behind (the per-job log persists, and carries the
// worker's stderr, not the hand-off). The engine argv gets `--` before the prompt (a prompt that
// begins with `-` is a prompt, never a flag), `--effort` is allow-listed (`-c reasoning.effort=` takes
// a free string), and `--skip-git-repo-check` is passed only for `read-only`: a sandbox that can write
// keeps codex's own non-repository refusal ("Not inside a trusted directory and
// --skip-git-repo-check was not specified.").
//
// **Testing seam:** `VIBE_SUITE_CODEX_BIN` overrides the executable so the suite runs hermetically
// against fixtures. It selects the binary only — it does not relax sandbox arguments — and anyone who
// can set it already controls the process environment.

import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { readdir } from "node:fs/promises";

import {
  ensureDirAt, isOwnedTempRoot, writeAtomic, PRIVATE_FILE_MODE,
} from "./lib/write.mjs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { claimFailureMessage, resolveClaimBudget } from "./lib/claim-budget.mjs";
import { emit } from "./lib/eventlog.mjs";
import { billableTokens, readEventStream } from "./lib/events.mjs";
import { noTerminalEvent, stderrTail } from "./lib/render.mjs";
import { loadConfig, resolveDefaults } from "./lib/config-bridge.mjs";
import {
  DEFAULT_TIMEOUT_MS, heartbeatInterval, runWithDeadline, signalGroup,
} from "./lib/process.mjs";
import {
  claimWith, createRecord, finaliseRecord, hashToken, newClaimToken, newJobId, newRecord,
  readRecord, resultLine, TERMINAL_STATUSES, updateRecord, withWorkerSink,
} from "./lib/jobs.mjs";

const SELF = fileURLToPath(import.meta.url);
const SANDBOXES = new Set(["read-only", "workspace-write", "danger-full-access"]);
const WORKER_FLAG = "--__worker";
// vibe-193: the worker is told the NUMBER of an inherited pipe carrying the one-time claim token
// (first line) and the prompt (the rest) — never the token or the prompt themselves.
const HANDOFF_FLAG = "--__handoff";
const HANDOFF_FD = 3;
// vibe-193: the effort vocabulary the suite speaks — the same `low|medium|high` enum
// `scripts/lib/config.py` enforces for a CONFIGURED effort (the `--effort` flag bypassed that check
// and reached `-c reasoning.effort=` as a free string, an injection surface rather than a setting).
// One vocabulary, enforced at both doors; `tests/test_codex_runner.py` pins the two lists equal.
const EFFORTS = new Set(["low", "medium", "high"]);

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
  // vibe-103: an env-supplied path is an operator input, not a licence to write anywhere. The latch
  // must live in an owned temp root (the suite's own) — nothing else is a permitted destination.
  if (!(await isOwnedTempRoot(dir))) return;
  await ensureDirAt(dir, ".");
  await writeAtomic(dir, path.join(dir, `${name}.signal`), "1",
    { mode: PRIVATE_FILE_MODE }).catch(() => {});
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
    background: false, wait: false, resume: null, confirmDanger: false, noModel: false,
    promptFile: null,
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
      // E1.6 / vibe-16: "run the backend's own default model", which an OMITTED --model cannot
      // express — resolveDefaults falls back to the project's model_overrides.codex. The stop
      // gate needs the difference: `gate.model` unset must mean the backend default, not whatever
      // the project configured for ordinary dispatches.
      case "--no-model": options.noModel = true; break;
      // E1.6 / vibe-16: a large prompt cannot travel in argv — a multi-hundred-KB review prompt
      // hits the OS limit (observed as spawnSync E2BIG on Linux CI while passing on macOS, which
      // is exactly the kind of platform-dependent break a file removes).
      case "--prompt-file": options.promptFile = next(); break;
      case WORKER_FLAG: options.worker = next(); break;
      case HANDOFF_FLAG: options.handoff = next(); break;
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
  if (options.noModel && options.model) {
    throw new UsageError("--no-model and --model are mutually exclusive");
  }
  if (options.promptFile !== null) {
    if (options.prompt) throw new UsageError("--prompt-file and an inline prompt are mutually exclusive");
    try {
      options.prompt = readFileSync(options.promptFile, "utf8");
    } catch (error) {
      throw new UsageError(`--prompt-file ${options.promptFile}: ${error.message}`);
    }
  }
  if (options.worker) return;
  if (!options.prompt) throw new UsageError("a prompt is required after `--`");
  if (options.sandbox !== null && !SANDBOXES.has(options.sandbox)) {
    throw new UsageError(`--sandbox expects one of ${[...SANDBOXES].join("|")}`);
  }
  if (options.effort !== null && !EFFORTS.has(options.effort)) {
    throw new UsageError(`--effort expects one of ${[...EFFORTS].join("|")}, got '${options.effort}'`);
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

/** The effective effort (after config defaults and resume inheritance) must be one codex accepts. */
function assertEffortAllowed(effective) {
  if (effective !== null && effective !== undefined && !EFFORTS.has(effective)) {
    throw new UsageError(
      `resolved effort '${effective}' is not one of ${[...EFFORTS].join("|")} ` +
      "(it resolved from your --effort flag, .vibe-suite.md, or the resumed job)");
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
  // vibe-193 / grill S7: codex's own non-repository check stays armed for any sandbox that can
  // write. `--skip-git-repo-check` is passed only when nothing can be written anyway; a
  // workspace-write or danger-full-access run outside a git repository fails fast with codex's own
  // message. For a resume the record's sandbox decides, as it does for the danger gate.
  if (sandbox === "read-only") args.push("--skip-git-repo-check");
  args.push("--json");
  if (effort) args.push("-c", `reasoning.effort=${effort}`);
  if (model) args.push("-m", model);
  // `--` ends option parsing (verified on codex-cli 0.146.1 for `exec` and `exec resume`): a prompt
  // that begins with `-` is a prompt, never a flag.
  args.push("--", prompt);
  return args;
}

function codexBinary(env = process.env) {
  return env.VIBE_SUITE_CODEX_BIN || "codex";
}

// --------------------------------------------------------------------------- execution

/** An exhausted allowance, or a substantive rejection?
 *
 * The contract calls this row "the one most easily collapsed into the others and the one that must
 * not be": a quota is retryable later, a rejection is a judgement, and a loop that confuses them
 * either retries a verdict or abandons a round it could have finished.
 *
 * **Structured fields first.** A `code` or `type` on the error is machine-set and stable; prose is
 * neither. Phrase matching is the fallback for backends that supply only a message, and it is a
 * table so a new variant is a data change.
 */
const QUOTA_CODES = new Set([
  "insufficient_quota", "quota_exceeded", "rate_limit_exceeded", "resource_exhausted",
  "usage_limit_reached", "too_many_requests",
]);
const QUOTA_PHRASES = [
  /\bquota\b/i, /\brate.?limit/i, /\busage (?:limit|cap)\b/i, /\bexceeded your\b/i,
  /\btoo many requests\b/i, /\bresource exhausted\b/i, /\bout of credits?\b/i,
];

function classifyError(events) {
  const code = String(events.errorCode ?? events.errorType ?? "").toLowerCase();
  if (code && QUOTA_CODES.has(code)) return "quota";
  const message = events.errorMessage ?? "";
  return QUOTA_PHRASES.some((pattern) => pattern.test(message)) ? "quota" : "failure";
}

/** The verdict, from the event stream (vibe-137).
 *
 * The Output capture obligation is that the verdict is retrievable and *"a run that produced none is
 * distinguishable from one that produced an empty one."* The stream carries both facts: no
 * `agent_message` item is `absent`, one with no non-whitespace text is `empty`.
 *
 * An earlier version read this from a `-o <result>` file. The stream is **mandatory** — status,
 * threadId, error class and token accounting all come from it — so a second channel for one field
 * bought redundancy nobody needed and a disagreement surface nothing reconciled.
 */
function verdictFrom(events) {
  if (events.agentMessage === null || events.agentMessage === undefined) {
    return { verdictText: null, verdictState: "absent" };
  }
  const text = String(events.agentMessage);
  return { verdictText: text, verdictState: text.trim() === "" ? "empty" : "present" };
}

async function execute(workspace, record, prompt) {
  // vibe-207: dispatch.start lives HERE, not in runForeground, because `execute` is the one
  // function BOTH paths reach — the foreground caller and the detached background worker. The
  // Step-8 review found the events only on the foreground path, which meant a background job, the
  // shape an operator is most likely to be asking about later, recorded nothing.
  await emit(workspace, { component: "runner", event: "dispatch.start", jobId: record.jobId,
    detail: { kind: record.kind, sandbox: record.sandbox, effort: record.effort,
              background: record.background } });

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
            .catch((error) => {
              // A missed beat must never kill the job — but it must no longer be invisible either.
              // A job that looks abandoned because its heartbeats were failing is exactly the
              // question this log exists to answer, and the swallow used to erase it.
              void emit(workspace, { component: "store", event: "heartbeat.error",
                jobId: record.jobId,
                detail: { errorClass: "failure", message: String(error?.message ?? error) } });
            });
        }
      : null,
  });

  const events = readEventStream(outcome.stdout);
  const verdict = verdictFrom(events);
  let status;
  if (outcome.timedOut) status = "timed_out";
  else if (events.terminal === "completed") status = "completed";
  else status = "failed";                            // includes "no terminal event at all"

  // Quota signature: the contract calls this "the one most easily collapsed into the others and the
  // one that must not be." An exhausted allowance is retryable later; a rejection is a judgement.
  // Both arrive as `turn.failed`, so the message is normalised into a class rather than left as text.
  const errorClass = status === "completed" ? null : classifyError(events);

  const finished = await finaliseRecord(workspace, record.jobId, {
    status,
    errorClass,
    threadId: events.threadId ?? record.threadId ?? null,
    rawOutput: outcome.stdout,
    verdictText: verdict.verdictText,
    verdictState: verdict.verdictState,
    exitCode: outcome.exitCode,
    pipesLeaked: outcome.pipesLeaked,
    // vibe-182: the engine's stderr (tail, control-stripped), the signal that ended it, and the
    // count of event lines that did not parse — persisted whatever the status, so a failure can be
    // read back instead of re-run. A run with no terminal event names how the engine ended and
    // quotes the first stderr line (`noTerminalEvent`); the timed-out and `turn.failed` messages keep
    // their precedence.
    stderrTail: stderrTail(outcome.stderr),
    signal: typeof outcome.signal === "string" ? outcome.signal : null,
    malformedLines: events.malformedLines,
    error: status === "completed"
      ? null
      : events.errorMessage
        ?? (outcome.timedOut ? `deadline of ${record.timeoutMs}ms exceeded` : noTerminalEvent(outcome)),
    tokens: billableTokens(events.usage),
  });
  const settled = finished ?? await readRecord(workspace, record.jobId);
  // vibe-207: dispatch.finalise beside dispatch.start, for the same reason — this is the one place
  // both the foreground caller and the detached background worker pass through.
  await emitFinalise(workspace, settled);
  return settled;
}

/** Resolve the record to run, asserting the effective sandbox before anything can be spawned. */
async function prepareRecord(workspace, options, timeoutMs, claimDigest) {
  if (!options.resume) {
    const defaults = resolveDefaults(loadConfig(workspace), {
      sandbox: options.sandbox, effort: options.effort, model: options.model,
    });
    if (options.noModel) defaults.model = null;      // past the config fallback, deliberately
    assertSandboxAllowed(defaults.sandbox, { confirmDanger: options.confirmDanger });
    assertEffortAllowed(defaults.effort);
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
  assertEffortAllowed(prior.effort);
  return createRecord(workspace, {
    ...newRecord({
      jobId: newJobId(), kind: prior.kind, sandbox: prior.sandbox, effort: prior.effort,
      model: prior.model, background: options.background, timeoutMs, claimDigest,
    }),
    threadId: prior.threadId,
  });
}

/**
 * A failure BEFORE a record exists still owes the consumer the contract line (vibe-180 / grill M7).
 *
 * `prepareRecord` shells out to `python3 config.py` and creates the job record; a missing
 * interpreter, an invalid `.vibe-suite.md` or an unwritable state directory used to escape every
 * guard and reach `main()`'s terminal `.catch` — a raw stack on stderr and NO result line, which the
 * slash commands that branch on `status` cannot interpret. `ConfigBridgeError` and its kin are
 * contract-level failures: the line says `failed`, `jobId` is null because nothing was recorded, and
 * the reason travels on stderr in the same `codex-runner:` form usage errors use. Usage errors are
 * NOT failures — they keep exit 2 and no line, so the caller learns its invocation was wrong.
 */
function preRecordFailure(error) {
  const message = String(error?.message ?? error);
  process.stderr.write(`codex-runner: ${message}\n`);
  process.stdout.write(resultLine({ jobId: null, status: "failed", errorClass: "failure", error: message }) + "\n");
  return 1;
}

async function runForeground(workspace, options, timeoutMs) {
  let record;
  let claimed;
  try {
    record = await prepareRecord(workspace, options, timeoutMs, null);
    // Foreground records no pgid: this process inherits the invoking shell's group, so a number
    // here would name someone else's group and #12 is told to trust it. `pgid` non-null ⟺ background.
    claimed = await updateRecord(workspace, record.jobId, {
      workerPid: process.pid, pgid: null, startedAt: new Date().toISOString(),
    });
  } catch (error) {
    if (error instanceof UsageError) throw error;
    if (!record) return preRecordFailure(error);
    await emit(workspace, { component: "store", event: "claim.error", jobId: record.jobId,
      detail: { errorClass: "failure", message: String(error?.message ?? error) } });
    // The record exists (the claim step failed): finalise it as failed so the store and the line
    // agree, then emit the line — the same shape the execution guard below uses.
    const failed = await finaliseRecord(workspace, record.jobId, {
      status: "failed", errorClass: "failure", error: String(error?.message ?? error),
    }).catch(() => null);
    process.stderr.write(`codex-runner: ${String(error?.message ?? error)}\n`);
    process.stdout.write(resultLine(failed ?? { ...record, status: "failed" }) + "\n");
    return 1;
  }
  try {
    const finished = await execute(workspace, claimed ?? record, options.prompt);
    process.stdout.write(resultLine(finished) + "\n");
    return finished.status === "completed" ? 0 : 1;
  } catch (error) {
    // A spawn failure must still finalise and still emit the contract line — this is the path a
    // misconfigured VIBE_SUITE_CODEX_BIN reaches first.
    const failed = await finaliseRecord(workspace, record.jobId, {
      status: "failed", errorClass: "failure", error: String(error?.message ?? error),
    }).catch(() => null);
    await emit(workspace, { component: "store", event: "finalise.error", jobId: record.jobId,
      detail: { errorClass: "failure", message: String(error?.message ?? error) } });
    await emitFinalise(workspace, failed ?? { ...record, status: "failed" });
    process.stdout.write(resultLine(failed ?? { ...record, status: "failed" }) + "\n");
    // (dispatch.finalise for the ordinary path is emitted inside execute(), which both the
    // foreground and the background WORKER go through — see the note there.)
    return 1;
  }
}

/**
 * The three store-error events (vibe-207).
 *
 * `component: "store"` rather than `"runner"`, per the frozen detail contract: the runner is where
 * these are CAUGHT, but what they are ABOUT is a store operation that failed. An operator asking
 * "why did this job look abandoned" is asking about the store.
 */

/**
 * `dispatch.finalise` for a terminal record (vibe-207).
 *
 * `durationMs` is `endedAt - startedAt`, and **null when `startedAt` is null** — a job finalised
 * before it was ever claimed has no run to measure, and falling back to `createdAt` would report
 * queue time under a name that means run time. The record's terminal timestamp is `endedAt`; there
 * is no `finalisedAt` field anywhere in the store.
 */
async function emitFinalise(workspace, record) {
  const startedAt = record?.startedAt ?? null;
  const endedAt = record?.endedAt ?? null;
  const durationMs = startedAt === null || endedAt === null
    ? null
    : Date.parse(endedAt) - Date.parse(startedAt);
  await emit(workspace, {
    component: "runner", event: "dispatch.finalise", jobId: record?.jobId ?? null,
    detail: {
      status: record?.status ?? null, errorClass: record?.errorClass ?? null,
      exitCode: record?.exitCode ?? null, signal: record?.signal ?? null, durationMs,
    },
  });
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
  let record;
  try {
    record = await prepareRecord(workspace, options, timeoutMs, hashToken(token));
  } catch (error) {
    if (error instanceof UsageError) throw error;
    return preRecordFailure(error);
  }

  // vibe-182 / grill H7: the worker's OWN stderr — a stack from a throw before the claim, the
  // `codex-runner:` lines — used to go to /dev/null, so a worker that died before claiming left no
  // trace. It now goes to a private per-job log (`withWorkerSink`: opened through the audited
  // primitive, handed over as the stderr slot, the launcher's handle closed at once). The Codex
  // child's stderr is unaffected: `runWithDeadline` pipes it back to the worker, which persists its
  // tail on the record. The `pre-spawn` latch is a test seam, inert outside the suite.
  await signalLatch("pre-spawn");
  await awaitLatch("pre-spawn");
  // vibe-193 / grill S7+S15: neither the prompt nor the one-time claim token travels on the
  // worker's argv, and neither is written to disk (see the header). Both go down an inherited pipe
  // the launcher ends right after writing — the token on the first line, the prompt after it; the
  // argv carries the fd NUMBER. A worker that never reads (died before the claim) simply never
  // claims — the launcher's existing no-claim path below reaps it; the pipe dies with the processes.
  const { child, warning } = await withWorkerSink(workspace, record.jobId, (stderr) => spawn(
    process.execPath, [SELF, WORKER_FLAG, record.jobId, HANDOFF_FLAG, String(HANDOFF_FD)],
    { cwd: workspace, env: process.env, detached: true, stdio: ["ignore", "ignore", stderr, "pipe"] }));
  if (warning) process.stderr.write(`codex-runner: ${warning}\n`);
  const handoff = child.stdio[HANDOFF_FD];
  handoff.on("error", () => { /* the worker died before reading: no claim; the reaper below runs */ });
  // `end(payload, cb)`: the callback fires once the payload is flushed to the kernel and EOF is sent
  // — the worker reads everything to EOF before it claims, so nothing is lost — and only THEN is the
  // launcher's end destroyed. Without that, a `stdio` pipe stays half-open until the worker exits and
  // the launcher — which "hands off and leaves" — would sit on the job for its whole lifetime.
  handoff.end(`${token}\n${options.prompt}`, () => handoff.destroy());
  child.unref();

  // vibe-209 / grill A14: the budget is an operator seam now, because a cold Node start on a
  // loaded box can exceed the old fixed 5 s and there was no way to wait longer.
  const claimBudgetMs = resolveClaimBudget();
  const claimed = await awaitWorkerClaim(workspace, record.jobId, { timeoutMs: claimBudgetMs });
  if (claimed === null) {
    await signalLatch("final-poll");
    await awaitLatch("pre-kill");
    // Group-signal, because the worker may already have spawned Codex; killing only the worker would
    // orphan it. Then reap before touching the record, so nothing outlives the verdict.
    signalGroup(child.pid, "SIGTERM");
    signalGroup(child.pid, "SIGKILL");
    // Confirm the reap rather than trusting a timer: poll until the group is gone. A timer that
    // merely expires proves nothing, and the record decision below depends on the worker being dead.
    // Only the group actually disappearing counts as reaped. `child.on("exit")` fires when the
    // direct child dies, which says nothing about the Codex process it spawned into the same group —
    // and that grandchild is exactly what a group kill exists to catch.
    const reaped = await new Promise((resolve) => {
      const deadline = Date.now() + 15_000;
      const poll = setInterval(() => {
        if (!signalGroup(child.pid, 0)) { clearInterval(poll); resolve(true); }
        else if (Date.now() > deadline) { clearInterval(poll); resolve(false); }
      }, 50);
    });

    // **Always** attempt the guarded finalisation. A worker killed immediately after claiming would
    // otherwise leave the record `running` forever with nobody alive to finish it. The guard means a
    // job that genuinely completed before the kill keeps its verdict: the transition simply rejects.
    // Retry finalisation: a transient store fault must not be the reason a killed job is left
    // looking alive. Each attempt is guarded, so a job that genuinely finished keeps its verdict.
    let finaliseError = null;
    let after = null;
    for (let attempt = 0; attempt < 5; attempt += 1) {
      finaliseError = null;
      await finaliseRecord(workspace, record.jobId, {
        status: "failed",
        errorClass: "failure",
        // vibe-209: the budget and the pid both travel here. The budget is a parameter of
        // awaitWorkerClaim rather than of this caller, so a message built without passing it would
        // report a number that is merely the default — true by luck, wrong the moment a seam is set.
        error: claimFailureMessage({ budgetMs: claimBudgetMs, pid: child.pid, reaped }),
      }).catch((error) => { finaliseError = error; });

      after = await readRecord(workspace, record.jobId).catch(() => null);
      if (after && TERMINAL_STATUSES.has(after.status)) break;
      await new Promise((resolve) => { setTimeout(resolve, 100); });
    }
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

/**
 * The one-time claim token and the prompt arrive on an inherited fd (vibe-193), never on argv and
 * never on disk: the token is the first line, the prompt is everything after it. An fd that is not
 * an integer, is below 3, is unreadable, carries no newline, or carries an empty token yields no
 * hand-off — and no hand-off means no claim (the existing refusal), so a forged or broken hand-off
 * fails closed.
 */
function readHandoff(handoffFd) {
  const fd = Number(handoffFd);
  if (!Number.isInteger(fd) || fd < HANDOFF_FD) return null;
  let raw;
  try {
    raw = readFileSync(fd, "utf8");
  } catch {
    return null;
  }
  const newline = raw.indexOf("\n");
  if (newline === -1) return null;
  const token = raw.slice(0, newline).trim();
  if (!token) return null;
  return { token, prompt: raw.slice(newline + 1) };
}

/** The worker owns the whole lifecycle and speaks to nobody: its output is the record. */
async function runWorker(workspace, jobId, handoffFd) {
  await signalLatch("pre-claim");
  await awaitLatch("pre-claim");

  const handoff = readHandoff(handoffFd);
  if (handoff === null) {
    // No usable hand-off (absent, non-integer or below-3 fd, unreadable, no newline, empty token):
    // nothing to claim with. Spawn nothing — the same fail-closed outcome as a refused claim.
    process.stderr.write(`codex-runner: worker hand-off unreadable for ${jobId}
`);
    return 1;
  }
  let claimed;
  try {
    claimed = await claimWith(workspace, jobId, handoff.token);
  } catch (error) {
    // vibe-207: a THROWN claim, as opposed to a refused one. Previously it propagated with no record
    // at all, so a background job that died claiming left nothing behind but a stack in its worker
    // log — which is the case this feature exists for.
    await emit(workspace, { component: "store", event: "claim.error", jobId,
      detail: { errorClass: "failure", message: String(error?.message ?? error) } });
    throw error;
  }
  if (claimed === null) {
    // No valid one-time token, or already claimed, or already terminal. Spawn nothing.
    process.stderr.write(`codex-runner: worker claim refused for ${jobId}\n`);
    await emit(workspace, { component: "store", event: "claim.error", jobId,
      detail: { errorClass: "failure", message: "claim refused (no valid token, or already claimed)" } });
    return 1;
  }
  await signalLatch("post-claim");

  try {
    await execute(workspace, claimed, handoff.prompt);
    return 0;
  } catch (error) {
    const failed = await finaliseRecord(workspace, jobId, {
      status: "failed", errorClass: "failure", error: String(error?.message ?? error),
    }).catch(() => null);
    // vibe-207: this path finalised in silence. A background job that threw out of `execute` — the
    // spawn failed, the store faulted — recorded neither the error nor an outcome, so the log said
    // the dispatch started and then nothing. Both halves are emitted now.
    await emit(workspace, { component: "store", event: "finalise.error", jobId,
      detail: { errorClass: "failure", message: String(error?.message ?? error) } });
    await emitFinalise(workspace, failed ?? { jobId, status: "failed", errorClass: "failure",
      startedAt: null, endedAt: null, exitCode: null, signal: null });
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
    if (options.worker) return await runWorker(workspace, options.worker, options.handoff);
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
