#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex that outlives its deadline and ignores SIGTERM (E1.1 / vibe-11).
//
// Ignoring SIGTERM is the point: a runner that sends SIGTERM and assumes death would leave this
// process alive. Only an escalation to SIGKILL reaps it, so this fixture is what makes the
// escalation observable rather than merely coded.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, fixture: "sleeper" });

  process.on("SIGTERM", () => { /* deliberately ignored */ });
  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_sleeper_0003" }) + "\n");
  setInterval(() => {}, 1000);        // stay alive until signalled
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
