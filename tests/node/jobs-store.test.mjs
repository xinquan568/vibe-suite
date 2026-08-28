// SPDX-License-Identifier: ISC
// CAS record store: crash recovery and transition safety (E1.1 / vibe-11).
//
// These live in `node:test` because they construct filesystem states a subprocess test cannot reach
// cleanly — notably an uncommitted version slot beside a canonical record, which is what a writer
// that died between `link` and `rename` leaves behind.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import {
  existsSync, lstatSync, mkdirSync, readdirSync, readFileSync, renameSync, rmdirSync, symlinkSync, unlinkSync,
  utimesSync, writeFileSync,
} from "node:fs";

import path from "node:path";
import test from "node:test";

import {
  createRecord, finaliseRecord, isAbandoned, jobsDir, listRecords, newRecord, pruneTerminalJobs,
  readRecord, reapOrphanTemps, recordPath, transact, updateRecord, DEFAULT_PRUNE_OLDER_THAN_MS,
  PRUNE_TOMBSTONE_TTL_MS, REJECT, TEMP_REAP_MIN_AGE_MS,
} from "../../scripts/lib/jobs.mjs";
import { writeAtomic } from "../../scripts/lib/write.mjs";

function workspace() {
  return tmpWorkspace("jobs-store-");
}

async function seed(ws, overrides = {}, jobId = "job_test") {
  const record = {
    ...newRecord({
      jobId, kind: "review", sandbox: "read-only", effort: "low",
      model: null, background: true, timeoutMs: 1000, claimDigest: null,
    }),
    ...overrides,
  };
  return createRecord(ws, record);
}

function newSeed(jobId) {
  return newRecord({
    jobId, kind: "review", sandbox: "read-only", effort: "low",
    model: null, background: true, timeoutMs: 1000, claimDigest: null,
  });
}

/** Every file of one job, sorted — canonical, slots, log. */
const filesOf = (ws, id) => readdirSync(jobsDir(ws)).filter((n) => n.startsWith(`${id}.`)).sort();
const STAMP = { "_vibe-suite_owned": { kind: "job-scratch", schema: 1 } };
const validMarker = (jobId, createdAt) =>
  JSON.stringify({ "_vibe-suite_owned": { kind: "job-prune-marker", schema: 1 }, jobId, createdAt }) + "\n";
const TOMBSTONE_STAMP = ".vibe-suite-tombstone";
const isTombstone = (ws, id) => {
  const p = recordPath(ws, id);
  if (!lstatSync(p).isDirectory()) return false;
  const stamp = JSON.parse(readFileSync(path.join(p, TOMBSTONE_STAMP), "utf8"));
  return stamp["_vibe-suite_owned"].kind === "job-tombstone" && stamp.jobId === id && readdirSync(p).length === 1;
};
const DAY = 24 * 60 * 60 * 1000;

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
  // The slot is RETAINED, not consumed: it is the job's TOP slot, and the top slot is never
  // deleted (vibe-204 compacts only what lies below it). Renaming it away would free the `v2`
  // pathname, letting a delayed writer still holding a stale read at v1 claim that version again
  // and publish its obsolete candidate over a newer — possibly terminal — record.
  assert.ok(readdirSync(jobsDir(ws)).includes("job_test.v2.json"),
    "a committed top slot is retained so its version can never be re-claimed");
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
    "the temp reaper never touches a version slot, at any age (terminal-job slots go at compaction/prune, not here)");
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
  // Capture v2's bytes now: the terminal commit below compacts the v2 slot away (vibe-204).
  const stale = JSON.parse(readFileSync(path.join(jobsDir(ws), "job_test.v2.json"), "utf8"));
  await transact(ws, "job_test", (record) => ({ ...record, status: "completed" })); // v3, terminal

  // Simulate a delayed writer publishing an older version over the canonical path. `rename` cannot
  // be made conditional, so this is the race the highest-slot read exists to absorb.
  writeFileSync(recordPath(ws, "job_test"), JSON.stringify(stale, null, 2) + "\n", "utf8");

  const seen = await readRecord(ws, "job_test");
  assert.equal(seen.version, 3, "the highest committed slot is the authority");
  assert.equal(seen.status, "completed", "a terminal record must not be lost to a stale publish");

  // And it self-heals: the canonical path converges on the next read.
  const republished = JSON.parse(readFileSync(recordPath(ws, "job_test"), "utf8"));
  assert.equal(republished.version, 3);
});

// ---------------------------------------------------------------------------------------------
// vibe-204 (grill H8): compaction at a terminal commit, confirmed wins, prune.

test("a terminal commit compacts: exactly the canonical and the top slot remain", async () => {
  const ws = workspace();
  await seed(ws);
  for (let i = 0; i < 3; i += 1) {
    await updateRecord(ws, "job_test", { heartbeatAt: new Date().toISOString() });   // v2, v3, v4
  }
  assert.deepEqual(filesOf(ws, "job_test"),
    ["job_test.json", "job_test.v2.json", "job_test.v3.json", "job_test.v4.json"]);
  const done = await finaliseRecord(ws, "job_test", { status: "completed" });          // v5, terminal
  assert.equal(done.version, 5);
  assert.deepEqual(filesOf(ws, "job_test"), ["job_test.json", "job_test.v5.json"],
    "after finalise: canonical + the top slot, nothing else");
  assert.equal((await readRecord(ws, "job_test")).status, "completed");
});

test("compaction removes only stamped slots below the top; a slot-shaped file that is not ours survives", async () => {
  const ws = workspace();
  await seed(ws);
  await updateRecord(ws, "job_test", { kind: "beat" });                          // v2, stamped by the store
  writeFileSync(path.join(jobsDir(ws), "job_test.v0.json"), "{}", "utf8");      // slot shape, no stamp
  await finaliseRecord(ws, "job_test", { status: "failed" });                    // v3, terminal
  assert.deepEqual(filesOf(ws, "job_test"), ["job_test.json", "job_test.v0.json", "job_test.v3.json"],
    "our v2 is compacted; the unstamped file is not ours to delete");
});

test("rolling forward someone else's terminal slot compacts the history beneath it too", async () => {
  const ws = workspace();
  await seed(ws);
  await updateRecord(ws, "job_test", { kind: "beat" });                          // v2
  // A finaliser that died between link and rename: a stamped terminal v3 slot, canonical still at v2.
  const v3 = { ...(await readRecord(ws, "job_test")), version: 3, status: "completed", ...STAMP };
  writeFileSync(path.join(jobsDir(ws), "job_test.v3.json"), JSON.stringify(v3, null, 2) + "\n", "utf8");
  // The next writer completes that commit and is then refused — the job is terminal …
  assert.equal(await transact(ws, "job_test", (record) => ({ ...record, kind: "later" })), null);
  // … and the commit it completed compacted v2 away.
  assert.deepEqual(filesOf(ws, "job_test"), ["job_test.json", "job_test.v3.json"]);
  assert.equal(JSON.parse(readFileSync(recordPath(ws, "job_test"), "utf8")).version, 3);
});

test("a writer whose job was pruned under it publishes nothing and resurrects nothing", async () => {
  const ws = workspace();
  const id = "job_cafecafecafecafecafe";
  await seed(ws, {}, id);
  let seen = 0;
  await assert.rejects(() => transact(ws, id, (record) => {
    seen += 1;
    // Between this writer's read and its link, the job is finished and pruned by someone else:
    // the canonical is gone. (Prune deletes the canonical first for exactly this reason.)
    if (seen === 1) unlinkSync(recordPath(ws, id));
    return { ...record, kind: "stale" };
  }), /no record/, "the stale writer is told the job is gone, not that its update landed");
  assert.deepEqual(filesOf(ws, id), [],
    "no canonical came back, and the stale writer's own slot was removed");
});

test("a writer two versions stale cannot re-claim a compacted version — the win is confirmed, not assumed", async () => {
  const ws = workspace();
  await seed(ws);
  let seen = 0;
  const result = await transact(ws, "job_test", (record) => {
    seen += 1;
    if (seen === 1) {
      // While this writer holds its v1 read: a heartbeat commits v2, a finaliser commits v3
      // (terminal) and compaction frees v2. Written by hand — the updater is synchronous.
      const done = { ...record, version: 3, kind: "beat", status: "completed", ...STAMP };
      writeFileSync(path.join(jobsDir(ws), "job_test.v3.json"), JSON.stringify(done, null, 2) + "\n", "utf8");
      writeFileSync(recordPath(ws, "job_test"), JSON.stringify(done, null, 2) + "\n", "utf8");
    }
    return { ...record, kind: "stale" };
  });
  assert.equal(result, null, "the stale candidate must be refused, never reported as applied");
  const final = JSON.parse(readFileSync(recordPath(ws, "job_test"), "utf8"));
  assert.equal(final.version, 3);
  assert.equal(final.status, "completed");
  assert.equal(final.kind, "beat", "the terminal record is untouched");
  // The reclaimed v2 slot stays: the store never deletes a slot someone may have built on, and
  // beneath a retained terminal top it is inert — every read still resolves v3.
  assert.deepEqual(filesOf(ws, "job_test"), ["job_test.json", "job_test.v2.json", "job_test.v3.json"]);
  assert.equal((await readRecord(ws, "job_test")).version, 3);
  assert.equal((await readRecord(ws, "job_test")).status, "completed");
});

