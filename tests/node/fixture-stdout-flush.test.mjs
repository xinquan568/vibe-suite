// SPDX-License-Identifier: ISC
// Fixture stdout must survive the process that wrote it (vibe-279).
//
// `process.exit` does not wait for stdout to drain. When stdout is a pipe — always, under the test
// harness — a write larger than the pipe buffer completes asynchronously and the queued tail dies
// with the process. A fixture built to present a large payload then presents a DIFFERENT payload,
// cut at an offset set by buffer size and scheduling rather than by the fixture. The suites that
// consume these fixtures pass either way, which is why this went unnoticed: the failure is a silent
// change in what is being tested, not a red test.
//
// THE ORACLE. On POSIX, Node writes stdout synchronously when fd 1 is a FILE and asynchronously
// when it is a PIPE. The same fixture captured both ways therefore yields the intended payload from
// the file and the truncated payload from the pipe, and every row below asserts the two are
// byte-identical. That needs no payload arithmetic and pins no platform constant — it compares a
// fixture against itself.
//
// NON-VACUITY. A differential assertion goes green when both sides are small, so every row also
// asserts the capture exceeds 64 KiB. Stated as a limit: that floor is the observed macOS/Linux
// pipe-buffer default, so on a platform with a larger buffer these rows would pass without
// exercising the defect. The floor keeps a row honest about its own relevance; it does not make the
// row portable.
//
// A SECOND, INDEPENDENT FAMILY. The differential is provably blind to branch fallthrough. With
// `process.exit(0)` replaced by `process.exitCode = 0` and nothing else, `preflight-hostile.mjs`
// delivers 131,154 bytes for `--version` both piped and to a file — equal, so a purely differential
// suite would pass a fixture emitting double its intended payload. `each preflight-hostile.mjs
// branch emits only its own payload` catches that, and unlike an exact-byte-total assertion it
// survives a legitimate payload-size edit.
//
// WHAT THIS FILE DOES NOT COVER, and why the rows are named rather than globbed:
//   * `sleeper.mjs` ignores SIGTERM and `leaker.mjs` holds an interval, both by design so a deadline
//     can signal them. A suite that enumerated `tests/fixtures/` would hang the CI shard on them.
//   * `record.mjs` is an imported module, not a program.
//   * A payload arriving from a file read or from stdin, in a shape no row here supplies, would
//     evade this suite exactly as the environment-derived payload in `verdict-writer.mjs` evaded the
//     shape grep that first looked for this defect. The criterion is whether the bytes a fixture
//     writes can exceed a pipe buffer, tracing inputs and serialisation — not the shape of the call.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { closeSync, mkdtempSync, openSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures");

// The observed macOS/Linux pipe-buffer default. A capture at or below this could be delivered whole
// by a synchronous write, so a row that does not clear it proves nothing about draining.
const PIPE_BUFFER_FLOOR = 64 * 1024;

// Large enough that any single-buffer write is impossible, and not a round multiple of the buffer,
// so an off-by-one in a boundary would show as a mismatch rather than cancel out.
const BIG = "y".repeat(100_000);

// Placeholder for the per-run temp path a fixture's `-o` option receives.
const OUT = "@OUT@";

/**
 * Run one fixture twice — stdout on a pipe, stdout on a file — and return both captures.
 *
 * `cwd` is a fresh temp directory because some fake-codex fixtures write relative to it
 * (`delegate-writer.mjs:15` creates `IMPLEMENTED.txt`), and a suite must not litter the worktree.
 * stdin is `ignore`, matching the harness: a fixture handed an OPEN stdin pipe would have
 * `probeStdin`'s `process.stdin.resume()` holding the event loop, and `process.exitCode` would then
 * hang rather than drain — a different failure from the one under test here.
 */
