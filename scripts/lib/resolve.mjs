// SPDX-License-Identifier: ISC
// Job resolution and the cancel lifecycle for /vibe-suite:jobs (E1.2 / vibe-12, implements F2.5).
//
// Independently written for this repo (D7): F2.5 names `resolveResultJob`/`resolveCancelableJob` as
// a contract, and the semantics are defined here — which job a bare `cancel` means, what `result`
// does for an unfinished job — then pinned by tests and documented in `commands/jobs.md`.
//
// ## Cancel is a lifecycle, not a signal
//
// The order is the whole design (rounds 1–3 of this issue's review): **claim, then signal, then
// confirm, and the claim is the store's own CAS.** `finaliseRecord` transitions to `cancelled` only
// if the record is still non-terminal; a competing completion races the same CAS, so exactly one
// verdict ever commits. A lost claim means the job finished first — that is a result to report, not
// a failure, and above all NOT a reason to signal: no signal is ever sent without first owning the
// terminal state. What remains after the claim is pid reuse — the dying group's pgid recycled to an
// unrelated process between claim and signal. Node has no pidfd-shaped answer to that; the window
// is narrowed by the validator's handle invariants and a liveness probe, and is documented in the
// command artifact as an accepted residual rather than papered over.
//
// Effects are injected (`signalGroup`, `sleep`) as ordinary parameters: the Node 18 floor has no
// module mocking, and the unit tests must prove "no signal" by inspecting a recorder, not by hoping.

import { signalGroup as realSignalGroup } from "./process.mjs";
import {
  finaliseRecord, isAbandoned, isValidJobId, listRecords, readRecord, validateRecord,
  TERMINAL_STATUSES,
} from "./jobs.mjs";

export const CANCEL_GRACE_MS = 2000;
export const CANCEL_REAP_DEADLINE_MS = 15_000;
export const CANCEL_POLL_MS = 50;

/**
 * Resolution failure with a machine-readable `code`:
 * `usage` (bad invocation — exit 2) · `not-found` · `invalid` (failed validation) ·
 * `none` (nothing to cancel) · `ambiguous` (several candidates) — all exit 1.
 */
export class ResolveError extends Error {
  constructor(message, code) {
    super(message);
    this.code = code;
  }
}

/**
 * Load one record safely: id shape BEFORE any filesystem access (`recordPath` interpolates the id
 * into a path), full validation after. Nothing that fails here may be rendered as healthy, settled,
 * or signalled.
 */
export async function loadValidated(workspace, jobId) {
  if (!isValidJobId(jobId)) {
    throw new ResolveError(`invalid job id '${jobId}' — expected job_<20 hex chars>`, "usage");
  }
  let record;
  try {
    record = await readRecord(workspace, jobId);
  } catch (error) {
    throw new ResolveError(`job ${jobId} not found: ${error?.message ?? error}`, "not-found");
  }
  const verdict = validateRecord(record, jobId);
  if (!verdict.ok) {
    throw new ResolveError(`job ${jobId}: invalid record (${verdict.reason})`, "invalid");
  }
  return record;
}

/** `status` scope: one job by id, non-terminal by default, everything with `all`. */
export async function resolveStatusJobs(workspace, { jobId = null, all = false } = {}) {
  if (jobId !== null) {
    return { records: [await loadValidated(workspace, jobId)], invalid: [] };
  }
  const { records, invalid } = await listRecords(workspace);
  return { records: all ? records : records.filter((r) => !TERMINAL_STATUSES.has(r.status)), invalid };
}

/** `result` names its job explicitly — a "latest result" default would reward guessing. */
export async function resolveResultJob(workspace, jobId) {
  if (jobId === null || jobId === undefined) {
    throw new ResolveError("result requires a job id (see: status --all)", "usage");
  }
  return loadValidated(workspace, jobId);
}

/**
 * `cancel <id>` resolves that record even when terminal — the claim step turns "already finished"
 * into a report instead of an error. Bare `cancel` targets the single running background job, and
 * refuses to guess between several: cancelling the wrong long job is expensive precisely when
 * several are running.
 */
