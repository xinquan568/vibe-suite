#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake codex that is installed but not signed in (E1.3 / vibe-13). Its auth output deliberately
// contains a credential-shaped token: the probe must classify and DISCARD this text — if the
// token ever appears in preflight output, the non-echo rule is broken and the test fails.

import { writeProbe } from "./record.mjs";

function main() {
  writeProbe({ fixture: "preflight-authless" });
  const argv = process.argv.slice(2);

  if (argv[0] === "--version") {
    process.stdout.write("codex-cli 0.0.7\n");
    process.exit(0);
  }
  if (argv[0] === "login") {
    process.stderr.write("Not logged in. Run `codex login`. last-token=sk-HOSTILE-CREDENTIAL-LEAK\n");
    process.exit(1);
  }
  // exec without auth: the exit-0-with-turn.failed shape the runner exists to absorb.
  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_authless" }) + "\n");
  process.stdout.write(JSON.stringify({ type: "turn.failed", error: "401 unauthorized" }) + "\n");
  process.exit(0);
}

main();
