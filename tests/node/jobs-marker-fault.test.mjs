// SPDX-License-Identifier: ISC
// vibe-302 round 2 — a prune marker that cannot be inspected, on the READ path.
//
// `inspectMarker` rethrows any `lstat` failure but ENOENT raw. On a read, that raw error used to
// replace a canonical refusal already observed and — inside `commit` — leave the store UNFLAGGED,
// so `readCanonical`'s best-effort self-heal swallowed it and handed the caller the slot as a
// healthy record (round-1 Step-8, F1). A marker that cannot be inspected is now the canonical's own
// refusal when there is one, and otherwise a flagged refusal naming the marker with the procedure.
//
// The window inside `commit` has no filesystem-only reproduction without a race (a directory that
// loses search permission earlier is refused at the slot read first), so the fault is injected on
// `lstat` of the marker pathname — a raw-throwing step of a marker inspection (`readOwned`'s
// containment checks and `close` are others) — using the same technique as
// `jobs-listing-snapshot.test.mjs`: the CJS `fs.promises` object is patched BEFORE the store is
// linked, which is why the store and the helpers are imported dynamically below. The same injection
// on `<id>.json` reaches the listing's inspection of a directory at a canonical path (N24).
import { strict as assert } from "node:assert";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const require = createRequire(import.meta.url);
const fsCjs = require("fs");
const realLstat = fsCjs.promises.lstat;

/** The job ids whose `<jobId>.pruning` lstat fails EACCES; likewise `<jobId>.json` for `faultCanonicalFor`. */
let faultFor = new Set();
let faultCanonicalFor = new Set();
let faults = 0;

Object.defineProperty(fsCjs.promises, "lstat", {
  configurable: true,
  writable: true,
  value: async (target, ...rest) => {
    const name = path.basename(String(target));
    if ((name.endsWith(".pruning") && faultFor.has(name.slice(0, -".pruning".length)))
        || (name.endsWith(".json") && faultCanonicalFor.has(name.slice(0, -".json".length)))) {
      faults += 1;
      const error = new Error(`EACCES: permission denied, lstat '${target}'`);
      Object.assign(error, { code: "EACCES", errno: -13, syscall: "lstat", path: String(target) });
      throw error;
    }
    return realLstat(target, ...rest);
  },
});

const { tmpWorkspace } = await import("./_tmp.mjs");
const { slotBytes } = await import("./_stamp.mjs");
const {
  createRecord, jobsDir, listRecords, newRecord, readRecord, recordPath, JobStoreError,
} = await import("../../scripts/lib/jobs.mjs");

const ID = "job_0123456789abcdef0123";
const seedRecord = (jobId = ID) => newRecord({
  jobId, kind: "review", sandbox: "read-only", effort: "low",
  model: null, background: true, timeoutMs: 1000, claimDigest: null,
});
const GUIDANCE = /preserve the canonical and every slot, then quarantine the job or recover it offline/;

test("vibe-302 N20: a canonical refused inside the self-heal is not swallowed when the marker cannot be inspected", async () => {
  const ws = tmpWorkspace("jobs-marker-fault-n20-");
  await createRecord(ws, seedRecord());
  const canonical = recordPath(ws, ID);
  const v1 = JSON.parse(readFileSync(canonical, "utf8"));
  writeFileSync(path.join(jobsDir(ws), `${ID}.v2.json`), slotBytes({ ...v1, version: 2, kind: "later" }), "utf8");
  const { "_vibe-suite_owned": _stamp, ...unstamped } = v1;
  const planted = JSON.stringify(unstamped);
  let fired = false;
  faults = 0;
  try {
    await assert.rejects(() => readRecord(ws, ID, {
      onSelfHeal: () => {
        if (fired) return;
        fired = true;
        writeFileSync(canonical, planted, "utf8");      // the canonical turns foreign in the window …
        faultFor = new Set([ID]);                       // … and its marker can no longer be inspected
      },
    }), (error) => error instanceof JobStoreError && /no ownership stamp/.test(error.message)
      && error.refusal === true && GUIDANCE.test(error.message));
  } finally {
    faultFor = new Set();
  }
  assert.ok(fired, "the seam fired: the swap landed inside the self-heal window");
  assert.ok(faults > 0, "the fault reached the marker inspection");
  assert.equal(readFileSync(canonical, "utf8"), planted, "nothing was published over the foreign canonical");
});

