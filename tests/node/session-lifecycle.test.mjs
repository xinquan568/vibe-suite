// SPDX-License-Identifier: ISC
// SessionStart / SessionEnd hygiene (E1.6 / vibe-16). The properties under test are what the hook
// must NOT do as much as what it does: it reports, it never rewrites a record it does not own, and
// it exits 0 even when the store is damaged — a convenience hook that breaks a session is not one.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";

import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createRecord, jobsDir, newRecord, readRecord, TEMP_REAP_MIN_AGE_MS } from "../../scripts/lib/jobs.mjs";
import { utimesSync } from "node:fs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOK = path.join(REPO_ROOT, "scripts", "session-lifecycle-hook.mjs");

const runHook = (cwd, event) => spawnSync(process.execPath, [HOOK, "--event", event],
  { cwd, encoding: "utf8", timeout: 30_000 });

// vibe-203: SessionStart reports go to stdout (the harness adds it to context); SessionEnd reports
// stay on stderr (SessionEnd stdout is not shown). The report channel therefore depends on the event.
const reportChan = (result, event) => (event === "start" ? result.stdout : result.stderr);

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
    assert.ok(reportChan(result, event).includes("reaped 1 orphan temp"), `${event}: ${reportChan(result, event)}`);
    assert.ok(readdirSync(jobsDir(ws)).includes(path.basename(foreign)),
      `${event}: an unstamped file matching the temp pattern must survive`);
    assert.ok(reportChan(result, event).includes("looks abandoned"), `${event}: ${reportChan(result, event)}`);

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
  const startRes = runHook(ws, "start");
  assert.ok(!startRes.stderr.includes("still running") && !startRes.stdout.includes("still running"));
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
    assert.ok(reportChan(result, event).includes("unreadable"), reportChan(result, event));
  }
});

test("an empty workspace is silent and successful", () => {
  const ws = tmpWorkspace("lifecycle-empty-");
  const result = runHook(ws, "start");
  assert.equal(result.status, 0);
  assert.equal(result.stderr.trim(), "");
  assert.equal(result.stdout.trim(), "", "an empty workspace is silent on the SessionStart stdout channel too");
});

// vibe-201 (M29): an unknown --event is a usage error, not a silent "start".

test("an unknown --event is a usage error (exit 2), not a silent 'start'", () => {
  const r = spawnSync(process.execPath, [HOOK, "--event", "bogus"], { encoding: "utf8" });
  assert.equal(r.status, 2, `unknown --event must exit 2 (usage error), got ${r.status}: ${r.stderr}`);
  assert.match(r.stderr, /--event/, `stderr must name the --event usage error: ${r.stderr}`);
});

test("a MISSING --event is likewise a usage error (exit 2)", () => {
  const r = spawnSync(process.execPath, [HOOK], { encoding: "utf8" });
  assert.equal(r.status, 2, `a missing --event must exit 2, got ${r.status}: ${r.stderr}`);
});

// --- vibe-207: the two-phase emitter tests --------------------------------------------------------

function eventsOf207(ws) {
  const p = path.join(ws, ".vibe-suite-state", "events.log");
  // `existsSync` is true for a DIRECTORY, and a directory at this path is exactly the phase-B
  // fixture — so asking "does it exist?" reads it and throws EISDIR. Ask whether it is a file.
  if (!existsSync(p) || !statSync(p).isFile()) return [];
  return readFileSync(p, "utf8").split("\n").filter(Boolean).flatMap((line) => {
    try { return [JSON.parse(line)]; } catch { return []; }
  });
}

function seedReportable(ws) {
  mkdirSync(jobsDir(ws), { recursive: true });
  // The suite's own reliable report fixture: a STAMPED orphan temp, aged past the reap floor.
  // An unstamped one is left alone by design, so only the stamp produces the "reaped 1" line.
  const orphan = path.join(jobsDir(ws), "job_cccccccccccccccccccc.tmp.207.feedface");
  writeFileSync(orphan, JSON.stringify({ "_vibe-suite_owned": { kind: "job-scratch", schema: 1 } }));
  const aged = (Date.now() - TEMP_REAP_MIN_AGE_MS - 60_000) / 1000;
  utimesSync(orphan, aged, aged);
  return ws;
}

test("phase A: a lifecycle report is also recorded durably (vibe-207)", () => {
  const ws = seedReportable(tmpWorkspace("lifecycle-207-"));

  const result = runHook(ws, "start");
  assert.match(result.stdout, /reaped 1 orphan temp/,
    "the fixture must actually produce a report — an emitter test whose fixture triggers nothing proves nothing");
  assert.equal(result.status, 0, "a lifecycle hook never fails the session");
  const reports = eventsOf207(ws).filter((e) => e.event === "hook.report");
  assert.ok(reports.length >= 1, "the text the operator sees is kept where it can be read tomorrow");
  assert.equal(reports[0].component, "hook");
  assert.equal(reports[0].detail.event, "start");
});

test("phase B: the lifecycle hook is unchanged when the event log cannot be written (vibe-207)", () => {
  const expected = runHook(seedReportable(tmpWorkspace("lifecycle-207-clean-")), "start");

  const blocked = seedReportable(tmpWorkspace("lifecycle-207-blocked-"));
  mkdirSync(path.join(blocked, ".vibe-suite-state", "events.log"), { recursive: true });
  const actual = runHook(blocked, "start");

  assert.equal(actual.status, expected.status);
  assert.equal(actual.stdout, expected.stdout,
    "byte-identical — a hook that reported differently because its log was blocked would have failed property 1");
  assert.equal(actual.stderr, expected.stderr, "and stderr, which is where SessionEnd reports go");
});
