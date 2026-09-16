#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Stop-gate fixture that BLOCKS with an ANSI-ONLY reason (vibe-310).
//
// The reason carries nothing but two colour sequences. After the transport strips complete ANSI
// sequences before bounding, the wire carries `BLOCK: ` with an empty reason; the gate's existing
// `parsed.reason || default` fallback then selects its own text, `the review blocked this stop`.
// That outcome is pinned in #310 (Scope, 2026-09-16) — before the strip, the raw sequences were
// truthy at the fallback, skipped it, and sanitised to an EMPTY framed reason.
//
// The structure mirrors `gate-hostile-reason.mjs`. **This file must be mode 0755** — the runner execs
// the binary directly, so a non-executable fixture is recorded as a FAILED job, the hook falls open,
// and the test that depends on it would pass for the wrong reason. The test asserts a BLOCK first.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const ESC = String.fromCharCode(0x1b);
const ANSI_ONLY = `${ESC}[31m${ESC}[0m`;        // two complete SGR sequences, no text

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, prompt: process.argv.slice(2).at(-1) ?? "", fixture: "gate-ansi-only" });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_gate_0003" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "item.completed", item: { type: "agent_message", text: `BLOCK: ${ANSI_ONLY}` },
  }) + "\n");
  process.stdout.write(JSON.stringify({ type: "turn.completed", usage: {} }) + "\n");
  process.exit(0);
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
