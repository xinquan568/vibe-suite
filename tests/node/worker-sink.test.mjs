// SPDX-License-Identifier: ISC
// The background worker's stderr sink (vibe-182 / grill H7): `withWorkerSink` owns the whole
// lifecycle — open through the audited primitive, hand the descriptor to the spawn, close the
// launcher's copy, and degrade (said out loud) when the sink cannot be opened. Tested directly,
// because the runner cannot be imported (it runs `main()` on load) and a descriptor's lifetime is
// not visible from outside the process that holds it.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { fstatSync, lstatSync, readFileSync, statSync, symlinkSync } from "node:fs";

import path from "node:path";
import test from "node:test";

import {
  createRecord, jobsDir, newRecord, withWorkerSink, workerLogPath,
} from "../../scripts/lib/jobs.mjs";

const ID = "job_aaaaaaaaaaaaaaaaaaaa";

async function workspaceWithRecord() {
  const ws = tmpWorkspace("worker-sink-");
  await createRecord(ws, newRecord({
    jobId: ID, kind: "review", sandbox: "read-only", effort: "low",
    model: null, background: true, timeoutMs: 1000, claimDigest: null,
  }));
  return ws;
}

/** True while `fd` still refers to the file at `p` — false once closed (or reused for another file). */
function fdStillOpenOn(fd, p) {
  try { return fstatSync(fd).ino === statSync(p).ino; } catch { return false; }
}

test("withWorkerSink hands the spawn a live 0600 sink descriptor, then closes the launcher's copy", async () => {
  const ws = await workspaceWithRecord();
  let seenFd = null;
  let writtenInside = null;
  const { child, logPath, warning } = await withWorkerSink(ws, ID, (stderr) => {
    seenFd = stderr;
    assert.equal(typeof stderr, "number", "the spawn receives a descriptor, not 'ignore'");
    // Inside the spawn callback the descriptor is live: a child whose stderr IS that slot writes
    // straight into the log — exactly what the real worker spawn does.
    writtenInside = spawnSync(process.execPath, ["-e", "process.stderr.write('from the worker\\n')"],
      { stdio: ["ignore", "ignore", stderr] });
    return { pid: writtenInside.pid };
  });
  assert.equal(warning, null);
  assert.equal(logPath, workerLogPath(ws, ID));
  assert.equal(child.pid, writtenInside.pid, "the callback's child is what the helper returns");
  assert.equal(statSync(logPath).mode & 0o777, 0o600, "the sink is private");
  assert.equal(readFileSync(logPath, "utf8"), "from the worker\n");
  assert.equal(fdStillOpenOn(seenFd, logPath), false,
    "the launcher's descriptor is closed once the spawn has its own copy — nothing holds the log open");
});

test("withWorkerSink degrades to 'ignore' with a warning when the sink cannot be opened, and creates nothing", async () => {
  const ws = await workspaceWithRecord();
  const logPath = workerLogPath(ws, ID);
  symlinkSync(path.join(jobsDir(ws), "elsewhere.log"), logPath);      // a symlink squats on the path
  let seen = null;
  const out = await withWorkerSink(ws, ID, (stderr) => { seen = stderr; return { pid: 1 }; });
  assert.equal(seen, "ignore", "the worker is still spawned — with its stderr discarded, as before vibe-182");
  assert.equal(out.logPath, null);
  assert.match(out.warning, /worker log unavailable for job_aaaaaaaaaaaaaaaaaaaa/);
  assert.match(out.warning, /symlink/, "the reason travels in the warning");
  assert.match(out.warning, /stderr is discarded/);
  assert.ok(lstatSync(logPath).isSymbolicLink(), "the squatting symlink is untouched — never followed, never replaced");
});

test("withWorkerSink closes its descriptor even when the spawn throws, and the error propagates", async () => {
  const ws = await workspaceWithRecord();
  let seenFd = null;
  await assert.rejects(
    withWorkerSink(ws, ID, (stderr) => { seenFd = stderr; throw new Error("spawn failed (test)"); }),
    /spawn failed \(test\)/);
  assert.equal(typeof seenFd, "number");
  assert.equal(fdStillOpenOn(seenFd, workerLogPath(ws, ID)), false, "no leaked descriptor on the failure path");
});
