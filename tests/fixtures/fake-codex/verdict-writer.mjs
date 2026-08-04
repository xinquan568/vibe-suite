#!/usr/bin/env node
// SPDX-License-Identifier: ISC
//
// A fake `codex exec` that honours `-o <path>` (vibe-46). The reviewer contract's Output capture row
// requires the verdict text to be retrievable from a result file, and a run that produced none to be
// distinguishable from one that produced an empty one — so this fixture can do all three:
//
//   VIBE_TEST_VERDICT_FILE=present  write a non-empty verdict     -> verdictState "present"
//   VIBE_TEST_VERDICT_FILE=empty    write a zero-length file      -> verdictState "empty"
//   VIBE_TEST_VERDICT_FILE=absent   write nothing at all          -> verdictState "absent"
//
// `VIBE_TEST_QUOTA=1` emits a `turn.failed` whose message reads as an exhausted allowance, so the
// runner's quota classification can be exercised apart from a substantive rejection.
import { writeFileSync } from "node:fs";


const argv = process.argv.slice(2);
const outIndex = argv.indexOf("-o");
const outPath = outIndex >= 0 ? argv[outIndex + 1] : null;

// A barrier so two jobs are provably in flight at the same moment: each writes its own file, then
// waits for the other's to appear. Without it "concurrent" is a hope about scheduling.
//
// It runs **before** the verdict is written, so a run that timed out leaves no verdict file — two
// sequential runs can no longer satisfy the overlap assertions between them.
if (process.env.VIBE_TEST_BARRIER) {
  const { existsSync, writeFileSync: write } = await import("node:fs");
  const [mine, theirs] = process.env.VIBE_TEST_BARRIER.split(":");
  write(mine, "ready");
  const deadline = Date.now() + 10000;
  while (!existsSync(theirs) && Date.now() < deadline) {
    // Busy-wait deliberately: this fixture must not depend on timers being faithful.
  }
  if (!existsSync(theirs)) {
    // Fail **closed**. Falling through on timeout would let the overlap test pass without overlap
    // ever happening — a test that cannot fail, which is the defect it exists to prevent.
    process.stderr.write(`barrier timeout: ${theirs} never appeared\n`);
    process.exit(97);
  }
}

const mode = process.env.VIBE_TEST_VERDICT_FILE ?? "present";
if (outPath && mode !== "absent") {
  writeFileSync(outPath,
    mode === "empty" ? "" : `verdict: ${process.env.VIBE_TEST_VERDICT_TEXT ?? "approve"}\n`);
}

// The shared probe the suite reads with `read_probe()`: argv and stdin state, as the other fixtures
// record them.
if (process.env.VIBE_TEST_PROBE) {
  writeFileSync(process.env.VIBE_TEST_PROBE,
    JSON.stringify({ argv, stdin: "eof", cwd: process.cwd() }));
}

const emit = (event) => process.stdout.write(JSON.stringify(event) + "\n");
emit({ type: "thread.started", thread_id: "thread_fixture_0001" });

if (process.env.VIBE_TEST_QUOTA === "1") {
  emit({ type: "turn.failed",
         error: {
           message: process.env.VIBE_TEST_QUOTA_MESSAGE ?? "You have exceeded your usage limit.",
           ...(process.env.VIBE_TEST_QUOTA_CODE ? { code: process.env.VIBE_TEST_QUOTA_CODE } : {}),
         } });
} else if (process.env.VIBE_TEST_REJECT === "1") {
  emit({ type: "turn.failed", error: { message: "The model declined to produce a review." } });
} else {
  emit({ type: "item.completed", item: { type: "agent_message", text: "verdict: approve" } });
  emit({ type: "turn.completed", usage: { input_tokens: 100, cached_input_tokens: 60, output_tokens: 20 } });
}
process.exit(0);
