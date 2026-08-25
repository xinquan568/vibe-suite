// SPDX-License-Identifier: ISC
// SessionStart / SessionEnd hygiene (E1.6 / vibe-16). The properties under test are what the hook
// must NOT do as much as what it does: it reports, it never rewrites a record it does not own, and
// it exits 0 even when the store is damaged — a convenience hook that breaks a session is not one.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { mkdirSync, readdirSync, writeFileSync } from "node:fs";

import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createRecord, jobsDir, newRecord, readRecord, TEMP_REAP_MIN_AGE_MS } from "../../scripts/lib/jobs.mjs";
import { utimesSync } from "node:fs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOK = path.join(REPO_ROOT, "scripts", "session-lifecycle-hook.mjs");

const runHook = (cwd, event) => spawnSync(process.execPath, [HOOK, "--event", event],
  { cwd, encoding: "utf8", timeout: 30_000 });

function abandonedRecord(jobId) {
  const stale = new Date(Date.now() - 10 * 60 * 1000).toISOString();
  return {
    ...newRecord({ jobId, kind: "review", sandbox: "read-only", effort: "low", model: null,
      background: true, timeoutMs: 1000, claimDigest: null }),
    workerPid: 999_999, pgid: 999_999, startedAt: stale, heartbeatAt: stale,
  };
}

test("BOTH events reap orphan temps and report abandoned jobs WITHOUT rewriting them", async () => {
  // Run the identical assertions for start and end: the frozen plan promises both directions, and
  // a shared implementation is exactly the kind of thing that grows an event-specific branch later.
  for (const event of ["start", "end"]) {
    const ws = tmpWorkspace(`lifecycle-${event}-`);
    await createRecord(ws, abandonedRecord("job_aaaaaaaaaaaaaaaaaaaa"));
    const before = await readRecord(ws, "job_aaaaaaaaaaaaaaaaaaaa");

    // vibe-103: an orphan is collectible only if it carries the ownership stamp this suite writes.
    // The fixture used to be a bare "{}", which the reaper deleted on the strength of its name —
    // the defect, not the feature. A same-named unstamped file is added to prove it now survives.
    const orphan = path.join(jobsDir(ws), "job_bbbbbbbbbbbbbbbbbbbb.tmp.123.deadbeef");
    writeFileSync(orphan, JSON.stringify({ "_vibe-suite_owned": { kind: "job-scratch", schema: 1 } }));
    const foreign = path.join(jobsDir(ws), "job_dddddddddddddddddddd.tmp.123.cafebabe");
    writeFileSync(foreign, "{}");
    const old = (Date.now() - TEMP_REAP_MIN_AGE_MS - 60_000) / 1000;
    utimesSync(orphan, old, old);
    utimesSync(foreign, old, old);

    const result = runHook(ws, event);
    assert.equal(result.status, 0, `${event}: ${result.stderr}`);
    assert.ok(result.stderr.includes("reaped 1 orphan temp"), `${event}: ${result.stderr}`);
    assert.ok(readdirSync(jobsDir(ws)).includes(path.basename(foreign)),
      `${event}: an unstamped file matching the temp pattern must survive`);
    assert.ok(result.stderr.includes("looks abandoned"), `${event}: ${result.stderr}`);

    const after = await readRecord(ws, "job_aaaaaaaaaaaaaaaaaaaa");
    assert.equal(after.version, before.version, `${event}: reporting must not bump the version`);
    assert.equal(after.status, "running", `${event}: never settle a job the hook does not own`);
  }
});

test("end additionally reports still-running jobs; start does not", async () => {
  const ws = tmpWorkspace("lifecycle-live-");
  await createRecord(ws, {
    ...newRecord({ jobId: "job_cccccccccccccccccccc", kind: "delegate", sandbox: "read-only",
      effort: "low", model: null, background: true, timeoutMs: 1000, claimDigest: null }),
    workerPid: process.pid, pgid: process.pid,
    startedAt: new Date().toISOString(), heartbeatAt: new Date().toISOString(),
  });
  assert.ok(!runHook(ws, "start").stderr.includes("still running"));
  const end = runHook(ws, "end");
  assert.equal(end.status, 0);
  assert.ok(end.stderr.includes("still running"), end.stderr);
});

test("a damaged JOB RECORD is reported, and both events still exit 0", () => {
  const ws = tmpWorkspace("lifecycle-damaged-");
  mkdirSync(jobsDir(ws), { recursive: true });
  writeFileSync(path.join(jobsDir(ws), "job_dddddddddddddddddddd.json"), "not json at all");
  for (const event of ["start", "end"]) {
    const result = runHook(ws, event);
    assert.equal(result.status, 0, `${event}: ${result.stderr}`);
    assert.ok(result.stderr.includes("unreadable"), result.stderr);
  }
});

test("an empty workspace is silent and successful", () => {
  const ws = tmpWorkspace("lifecycle-empty-");
  const result = runHook(ws, "start");
  assert.equal(result.status, 0);
  assert.equal(result.stderr.trim(), "");
});
