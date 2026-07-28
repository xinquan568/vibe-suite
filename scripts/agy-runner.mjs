#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// The agy dispatch engine (E1.7 / vibe-17, implements F2.7 behind the D5/D8 contract gate).
//
// The third engine lane — headless, read-only-attempted dispatch to the agy (Gemini) CLI — mirrors
// E1.1's CONTRACT SURFACE (same job store, same four-key one-line result, same seam and deadline
// discipline) without mirroring its internals. v1 has no resume and no heartbeat: audit calls are
// bounded one-shots.
//
// What agy's own behaviour forces, learned by probing 1.1.2 rather than assumed:
//
// - **The gate decides reachability, not this file.** Until `resolveAgyGate` passes, every dispatch
//   is refused with the gate status. A default path resting on an unconfirmed contract is the
//   defect the gate exists to prevent.
// - **A deadline is mandatory and must be group-wide.** Unauthenticated agy prints an OAuth URL and
//   blocks awaiting an authorization code **even with stdin at /dev/null** — unlike codex, closing
//   stdin does not save you. Only a detached process-group kill bounds it.
// - **The exit code is not a success signal** (agy exits 0 on "Please sign in"). Success is judged
//   from output, and the unauthenticated signature is a failure with a reason, never a result.
// - **`threadId` is always null.** agy v1 exposes no thread id through this path; inventing one
//   would put a fiction in the shared store.
// - **An oversized prompt fails closed.** Truncating an audit prompt silently changes its scope and
//   returns a plausible, incomplete answer, so the runner refuses instead.
//
// **Node floor: 18.** No top-level await.

import { readFileSync } from "node:fs";
import { agyGate } from "./lib/agy-gate.mjs";
import { loadConfig } from "./lib/config-bridge.mjs";
import { runWithDeadline } from "./lib/process.mjs";
import {
  createRecord, finaliseRecord, newJobId, newRecord, readRecord, resultLine, updateRecord,
} from "./lib/jobs.mjs";

export const DEFAULT_TIMEOUT_MS = 600_000;
// Below Linux MAX_ARG_STRLEN (128 KiB): agy takes the prompt as one argv string.
export const PROMPT_ARGV_CAP = 96_000;

class UsageError extends Error {}

function parseArgs(argv) {
  const options = {
    kind: null, model: null, noModel: false, timeoutMs: null, promptFile: null, prompt: null,
  };
  const rest = [];
  for (let index = 0; index < argv.length; index += 1) {
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
      case "--no-model": options.noModel = true; break;
      case "--timeout-ms": options.timeoutMs = next(); break;
      case "--prompt-file": options.promptFile = next(); break;
      default: throw new UsageError(`unknown option: ${arg}`);
    }
  }
  options.prompt = rest.join(" ");
  return options;
}

function resolveModel(workspace, options) {
  if (options.noModel && options.model) {
    throw new UsageError("--no-model and --model are mutually exclusive");
  }
  if (options.model) return options.model;
  if (options.noModel) return null;                       // past the config override, deliberately
  // Engine-specific: agy's override, never codex's (P9 — no default is ever synthesised).
  try {
    return loadConfig(workspace)?.model_overrides?.agy ?? null;
  } catch {
    return null;
  }
}

function resolveTimeout(raw) {
  if (raw === null) return DEFAULT_TIMEOUT_MS;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) {
    throw new UsageError(`--timeout-ms must be a positive number, got '${raw}'`);
  }
  return value;
}

/** Classify agy's plain-text output. The exit code is deliberately not consulted. */
export function classifyOutput({ stdout = "", stderr = "", timedOut = false, spawnFailed = false }) {
  if (spawnFailed) return { status: "failed", reason: "agy-not-found" };
  if (timedOut) return { status: "timed_out", reason: "deadline exceeded" };
  const text = `${stdout}\n${stderr}`.toLowerCase();
  if (text.includes("authentication required") || text.includes("please sign in")) {
    return { status: "failed", reason: "unauthenticated" };
  }
  if (text.includes("quota") || text.includes("resource exhausted") || text.includes("rate limit")) {
    return { status: "failed", reason: "quota" };
  }
  if (!stdout.trim()) return { status: "failed", reason: "empty output" };
  return { status: "completed", reason: null };
}

async function main() {
  const workspace = process.cwd();
  let options;
  let timeoutMs;
  let model;
  try {
    options = parseArgs(process.argv.slice(2));
    if (options.promptFile) {
      if (options.prompt) throw new UsageError("--prompt-file and an inline prompt are mutually exclusive");
      options.prompt = readFileSync(options.promptFile, "utf8");
    }
    if (!options.prompt) throw new UsageError("a prompt is required after `--`");
    if (!options.kind) throw new UsageError("--kind is required");
    timeoutMs = resolveTimeout(options.timeoutMs);
    model = resolveModel(workspace, options);
    if (Buffer.byteLength(options.prompt, "utf8") > PROMPT_ARGV_CAP) {
      // Fail closed: a silently truncated audit prompt returns a plausible, incomplete answer.
      throw new UsageError(
        `prompt exceeds ${PROMPT_ARGV_CAP} bytes; agy takes it as one argv string and truncating ` +
        `it would silently change the scope of the analysis`);
    }
  } catch (error) {
    if (!(error instanceof UsageError)) throw error;
    process.stderr.write(`agy-runner: ${error.message}\n`);
    return 2;
  }

  // The gate, before anything is created or spawned.
  const gate = agyGate();
  if (!gate.passed) {
    process.stderr.write(
      `agy-runner: the agy lane is gated shut — ${gate.reason}. ` +
      `See docs/agy-flip-checklist.md; the cross-model audit engine remains codex.\n`);
    return 2;
  }

  const record = await createRecord(workspace, newRecord({
    jobId: newJobId(), kind: options.kind, sandbox: "read-only", effort: null,
    model, background: false, timeoutMs, claimDigest: null,
  }));
  await updateRecord(workspace, record.jobId, {
    workerPid: process.pid, pgid: null, startedAt: new Date().toISOString(),
  });

  const args = ["--sandbox", "--print"];
  if (model) args.push("--model", model);
  args.push(options.prompt);

  let outcome;
  try {
    outcome = await runWithDeadline({
      command: process.env.VIBE_SUITE_AGY_BIN || "agy",
      args, cwd: workspace, timeoutMs,
      detached: true,        // agy blocks on OAuth regardless of stdin: only a group kill bounds it
    });
  } catch (error) {
    outcome = { stdout: "", stderr: String(error?.message ?? error), timedOut: false, spawnFailed: true };
  }

  const verdict = classifyOutput(outcome);
  const finished = await finaliseRecord(workspace, record.jobId, {
    status: verdict.status,
    rawOutput: outcome.stdout ?? "",
    error: verdict.reason,
    exitCode: Number.isInteger(outcome.exitCode) ? outcome.exitCode : null,
  });
  const final = finished ?? await readRecord(workspace, record.jobId);
  process.stdout.write(resultLine(final) + "\n");
  return final.status === "completed" ? 0 : 1;
}

main()
  .then((code) => { process.exitCode = code; })
  .catch((error) => {
    process.stderr.write(`agy-runner: ${error?.stack ?? error}\n`);
    process.exitCode = 1;
  });
