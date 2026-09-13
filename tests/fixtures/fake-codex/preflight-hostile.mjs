#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex whose every output is hostile (E1.3 / vibe-13): ANSI redraw sequences, fence-breaking
// backtick runs, unrecognized auth wording, kilobytes of noise, no terminal event. The probe must
// degrade to bounded `unknown`/failure enums, still print the matrix, and let NONE of these bytes
// reach its own stdout or stderr.

import { writeProbe } from "./record.mjs";

const ANSI = "\x1b[2J\x1b[31m";
const NOISE = `${ANSI}HOSTILE-BYTES  ${"`".repeat(7)}\n` + "z".repeat(64 * 1024);

function main() {
  writeProbe({ fixture: "preflight-hostile" });
  const argv = process.argv.slice(2);

  if (argv[0] === "--version") {
    process.stdout.write(NOISE + "\n");
    // NOT process.exit(0): this fixture writes more than a pipe buffer, and exit() does not
    // wait for stdout to drain — the capture would be cut mid-line, so the pre-flight path
    // would be handed a payload nobody chose. The `return` is load-bearing too: exit() was
    // also leaving the branch, and dropping it lets --version fall through into the exec
    // output (131,154 bytes measured, against an intended 65,569).
    process.exitCode = 0;
    return;
  }
  if (argv[0] === "login") {
    process.stdout.write(`session state: ${NOISE}\n`);   // unrecognized wording, status 0
    process.exitCode = 0;
    return;
  }
  process.stdout.write(NOISE + "\nnot json at all\n");   // exec: no terminal event
  process.exitCode = 0;
}

main();
