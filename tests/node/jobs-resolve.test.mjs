// SPDX-License-Identifier: ISC
// Resolver semantics and the cancel lifecycle for /vibe-suite:jobs (E1.2 / vibe-12).
//
// The cancel tests are the heart of this issue's review history. Round 1 planned SIGTERM-and-hope;
// round 3's frozen analysis settled on: **the store CAS is the interlock** — cancel claims the
// terminal verdict via `transact` BEFORE any signal, competing completion races the same CAS, a
// rejected claim reports the stored verdict and sends NO signal. `signalGroup` is injected as an
// ordinary dependency (round-3 plan review, finding 1: module mocking is unavailable at the Node 18
// floor), so these tests pass a recording stub and never touch a real process.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { existsSync } from "node:fs";

import path from "node:path";
import test from "node:test";

import {
  createRecord, finaliseRecord, newRecord, readRecord, transact, updateRecord, STATE_DIRNAME,
} from "../../scripts/lib/jobs.mjs";
import {
  cancelJob, parseOlderThan, resolveCancelableJob, resolveResultJob, resolveStatusJobs,
  OLDER_THAN_DEFAULT, ResolveError,
} from "../../scripts/lib/resolve.mjs";

function workspace() {
  return tmpWorkspace("jobs-resolve-");
}

function record(jobId, overrides = {}) {
  return {
    ...newRecord({
      jobId, kind: "review", sandbox: "read-only", effort: "low",
      model: null, background: false, timeoutMs: 1000, claimDigest: null,
    }),
    ...overrides,
  };
}

/** A signalGroup stub: scripted liveness answers, full call recording. */
function stubSignal(aliveAnswers) {
  const calls = [];
  const answers = [...aliveAnswers];
  const fn = (pid, signal) => {
    calls.push([pid, signal]);
    if (signal === 0) return answers.length > 0 ? answers.shift() : false;
    return true;
  };
  return { fn, calls };
}

const instantSleep = () => Promise.resolve();

const ID_A = "job_aaaaaaaaaaaaaaaaaaaa";
const ID_B = "job_bbbbbbbbbbbbbbbbbbbb";

const BG = { background: true, workerPid: 424242, pgid: 424242, startedAt: new Date().toISOString() };

test("an invalid job id is rejected before any filesystem access", async () => {
  const ws = workspace();
  const { fn, calls } = stubSignal([]);
  await assert.rejects(
    () => cancelJob(ws, "../../../etc/passwd", { signalGroup: fn, sleep: instantSleep }),
    (error) => error instanceof ResolveError && error.code === "usage",
  );
  assert.deepEqual(calls, [], "a rejected id must never reach signalGroup");
  assert.equal(existsSync(path.join(ws, STATE_DIRNAME)), false,
    "id validation must precede filesystem access — no state dir may appear");
});

test("resolveResultJob requires an id; resolveStatusJobs filters terminal by default", async () => {
  const ws = workspace();
  await createRecord(ws, record(ID_A, { status: "completed", endedAt: new Date().toISOString() }));
  await createRecord(ws, record(ID_B, BG));

  await assert.rejects(() => resolveResultJob(ws, null),
    (error) => error instanceof ResolveError && error.code === "usage");

  const active = await resolveStatusJobs(ws, {});
  assert.deepEqual(active.records.map((r) => r.jobId), [ID_B]);
  const all = await resolveStatusJobs(ws, { all: true });
  assert.deepEqual(all.records.map((r) => r.jobId).sort(), [ID_A, ID_B]);
  const one = await resolveStatusJobs(ws, { jobId: ID_A });
  assert.equal(one.records[0].status, "completed");
});

test("bare cancel: zero candidates errors, one resolves, several demand an explicit id", async () => {
  const empty = workspace();
  await assert.rejects(() => resolveCancelableJob(empty, null),
    (error) => error instanceof ResolveError && error.code === "none");

  const single = workspace();
  await createRecord(single, record(ID_A, BG));
  await createRecord(single, record(ID_B, { status: "completed" }));  // terminal: not a candidate
  const resolved = await resolveCancelableJob(single, null);
  assert.equal(resolved.jobId, ID_A);

  const crowded = workspace();
  await createRecord(crowded, record(ID_A, BG));
  await createRecord(crowded, record(ID_B, { ...BG, workerPid: 424243, pgid: 424243 }));
  await assert.rejects(() => resolveCancelableJob(crowded, null),
    (error) => error instanceof ResolveError && error.code === "ambiguous"
      && error.message.includes(ID_A) && error.message.includes(ID_B));
});

