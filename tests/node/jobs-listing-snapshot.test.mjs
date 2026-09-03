// SPDX-License-Identifier: ISC
// vibe-205 / W2 — `listRecords` supplies the directory snapshot it already holds.
//
// `listRecords` reads the jobs directory once, then every record it resolves used to read that same
// directory again through `highestSlot` — O(jobs × entries) on a path that runs on every
// SessionStart/End and every 25 ms in `awaitWorkerClaim`. The fix hands the listing down.
//
// The discriminator here is a READDIR COUNT, never wall-clock: a timing assertion passes on a fast
// disk with the re-scan still in place, so it would prove nothing.
//
// Two invariants make this safe, and each has a test that fails if it is broken:
//   1. the snapshot is EVERY entry name, not the file-filtered `names` — `highestSlot` matches names
//      without checking file type, so a filtered listing would hide a slot-shaped directory (T8);
//   2. `commit`'s `highestSlot(..., { except })` still lists afresh — that scan is a confirmation,
//      and a stale one would publish over a newer slot (T9).

import { strict as assert } from "node:assert";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

// ---------------------------------------------------------------------------------------------
// Instrumentation, installed BEFORE the store is linked.
//
// `node:fs/promises`'s ESM namespace object is frozen, so the binding jobs.mjs imported cannot be
// replaced after the fact (`mock.method` on it throws). Patching the CJS `fs.promises` object before
// the ESM facade is built does reach it — which is why the store and the tmp helper are imported
// dynamically below, and why nothing above this point imports either of them.
// ---------------------------------------------------------------------------------------------
const require = createRequire(import.meta.url);
const fsCjs = require("fs");
const realReaddir = fsCjs.promises.readdir;

/** Every readdir the store performs, as absolute paths, in order. */
let readdirLog = [];
/** Fires once, immediately after a readdir of `dir` returns — used to race a slot in. */
let afterReaddirOf = null;

Object.defineProperty(fsCjs.promises, "readdir", {
  configurable: true,
  writable: true,
  value: async (dir, ...rest) => {
    const result = await realReaddir(dir, ...rest);
    readdirLog.push(String(dir));
    if (afterReaddirOf && String(dir) === afterReaddirOf.dir) {
      const hook = afterReaddirOf.fn;
      afterReaddirOf = null;
      await hook();
    }
    return result;
  },
});

const { tmpWorkspace } = await import("./_tmp.mjs");
const {
  createRecord, jobsDir, listRecords, newRecord, readRecord, RESULT_KEYS, resultLine,
} = await import("../../scripts/lib/jobs.mjs");

const ID_A = "job_aaaaaaaaaaaaaaaaaaaa";
const ID_B = "job_bbbbbbbbbbbbbbbbbbbb";
const ID_C = "job_cccccccccccccccccccc";

function baseRecord(jobId, overrides = {}) {
  return {
    ...newRecord({
      jobId, kind: "review", sandbox: "read-only", effort: "low",
      model: null, background: false, timeoutMs: 1000, claimDigest: null,
    }),
    ...overrides,
  };
}

function scansOf(dir) {
  return readdirLog.filter((seen) => seen === dir).length;
}

function slotFile(ws, jobId, version, record) {
  writeFileSync(
    path.join(jobsDir(ws), `${jobId}.v${version}.json`),
    JSON.stringify({ ...record, version }),
  );
}

// ---------------------------------------------------------------------------------------------
// Sanity anchor. If the patch above ever stops reaching the store — a Node change, an import moved
// above the instrumentation — every count below would read 0 and the assertions would pass
// vacuously. This test fails loudly in that case instead.
// ---------------------------------------------------------------------------------------------
test("the readdir instrumentation actually observes the store", async () => {
  const ws = tmpWorkspace("jobs-snapshot-sanity-");
  await createRecord(ws, baseRecord(ID_A));
  readdirLog = [];
  await readRecord(ws, ID_A);                       // no listing passed → resolves by its own scan
  assert.ok(scansOf(jobsDir(ws)) >= 1,
    "instrumentation saw no readdir; the counts in this file would be meaningless");
});

// T7 --------------------------------------------------------------------------------------------
test("T7: listRecords reads the jobs directory exactly once, whatever the job count", async () => {
  const ws = tmpWorkspace("jobs-snapshot-t7-");
  for (const id of [ID_A, ID_B, ID_C]) await createRecord(ws, baseRecord(id));
  readdirLog = [];
  const { records, invalid } = await listRecords(ws);
  assert.equal(records.length, 3);
  assert.deepEqual(invalid, []);
  assert.equal(scansOf(jobsDir(ws)), 1,
    `expected one scan for 3 jobs, saw ${scansOf(jobsDir(ws))} — the per-record re-scan is back`);
});