test("a lowered canonical cannot make a reclaimed version look confirmable — the highest OTHER slot decides", async () => {
  const ws = workspace();
  await seed(ws);
  await updateRecord(ws, "job_test", { kind: "beat" });                          // v2 (a recoverer published it)
  let seen = 0;
  const result = await transact(ws, "job_test", (record) => {                    // this writer reads v2
    seen += 1;
    if (seen === 1) {
      // Meanwhile: others publish v3 (non-terminal) and v4 (terminal); compaction frees v2 and v3;
      // then a publisher paused before its rename LOWERS the canonical back to v2.
      const v4 = { ...record, version: 4, kind: "done", status: "completed", ...STAMP };
      writeFileSync(path.join(jobsDir(ws), "job_test.v4.json"), JSON.stringify(v4, null, 2) + "\n", "utf8");
      unlinkSync(path.join(jobsDir(ws), "job_test.v2.json"));
      writeFileSync(recordPath(ws, "job_test"), JSON.stringify({ ...record, ...STAMP }, null, 2) + "\n", "utf8");
    }
    return { ...record, status: "timed_out", kind: "stale-terminal" };          // its own terminal candidate for v3
  });
  assert.equal(result, null, "the canonical said v2, exactly what was read — and that must not be enough");
  const canonical = JSON.parse(readFileSync(recordPath(ws, "job_test"), "utf8"));
  assert.equal(canonical.kind, "done", "the stale terminal candidate was never published over the real one");
  const seenNow = await readRecord(ws, "job_test");
  assert.equal(seenNow.version, 4);
  assert.equal(seenNow.status, "completed");
});

test("prune leaves a tombstone: a 0700 directory at the canonical path that bars every late publication", async () => {
  const ws = workspace();
  const id = "job_4444444444444444444d";
  await seed(ws, {}, id);
  await updateRecord(ws, id, { kind: "beat" });
  await finaliseRecord(ws, id, { status: "completed" });
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.deepEqual(report.pruned.map((job) => job.jobId), [id]);

  const canonical = recordPath(ws, id);
  const info = lstatSync(canonical);
  assert.ok(info.isDirectory(), "the canonical path is now a directory");
  assert.equal(info.mode & 0o777, 0o700);
  assert.deepEqual(readdirSync(canonical), [TOMBSTONE_STAMP], "…holding exactly this store's provenance");
  assert.ok(isTombstone(ws, id));
  assert.deepEqual(filesOf(ws, id), [`${id}.json`], "no slot survives beside it");

  // The barrier, at the syscall the design relies on: rename(file, dir) is EISDIR. This is the late
  // publication of a writer paused inside `writeAtomic` after it confirmed its win.
  const late = path.join(jobsDir(ws), ".late.vibe-tmp");
  writeFileSync(late, "{}", "utf8");
  assert.throws(() => renameSync(late, canonical), { code: "EISDIR" });
  // …and through the audited primitive itself, which refuses to publish over a directory.
  await assert.rejects(() => writeAtomic(jobsDir(ws), canonical, "{}", { mode: 0o600 }), /is a dir/);
  // Readers: no job. A stale writer's slot beside the tombstone is an orphan, never a record.
  writeFileSync(path.join(jobsDir(ws), `${id}.v9.json`),
    JSON.stringify({ jobId: id, version: 9, status: "running" }), "utf8");
  await assert.rejects(() => readRecord(ws, id), /no record/);
  await assert.rejects(() => transact(ws, id, (record) => ({ ...record, kind: "reclaimed" })), /no record/);
  assert.deepEqual(await listRecords(ws), { records: [], invalid: [] }, "a tombstone is not an invalid record");
  await assert.rejects(() => createRecord(ws, newSeed(id)), /pruned/,
    "a dead id cannot be recreated while its tombstone stands");
});

test("a canonical that comes back between prune's unlink and its tombstone is unlinked again", async () => {
  const ws = workspace();
  const id = "job_5555555555555555555e";
  await seed(ws, {}, id);
  await finaliseRecord(ws, id, { status: "failed" });
  const bytes = readFileSync(recordPath(ws, id), "utf8");
  let landed = 0;
  const report = await pruneTerminalJobs(ws, {
    olderThanMs: 0,
    onStep: (jobId, step) => {
      // A paused publisher's rename lands in the gap after the unlink — twice.
      if (step === "unlinked" && landed < 2) { landed += 1; writeFileSync(recordPath(ws, jobId), bytes, "utf8"); }
    },
  });
  assert.equal(landed, 2, "each resurrection was answered by another unlink");
  assert.deepEqual(report.pruned.map((job) => job.jobId), [id]);
  assert.ok(lstatSync(recordPath(ws, id)).isDirectory(), "the tombstone stands in the end");
  assert.ok(!existsSync(path.join(jobsDir(ws), `${id}.pruning`)), "the marker is gone once the job is");
});

test("a prune interrupted at ANY step is completed by the next one, and the late publisher still fails", async () => {
  for (const crashAt of ["marker", "unlinked", "staged", "entombed", "slots"]) {
    const ws = workspace();
    const id = "job_9999999999999999999c";
    await seed(ws, {}, id);
    await updateRecord(ws, id, { kind: "beat" });
    await finaliseRecord(ws, id, { status: "completed" });
    const marker = path.join(jobsDir(ws), `${id}.pruning`);
    await assert.rejects(() => pruneTerminalJobs(ws, {
      olderThanMs: 0, onStep: (jobId, step) => { if (step === crashAt) throw new Error(`crash@${step}`); },
    }), /crash@/, crashAt);
    assert.ok(existsSync(marker), `${crashAt}: the marker is on disk before anything else is touched`);
    // The deletion is already durable: a new record with this id is refused, and a writer that finds
    // the marker reports the job gone rather than publishing.
    await assert.rejects(() => createRecord(ws, newSeed(id)), /pruned/, crashAt);
    if (crashAt === "marker") {
      assert.ok(lstatSync(recordPath(ws, id)).isFile(), "nothing else was touched yet");
    }
    // The next prune completes it — no eligibility check needed, whatever state the crash left.
    const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
    assert.deepEqual(report.resumed, [id], crashAt);
    assert.deepEqual(report.pruned, [], `${crashAt}: a resumed job is not counted twice`);
    assert.ok(isTombstone(ws, id), `${crashAt}: the tombstone stands, with its provenance`);
    assert.deepEqual(filesOf(ws, id), [`${id}.json`], `${crashAt}: no slot, no marker survive`);
    if (crashAt === "staged") {
      // The staging directory a crash left is provenance-carrying and swept once it is old enough.
      const staged = readdirSync(jobsDir(ws)).filter((n) => /^\.tomb\.[0-9a-f]{12}\.vibe-tmp$/.test(n));
      assert.equal(staged.length, 1, "the staged tombstone survived the crash, never at the canonical path");
      const old = new Date(Date.now() - 7 * 60 * 60 * 1000);
      utimesSync(path.join(jobsDir(ws), staged[0]), old, old);
      const sweep = await pruneTerminalJobs(ws, { olderThanMs: 0 });
      assert.equal(sweep.stagingSwept, 1);
      assert.ok(!existsSync(path.join(jobsDir(ws), staged[0])));
    }
    const late = path.join(jobsDir(ws), ".late.vibe-tmp");
    writeFileSync(late, "{}", "utf8");
    assert.throws(() => renameSync(late, recordPath(ws, id)), { code: "EISDIR" }, crashAt);
    await assert.rejects(() => readRecord(ws, id), /no record/, crashAt);
  }
});

test("two prunes racing on one job both finish with the tombstone standing, whoever wins each step", async () => {
  // The round-3 blocker: prune A unlinks the canonical; prune B's unlink finds nothing and used to
  // read that as "not ours", withdrawing the marker both shared. Then A crashed before the mkdir and
  // B's sweep left no canonical, no marker, no tombstone. Now: `absent` is a lost race, B proceeds.
  for (const crashA of [false, true]) {
    const ws = workspace();
    const id = "job_aaaaaaaaaaaaaaaaaaab";
    await seed(ws, {}, id);
    await updateRecord(ws, id, { kind: "beat" });
    await finaliseRecord(ws, id, { status: "completed" });
    let reportB = null;
    const runA = pruneTerminalJobs(ws, {
      olderThanMs: 0,
      onStep: async (jobId, step) => {
        if (step === "unlinked") {
          reportB = await pruneTerminalJobs(ws, { olderThanMs: 0 });      // B runs to completion in A's gap
          if (crashA) throw new Error("crash@A-after-unlink");
        }
      },
    });
    if (crashA) await assert.rejects(runA, /crash@A/);
    else {
      const reportA = await runA;
      assert.deepEqual(reportA.pruned.map((job) => job.jobId), [id]);
      assert.deepEqual(reportA.leftovers, [], "A's lost races are not leftovers");
    }
    assert.deepEqual(reportB.resumed, [id], "B found A's valid marker and completed the deletion");
    assert.deepEqual(reportB.leftovers, [], "B's lost unlink race is not a refusal");
    assert.ok(lstatSync(recordPath(ws, id)).isDirectory(), `crashA=${crashA}: the tombstone stands`);
    assert.deepEqual(filesOf(ws, id), [`${id}.json`], `crashA=${crashA}: no slot, no marker`);
    const late = path.join(jobsDir(ws), ".late.vibe-tmp");
    writeFileSync(late, "{}", "utf8");
    assert.throws(() => renameSync(late, recordPath(ws, id)), { code: "EISDIR" });
  }
});

