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
import { chmodSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

import {
  emit, eventLogPath, EVENT_LOG_MAX_BYTES, EVENT_LOG_NAME, STATE_DIRNAME,
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
