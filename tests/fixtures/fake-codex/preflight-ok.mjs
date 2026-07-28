#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex for the preflight happy path (E1.3 / vibe-13): a healthy, authenticated CLI.
// Dispatches the three grammars the probes use — `--version`, `login status`, `exec`.

import { writeProbe } from "./record.mjs";

function main() {
  writeProbe({ fixture: "preflight-ok" });
  const argv = process.argv.slice(2);

  if (argv[0] === "--version") {
    process.stdout.write("codex-cli 0.0.7\n");
    process.exit(0);
  }
  if (argv[0] === "login") {
    process.stdout.write("Logged in using ChatGPT\n");
    process.exit(0);
  }
  // exec smoke: a well-formed stream ending in turn.completed.
  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_preflight_ok" }) + "\n");
  process.stdout.write(JSON.stringify({ type: "item.completed", text: "ok" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "turn.completed",
    usage: { input_tokens: 10, cached_input_tokens: 0, output_tokens: 2, reasoning_output_tokens: 0 },
  }) + "\n");
  process.exit(0);
}

main();
