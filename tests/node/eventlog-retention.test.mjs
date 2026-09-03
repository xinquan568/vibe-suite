// SPDX-License-Identifier: ISC
// Bounded retention for the event log under concurrent writers (vibe-266).
//
// Every test here drives the protocol through `emit` or through the `write.mjs` primitives it is
// built from, and forces an interleaving through a SEAM — never a promise race, never a sleep. The
// schedules are the ones that defeated six designs and four analysis rounds; each is named for the
// review that produced it, and each says which mechanism defeats it.
//
// Two tests are labelled CHARACTERISATION: they pin a declared NON-guarantee (the frozen analysis's
// non-guarantee (a)) so the boundary is visible, and they are not counted as coverage of anything.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import {
  appendFileSync, chmodSync, closeSync, existsSync, linkSync, mkdirSync, openSync, readdirSync, readFileSync,
  renameSync, statSync, utimesSync, writeFileSync, writeSync,
} from "node:fs";
import path from "node:path";
import test from "node:test";

import {
  emit, eventLogPath, generationName, tailEventLog, tailRecords,
  EVENT_LOG_CLOCK_MARGIN_MS, EVENT_LOG_ELIGIBILITY_MS, EVENT_LOG_MAX_BYTES, EVENT_LOG_MAX_GENERATIONS,
  EVENT_LOG_NAME, EVENT_LOG_NONCE_BYTES, EVENT_LOG_RETAIN_MS, EVENT_LOG_ROTATE_BYTES,
  EVENT_LOG_STALL_BOUND_MS, GENERATION_SHAPE, STATE_DIRNAME,
} from "../../scripts/lib/eventlog.mjs";
import { appendLineAt, retireGenerationsAt, rotateLogAt, EVENT_LINE_MAX } from "../../scripts/lib/write.mjs";

const R = EVENT_LOG_ROTATE_BYTES;
const C = EVENT_LOG_MAX_GENERATIONS;
const E = EVENT_LOG_ELIGIBILITY_MS;
const LOG_REL = path.join(STATE_DIRNAME, EVENT_LOG_NAME);

const ws = () => tmpWorkspace("eventlog-retention-");
const stateDir = (w) => path.join(w, STATE_DIRNAME);
const live = (w) => eventLogPath(w);
const gens = (w) => readdirSync(stateDir(w)).filter((n) => GENERATION_SHAPE.test(n)).sort();
const records = (p) => readFileSync(p, "utf8").split("\n").filter(Boolean).flatMap((l) => { try { return [JSON.parse(l)]; } catch { return []; } });
const allRecords = (w) => [...gens(w).flatMap((g) => records(path.join(stateDir(w), g))), ...(existsSync(live(w)) ? records(live(w)) : [])];
const ageTo = (p, ageMs, now = Date.now()) => { const t = new Date(now - ageMs); utimesSync(p, t, t); };

/** One valid NDJSON record of ~1000 bytes, so a pre-filled live file is also a readable one. */
const FILLER = `${JSON.stringify({ ts: "2026-09-03T00:00:00.000Z", component: "test", event: "fill", detail: { pad: "x".repeat(900) } })}\n`;

/** A live file already at (or past) the rotation threshold, private, in a private state dir. */
function fillLive(w, bytes = R) {
  mkdirSync(stateDir(w), { recursive: true, mode: 0o700 });
  const copies = Math.ceil(bytes / FILLER.length);
  writeFileSync(live(w), FILLER.repeat(copies), { mode: 0o600 });
  return readFileSync(live(w));
}

/** A generation-shaped file of ours, `ageMs` old by mtime. Returns its name. */
function makeGeneration(w, { ageMs = 0, mode = 0o600, name = generationName(), content = FILLER, now = Date.now() } = {}) {
  mkdirSync(stateDir(w), { recursive: true, mode: 0o700 });
  const p = path.join(stateDir(w), name);
  writeFileSync(p, content, { mode });
  chmodSync(p, mode);
  ageTo(p, ageMs, now);
  return name;
}

const rec = (event, extra = {}) => ({ component: "test", event, detail: { ...extra } });

// ------------------------------------------------------------------------------- the constants

