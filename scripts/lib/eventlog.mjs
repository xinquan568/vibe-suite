// SPDX-License-Identifier: ISC
// The suite's own append-only event log (vibe-207 / grill M5), with bounded retention (vibe-266).
//
// **Not to be confused with `events.mjs`, one directory entry away.** That module *reads* codex's
// `--json` stream and reduces it to the facts the job engine needs. This one *writes* the suite's
// own records — a durable history spanning dispatch, gate decisions, hook reports and prune, which
// is the thing no existing channel covers. Per-job worker logs, the record's own
// `errorClass`/`stderrTail`, and the auditor's ledger are each scoped to one subject; none is a
// history you can read.
//
// **The durability contract this module implements** (frozen in the issue). `events.log` is a
// diagnostic record, not a ledger:
//
//   1. Observability never affects the operation observed. `emit` has NO failing path a caller can
//      see: it returns `false` and moves on, whatever went wrong. Every call site is
//      fire-and-forget, and none branches on the result. A throw here could block a session inside
//      the Stop gate or strand a job inside finalise, which would make the diagnostics more
//      expensive than the thing they diagnose.
//   2. A record is written whole or not at all — `appendLineAt` does one bounded `write` and
//      verifies it; a torn line is the reader's to drop.
//   3. Retention is bounded and has a content-age floor (vibe-266). The live file rotates at
//      `EVENT_LOG_ROTATE_BYTES` into a dated generation beside it; a generation is retired only once
//      its newest record — its `mtime` — is older than `EVENT_LOG_ELIGIBILITY_MS`; at most
//      `EVENT_LOG_MAX_GENERATIONS` are kept, and when all of them are still inside the floor a new
//      record is REFUSED rather than a generation destroyed.
//   4. Destruction unrelated to retention is unacceptable. The only deletion is the sweep in
//      `write.mjs`, and it deletes only what `judgeGenerationsAt` recognises as an aged generation
//      of ours. What that guarantee rests on, and what it does not promise, is stated in
//      `commands/jobs.md` and in the retention constants' comments below.
//   5. No total order is guaranteed. `ts` is metadata, not a sequence: records from different
//      processes interleave, and a reader that infers causality from adjacency will be wrong.

import { randomBytes } from "node:crypto";
import { open, readdir } from "node:fs/promises";
import path from "node:path";

import {
  appendLineAt, ensureDirAt, judgeGenerationsAt, retireGenerationsAt, rotateLogAt, secureDirAt,
  EVENT_LINE_MAX,
} from "./write.mjs";

/**
 * The state directory's name, declared here rather than imported from `jobs.mjs`.
 *
 * `jobs.mjs` imports this module to emit, so importing it back would close a cycle. The duplication
 * is made safe by a test that pins the two equal — a guard, not a hope.
 */
export const STATE_DIRNAME = ".vibe-suite-state";

/** The log's name inside the state directory. */
export const EVENT_LOG_NAME = "events.log";

// ------------------------------------------------------------------------ retention (vibe-266)

/** The live file rotates once a writer observes it at or above this many bytes. ~3,500 records. */
export const EVENT_LOG_ROTATE_BYTES = 1 * 1024 * 1024;

/**
 * How many rotated generations may exist. With `EVENT_LOG_ROTATE_BYTES` this makes the nominal total
 * `(EVENT_LOG_MAX_GENERATIONS + 1) * EVENT_LOG_ROTATE_BYTES` — the 8 MiB the documentation has
 * always named. When this many generations are all still inside the floor, a new record is refused.
 */
export const EVENT_LOG_MAX_GENERATIONS = 7;

/**
 * The cap's nominal total: the generations plus one live file, before the concurrency slack.
 *
 * **Derived, not a literal**, so the number the operator reads and the mechanism that produces it
 * cannot drift apart. The slack: the live file can exceed the rotation size by one record per appender
 * whose write landed past the threshold before the first rename, and the cap by one generation per
 * rotator that acted on a stale count — both proportional to how many suite processes run at once,
 * which nothing here caps.
 */
