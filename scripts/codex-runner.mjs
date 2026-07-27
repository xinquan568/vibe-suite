#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// The Codex dispatch engine (E1.1 / vibe-11, implements F2.1).
//
// Every external-engine call in the suite flows through here: `/vibe-suite:delegate`,
// `:bug-analyze`, `:continue`, `:jobs`, the stop-review gate, and the agy runner, which mirrors this
// contract surface. Six consumers inherit whatever this file decides, so the decisions are written
// down rather than left to be inferred.
//
// Canonical call:
//
//   node scripts/codex-runner.mjs --kind <k> [--model <m>] --effort <e> --sandbox <s>
//        --timeout-ms <t> [--background | --resume <jobId>] [--confirm-danger] -- "<prompt>"
//
// **Node floor: 18.** No top-level await anywhere — `main()` is invoked, not awaited at module scope
// (cc-suite W7 class). `tests/node/no-top-level-await.mjs` enforces this with Node's own parser,
// because `node --check` accepts top-level await and is not an oracle for it.
//
// **The result contract is one line of JSON with exactly four keys** — `jobId`, `status`, `threadId`,
// `rawOutput` — in every mode. A background launch returns the same shape with `status: "running"`
// and nulls; callers branch on `status`, never on shape. Unavailable values are `null` rather than
// absent, which differs from the toggle store on purpose (see `lib/jobs.mjs`).
//
// **Success is decided by the event stream, never the exit code.** codex-cli 0.144.6 exits 0 on an
// upstream failure while emitting `turn.failed`; reading the exit code would file that as success.
//
// **Testing seam:** `VIBE_SUITE_CODEX_BIN` overrides the executable so the suite can run hermetically
// against fixtures. It selects the binary only — it does not relax sandbox arguments — and anyone who
// can set it already controls the process environment.

import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { billableTokens, readEventStream } from "./lib/events.mjs";
import { loadConfig, resolveDefaults } from "./lib/config-bridge.mjs";
import { heartbeatInterval, runWithDeadline } from "./lib/process.mjs";
import {
  awaitWorkerClaim, newJobId, newRecord, readRecord, resultLine, updateRecord, writeRecord,
} from "./lib/jobs.mjs";

const SELF = fileURLToPath(import.meta.url);
const SANDBOXES = new Set(["read-only", "workspace-write", "danger-full-access"]);
const WORKER_FLAG = "--__worker";

class UsageError extends Error {}

function parseArgs(argv) {
  const options = {
    kind: null, model: null, effort: null, sandbox: null, timeoutMs: null,
    background: false, resume: null, confirmDanger: false, worker: null, prompt: null,
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
      case "--timeout-ms": options.timeoutMs = Number(next()); break;
      case "--resume": options.resume = next(); break;
      case "--background": options.background = true; break;
      case "--confirm-danger": options.confirmDanger = true; break;
      case WORKER_FLAG: options.worker = next(); break;
      default:
        if (arg.startsWith("-")) throw new UsageError(`unknown option ${arg}`);
        rest.push(arg);
    }
  }

  options.prompt = rest.join(" ").trim() || null;
  return options;
}

function validate(options) {
  if (options.worker) return;                       // the worker re-reads a validated record
  if (!options.prompt) throw new UsageError("a prompt is required after `--`");
  if (options.sandbox !== null && !SANDBOXES.has(options.sandbox)) {
    throw new UsageError(`--sandbox expects one of ${[...SANDBOXES].join("|")}`);
  }
  if (options.timeoutMs !== null && !Number.isFinite(options.timeoutMs)) {
    throw new UsageError("--timeout-ms expects a number of milliseconds");
  }
  if (options.background && options.resume) {
    throw new UsageError("--background and --resume are mutually exclusive");
  }
  // Refusal is the default. The gate cannot be reached by omission, and the flag is an error where
  // it would do nothing, so it cannot be set once "just in case" and then forgotten.
  if (options.sandbox === "danger-full-access" && !options.confirmDanger) {
    throw new UsageError(
      "--sandbox danger-full-access requires --confirm-danger (refusing to run unconfirmed)");
  }
  if (options.confirmDanger && options.sandbox !== "danger-full-access") {
    throw new UsageError("--confirm-danger is only meaningful with --sandbox danger-full-access");
  }
}

/** Build the `codex exec` argument vector. No model flag unless one was explicitly chosen (P9). */
function codexArgs({ sandbox, effort, model, threadId, prompt }) {
  const args = ["exec"];
  if (threadId) args.push("resume", threadId);
  args.push("-s", sandbox, "--skip-git-repo-check", "--json");
  if (effort) args.push("-c", `reasoning.effort=${effort}`);
  if (model) args.push("-m", model);
  args.push(prompt);
  return args;
}

function codexBinary(env = process.env) {
  return env.VIBE_SUITE_CODEX_BIN || "codex";
}