test("a foreign file wearing the marker name is authority for nothing: the job is neither deleted nor hidden", async () => {
  const ws = workspace();
  const live = "job_bbbbbbbbbbbbbbbbbbbc";
  const other = "job_cccccccccccccccccccd";
  await seed(ws, {}, live);                                                     // running
  await seed(ws, {}, other);
  await finaliseRecord(ws, other, { status: "completed" });
  // Four impostors: unstamped, malformed, the wrong kind, another job's id.
  const impostors = [
    "{}",
    "not json",
    JSON.stringify({ "_vibe-suite_owned": { kind: "job-scratch", schema: 1 }, jobId: live }),
    JSON.stringify({ "_vibe-suite_owned": { kind: "job-prune-marker", schema: 1 }, jobId: other, createdAt: "2026-01-01T00:00:00.000Z" }),
    JSON.stringify({ "_vibe-suite_owned": { kind: "job-prune-marker", schema: 1 }, jobId: live }),   // no identity
  ];
  for (const body of impostors) {
    writeFileSync(path.join(jobsDir(ws), `${live}.pruning`), body, "utf8");
    assert.equal((await readRecord(ws, live)).status, "running", "readers still see the job");
    assert.ok((await listRecords(ws)).records.some((r) => r.jobId === live), "listRecords still lists it");
    assert.equal((await transact(ws, live, (r) => ({ ...r, kind: "still-writable" }))).kind, "still-writable");
    const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
    assert.ok(!report.resumed.includes(live), "never resumed from a foreign marker");
    assert.ok(!report.pruned.some((job) => job.jobId === live), "a running job is never pruned");
    assert.ok(report.leftovers.includes(`${live}.pruning`), "the foreign marker is reported");
    assert.ok(lstatSync(recordPath(ws, live)).isFile(), "the canonical is untouched");
    assert.ok(existsSync(path.join(jobsDir(ws), `${live}.pruning`)), "…and the impostor is not ours to delete");
  }
  // The genuinely finished job beside it was pruned normally by the first of those runs.
  assert.ok(lstatSync(recordPath(ws, other)).isDirectory());
});

test("a canonical that is not ours is never marked, and a valid marker is never withdrawn — the job is blocked and reported", async () => {
  const ws = workspace();
  const foreign = "job_dddddddddddddddddddc";
  const blocked = "job_eeeeeeeeeeeeeeeeeeed";
  const now = Date.now();
  const past = new Date(now - 30 * DAY).toISOString();
  mkdirSync(jobsDir(ws), { recursive: true });
  const looksTerminal = { ...newSeed(foreign), status: "completed", endedAt: past, updatedAt: past };
  writeFileSync(path.join(jobsDir(ws), `${foreign}.json`), JSON.stringify(looksTerminal), "utf8");   // no stamp
  let report = await pruneTerminalJobs(ws, { olderThanMs: 0, now });
  assert.deepEqual(report.leftovers, [`${foreign}.json`]);
  assert.ok(!existsSync(path.join(jobsDir(ws), `${foreign}.pruning`)), "no marker is ever written for a file we did not write");

  // A prune crashes right after unlinking; before the next prune, something that is not ours puts
  // a file back at the canonical path. The marker stays, the job is blocked, both are reported.
  await seed(ws, {}, blocked);
  await finaliseRecord(ws, blocked, { status: "failed" });
  await assert.rejects(() => pruneTerminalJobs(ws, {
    olderThanMs: 0, onStep: (jobId, step) => { if (jobId === blocked && step === "unlinked") throw new Error("crash"); },
  }), /crash/);
  writeFileSync(recordPath(ws, blocked), JSON.stringify({ ...newSeed(blocked), status: "running" }), "utf8");   // unstamped
  report = await pruneTerminalJobs(ws, { olderThanMs: 0, now });
  assert.deepEqual(report.resumed, [], "blocked, not resumed");
  // …and NAMED as blocked. A job that leaves every total — pruned, resumed, kept, blocked, invalid —
  // is the one an operator most needs to see and the one the report would never count.
  assert.deepEqual(report.blocked.sort(), [blocked, foreign].sort(),
    "both the unmarkable foreign canonical and the marked job that could not be finished are counted");
  assert.equal(report.kept, 0, "and neither is a retention decision");
  assert.deepEqual(report.leftovers.sort(), [`${blocked}.json`, `${blocked}.pruning`, `${foreign}.json`].sort());
  assert.ok(existsSync(path.join(jobsDir(ws), `${blocked}.pruning`)), "the valid marker is preserved");
  assert.ok(lstatSync(recordPath(ws, blocked)).isFile(), "the foreign file is not ours to remove");
  await assert.rejects(() => readRecord(ws, blocked), /no record/, "a validly marked job stays gone to readers");
});

test("a marker that cannot be removed at the end is a reported leftover, not a clean exit", async () => {
  const ws = workspace();
  const id = "job_ffffffffffffffffffe0";
  await seed(ws, {}, id);
  await finaliseRecord(ws, id, { status: "completed" });
  const report = await pruneTerminalJobs(ws, {
    olderThanMs: 0,
    onStep: (jobId, step) => {
      // Between the slots and the marker removal, the marker is replaced by a file that is not ours.
      if (step === "slots") writeFileSync(path.join(jobsDir(ws), `${jobId}.pruning`), "{}", "utf8");
    },
  });
  assert.deepEqual(report.pruned.map((job) => job.jobId), [id], "the job itself was deleted");
  assert.deepEqual(report.leftovers, [`${id}.pruning`], "the unremovable marker is reported");
  assert.ok(lstatSync(recordPath(ws, id)).isDirectory());
});

test("a marked job is gone to a writer mid-flight, even while its canonical still exists", async () => {
  const ws = workspace();
  const id = "job_abababababababababab";
  await seed(ws, {}, id);
  let seen = 0;
  await assert.rejects(() => transact(ws, id, (record) => {
    seen += 1;
    // Between this writer's read and its link, a prune publishes its marker and crashes.
    if (seen === 1) writeFileSync(path.join(jobsDir(ws), `${id}.pruning`), validMarker(id, record.createdAt), "utf8");
    return { ...record, kind: "stale" };
  }), /no record|gone/);
  assert.equal(JSON.parse(readFileSync(recordPath(ws, id), "utf8")).kind, "review",
    "the stale candidate was never published over the marked job");
});

test("ALREADY needs the winner's exact bytes: a slot compacted between the win and the confirmation is superseded", async () => {
  const ws = workspace();
  await seed(ws);
  const result = await transact(ws, "job_test", (record) => ({ ...record, kind: "stale" }), {
    onWon: (jobId, target) => {
      // In the window between winning v2 and confirming it: a terminal v4 is committed and the
      // canonical self-healed to it, and compaction has already removed our uncommitted v2 slot.
      const record = JSON.parse(readFileSync(recordPath(ws, jobId), "utf8"));
      const done = { ...record, version: 4, kind: "done", status: "completed", ...STAMP };
      const bytes = JSON.stringify(done, null, 2) + "\n";
      writeFileSync(path.join(jobsDir(ws), `${jobId}.v4.json`), bytes, "utf8");
      writeFileSync(recordPath(ws, jobId), bytes, "utf8");
      unlinkSync(path.join(jobsDir(ws), `${jobId}.v${target}.json`));
    },
  });
  assert.equal(result, null, "a canonical at v4 is not proof that OUR v2 was published");
  const final = JSON.parse(readFileSync(recordPath(ws, "job_test"), "utf8"));
  assert.equal(final.kind, "done");
  assert.equal(final.version, 4);
});

test("expired tombstones are removed by prune; fresh ones stay", async () => {
  const ws = workspace();
  const old = "job_6666666666666666666f";
  const fresh = "job_7777777777777777777a";
  for (const id of [old, fresh]) {
    await seed(ws, {}, id);
    await finaliseRecord(ws, id, { status: "completed" });
  }
  assert.equal((await pruneTerminalJobs(ws, { olderThanMs: 0 })).pruned.length, 2);
  const now = Date.now();
  const past = new Date(now - PRUNE_TOMBSTONE_TTL_MS - 1000);
  utimesSync(recordPath(ws, old), past, past);
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0, now });
  assert.equal(report.tombstonesExpired, 1);
  assert.ok(!existsSync(recordPath(ws, old)), "the expired tombstone is gone");
  assert.ok(isTombstone(ws, fresh), "the fresh one stands");
  assert.equal(PRUNE_TOMBSTONE_TTL_MS, 30 * DAY);
  // A directory that merely looks like an old tombstone — 0700, empty, canonical-shaped, same uid,
  // but WITHOUT this store's provenance — is never expired; it is reported, every time.
  const fake = "job_1010101010101010101a";
  mkdirSync(recordPath(ws, fake), { mode: 0o700 });
  utimesSync(recordPath(ws, fake), past, past);
  const again = await pruneTerminalJobs(ws, { olderThanMs: 0, now });
  assert.equal(again.tombstonesExpired, 0);
  assert.ok(again.leftovers.includes(`${fake}.json`), "reported as not ours");
  assert.ok(lstatSync(recordPath(ws, fake)).isDirectory(), "…and left alone");
  const listed = await listRecords(ws);
  assert.ok(listed.invalid.some((e) => e.jobId === fake && /not this store's tombstone/.test(e.reason)),
    "status shows the foreign directory instead of hiding it");
});

