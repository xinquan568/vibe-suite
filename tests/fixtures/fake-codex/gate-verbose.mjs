#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Stop-gate fixture that emits an OVER-BUDGET event stream (vibe-274). The verdict-bearing
// `agent_message` sits at the start, in the middle, or at the end, selected by
// VIBE_TEST_VERDICT_AT, so the gate's decision can be compared against the same stream unbounded.
//
// The padding is deliberately larger than RAW_OUTPUT_BYTES (128 KiB) so the runner's bound is the
// thing under test rather than a contrived cap. Padding events are `reasoning` items: real content,
// but never verdict-bearing, so only the allocator decides whether the verdict survives.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const MARKER = "SEEDED-DEFECT-MARKER";
// VIBE_TEST_PAD=0 emits the SAME verdict with no padding at all, so a test can compare a
// bounded run against its own unbounded control rather than against a different fixture.
const PAD_EVENTS = process.env.VIBE_TEST_PAD === "0" ? 0 : 700;   // ~110 bytes each, over 128 KiB
const PAD_TEXT = "z".repeat(160);

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, prompt: process.argv.slice(2).at(-1) ?? "", fixture: "gate-verbose" });

  const sawMarker = (process.argv.slice(2).at(-1) ?? "").includes(MARKER);
  const text = sawMarker
    ? "BLOCK: the diff introduces the seeded defect"
    : "ALLOW: nothing of concern in the reviewed diff";

  const at = process.env.VIBE_TEST_VERDICT_AT ?? "end";
  const pad = () => process.stdout.write(JSON.stringify({
    type: "item.completed", item: { type: "reasoning", text: PAD_TEXT },
  }) + "\n");
  const verdict = () => process.stdout.write(JSON.stringify({
    type: "item.completed", item: { type: "agent_message", text },
  }) + "\n");

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_gate_0274" }) + "\n");
  const before = at === "start" ? 0 : at === "middle" ? Math.floor(PAD_EVENTS / 2) : PAD_EVENTS;
  for (let i = 0; i < before; i += 1) pad();
  verdict();
  for (let i = before; i < PAD_EVENTS; i += 1) pad();
  process.stdout.write(JSON.stringify({ type: "turn.completed", usage: {} }) + "\n");
  // NOT process.exit(0): this fixture writes more than a pipe buffer, and exit() does not
  // wait for stdout to drain — the stream would be cut mid-line and the runner would see a
  // truncated capture rather than an over-budget one.
  process.exitCode = 0;
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