export const EVENT_LOG_MAX_BYTES = (EVENT_LOG_MAX_GENERATIONS + 1) * EVENT_LOG_ROTATE_BYTES;

/** The content-age floor: a generation younger than this, by its newest record, is never retired. */
export const EVENT_LOG_RETAIN_MS = 7 * 24 * 60 * 60 * 1000;

/**
 * The clock margin added to the floor before a generation is eligible, allocated — the sum is the
 * budget, and each part is the thing it covers:
 *
 *   * `<= 2 s`       the coarsest timestamp precision of a local filesystem (FAT); APFS and ext4 keep
 *                    nanoseconds, HFS+ one second.
 *   * `<= 50 min`    the total FORWARD movement of the wall clock since the generation's last write,
 *                    steps and slew together — a 500 ppm slew over a 7-day retained lifetime is about
 *                    5 minutes; the rest is a budget for small corrections. A forward move larger than
 *                    this during a generation's lifetime can retire it early, and is declared as a
 *                    non-guarantee.
 *   * `<= 9 min 58 s` the sweeper's own observation latency between its `lstat` and its `unlink` — a
 *                    sweep over a handful of entries is milliseconds; the allowance is generous.
 *
 * A backward clock move only delays a retirement and needs no budget.
 */
export const EVENT_LOG_CLOCK_MARGIN_MS = 60 * 60 * 1000;

/** The age past which a generation is eligible to be retired: the floor plus the clock margin. */
export const EVENT_LOG_ELIGIBILITY_MS = EVENT_LOG_RETAIN_MS + EVENT_LOG_CLOCK_MARGIN_MS;

/**
 * The declared bound on each of the two intervals the floor's guarantee depends on: a writer's, from
 * its own size observation to its write; a rotator's, from the observation that authorises its
 * rename to the rename. Both under half the eligibility delay and no record inside the floor can be
 * lost to the sweep; a process suspended longer than this between two filesystem calls is outside the
 * guarantee. Exported so the documentation and the PR quote one number.
 */
export const EVENT_LOG_STALL_BOUND_MS = Math.floor(EVENT_LOG_ELIGIBILITY_MS / 2);

/**
 * Bytes of CSPRNG entropy in a generation name. 128 bits: the chance that any two of N lifetime
 * rotations draw the same value is at most N² · 2⁻¹²⁹ — at the declared operational maximum of 2²⁴
 * rotations per workspace (16 TiB of log at a megabyte a generation) that is 2⁻⁸¹, against a
 * declared budget of 2⁻⁶⁴. A repeated draw is refused by `rotateLogAt`, never renamed over.
 */
export const EVENT_LOG_NONCE_BYTES = 16;

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * The writer's exact generated name: `events.log.<yyyymmdd>T<hhmmss>Z.<32 hex>`. The timestamp is the
 * rotation time and orders generations for display ONLY — `mtime` is the retention clock, because
 * content can still arrive after the name is chosen. The live file does not match, so no sweep ever
 * considers it.
 */
export const GENERATION_SHAPE = new RegExp(
  `^${escapeRegExp(EVENT_LOG_NAME)}\\.\\d{8}T\\d{6}Z\\.[0-9a-f]{${EVENT_LOG_NONCE_BYTES * 2}}$`);

/** A fresh generation name for a rotation happening `now`. */
export function generationName(now = new Date()) {
  const stamp = now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");   // 20260903T131500Z
  return `${EVENT_LOG_NAME}.${stamp}.${randomBytes(EVENT_LOG_NONCE_BYTES).toString("hex")}`;
}

/**
 * The cap applied to each string in `detail` when a record does not fit.
 *
 * Sized to the gate's own `REASON_CAP` (500), because the longest field the suite routinely records
 * is a normalized reviewer reason and the gate already truncates it there.
 */
const DETAIL_STRING_CAP = 500;

/** `<workspace>/.vibe-suite-state/events.log`. */
export function eventLogPath(workspace) {
  return path.join(workspace, STATE_DIRNAME, EVENT_LOG_NAME);
}

/** Bytes the record occupies as one NDJSON line, terminator included. */
function lineBytes(record) {
  return Buffer.byteLength(JSON.stringify(record), "utf8") + 1;
}