// T8 — invariant 1 -------------------------------------------------------------------------------
test("T8: a slot-shaped DIRECTORY is still seen by the slot resolver", async () => {
  const ws = tmpWorkspace("jobs-snapshot-t8-");
  await createRecord(ws, baseRecord(ID_A));
  // A directory named like a committed slot. `highestSlot` matches names without checking type, so
  // it must count as version 9 — the record then resolves to an unreadable slot and is REPORTED.
  // Hand it the file-filtered listing instead and this vanishes: the job reads back as healthy.
  mkdirSync(path.join(jobsDir(ws), `${ID_A}.v9.json`));
  const { records, invalid } = await listRecords(ws);
  assert.deepEqual(records.map((r) => r.jobId), [],
    "the job resolved as healthy — the resolver was handed a listing with directories filtered out");
  assert.equal(invalid.length, 1);
  assert.equal(invalid[0].jobId, ID_A);
  assert.match(invalid[0].reason, /unreadable/);
});

// T9 — invariant 2 -------------------------------------------------------------------------------
test("T9: commit still lists afresh, so a slot published after the snapshot is seen", async () => {
  const ws = tmpWorkspace("jobs-snapshot-t9-");
  const record = baseRecord(ID_A);
  await createRecord(ws, record);                   // canonical at version 1
  slotFile(ws, ID_A, 2, record);                    // a newer committed slot → self-heal will run

  // Race a HIGHER slot in immediately after listRecords takes its snapshot. `commit`'s
  // `highestSlot(..., { except })` must not be answered from that stale snapshot: version 3 is
  // above the version being published, so the publication must be refused as SUPERSEDED.
  afterReaddirOf = { dir: jobsDir(ws), fn: async () => { slotFile(ws, ID_A, 3, record); } };
  readdirLog = [];
  await listRecords(ws);
  assert.equal(afterReaddirOf, null, "the snapshot readdir never happened — the race never ran");

  const canonical = JSON.parse(readFileSync(path.join(jobsDir(ws), `${ID_A}.json`), "utf8"));
  assert.equal(canonical.version, 1,
    "the canonical was republished at version 2 despite a version 3 slot — commit was answered " +
    "from the stale snapshot instead of listing afresh");
  assert.ok(scansOf(jobsDir(ws)) >= 2,
    "only one scan on the self-heal path — commit stopped confirming against a current listing");
});

// T7b -------------------------------------------------------------------------------------------
test("T7b: results are unchanged for a store holding tombstones, markers and a foreign directory",
  async () => {
    const ws = tmpWorkspace("jobs-snapshot-t7b-");
    await createRecord(ws, baseRecord(ID_A));
    await createRecord(ws, baseRecord(ID_B));
    const dir = jobsDir(ws);
    // Residents that are not records and must not become ones.
    writeFileSync(path.join(dir, `${ID_C}.pruning`), "not this store's marker");
    writeFileSync(path.join(dir, "notes.txt"), "foreign file");
    writeFileSync(path.join(dir, `${ID_A}.v1.json.tmp`), "{}");
    mkdirSync(path.join(dir, "scratch-dir"));

    readdirLog = [];
    const { records, invalid } = await listRecords(ws);
    assert.deepEqual(records.map((r) => r.jobId).sort(), [ID_A, ID_B]);
    assert.deepEqual(invalid, []);
    assert.equal(scansOf(dir), 1);
  });

// T9b -------------------------------------------------------------------------------------------
test("T9b: a job buried under a foreign directory is reported, never silently dropped", async () => {
  const ws = tmpWorkspace("jobs-snapshot-t9b-");
  await createRecord(ws, baseRecord(ID_A));
  // A directory that is NOT this store's tombstone, sitting on a canonical path.
  mkdirSync(path.join(jobsDir(ws), `${ID_B}.json`));
  const { records, invalid } = await listRecords(ws);
  assert.deepEqual(records.map((r) => r.jobId), [ID_A]);
  assert.equal(invalid.length, 1);
  assert.equal(invalid[0].jobId, ID_B);
  assert.match(invalid[0].reason, /not this store's tombstone/);
});

// T10 -------------------------------------------------------------------------------------------
test("T10: the record contract and the result line are untouched by this change", () => {
  assert.deepEqual(RESULT_KEYS, ["jobId", "status", "threadId", "rawOutput", "verdictState"]);
  const line = JSON.parse(resultLine(baseRecord(ID_A, { status: "done", rawOutput: "x" })));
  assert.deepEqual(Object.keys(line), RESULT_KEYS);
  assert.equal(Object.keys(line).length, 5);
});
