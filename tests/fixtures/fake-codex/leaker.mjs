#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex that LEAKS its stdio pipes and outlives its deadline (vibe-181 / grill H6).
//
// It spawns a grandchild that inherits stdout/stderr and idles for a long time, records the
// grandchild's pid in the probe (so the test can reap it deliberately), then hangs until signalled.
// SIGTERM is NOT ignored: the deadline kills this process promptly, which is the point — the
// process is dead but its pipes are still held by the grandchild, and a runner that waited for
// `close` would never finalise the job while the grandchild lives.

import { spawn } from "node:child_process";

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

async function main() {
  announcePid();
  // Leak FIRST, before anything that takes time: the deadline under test is short, and the
  // grandchild must be holding the pipes by the time SIGTERM arrives.
  const holdMs = Number(process.env.VIBE_TEST_LEAK_HOLD_MS ?? 10_000);
  const grandchild = spawn(process.execPath, ["-e", `setTimeout(() => {}, ${holdMs});`],
    { stdio: ["ignore", "inherit", "inherit"] });
  grandchild.unref();
  writeProbe({ stdin: "not-probed", fixture: "leaker", grandchild: grandchild.pid });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_leaker_0004" }) + "\n");
  await probeStdin();
  setInterval(() => {}, 1000);        // stay alive until the deadline's SIGTERM
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
