// SPDX-License-Identifier: ISC
// End-to-end subprocess tests for the /vibe-suite:jobs CLI (E1.2 / vibe-12).
//
// These are the "live jobs" of the acceptance bullet, made hermetic: real `codex-runner.mjs
// --background` launches against the fake-codex fixtures (never the real CLI), a real detached
// process group for cancel, real signals. Everything runs with cwd = a temp workspace and absolute
// script paths (round-1 plan review, finding 3): the CLI must work when invoked from outside the
// repo, because an installed plugin is not the user's cwd.

import { strict as assert } from "node:assert";
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createRecord, newRecord, readRecord } from "../../scripts/lib/jobs.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CLI = path.join(REPO_ROOT, "scripts", "jobs-cli.mjs");
const RUNNER = path.join(REPO_ROOT, "scripts", "codex-runner.mjs");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex");

function workspace() {
  return mkdtempSync(path.join(tmpdir(), "jobs-cli-"));
}

function cli(ws, ...args) {
  return spawnSync("node", [CLI, ...args], { cwd: ws, encoding: "utf8", timeout: 30_000 });
}

function launch(ws, fixture, ...extra) {
  const result = spawnSync("node", [RUNNER,
    "--kind", "review", "--effort", "low", "--sandbox", "read-only",
    "--timeout-ms", "120000", "--background", ...extra, "--", "fixture prompt",
  ], {
    cwd: ws, encoding: "utf8", timeout: 30_000,
    env: { ...process.env, VIBE_SUITE_CODEX_BIN: path.join(FIXTURES, fixture) },
  });
  assert.equal(result.status, 0, `runner failed: ${result.stdout}\n${result.stderr}`);
  const receipt = JSON.parse(result.stdout.trim().split("\n").at(-1));
  assert.equal(receipt.status, "running", "launch receipt contract");
  return receipt.jobId;
}