test("the retention constants relate as the plan states, and the nominal total is derived (vibe-266)", () => {
  assert.equal(EVENT_LOG_MAX_BYTES, (EVENT_LOG_MAX_GENERATIONS + 1) * EVENT_LOG_ROTATE_BYTES,
    "the 8 MiB the operator reads is (C + 1) generations' worth, not a free literal");
  assert.equal(EVENT_LOG_ELIGIBILITY_MS, EVENT_LOG_RETAIN_MS + EVENT_LOG_CLOCK_MARGIN_MS);
  assert.equal(EVENT_LOG_STALL_BOUND_MS, Math.floor(EVENT_LOG_ELIGIBILITY_MS / 2));
  // The margin's three allocated parts: <= 2 s precision + <= 50 min forward clock movement + <= 9 min 58 s latency.
  assert.ok(EVENT_LOG_CLOCK_MARGIN_MS >= 2_000 + 50 * 60_000 + (9 * 60_000 + 58_000),
    "the margin must cover the sum of what it is said to cover");
  assert.equal(EVENT_LOG_NONCE_BYTES * 8, 128, "a 128-bit fresh value is the declared width");
  // The policy VALUES, pinned literally as well: a change to R or C is a change to the operator's contract
  // and must fail a test, not merely keep the derivation consistent.
  assert.equal(EVENT_LOG_ROTATE_BYTES, 1024 * 1024);
  assert.equal(EVENT_LOG_MAX_GENERATIONS, 7);
  assert.equal(EVENT_LOG_MAX_BYTES, 8 * 1024 * 1024);
  assert.equal(EVENT_LOG_RETAIN_MS, 7 * 24 * 60 * 60 * 1000);
  assert.equal(EVENT_LOG_CLOCK_MARGIN_MS, 60 * 60 * 1000);
});

test("generationName matches GENERATION_SHAPE and three near-miss names do not (vibe-266)", () => {
  const name = generationName(new Date("2026-09-03T13:15:00.123Z"));
  assert.match(name, GENERATION_SHAPE);
  assert.ok(name.startsWith(`${EVENT_LOG_NAME}.20260903T131500Z.`), name);
  const hex = name.split(".").at(-1);
  assert.doesNotMatch(`${EVENT_LOG_NAME}.20260903T131500Z.${hex.slice(0, 31)}`, GENERATION_SHAPE, "31 hex digits");
  assert.doesNotMatch(`${EVENT_LOG_NAME}.20260903T131500.${hex}`, GENERATION_SHAPE, "no Z");
  assert.doesNotMatch(`${EVENT_LOG_NAME}.20260903T131500Z.${hex.toUpperCase()}`, GENERATION_SHAPE, "upper-case hex");
  assert.doesNotMatch(EVENT_LOG_NAME, GENERATION_SHAPE, "the live file itself is never a candidate");
});

// ------------------------------------------------------------------------- the protocol via emit

test("past the rotation threshold the live file is rotated and a fresh live receives the record (vibe-266)", async () => {
  const w = ws();
  const before = fillLive(w);
  assert.equal(await emit(w, rec("after-rotation")), true);
  const g = gens(w);
  assert.equal(g.length, 1, "exactly one generation");
  assert.deepEqual(readFileSync(path.join(stateDir(w), g[0])), before, "the generation IS the old live file, byte for byte");
  const fresh = records(live(w));
  assert.equal(fresh.length, 1);
  assert.equal(fresh[0].event, "after-rotation", "the record landed in the fresh live, not the full one");
  assert.equal(statSync(live(w)).mode & 0o777, 0o600);
});

test("at capacity — C generations inside the floor and a full live — emit refuses and changes nothing (vibe-266)", async () => {
  const w = ws();
  fillLive(w);
  const names = Array.from({ length: C }, () => makeGeneration(w, { ageMs: 60_000 }));
  const snapshot = () => Object.fromEntries(readdirSync(stateDir(w)).map((n) => [n, statSync(path.join(stateDir(w), n)).size]));
  const before = snapshot();
  assert.equal(await emit(w, rec("refused")), false, "G4: nothing inside the floor is discarded to make room");
  assert.deepEqual(snapshot(), before, "no file created, none removed, none grown");
  assert.deepEqual(gens(w), names.sort());
});

