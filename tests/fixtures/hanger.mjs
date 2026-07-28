#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// A process tree that ignores SIGTERM at every level (E1.3 / vibe-13). The parent spawns a child
// into its own process group (no detach), so only a GROUP kill reaps both — this is what makes
// runWithDeadline's detached mode observable: a runner that signals only the direct child leaves
// the descendant alive, and the test's ESRCH probe on the group catches it.

import { spawn } from "node:child_process";

process.on("SIGTERM", () => { /* deliberately ignored */ });

const descendant = spawn(process.execPath, ["-e",
  'process.on("SIGTERM", () => {}); setInterval(() => {}, 1000);',
], { stdio: "ignore" });
descendant.unref();

process.stdout.write("hanging\n");
setInterval(() => {}, 1000);
