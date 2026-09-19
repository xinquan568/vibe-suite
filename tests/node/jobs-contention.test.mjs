// SPDX-License-Identifier: ISC
// The job store under real contention and a real crash (vibe-225 / grill M26).
//
// `jobs-store.test.mjs` stages its races by hand: it writes the slot a dead writer would have left, or
// plants an entry through a seam. These tests make the races happen. In one process, 32 `transact`
// calls are in flight at once. Across processes, four writers contend for one record, and one of them
// holds its won, unconfirmed slot while the other three must build on it — so the cross-process path
// is exercised by construction, not by luck. And a writer is killed for real (`SIGKILL`, through the
// store's `VIBE_TEST_FAIL_AFTER=link` seam) right after its link, leaving exactly what a crash leaves.
//
// Nothing here sleeps. Children wait on a pipe read for the parent's word, and the parent waits on
// their output and their exit.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawn } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  createRecord, finaliseRecord, jobsDir, newRecord, readRecord, reapOrphanTemps, recordPath, transact,
  updateRecord, TEMP_REAP_MIN_AGE_MS,
} from "../../scripts/lib/jobs.mjs";

const JOBS_URL = pathToFileURL(
  path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "scripts", "lib", "jobs.mjs")).href;
const ID = "job_c0c0c0c0c0c0c0c0c0c0";
const bump = (record) => ({ ...record, contended: (record.contended ?? 0) + 1 });

function workspace() {
  return tmpWorkspace("jobs-contention-");
}

function seedRecord(jobId = ID) {
  return newRecord({
    jobId, kind: "review", sandbox: "read-only", effort: "low",
    model: null, background: false, timeoutMs: 1000, claimDigest: null,
  });
}

const scratches = (ws) => readdirSync(jobsDir(ws)).filter((name) => name.endsWith(".vibe-tmp"));
const canonicals = (ws) => readdirSync(jobsDir(ws)).filter((name) => /^job_[0-9a-f]{20}\.json$/.test(name));

// The children's prelude: the store, a line reader on stdin (the barrier), and the increment.
const PRELUDE = `
const J = await import(process.env.JOBS_URL);
let buffered = ""; const pending = []; const waiters = [];
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  buffered += chunk;
  let at;
  while ((at = buffered.indexOf("\\n")) >= 0) {
    const line = buffered.slice(0, at); buffered = buffered.slice(at + 1);
    const waiter = waiters.shift(); if (waiter) waiter(line); else pending.push(line);
  }
});
const next = () => (pending.length ? Promise.resolve(pending.shift()) : new Promise((r) => waiters.push(r)));
const bump = (record) => ({ ...record, contended: (record.contended ?? 0) + 1 });
const done = () => { process.stdin.destroy(); };
`;

// Every child is killed when the file's tests end, pass or fail: a child left waiting on its pipe for a word the
// parent never sent (because an assertion failed first) would otherwise keep the test process alive forever.
const live = new Set();
test.afterEach(() => {
  for (const proc of live) proc.kill("SIGKILL");
  live.clear();
});

/** Spawn a child running `body` after the prelude. Collects stdout lines; resolves `exit` with code and signal. */
function child(body, env) {
  const full = { ...process.env, JOBS_URL, ...env };
  if (!("VIBE_TEST_FAIL_AFTER" in env)) delete full.VIBE_TEST_FAIL_AFTER;
  const proc = spawn(process.execPath, ["--input-type=module", "-e", PRELUDE + body],
    { env: full, stdio: ["pipe", "pipe", "pipe"] });
  live.add(proc);
  proc.on("exit", () => live.delete(proc));
  const lines = [];
  const waiters = [];
  let buffered = "";
  let stderr = "";
  proc.stdout.setEncoding("utf8");
  proc.stdout.on("data", (chunk) => {
    buffered += chunk;
    let at;
    while ((at = buffered.indexOf("\n")) >= 0) {
      lines.push(buffered.slice(0, at));
      buffered = buffered.slice(at + 1);
      for (const waiter of waiters.splice(0)) waiter();
    }
  });
  proc.stderr.on("data", (chunk) => { stderr += chunk; });
  const exit = new Promise((resolve) => {
    proc.on("exit", (code, signal) => {
      for (const waiter of waiters.splice(0)) waiter();
      resolve({ code, signal, stderr });
    });
  });
  /** Resolve with the first line matching `predicate`, or reject if the child exits first. */
  async function line(predicate) {
    for (;;) {
      const found = lines.find(predicate);
      if (found !== undefined) return found;
      if (proc.exitCode !== null || proc.signalCode !== null) {
        throw new Error(`child exited before the expected line; stderr: ${stderr}`);
      }
      await new Promise((resolve) => waiters.push(resolve));
    }
  }
  return { proc, lines, exit, line, say: (word) => proc.stdin.write(`${word}\n`) };
}

