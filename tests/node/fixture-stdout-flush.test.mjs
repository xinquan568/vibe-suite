// SPDX-License-Identifier: ISC
// Fixture stdout must survive the process that wrote it (vibe-279).
//
// `process.exit` does not wait for stdout to drain. Under the test harness stdout is never the
// terminal, so a write larger than the transport's buffer completes asynchronously and the queued
// tail dies with the process. A fixture built to present a large payload then presents a DIFFERENT
// payload, cut at an offset set by buffer capacity and scheduling rather than by the fixture. The
// suites that consume these fixtures pass either way, which is why this went unnoticed: the failure
// is a silent change in what is being tested, not a red test.
//
// THE TRANSPORT IS A SOCKET, NOT A PIPE. `child_process` with `stdio: "pipe"` hands the child a
// socketpair on Unix, not a FIFO — `fstatSync(1).isSocket()` is true in a spawned child — so the
// capacity in play is a socket buffer that libuv sizes, and which Linux may enlarge beyond the value
// requested. An earlier draft of this file asserted a fixed "64 KiB pipe buffer" floor and argued
// non-vacuity from it. That was wrong twice over: wrong transport, and a constant where a
// measurement was needed. Capacity is therefore MEASURED here, by `truncationProbe`, rather than
// assumed.
//
// THE ORACLE. On POSIX, Node writes stdout synchronously when fd 1 is a FILE and asynchronously
// when it is a socket. The same fixture captured both ways therefore yields the intended payload
// from the file and the truncated payload from the socket, and every row below asserts the two are
// byte-identical. That needs no payload arithmetic and pins no platform constant — it compares a
// fixture against itself.
//
// NON-VACUITY IS MEASURED, NOT ASSUMED. A differential assertion goes green when both sides fit in
// the buffer, so `the transport truncates a writer that exits` probes this platform directly: it
// generates a throwaway writer at each payload size the rows rely on and checks whether
// `process.exit` actually costs it bytes. The 256 KiB size is ASSERTED, because no plausible buffer
// absorbs it. `preflight-hostile.mjs`'s payload is a fixture constant the issue's acceptance names
// by value (65,569 bytes), so it cannot be enlarged to suit the test; where a platform's buffer
// absorbs it, that probe reports the gap as a diagnostic instead of claiming coverage it does not
// have. The rows still assert a true and useful property there — the payload arrives whole — they
// just cannot catch a regression at that size on such a platform.
//
// A SECOND, INDEPENDENT FAMILY. The differential cannot see a lost branch exit, only a lost tail:
// with `process.exit(0)` replaced by `process.exitCode = 0` and nothing else, `preflight-hostile.mjs`
// delivers 131,154 bytes for `--version` both ways — equal, so the differential passes a fixture
// emitting double its payload. `each preflight-hostile.mjs branch emits only its own payload` covers
// that, and it reads the FILE captures deliberately. An earlier draft read the socket captures and
// asserted only the ABSENCE of foreign markers, reasoning that absence is truncation-independent.
// It is the opposite: truncation DELETES the foreign marker, so that draft passed a mutant with both
// `return`s removed (verified — 65,536 bytes, marker gone, assertions green). The file capture is
// whole whatever `process.exit` does, which is what makes this family independent of the first.
//
// WHAT THIS FILE DOES NOT COVER, and why the rows are named rather than globbed:
//   * `sleeper.mjs` ignores SIGTERM and `leaker.mjs` holds an interval, both by design so a deadline
//     can signal them. A suite that enumerated `tests/fixtures/` would hang the CI shard on them.
//   * `record.mjs` is an imported module, not a program.
//   * A payload arriving from a file read or from stdin, in a shape no row here supplies, would
//     evade this suite exactly as the environment-derived payload in `verdict-writer.mjs` evaded the
//     shape grep that first looked for this defect. The criterion is whether the bytes a fixture
//     writes can exceed the transport's buffer, tracing inputs and serialisation — not the shape of
//     the call.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { closeSync, openSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { tmpWorkspace } from "./_tmp.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures");

// Comfortably past any buffer a platform might grant a socketpair — four times the 64 KiB libuv
// requests, twice a Linux-doubled 128 KiB — so the rows driven by an input are non-vacuous
// everywhere rather than only where the buffer is small. It is also well under `ARG_MAX` (1 MiB
// here, shared between argv and the environment), which one of these payloads travels through. A
// 1,000,000-byte value was tried first and is NOT usable: `verdict-writer.mjs` then dies with
// `RangeError: Maximum call stack size exceeded` and exit 7, somewhere above 600,000. The clean exit
// `assertFlushed` demands is what surfaced that, rather than a confusing byte mismatch.
const BIG = "y".repeat(262_144);

// `preflight-hostile.mjs`'s intended payload for `--version`: the header plus `64 * 1024` of noise.
// The issue's acceptance names this number, so the fixture's size is fixed and the test adapts.
const HOSTILE_VERSION_BYTES = 65_569;

// Placeholder for the per-run temp path a fixture's `-o` option receives.
const OUT = "@OUT@";

