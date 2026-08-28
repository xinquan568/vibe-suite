// SPDX-License-Identifier: ISC
// Store listing and record validation for /vibe-suite:jobs (E1.2 / vibe-12).
//
// These live in `node:test` for the same reason jobs-store.test.mjs does: they construct filesystem
// states — a stale canonical beside a newer committed slot, foreign files in the jobs dir — that a
// subprocess test cannot reach cleanly. `listRecords` must enumerate canonical names only but load
// every record through the slot-aware path, or `status` reports stale state (round-1 plan review,
// finding 2).

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { mkdirSync, writeFileSync } from "node:fs";
import { createRecord as createRecordForTombstone } from "../../scripts/lib/jobs.mjs";

import path from "node:path";
import test from "node:test";

import {
  createRecord, isValidJobId, jobsDir, listRecords, newRecord, validateRecord, JOB_ID_RE,
} from "../../scripts/lib/jobs.mjs";

function workspace() {
  return tmpWorkspace("jobs-list-");
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
  // vibe-204: a prune tombstone (a directory at a canonical path) and a VALID prune marker are
  // neither records nor invalid records — while a foreign file wearing the marker name hides nothing.
  mkdirSync(path.join(dir, "job_dddddddddddddddddddd.json"), { mode: 0o700 });
  writeFileSync(path.join(dir, "job_dddddddddddddddddddd.json", ".vibe-suite-tombstone"),
    JSON.stringify({ "_vibe-suite_owned": { kind: "job-tombstone", schema: 1 }, jobId: "job_dddddddddddddddddddd" }));
  writeFileSync(path.join(dir, `${ID_B}.pruning`), "{}");                                   // foreign: ID_B stays listed
  writeFileSync(path.join(dir, "job_eeeeeeeeeeeeeeeeeeee.json"), JSON.stringify(baseRecord("job_eeeeeeeeeeeeeeeeeeee")));
  writeFileSync(path.join(dir, "job_eeeeeeeeeeeeeeeeeeee.pruning"),
    JSON.stringify({ "_vibe-suite_owned": { kind: "job-prune-marker", schema: 1 }, jobId: "job_eeeeeeeeeeeeeeeeeeee", createdAt: "2026-01-01T00:00:00.000Z" }));

  const { records, invalid } = await listRecords(ws);
  assert.deepEqual(records.map((r) => r.jobId).sort(), [ID_A, ID_B]);
  assert.deepEqual(invalid, []);
  void createRecordForTombstone;
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

test("pipesLeaked is declared at creation, validated as nullable boolean, and OPTIONAL for pre-field records (vibe-181)", () => {
  const fresh = baseRecord(ID_A);
  assert.equal(fresh.pipesLeaked, null, "newRecord must declare pipesLeaked (null until settle)");
  for (const value of [null, true, false]) {
    assert.equal(validateRecord(baseRecord(ID_A, { pipesLeaked: value }), ID_A).ok, true, `pipesLeaked ${value} must validate`);
  }
  assert.equal(validateRecord(baseRecord(ID_A, { pipesLeaked: "yes" }), ID_A).ok, false, "a non-boolean pipesLeaked must be rejected");
  const legacy = baseRecord(ID_A);
  delete legacy.pipesLeaked;                                   // a record written before the field existed
  assert.equal(validateRecord(legacy, ID_A).ok, true, "a pre-field record must remain valid");
  const broken = baseRecord(ID_A);
  delete broken.exitCode;                                      // any OTHER missing key is still corruption
  assert.equal(validateRecord(broken, ID_A).ok, false, "optionality must not leak to other keys");
});

test("stderrTail, signal and malformedLines are declared at creation, typed, and OPTIONAL for pre-field records (vibe-182)", () => {
  const fresh = baseRecord(ID_A);
  for (const key of ["stderrTail", "signal", "malformedLines"]) {
    assert.equal(fresh[key], null, `newRecord must declare ${key} (null until the run settles)`);
  }
  const ok = (overrides) => validateRecord(baseRecord(ID_A, overrides), ID_A).ok;
  assert.equal(ok({ stderrTail: "codex: error: unexpected argument" }), true);
  assert.equal(ok({ stderrTail: "" }), true, "an empty tail is a truthful 'printed nothing'");
  assert.equal(ok({ stderrTail: 42 }), false, "stderrTail is a string or null");
  assert.equal(ok({ signal: "SIGTERM" }), true);
  assert.equal(ok({ signal: "" }), false, "an empty signal name is not a signal");
  assert.equal(ok({ signal: 15 }), false, "a signal is a name, not a number");
  assert.equal(ok({ malformedLines: 0 }), true);
  assert.equal(ok({ malformedLines: 3 }), true);
  assert.equal(ok({ malformedLines: -1 }), false);
  assert.equal(ok({ malformedLines: 1.5 }), false);
  const legacy = baseRecord(ID_A);
  for (const key of ["stderrTail", "signal", "malformedLines"]) delete legacy[key];   // written before the fields existed
  assert.equal(validateRecord(legacy, ID_A).ok, true, "a pre-field record must remain valid");
  const broken = baseRecord(ID_A);
  delete broken.rawOutput;                                    // any OTHER missing key is still corruption
  assert.equal(validateRecord(broken, ID_A).ok, false, "optionality must not leak to other keys");
});
