// SPDX-License-Identifier: ISC
// CAS record store: crash recovery and transition safety (E1.1 / vibe-11).
//
// These live in `node:test` because they construct filesystem states a subprocess test cannot reach
// cleanly — notably an uncommitted version slot beside a canonical record, which is what a writer
// that died between `link` and `rename` leaves behind.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";

import path from "node:path";
import test from "node:test";

import {
  createRecord, finaliseRecord, isAbandoned, jobsDir, newRecord, readRecord, reapOrphanTemps,
  recordPath, transact, updateRecord, REJECT,
} from "../../scripts/lib/jobs.mjs";

function workspace() {
  return tmpWorkspace("jobs-store-");
}

async function seed(ws, overrides = {}) {
  const record = {
    ...newRecord({
      jobId: "job_test", kind: "review", sandbox: "read-only", effort: "low",
      model: null, background: true, timeoutMs: 1000, claimDigest: null,
    }),
    ...overrides,
  };
  return createRecord(ws, record);
}

test("an uncommitted version slot is rolled forward, not deleted", async () => {
  const ws = workspace();
  await seed(ws);
  // Simulate a writer that died between link and rename: the slot exists, canonical is still at 1.
  const slot = path.join(jobsDir(ws), "job_test.v2.json");
  const candidate = { ...(await readRecord(ws, "job_test")), version: 2, status: "completed" };
  writeFileSync(slot, JSON.stringify(candidate, null, 2) + "\n", "utf8");

  // The next writer must complete that commit rather than block on EEXIST forever.
  await transact(ws, "job_test", (record) => ({ ...record, kind: "later" }));

  const final = await readRecord(ws, "job_test");
  assert.ok(final.version >= 2, "the orphaned slot must have been committed");
  // The slot is RETAINED, not consumed. Renaming it away would free the `v2` pathname, letting a
  // delayed writer still holding a stale read at v1 claim that version again and publish its
  // obsolete candidate over a newer — possibly terminal — record.
  assert.ok(readdirSync(jobsDir(ws)).includes("job_test.v2.json"),
    "a committed slot is retained so its version can never be re-claimed");
});

test("a committed version can never be re-claimed by a stale writer", async () => {
  const ws = workspace();
  await seed(ws);
  await transact(ws, "job_test", (record) => ({ ...record, kind: "first" }));   // canonical -> v2
  const canonical = await readRecord(ws, "job_test");
  assert.equal(canonical.version, 2);

  // A stale writer that still believes the canonical is at v1 must not be able to take v2 again.
  await assert.rejects(async () => {
    const { link, writeFile } = await import("node:fs/promises");
    const temp = path.join(jobsDir(ws), "job_test.tmp.stale");
    await writeFile(temp, JSON.stringify({ ...canonical, version: 2, kind: "STALE" }), "utf8");
    await link(temp, path.join(jobsDir(ws), "job_test.v2.json"));
  }, /EEXIST/, "the retained slot must block re-use of a committed version");

  assert.equal((await readRecord(ws, "job_test")).kind, "first");
});

test("a malformed slot is reported, never deleted or committed", async () => {
  const ws = workspace();
  await seed(ws);
  writeFileSync(path.join(jobsDir(ws), "job_test.v2.json"), "{ not json", "utf8");

  await assert.rejects(
    () => transact(ws, "job_test", (record) => ({ ...record, kind: "later" })),
    /NOT deleted automatically/);
  assert.ok(readdirSync(jobsDir(ws)).includes("job_test.v2.json"),
    "a malformed slot must survive for administrative repair");
});

test("a terminal record is never reopened", async () => {
  const ws = workspace();
  await seed(ws);
  await finaliseRecord(ws, "job_test", { status: "completed" });
  const late = await updateRecord(ws, "job_test", { heartbeatAt: new Date().toISOString() });
  assert.equal(late, null, "a late heartbeat must be rejected, not applied");
  assert.equal((await readRecord(ws, "job_test")).status, "completed");
});

test("a terminal verdict is never replaced by another", async () => {
  const ws = workspace();
  await seed(ws);
  await finaliseRecord(ws, "job_test", { status: "timed_out" });
  const second = await finaliseRecord(ws, "job_test", { status: "completed" });
  assert.equal(second, null);
  assert.equal((await readRecord(ws, "job_test")).status, "timed_out");
});

test("the updater is re-run against the fresh record on contention", async () => {
  const ws = workspace();
  await seed(ws);
  let seen = 0;
  await transact(ws, "job_test", (record) => {
    seen += 1;
    if (seen === 1) {
      // Change the canonical underneath ourselves, so the first attempt must lose and re-run.
      const bumped = { ...record, version: record.version + 1, kind: "raced" };
      writeFileSync(recordPath(ws, "job_test"), JSON.stringify(bumped, null, 2) + "\n", "utf8");
      writeFileSync(path.join(jobsDir(ws), `job_test.v${record.version + 1}.json`),
        JSON.stringify(bumped, null, 2) + "\n", "utf8");
    }
    return { ...record, effort: "high" };
  });
  assert.ok(seen >= 2, "the updater must be re-run, not applied from the stale read");
  const final = await readRecord(ws, "job_test");
  assert.equal(final.effort, "high");
  assert.equal(final.kind, "raced", "the racing write must not have been clobbered");
});