/** Every string in `detail`, clipped — the cheapest shrink that keeps the shape readable. */
function capStrings(detail) {
  const out = {};
  for (const [key, value] of Object.entries(detail)) {
    out[key] = typeof value === "string" && value.length > DETAIL_STRING_CAP
      ? `${value.slice(0, DETAIL_STRING_CAP)}…`
      : value;
  }
  return out;
}

/**
 * Fit `record` inside `EVENT_LINE_MAX`, disclosing any elision.
 *
 * Three steps, weakest first: as given; every string clipped; the detail dropped entirely. The
 * *event* is what answers "what happened", so it is the last thing to go — a record that says
 * `gate.decision` with no detail is still worth more than no record.
 */
function fit(record) {
  if (lineBytes(record) <= EVENT_LINE_MAX) return record;

  const clipped = { ...record, detail: capStrings(record.detail), capped: true };
  if (lineBytes(clipped) <= EVENT_LINE_MAX) return clipped;

  const bare = { ...record, detail: { keys: Object.keys(record.detail).length }, capped: true };
  return lineBytes(bare) <= EVENT_LINE_MAX ? bare : null;
}

const LOG_REL = path.join(STATE_DIRNAME, EVENT_LOG_NAME);

/**
 * Append one record to the workspace's event log. **Never throws, never rejects.**
 *
 * Returns `true` when a record reached the log and `false` for every other outcome — an
 * unserialisable detail, a directory at the log path, a workspace that is not there, a state
 * directory that is a file, a log another uid owns, **or a log at capacity**. The caller is not
 * expected to look: property 1 says the operation being observed must run identically either way,
 * and a call site that branched on this would be the first step toward observability that can fail
 * its own caller.
 *
 * **The retention protocol (vibe-266), in the order that makes it safe:**
 *
 *   1. Append with `maxBytes`. The writer observes the live file's size through its own descriptor
 *      before writing; below the threshold the record lands and we are done. At or above it, nothing
 *      was written and we hold the inode we judged.
 *   2. Retire what has aged. The sweep runs BEFORE the count, so a cap full of old generations frees
 *      itself — otherwise a workspace that once filled its cap would stay deaf forever.
 *   3. Count. If the cap is full of generations still inside the floor, REFUSE this record. Nothing
 *      inside the floor is ever discarded to make room.
 *   4. Rotate the inode we judged, to a fresh name. `"exists"` (a repeated draw) refuses the record;
 *      every other outcome — rotated, or a peer got there first — falls through to
 *   5. one more append. A fresh live file receives the record, or a peer's fresh live does; if even
 *      that is full, the record is refused.
 *
 * Two append attempts at most; one directory read and a handful of `lstat`s, only when the live
 * file is at the threshold. No lock anywhere — a crash between any two steps leaves nothing the next
 * emit cannot finish, which is what a lock could not offer.
 *
 * `hooks` are test seams only: `{ now, generationName, onChecked, onQualified, onBeforeReopen }`.
 */
export async function emit(workspace, { component, event, jobId = null, detail = {} } = {}, hooks = {}) {
  try {
    const record = { ts: new Date().toISOString(), component, event };
    // Absent, not null: a null `jobId` would read as "this event had no job", which is a different
    // claim from "a job id does not apply to this kind of event".
    if (jobId !== null && jobId !== undefined) record.jobId = jobId;
    record.detail = detail;

    const fitted = fit(record);              // throws on a circular detail — caught below, as intended
    if (fitted === null) return false;
    const line = JSON.stringify(fitted);

    await ensureDirAt(workspace, STATE_DIRNAME);
    await secureDirAt(workspace, STATE_DIRNAME);

    const first = await appendLineAt(workspace, LOG_REL, line,
      { maxBytes: EVENT_LOG_ROTATE_BYTES, onBeforeReopen: hooks.onBeforeReopen ?? null });
    if (first.outcome === "appended") return true;

    // The live file is full and this descriptor wrote nothing into it (step 1).
    const now = hooks.now ?? Date.now();
    const sweep = await retireGenerationsAt(workspace, STATE_DIRNAME, {
      shape: GENERATION_SHAPE, olderThanMs: EVENT_LOG_ELIGIBILITY_MS, now,
      onQualified: hooks.onQualified ?? null,
    });                                                                          // step 2
    if (sweep.kept >= EVENT_LOG_MAX_GENERATIONS) return false;                  // step 3: at capacity, refuse

    const name = (hooks.generationName ?? generationName)();
    const rotated = await rotateLogAt(workspace, LOG_REL, {
      generationRel: path.join(STATE_DIRNAME, name), expectedIno: first.ino,
      onChecked: hooks.onChecked ?? null,
    });                                                                          // step 4
    if (rotated === "exists") return false;                                      // a repeated draw refuses the record

    const second = await appendLineAt(workspace, LOG_REL, line, { maxBytes: EVENT_LOG_ROTATE_BYTES });   // step 5
    return second.outcome === "appended";
  } catch {
    return false;
  }
}