test("a reclaimed slot beneath a terminal top is residue that prune removes with the job", async () => {
  const ws = workspace();
  const id = "job_8888888888888888888b";
  await seed(ws, {}, id);
  await updateRecord(ws, id, { kind: "beat" });                                  // v2
  await finaliseRecord(ws, id, { status: "completed" });                          // v3, compaction frees v2
  // A writer that read v1 long ago reclaims the freed v2 pathname and crashes before learning better.
  const stale = { ...(await readRecord(ws, id)), version: 2, status: "running", kind: "stale", ...STAMP };
  writeFileSync(path.join(jobsDir(ws), `${id}.v2.json`), JSON.stringify(stale, null, 2) + "\n", "utf8");
  assert.equal((await readRecord(ws, id)).status, "completed", "the residue is inert: the top slot decides");
  assert.deepEqual(filesOf(ws, id), [`${id}.json`, `${id}.v2.json`, `${id}.v3.json`]);
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.equal(report.pruned[0].files, 3, "canonical + both slots go with the job");
  assert.deepEqual(filesOf(ws, id), [`${id}.json`], "only the tombstone remains");
});

test("a canonical already at the won version with different bytes is superseded, not confirmed", async () => {
  const ws = workspace();
  await seed(ws);
  let seen = 0;
  await transact(ws, "job_test", (record) => {
    seen += 1;
    if (seen === 1) {
      // Another writer committed v2 and its slot is no longer there — only the canonical says so.
      const raced = { ...record, version: 2, kind: "raced", ...STAMP };
      writeFileSync(recordPath(ws, "job_test"), JSON.stringify(raced, null, 2) + "\n", "utf8");
    }
    return { ...record, effort: "high" };
  });
  assert.ok(seen >= 2, "the updater must be re-run against the raced record, not applied from the stale read");
  const final = await readRecord(ws, "job_test");
  assert.equal(final.version, 3);
  assert.equal(final.kind, "raced", "the racing write must not have been clobbered");
  assert.equal(final.effort, "high");
});

test("prune removes only terminal jobs older than the cutoff, whole; running and recent jobs are untouched", async () => {
  const ws = workspace();
  const old = "job_aaaaaaaaaaaaaaaaaaaa";
  const fresh = "job_bbbbbbbbbbbbbbbbbbbb";
  const live = "job_cccccccccccccccccccc";
  const now = Date.now();
  for (const id of [old, fresh, live]) {
    await seed(ws, {}, id);
    await updateRecord(ws, id, { kind: "beat" });                                 // v2 each
  }
  await finaliseRecord(ws, old, { status: "completed", endedAt: new Date(now - 8 * DAY).toISOString() });
  await finaliseRecord(ws, fresh, { status: "failed", endedAt: new Date(now - 1 * DAY).toISOString() });
  writeFileSync(path.join(jobsDir(ws), `${old}.log`), "worker stderr\n", "utf8");

  const report = await pruneTerminalJobs(ws, { olderThanMs: 7 * DAY, now });
  assert.deepEqual(report.pruned.map((job) => job.jobId), [old]);
  assert.equal(report.pruned[0].status, "completed");
  assert.equal(report.pruned[0].files, 2, "canonical + the compacted top slot");
  assert.equal(report.kept, 2, "one recent terminal job and one running job");
  assert.deepEqual(report.invalid, []);
  assert.deepEqual(report.leftovers, []);
  assert.deepEqual(report.logsLeft, [old], "the worker log is reported as left in place");

  assert.deepEqual(filesOf(ws, old), [`${old}.json`, `${old}.log`], "the job is gone whole; its tombstone and log remain");
  assert.ok(lstatSync(recordPath(ws, old)).isDirectory());
  assert.deepEqual(filesOf(ws, fresh), [`${fresh}.json`, `${fresh}.v3.json`]);
  assert.deepEqual(filesOf(ws, live), [`${live}.json`, `${live}.v2.json`]);
  assert.equal((await readRecord(ws, live)).status, "running");
  await assert.rejects(() => readRecord(ws, old), /no record/);
});

test("prune's default cutoff is seven days, and the boundary is inclusive of older", async () => {
  assert.equal(DEFAULT_PRUNE_OLDER_THAN_MS, 7 * DAY);
  const ws = workspace();
  const older = "job_1111111111111111111a";
  const younger = "job_2222222222222222222b";
  const now = Date.now();
  await seed(ws, {}, older);
  await seed(ws, {}, younger);
  await finaliseRecord(ws, older, { status: "timed_out", endedAt: new Date(now - 7 * DAY - 1000).toISOString() });
  await finaliseRecord(ws, younger, { status: "timed_out", endedAt: new Date(now - 7 * DAY + 1000).toISOString() });
  const report = await pruneTerminalJobs(ws, { now });
  assert.deepEqual(report.pruned.map((job) => job.jobId), [older]);
  assert.equal(report.kept, 1);
});

test("prune falls back to updatedAt for a terminal record without endedAt", async () => {
  const ws = workspace();
  const id = "job_3333333333333333333c";
  const now = Date.now();
  const stale = new Date(now - 30 * DAY).toISOString();
  await seed(ws, { status: "completed", endedAt: null, updatedAt: stale }, id);
  const report = await pruneTerminalJobs(ws, { olderThanMs: 7 * DAY, now });
  assert.deepEqual(report.pruned.map((job) => job.jobId), [id]);
  assert.equal(report.pruned[0].endedAt, stale);
});

test("prune leaves alone what it cannot vouch for: invalid records and unstamped canonicals, reported", async () => {
  const ws = workspace();
  const foreign = "job_dddddddddddddddddddd";
  const bad = "job_eeeeeeeeeeeeeeeeeeee";
  const now = Date.now();
  mkdirSync(jobsDir(ws), { recursive: true });
  const past = new Date(now - 30 * DAY).toISOString();
  const looksTerminal = {
    ...newRecord({ jobId: foreign, kind: "review", sandbox: "read-only", effort: "low",
      model: null, background: false, timeoutMs: 1000, claimDigest: null }),
    status: "completed", endedAt: past, updatedAt: past,
  };
  writeFileSync(path.join(jobsDir(ws), `${foreign}.json`), JSON.stringify(looksTerminal), "utf8");   // no stamp
  writeFileSync(path.join(jobsDir(ws), `${bad}.json`),
    JSON.stringify({ jobId: bad, version: 1, status: "zombie" }), "utf8");

  const report = await pruneTerminalJobs(ws, { olderThanMs: 0, now });
  assert.deepEqual(report.pruned, []);
  assert.deepEqual(report.leftovers, [`${foreign}.json`], "a canonical without our stamp is not ours to delete");
  assert.deepEqual(report.blocked, [foreign],
    "…and that job is counted as BLOCKED, not kept: the store made no retention decision about it");
  assert.equal(report.kept, 0, "nothing here was left alone for being running or recent");
  assert.equal(report.invalid.length, 1);
  assert.equal(report.invalid[0].jobId, bad);
  assert.ok(existsSync(path.join(jobsDir(ws), `${foreign}.json`)));
  assert.ok(existsSync(path.join(jobsDir(ws), `${bad}.json`)));
});

test("prune sweeps stamped orphan slots whose canonical is gone, so a crashed prune converges", async () => {
  const ws = workspace();
  const id = "job_ffffffffffffffffffff";
  await seed(ws, {}, id);
  await updateRecord(ws, id, { kind: "beat" });
  await finaliseRecord(ws, id, { status: "completed" });                          // canonical + v3
  unlinkSync(recordPath(ws, id));                                                 // a prune that died after step one
  writeFileSync(path.join(jobsDir(ws), `${id}.v9.json`), "{}", "utf8");          // slot shape, not ours
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.deepEqual(report.pruned, []);
  assert.equal(report.orphanSlots, 1, "our stamped v3 orphan is swept");
  assert.deepEqual(report.leftovers, [`${id}.v9.json`], "the unstamped one is reported, not deleted");
  assert.deepEqual(filesOf(ws, id), [`${id}.v9.json`], "no canonical, no tombstone: a crashed prune left nothing to entomb");
});

