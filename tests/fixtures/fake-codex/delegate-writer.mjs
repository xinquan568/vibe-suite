#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex that IMPLEMENTS something (E1.4 / vibe-14): records its cwd into the probe — the
// delegation test's proof that the engine ran in the scratch workspace, not the repo — writes a
// real workspace change, and completes cleanly. The emitter proves streams; this proves work.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";
import { writeFileSync } from "node:fs";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, cwd: process.cwd(), fixture: "delegate-writer" });

  writeFileSync("IMPLEMENTED.txt", "created by the delegated implementation fixture\n");

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_delegate_0001" }) + "\n");
  process.stdout.write(JSON.stringify({ type: "item.completed", text: "implementation applied" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "turn.completed",
    usage: { input_tokens: 40, cached_input_tokens: 0, output_tokens: 8, reasoning_output_tokens: 0 },
  }) + "\n");
  process.exit(0);
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