async function waitFor(ws, jobId, predicate, what, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const record = await readRecord(ws, jobId).catch(() => null);
    if (record && predicate(record)) return record;
    if (Date.now() > deadline) {
      throw new Error(`job ${jobId} never reached: ${what} (last: ${JSON.stringify(record)})`);
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

const TERMINAL = new Set(["completed", "failed", "timed_out", "cancelled"]);

test("completion path: a live background job completes; status and result exercise the contract", async () => {
  const ws = workspace();
  const jobId = launch(ws, "emitter.mjs");
  await waitFor(ws, jobId, (r) => TERMINAL.has(r.status), "a terminal status");

  const all = cli(ws, "status", "--all");
  assert.equal(all.status, 0, all.stderr);
  assert.ok(all.stdout.includes(jobId) && all.stdout.includes("completed"), all.stdout);

  // Default status hides terminal jobs — the completed job must NOT appear without --all.
  const active = cli(ws, "status");
  assert.equal(active.status, 0, active.stderr);
  assert.ok(!active.stdout.includes(jobId), active.stdout);

  const result = cli(ws, "result", jobId);
  assert.equal(result.status, 0, result.stderr);
  const line = result.stdout.trim();
  assert.equal(line.split("\n").length, 1, "result is one line of JSON");
  const parsed = JSON.parse(line);
  assert.deepEqual(Object.keys(parsed), ["jobId", "status", "threadId", "rawOutput"],
    "exactly the four contract keys, in contract order");
  assert.equal(parsed.jobId, jobId);
  assert.equal(parsed.status, "completed");

  const json = cli(ws, "status", "--all", "--json");
  assert.equal(json.status, 0, json.stderr);
  const payload = JSON.parse(json.stdout);
  assert.equal(payload.records.length, 1);
  assert.equal(payload.records[0].jobId, jobId);
});

test("result on a running job explains itself and exits 1", async () => {
  const ws = workspace();
  const jobId = launch(ws, "sleeper.mjs");
  const claimed = await waitFor(ws, jobId, (r) => r.pgid !== null, "a claimed pgid");

  try {
    const result = cli(ws, "result", jobId);
    assert.equal(result.status, 1, `stdout: ${result.stdout}\nstderr: ${result.stderr}`);
    assert.ok((result.stdout + result.stderr).includes("running"));
  } finally {
    try { process.kill(-claimed.pgid, "SIGKILL"); } catch { /* already gone */ }
  }
});

test("cancel path: a SIGTERM-immune live group is escalated, confirmed dead, and recorded cancelled", async () => {
  const ws = workspace();
  const jobId = launch(ws, "sleeper.mjs");
  const claimed = await waitFor(ws, jobId, (r) => r.pgid !== null, "a claimed pgid");

  const cancel = cli(ws, "cancel", jobId);
  assert.equal(cancel.status, 0, `stdout: ${cancel.stdout}\nstderr: ${cancel.stderr}`);
  assert.ok(cancel.stdout.toLowerCase().includes("confirmed dead"), cancel.stdout);

  const record = await readRecord(ws, jobId);
  assert.equal(record.status, "cancelled");

  // The whole group — worker AND the SIGTERM-immune fixture it spawned — must be gone.
  assert.throws(() => process.kill(-claimed.pgid, 0), { code: "ESRCH" },
    "the process group must be dead, not merely the record terminal");
});

test("cancel on an already-terminal job reports the stored verdict and exits 0", async () => {
  const ws = workspace();
  const jobId = launch(ws, "emitter.mjs");
  await waitFor(ws, jobId, (r) => TERMINAL.has(r.status), "a terminal status");

  const cancel = cli(ws, "cancel", jobId);
  assert.equal(cancel.status, 0, cancel.stderr);
  assert.ok(cancel.stdout.includes("already finished"), cancel.stdout);
  assert.ok(cancel.stdout.includes("completed"), cancel.stdout);
});

test("bare cancel with nothing running exits 1 with a clear message", () => {
  const ws = workspace();
  const cancel = cli(ws, "cancel");
  assert.equal(cancel.status, 1, cancel.stdout + cancel.stderr);
  assert.ok((cancel.stdout + cancel.stderr).includes("nothing to cancel"));
});

test("usage errors exit 2", () => {
  const ws = workspace();
  const bad = cli(ws, "result");                       // result requires an id
  assert.equal(bad.status, 2, bad.stdout + bad.stderr);
  const worse = cli(ws, "obliterate", "everything");   // unknown subcommand
  assert.equal(worse.status, 2, worse.stdout + worse.stderr);
});

test("status --settle-abandoned finalises a dead-worker record to failed; plain status only reports", async () => {
  const ws = workspace();
  // A worker that died without finalising: stale heartbeat, dead pid. The pid comes from a child we
  // spawned and reaped ourselves, so it is guaranteed dead (modulo pid reuse, accepted in a test).
  const child = spawn("node", ["-e", "process.exit(0)"]);
  const deadPid = child.pid;
  await new Promise((resolve) => child.on("exit", resolve));

  const stale = new Date(Date.now() - 10 * 60 * 1000).toISOString();
  await createRecord(ws, {
    ...newRecord({
      jobId: "job_abababababababababab", kind: "review", sandbox: "read-only", effort: "low",
      model: null, background: true, timeoutMs: 1000, claimDigest: null,
    }),
    workerPid: deadPid, pgid: deadPid, startedAt: stale, heartbeatAt: stale,
  });

  const report = cli(ws, "status");
  assert.equal(report.status, 0, report.stderr);
  assert.ok(report.stdout.includes("abandoned (stale heartbeat)"), report.stdout);
  assert.equal((await readRecord(ws, "job_abababababababababab")).status, "running",
    "plain status must never mutate");

  const settle = cli(ws, "status", "--settle-abandoned");
  assert.equal(settle.status, 0, settle.stderr);
  const settled = await readRecord(ws, "job_abababababababababab");
  assert.equal(settled.status, "failed");
  assert.ok(settled.error.includes("abandoned"));
});
