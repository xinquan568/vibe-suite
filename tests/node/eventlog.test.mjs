// SPDX-License-Identifier: ISC
// The event log's writer (vibe-207 / grill M5).
//
// The contract these tests hold the module to is the issue's, and property 1 is the one that shapes
// the whole module: **observability never affects the operation observed**. `emit` therefore has no
// failing path a caller can see — it reports `false` and moves on, whatever went wrong. Several
// tests below exist only to prove that a failure a reasonable implementation would raise on is
// swallowed instead.
//
// Retention is NOT tested here and is not in this module: bounded retention under concurrent writers
// is #266. `EVENT_LOG_MAX_BYTES` exists and is measured against, but nothing trims.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { appendFileSync, chmodSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

import {
  emit, eventLogPath, tailRecords, EVENT_LOG_MAX_BYTES, EVENT_LOG_NAME,
  EVENT_LOG_TAIL_MAX_BYTES, STATE_DIRNAME,
} from "../../scripts/lib/eventlog.mjs";
import { EVENT_LINE_MAX } from "../../scripts/lib/write.mjs";
import { STATE_DIRNAME as STORE_STATE_DIRNAME } from "../../scripts/lib/jobs.mjs";

const mode = (p) => statSync(p).mode & 0o777;
const ws = () => tmpWorkspace("eventlog-");
const readRecords = (workspace) =>
  readFileSync(eventLogPath(workspace), "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));

// ------------------------------------------------------------------------------- the record shape

test("emit writes one NDJSON record carrying ts, component, event and detail (vibe-207)", async () => {
  const workspace = ws();
  const before = Date.now();
  assert.equal(await emit(workspace, { component: "runner", event: "dispatch.start",
    detail: { kind: "exec", background: true } }), true, "a writable workspace accepts the record");

  const [record] = readRecords(workspace);
  assert.equal(record.component, "runner");
  assert.equal(record.event, "dispatch.start");
  assert.deepEqual(record.detail, { kind: "exec", background: true });
  assert.ok(Date.parse(record.ts) >= before - 1000 && Date.parse(record.ts) <= Date.now() + 1000,
    "ts is the wall clock at emission — metadata, not a sequence number");
});

test("jobId is carried when there is one and the KEY IS ABSENT when there is not (vibe-207)", async () => {
  const workspace = ws();
  await emit(workspace, { component: "runner", event: "dispatch.finalise", jobId: "abc123", detail: {} });
  await emit(workspace, { component: "hook", event: "hook.report", detail: {} });

  const [withJob, withoutJob] = readRecords(workspace);
  assert.equal(withJob.jobId, "abc123", "correlation is the only identity the suite carries across processes");
  assert.equal("jobId" in withoutJob, false,
    "absent, not null — a null would read as 'this event had no job', which is a different claim from 'not applicable'");
});

test("records accumulate in file order, one line each (vibe-207)", async () => {
  const workspace = ws();
  for (const n of [1, 2, 3]) await emit(workspace, { component: "jobs", event: "prune.action", detail: { n } });
  const raw = readFileSync(eventLogPath(workspace), "utf8");
  assert.equal(raw.split("\n").filter(Boolean).length, 3, "three lines, not three records on one line");
  assert.deepEqual(readRecords(workspace).map((r) => r.detail.n), [1, 2, 3]);
});

// ---------------------------------------------------------------------------- the state directory

test("the first event creates the state directory 0700 (vibe-207)", async () => {
  const workspace = ws();
  await emit(workspace, { component: "runner", event: "dispatch.start", detail: {} });
  assert.equal(mode(path.join(workspace, STATE_DIRNAME)), 0o700, "private from the first event");
  assert.equal(mode(eventLogPath(workspace)), 0o600, "and so is the log");
});

test("an existing state directory at 0755 is re-tightened before the first event (vibe-207)", async () => {
  const workspace = ws();
  mkdirSync(path.join(workspace, STATE_DIRNAME), { mode: 0o755 });
  chmodSync(path.join(workspace, STATE_DIRNAME), 0o755);       // defeat the umask
  await emit(workspace, { component: "runner", event: "dispatch.start", detail: {} });
  assert.equal(mode(path.join(workspace, STATE_DIRNAME)), 0o700,
    "ensureDirAt creates and secureDirAt tightens — two primitives because they answer two questions");
});

test("STATE_DIRNAME agrees with the store's, which is the only thing keeping them in one place (vibe-207)", () => {
  assert.equal(STATE_DIRNAME, STORE_STATE_DIRNAME,
    "eventlog.mjs declares its own copy to avoid an import cycle with jobs.mjs; this test is what makes that safe");
});

// ------------------------------------------------------------------------------------ the caps

test("an oversized detail is capped so the record still fits EVENT_LINE_MAX (vibe-207)", async () => {
  const workspace = ws();
  assert.equal(await emit(workspace, { component: "gate", event: "gate.decision",
    detail: { decision: "BLOCK", reason: "x".repeat(50_000) } }), true,
    "a huge detail is capped, not refused — losing the whole record would lose the decision too");

  const line = readFileSync(eventLogPath(workspace), "utf8");
  assert.ok(Buffer.byteLength(line, "utf8") <= EVENT_LINE_MAX,
    `the written line is ${Buffer.byteLength(line, "utf8")} bytes, over EVENT_LINE_MAX ${EVENT_LINE_MAX}`);
  const [record] = readRecords(workspace);
  assert.equal(record.event, "gate.decision", "the event survives capping — it is the part that answers the question");
  assert.equal(record.detail.decision, "BLOCK", "and so does the verdict");
  assert.equal(record.capped, true, "the elision is disclosed rather than silent");
});

test("a detail that cannot be capped small enough is disclosed, not silently dropped (vibe-207)", async () => {
  const workspace = ws();
  const wide = {};
  for (let i = 0; i < 4000; i += 1) wide[`k${i}`] = i;            // too many KEYS to shrink by capping values
  assert.equal(await emit(workspace, { component: "store", event: "finalise.error", detail: wide }), true);
  const [record] = readRecords(workspace);
  assert.equal(record.capped, true);
  assert.equal(record.event, "finalise.error", "the event is what a reader needs; the detail is the part that can go");
  assert.ok(Buffer.byteLength(JSON.stringify(record), "utf8") + 1 <= EVENT_LINE_MAX);
});

// --------------------------------------------------- property 1: emission never affects the caller

test("emit reports false and does NOT throw when the log path is a directory (vibe-207)", async () => {
  const workspace = ws();
  mkdirSync(path.join(workspace, STATE_DIRNAME), { recursive: true });
  mkdirSync(path.join(workspace, STATE_DIRNAME, EVENT_LOG_NAME));
  assert.equal(await emit(workspace, { component: "runner", event: "dispatch.start", detail: {} }), false,
    "a directory at the log path is exactly what an emitter's degrade test plants");
});

test("emit reports false and does NOT throw on an unserialisable detail (vibe-207)", async () => {
  const workspace = ws();
  const circular = { name: "loop" };
  circular.self = circular;
  assert.equal(await emit(workspace, { component: "runner", event: "dispatch.start", detail: circular }), false,
    "a caller that hands us something JSON cannot express gets a false, not an exception it did not plan for");
});

test("emit reports false and does NOT throw when the workspace does not exist (vibe-207)", async () => {
  assert.equal(await emit(path.join(ws(), "no", "such", "workspace"),
    { component: "runner", event: "dispatch.start", detail: {} }), false);
});

test("emit reports false and does NOT throw when the state dir is a FILE (vibe-207)", async () => {
  const workspace = ws();
  writeFileSync(path.join(workspace, STATE_DIRNAME), "not a directory");
  assert.equal(await emit(workspace, { component: "runner", event: "dispatch.start", detail: {} }), false);
});

// ------------------------------------------------------------------- the cap is measured, not enforced

test("EVENT_LOG_MAX_BYTES is exported for measurement; NOTHING in this module trims (vibe-207)", async () => {
  assert.equal(typeof EVENT_LOG_MAX_BYTES, "number");
  const workspace = ws();
  await emit(workspace, { component: "runner", event: "dispatch.start", detail: {} });
  const grown = "y".repeat(1024);
  for (let i = 0; i < 200; i += 1) await emit(workspace, { component: "runner", event: "noise", detail: { grown } });
  const size = statSync(eventLogPath(workspace)).size;
  assert.ok(size > 200 * 1024, "the log grew; retention is #266's, not this module's");
  assert.equal(readRecords(workspace).length, 201, "and every record is still there — nothing was discarded");
});


// ------------------------------------------------------- tailRecords: the bounded reader (vibe-207)
//
// "Read backwards until N complete lines" is NOT a byte bound — the termination condition is finding
// N newlines, and nothing guarantees the file contains them within any distance of the end. With
// retention split to #266 the file is unbounded too, so an unbounded scan is reachable. The reader
// therefore stops at a CEILING that does not depend on finding N lines.
//
// The ceiling tests assert BYTES READ, never output: an unbounded reader produces identical output
// on every well-formed input, so an output assertion would pass with the ceiling removed.

test("tailRecords returns the last N records, newest last (vibe-207)", async () => {
  const workspace = ws();
  for (const n of [1, 2, 3, 4, 5]) await emit(workspace, { component: "jobs", event: "e", detail: { n } });
  const { records, truncated } = await tailRecords(eventLogPath(workspace), 2);
  assert.deepEqual(records.map((r) => r.detail.n), [4, 5], "the tail is the END of the file");
  assert.equal(truncated, true, "the view does not include the whole file, and says so");
});

test("tailRecords reads the whole file when it is short, and is not truncated (vibe-207)", async () => {
  const workspace = ws();
  await emit(workspace, { component: "jobs", event: "only", detail: {} });
  const { records, truncated, bytesRead } = await tailRecords(eventLogPath(workspace), 10);
  assert.equal(records.length, 1);
  assert.equal(truncated, false, "reaching the start of the file is not truncation");
  assert.ok(bytesRead < 1024, `a one-record log should not read ${bytesRead} bytes`);
});

test("a huge newline-free suffix stops the reader AT THE CEILING — asserted as bytes read (vibe-207)", async () => {
  const workspace = ws();
  await emit(workspace, { component: "jobs", event: "buried", detail: {} });
  // 4 MiB with no newline anywhere: the shape a torn write or a foreign writer leaves behind.
  appendFileSync(eventLogPath(workspace), "z".repeat(4 * 1024 * 1024));

  const ceiling = 64 * 1024;
  const { records, truncated, bytesRead } =
    await tailRecords(eventLogPath(workspace), 5, { ceiling, chunk: 16 * 1024 });

  assert.ok(bytesRead <= ceiling,
    `read ${bytesRead} bytes against a ceiling of ${ceiling} — the scan is unbounded without it`);
  assert.equal(truncated, true, "and the view is reported truncated rather than passed off as the tail");
  assert.deepEqual(records, [],
    "no COMPLETE record lies within the ceiling, so none is reported — reporting the buried one would mean reading past it");
});

test("the ceiling holds even when N is never reachable (vibe-207)", async () => {
  const workspace = ws();
  for (let i = 0; i < 50; i += 1) await emit(workspace, { component: "jobs", event: "e", detail: { i } });
  const ceiling = 2048;
  const { bytesRead, truncated } = await tailRecords(eventLogPath(workspace), 10_000, { ceiling, chunk: 512 });
  assert.ok(bytesRead <= ceiling, `asked for 10,000 records and read ${bytesRead} bytes past a ${ceiling} ceiling`);
  assert.equal(truncated, true);
});

test("a multi-byte character split across a chunk boundary decodes correctly (vibe-207)", async () => {
  const workspace = ws();
  // Pad so a 3-byte character straddles a 64-byte chunk boundary when read backwards.
  for (let pad = 0; pad < 12; pad += 1) {
    const wsp = ws();
    await emit(wsp, { component: "jobs", event: "e", detail: { pad: "x".repeat(pad), text: "日本語テキスト" } });
    const { records } = await tailRecords(eventLogPath(wsp), 1, { ceiling: 64 * 1024, chunk: 64 });
    assert.equal(records[0]?.detail.text, "日本語テキスト",
      `pad=${pad}: decoding before the chunks are assembled corrupts a multi-byte character`);
  }
  assert.ok(workspace, "the outer workspace is unused; each pad gets its own");
});

test("a leading partial line is dropped rather than parsed (vibe-207)", async () => {
  const workspace = ws();
  for (const n of [1, 2, 3]) await emit(workspace, { component: "jobs", event: "e", detail: { n } });
  // A ceiling that lands mid-record: the first thing the reader sees is half a line.
  const size = statSync(eventLogPath(workspace)).size;
  const { records } = await tailRecords(eventLogPath(workspace), 5, { ceiling: Math.floor(size / 2), chunk: 16 });
  assert.ok(records.every((r) => typeof r.detail?.n === "number"),
    "every record returned parsed cleanly — a half line was discarded, not handed to JSON.parse");
});

test("an unparseable line is dropped, not fatal (vibe-207)", async () => {
  const workspace = ws();
  await emit(workspace, { component: "jobs", event: "before", detail: {} });
  appendFileSync(eventLogPath(workspace), "{ this is not json\n");
  await emit(workspace, { component: "jobs", event: "after", detail: {} });
  const { records } = await tailRecords(eventLogPath(workspace), 10);
  assert.deepEqual(records.map((r) => r.event), ["before", "after"],
    "a torn record is expected, not exceptional — property 2 says the reader drops it");
});

test("tailRecords on an absent log is empty, not an error (vibe-207)", async () => {
  const { records, truncated, bytesRead } = await tailRecords(eventLogPath(ws()), 10);
  assert.deepEqual(records, []);
  assert.equal(truncated, false);
  assert.equal(bytesRead, 0);
});