test("a record failing validation never reaches signalGroup", async () => {
  const ws = workspace();
  // Foreground record carrying a pgid — the handle invariant the validator exists to stop.
  await createRecord(ws, record(ID_A, { background: false, workerPid: 4242, pgid: 4242 }));
  const { fn, calls } = stubSignal([]);
  await assert.rejects(
    () => cancelJob(ws, ID_A, { signalGroup: fn, sleep: instantSleep }),
    (error) => error instanceof ResolveError && error.code === "invalid",
  );
  assert.deepEqual(calls, []);
});

test("claim rejected: completion committed between resolve and claim wins; no signal is sent", async () => {
  const ws = workspace();
  await createRecord(ws, record(ID_A, BG));
  const { fn, calls } = stubSignal([true]);
  const outcome = await cancelJob(ws, ID_A, {
    signalGroup: fn,
    sleep: instantSleep,
    // Documented test seam (same species as VIBE_SUITE_CODEX_BIN): runs after resolve, before the
    // claim — the exact window the round-2 analysis blocker was about.
    onResolved: async () => {
      await finaliseRecord(ws, ID_A, { status: "completed", rawOutput: "done first" });
    },
  });
  assert.equal(outcome.outcome, "already-terminal");
  assert.equal(outcome.record.status, "completed", "the real verdict is reported, not overwritten");
  assert.deepEqual(calls, [], "a lost claim must send no signal at all");
});

test("a record corrupted AFTER resolve never reaches signalGroup — the claim itself validates", async () => {
  // transact re-reads under contention, so the version the claim commits against can differ from
  // the resolved one (Step-8 review, finding 1). Every corruption lands via the store's own CAS in
  // the onResolved window; the claim updater must refuse each, and the recorder must stay empty.
  // One corruption per validator dimension: handle invariants, schema keys, types, identity.
  function patch(p) {
    return function corrupt(ws) { return updateRecord(ws, ID_A, p); };
  }
  const corruptions = [
    ["forged pgid without a worker", patch({ pgid: 666 })],
    ["pgid !== workerPid", patch({ workerPid: 424242, pgid: 424243 })],
    ["zero pid", patch({ workerPid: 0, pgid: 0 })],
    ["negative pid", patch({ workerPid: -5, pgid: -5 })],
    ["non-integer pid", patch({ workerPid: 10.5, pgid: 10.5 })],
    ["unknown status", patch({ status: "zombie" })],
    ["background flag corrupted", patch({ background: "yes" })],
    ["unparseable timestamp", patch({ createdAt: "yesterday-ish" })],
    ["identity mismatch", patch({ jobId: ID_B })],
    ["missing contract key", async (ws) => {
      await transact(ws, ID_A, (fresh) => {
        const mutilated = { ...fresh };
        delete mutilated.status;
        return mutilated;
      });
    }],
  ];
  for (const [label, corrupt] of corruptions) {
    const ws = workspace();
    await createRecord(ws, record(ID_A, BG));
    const { fn, calls } = stubSignal([true]);
    await assert.rejects(
      () => cancelJob(ws, ID_A, {
        signalGroup: fn, sleep: instantSleep,
        onResolved: async () => { await corrupt(ws); },
      }),
      (error) => error instanceof ResolveError && error.code === "invalid",
      `corruption not refused: ${label}`,
    );
    assert.deepEqual(calls, [], `signal sent despite corruption: ${label}`);
  }
});

test("claim won: a late worker finalise rejects and the cancelled verdict stands", async () => {
  const ws = workspace();
  await createRecord(ws, record(ID_A, BG));
  const { fn } = stubSignal([true, false]);   // alive at probe; gone after SIGTERM grace
  const outcome = await cancelJob(ws, ID_A, { signalGroup: fn, sleep: instantSleep });
  assert.equal(outcome.outcome, "cancelled");

  const late = await finaliseRecord(ws, ID_A, { status: "completed" });
  assert.equal(late, null, "the CAS must refuse to replace the cancel verdict");
  assert.equal((await readRecord(ws, ID_A)).status, "cancelled");
});