function captures(rel, argv, env = {}) {
  const dir = mkdtempSync(path.join(tmpdir(), "vibe-279-"));
  const resolved = argv.map((arg) => (arg === OUT ? path.join(dir, "result.md") : arg));
  const command = [path.join(FIXTURES, rel), ...resolved];
  const shared = {
    cwd: dir,
    env: { ...process.env, ...env },
    timeout: 20_000,
    maxBuffer: 64 * 1024 * 1024,
  };

  const piped = spawnSync(process.execPath, command, { ...shared, stdio: ["ignore", "pipe", "ignore"] });

  const target = path.join(dir, "capture.bin");
  const fd = openSync(target, "w");
  const direct = spawnSync(process.execPath, command, { ...shared, stdio: ["ignore", fd, "ignore"] });
  closeSync(fd);

  return {
    pipe: piped.stdout ?? Buffer.alloc(0),
    file: readFileSync(target),
    pipeStatus: piped.status,
    fileStatus: direct.status,
  };
}

/**
 * The differential plus its non-vacuity floor, with the numbers in the failure message.
 *
 * `normalise` exists for one fixture whose payload legitimately varies between runs: `pipe-leaker.mjs`
 * echoes its grandchild's pid. Two runs then differ in content, and — worse — differ in LENGTH
 * whenever the two pids have different digit counts, which would make the row flake rather than
 * fail. Normalising the pid away is not a loophole: it substitutes a fixed-width placeholder for a
 * run-varying token, and no amount of normalising turns a capture cut at a buffer boundary into a
 * whole one. Rows without run-varying output pass the identity function and are compared verbatim.
 */
function assertFlushed(label, capture, normalise = (buffer) => buffer) {
  const pipe = normalise(capture.pipe);
  const file = normalise(capture.file);
  assert.equal(capture.pipeStatus, capture.fileStatus,
    `${label}: the two runs exited differently (${capture.pipeStatus} piped, ${capture.fileStatus} to a file) — ` +
    "they are not the same execution and the captures cannot be compared");
  assert.ok(file.length > PIPE_BUFFER_FLOOR,
    `${label}: the intended payload is only ${file.length} bytes, at or below the ` +
    `${PIPE_BUFFER_FLOOR}-byte floor — this row would pass without exercising draining at all`);
  assert.equal(pipe.length, file.length,
    `${label}: ${pipe.length} bytes arrived through the pipe against ${file.length} ` +
    "written to a file — process.exit discarded the queued tail");
  assert.ok(pipe.equals(file),
    `${label}: the captures are the same length but differ in content`);
}

/** Replace the one run-varying token in `pipe-leaker.mjs`'s diagnostic line. */
function withoutPid(buffer) {
  return Buffer.from(buffer.toString("utf8").replace(/grandchild=\d+/g, "grandchild=<pid>"), "utf8");
}

// ---------------------------------------------------------------------------------------------
// The truncation family. Each row is RED at the commit that introduced this file.
// ---------------------------------------------------------------------------------------------

test("preflight-hostile.mjs --version delivers its whole payload through a pipe", () => {
  assertFlushed("preflight-hostile --version",
    captures("fake-codex/preflight-hostile.mjs", ["--version"]));
});

test("preflight-hostile.mjs login status delivers its whole payload through a pipe", () => {
  // `login status`, not `login`: record.mjs:41 rejects any other login argv with exit 2 and an empty
  // stdout, which would make this row measure 0 bytes both ways and pass with the defect intact.
  assertFlushed("preflight-hostile login status",
    captures("fake-codex/preflight-hostile.mjs", ["login", "status"]));
});

test("preflight-hostile.mjs exec delivers its whole payload through a pipe", () => {
  const capture = captures("fake-codex/preflight-hostile.mjs", ["exec", "-o", OUT, "prompt"]);
  assertFlushed("preflight-hostile exec", capture);
  // The intended payload ends with the exec branch's own terminator; its arrival is what the
  // differential is asserting, and naming it here says what "whole" means for this branch.
  assert.ok(capture.file.toString("utf8").endsWith("not json at all\n"),
    "the exec branch's intended payload no longer ends with its terminator");
});

test("verdict-writer.mjs delivers a large verdict text through a pipe", () => {
  // The payload is an INPUT, not a literal: neither a shape grep nor payload arithmetic over the
  // source finds this one. A large verdict is a legitimate use — it is what the verdict byte budget
  // exists for — so the defect is latent rather than theoretical.
  assertFlushed("verdict-writer VIBE_TEST_VERDICT_TEXT",
    captures("fake-codex/verdict-writer.mjs", ["exec", "-o", OUT, "prompt"],
      { VIBE_TEST_VERDICT_TEXT: BIG }));
});

