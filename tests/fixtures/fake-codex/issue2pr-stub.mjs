#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// A deterministic reviewer for issue2pr's golden runs (E5.3 / vibe-42).
//
// It returns a clean verdict, so the three review modes differ only in the machinery they engage
// rather than in what the reviewer happened to say. That is the whole point of a golden run: hold the
// reviewer constant and let the mode be the variable.
//
// `VIBE_TEST_STUB_VERDICT` selects the answer — `approve` by default. E5.6 (#45) extended it rather
// than building a second stub, which is what made the verdict selectable in the first place.
//
// **An unknown mode falls back to `approve`**, and that is load-bearing rather than lazy: a missing
// mode therefore returns a CLEAN verdict, which is exactly what would make an absent stimulus look
// like a passing loop. #45's assertions are "this mode never returns clean" rather than "this mode
// exists", because the fallback is what a weaker assertion would sail past.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const VERDICTS = {
  approve: "verdict: approve\nfindings: []",
  // Never returns clean: an open `major` on every invocation. This is AC-4's first stimulus, and it
  // is deliberately `major` rather than `blocker` — a blocker HALTS issue2pr's round before the
  // update loop, so the cap would never be reached and a bounded-looking run would prove nothing.
  revise: "verdict: approve_with_revisions\nfindings:\n  - id: 1\n    severity: major\n    description: 'seeded'",
  // `fix` has no severity vocabulary. `REGRESSED` stops its loop, which is the opposite of what AC-4
  // wants observed, so the stimulus is the verdict that continues it.
  "never-fixed": "verdict: NOT FIXED\nissues:\n  - id: 1\n    state: 'NOT FIXED'",
};

// Not YAML, inside a fence that looks like one. AC-4's second stimulus: the contract's parser must
// fail on this, or every claim about re-asking is vacuous.
const MALFORMED = "verdict = approve;\n\t<<<not: [yaml\n  - - -";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  const mode = process.env.VIBE_TEST_STUB_VERDICT || "approve";

// vibe-46: the reviewer contract's Output capture row requires the verdict text in the `-o` file.
// Without this the goldens' `verdictState: "present"` would not be reproducible from the fixture
// that generated them — a golden nobody can regenerate is a fixture someone wrote.
{
  const argv = process.argv.slice(2);
  const at = argv.indexOf("-o");
  if (at >= 0 && argv[at + 1]) {
    const { writeFileSync } = await import("node:fs");
    writeFileSync(argv[at + 1], `verdict: ${mode}\n`);
  }
}
  writeProbe({ stdin, fixture: "issue2pr-stub", mode });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_i2p_0001" }) + "\n");
  // vibe-224: `VIBE_TEST_STUB_PAD_BYTES` emits that many bytes of command-output events before the
  // verdict — the shape of a real review, whose stream runs to hundreds of KB — so a test can push the
  // capture past the record's byte cap and prove the verdict is read from the record, not the wire.
  let pad = Number(process.env.VIBE_TEST_STUB_PAD_BYTES || 0);
  const chunk = "x".repeat(4096);
  while (pad > 0) {
    process.stdout.write(JSON.stringify({
      type: "item.completed", item: { type: "command_execution", aggregated_output: chunk },
    }) + "\n");
    pad -= chunk.length;
  }
  // vibe-224: the verdict travels as the engine sends it — an `agent_message` item. The runner reads
  // only that shape (`events.mjs`); the earlier top-level `text` field was invisible to it once the
  // verdict stopped coming from a `-o` file (vibe-137), so a dispatch through this stub recorded
  // `verdictState: "absent"`.
  process.stdout.write(JSON.stringify({
    type: "item.completed",
    item: {
      type: "agent_message",
      text: "Reviewed.\n\n```yaml\n"
        + (mode === "malformed" ? MALFORMED : (VERDICTS[mode] ?? VERDICTS.approve))
        + "\n```",
    },
  }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "turn.completed",
    usage: { input_tokens: 100, cached_input_tokens: 40, output_tokens: 20, reasoning_output_tokens: 5 },
  }) + "\n");
  // vibe-224: an exit code, not `process.exit()` — writes to a pipe are asynchronous, and exiting at once
  // drops whatever has not drained, which with a padded stream is the usage event and the verdict.
  process.exitCode = 0;
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
