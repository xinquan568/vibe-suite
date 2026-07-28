// SPDX-License-Identifier: ISC
// Store listing and record validation for /vibe-suite:jobs (E1.2 / vibe-12).
//
// These live in `node:test` for the same reason jobs-store.test.mjs does: they construct filesystem
// states — a stale canonical beside a newer committed slot, foreign files in the jobs dir — that a
// subprocess test cannot reach cleanly. `listRecords` must enumerate canonical names only but load
// every record through the slot-aware path, or `status` reports stale state (round-1 plan review,
// finding 2).

import { strict as assert } from "node:assert";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import {
  createRecord, isValidJobId, jobsDir, listRecords, newRecord, validateRecord, JOB_ID_RE,
} from "../../scripts/lib/jobs.mjs";

function workspace() {
  return mkdtempSync(path.join(tmpdir(), "jobs-list-"));
}

function baseRecord(jobId, overrides = {}) {
  return {
    ...newRecord({
      jobId, kind: "review", sandbox: "read-only", effort: "low",
      model: null, background: false, timeoutMs: 1000, claimDigest: null,
    }),
    ...overrides,
  };
}

const ID_A = "job_aaaaaaaaaaaaaaaaaaaa";
const ID_B = "job_bbbbbbbbbbbbbbbbbbbb";
const ID_C = "job_cccccccccccccccccccc";

test("job id validation accepts the canonical shape only", () => {
  assert.equal(isValidJobId(ID_A), true);
  for (const bad of [
    "job_AAAAAAAAAAAAAAAAAAAA",            // uppercase is not the generator's alphabet
    "job_aaaaaaaaaaaaaaaaaaa",             // 19 hex chars
    "job_aaaaaaaaaaaaaaaaaaaaa",           // 21 hex chars
    "../../etc/passwd",                    // traversal-shaped
    "job_../../../../etc/pass",            // traversal wearing the prefix
    "", null, undefined, 42,
  ]) {
    assert.equal(isValidJobId(bad), false, `accepted: ${String(bad)}`);
  }
  assert.equal(JOB_ID_RE.test(ID_B), true);
});

test("listRecords enumerates canonical records only and skips slots, temps and foreign files", async () => {
  const ws = workspace();
  await createRecord(ws, baseRecord(ID_A));
  await createRecord(ws, baseRecord(ID_B, { background: true }));
  const dir = jobsDir(ws);
  // Non-canonical residents the enumeration must ignore (slots/temps belong to the CAS protocol).
  writeFileSync(path.join(dir, `${ID_A}.v2.json`), JSON.stringify(baseRecord(ID_A, { version: 2 })));
  writeFileSync(path.join(dir, `${ID_C}.tmp.deadbeef.json`), "{}");
  writeFileSync(path.join(dir, "notes.txt"), "not a record");

  const { records, invalid } = await listRecords(ws);
  assert.deepEqual(records.map((r) => r.jobId).sort(), [ID_A, ID_B]);
  assert.deepEqual(invalid, []);
});

test("listRecords loads through the slot-aware path: a newer committed slot wins over a stale canonical", async () => {
  const ws = workspace();
  await createRecord(ws, baseRecord(ID_A, { status: "running" }));
  // A writer that died between link and rename leaves the newest state in a .vN slot. A raw read of
  // the canonical would report `running`; the store's own read path must surface `completed`.
  writeFileSync(
    path.join(jobsDir(ws), `${ID_A}.v2.json`),
    JSON.stringify(baseRecord(ID_A, { version: 2, status: "completed", endedAt: new Date().toISOString() })),
  );

  const { records } = await listRecords(ws);
  assert.equal(records.length, 1);
  assert.equal(records[0].status, "completed");
  assert.equal(records[0].version, 2);
});

test("listRecords reports invalid records as errors instead of returning them", async () => {
  const ws = workspace();
  const dir = jobsDir(ws);
  mkdirSync(dir, { recursive: true });
  // Identity mismatch: the file wears ID_A, the record claims ID_B.
  writeFileSync(path.join(dir, `${ID_A}.json`), JSON.stringify(baseRecord(ID_B)));
  // Unknown status.
  writeFileSync(path.join(dir, `${ID_B}.json`), JSON.stringify(baseRecord(ID_B, { status: "zombie" })));
  await createRecord(ws, baseRecord(ID_C));

  const { records, invalid } = await listRecords(ws);
  assert.deepEqual(records.map((r) => r.jobId), [ID_C]);
  assert.deepEqual(invalid.map((entry) => entry.jobId).sort(), [ID_A, ID_B]);
  for (const entry of invalid) assert.equal(typeof entry.reason, "string");
});

test("listRecords on a workspace with no store returns empty, not an error", async () => {
  const { records, invalid } = await listRecords(workspace());
  assert.deepEqual(records, []);
  assert.deepEqual(invalid, []);
});

test("validateRecord enforces schema, identity and handle invariants", () => {
  const ok = validateRecord(baseRecord(ID_A), ID_A);
  assert.equal(ok.ok, true);

  const cases = [
    ["identity mismatch", baseRecord(ID_B), ID_A],
    ["not an object", null, ID_A],
    ["missing key", (() => { const r = baseRecord(ID_A); delete r.status; return r; })(), ID_A],
    ["unknown status", baseRecord(ID_A, { status: "zombie" }), ID_A],
    ["background not boolean", baseRecord(ID_A, { background: "yes" }), ID_A],
    ["unparseable timestamp", baseRecord(ID_A, { createdAt: "yesterday-ish" }), ID_A],
    ["negative workerPid", baseRecord(ID_A, { background: true, workerPid: -5, pgid: -5 }), ID_A],
    ["zero pgid", baseRecord(ID_A, { background: true, workerPid: 10, pgid: 0 }), ID_A],
    ["non-integer pid", baseRecord(ID_A, { background: true, workerPid: 10.5, pgid: 10.5 }), ID_A],
    ["foreground carrying a pgid", baseRecord(ID_A, { background: false, workerPid: 10, pgid: 10 }), ID_A],
    ["background pgid !== workerPid", baseRecord(ID_A, { background: true, workerPid: 10, pgid: 11 }), ID_A],
  ];
  for (const [label, record, id] of cases) {
    const verdict = validateRecord(record, id);
    assert.equal(verdict.ok, false, `validator accepted: ${label}`);
    assert.equal(typeof verdict.reason, "string", `no reason for: ${label}`);
  }
});