/** Both captures of one fixture run: through the socket the harness gives it, and through a file. */
function captures(rel, argv, env = {}) {
  const dir = tmpWorkspace("vibe-279-");
  const resolved = argv.map((arg) => (arg === OUT ? path.join(dir, "result.md") : arg));
  const command = [path.join(FIXTURES, rel), ...resolved];
  // `cwd` is the throwaway directory because some fake-codex fixtures write relative to it
  // (`delegate-writer.mjs:15` creates `IMPLEMENTED.txt`), and a suite must not litter the worktree.
  // stdin is `ignore`, matching the harness: a fixture handed an OPEN stdin pipe would have
  // `probeStdin`'s `process.stdin.resume()` holding the event loop, and `process.exitCode` would
  // then hang rather than drain — a different failure from the one under test here.
  const shared = { cwd: dir, env: { ...process.env, ...env }, timeout: 20_000, maxBuffer: 64 * 1024 * 1024 };

  const piped = spawnSync(process.execPath, command, { ...shared, stdio: ["ignore", "pipe", "ignore"] });

  const target = path.join(dir, "capture.bin");
  const fd = openSync(target, "w");
  const direct = spawnSync(process.execPath, command, { ...shared, stdio: ["ignore", fd, "ignore"] });
  closeSync(fd);

  return { socket: piped.stdout ?? Buffer.alloc(0), file: readFileSync(target), piped, direct };
}

/**
 * The differential, plus proof that both runs actually TERMINATED.
 *
 * The exit check is not ceremony. `process.exitCode` ends a process only once nothing keeps its
 * event loop alive, so the failure mode this remedy can introduce is a HANG, not a truncation. A
 * timed-out `spawnSync` reports `status: null` and `error.code: "ETIMEDOUT"` — and two hung runs
 * agree on `null`, so comparing statuses alone would pass a fixture that never exits at all.
 */
function assertFlushed(label, capture, normalise = (buffer) => buffer) {
  for (const [which, result] of [["socket", capture.piped], ["file", capture.direct]]) {
    assert.equal(result.error, undefined,
      `${label}: the ${which} run failed to complete (${result.error?.code}) — ` +
      "a fixture that hangs under process.exitCode fails here, not in the byte comparison");
    assert.equal(result.status, 0, `${label}: the ${which} run exited ${result.status} (signal ${result.signal})`);
  }
  const socket = normalise(capture.socket);
  const file = normalise(capture.file);
  assert.equal(socket.length, file.length,
    `${label}: ${socket.length} bytes arrived through the socket against ${file.length} ` +
    "written to a file — process.exit discarded the queued tail");
  assert.ok(socket.equals(file), `${label}: the captures are the same length but differ in content`);
}

/** Replace the one run-varying token in `pipe-leaker.mjs`'s diagnostic line. */
function withoutPid(buffer) {
  return Buffer.from(buffer.toString("utf8").replace(/grandchild=\d+/g, "grandchild=<pid>"), "utf8");
}

/**
 * Measure on THIS platform whether `process.exit` costs a writer of `bytes` any bytes.
 *
 * A throwaway writer stands in for the fixtures, so the measurement is of the transport rather than
 * of any particular fixture's shape. This is what makes the rows' non-vacuity a fact about the
 * running machine instead of an assumption about buffer sizes.
 */
function truncationProbe(bytes) {
  const dir = tmpWorkspace("vibe-279-probe-");
  const script = path.join(dir, "writer.mjs");
  writeFileSync(script, `process.stdout.write("y".repeat(${bytes}));\nprocess.exit(0);\n`, "utf8");
  const run = spawnSync(process.execPath, [script], {
    cwd: dir, stdio: ["ignore", "pipe", "ignore"], timeout: 20_000, maxBuffer: 64 * 1024 * 1024,
  });
  const delivered = run.stdout ? run.stdout.length : 0;
  return { bytes, delivered, truncated: delivered < bytes };
}

// ---------------------------------------------------------------------------------------------
// Non-vacuity, measured before the rows that depend on it.
// ---------------------------------------------------------------------------------------------

test("the transport truncates a writer that exits, at the payload sizes these rows rely on", (t) => {
  const big = truncationProbe(BIG.length);
  assert.ok(big.truncated,
    `a writer of ${big.bytes} bytes delivered all of them despite process.exit — no plausible ` +
    "socket buffer absorbs that, so either the transport changed or this probe is wrong; the " +
    "input-driven rows below would assert nothing");

  const hostile = truncationProbe(HOSTILE_VERSION_BYTES);
  if (!hostile.truncated) {
    t.diagnostic(
      `this platform delivered all ${hostile.bytes} bytes despite process.exit, so its stdio buffer ` +
      "is larger than preflight-hostile.mjs's payload. The three preflight-hostile rows still " +
      "assert a true property here — the payload arrives whole — but cannot catch a regression at " +
      "that size on this platform. The four input-driven rows cover the defect class regardless.");
  }
});

