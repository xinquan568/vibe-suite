#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// The audit-lane entry point (E1.7 / vibe-17): agy → codex → manual, as observable process behaviour.
//
// This exists because a state machine that only returns objects is a state machine nobody can
// verify. Its exit codes and stdout are the contract:
//
//   0  an engine answered — its four-key result line is on stdout
//   2  the lane is gated shut, or the invocation was malformed — nothing dispatched
//   3  no engine could run it — `{"fallback":"manual",...}` on stdout, for the caller to act on
//
// Diagnostics go to stderr, always: stdout carries exactly one machine-readable thing.
//
// **Node floor: 18.** No top-level await.

import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { agyGate } from "./lib/agy-gate.mjs";
import { EXIT, runWithFallback } from "./lib/agy-fallback.mjs";

const SELF_DIR = path.dirname(fileURLToPath(import.meta.url));

function dispatch(runner, args, cwd) {
  const result = spawnSync(process.execPath, [path.join(SELF_DIR, runner), ...args],
    { cwd, encoding: "utf8", timeout: 900_000 });
  const line = (result.stdout || "").trim().split("\n").filter(Boolean).at(-1);
  try {
    return line ? JSON.parse(line) : null;
  } catch {
    return null;
  }
}

async function main() {
  const argv = process.argv.slice(2);
  const separator = argv.indexOf("--");
  const prompt = separator === -1 ? "" : argv.slice(separator + 1).join(" ");
  if (!prompt) {
    process.stderr.write("agy-audit: a prompt is required after `--`\n");
    return EXIT.refused;
  }
  const cwd = process.cwd();
  const shared = ["--kind", "audit", "--timeout-ms", "600000", "--", prompt];

  const outcome = await runWithFallback({
    gate: agyGate(),
    runAgy: async () => dispatch("agy-runner.mjs", shared, cwd),
    runCodex: async () => dispatch("codex-runner.mjs", ["--sandbox", "read-only", ...shared], cwd),
    emitHeader: (text) => process.stderr.write(`agy-audit: ${text}\n`),
  });

  if (outcome.outcome === "refused") {
    process.stderr.write(`agy-audit: ${outcome.reason}. See docs/agy-flip-checklist.md\n`);
    return outcome.exitCode;
  }
  if (outcome.outcome === "manual") {
    process.stdout.write(JSON.stringify(outcome.signal) + "\n");
    return outcome.exitCode;
  }
  process.stdout.write(JSON.stringify(outcome.result) + "\n");
  return outcome.exitCode;
}

main()
  .then((code) => { process.exitCode = code; })
  .catch((error) => {
    process.stderr.write(`agy-audit: ${error?.stack ?? error}\n`);
    process.exitCode = 1;
  });