test("cancel on an already-terminal job reports the verdict and signals nothing", async () => {
  const ws = workspace();
  await createRecord(ws, record(ID_A, { status: "failed", error: "it broke" }));
  const { fn, calls } = stubSignal([]);
  const outcome = await cancelJob(ws, ID_A, { signalGroup: fn, sleep: instantSleep });
  assert.equal(outcome.outcome, "already-terminal");
  assert.equal(outcome.record.status, "failed");
  assert.deepEqual(calls, []);
});

test("live group: SIGTERM suffices when the group dies in grace", async () => {
  const ws = workspace();
  await createRecord(ws, record(ID_A, BG));
  const { fn, calls } = stubSignal([true, false]);   // probe: alive; first grace poll: gone
  const outcome = await cancelJob(ws, ID_A, { signalGroup: fn, sleep: instantSleep });
  assert.equal(outcome.outcome, "cancelled");
  assert.equal(outcome.signalled, true);
  assert.equal(outcome.groupDead, true);
  const signals = calls.filter(([, s]) => s !== 0).map(([, s]) => s);
  assert.deepEqual(signals, ["SIGTERM"], "no SIGKILL when SIGTERM already reaped the group");
  assert.ok(calls.every(([pid]) => pid === 424242));
});

test("live group ignoring SIGTERM: escalation to SIGKILL, then confirmed dead", async () => {
  const ws = workspace();
  await createRecord(ws, record(ID_A, BG));
  // Probe alive; every grace poll alive; first post-KILL poll gone.
  const graceRounds = Math.ceil(2000 / 50);
  const { fn, calls } = stubSignal([true, ...Array(graceRounds + 1).fill(true), false]);
  const outcome = await cancelJob(ws, ID_A, { signalGroup: fn, sleep: instantSleep });
  assert.equal(outcome.groupDead, true);
  const signals = calls.filter(([, s]) => s !== 0).map(([, s]) => s);
  assert.deepEqual(signals, ["SIGTERM", "SIGKILL"]);
});

test("a group that never dies is reported, not papered over", async () => {
  const ws = workspace();
  await createRecord(ws, record(ID_A, BG));
  const calls = [];
  const immortal = (pid, signal) => { calls.push([pid, signal]); return true; };
  const outcome = await cancelJob(ws, ID_A, { signalGroup: immortal, sleep: instantSleep });
  const signals = calls.filter(([, s]) => s !== 0).map(([, s]) => s);
  assert.deepEqual(signals, ["SIGTERM", "SIGKILL"], "escalation must still run to completion");
  assert.equal(outcome.outcome, "cancelled");
  assert.equal(outcome.groupDead, false, "an unreaped group must surface as a failure to confirm");
  assert.equal((await readRecord(ws, ID_A)).status, "cancelled",
    "the verdict is still owned even when the group resists");
});

test("no live process: abandoned-style records are finalised without signalling", async () => {
  const ws = workspace();
  await createRecord(ws, record(ID_A, BG));
  const { fn, calls } = stubSignal([false]);   // liveness probe: already gone
  const outcome = await cancelJob(ws, ID_A, { signalGroup: fn, sleep: instantSleep });
  assert.equal(outcome.outcome, "cancelled");
  assert.equal(outcome.signalled, false);
  assert.equal(outcome.groupDead, true);
  assert.deepEqual(calls, [[424242, 0]], "one liveness probe, no signals");
});

test("parseOlderThan accepts <n>d|h|m|s and the bare 0, and refuses everything else as usage", () => {
  assert.equal(OLDER_THAN_DEFAULT, "7d");
  for (const [text, ms] of [
    ["7d", 7 * 86_400_000], ["12h", 12 * 3_600_000], ["30m", 30 * 60_000], ["45s", 45_000],
    ["0", 0], ["0d", 0], ["1s", 1000],
  ]) {
    assert.equal(parseOlderThan(text), ms, text);
  }
  for (const bad of ["", "7", "-1d", "1w", "1.5d", "d", "abc", " 7d", "7d ", null, undefined, 7]) {
    assert.throws(() => parseOlderThan(bad), (error) => error instanceof ResolveError && error.code === "usage",
      `accepted: ${String(bad)}`);
  }
});
