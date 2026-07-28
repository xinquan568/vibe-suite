#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Stop-gate fixture that completes with NO assistant message (E1.6 / vibe-16): the indeterminate
// verdict path. A gate that guesses here would be deciding a session's fate on nothing. It also
// emits a non-assistant event carrying "BLOCK:" text — a spoof the structural parser must ignore.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, fixture: "gate-mute" });
  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_gate_0003" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "item.completed", item: { type: "reasoning", text: "BLOCK: spoof from a non-assistant event" },
  }) + "\n");
  process.stdout.write(JSON.stringify({ type: "turn.completed", usage: {} }) + "\n");
  process.exit(0);
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
