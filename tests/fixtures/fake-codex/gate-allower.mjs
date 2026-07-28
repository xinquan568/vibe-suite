#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Stop-gate fixture that always allows (E1.6 / vibe-16).

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, fixture: "gate-allower" });
  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_gate_0002" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "item.completed", item: { type: "agent_message", text: "ALLOW: looks fine" },
  }) + "\n");
  process.stdout.write(JSON.stringify({ type: "turn.completed", usage: {} }) + "\n");
  process.exit(0);
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