test("a generation older than the floor but inside the clock margin is NOT yet eligible: emit refuses at capacity and the reader says so (vibe-266)", async () => {
  // The floor is W; eligibility is W + margin. Inside that hour a generation is old but still protected —
  // a sweep that compared against W alone would retire it early on a clock that has merely slewed.
  const w = ws();
  fillLive(w);
  const now = Date.now();
  const inTheMargin = EVENT_LOG_RETAIN_MS + Math.floor(EVENT_LOG_CLOCK_MARGIN_MS / 2);
  const names = Array.from({ length: C }, () => makeGeneration(w, { ageMs: inTheMargin, now }));
  assert.equal(await emit(w, rec("refused"), { now }), false, "all C are past the floor but inside the margin: none eligible, refuse");
  assert.deepEqual(gens(w), names.sort(), "nothing retired");
  const view = await tailEventLog(w, 5, { now });
  assert.equal(view.atCapacity, true);
  assert.equal(view.generations, C);
});

test("the sweep runs BEFORE the count: one aged generation frees a slot and the record is admitted (vibe-266)", async () => {
  const w = ws();
  fillLive(w);
  const fresh = Array.from({ length: C - 1 }, () => makeGeneration(w, { ageMs: 60_000 }));
  const aged = makeGeneration(w, { ageMs: E + 60_000 });
  assert.equal(await emit(w, rec("admitted")), true, "a cap full of old generations is not a one-way latch");
  const after = gens(w);
  assert.ok(!after.includes(aged), "the aged generation was retired");
  assert.equal(after.length, C, "C - 1 fresh + the one just rotated");
  for (const f of fresh) assert.ok(after.includes(f), `fresh generation ${f} untouched`);
  assert.equal(records(live(w))[0].event, "admitted");
});

test("two emitters that both observe a full live produce exactly one generation and both records land (vibe-266)", async () => {
  const w = ws();
  fillLive(w);
  let peer;
  const ok = await emit(w, rec("A"), {
    onChecked: async () => { peer = await emit(w, rec("B")); },   // inside A's window: B rotates and writes first
  });
  assert.equal(peer, true);
  assert.equal(ok, true, "A finds the pathname moved, retries, and lands");
  assert.equal(gens(w).length, 1, "design 4's failure — a fresh live destroyed in the gap — cannot happen: A moves nothing");
  assert.deepEqual(records(live(w)).map((r) => r.event), ["B", "A"]);
});

test("emit falls through an 'absent' rotation: the live file removed inside the window, the retry creates a fresh one and the record lands (vibe-266)", async () => {
  const w = ws();
  fillLive(w);
  const ok = await emit(w, rec("after-absent"), {
    onChecked: () => { renameSync(live(w), path.join(stateDir(w), "moved-aside.bin")); },   // not a generation shape: the sweep never sees it
  });
  assert.equal(ok, true, "absent is not a refusal — the retry creates the fresh live");
  assert.deepEqual(records(live(w)).map((r) => r.event), ["after-absent"]);
  assert.equal(gens(w).length, 0);
});

test("a peer's replacement that is itself full makes the second append full: the record is refused, not written anywhere (vibe-266)", async () => {
  const w = ws();
  fillLive(w);
  const ok = await emit(w, rec("R2"), {
    onChecked: async () => {
      assert.equal(await emit(w, rec("P")), true);                          // rotates A, creates B, writes P
      appendFileSync(live(w), FILLER.repeat(Math.ceil(R / FILLER.length)));  // B is now at the threshold too
    },
  });
  assert.equal(ok, false, "moved, then the retry observes B full: two attempts at most, then refuse");
  assert.ok(!allRecords(w).some((r) => r.event === "R2"), "the refused record is nowhere on disk");
  assert.equal(gens(w).length, 1, "and nothing was rotated by the stale rotator");
});

test("ROUND 3/4 — a stale rotator does not move a below-threshold replacement; the late writer's record survives (vibe-266)", async () => {
  // R2 judged A full and stalls before its identity observation. Inside the stall: P rotates A and
  // creates B; Q opens B, observes it below the threshold, and writes. R2 resumes: its lstat sees B,
  // not A -> "moved" -> nothing renamed -> R2 retries into B. The replacement inode is never moved,
  // so no sweep can ever qualify a file that holds Q's fresh record.
  const w = ws();
  const original = fillLive(w);
  let q;
  const ok = await emit(w, rec("R2"), {
    onChecked: async () => {
      assert.equal(await emit(w, rec("P")), true);                         // rotates A -> G, creates B, writes P
      q = await appendLineAt(w, LOG_REL, JSON.stringify(rec("Q")), { maxBytes: R });
      assert.equal(q.outcome, "appended", "Q observed B below the threshold and wrote into B");
    },
  });
  assert.equal(ok, true);
  const g = gens(w);
  assert.equal(g.length, 1, "B was NOT moved by the stale rotator");
  assert.deepEqual(readFileSync(path.join(stateDir(w), g[0])), original, "the one generation is A, untouched");
  assert.deepEqual(records(live(w)).map((r) => r.event), ["P", "Q", "R2"], "all three in the live inode B");
});