// Sizes are the acceptance budget's, not the issue's example: 32 in-process contenders cost 330 attempts (quadratic —
// every round has one winner) and ~5 s on a loaded host; 16 still run ~90 contended attempts. Across processes the race
// is constructed (the held win), so four increments per writer prove what thirty-two would.
const IN_PROCESS = 16;
const PER_PROCESS = 4;

test("concurrent transacts in one process commit exactly one version each", async () => {
  const ws = workspace();
  await createRecord(ws, seedRecord());
  const results = await Promise.all(Array.from({ length: IN_PROCESS }, () => transact(ws, ID, bump)));
  assert.ok(results.every((record) => record && typeof record.version === "number"), "every call resolved to a record");
  assert.deepEqual(results.map((record) => record.version).sort((a, b) => a - b),
    Array.from({ length: IN_PROCESS }, (_, i) => i + 2), "each call committed its own version");
  const final = await readRecord(ws, ID);
  assert.equal(final.version, IN_PROCESS + 1);
  assert.equal(final.contended, IN_PROCESS);
  assert.deepEqual(canonicals(ws), [`${ID}.json`], "one canonical");
  assert.ok(readdirSync(jobsDir(ws)).includes(`${ID}.v${IN_PROCESS + 1}.json`), "the top slot is retained");
  assert.deepEqual(scratches(ws), [], "an uncrashed run leaves no scratch");
});

test("four processes contending for one record lose no increment", { timeout: 60_000 }, async () => {
  const ws = workspace();
  await createRecord(ws, seedRecord());
  const body = `
    process.stdout.write("ready\\n");
    await next();
    const versions = [];
    let held = false;
    for (let i = 0; i < Number(process.env.PER_PROCESS); i += 1) {
      // Hold the FIRST win only: a store that re-applied a confirmed write would win again, and a second hold
      // would wait for a word the parent never sends — the defect must show as a wrong count, not a hang.
      const options = process.env.HOLDER === "1" && i === 0
        ? { onWon: async () => { if (held) return; held = true; process.stdout.write("won\\n"); await next(); } }
        : {};
      versions.push((await J.transact(process.env.WS, process.env.ID, bump, options)).version);
    }
    process.stdout.write(JSON.stringify({ versions }) + "\\n");
    done();
  `;
  const holder = child(body, { WS: ws, ID, HOLDER: "1", PER_PROCESS: String(PER_PROCESS) });
  const others = [0, 1, 2].map(() => child(body, { WS: ws, ID, HOLDER: "0", PER_PROCESS: String(PER_PROCESS) }));
  for (const c of [holder, ...others]) await c.line((l) => l === "ready");
  holder.say("go");
  await holder.line((l) => l === "won");            // v2 linked, not confirmed — and it stays that way
  for (const c of others) c.say("go");
  const exits = await Promise.all(others.map((c) => c.exit));
  // The three finished all their increments while the holder still held: they could only do so by
  // completing the holder's slot across processes.
  for (const result of exits) assert.equal(result.code, 0, result.stderr);
  holder.say("resume");
  const held = await holder.exit;
  assert.equal(held.code, 0, held.stderr);
  const report = (c) => JSON.parse(c.lines.find((l) => l.startsWith("{"))).versions;
  assert.equal(report(holder)[0], 2, "the held win landed at v2 and was confirmed, not re-applied");
  for (const c of others) assert.ok(report(c).every((v) => v >= 3), "the others built on the held v2");
  const final = await readRecord(ws, ID);
  assert.equal(final.version, 4 * PER_PROCESS + 1);
  assert.equal(final.contended, 4 * PER_PROCESS, "every increment across four processes, none lost, none doubled");
  assert.deepEqual(canonicals(ws), [`${ID}.json`]);
  assert.deepEqual(scratches(ws), []);
});