test("a stale writer cannot reclaim a pruned job id: a fresh read finds no job, even beside a leftover slot", async () => {
  const ws = workspace();
  const id = "job_1234567890abcdef1234";
  await seed(ws, {}, id);
  await finaliseRecord(ws, id, { status: "completed" });
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.deepEqual(report.pruned.map((job) => job.jobId), [id]);
  // A stale writer's slot left beside the gap (unstamped, so no sweep removes it) must not bring the
  // job back — before vibe-204 the store rebuilt a missing canonical from exactly such a slot.
  writeFileSync(path.join(jobsDir(ws), `${id}.v9.json`),
    JSON.stringify({ jobId: id, version: 9, status: "running" }), "utf8");
  await assert.rejects(() => readRecord(ws, id), /no record/);
  await assert.rejects(() => transact(ws, id, (record) => ({ ...record, kind: "reclaimed" })), /no record/);
  assert.deepEqual((await listRecords(ws)).records, []);
  assert.ok(lstatSync(recordPath(ws, id)).isDirectory(), "nothing republished the canonical: the tombstone stands");
});

test("prune on a workspace without a state directory is a no-op report", async () => {
  const ws = workspace();
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.deepEqual(report, {
    pruned: [], resumed: [], kept: 0, blocked: [], invalid: [], leftovers: [], orphanSlots: 0,
    logsLeft: [], tombstonesExpired: 0, stagingSwept: 0,
  });
});

// ---------------------------------------------------------------------------------------------
// vibe-204 round 5: nothing is authority by name or by what a name points at.

test("a symlink to a valid marker, or a directory at the marker path, is foreign: the job is neither deleted nor hidden", async () => {
  const ws = workspace();
  const live = "job_2020202020202020202b";
  await seed(ws, {}, live);
  const record = await readRecord(ws, live);
  const elsewhere = tmpWorkspace("marker-target-");
  writeFileSync(path.join(elsewhere, "real.pruning"), validMarker(live, record.createdAt), "utf8");
  symlinkSync(path.join(elsewhere, "real.pruning"), path.join(jobsDir(ws), `${live}.pruning`));
  for (const shape of ["symlink", "directory"]) {
    if (shape === "directory") {
      unlinkSync(path.join(jobsDir(ws), `${live}.pruning`));
      mkdirSync(path.join(jobsDir(ws), `${live}.pruning`), { mode: 0o700 });
    }
    assert.equal((await readRecord(ws, live)).status, "running", shape);
    assert.ok((await listRecords(ws)).records.some((r) => r.jobId === live), shape);
    assert.equal((await transact(ws, live, (r) => ({ ...r, kind: shape }))).kind, shape);
    const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
    assert.deepEqual(report.resumed, [], shape);
    assert.deepEqual(report.pruned, [], shape);
    assert.ok(report.leftovers.includes(`${live}.pruning`), `${shape}: reported`);
    assert.ok(lstatSync(recordPath(ws, live)).isFile(), `${shape}: the record is untouched`);
    assert.ok(existsSync(path.join(elsewhere, "real.pruning")), "the symlink target is never touched");
  }
});

test("a foreign directory at the canonical path is never a tombstone: the prune is blocked, the marker kept, a late publication is caught by the next prune", async () => {
  const ws = workspace();
  const id = "job_3030303030303030303c";
  await seed(ws, {}, id);
  await updateRecord(ws, id, { kind: "beat" });
  await finaliseRecord(ws, id, { status: "completed" });
  const bytes = readFileSync(recordPath(ws, id), "utf8");
  await assert.rejects(() => pruneTerminalJobs(ws, {
    olderThanMs: 0, onStep: (jobId, step) => { if (step === "unlinked") throw new Error("crash"); },
  }), /crash/);
  // A directory that is not ours appears at the canonical path.
  mkdirSync(recordPath(ws, id), { mode: 0o700 });
  let report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.deepEqual(report.resumed, [], "blocked, not completed");
  assert.deepEqual(report.leftovers.sort(), [`${id}.json`, `${id}.pruning`].sort());
  assert.ok(existsSync(path.join(jobsDir(ws), `${id}.pruning`)), "the marker is kept");
  assert.ok(existsSync(path.join(jobsDir(ws), `${id}.v3.json`)), "the (top) slot is kept too");
  assert.ok(lstatSync(recordPath(ws, id)).isDirectory() && readdirSync(recordPath(ws, id)).length === 0, "the foreign directory is untouched");
  await assert.rejects(() => readRecord(ws, id), /no record/, "still gone to readers: the marker is valid");
  // The foreign directory disappears and a publisher paused inside its rename lands: the canonical
  // is back with the old bytes. The marker keeps the job gone, and the next prune finishes it.
  rmdirSync(recordPath(ws, id));
  const late = path.join(jobsDir(ws), ".late.vibe-tmp");
  writeFileSync(late, bytes, "utf8");
  renameSync(late, recordPath(ws, id));
  await assert.rejects(() => readRecord(ws, id), /no record/);
  report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.deepEqual(report.resumed, [id]);
  assert.ok(isTombstone(ws, id));
  assert.deepEqual(filesOf(ws, id), [`${id}.json`]);
});

test("createRecord is linearised against the marker: a creation that lands behind a concurrent prune's marker withdraws itself", async () => {
  const ws = workspace();
  const id = "job_4040404040404040404d";
  const fresh = newSeed(id);
  await assert.rejects(() => createRecord(ws, fresh, {
    onPublished: (jobId) => {
      // Between this creation's publish and its re-check, a prune marks the id — for the OLD record
      // it judged eligible (a different identity) — and unlinks that record.
      writeFileSync(path.join(jobsDir(ws), `${jobId}.pruning`), validMarker(jobId, "2026-01-01T00:00:00.000Z"), "utf8");
    },
  }), /pruned/, "the caller is never told the creation landed");
  assert.ok(!existsSync(recordPath(ws, id)), "the record withdrew itself");
  // The prune side: a valid marker whose identity is not the record at the path blocks (the
  // record withdraws itself; the prune never deletes a record it did not judge).
  const other = "job_5050505050505050505e";
  await seed(ws, {}, other);
  writeFileSync(path.join(jobsDir(ws), `${other}.pruning`), validMarker(other, "2026-01-01T00:00:00.000Z"), "utf8");
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  // The marker left behind for the withdrawn id is a deletion that began: it is completed (no record
  // stands at the path, so the tombstone goes straight in) — while `other` is blocked and reported.
  assert.deepEqual(report.resumed, [id]);
  assert.ok(isTombstone(ws, id));
  assert.deepEqual(report.leftovers.sort(), [`${other}.json`, `${other}.pruning`].sort());
  assert.deepEqual(report.blocked, [other], "and the blocked job is counted, not left out of every total");
  assert.equal(report.kept, 0, "…as blocked, not as a retention decision the store never made");
  assert.ok(lstatSync(recordPath(ws, other)).isFile(), "a record of another identity is never unlinked under a marker");
});

test("losing the marker race to a prune that already finished counts as nothing — no phantom leftover, no double count", async () => {
  const ws = workspace();
  const id = "job_6060606060606060606f";
  await seed(ws, {}, id);
  await finaliseRecord(ws, id, { status: "completed" });
  let inner = null;
  let ran = false;
  const outer = await pruneTerminalJobs(ws, {
    olderThanMs: 0,
    onStep: async (jobId, step) => {
      // Inside A's marker step, B runs from scratch to completion (B finds A's valid marker and
      // resumes it, removing it at the end) — so A's later steps find everything already done.
      if (step === "marker" && !ran) { ran = true; inner = await pruneTerminalJobs(ws, { olderThanMs: 0 }); }
    },
  });
  assert.deepEqual(inner.resumed, [id]);
  assert.deepEqual(inner.leftovers, []);
  assert.deepEqual(outer.leftovers, [], "A's absent slots, absent marker and existing tombstone are not leftovers");
  assert.ok(isTombstone(ws, id));
});

test("a slot that is not ours — unstamped, or a symlink — survives compaction and prune, and is reported", async () => {
  const ws = workspace();
  const id = "job_7070707070707070707a";
  await seed(ws, {}, id);
  await updateRecord(ws, id, { kind: "beat" });
  const elsewhere = tmpWorkspace("slot-target-");
  writeFileSync(path.join(elsewhere, "v0.json"), "{}", "utf8");
  symlinkSync(path.join(elsewhere, "v0.json"), path.join(jobsDir(ws), `${id}.v0.json`));
  writeFileSync(path.join(jobsDir(ws), `${id}.v1.json`), "{}", "utf8");        // unstamped, slot-shaped
  await finaliseRecord(ws, id, { status: "completed" });                        // v3; compaction
  assert.deepEqual(filesOf(ws, id), [`${id}.json`, `${id}.v0.json`, `${id}.v1.json`, `${id}.v3.json`],
    "compaction removed only our v2");
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.deepEqual(report.pruned.map((job) => job.jobId), [id]);
  assert.deepEqual(report.leftovers.sort(), [`${id}.v0.json`, `${id}.v1.json`]);
  assert.ok(isTombstone(ws, id));
  assert.ok(existsSync(path.join(elsewhere, "v0.json")), "the symlink target is never touched");
});

// --------------------------------------------------------------------- vibe-204 round 6 helpers

async function seedTerminal(ws, jobId) {
  await createRecord(ws, newSeed(jobId));
  await updateRecord(ws, jobId, { kind: "beat" });
  return finaliseRecord(ws, jobId, { status: "completed" });
}

