// SPDX-License-Identifier: ISC
// scripts/lib/cli.mjs — the shared CLI shape (M6 / vibe-218).
import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { UsageError, parseLastJsonLine, readValue } from "../../scripts/lib/cli.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CLI = path.resolve(HERE, "..", "..", "scripts", "lib", "cli.mjs");

function runMainIn(body) {
  // process.exitCode is only observable from outside the process, so drive runMain in a child.
  const script = `import { runMain } from ${JSON.stringify(CLI)}; ${body}`;
  return spawnSync(process.execPath, ["--input-type=module", "-e", script], { encoding: "utf8" });
}

test("runMain: a resolved code becomes the exit code and nothing is written", () => {
  const r = runMainIn(`runMain(async () => 3, "probe");`);
  assert.equal(r.status, 3); assert.equal(r.stderr, "");
});

test("runMain: a rejection is a named stderr line and exit 1", () => {
  const r = runMainIn(`runMain(async () => { throw new Error("boom"); }, "probe");`);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /^probe: Error: boom/);
});

test("runMain: a code of 0 is exit 0", () => {
  assert.equal(runMainIn(`runMain(async () => 0, "probe");`).status, 0);
});

test("parseLastJsonLine: last non-empty line wins; trailing newlines and blank lines are ignored", () => {
  assert.deepEqual(parseLastJsonLine('{"a":1}\n{"b":2}\n\n'), { b: 2 });
  assert.deepEqual(parseLastJsonLine("noise\n{\"ok\":true}"), { ok: true });
});

test("parseLastJsonLine: no line, or a last line that is not JSON, is null", () => {
  assert.equal(parseLastJsonLine(""), null);
  assert.equal(parseLastJsonLine(undefined), null);
  assert.equal(parseLastJsonLine('{"a":1}\nnot json'), null);
});

test("readValue: returns the following argv entry; a missing one is a UsageError naming the flag", () => {
  assert.equal(readValue(["--tz", "UTC"], 0, "--tz"), "UTC");
  assert.throws(() => readValue(["--tz"], 0, "--tz"), (e) => e instanceof UsageError && e.message === "--tz expects a value");
});
