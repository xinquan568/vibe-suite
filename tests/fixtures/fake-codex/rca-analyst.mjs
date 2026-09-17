#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex for RCA analysis (E1.5 / vibe-15): reads the per-file `FILE:` headers out of its own
// prompt, names the FIRST shortlisted file as the root cause — and deliberately also names a path
// that is NOT in the shortlist, so the report's verification split is observable: a claim without
// recon support must never be promoted into the findings section.
//
// vibe-317: an OPT-IN file-borne payload. A `PAYLOAD-FILE: <path>` line in the prompt makes the fixture
// read that file and append its contents to the analysis, so the bytes on the wire are bounded by the
// file, not by argv (`MAX_ARG_STRLEN` caps one argv string at 131,072 bytes on Linux, below the 262,144 at
// which the pipe transport starts truncating a writer that calls `process.exit`). The `FILE:` headers keep
// their E1.5 meaning untouched; without a `PAYLOAD-FILE:` line the output is byte-for-byte what it was.

import { readFileSync } from "node:fs";

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, fixture: "rca-analyst" });

  const prompt = process.argv.slice(2).at(-1) ?? "";
  const files = prompt.split("\n")
    .filter((line) => line.startsWith("FILE: "))
    .map((line) => line.slice("FILE: ".length).trim());
  const culprit = files[0] ?? "(no per-file sections found)";
  const payloadPath = prompt.split("\n")
    .filter((line) => line.startsWith("PAYLOAD-FILE: "))
    .map((line) => line.slice("PAYLOAD-FILE: ".length).trim())[0];
  const payload = payloadPath ? readFileSync(payloadPath, "utf8") : "";

  const analysis = `The root cause is in ${culprit}: the increment is applied twice. ` +
    `Unsupported claim for the split test: /tmp/not-in-shortlist.js also looks broken.` + payload;

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_rca_0001" }) + "\n");
  process.stdout.write(JSON.stringify({ type: "item.completed", text: analysis }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "turn.completed",
    usage: { input_tokens: 30, cached_input_tokens: 0, output_tokens: 12, reasoning_output_tokens: 0 },
  }) + "\n");
  // NOT process.exit(0): the analysis line carries a path lifted out of the prompt, so this
  // fixture can write more than a pipe buffer, and exit() does not wait for stdout to drain.
  process.exit(0);   // MEASUREMENT MUTANT — never merged (vibe-317)
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