/** Write a record file directly — a second incarnation of the same id, as `createRecord` would. */
function plantRecord(ws, jobId, { createdAt, incarnation }) {
  const record = { ...newSeed(jobId), createdAt, updatedAt: createdAt, incarnation };
  writeFileSync(recordPath(ws, jobId), JSON.stringify({ ...record, ...STAMP }, null, 2) + "\n", "utf8");
  return record;
}

/** A tombstone directory of ours, built by hand (a peer prune's finished work). */
function plantTombstone(ws, jobId, { name = null, extra = null, stamp = true } = {}) {
  const p = name === null ? recordPath(ws, jobId) : path.join(jobsDir(ws), name);
  mkdirSync(p, { mode: 0o700 });
  if (stamp) {
    writeFileSync(path.join(p, TOMBSTONE_STAMP),
      JSON.stringify({ "_vibe-suite_owned": { kind: "job-tombstone", schema: 1 }, jobId }) + "\n", "utf8");
  }
  if (extra !== null) writeFileSync(path.join(p, extra), "{}\n", "utf8");
  return p;
}

const ageTo = (p, ms) => {
  const when = (Date.now() - ms) / 1000;
  utimesSync(p, when, when);
};

// ---------------------------------------------------------------------------------------------
// Finding 1 — identity at the mutation, not one step earlier.

test("a record published in the gap is NOT unlinked, even when it reuses the pruned record's createdAt",
  async () => {
    // Round-5 blocker: `entomb` validated the canonical with `ownedRecordAt` and then called an
    // unqualified `removeOwned`, which accepts any `job-scratch` stamp. Two prunes can both validate
    // incarnation I; A unlinks it; a `createRecord` paused inside `publishNew` lands incarnation J;
    // B then deletes J on kind alone. A reused `createdAt` defeats a `createdAt`-only predicate, so
    // the identity has to be an incarnation the store mints, and it has to be checked by the
    // operation that mutates.
    const ws = workspace();
    const id = "job_aaaaaaaaaaaaaaaaaa01";
    const original = await seedTerminal(ws, id);
    let planted = null;
    const report = await pruneTerminalJobs(ws, {
      olderThanMs: 0,
      onStep: (jobId, step) => {
        if (step !== "marker" || planted !== null) return;
        unlinkSync(recordPath(ws, jobId));                       // prune A's unlink
        planted = plantRecord(ws, jobId, {                       // createRecord's paused publish
          createdAt: original.createdAt, incarnation: "b".repeat(32),
        });
      },
    });
    assert.ok(lstatSync(recordPath(ws, id)).isFile(),
      "the new incarnation survives the prune (a directory here means it was deleted and entombed)");
    assert.equal(JSON.parse(readFileSync(recordPath(ws, id), "utf8")).incarnation, planted.incarnation);
    assert.deepEqual(report.pruned, [], "nothing is reported pruned: the record judged is gone, this one was not judged");
    assert.ok(report.leftovers.includes(`${id}.json`), "the record that blocked the prune is reported");
    assert.ok(report.leftovers.includes(`${id}.pruning`), "the marker is kept and reported");
  });

test("createRecord fails when its own canonical no longer stands — a tombstone won the race", async () => {
  // Round-5 blocker, second half: the post-publish proof was marker-only, so a prune that finished
  // and removed its marker inside the window left `createRecord` reporting success while only a
  // tombstone remained.
  const ws = workspace();
  const id = "job_aaaaaaaaaaaaaaaaaa02";
  await createRecord(ws, newSeed("job_aaaaaaaaaaaaaaaaaa99"));                 // the store exists
  await assert.rejects(createRecord(ws, newSeed(id), {
    onPublished: (jobId) => {
      unlinkSync(recordPath(ws, jobId));                                       // the peer's unlink
      plantTombstone(ws, jobId);                                               // …and its tombstone
    },
  }), /did not stand|is pruned/);
  assert.ok(lstatSync(recordPath(ws, id)).isDirectory(), "the tombstone is untouched");
});

test("createRecord withdraws only its own incarnation, never another record that took the path", async () => {
  // The withdrawal was `removeOwned(dir, name, [SCRATCH_KIND])` — kind alone. A record another
  // writer published in the window is not ours to delete just because a marker appeared.
  const ws = workspace();
  const id = "job_aaaaaaaaaaaaaaaaaa03";
  const other = { createdAt: new Date().toISOString(), incarnation: "c".repeat(32) };
  await assert.rejects(createRecord(ws, newSeed(id), {
    onPublished: (jobId) => {
      unlinkSync(recordPath(ws, jobId));
      plantRecord(ws, jobId, other);                                           // a different incarnation
      writeFileSync(path.join(jobsDir(ws), `${jobId}.pruning`),
        JSON.stringify({
          "_vibe-suite_owned": { kind: "job-prune-marker", schema: 1 },
          jobId, createdAt: other.createdAt, incarnation: "d".repeat(32),
        }) + "\n", "utf8");
    },
  }), /is pruned|did not stand/);
  assert.ok(existsSync(recordPath(ws, id)), "the other incarnation is still there");
  assert.equal(JSON.parse(readFileSync(recordPath(ws, id), "utf8")).incarnation, other.incarnation);
});

// ---------------------------------------------------------------------------------------------
// Finding 3 — concurrency reporting.

test("a prune whose marker is fresh over a standing tombstone counts nothing and reports nothing",
  async () => {
    // Round-5 medium: a prune paused before linking its marker resumes after a peer entombed the job
    // and removed the first marker. It wins the link, sees the tombstone, and used to report the job
    // pruned a second time with one file removed — a file it never removed.
    const ws = workspace();
    const id = "job_aaaaaaaaaaaaaaaaaa04";
    await seedTerminal(ws, id);
    let peer = null;
    const mine = await pruneTerminalJobs(ws, {
      olderThanMs: 0,
      onStep: async (jobId, step) => {
        if (step !== "preflight" || peer !== null) return;
        peer = await pruneTerminalJobs(ws, { olderThanMs: 0 });                 // the peer finishes
      },
    });
    assert.ok(peer !== null, "the preflight seam fires before the marker is published");
    assert.deepEqual(peer.pruned.map((job) => job.jobId), [id], "the peer pruned the job once");
    assert.deepEqual(mine.pruned, [], "the resumed prune does not report the job a second time");
    assert.deepEqual(mine.resumed, [], "nor as a resumed one: nothing of it was left to finish");
    assert.deepEqual(mine.leftovers, [], "and leaves nothing behind");
    assert.deepEqual(filesOf(ws, id), [`${id}.json`], "the tombstone stands alone: the fresh marker is gone");
  });

test("a concurrent expiry sees the tombstone path vacated, not an unprovenanced directory", async () => {
  // Round-5 medium: removal unlinked the stamp in place, so a peer arriving in the gap saw a
  // directory it could not prove and reported a phantom leftover. Removal now vacates the canonical
  // path by rename FIRST, so the only states a peer can observe are "tombstone" and "absent".
  const ws = workspace();
  const id = "job_aaaaaaaaaaaaaaaaaa05";
  await seedTerminal(ws, id);
  await pruneTerminalJobs(ws, { olderThanMs: 0 });
  ageTo(recordPath(ws, id), PRUNE_TOMBSTONE_TTL_MS + DAY);
  let peer = null;
  const mine = await pruneTerminalJobs(ws, {
    olderThanMs: 0,
    onStep: async (jobId, step) => {
      if (step !== "vacated" || peer !== null) return;
      peer = await pruneTerminalJobs(ws, { olderThanMs: 0 });
    },
  });
  assert.ok(peer !== null, "the vacate seam fires between taking the path and removing the directory");
  assert.deepEqual(peer.leftovers, [], "the peer reports no phantom leftover");
  assert.deepEqual(mine.leftovers, [], "and neither does the run that lost a step of its own removal");
  const counted = mine.tombstonesExpired + peer.tombstonesExpired + mine.stagingSwept + peer.stagingSwept;
  assert.equal(counted, 1, "the directory is accounted for exactly once between the two runs");
  assert.deepEqual(filesOf(ws, id), [], "nothing of the job is left");
  assert.deepEqual(readdirSync(jobsDir(ws)).filter((n) => n.startsWith(".tomb.")), [],
    "and no staging directory is stranded");
});

// ---------------------------------------------------------------------------------------------
// Finding 4 — the declared crash-residue rows.

test("an empty staging directory left by a crash before the stamp was published converges", async () => {
  // `installTombstone` creates `.tomb.<nonce>.vibe-tmp/` and then publishes the stamp inside it. A
  // crash between the two leaves a directory with no provenance, which the sweep refused forever.
  // Under the pinned threat model nothing but this store writes here, and `rmdir` cannot destroy
  // data: an EMPTY staging directory past the reap age is removed.
  const ws = workspace();
  const staged = path.join(jobsDir(ws), ".tomb.0123456789ab.vibe-tmp");
  await createRecord(ws, newSeed("job_aaaaaaaaaaaaaaaaaa06"));
  mkdirSync(staged, { mode: 0o700 });
  ageTo(staged, TEMP_REAP_MIN_AGE_MS + DAY);
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.equal(existsSync(staged), false, "the empty staging directory is gone");
  assert.equal(report.stagingSwept, 1);
  assert.deepEqual(report.leftovers, [], "and it is not reported as residue an operator must clear");
});