/**
 * The furthest back a `jobs log` read will scan, in bytes — a TOTAL across the live file and every
 * generation it reaches (vibe-266), not a per-file allowance.
 *
 * **This is the bound, and "read backwards until N complete lines" is not one.** That termination
 * condition is finding N newlines, and nothing guarantees a file contains them within any distance
 * of the end: a torn write leaves a fragment, and a foreign writer can leave an arbitrarily long run
 * with no newline in it at all. The ceiling is what makes the read finite regardless of content.
 */
export const EVENT_LOG_TAIL_MAX_BYTES = 256 * 1024;

/** Read granularity. Large enough that an ordinary tail is one or two reads. */
const READ_CHUNK = 64 * 1024;

/**
 * The last `n` parseable records of ONE file, read backwards from the end and bounded by `ceiling`
 * bytes.
 *
 * Returns `{ records, truncated, bytesRead, size }`. **`truncated` is true whenever older records
 * exist that this result does not carry** — either because the scan stopped before the start of the
 * file (the ceiling, or enough records found) or because more records were parsed than `n`. It is
 * deliberately the operator's question, "am I seeing everything?", rather than the implementation's
 * "did the scan reach byte zero?": on a small file the scan reaches the start and the answer is
 * still no. A tail presented as the whole log is a lie a reader cannot detect.
 *
 * Three details that are easy to get wrong and are the reason this is a function rather than three
 * lines at the call site:
 *
 *   * **Decoding happens after the chunks are assembled**, never per chunk. A backwards read splits
 *     a multi-byte character across a boundary roughly one time in three for CJK text, and decoding
 *     early replaces it with U+FFFD.
 *   * **The first line is dropped whenever the scan started mid-file**, because it is a fragment of
 *     a record whose beginning was never read. Handing it to `JSON.parse` would be a parse error the
 *     reader then has to explain.
 *   * **An unparseable line is skipped, not fatal.** Property 2 of the contract says a record is
 *     written whole or not at all and a torn one is the reader's to drop; a concurrent appender's
 *     partial write is expected, not exceptional.
 *
 * Every failure — an absent log, a directory, an unreadable file — yields the empty result rather
 * than raising, for the same reason `emit` cannot throw.
 */