test("vibe-302 N21: a healthy job whose marker cannot be inspected is refused by name with the guidance, never a bare errno", async () => {
  const ws = tmpWorkspace("jobs-marker-fault-n21-");
  await createRecord(ws, seedRecord());
  const before = readFileSync(recordPath(ws, ID), "utf8");
  faults = 0;
  faultFor = new Set([ID]);
  try {
    await assert.rejects(() => readRecord(ws, ID), (error) => error instanceof JobStoreError
      && /\.pruning: prune marker could not be inspected \(EACCES/.test(error.message) && GUIDANCE.test(error.message));
  } finally {
    faultFor = new Set();
  }
  assert.ok(faults > 0, "the fault reached the marker inspection");
  assert.equal(readFileSync(recordPath(ws, ID), "utf8"), before, "the canonical is untouched");
  assert.equal((await readRecord(ws, ID)).version, 1, "with the marker inspectable again the job reads as before");
});

test("vibe-302 N22: in a listing, a marker that cannot be inspected is local to its job — neighbours list, a refused canonical keeps its cause", async () => {
  const ws = tmpWorkspace("jobs-marker-fault-n22-");
  const [A, B, C] = ["job_aaaaaaaaaaaaaaaaaaaa", "job_bbbbbbbbbbbbbbbbbbbb", "job_cccccccccccccccccccc"];
  for (const id of [A, B, C]) await createRecord(ws, seedRecord(id));
  // B: a healthy canonical whose marker cannot be inspected. C: the same, with a refused (unstamped) canonical.
  const { "_vibe-suite_owned": _stamp, ...cUnstamped } = JSON.parse(readFileSync(recordPath(ws, C), "utf8"));
  writeFileSync(recordPath(ws, C), JSON.stringify(cUnstamped), "utf8");
  for (const id of [B, C]) writeFileSync(path.join(jobsDir(ws), `${id}.pruning`), "{}", "utf8");
  faults = 0;
  faultFor = new Set([B, C]);
  let listed;
  try {
    listed = await listRecords(ws);
  } finally {
    faultFor = new Set();
  }
  assert.ok(faults > 0, "the fault reached the listing's marker inspections");
  assert.deepEqual(listed.records.map((record) => record.jobId), [A], "the healthy neighbour still lists");
  assert.deepEqual(listed.invalid.map((entry) => entry.jobId).sort(), [B, C], "each affected job is one invalid row");
  const reason = (id) => listed.invalid.find((entry) => entry.jobId === id).reason;
  assert.match(reason(B), /prune marker could not be inspected \(EACCES/);
  assert.match(reason(B), GUIDANCE);
  assert.match(reason(C), /no ownership stamp/, "the canonical's own refusal is what C reports");
});

test("vibe-302 N23: a marker that turns uninspectable inside the self-heal is a FLAGGED refusal — the self-heal cannot swallow it", async () => {
  // The canonical stays stamped, so there is no canonical refusal to prefer: the refusal `commit`
  // raises is the one the helper constructs, and only its flag keeps `readCanonical`'s best-effort
  // self-heal from swallowing it and returning the slot as a healthy record.
  const ws = tmpWorkspace("jobs-marker-fault-n23-");
  await createRecord(ws, seedRecord());
  const canonical = recordPath(ws, ID);
  const slot = path.join(jobsDir(ws), `${ID}.v2.json`);
  writeFileSync(slot, slotBytes({ ...JSON.parse(readFileSync(canonical, "utf8")), version: 2, kind: "later" }), "utf8");
  const before = { canonical: readFileSync(canonical, "utf8"), slot: readFileSync(slot, "utf8") };
  let fired = false;
  faults = 0;
  try {
    await assert.rejects(() => readRecord(ws, ID, {
      onSelfHeal: () => {
        if (fired) return;
        fired = true;
        faultFor = new Set([ID]);
      },
    }), (error) => error instanceof JobStoreError && /prune marker could not be inspected \(EACCES/.test(error.message)
      && error.refusal === true && GUIDANCE.test(error.message));
  } finally {
    faultFor = new Set();
  }
  assert.ok(fired, "the seam fired");
  assert.ok(faults > 0, "the fault reached commit's marker inspection");
  assert.deepEqual({ canonical: readFileSync(canonical, "utf8"), slot: readFileSync(slot, "utf8") }, before,
    "nothing was published and the slot is untouched");
});

test("vibe-302 N24: in a listing, a directory at a canonical path that cannot be inspected is local to its job — neighbours still list", async () => {
  const ws = tmpWorkspace("jobs-marker-fault-n24-");
  const [A, D] = ["job_aaaaaaaaaaaaaaaaaaaa", "job_dddddddddddddddddddd"];
  await createRecord(ws, seedRecord(A));
  mkdirSync(path.join(jobsDir(ws), `${D}.json`));            // a directory where D's canonical would be
  faults = 0;
  faultCanonicalFor = new Set([D]);
  let listed;
  try {
    listed = await listRecords(ws);
  } finally {
    faultCanonicalFor = new Set();
  }
  assert.ok(faults > 0, "the fault reached the listing's canonical-path inspection");
  assert.deepEqual(listed.records.map((record) => record.jobId), [A], "the healthy neighbour still lists");
  assert.deepEqual(listed.invalid.map((entry) => entry.jobId), [D], "the affected job is one invalid row");
  assert.match(listed.invalid[0].reason, /the directory at the canonical path could not be inspected \(EACCES/);
  assert.match(listed.invalid[0].reason, GUIDANCE);
});
