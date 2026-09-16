#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Stop-gate fixture: a colour sequence HIDING leading whitespace in front of an over-cap reason (vibe-310).
//
// `BLOCK: ` + ESC[31m + two tabs + 600 A + ESC[0m. Before the transport stripped sequences, the ESC shielded
// the tabs from the verdict parser's leading-whitespace match: the sanitiser turned them into two spaces the
// cap counted and the trim removed — 498 A. After the strip the tabs are the first thing after the token, the
// parser consumes them, and the sanitiser sees 600 A — 500. The same tabs with no sequence in front always
// yielded 500; the prefixed case now agrees with it. Pinned in #310 (Second pin, 2026-09-16).
//
// Mirrors `gate-hostile-reason.mjs`. **This file must be mode 0755** — a non-executable fixture is recorded as a
// FAILED job, the hook falls open, and the test that depends on it would pass for the wrong reason.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const ESC = String.fromCharCode(0x1b);
const TAB = String.fromCharCode(9);
const REASON = `${ESC}[31m${TAB}${TAB}${"A".repeat(600)}${ESC}[0m`;

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, prompt: process.argv.slice(2).at(-1) ?? "", fixture: "gate-ansi-tabs" });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_gate_0004" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "item.completed", item: { type: "agent_message", text: `BLOCK: ${REASON}` },
  }) + "\n");
  process.stdout.write(JSON.stringify({ type: "turn.completed", usage: {} }) + "\n");
  process.exit(0);
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