// ---------------------------------------------------------------------------------------------
// The truncation family. Every row was observed RED against the unfixed fixtures.
// ---------------------------------------------------------------------------------------------

test("preflight-hostile.mjs --version delivers its whole payload through the harness", () => {
  const capture = captures("fake-codex/preflight-hostile.mjs", ["--version"]);
  assertFlushed("preflight-hostile --version", capture);
  assert.equal(capture.file.length, HOSTILE_VERSION_BYTES,
    "the intended payload is no longer the size the issue's acceptance names");
});

test("preflight-hostile.mjs login status delivers its whole payload through the harness", () => {
  // `login status`, not `login`: record.mjs:41 rejects any other login argv with exit 2 and an empty
  // stdout, which would make this row measure 0 bytes both ways and pass with the defect intact.
  assertFlushed("preflight-hostile login status",
    captures("fake-codex/preflight-hostile.mjs", ["login", "status"]));
});

test("preflight-hostile.mjs exec delivers its whole payload through the harness", () => {
  assertFlushed("preflight-hostile exec",
    captures("fake-codex/preflight-hostile.mjs", ["exec", "-o", OUT, "prompt"]));
});

test("verdict-writer.mjs delivers a large verdict text through the harness", () => {
  // The payload is an INPUT, not a literal: neither a shape grep nor payload arithmetic over the
  // source finds this one. A large verdict is a legitimate use — it is what the verdict byte budget
  // exists for — so the defect is latent rather than theoretical.
  assertFlushed("verdict-writer VIBE_TEST_VERDICT_TEXT",
    captures("fake-codex/verdict-writer.mjs", ["exec", "-o", OUT, "prompt"],
      { VIBE_TEST_VERDICT_TEXT: BIG }));
});

test("verdict-writer.mjs delivers a large quota message through the harness", () => {
  // The same site, reached by a second knob. One fix covers both; two rows keep that true.
  assertFlushed("verdict-writer VIBE_TEST_QUOTA_MESSAGE",
    captures("fake-codex/verdict-writer.mjs", ["exec", "-o", OUT, "prompt"],
      { VIBE_TEST_QUOTA: "1", VIBE_TEST_QUOTA_MESSAGE: BIG }));
});

test("rca-analyst.mjs delivers an analysis built from a long prompt line through the harness", () => {
  // Payload from argv: the fixture lifts the first `FILE:` path out of its prompt and echoes it.
  assertFlushed("rca-analyst long FILE: line",
    captures("fake-codex/rca-analyst.mjs", ["exec", "-o", OUT, `FILE: ${BIG}`]));
});

test("pipe-leaker.mjs delivers its diagnostic line through the harness", () => {
  // argv[3] is a mode selector echoed back for diagnostics; anything outside immune/linger takes the
  // exit branch. A short hold keeps the grandchild's lifetime inside the row, and the pid in the
  // line is normalised away because it differs between the two runs.
  assertFlushed("pipe-leaker long mode string", captures("pipe-leaker.mjs", ["100", BIG]), withoutPid);
});

// ---------------------------------------------------------------------------------------------
// The consumer-visible consequence: a truncated NDJSON stream ends mid-token.
// ---------------------------------------------------------------------------------------------

test("verdict-writer.mjs's final event survives the harness as parseable JSON", () => {
  const capture = captures("fake-codex/verdict-writer.mjs", ["exec", "-o", OUT, "prompt"],
    { VIBE_TEST_VERDICT_TEXT: BIG });
  const lines = capture.socket.toString("utf8").trimEnd().split("\n");
  // At the defective commit this throws `Unterminated string in JSON`: the last line is cut inside
  // the verdict string, which is exactly what an NDJSON reader sees.
  const last = JSON.parse(lines.at(-1));
  assert.equal(last.type, "turn.completed",
    "the stream's last event is not the terminal one — the tail was lost");
});

// ---------------------------------------------------------------------------------------------
// The branch-identity family, read from the FILE captures so truncation cannot delete the evidence.
// ---------------------------------------------------------------------------------------------

test("each preflight-hostile.mjs branch emits only its own payload", () => {
  const fixture = "fake-codex/preflight-hostile.mjs";
  const version = captures(fixture, ["--version"]).file.toString("utf8");
  const login = captures(fixture, ["login", "status"]).file.toString("utf8");
  const exec = captures(fixture, ["exec", "-o", OUT, "prompt"]).file.toString("utf8");

  // A lost `return` appends the next branch's output, which these reject at any payload size.
  assert.ok(!version.includes("not json at all"), "--version fell through into the exec branch");
  assert.ok(!version.includes("session state:"), "--version fell through into the login branch");
  assert.ok(!login.includes("not json at all"), "login status fell through into the exec branch");
  assert.ok(!exec.includes("session state:"), "the exec path emitted the login branch's payload");

  // The positives: each branch's own terminator, which only the whole capture can show.
  assert.ok(login.startsWith("session state: "), "login status no longer emits its own prefix");
  assert.ok(exec.endsWith("not json at all\n"), "the exec branch no longer ends with its terminator");
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
