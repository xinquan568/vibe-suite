// SPDX-License-Identifier: ISC
// SessionStart / SessionEnd hygiene (E1.6 / vibe-16). The properties under test are what the hook
// must NOT do as much as what it does: it reports, it never rewrites a record it does not own, and
// it exits 0 even when the store is damaged — a convenience hook that breaks a session is not one.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
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

test("start and end reap orphan temps and report abandoned jobs WITHOUT rewriting them", async () => {
  const ws = mkdtempSync(path.join(tmpdir(), "lifecycle-"));
  await createRecord(ws, abandonedRecord("job_aaaaaaaaaaaaaaaaaaaa"));
  const before = await readRecord(ws, "job_aaaaaaaaaaaaaaaaaaaa");

  const orphan = path.join(jobsDir(ws), "job_bbbbbbbbbbbbbbbbbbbb.tmp.123.deadbeef");
  writeFileSync(orphan, "{}");
  const old = (Date.now() - TEMP_REAP_MIN_AGE_MS - 60_000) / 1000;
  utimesSync(orphan, old, old);

  const start = runHook(ws, "start");
  assert.equal(start.status, 0, start.stderr);
  assert.ok(start.stderr.includes("reaped 1 orphan temp"), start.stderr);
  assert.ok(start.stderr.includes("looks abandoned"), start.stderr);

  const after = await readRecord(ws, "job_aaaaaaaaaaaaaaaaaaaa");
  assert.equal(after.version, before.version, "reporting must not bump the record version");
  assert.equal(after.status, "running", "the hook must never settle a job it does not own");
});

test("end additionally reports still-running jobs; start does not", async () => {
  const ws = mkdtempSync(path.join(tmpdir(), "lifecycle-live-"));
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
  const ws = mkdtempSync(path.join(tmpdir(), "lifecycle-damaged-"));
  mkdirSync(jobsDir(ws), { recursive: true });
  writeFileSync(path.join(jobsDir(ws), "job_dddddddddddddddddddd.json"), "not json at all");
  for (const event of ["start", "end"]) {
    const result = runHook(ws, event);
    assert.equal(result.status, 0, `${event}: ${result.stderr}`);
    assert.ok(result.stderr.includes("unreadable"), result.stderr);
  }
});

test("an empty workspace is silent and successful", () => {
  const ws = mkdtempSync(path.join(tmpdir(), "lifecycle-empty-"));
  const result = runHook(ws, "start");
  assert.equal(result.status, 0);
  assert.equal(result.stderr.trim(), "");
});
