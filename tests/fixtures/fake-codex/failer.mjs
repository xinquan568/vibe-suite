#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex that fails while exiting 0 (E1.1 / vibe-11).
//
// This is not a contrived case. codex-cli 0.144.6 was observed returning exit 0 with no result and a
// `turn.failed` event after an upstream outage; the issue2pr skill records it. A runner that reads
// the exit code would record this job as `completed`. The whole point of the fixture is that it
// exits 0.

import { probeStdin, writeProbe } from "./record.mjs";

async function main() {
  const stdin = await probeStdin();
  writeProbe({ stdin, fixture: "failer" });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_failed_0002" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "turn.failed",
    error: { message: "circuit open (fixture)" },
  }) + "\n");
  process.exit(0);
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