test("ROUND 2 — the split-stall ORDERING: a rotator paused before its observation, an appender arriving in the pause, then the sweep — nothing destroyed, because the appender observes full and writes nothing into A (vibe-266)", async () => {
  // The old timeline: rotator R judges A full and stalls 99.5 of 101; appender Q arrives at 99.4 and
  // writes at 101.2; a sweeper qualifies A's generation at 101.1 and unlinks at 101.3. This test forces
  // that ORDERING through the seam, not the virtual times: E is a module constant, the sweep step is
  // made real by ageing A's generation with utimes, and the mechanism that defeats the timeline is
  // time-independent -- O2-i: Q observes A AT the threshold through its own fstat and writes NOTHING
  // into A, so it rotates A itself and lands in the fresh live. R's stall length is irrelevant; the
  // plan's "E = 101 by injected constants" fixture is therefore not modelled, and that is disclosed.
  const w = ws();
  const original = fillLive(w);
  const ok = await emit(w, rec("R"), {
    onChecked: async () => {
      assert.equal(await emit(w, rec("Q")), true, "Q: observed full, rotated A, wrote into the fresh live");
    },
  });
  assert.equal(ok, true, "R resumes, finds the live moved, retries into the fresh live");
  const [gA] = gens(w);
  assert.deepEqual(readFileSync(path.join(stateDir(w), gA)), original, "Q's record is NOT in A's generation");
  // Now the sweeper's turn, at 101.1 in the old timeline: A's generation is aged and retired ...
  ageTo(path.join(stateDir(w), gA), E + 60_000);
  const swept = await retireGenerationsAt(w, STATE_DIRNAME, { shape: GENERATION_SHAPE, olderThanMs: E });
  assert.deepEqual(swept.retired, [gA]);
  // ... and both records are exactly where they were written: the surviving live file.
  assert.deepEqual(records(live(w)).map((r) => r.event), ["Q", "R"]);
});

test("ROUND 1 — a write through a pre-rotation descriptor BEFORE qualification refreshes mtime and protects the generation (vibe-266)", async () => {
  const w = ws();
  fillLive(w);
  ageTo(live(w), E + 60_000);                                              // content already aged
  const fd = openSync(live(w), "a");                                       // a pre-rotation descriptor
  try {
    const ino = statSync(live(w)).ino;
    const name = generationName();
    assert.equal(await rotateLogAt(w, LOG_REL, { generationRel: path.join(STATE_DIRNAME, name), expectedIno: ino }), "rotated");
    writeSync(fd, `${JSON.stringify(rec("straggler"))}\n`);              // lands in the rotated inode, refreshing mtime
    const judged = await retireGenerationsAt(w, STATE_DIRNAME, { shape: GENERATION_SHAPE, olderThanMs: E });
    assert.deepEqual(judged.retired, [], "refreshed mtime: inside the floor, kept");
    assert.equal(judged.kept, 1);
    assert.equal(records(path.join(stateDir(w), name)).at(-1).event, "straggler");
  } finally {
    closeSync(fd);
  }
});

test("CHARACTERISATION of non-guarantee (a): a write through a pre-rotation descriptor AFTER qualification is lost with the retired generation (vibe-266)", async () => {
  // Not coverage. The frozen analysis declares this: a writer whose interval from its size observation
  // to its write exceeds the eligibility delay can lose its one record. Pinned so the boundary is
  // visible, not to claim anything about it.
  const w = ws();
  fillLive(w);
  ageTo(live(w), E + 60_000);
  const fd = openSync(live(w), "a");
  try {
    const name = generationName();
    assert.equal(await rotateLogAt(w, LOG_REL, { generationRel: path.join(STATE_DIRNAME, name), expectedIno: statSync(live(w)).ino }), "rotated");
    const swept = await retireGenerationsAt(w, STATE_DIRNAME, {
      shape: GENERATION_SHAPE, olderThanMs: E,
      onQualified: () => { writeSync(fd, `${JSON.stringify(rec("late"))}\n`); },   // after qualification, before the unlink
    });
    assert.deepEqual(swept.retired, [name]);
    assert.ok(!allRecords(w).some((r) => r.event === "late"), "the late record went with the retired generation — the declared boundary");
  } finally {
    closeSync(fd);
  }
});

