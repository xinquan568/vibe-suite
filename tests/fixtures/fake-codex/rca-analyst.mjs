#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex for RCA analysis (E1.5 / vibe-15): reads the per-file `FILE:` headers out of its own
// prompt, names the FIRST shortlisted file as the root cause — and deliberately also names a path
// that is NOT in the shortlist, so the report's verification split is observable: a claim without
// recon support must never be promoted into the findings section.

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

  const analysis = `The root cause is in ${culprit}: the increment is applied twice. ` +
    `Unsupported claim for the split test: /tmp/not-in-shortlist.js also looks broken.`;

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_rca_0001" }) + "\n");
  process.stdout.write(JSON.stringify({ type: "item.completed", text: analysis }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "turn.completed",
    usage: { input_tokens: 30, cached_input_tokens: 0, output_tokens: 12, reasoning_output_tokens: 0 },
  }) + "\n");
  process.exit(0);
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