test("verdict-writer.mjs delivers a large quota message through a pipe", () => {
  // The same site, reached by a second knob. One fix covers both; two rows keep that true.
  assertFlushed("verdict-writer VIBE_TEST_QUOTA_MESSAGE",
    captures("fake-codex/verdict-writer.mjs", ["exec", "-o", OUT, "prompt"],
      { VIBE_TEST_QUOTA: "1", VIBE_TEST_QUOTA_MESSAGE: BIG }));
});

test("rca-analyst.mjs delivers an analysis built from a long prompt line through a pipe", () => {
  // Payload from argv: the fixture lifts the first `FILE:` path out of its prompt and echoes it.
  assertFlushed("rca-analyst long FILE: line",
    captures("fake-codex/rca-analyst.mjs", ["exec", "-o", OUT, `FILE: ${BIG}`]));
});

test("pipe-leaker.mjs delivers its diagnostic line through a pipe", () => {
  // argv[3] is a mode selector echoed back for diagnostics; anything outside immune/linger takes the
  // exit branch. A short hold keeps the grandchild's lifetime inside the row, and the pid in the
  // line is normalised away because it differs between the two runs.
  assertFlushed("pipe-leaker long mode string", captures("pipe-leaker.mjs", ["100", BIG]), withoutPid);
});

// ---------------------------------------------------------------------------------------------
// The consumer-visible consequence: a truncated NDJSON stream ends mid-token.
// ---------------------------------------------------------------------------------------------

test("verdict-writer.mjs's final event survives the pipe as parseable JSON", () => {
  const capture = captures("fake-codex/verdict-writer.mjs", ["exec", "-o", OUT, "prompt"],
    { VIBE_TEST_VERDICT_TEXT: BIG });
  const lines = capture.pipe.toString("utf8").trimEnd().split("\n");
  // At the defective commit this throws `Unterminated string in JSON at position 81920`: the last
  // line is cut inside the verdict string, which is exactly what an NDJSON reader sees.
  const last = JSON.parse(lines.at(-1));
  assert.equal(last.type, "turn.completed",
    "the stream's last event is not the terminal one — the tail was lost");
});

// ---------------------------------------------------------------------------------------------
// The branch-identity family. Green before the fix and after it: these rows exist because the
// differential above cannot see a lost branch exit, only a lost tail.
// ---------------------------------------------------------------------------------------------

test("each preflight-hostile.mjs branch emits only its own payload", () => {
  const fixture = "fake-codex/preflight-hostile.mjs";
  const version = captures(fixture, ["--version"]).pipe.toString("utf8");
  const login = captures(fixture, ["login", "status"]).pipe.toString("utf8");
  const exec = captures(fixture, ["exec", "-o", OUT, "prompt"]).pipe.toString("utf8");

  // Absence-only, so truncation cannot make these pass or fail: a lost `return` shows up as a
  // foreign marker in the capture, at any payload size.
  assert.ok(!version.includes("not json at all"),
    "--version fell through into the exec branch");
  assert.ok(!version.includes("session state:"),
    "--version fell through into the login branch");
  assert.ok(!login.includes("not json at all"),
    "login status fell through into the exec branch");
  assert.ok(!exec.includes("session state:"),
    "the exec path emitted the login branch's payload");

  // One positive that truncation cannot affect, since it reads the head of the capture.
  assert.ok(login.startsWith("session state: "),
    "login status no longer emits its own prefix");
});

// ---------------------------------------------------------------------------------------------
// The convention guard. Both fixtures already set `process.exitCode`; these rows are green before
// this change and after it, and exist so a reintroduced `process.exit` at either site goes red.
// ---------------------------------------------------------------------------------------------

test("gate-verbose.mjs, which already holds the convention, stays flushed", () => {
  assertFlushed("gate-verbose", captures("fake-codex/gate-verbose.mjs", ["exec", "-o", OUT, "prompt"]));
});

test("gate-oversized.mjs, which already holds the convention, stays flushed", () => {
  assertFlushed("gate-oversized", captures("fake-codex/gate-oversized.mjs", ["exec", "-o", OUT, "prompt"]));
});