export async function tailRecords(logPath, n, options = {}) {
  const { ceiling = EVENT_LOG_TAIL_MAX_BYTES, chunk = READ_CHUNK } = options;
  const empty = { records: [], truncated: false, bytesRead: 0, size: 0 };
  try {
    // `const handle = await open(p, "r")` is the ONE consumption form the write-discipline checker
    // accepts for an open: a read-only string literal flag, bound to a fresh local. The handle may
    // then only be called through — never hoisted to an outer `let`, never passed to a helper — so
    // the whole scan lives here rather than in a function taking the handle as an argument.
    const handle = await open(logPath, "r");
    try {
      const info = await handle.stat();
      if (!info.isFile()) return empty;

      const size = info.size;
      const parts = [];
      let pos = size;
      let bytesRead = 0;
      let newlines = 0;
      // `newlines <= n` rather than `< n`: with a fragment at the front, n complete records need
      // n+1 newlines. Stopping a chunk early would return n-1 records and call it n.
      while (pos > 0 && bytesRead < ceiling && newlines <= n) {
        const want = Math.min(chunk, pos, ceiling - bytesRead);
        const buffer = Buffer.alloc(want);
        pos -= want;
        const read = await handle.read(buffer, 0, want, pos);
        if (read.bytesRead <= 0) break;
        const piece = buffer.subarray(0, read.bytesRead);
        parts.unshift(piece);
        bytesRead += read.bytesRead;
        for (const byte of piece) if (byte === 0x0a) newlines += 1;
      }

      // Decode ONCE, after assembly: a backwards read splits a multi-byte character across a chunk
      // boundary, and decoding per chunk turns it into U+FFFD.
      const lines = Buffer.concat(parts).toString("utf8").split("\n");
      if (pos > 0) lines.shift();                 // a fragment whose beginning was never read
      const records = [];
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          records.push(JSON.parse(line));
        } catch {
          // A torn record, or something a foreign writer left. Expected; dropped.
        }
      }
      // `truncated` answers the operator's question — "am I seeing everything?" — not the loop's.
      // The scan reaching the start of a small file does NOT make the view complete: asking for the
      // last 2 of 5 records omits 3. Both causes are truncation.
      return { records: records.slice(-n), truncated: pos > 0 || records.length > n, bytesRead, size };
    } finally {
      try {
        await handle.close();
      } catch {
        // A close that fails has nothing left to protect.
      }
    }
  } catch {
    return empty;
  }
}

/**
 * The last `n` records across the live file AND its generations, newest last (vibe-266).
 *
 * Returns `{ records, truncated, bytesRead, generations, liveSize, atCapacity }`. The live file is
 * read first, then generations newest-first — by their names' rotation timestamps, which is display
 * order and no claim of sequence (property 5) — each with the ceiling and count that remain, so the
 * `ceiling` is a TOTAL: a log with many generations is not many ceilings. `truncated` is true when any
 * file's scan was cut short, when generations were left unread, or when more records exist than were
 * asked for.
 *
 * **`atCapacity` and `generations` come from the same judgment admission uses** — `judgeGenerationsAt`
 * with the same shape, the same eligibility delay and the same six clauses — never from a count of
 * names: a name count would call a log "at capacity" while the next emit was about to retire an aged
 * generation and admit the record. The reader is the only place the at-capacity refusal can be made
 * visible, since a full log cannot record its own refusal.
 */
export async function tailEventLog(workspace, n, options = {}) {
  const { ceiling = EVENT_LOG_TAIL_MAX_BYTES, chunk = READ_CHUNK, now = Date.now() } = options;
  const dir = path.join(workspace, STATE_DIRNAME);
  let names = [];
  try {
    names = await readdir(dir);
  } catch {
    names = [];
  }
  const generations = names.filter((name) => GENERATION_SHAPE.test(name)).sort().reverse();

  const live = await tailRecords(eventLogPath(workspace), n, { ceiling, chunk });
  let records = live.records;
  let bytesRead = live.bytesRead;
  let truncated = live.truncated;
  let unread = generations.length;
  for (const name of generations) {
    if (records.length >= n || bytesRead >= ceiling) break;
    const older = await tailRecords(path.join(dir, name), n - records.length,
      { ceiling: ceiling - bytesRead, chunk });
    records = [...older.records, ...records];
    bytesRead += older.bytesRead;
    truncated = truncated || older.truncated;
    unread -= 1;
  }
  if (unread > 0) truncated = true;

  let judged = { eligible: [], kept: 0, refused: [] };
  try {
    judged = await judgeGenerationsAt(workspace, STATE_DIRNAME,
      { shape: GENERATION_SHAPE, olderThanMs: EVENT_LOG_ELIGIBILITY_MS, now });
  } catch {
    // an unjudgeable directory reports no generations and no capacity
  }
  return {
    records, truncated, bytesRead,
    generations: judged.kept,
    liveSize: live.size,
    atCapacity: judged.kept >= EVENT_LOG_MAX_GENERATIONS && live.size >= EVENT_LOG_ROTATE_BYTES,
  };
}