/** Run the child and fold the outcome into the record. Shared by foreground and worker paths. */
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
    onHeartbeat: record.background
      ? () => { updateRecord(workspace, record.jobId, { heartbeatAt: new Date().toISOString() })
          .catch(() => { /* a missed beat must never kill the job */ }); }
      : null,
  });

  const events = readEventStream(outcome.stdout);
  let status;
  if (outcome.timedOut) status = "timed_out";
  else if (events.terminal === "completed") status = "completed";
  else status = "failed";                            // includes "no terminal event at all"

  return updateRecord(workspace, record.jobId, {
    status,
    threadId: events.threadId ?? record.threadId ?? null,
    rawOutput: outcome.stdout,
    exitCode: outcome.exitCode,
    endedAt: new Date().toISOString(),
    error: status === "completed"
      ? null
      : events.errorMessage
        ?? (outcome.timedOut ? `deadline of ${record.timeoutMs}ms exceeded` : "no terminal event"),
    tokens: billableTokens(events.usage),
  });
}

/** Foreground and worker share this; only who prints the line differs. */
async function resolveRecord(workspace, options) {
  if (!options.resume) {
    const config = loadConfig(workspace);
    const defaults = resolveDefaults(config, {
      sandbox: options.sandbox, effort: options.effort, model: options.model,
    });
    return writeRecord(workspace, newRecord({
      jobId: newJobId(), kind: options.kind ?? "exec", background: options.background,
      timeoutMs: options.timeoutMs, ...defaults,
    }));
  }

  // Resume inherits the original sandbox — re-deriving it from config or defaults could silently
  // widen a job's permissions between turns, which is exactly what F2.1 forbids.
  const prior = await readRecord(workspace, options.resume);
  if (!prior.threadId) {
    throw new UsageError(`job ${options.resume} has no thread id to resume`);
  }
  return writeRecord(workspace, {
    ...newRecord({
      jobId: newJobId(), kind: prior.kind, sandbox: prior.sandbox, effort: prior.effort,
      model: prior.model, background: options.background, timeoutMs: options.timeoutMs,
    }),
    threadId: prior.threadId,
  });
}

async function runForeground(workspace, options) {
  const record = await resolveRecord(workspace, options);
  const claimed = await updateRecord(workspace, record.jobId, {
    workerPid: process.pid, pgid: process.pid, startedAt: new Date().toISOString(),
  });
  const finished = await execute(workspace, claimed, options.prompt);
  process.stdout.write(resultLine(finished) + "\n");
  return finished.status === "completed" ? 0 : 1;
}

/**
 * Background launch: create the record, hand off to a detached worker, acknowledge, leave.
 *
 * A single process cannot both hold the child's pipes, deadline timer and heartbeat *and* return
 * promptly — Node will not exit while those handles are live. So the launcher supervises nothing.
 * `detached: true` puts the worker in its own process group, which is what makes the recorded `pgid`
 * a usable cancellation handle for `/vibe-suite:jobs` (#12).
 */
async function runBackground(workspace, options) {
  const record = await resolveRecord(workspace, options);

  const child = spawn(process.execPath, [SELF, WORKER_FLAG, record.jobId, "--", options.prompt], {
    cwd: workspace,
    env: process.env,
    detached: true,
    stdio: ["ignore", "ignore", "ignore"],
  });
  child.unref();

  // The record is already the source of truth, so the handshake needs no IPC channel — and it is
  // bounded, so a worker that dies before claiming cannot hang the launcher.
  const claimed = await awaitWorkerClaim(workspace, record.jobId);
  if (claimed === null) {
    const failed = await updateRecord(workspace, record.jobId, {
      status: "failed", error: "worker did not start", endedAt: new Date().toISOString(),
    });
    process.stdout.write(resultLine(failed) + "\n");
    return 1;
  }

  process.stdout.write(resultLine(claimed) + "\n");
  return 0;
}

/** The worker owns the whole lifecycle and speaks to nobody: its output is the record. */
async function runWorker(workspace, jobId, prompt) {
  const record = await readRecord(workspace, jobId);
  const claimed = await updateRecord(workspace, jobId, {
    workerPid: process.pid,
    pgid: typeof process.getpgrp === "function" ? process.getpgrp() : process.pid,
    startedAt: new Date().toISOString(),
  });
  try {
    await execute(workspace, { ...record, ...claimed }, prompt);
  } catch (error) {
    await updateRecord(workspace, jobId, {
      status: "failed", error: String(error?.message ?? error), endedAt: new Date().toISOString(),
    });
    return 1;
  }
  return 0;
}

async function main() {
  const workspace = process.cwd();
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
    validate(options);
  } catch (error) {
    if (!(error instanceof UsageError)) throw error;
    process.stderr.write(`codex-runner: ${error.message}\n`);
    return 2;
  }

  if (options.worker) return runWorker(workspace, options.worker, options.prompt);
  if (options.background) return runBackground(workspace, options);
  return runForeground(workspace, options);
}

main()
  .then((code) => { process.exitCode = code; })
  .catch((error) => {
    process.stderr.write(`codex-runner: ${error?.stack ?? error}\n`);
    process.exitCode = 1;
  });
