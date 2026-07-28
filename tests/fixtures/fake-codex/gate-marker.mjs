#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Stop-gate fixture that blocks ONLY if the seeded defect marker actually reached its prompt
// (E1.6 / vibe-16). This is what makes "the untracked file's CONTENT was reviewed" an assertion
// rather than a hope: a gate that sent only `git status` and a filename gets an ALLOW here.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const MARKER = "SEEDED-DEFECT-MARKER";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, prompt: process.argv.slice(2).at(-1) ?? "", fixture: "gate-marker" });

  const sawMarker = (process.argv.slice(2).at(-1) ?? "").includes(MARKER);
  const text = sawMarker
    ? "BLOCK: the diff introduces the seeded defect"
    : "ALLOW: nothing of concern in the reviewed diff";

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_gate_0001" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "item.completed", item: { type: "agent_message", text },
  }) + "\n");
  process.stdout.write(JSON.stringify({ type: "turn.completed", usage: {} }) + "\n");
  process.exit(0);
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
