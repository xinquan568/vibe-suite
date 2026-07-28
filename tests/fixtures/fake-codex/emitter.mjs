#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex that succeeds: emits a well-formed --json event stream and exits 0 (E1.1 / vibe-11).
//
// The stream deliberately includes a blank line and one malformed line. A parser that treats any
// unparseable line as fatal would reject a real stream too — codex-cli interleaves diagnostics —
// while one that ignores parse errors entirely could swallow a terminal event. Both failure modes
// are exercised here rather than described in a comment.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const THREAD_ID = "thread_fixture_0001";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, fixture: "emitter" });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: THREAD_ID }) + "\n");
  process.stdout.write("\n");
  process.stdout.write("not json at all\n");
  process.stdout.write(JSON.stringify({ type: "item.completed", text: "fixture output" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "turn.completed",
    usage: { input_tokens: 100, cached_input_tokens: 60, output_tokens: 10, reasoning_output_tokens: 4 },
  }) + "\n");
  process.exit(0);
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ?? error) + "\n");
  process.exit(1);
});
