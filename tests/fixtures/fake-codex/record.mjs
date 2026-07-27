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

export function writeProbe(extra = {}) {
  const target = process.env.VIBE_TEST_PROBE;
  if (!target) return;
  writeFileSync(target, JSON.stringify({ argv: process.argv.slice(2), ...extra }, null, 2));
}
