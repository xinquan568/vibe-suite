#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Stop-gate fixture for verdict discrimination (E1.6 / vibe-16). Three ways to be almost-a-verdict:
// an earlier assistant message that says BLOCK (the LAST one must win), leading prose before the
// word BLOCK (the FIRST non-empty line must be the verdict), and a verdict-looking marker on a
// later line (ignored). Selected with VIBE_TEST_GATE_CASE: last-wins | prose | later-line.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const CASES = {
  "last-wins": [
    "BLOCK: an earlier verdict that must NOT win",
    "ALLOW: the final verdict",
  ],
  prose: ["Here is my considered review.\nBLOCK: buried after prose"],
  "later-line": ["ALLOW-ish preamble\nBLOCK: on a later line"],
};

async function main() {
  announcePid();
  const stdin = await probeStdin();
  const which = process.env.VIBE_TEST_GATE_CASE ?? "last-wins";
  writeProbe({ stdin, fixture: "gate-chatty", case: which });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_gate_0004" }) + "\n");
  for (const text of CASES[which] ?? CASES["last-wins"]) {
    process.stdout.write(JSON.stringify({
      type: "item.completed", item: { type: "agent_message", text },
    }) + "\n");
  }
  process.stdout.write(JSON.stringify({ type: "turn.completed", usage: {} }) + "\n");
  process.exit(0);
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
