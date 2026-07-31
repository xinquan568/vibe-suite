#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// A deterministic reviewer for issue2pr's golden runs (E5.3 / vibe-42).
//
// It returns a clean verdict, so the three review modes differ only in the machinery they engage
// rather than in what the reviewer happened to say. That is the whole point of a golden run: hold the
// reviewer constant and let the mode be the variable.
//
// `VIBE_TEST_STUB_VERDICT` selects the answer — `approve` by default. E5.6 (#45) needs the other
// answers to stress the loop's bounds, and this is the fixture it will extend rather than replace.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const VERDICTS = {
  approve: "verdict: approve\nfindings: []",
  revise: "verdict: approve_with_revisions\nfindings:\n  - id: 1\n    severity: major\n    description: 'seeded'",
};

async function main() {
  announcePid();
  const stdin = await probeStdin();
  const mode = process.env.VIBE_TEST_STUB_VERDICT || "approve";
  writeProbe({ stdin, fixture: "issue2pr-stub", mode });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_i2p_0001" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "item.completed",
    text: "Reviewed.\n\n```yaml\n" + (VERDICTS[mode] ?? VERDICTS.approve) + "\n```",
  }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "turn.completed",
    usage: { input_tokens: 100, cached_input_tokens: 40, output_tokens: 20, reasoning_output_tokens: 5 },
  }) + "\n");
  process.exit(0);
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