test("an empty staging directory left by a crash after the stamp was removed converges too", async () => {
  // The tail of a removal: the directory was vacated out of the canonical namespace, its stamp
  // unlinked, and the process died before `rmdir`. Same shape, same rule.
  const ws = workspace();
  const id = "job_aaaaaaaaaaaaaaaaaa07";
  await seedTerminal(ws, id);
  await pruneTerminalJobs(ws, { olderThanMs: 0 });
  const staged = plantTombstone(ws, id, { name: ".tomb.fedcba987654.vibe-tmp", stamp: false });
  ageTo(staged, TEMP_REAP_MIN_AGE_MS + DAY);
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.equal(existsSync(staged), false);
  assert.equal(report.stagingSwept, 1);
  assert.deepEqual(report.leftovers, []);
});

test("a live staging directory is never swept, empty or not", async () => {
  const ws = workspace();
  await createRecord(ws, newSeed("job_aaaaaaaaaaaaaaaaaa08"));
  const fresh = path.join(jobsDir(ws), ".tomb.aabbccddeeff.vibe-tmp");
  mkdirSync(fresh, { mode: 0o700 });
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.ok(existsSync(fresh), "younger than the reap age: another prune may be staging it right now");
  assert.equal(report.stagingSwept, 0);
});

test("a non-empty staging directory without provenance is refused and reported, never removed", async () => {
  const ws = workspace();
  await createRecord(ws, newSeed("job_aaaaaaaaaaaaaaaaaa09"));
  const staged = path.join(jobsDir(ws), ".tomb.001122334455.vibe-tmp");
  mkdirSync(staged, { mode: 0o700 });
  writeFileSync(path.join(staged, "something.json"), "{}\n", "utf8");
  ageTo(staged, TEMP_REAP_MIN_AGE_MS + DAY);
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.ok(existsSync(staged), "rmdir removes nothing that holds data, and nothing here descends");
  assert.equal(report.stagingSwept, 0);
  assert.ok(report.leftovers.includes(".tomb.001122334455.vibe-tmp"));
});

test("a tombstone holding an extra entry keeps the job gone, is reported every run, and is never removed",
  async () => {
    // The third declared residue row: `removeOwnedDirAt` requires the stamp and NOTHING else, so a
    // tombstone with a second entry cannot expire. It stays a reported, operator-owned object — the
    // job stays gone to every reader, and nothing of ours is deleted around it.
    const ws = workspace();
    const id = "job_aaaaaaaaaaaaaaaaaa10";
    await createRecord(ws, newSeed("job_aaaaaaaaaaaaaaaaaa98"));                // the store exists
    plantTombstone(ws, id, { extra: "left-behind.json" });
    ageTo(recordPath(ws, id), PRUNE_TOMBSTONE_TTL_MS + DAY);
    for (const run of [1, 2]) {
      const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
      assert.equal(report.tombstonesExpired, 0, `run ${run}: never expired`);
      assert.ok(report.leftovers.includes(`${id}.json`), `run ${run}: reported`);
      assert.ok(existsSync(path.join(recordPath(ws, id), "left-behind.json")), `run ${run}: nothing inside is touched`);
    }
    await assert.rejects(readRecord(ws, id), /no record/, "the job is gone to readers");
    const listed = await listRecords(ws);
    assert.deepEqual(listed.records.filter((record) => record.jobId === id), [], "and it is not a record");
    assert.deepEqual(listed.invalid.filter((entry) => entry.jobId === id), [], "nor an unreadable one");
  });

/** A record file written directly, with `incarnation` omitted — a record from before the field. */
function plantLegacyRecord(ws, jobId, { createdAt, status = "completed" } = {}) {
  const record = { ...newSeed(jobId), status, createdAt, updatedAt: createdAt, endedAt: createdAt };
  delete record.incarnation;
  writeFileSync(recordPath(ws, jobId), JSON.stringify({ ...record, ...STAMP }, null, 2) + "\n", "utf8");
  return record;
}

const mentions = (report, id) =>
  report.pruned.filter((job) => job.jobId === id).length + report.resumed.filter((j) => j === id).length;

test("three prunes relaying one marker report the job exactly once", async () => {
  // Review finding 1: A completes the deletion and removes its marker. B, paused at `preflight`,
  // publishes a FRESH marker over A's tombstone. C then adopts B's marker, and — having adopted
  // rather than published it — used to read the standing tombstone as a genuine interrupted
  // deletion, report `resumed`, and give the job a second line after A's `pruned`.
  const ws = workspace();
  const id = "job_bbbbbbbbbbbbbbbbbb01";
  await seedTerminal(ws, id);
  let a = null;
  let c = null;
  const b = await pruneTerminalJobs(ws, {
    olderThanMs: 0,
    onStep: async (jobId, step) => {
      if (step === "preflight" && a === null) a = await pruneTerminalJobs(ws, { olderThanMs: 0 });
      if (step === "marker" && a !== null && c === null) c = await pruneTerminalJobs(ws, { olderThanMs: 0 });
    },
  });
  assert.ok(a !== null && c !== null, "both seams fired");
  assert.equal(mentions(a, id), 1, "A deleted the job and says so");
  assert.equal(mentions(c, id), 0, "C adopted a marker published over a tombstone it did not make");
  assert.equal(mentions(b, id), 0, "and B, whose marker that was, removed nothing either");
  assert.deepEqual([...a.leftovers, ...b.leftovers, ...c.leftovers], [], "no run reports a leftover");
  assert.deepEqual(readdirSync(jobsDir(ws)).filter((n) => n.startsWith(`${id}.`)), [`${id}.json`],
    "the tombstone stands alone: every stray marker was withdrawn");
  assert.ok(lstatSync(recordPath(ws, id)).isDirectory());
});

// --------------------------------------------------------------------- finding 2 (medium)


test("two sweeps over one aged staging directory: removed once, reported by neither", async () => {
  const ws = workspace();
  await createRecord(ws, newSeed("job_bbbbbbbbbbbbbbbbbb02"));
  const { mkdirSync } = await import("node:fs");
  const staged = path.join(jobsDir(ws), ".tomb.0f0f0f0f0f0f.vibe-tmp");
  mkdirSync(staged, { mode: 0o700 });
  writeFileSync(path.join(staged, ".vibe-suite-tombstone"),
    JSON.stringify({ "_vibe-suite_owned": { kind: "job-tombstone", schema: 1 }, jobId: "job_bbbbbbbbbbbbbbbbbb02" }) + "\n",
    "utf8");
  const old = (Date.now() - 7 * 60 * 60 * 1000) / 1000;
  utimesSync(staged, old, old);
  const first = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  const second = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.equal(first.stagingSwept, 1);
  assert.equal(second.stagingSwept, 0, "the second sweep finds nothing, and says nothing");
  assert.deepEqual([...first.leftovers, ...second.leftovers], []);
  assert.ok(!existsSync(staged));
});

// --------------------------------------------------------------------- finding 3 (low)


test("a record written before incarnations existed is still prunable, matched on createdAt", async () => {
  const ws = workspace();
  const id = "job_bbbbbbbbbbbbbbbbbb03";
  await createRecord(ws, newSeed("job_bbbbbbbbbbbbbbbbbb99"));                  // the store exists
  const legacy = plantLegacyRecord(ws, id, { createdAt: new Date(Date.now() - 60_000).toISOString() });
  assert.equal("incarnation" in legacy, false, "the fixture really has no incarnation");
  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.deepEqual(report.pruned.map((job) => job.jobId), [id]);
  assert.deepEqual(report.leftovers, []);
  assert.ok(lstatSync(recordPath(ws, id)).isDirectory(), "and it is entombed like any other job");
});


test("a legacy identity never stands in for a record created since, even on the same createdAt", async () => {
  // The asymmetry that makes the reused-`createdAt` collision unreachable in the dangerous
  // direction: a marker committed to a record with no incarnation must not match a record that has
  // one, however the two timestamps compare.
  const ws = workspace();
  const id = "job_bbbbbbbbbbbbbbbbbb04";
  await createRecord(ws, newSeed("job_bbbbbbbbbbbbbbbbbb98"));
  const when = new Date(Date.now() - 60_000).toISOString();
  plantLegacyRecord(ws, id, { createdAt: when });
  let planted = null;
  const report = await pruneTerminalJobs(ws, {
    olderThanMs: 0,
    onStep: (jobId, step) => {
      if (step !== "marker" || jobId !== id || planted !== null) return;
      unlinkSync(recordPath(ws, jobId));
      const record = { ...newSeed(jobId), createdAt: when, updatedAt: when, incarnation: "e".repeat(32) };
      writeFileSync(recordPath(ws, jobId),
        JSON.stringify({ ...record, ...STAMP }, null, 2) + "\n", "utf8");
      planted = record;
    },
  });
  assert.ok(planted !== null && lstatSync(recordPath(ws, id)).isFile(), "the newer record survives");
  assert.equal(JSON.parse(readFileSync(recordPath(ws, id), "utf8")).incarnation, planted.incarnation);
  assert.deepEqual(report.pruned, []);
  assert.ok(report.leftovers.includes(`${id}.json`) && report.leftovers.includes(`${id}.pruning`));
  await assert.rejects(readRecord(ws, id), /is pruned|no record/, "the job stays gone behind its marker");
});

