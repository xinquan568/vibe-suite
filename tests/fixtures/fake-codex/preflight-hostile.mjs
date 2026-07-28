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
    process.exit(0);
  }
  if (argv[0] === "login") {
    process.stdout.write(`session state: ${NOISE}\n`);   // unrecognized wording, exit 0
    process.exit(0);
  }
  process.stdout.write(NOISE + "\nnot json at all\n");   // exec: no terminal event
  process.exit(0);
}

main();