test("ROUND 2 BLOCKER, literally: a sweeper qualifies an aged reservation, a rotation aims at that exact name, the resumed unlink destroys nothing fresh (vibe-266)", async () => {
  // The production protocol never reserves a name, so the fixture creates the aged, generation-shaped
  // file the blocker needs. The absent-check is what must refuse the rename: without it, rename would
  // replace the qualified inode with the fresh live file and the resumed unlink would destroy it.
  const w = ws();
  const fresh = fillLive(w);
  const reserved = makeGeneration(w, { ageMs: E + 60_000, content: "" });   // aged and EMPTY, like a reservation
  const ino = statSync(live(w)).ino;
  let rotation;
  const swept = await retireGenerationsAt(w, STATE_DIRNAME, {
    shape: GENERATION_SHAPE, olderThanMs: E,
    onQualified: async (name) => {
      assert.equal(name, reserved);
      rotation = await rotateLogAt(w, LOG_REL, { generationRel: path.join(STATE_DIRNAME, reserved), expectedIno: ino });
    },
  });
  assert.equal(rotation, "exists", "O1: the destination is in use — refused, not renamed over");
  assert.deepEqual(swept.retired, [reserved], "the aged reservation is retired");
  assert.ok(existsSync(live(w)), "the fresh live file survives");
  assert.deepEqual(readFileSync(live(w)), fresh, "byte for byte");
});

test("a paused sweeper resumes after a concurrent rotation to a DIFFERENT fresh name: the aged one goes, the fresh generation and the live survive (vibe-266)", async () => {
  const w = ws();
  const aged = makeGeneration(w, { ageMs: E + 60_000 });
  let fresh;
  const swept = await retireGenerationsAt(w, STATE_DIRNAME, {
    shape: GENERATION_SHAPE, olderThanMs: E,
    onQualified: async () => {
      fillLive(w);
      assert.equal(await emit(w, rec("during-sweep")), true);
      [fresh] = gens(w).filter((n) => n !== aged);
    },
  });
  // The emit inside the window runs its own sweep and may retire the aged generation first; the outer
  // sweep then meets ENOENT and skips. Either way the aged one is gone and nothing else was touched.
  assert.ok(!existsSync(path.join(stateDir(w), aged)), "the aged generation is gone");
  assert.deepEqual(swept.refused, []);
  assert.ok(swept.retired.length <= 1 && swept.retired.every((n) => n === aged));
  assert.ok(existsSync(path.join(stateDir(w), fresh)), "the generation created inside the sweep's window survives");
  assert.equal(records(live(w))[0].event, "during-sweep");
});

test("a nonce collision refuses the record: emit is false and nothing on disk changes (vibe-266)", async () => {
  const w = ws();
  fillLive(w);
  const existing = makeGeneration(w, { ageMs: 60_000 });
  const before = Object.fromEntries(readdirSync(stateDir(w)).map((n) => [n, readFileSync(path.join(stateDir(w), n)).length]));
  assert.equal(await emit(w, rec("collide"), { generationName: () => existing }), false,
    "rotateLogAt returns exists; the record is refused rather than the generation replaced");
  const after = Object.fromEntries(readdirSync(stateDir(w)).map((n) => [n, readFileSync(path.join(stateDir(w), n)).length]));
  assert.deepEqual(after, before);
});

test("a REAL filesystem failure inside the retention protocol surfaces as false, never as a throw (property 1) (vibe-266)", async () => {
  // The plan's read-only-state-directory fixture is defeated by emit itself: `secureDirAt` re-tightens the
  // directory to 0700 on every call, restoring write permission before the protocol runs. The permission
  // is therefore removed INSIDE the rotation window, after `secureDirAt` and before the rename.
  if (typeof process.getuid === "function" && process.getuid() === 0) return;   // root writes anywhere: skip honestly
  const w = ws();
  fillLive(w);
  let ok;
  try {
    ok = await emit(w, rec("blocked"), { onChecked: () => { chmodSync(stateDir(w), 0o500); } });   // rename -> EACCES
  } finally {
    chmodSync(stateDir(w), 0o700);
  }
  assert.equal(ok, false, "EACCES from rename is swallowed by emit's boundary");
  assert.ok(!allRecords(w).some((r) => r.event === "blocked"));
  assert.equal(gens(w).length, 0, "nothing was renamed");
});

