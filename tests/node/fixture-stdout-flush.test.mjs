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
// NON-VACUITY IS MEASURED, NOT ASSUMED, AND IT DIFFERS BY PLATFORM. A differential assertion goes
// green when both sides fit in the buffer, so `the transport truncates a writer that exits` probes
// this machine directly: it generates a throwaway writer — no argv, so any size — and checks whether
// `process.exit` actually costs it bytes.
//
// What that probe has measured, and it is not symmetric:
//
//   * macOS: 65,569 is cut to 65,536, and 130,000 likewise. Every row here is a live regression
//     probe — revert any of the four fixtures and its rows go red.
//   * Ubuntu (this repo's CI): 65,569 arrives WHOLE, 130,000 arrives WHOLE, 262,144 is truncated on
//     most runs and 1,048,576 on nearly all — the measured numbers are below (vibe-327).
//
// **So on CI none of the seven differential rows can catch a regression, and that cannot be fixed by
// choosing a bigger input.** Linux caps a SINGLE argv or environment string at `MAX_ARG_STRLEN` —
// 32 pages, 131,072 bytes — independently of `ARG_MAX`, and `spawnSync` raises `E2BIG` past it. The
// cap therefore sits BELOW the buffer threshold: no payload delivered through argv or the
// environment can exceed what Linux absorbs. `preflight-hostile.mjs`'s 65,569 is a fixture constant
// the issue's acceptance names by value, so it cannot be raised either.
//
// What the rows still do on such a platform is assert a true and useful property — the payload
// arrives whole — which is worth having; they simply are not regression probes there. The probe
// prints which rows are which on the running machine, every run, so the difference is never implied.
//
// The regression power that DOES survive on both platforms sits in the convention guards at the
// bottom of this file: `gate-oversized.mjs` writes 289,943 bytes from a literal, above the 262,144
// threshold at which Linux starts truncating, so a `process.exit` reintroduced there goes red on nearly
// every run (the threshold drains occasionally — the measurement is below). Giving one of the four
// subjects a payload route that is not argv-limited — a file, say — would extend that to them, and
// is a fixture-design change deliberately left out of this issue.
//
// THE HARD ASSERTION PROBES WELL ABOVE THE THRESHOLD, AND RETRIES. 262,144 is where truncation
// STARTS under load on Linux, not a size the socket can never drain before `exit` returns. An earlier
// version of this file asserted a single probe at 262,144 "because both platforms truncate it"; they
// usually do. Across the `test shard 0` logs of 20 CI runs (80 jobs, Node 18 and 24) a 262,144-byte
// writer arrived WHOLE in 12 of 96 invocations, and this test went red for changes that touched
// nothing near it — first on #322 (job 104821809756), then #325 (job 105036683165) and the #317
// measurement (job 105035586391); reruns inside jobs masked most of the rest. A 1 MiB writer arrived
// whole once in 22 (job 105090065422). So the probe the test ASSERTS is 1 MiB AND it may take up to
// `ASSERT_ATTEMPTS` runs, passing on the first truncation: one drained run is scheduling, five in a
// row would mean the transport changed — and then this test fails loudly instead of passing emptily.
// 262,144 stays as the documented threshold, reported by the diagnostic below and asserted by nothing
// (vibe-327).
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

// The payload the input-driven rows pass through argv or the environment. Bounded above by Linux's
// `MAX_ARG_STRLEN` (131,072 bytes for one string; `spawnSync` raises `E2BIG` past it) with headroom,
// and as far above a 64 KiB buffer as that ceiling allows. Two larger values were tried and are NOT
// usable: 262,144 raises `E2BIG` on Linux, and 1,000,000 additionally kills `verdict-writer.mjs`
// with `RangeError: Maximum call stack size exceeded` above roughly 600,000 bytes. The clean-exit
// check in `assertFlushed` is what surfaced both, instead of a confusing byte mismatch.
const BIG = "y".repeat(130_000);

// The hard assertion's writer: 1 MiB, four times the Linux threshold, because a writer AT the threshold
// arrived whole in 12 of 96 CI invocations and even this size once in 22 (vibe-327; the header has the
// measurement). It travels in a generated script rather than argv, so no per-string limit applies to it.
const BEYOND_ANY_BUFFER = 1_048_576;
// How many times the hard assertion may probe before concluding the transport no longer truncates.
// One drained run is scheduling; this many in a row would be a changed transport.
const ASSERT_ATTEMPTS = 5;
// Where truncation STARTS under load on Linux — reported by the diagnostic loop, asserted by nothing.
const TRUNCATION_THRESHOLD_BYTES = 262_144;

