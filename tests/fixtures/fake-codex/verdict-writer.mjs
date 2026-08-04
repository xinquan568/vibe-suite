#!/usr/bin/env node
// SPDX-License-Identifier: ISC
//
// A fake `codex exec` for the Output capture and Quota signature rows (vibe-46, vibe-137).
//
// The verdict travels in the **event stream** — there is no result file. `VIBE_TEST_VERDICT_FILE`
// selects which of the three states the stream expresses:
//
//   present  an `agent_message` item carrying text     -> verdictState "present"
//   empty    an `agent_message` item carrying ""       -> verdictState "empty"
//   absent   no `agent_message` item at all            -> verdictState "absent"
//
// `VIBE_TEST_QUOTA=1` emits a `turn.failed` whose message — and optionally whose `code` — reads as an
// exhausted allowance, so quota classification is exercised apart from a substantive rejection.
import { writeFileSync } from "node:fs";

const argv = process.argv.slice(2);

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
  const mode = process.env.VIBE_TEST_VERDICT_FILE ?? "present";
  if (mode !== "absent") {
    emit({ type: "item.completed",
           item: { type: "agent_message",
                   text: mode === "empty" ? "" : `verdict: ${process.env.VIBE_TEST_VERDICT_TEXT ?? "approve"}` } });
  }
  emit({ type: "turn.completed",
         usage: { input_tokens: 100, cached_input_tokens: 60, output_tokens: 20 } });
}
process.exit(0);
