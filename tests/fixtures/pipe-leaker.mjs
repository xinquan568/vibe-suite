#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// A child that LEAKS its stdio pipes (vibe-181 / grill H6): it spawns a grandchild that inherits
// stdout and stderr, then — by default — exits at once. The grandchild idles for `holdMs` holding
// the pipes open, so the parent's `close` cannot fire until it dies: exactly the tree a deadline
// that waits for `close` cannot bound. The grandchild's pid is printed so a test can reap it
// deliberately and verify it gone.
//
// Modes (argv[3]):
//   (none)   exit 0 immediately after spawning the grandchild
//   immune   ignore SIGTERM and idle — stays alive through the deadline so only SIGKILL ends it
//   linger   idle until SIGTERM, which it honours — a TERM-responsive child that times out
// argv[2] is the grandchild's hold time in ms (default 4000).

import { spawn } from "node:child_process";

const holdMs = Number(process.argv[2] ?? 4000);
const mode = process.argv[3] ?? "exit";
const grandchild = spawn(process.execPath, ["-e", `setTimeout(() => {}, ${holdMs});`],
  { stdio: ["ignore", "inherit", "inherit"] });
grandchild.unref();

process.stdout.write(`leaking grandchild=${grandchild.pid} mode=${mode}\n`);
if (mode === "immune") {
  process.on("SIGTERM", () => { /* deliberately ignored */ });
  setInterval(() => {}, 1000);
} else if (mode === "linger") {
  setInterval(() => {}, 1000);        // default SIGTERM disposition: dies on the first TERM
} else {
  // NOT process.exit(0): the mode is echoed back in the line above, so this fixture can write
  // more than a pipe buffer, and exit() does not wait for stdout to drain. The abrupt-exit
  // behaviour this mode models is unaffected: `grandchild.unref()` above and the absence of a
  // timer on THIS branch mean nothing survives the drain, so the process still ends at once
  // while the grandchild keeps the inherited descriptors. `immune` and `linger` each hold an
  // interval and are meant to be signalled, so neither is touched.
  process.exitCode = 0;
}