// `preflight-hostile.mjs`'s intended payload for `--version`: the header plus `64 * 1024` of noise.
// The issue's acceptance names this number, so the fixture's size is fixed and the test adapts.
const HOSTILE_VERSION_BYTES = 65_569;

// vibe-317: the FILE-BORNE payload. It reaches the subject through a file the fixture reads, so no argv or
// environment limit applies to it. It is deliberately far ABOVE the transport's truncation threshold: at
// exactly 262,144 bytes the row was measured on CI's ubuntu jobs to fail a reintroduced `process.exit` on
// 3 runs in 4 — the pipe occasionally drained the whole payload before exit returned — so the threshold is
// where truncation STARTS under load, not a size the pipe can never drain. At 1 MiB the mutant was measured
// to fail this row on every ubuntu shard-0 job and locally on macOS (the probe's hard assertion measures only
// its own throwaway writer; a row's liveness is the mutation measurement, never inferred). The file capture
// asserts the whole payload arrived, so the size cannot silently shrink.
const FILE_PAYLOAD_BYTES = 1_048_576;

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

/**
 * Probe up to `attempts` times and stop at the first truncation (vibe-327).
 *
 * A single probe at the threshold drains whole about one run in eight on Linux CI; one drained run says
 * nothing about the transport, `attempts` in a row would. `attempts` is the record of every delivered
 * size, in order, so a failure message can show them and a diagnostic can count how often the retry was
 * needed. `probe` is injectable so the stop-and-record behaviour is tested in-process, without spawning.
 */
function truncatesWithin(bytes, attempts, probe = truncationProbe) {
  if (!(Number.isInteger(attempts) && attempts >= 1)) throw new RangeError(`attempts must be a positive integer, got ${attempts}`);
  const delivered = [];
  for (let i = 0; i < attempts; i += 1) {
    const run = probe(bytes);
    delivered.push(run.delivered);
    if (run.truncated) return { bytes, attempts: delivered, truncated: true };
  }
  return { bytes, attempts: delivered, truncated: false };
}

// ---------------------------------------------------------------------------------------------
// Non-vacuity, measured before the rows that depend on it.
// ---------------------------------------------------------------------------------------------

test("the transport truncates a writer that exits, at the payload sizes these rows rely on", (t) => {
  // The one hard assertion: if the transport stops truncating even here, the differential oracle
  // rests on nothing and every row above would be passing emptily.
  const beyond = truncatesWithin(BEYOND_ANY_BUFFER, ASSERT_ATTEMPTS);
  assert.ok(beyond.truncated,
    `a writer of ${beyond.bytes} bytes delivered all of them despite process.exit on ${beyond.attempts.length} ` +
    `consecutive attempts (delivered: ${beyond.attempts.join(", ")}) — one drained run is scheduling, this many ` +
    "means the transport changed or this probe is wrong; either way the rows above assert nothing about draining");
  t.diagnostic(`the hard assertion truncated on attempt ${beyond.attempts.length} of ${ASSERT_ATTEMPTS} at ` +
    `${beyond.bytes} bytes (delivered ${beyond.attempts.join(", ")})`);
  // The documented threshold: where truncation starts under load. Reported, never asserted — a whole
  // delivery here is exactly the drain the retrying assertion above absorbs.
  const threshold = truncationProbe(TRUNCATION_THRESHOLD_BYTES);
  t.diagnostic(threshold.truncated
    ? `the documented threshold, ${threshold.bytes} bytes, truncated this run (delivered ${threshold.delivered})`
    : `the documented threshold, ${threshold.bytes} bytes, arrived whole this run — the drain the retrying assertion absorbs`);

  // The rest is measurement, reported rather than asserted, because a platform with a buffer larger
  // than a given payload is not a defect — it just means that row cannot catch a regression there.
  for (const [bytes, rows] of [
    [HOSTILE_VERSION_BYTES, "the three preflight-hostile rows"],
    [BIG.length, "the four input-driven rows"],
    [FILE_PAYLOAD_BYTES, "the file-borne rca-analyst row (vibe-317)"],
  ]) {
    const probe = truncationProbe(bytes);
    t.diagnostic(probe.truncated
      ? `truncates at ${probe.bytes} bytes (delivered ${probe.delivered}) — ${rows} are live regression probes here`
      : `delivers all ${probe.bytes} bytes despite process.exit, so this platform's stdio buffer exceeds `
        + `that payload: ${rows} assert a true property here — the payload arrives whole — but cannot `
        + "catch a regression at that size. Recorded so the gap is visible rather than implied.");
  }
});

