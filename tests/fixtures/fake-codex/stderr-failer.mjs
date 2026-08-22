#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex that explains itself on STDERR and exits 2 with NO terminal event (vibe-182 / grill H7).
//
// This is what a rejected flag, a login failure before any JSON, or a crashed CLI looks like from the
// runner's side: one line on stdout that is not an event, the only diagnostic on stderr — wrapped in
// the colour codes a CLI emits — and a non-zero exit. Before vibe-182 the record said
// `error: "no terminal event"`, `rawOutput: "this line is not JSON\n"`, and kept nothing else; the
// stderr that would have told the operator what happened was gone.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const RED = String.fromCharCode(27) + "[31m";      // ESC [31m — the colour code a CLI emits
const RESET = String.fromCharCode(27) + "[0m";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, fixture: "stderr-failer" });

  process.stdout.write("this line is not JSON\n");                       // counted as malformed, never fatal
  process.stderr.write(`${RED}codex: error: unexpected argument '--bogus'${RESET}\n`);
  process.stderr.write("  tip: run with --help\r\n");                    // \r is a control byte: stripped
  process.exitCode = 2;
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