test("a writer killed after its link is rolled forward by the next writer", { timeout: 30_000 }, async () => {
  const ws = workspace();
  await createRecord(ws, seedRecord());
  const crashed = child(`
    await J.transact(process.env.WS, process.env.ID, (r) => ({ ...r, contended: 1, kind: "crashed" }));
    process.stdout.write("survived\\n");
    done();
  `, { WS: ws, ID, VIBE_TEST_FAIL_AFTER: "link" });
  crashed.proc.stdin.end();
  const result = await crashed.exit;
  assert.equal(result.signal, "SIGKILL", `the seam must kill the writer after its link; stderr: ${result.stderr}`);
  assert.ok(!crashed.lines.includes("survived"));
  const slot = JSON.parse(readFileSync(path.join(jobsDir(ws), `${ID}.v2.json`), "utf8"));
  assert.equal(slot.kind, "crashed", "the dead writer's slot is published");
  assert.equal(JSON.parse(readFileSync(recordPath(ws, ID), "utf8")).version, 1, "and not committed");
  assert.equal(scratches(ws).length, 1, "the crash stranded its scratch");
  await transact(ws, ID, bump);
  const final = await readRecord(ws, ID);
  assert.equal(final.version, 3);
  assert.equal(final.kind, "crashed", "the dead writer's change was rolled forward");
  assert.equal(final.contended, 2, "and the next writer's change landed on top of it");
  assert.equal(await reapOrphanTemps(ws, { now: Date.now() + TEMP_REAP_MIN_AGE_MS + 1000 }), 1);
  assert.deepEqual(scratches(ws), []);
});

test("a creation killed after its link leaves a readable record and one orphan scratch", { timeout: 30_000 }, async () => {
  const ws = workspace();
  const crashed = child(`
    await J.createRecord(process.env.WS, J.newRecord({ jobId: process.env.ID, kind: "review", sandbox: "read-only",
      effort: "low", model: null, background: false, timeoutMs: 1000, claimDigest: null }));
    process.stdout.write("survived\\n");
    done();
  `, { WS: ws, ID, VIBE_TEST_FAIL_AFTER: "link" });
  crashed.proc.stdin.end();
  const result = await crashed.exit;
  assert.equal(result.signal, "SIGKILL", result.stderr);
  const record = await readRecord(ws, ID);
  assert.equal(record.jobId, ID, "the canonical was published whole by the link");
  assert.equal(scratches(ws).length, 1);
  assert.equal(await reapOrphanTemps(ws, { now: Date.now() + TEMP_REAP_MIN_AGE_MS + 1000 }), 1);
  assert.deepEqual(scratches(ws), []);
});

test("the seam is inert unless its value is exactly \"link\"", { timeout: 30_000 }, async () => {
  const ws = workspace();
  await createRecord(ws, seedRecord());
  const body = `
    await J.transact(process.env.WS, process.env.ID, bump);
    process.stdout.write("survived\\n");
    done();
  `;
  for (const env of [{}, { VIBE_TEST_FAIL_AFTER: "Link" }, { VIBE_TEST_FAIL_AFTER: "" }]) {
    const run = child(body, { WS: ws, ID, ...env });
    run.proc.stdin.end();
    const result = await run.exit;
    assert.deepEqual([result.code, result.signal], [0, null], `inert for ${JSON.stringify(env)}: ${result.stderr}`);
    assert.ok(run.lines.includes("survived"));
  }
  assert.equal((await readRecord(ws, ID)).contended, 3);
  assert.deepEqual(scratches(ws), []);
});

test("prune and entomb never reach the seam", { timeout: 30_000 }, async () => {
  const ws = workspace();
  await createRecord(ws, seedRecord());
  await updateRecord(ws, ID, { kind: "beat" });
  await finaliseRecord(ws, ID, { status: "completed" });
  const run = child(`
    const report = await J.pruneTerminalJobs(process.env.WS, { olderThanMs: 0 });
    process.stdout.write(JSON.stringify(report.pruned.map((entry) => entry.jobId)) + "\\n");
    done();
  `, { WS: ws, ID, VIBE_TEST_FAIL_AFTER: "link" });
  run.proc.stdin.end();
  const result = await run.exit;
  assert.deepEqual([result.code, result.signal], [0, null], result.stderr);
  assert.deepEqual(JSON.parse(run.lines[0]), [ID], "the job was pruned with the variable set");
  await assert.rejects(() => readRecord(ws, ID), /no record/);
});
