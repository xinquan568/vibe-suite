#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex for the cross-engine lane tests (E4.5 / vibe-39).
//
// Two jobs the other fixtures do not do.
//
// **It records the prompt.** `writeProbe` captures argv, and the prompt is the last argv element, so
// a test can assert what the lane actually packaged — the scoring rubric and the engine's check
// catalog. That is the strongest evidence available in CI that the second opinion is "on the same
// rubric" as F4.2 requires: the rendered comparison needs a host, but what went into the prompt does
// not.
//
// **It returns a divergent payload.** `VIBE_TEST_LANE_MODE` selects what comes back:
//
//   agree     a score and finding set matching the deterministic engine's
//   diverge   a different score AND one extra finding, so both disagreement granularities fire
//   unusable  a completed turn whose output is not the record shape — the `fallback.md`
//             "reachable but returned nothing usable" path, which must NOT produce a diagnostic
//             header and must NOT be reported as a set of disagreements
//
// `unusable` is the mode worth having: an engine that answers uselessly is a different state from one
// that is unreachable, and collapsing them is the defect the fallback partial exists to prevent.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const PAYLOADS = {
  agree: {
    score: 45,
    findings: [
      { rule: "--", check: "name present", line: 1, penalty: -25 },
      { rule: "R05", check: "body length", line: 1, penalty: -10 },
      { rule: "R01", check: "vague quantifier", line: 11, penalty: -20 },
    ],
  },
  diverge: {
    score: 38,
    findings: [
      { rule: "--", check: "name present", line: 1, penalty: -25 },
      { rule: "R05", check: "body length", line: 1, penalty: -10 },
      { rule: "R01", check: "vague quantifier", line: 11, penalty: -20 },
      { rule: "R07", check: "scope note", line: 60, penalty: -3 },
    ],
  },
};

async function main() {
  announcePid();
  const stdin = await probeStdin();
  const mode = process.env.VIBE_TEST_LANE_MODE || "agree";
  writeProbe({ stdin, fixture: "lane-responder", mode });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_lane_0001" }) + "\n");

  const text = mode === "unusable"
    ? "I looked at the files but could not apply the rubric."
    : JSON.stringify(PAYLOADS[mode] ?? PAYLOADS.agree);
  process.stdout.write(JSON.stringify({ type: "item.completed", text }) + "\n");

  process.stdout.write(JSON.stringify({
    type: "turn.completed",
    usage: { input_tokens: 120, cached_input_tokens: 40, output_tokens: 30, reasoning_output_tokens: 8 },
  }) + "\n");
  process.exit(0);
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
