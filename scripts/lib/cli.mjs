// SPDX-License-Identifier: ISC
// Shared shape of every Node entry point under scripts/ (M6 / vibe-218).
//
// Six CLIs carried the same three things by copy: a `UsageError` class, the `main().then(...).catch(...)`
// tail that maps a resolved code to `process.exitCode` and an unexpected rejection to a named stderr
// line and exit 1, and small argv/stdout helpers. One copy drifts from the next; this module is the
// one place. The two hooks (`stop-review-gate-hook.mjs`, `session-lifecycle-hook.mjs`) are NOT callers:
// a crashed hook exits 0 by contract, and the Stop hook awaits an event emission after `main()` —
// their tails stay their own.

/** A caller mistake reported as usage text and exit 2 by the CLI's own `main`; never a stack trace. */
export class UsageError extends Error {}

/**
 * Run `main()` as a CLI: a resolved exit code becomes `process.exitCode`; an unexpected rejection is
 * written to stderr as `<name>: <stack>` and becomes exit 1. Never calls `process.exit()`, so pending
 * stdout flushes and `finally` blocks complete. Returns the promise so a caller may await it.
 */
export function runMain(main, name) {
  return main()
    .then((code) => { process.exitCode = code; })
    .catch((error) => {
      process.stderr.write(`${name}: ${error?.stack ?? error}\n`);
      process.exitCode = 1;
    });
}

/** The last non-empty line of a child's stdout parsed as JSON, or `null` when there is none or it does not parse. */
export function parseLastJsonLine(stdout) {
  const line = String(stdout ?? "").trim().split("\n").filter(Boolean).at(-1);
  try {
    return line ? JSON.parse(line) : null;
  } catch {
    return null;
  }
}

/** The value following `argv[index]` for `flag`, or a `UsageError` naming the flag. The caller advances `index`. */
export function readValue(argv, index, flag) {
  const value = argv[index + 1];
  if (value === undefined) throw new UsageError(`${flag} expects a value`);
  return value;
}
