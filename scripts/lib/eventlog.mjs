// SPDX-License-Identifier: ISC
// The suite's own append-only event log (vibe-207 / grill M5).
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
//   4. Destruction unrelated to retention is unacceptable. **There is no delete, rename or sweep in
//      this module at all**, which is the whole reason it is small.
//   5. No total order is guaranteed. `ts` is metadata, not a sequence: records from different
//      processes interleave, and a reader that infers causality from adjacency will be wrong.
//
// Property 3 — bounded retention with a content-age floor — is **#266**. `EVENT_LOG_MAX_BYTES` is
// defined here and measured against by `jobs log`, but **nothing in this module trims**. Until #266
// lands the log grows without bound; that is an accepted, declared liability, and a notice is not a
// cap.

import path from "node:path";

import { appendLineAt, ensureDirAt, secureDirAt, EVENT_LINE_MAX } from "./write.mjs";

/**
 * The state directory's name, declared here rather than imported from `jobs.mjs`.
 *
 * `jobs.mjs` imports this module to emit, so importing it back would close a cycle. The duplication
 * is made safe by a test that pins the two equal — a guard, not a hope.
 */
export const STATE_DIRNAME = ".vibe-suite-state";

/** The log's name inside the state directory. */
export const EVENT_LOG_NAME = "events.log";

/**
 * The size past which `jobs log` says the log is oversized.
 *
 * **Measured against, never enforced.** Nothing here trims: bounded retention under concurrent
 * writers is #266, and five designs for it were rejected before the mechanism was split out. What
 * this constant buys today is that the operator is told, which is strictly better than silence and
 * strictly worse than a cap.
 */
export const EVENT_LOG_MAX_BYTES = 8 * 1024 * 1024;

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

/**
 * Append one record to the workspace's event log. **Never throws, never rejects.**
 *
 * Returns `true` when a record reached the log and `false` for every other outcome — an
 * unserialisable detail, a directory at the log path, a workspace that is not there, a state
 * directory that is a file, a log another uid owns. The caller is not expected to look: property 1
 * says the operation being observed must run identically either way, and a call site that branched
 * on this would be the first step toward observability that can fail its own caller.
 */
export async function emit(workspace, { component, event, jobId = null, detail = {} } = {}) {
  try {
    const record = { ts: new Date().toISOString(), component, event };
    // Absent, not null: a null `jobId` would read as "this event had no job", which is a different
    // claim from "a job id does not apply to this kind of event".
    if (jobId !== null && jobId !== undefined) record.jobId = jobId;
    record.detail = detail;

    const fitted = fit(record);              // throws on a circular detail — caught below, as intended
    if (fitted === null) return false;

    await ensureDirAt(workspace, STATE_DIRNAME);
    await secureDirAt(workspace, STATE_DIRNAME);
    await appendLineAt(workspace, path.join(STATE_DIRNAME, EVENT_LOG_NAME), JSON.stringify(fitted));
    return true;
  } catch {
    return false;
  }
}