const STAGING_STAMP_MODE = 0o700;

/** An aged staging directory of ours, as a crash between staging and the rename leaves one. */
function plantStaging(ws, name, jobId) {
  const p = path.join(jobsDir(ws), name);
  mkdirSync(p, { mode: STAGING_STAMP_MODE });
  writeFileSync(path.join(p, TOMBSTONE_STAMP),
    JSON.stringify({ "_vibe-suite_owned": { kind: "job-tombstone", schema: 1 }, jobId, attempt: null }) + "\n",
    "utf8");
  ageTo(p, 7 * 60 * 60 * 1000);
  return p;
}

test("two sweeps that both validate the same staging directory: one count, no leftover, no throw", async () => {
  // The interleaving the sequential test did not reach: sweeper A validates the directory, and B
  // runs the whole way through in the window before A's unlink. A's unlink then finds nothing.
  // Before the fix that was an ENOENT raised out of `unlinkOwned`, aborting A's sweep entirely.
  const ws = workspace();
  const id = "job_cccccccccccccccccc01";
  await createRecord(ws, newSeed(id));
  const staged = plantStaging(ws, ".tomb.a1a1a1a1a1a1.vibe-tmp", id);
  let peer = null;
  const mine = await pruneTerminalJobs(ws, {
    olderThanMs: 0,
    onStep: async (what, step) => {
      if (step !== "staging-validated" || peer !== null) return;
      peer = await pruneTerminalJobs(ws, { olderThanMs: 0 });      // B validates and finishes here
    },
  });
  assert.ok(peer !== null, "the staging-validated seam fires between validation and the unlink");
  assert.equal(mine.stagingSwept + peer.stagingSwept, 1, "the directory is counted exactly once");
  assert.deepEqual([...mine.leftovers, ...peer.leftovers], [], "and neither run reports a leftover");
  assert.ok(!existsSync(staged));
});


test("the mirror order: the peer removes only the stamp, and the first sweeper still finishes", async () => {
  const ws = workspace();
  const id = "job_cccccccccccccccccc02";
  await createRecord(ws, newSeed(id));
  const staged = plantStaging(ws, ".tomb.b2b2b2b2b2b2.vibe-tmp", id);
  const { unlinkSync } = await import("node:fs");
  const mine = await pruneTerminalJobs(ws, {
    olderThanMs: 0,
    onStep: (what, step) => {
      if (step !== "staging-validated") return;
      unlinkSync(path.join(staged, TOMBSTONE_STAMP));             // a peer got as far as the stamp
    },
  });
  assert.equal(mine.stagingSwept, 1, "the empty-directory fallback finishes what the peer started");
  assert.deepEqual(mine.leftovers, []);
  assert.ok(!existsSync(staged));
});

test("both sweepers judge the same stamp; the one that loses the unlink does not abort the sweep", async () => {
  // The reachable window, and the one the previous iteration's tests missed: `holdsOnly` is passed
  // by BOTH sweepers, both open the stamp and read it, and only then does one of them unlink. The
  // loser reaches its own `fs.unlink` and finds nothing. Before the fix that raised ENOENT out of
  // `unlinkOwned` and out of `pruneTerminalJobs` with it, abandoning every sweep behind it.
  const ws = workspace();
  const id = "job_dddddddddddddddddd01";
  await createRecord(ws, newSeed(id));
  const staged = plantStaging(ws, ".tomb.c3c3c3c3c3c3.vibe-tmp", id);
  let peer = null;
  const mine = await pruneTerminalJobs(ws, {
    olderThanMs: 0,
    onStep: async (what, step) => {
      if (step !== "staging-stamp-judged" || peer !== null) return;
      peer = await pruneTerminalJobs(ws, { olderThanMs: 0 });   // B runs to completion in A's window
    },
  });
  assert.ok(peer !== null, "the seam fires between the stamp being read and being unlinked");
  assert.equal(peer.stagingSwept, 1, "the sweeper that won the unlink counts it");
  assert.equal(mine.stagingSwept, 0, "the one that lost counts nothing");
  assert.deepEqual([...mine.leftovers, ...peer.leftovers], [], "and neither reports a leftover");
  assert.ok(!existsSync(staged), "the directory is gone");
});

test("a job pruned after the contested staging directory is still pruned — the sweep is not abandoned",
  async () => {
    // Why the abort mattered: the staging sweep is the last thing `pruneTerminalJobs` does, and a
    // throw from it discards the whole run's report, including work already done.
    const ws = workspace();
    const id = "job_dddddddddddddddddd02";
    await createRecord(ws, newSeed(id));
    const staged = plantStaging(ws, ".tomb.d4d4d4d4d4d4.vibe-tmp", id);
    let peer = null;
    const mine = await pruneTerminalJobs(ws, {
      olderThanMs: 0,
      onStep: async (what, step) => {
        if (step !== "staging-stamp-judged" || peer !== null) return;
        peer = await pruneTerminalJobs(ws, { olderThanMs: 0 });
      },
    });
    assert.ok(peer !== null);
    assert.equal(typeof mine.kept, "number", "the losing run still returns a report");
    assert.equal(mine.kept, 1, "and it still accounts for the running job it kept");
    assert.ok(!existsSync(staged));
  });

test("a foreign slot beside a job that is NOT being pruned is reported every run", async () => {
  // Step-8 finding: the orphan sweep skipped every slot whose canonical was present, so a
  // slot-shaped entry that is not ours went unreported beside a live job — while the retention
  // documentation promised it is reported every run. Ownership is proven by a non-following stamped
  // read; nothing here is removed, because these slots belong to a job this sweep is not deleting.
  const ws = workspace();
  const id = "job_eeeeeeeeeeeeeeeeee01";
  await seed(ws, {}, id);
  await updateRecord(ws, id, { kind: "beat" });                        // our own slots: v1, v2
  const foreign = path.join(jobsDir(ws), `${id}.v9.json`);
  writeFileSync(foreign, "{}\n", "utf8");                              // unstamped: not ours
  mkdirSync(path.join(jobsDir(ws), `${id}.v8.json`), { mode: 0o700 });  // a slot-shaped directory
  const elsewhere = path.join(jobsDir(ws), ".target.json");
  writeFileSync(elsewhere, "{}\n", "utf8");
  symlinkSync(elsewhere, path.join(jobsDir(ws), `${id}.v7.json`));      // a slot-shaped symlink

  for (const run of [1, 2]) {
    const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
    assert.ok(report.leftovers.includes(`${id}.v9.json`), `run ${run}: the unstamped file is reported`);
    assert.ok(report.leftovers.includes(`${id}.v8.json`), `run ${run}: the directory is reported`);
    assert.ok(report.leftovers.includes(`${id}.v7.json`), `run ${run}: the symlink is reported`);
    assert.equal(report.orphanSlots, 0, `run ${run}: nothing belonging to this job is swept`);
    assert.deepEqual(report.pruned, [], `run ${run}: and nothing is pruned`);
    // The job itself is reported rather than silently dropped. It reads as INVALID here because the
    // highest slot is chosen by NAME — the pre-existing read path this issue declares out of scope
    // (#261) — so the foreign v9 is what a read resolves. That is the declared boundary, visible:
    // the store reports what it met and deletes none of it.
    assert.deepEqual(report.invalid.map((entry) => entry.jobId), [id],
      `run ${run}: the job is accounted for, not dropped`);
    for (const own of [`${id}.v1.json`, `${id}.v2.json`]) {
      assert.ok(!report.leftovers.includes(own), `run ${run}: ${own} is ours and is not a leftover`);
    }
  }
  assert.ok(existsSync(foreign) && existsSync(elsewhere), "nothing foreign is deleted");
  assert.ok(existsSync(recordPath(ws, id)), "and the record itself is untouched");
});

test("a job blocked by a foreign marker is reported as blocked, never as kept", async () => {
  // Step-8 finding: an id wearing a foreign marker was added to the blocked set before the canonical
  // loop, so a running job could vanish from the totals entirely; and an eligible terminal record
  // that could not be deleted was counted as `kept`, which reads as a retention decision the store
  // never made.
  const ws = workspace();
  const running = "job_eeeeeeeeeeeeeeeeee02";
  const terminal = "job_eeeeeeeeeeeeeeeeee03";
  await seed(ws, {}, running);
  await seed(ws, {}, terminal);
  await finaliseRecord(ws, terminal, { status: "completed" });
  writeFileSync(path.join(jobsDir(ws), `${running}.pruning`), "not ours\n", "utf8");
  writeFileSync(path.join(jobsDir(ws), `${terminal}.pruning`), "not ours\n", "utf8");

  const report = await pruneTerminalJobs(ws, { olderThanMs: 0 });
  assert.deepEqual(report.blocked.sort(), [running, terminal].sort(),
    "both jobs are accounted for, neither silently dropped");
  assert.equal(report.kept, 0, "and neither is reported as a retention decision");
  assert.deepEqual(report.pruned, []);
  assert.ok(report.leftovers.includes(`${running}.pruning`));
  assert.ok(report.leftovers.includes(`${terminal}.pruning`));
});