export async function resolveCancelableJob(workspace, jobId = null) {
  if (jobId !== null) return loadValidated(workspace, jobId);
  const { records } = await listRecords(workspace);
  const candidates = records.filter((r) => !TERMINAL_STATUSES.has(r.status) && r.background);
  if (candidates.length === 0) {
    throw new ResolveError("nothing to cancel: no running background job", "none");
  }
  if (candidates.length > 1) {
    throw new ResolveError(
      `multiple running background jobs — pass a job id: ${candidates.map((r) => r.jobId).join(", ")}`,
      "ambiguous");
  }
  return candidates[0];
}

async function pollGone(signalGroup, sleep, pgid, deadlineMs, pollMs) {
  const rounds = Math.max(1, Math.ceil(deadlineMs / pollMs));
  for (let i = 0; i < rounds; i += 1) {
    if (!signalGroup(pgid, 0)) return true;
    await sleep(pollMs);
  }
  return !signalGroup(pgid, 0);
}

/**
 * The cancel lifecycle. Returns one of:
 *   `{ outcome: "already-terminal", record }` — the job finished first; its verdict is reported.
 *   `{ outcome: "cancelled", record, signalled, groupDead }` — verdict owned; `groupDead: false`
 *     means escalation ran but the group outlived the reap deadline — surfaced, never hidden.
 *
 * `deps` are the injected effects: `signalGroup`, `sleep`, the poll knobs, and `onResolved` — a
 * documented test seam (same species as `VIBE_SUITE_CODEX_BIN`) that runs between resolve and
 * claim, where the completion-vs-cancel race lives.
 */
export async function cancelJob(workspace, jobId = null, deps = {}) {
  const {
    signalGroup = realSignalGroup,
    sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    graceMs = CANCEL_GRACE_MS,
    reapDeadlineMs = CANCEL_REAP_DEADLINE_MS,
    pollMs = CANCEL_POLL_MS,
    onResolved = null,
  } = deps;

  const record = await resolveCancelableJob(workspace, jobId);
  if (onResolved) await onResolved(record);

  if (TERMINAL_STATUSES.has(record.status)) {
    return { outcome: "already-terminal", record };
  }

  // The claim. Winning this CAS — not any later check — is what authorises a signal.
  const claimed = await finaliseRecord(workspace, record.jobId, {
    status: "cancelled", error: "cancelled by operator",
  });
  if (claimed === null) {
    return { outcome: "already-terminal", record: await readRecord(workspace, record.jobId) };
  }

  const pgid = claimed.pgid;
  if (pgid === null || !signalGroup(pgid, 0)) {
    // Foreground record, never-claimed worker, or a group already gone (e.g. abandoned): the
    // verdict alone is the whole cancel.
    return { outcome: "cancelled", record: claimed, signalled: false, groupDead: true };
  }

  // Group-wide escalation, the runner's own recovery shape: SIGTERM asks; a fixture-grade stubborn
  // child ignores it; SIGKILL cannot be refused; only the group actually disappearing counts.
  signalGroup(pgid, "SIGTERM");
  const gentle = await pollGone(signalGroup, sleep, pgid, graceMs, pollMs);
  if (!gentle) signalGroup(pgid, "SIGKILL");
  const groupDead = gentle || await pollGone(signalGroup, sleep, pgid, reapDeadlineMs, pollMs);
  return { outcome: "cancelled", record: claimed, signalled: true, groupDead };
}

/**
 * The reaping policy E1.1 left to this command (`isAbandoned` reports; this settles): a background
 * job whose heartbeat went stale and whose worker is dead is finalised `failed`. Invoked ONLY by
 * the explicit `--settle-abandoned` flag — display never mutates. The CAS guard means a worker that
 * was merely slow and finalises concurrently keeps its real verdict.
 */
export async function settleAbandoned(workspace, records, { now = Date.now() } = {}) {
  const settled = [];
  for (const record of records) {
    if (!isAbandoned(record, { now })) continue;
    const done = await finaliseRecord(workspace, record.jobId, {
      status: "failed", error: "abandoned: heartbeat stale, worker dead",
    });
    if (done) settled.push(done);
  }
  return settled;
}

/** Display-only abandonment scan for `status`. */
export function abandonedIds(records, { now = Date.now() } = {}) {
  return new Set(records.filter((record) => isAbandoned(record, { now })).map((r) => r.jobId));
}
