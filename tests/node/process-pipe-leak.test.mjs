// SPDX-License-Identifier: ISC
// runWithDeadline settles on EXIT, not on `close` (vibe-181 / grill H6).
//
// `close` fires only once every stdio pipe is released. A descendant that inherited the child's
// stdout/stderr holds them open after the child is dead, so a promise that waited for `close` never
// settled, the deadline's verdict was never reported, and a heartbeat cleared only at settle beat
// forever — a background job stayed `running` and `isAbandoned` called it healthy. The leaker fixture
// spawns exactly that grandchild; its modes (exit / immune / linger) give a child that exits at
// once, one that ignores SIGTERM, and one that honours it. The child's lifetime ends at `exit`: the
// deadline and the SIGKILL escalation are cancelled there, so neither can stamp `timedOut` or
// `killedHard` on a child that already died during the bounded pipe drain.

import { strict as assert } from "node:assert";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { runWithDeadline } from "../../scripts/lib/process.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const LEAKER = path.join(REPO_ROOT, "tests", "fixtures", "pipe-leaker.mjs");

// Test-owned cleanup WITH survivor verification: no harness reaps a descendant of a settled run, so
// the test that planted the grandchild kills it and proves it gone (ESRCH) before returning.
async function reapGrandchild(stdout) {
  const match = /grandchild=(\d+)/.exec(stdout);
  if (!match) return null;
  const pid = Number(match[1]);
  try { process.kill(pid, "SIGKILL"); } catch { /* already gone */ }
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    try { process.kill(pid, 0); } catch (error) { if (error.code === "ESRCH") return pid; }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  assert.fail(`grandchild ${pid} survived the test's kill`);
}

// Ceilings are chosen to pin the CONFIGURABLE graceMs, not merely "eventually": with graceMs 300 the
// settle lands at ~350 ms, so a ceiling of 1500 ms rejects an implementation that hard-codes the
// 2000 ms default (≈2050 ms) as surely as one that waits for the 6 s grandchild.
const HOLD_MS = "6000";

test("(a) a child whose grandchild holds stdout open still settles within graceMs, reporting pipesLeaked", async () => {
  const started = Date.now();
  const result = await runWithDeadline({
    command: process.execPath, args: [LEAKER, HOLD_MS], timeoutMs: 10_000, graceMs: 300,
  });
  const elapsed = Date.now() - started;
  const pid = await reapGrandchild(result.stdout);
  assert.ok(pid, `the fixture must print its grandchild pid; stdout was ${JSON.stringify(result.stdout)}`);
  assert.equal(result.exitCode, 0, "the child itself exited cleanly");
  assert.equal(result.timedOut, false, "the child exited long before the deadline");
  assert.equal(result.killedHard, false);
  assert.equal(result.pipesLeaked, true, "the grandchild held the pipes past exit; the result must say so");
  assert.ok(result.stdout.includes("leaking"), "output collected before exit is kept");
  assert.ok(elapsed < 1500, `settled in ${elapsed}ms — graceMs was 300; the 2000 ms default or the 6 s grandchild must not set the pace`);
});

test("(b) a child that releases its pipes reports pipesLeaked: false and keeps the old shape", async () => {
  const result = await runWithDeadline({
    command: process.execPath, args: ["-e", "process.stdout.write('clean\\n'); process.exit(0)"], timeoutMs: 5000,
  });
  assert.equal(result.exitCode, 0);
  assert.equal(result.pipesLeaked, false);
  assert.equal(result.groupReaped, null);
  assert.equal(result.stdout, "clean\n");
});

