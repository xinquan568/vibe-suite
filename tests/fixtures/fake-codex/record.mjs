// SPDX-License-Identifier: ISC
// Shared probe for the fake-codex fixtures (E1.1 / vibe-11).
//
// Every fixture records what the runner actually did to it — the argv it was handed and whether its
// stdin was at EOF — into the JSON file named by `VIBE_TEST_PROBE`. Assertions then read that file
// instead of inferring behaviour from the runner's own output, which is the thing under test.
//
// stdin is probed rather than assumed. `/dev/null` yields EOF on the first read; a pipe the runner
// forgot to close yields nothing and never ends. Reading with an explicit timer distinguishes the
// two without hanging the suite, which a bare `cat` would do.

import { writeFileSync } from "node:fs";

// Options the real CLI accepts, per `codex exec --help` and `codex exec resume --help` on
// codex-cli 0.144.6. Round 1's fixture accepted any argv, which is why it never noticed the runner
// passing `-s` to `exec resume` — a command the real binary rejects. A hermetic fixture that accepts
// anything tests the runner against an imaginary CLI.
const EXEC_OPTIONS = new Set(["-s", "--sandbox", "-c", "--config", "-m", "--model", "--json",
  "--skip-git-repo-check", "-o", "--output-last-message", "--output-schema", "-i", "--image"]);
const RESUME_OPTIONS = new Set(["-c", "--config", "-m", "--model", "--json",
  "--skip-git-repo-check", "-o", "--output-last-message", "--output-schema", "-i", "--image",
  "--last", "--all"]);

/** Reject argv the real CLI would reject, so a grammar error fails here instead of in production. */
export function assertArgvContract(argv) {
  const isResume = argv[0] === "exec" && argv[1] === "resume";
  const allowed = isResume ? RESUME_OPTIONS : EXEC_OPTIONS;
  for (const arg of argv) {
    if (!arg.startsWith("-") || arg === "--") continue;
    if (!allowed.has(arg)) {
      process.stderr.write(
        `fake-codex: '${arg}' is not accepted by \`codex ${isResume ? "exec resume" : "exec"}\`\n`);
      process.exit(2);
    }
  }
}

export function probeStdin(timeoutMs = 1000) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    };
    const timer = setTimeout(() => finish("open"), timeoutMs);
    process.stdin.on("end", () => finish("eof"));
    process.stdin.on("error", () => finish("error"));
    process.stdin.resume();
  });
}

/** Announce this process immediately, before any awaiting, so a test can assert on the grandchild. */
export function announcePid() {
  const target = process.env.VIBE_TEST_PID_FILE;
  if (target) writeFileSync(target, String(process.pid), "utf8");
}

export function writeProbe(extra = {}) {
  const argv = process.argv.slice(2);
  const target = process.env.VIBE_TEST_PROBE;
  if (target) writeFileSync(target, JSON.stringify({ argv, ...extra }, null, 2));
  assertArgvContract(argv);
}