test("truncatesWithin stops at the first truncation and records every attempt (vibe-327)", () => {
  // In-process: a fake probe replaces the spawning one, so this tests the retry contract the hard
  // assertion relies on — stop at the first truncation, exhaust the attempts otherwise, record each size.
  const fake = (outcomes) => {
    const calls = [];
    const probe = (bytes) => {
      const truncated = outcomes[calls.length];
      calls.push(bytes);
      return { bytes, delivered: truncated ? bytes - 1 : bytes, truncated };
    };
    return { probe, calls };
  };
  let f = fake([false, false, true]);
  assert.deepEqual(truncatesWithin(7, 5, f.probe), { bytes: 7, attempts: [7, 7, 6], truncated: true });
  assert.deepEqual(f.calls, [7, 7, 7], "stops at the first truncation: three calls, not five");
  f = fake([false, false, false, false, false]);
  assert.deepEqual(truncatesWithin(7, 5, f.probe), { bytes: 7, attempts: [7, 7, 7, 7, 7], truncated: false });
  assert.equal(f.calls.length, 5, "exhausts every attempt before concluding the transport drained");
  f = fake([true]);
  assert.deepEqual(truncatesWithin(7, 5, f.probe), { bytes: 7, attempts: [6], truncated: true });
  assert.equal(f.calls.length, 1, "a first-attempt truncation costs one probe");
  for (const bad of [0, -1, 2.5, NaN, "5"]) assert.throws(() => truncatesWithin(7, bad, f.probe), RangeError);
});

test("the hard assertion probes through truncatesWithin with at least five attempts (vibe-327)", () => {
  // A source pin, because the retry cannot be exercised on demand: macOS truncates every probe, and on
  // Linux only load drains one. Dropping the retry (attempts 1, or a direct truncationProbe call) would
  // survive every local run and reappear as the flake this guards against.
  const self = readFileSync(fileURLToPath(import.meta.url), "utf8");
  assert.ok(ASSERT_ATTEMPTS >= 5, `ASSERT_ATTEMPTS is ${ASSERT_ATTEMPTS}; five is the measured floor`);
  assert.match(self, /const beyond = truncatesWithin\(BEYOND_ANY_BUFFER, ASSERT_ATTEMPTS\);/, "the hard assertion goes through the retrying helper");
  assert.ok(BEYOND_ANY_BUFFER >= 4 * TRUNCATION_THRESHOLD_BYTES, "the asserted size stays well above the threshold");
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

test("rca-analyst.mjs delivers a FILE-BORNE payload through the harness — live on Linux too (vibe-317)", () => {
  // Payload from a file the fixture reads (`PAYLOAD-FILE:`), not from argv: no `MAX_ARG_STRLEN` bound, so
  // the wire carries four times the 262,144-byte threshold at which truncation starts under load (the size
  // the hard assertion above also probes, with retries). A reintroduced `process.exit(0)` in the fixture fails this row on every
  // platform — measured on macOS locally and on every ubuntu shard-0 job in CI.
  const dir = tmpWorkspace("vibe-317-");
  const payloadFile = path.join(dir, "payload.txt");
  writeFileSync(payloadFile, "x".repeat(FILE_PAYLOAD_BYTES), "utf8");
  const capture = captures("fake-codex/rca-analyst.mjs", ["exec", "-o", OUT, `PAYLOAD-FILE: ${payloadFile}`]);
  assert.ok(capture.file.length >= FILE_PAYLOAD_BYTES,
    `the file capture must carry the whole payload: ${capture.file.length} bytes < ${FILE_PAYLOAD_BYTES}`);
  assertFlushed("rca-analyst file-borne payload", capture);
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