test("(c) the heartbeat stops within graceMs of a natural exit even while a grandchild holds the pipes", async () => {
  let beats = 0;
  const started = Date.now();
  const result = await runWithDeadline({
    command: process.execPath, args: [LEAKER, HOLD_MS], timeoutMs: 10_000, graceMs: 300,
    heartbeatMs: 30, onHeartbeat: () => { beats += 1; },
  });
  const elapsed = Date.now() - started;
  await reapGrandchild(result.stdout);
  const atSettle = beats;
  await new Promise((resolve) => setTimeout(resolve, 200));
  assert.equal(beats, atSettle, "the heartbeat interval outlived the settle");
  assert.ok(elapsed < 1500, `the beats must stop at settle (${elapsed}ms) — within the supplied graceMs, not the 2000 ms default and not the 6 s grandchild`);
});

test("(d) a SIGTERM-immune child with a leaked pipe ends timedOut + killedHard within timeout+grace+drain, and its heartbeat stops at that settle", async () => {
  let beats = 0;
  const started = Date.now();
  const result = await runWithDeadline({
    command: process.execPath, args: [LEAKER, HOLD_MS, "immune"], timeoutMs: 300, graceMs: 200,
    heartbeatMs: 30, onHeartbeat: () => { beats += 1; },
  });
  const elapsed = Date.now() - started;
  await reapGrandchild(result.stdout);
  assert.equal(result.timedOut, true);
  assert.equal(result.killedHard, true, "SIGTERM was ignored; SIGKILL must have followed");
  assert.equal(result.pipesLeaked, true, "the grandchild held the pipes; the verdict must still arrive");
  // SIGTERM at 300 ms, SIGKILL at 500 ms, drain ≤ 200 ms → ≈ 700 ms. A 2000 ms hard-coded drain
  // (≈ 2500 ms) or waiting for the 6 s grandchild both breach this ceiling.
  assert.ok(elapsed < 1500, `settled in ${elapsed}ms — timeout + grace + drain is the bound, not the default drain or the grandchild`);
  const atSettle = beats;
  await new Promise((resolve) => setTimeout(resolve, 200));
  assert.equal(beats, atSettle, "the heartbeat kept beating after the SIGKILL settle");
});

test("(h) a natural exit before a deadline that falls inside the drain is NOT timedOut", async () => {
  // The child exits at once; the grandchild holds the pipes for 4 s; the deadline (400 ms) would fire
  // during the 600 ms drain. The child's lifetime ended at exit, so the deadline must be cancelled
  // there — an implementation that let it fire would report a clean exit as timedOut.
  const started = Date.now();
  const result = await runWithDeadline({
    command: process.execPath, args: [LEAKER, HOLD_MS], timeoutMs: 400, graceMs: 600,
  });
  const elapsed = Date.now() - started;
  await reapGrandchild(result.stdout);
  assert.equal(result.exitCode, 0);
  assert.equal(result.timedOut, false, "the deadline fired during the drain and was wrongly recorded");
  assert.equal(result.killedHard, false);
  assert.equal(result.pipesLeaked, true);
  assert.ok(elapsed < 1500, `settled in ${elapsed}ms — the 600 ms drain after an immediate exit, not the default drain or the grandchild`);
});

test("(i) a TERM-responsive child that times out with a leaked pipe is timedOut but NOT killedHard", async () => {
  // `linger` honours SIGTERM: the deadline (300 ms) kills it at once; the SIGKILL escalation would
  // fire 600 ms later, inside the drain. Exit must cancel that escalation — killedHard claims a
  // delivered SIGKILL, and none was needed.
  const started = Date.now();
  const result = await runWithDeadline({
    command: process.execPath, args: [LEAKER, HOLD_MS, "linger"], timeoutMs: 300, graceMs: 600,
  });
  const elapsed = Date.now() - started;
  await reapGrandchild(result.stdout);
  assert.equal(result.timedOut, true);
  assert.equal(result.signal, "SIGTERM");
  assert.equal(result.killedHard, false, "the escalation fired during the drain and was wrongly recorded");
  assert.equal(result.pipesLeaked, true);
  assert.ok(elapsed < 1500, `settled in ${elapsed}ms — SIGTERM at 300 ms plus the 600 ms drain, not the default drain or the grandchild`);
});