test("REJECT declines without writing", async () => {
  const ws = workspace();
  await seed(ws);
  const before = readFileSync(recordPath(ws, "job_test"), "utf8");
  assert.equal(await transact(ws, "job_test", () => REJECT), null);
  assert.equal(readFileSync(recordPath(ws, "job_test"), "utf8"), before);
});

test("orphan temps are reaped only past the age bound; version slots never", async () => {
  const ws = workspace();
  await seed(ws);
  // vibe-103: the temp must carry the ownership stamp to be collectible. This fixture wrote a bare
  // "{}" and asserted one deletion, so it would fail against a store that proves ownership — which
  // is the point: a name pattern was never evidence that the file was ours. It gains the stamp, and
  // an unstamped file matching the same pattern is added to prove that one survives.
  writeFileSync(path.join(jobsDir(ws), "job_test.tmp.999.abc"),
    JSON.stringify({ "_vibe-suite_owned": { kind: "job-scratch", schema: 1 } }), "utf8");
  writeFileSync(path.join(jobsDir(ws), "job_other.tmp.998.def"), "{}", "utf8");
  writeFileSync(path.join(jobsDir(ws), "job_test.v9.json"), "{}", "utf8");

  assert.equal(await reapOrphanTemps(ws), 0, "a fresh temp must not be reaped");
  assert.equal(await reapOrphanTemps(ws, { now: Date.now() + 7 * 60 * 60 * 1000 }), 1);
  assert.ok(readdirSync(jobsDir(ws)).includes("job_other.tmp.998.def"),
    "an unstamped file is not ours to delete, whatever its name looks like");
  assert.ok(readdirSync(jobsDir(ws)).includes("job_test.v9.json"),
    "a version slot is never reaped, at any age");
});

test("isAbandoned reports a dead background worker and never a live one", () => {
  const base = { background: true, status: "running", workerPid: process.pid };
  const stale = new Date(Date.now() - 10 * 60 * 1000).toISOString();
  assert.equal(isAbandoned({ ...base, heartbeatAt: stale }), false, "our own pid is alive");
  assert.equal(isAbandoned({ ...base, heartbeatAt: new Date().toISOString() }), false);
  assert.equal(isAbandoned({ ...base, workerPid: 2 ** 22 - 1, heartbeatAt: stale }), true);
  assert.equal(isAbandoned({ ...base, status: "completed", heartbeatAt: stale }), false,
    "a terminal job is finished, not abandoned");
});

test("transact itself refuses every terminal status — the guard is a store invariant", async () => {
  for (const status of ["completed", "failed", "timed_out", "cancelled"]) {
    const ws = workspace();
    await seed(ws, { status });
    const result = await transact(ws, "job_test", (record) => ({ ...record, status: "running", kind: "REOPENED" }));
    assert.equal(result, null, `transact must refuse to reopen a ${status} record`);
    const after = await readRecord(ws, "job_test");
    assert.equal(after.status, status);
    assert.notEqual(after.kind, "REOPENED");
  }
});

test("a claim token cannot be replayed against a still-runnable record", async () => {
  const { claimWith, hashToken, newClaimToken } = await import("../../scripts/lib/jobs.mjs");
  const ws = workspace();
  const token = newClaimToken();
  await seed(ws, { claimDigest: hashToken(token) });

  const first = await claimWith(ws, "job_test", token);
  assert.ok(first, "the first claim with a valid token must succeed");
  assert.equal(first.claimDigest, null, "the digest must be consumed");

  // Re-open the claim slot but leave the digest consumed: a replay must still fail, which is the
  // property. Merely observing a cleared field would pass an implementation that still allows replay.
  await transact(ws, "job_test", (record) => ({ ...record, workerPid: null, pgid: null }));
  const replay = await claimWith(ws, "job_test", token);
  assert.equal(replay, null, "the same raw token must not claim twice");
});

test("a stale publication cannot lose a newer record — reads resolve the highest slot", async () => {
  const ws = workspace();
  await seed(ws);
  await transact(ws, "job_test", (record) => ({ ...record, kind: "second" }));   // v2
  await transact(ws, "job_test", (record) => ({ ...record, status: "completed" })); // v3, terminal

  // Simulate a delayed writer publishing an older version over the canonical path. `rename` cannot
  // be made conditional, so this is the race the highest-slot read exists to absorb.
  const stale = JSON.parse(readFileSync(path.join(jobsDir(ws), "job_test.v2.json"), "utf8"));
  writeFileSync(recordPath(ws, "job_test"), JSON.stringify(stale, null, 2) + "\n", "utf8");

  const seen = await readRecord(ws, "job_test");
  assert.equal(seen.version, 3, "the highest committed slot is the authority");
  assert.equal(seen.status, "completed", "a terminal record must not be lost to a stale publish");

  // And it self-heals: the canonical path converges on the next read.
  const republished = JSON.parse(readFileSync(recordPath(ws, "job_test"), "utf8"));
  assert.equal(republished.version, 3);
});