test("a failure inside the retention protocol surfaces as false, never as a throw (property 1) (vibe-266)", async () => {
  const w = ws();
  fillLive(w);
  assert.equal(await emit(w, rec("x"), { onChecked: () => { throw new Error("rotation window failed"); } }), false);
  makeGeneration(w, { ageMs: E + 60_000 });
  assert.equal(await emit(w, rec("y"), { onQualified: () => { throw new Error("sweep window failed"); } }), false);
});

test("writers that observed the live below the threshold all land, and the live exceeds it by at most one record each (vibe-266)", async () => {
  const w = ws();
  mkdirSync(stateDir(w), { recursive: true, mode: 0o700 });
  const maxBytes = 1000;
  writeFileSync(live(w), "y".repeat(990) + "\n", { mode: 0o600 });
  const line = JSON.stringify({ e: "z".repeat(80) });
  const k = 5;
  const outcomes = await Promise.all(Array.from({ length: k }, () => appendLineAt(w, LOG_REL, line, { maxBytes })));
  for (const o of outcomes) assert.ok(["appended", "full"].includes(o.outcome));
  assert.ok(outcomes.some((o) => o.outcome === "appended"), "at least the first observer writes");
  const size = statSync(live(w)).size;
  assert.ok(size <= maxBytes + k * (Buffer.byteLength(line) + 1), `live is ${size}: the overshoot is bounded by the concurrent writers' records`);
});

// ------------------------------------------------------------------------------------ the reader

test("tailEventLog spans the live file and its generations newest last, with ONE ceiling across files (vibe-266)", async () => {
  const w = ws();
  mkdirSync(stateDir(w), { recursive: true, mode: 0o700 });
  const older = makeGeneration(w, { name: generationName(new Date("2026-09-01T00:00:00Z")), content: `${JSON.stringify(rec("g1a"))}\n${JSON.stringify(rec("g1b"))}\n` });
  const newer = makeGeneration(w, { name: generationName(new Date("2026-09-02T00:00:00Z")), content: `${JSON.stringify(rec("g2a"))}\n` });
  writeFileSync(live(w), `${JSON.stringify(rec("l1"))}\n${JSON.stringify(rec("l2"))}\n`, { mode: 0o600 });
  assert.ok(older < newer, "name order is rotation order");

  const all = await tailEventLog(w, 10);
  assert.deepEqual(all.records.map((r) => r.event), ["g1a", "g1b", "g2a", "l1", "l2"], "older generation, newer generation, live");
  assert.equal(all.truncated, false);
  assert.equal(all.generations, 2);

  const two = await tailEventLog(w, 2);
  assert.deepEqual(two.records.map((r) => r.event), ["l1", "l2"]);
  assert.equal(two.truncated, true, "older records exist — in the generations");

  const ceiling = 100;
  const capped = await tailEventLog(w, 10, { ceiling, chunk: 32 });
  assert.ok(capped.bytesRead <= ceiling, `read ${capped.bytesRead} bytes against a TOTAL ceiling of ${ceiling} across three files`);
  assert.equal(capped.truncated, true);
});

test("tailEventLog's atCapacity comes from the same judgment as admission, not from a name count (vibe-266)", async () => {
  const w = ws();
  fillLive(w);
  const names = Array.from({ length: C }, () => makeGeneration(w, { ageMs: 60_000 }));
  const now = Date.now();
  assert.equal((await tailEventLog(w, 5, { now })).atCapacity, true, "C fresh generations and a full live");

  ageTo(path.join(stateDir(w), names[0]), E + 60_000, now);                // one aged: the next emit would retire it
  const aged = await tailEventLog(w, 5, { now });
  assert.equal(aged.atCapacity, false, "a name count would say capacity; the judgment says one slot is about to free");
  assert.equal(aged.generations, C - 1);

  ageTo(path.join(stateDir(w), names[0]), 60_000, now);
  chmodSync(path.join(stateDir(w), names[1]), 0o644);                      // one near-miss: not the writer's shape
  const nearMiss = await tailEventLog(w, 5, { now });
  assert.equal(nearMiss.atCapacity, false);
  assert.equal(nearMiss.generations, C - 1, "a refused sibling is reported by the sweep, never counted");
});
