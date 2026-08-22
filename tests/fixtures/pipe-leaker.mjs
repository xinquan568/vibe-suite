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
  process.exit(0);
}
