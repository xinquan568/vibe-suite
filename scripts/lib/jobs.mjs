// SPDX-License-Identifier: ISC
// The job record store (E1.1 / vibe-11).
//
// Records live at `<workspace>/.vibe-suite-state/jobs/<jobId>.json` — one file per job, beside the
// toggle store's `state.json`, never inside it. `/vibe-suite:jobs` (#12) and the agy runner (#17)
// both read this layout, so the schema below is a shared contract, not an implementation detail.
//
// ## Why there is no lock
//
// Three lock designs were tried and each produced a race: a `mkdir` lock with mtime staleness could
// evict a live-but-delayed holder; an exclusive-create lock with rename-to-break left an ownerless
// window on crash and could ABA a successor. The defect was the lock itself — **any lock that can be
// broken needs a protocol to decide who may break it, and that decision is the race.**
//
// So this store does not lock. Writes are an optimistic compare-and-swap on a monotonically
// increasing `version`, made atomic by the filesystem:
//
//   read canonical (version N) -> run the updater -> write candidate to a unique temp
//   -> link(temp, <jobId>.v<N+1>)   <- the CAS: atomic, fails EEXIST, exactly one writer wins,
//                                      and the slot is published WITH its content already present
//   -> rename(<jobId>.v<N+1>, <jobId>.json)   <- the commit
//
// **A crash between `link` and `rename` is recoverable by anyone.** The next writer finds the slot
// taken with the canonical still at N, and *completes* the rename rather than deleting the slot.
// Deleting would race a merely-paused winner and re-create ABA; completing cannot, because `link`
// guarantees the content was whole before the slot became visible. The design's rule, learned the
// expensive way: **make the dangerous operation recoverable instead of deciding who may perform it.**
//
// `rename` removes its source, so a concurrent mover gets ENOENT. That is not a failure: re-read the
// canonical record, and a version at or past the target proves the transition committed.
//
// ## Nullability differs deliberately from the toggle store
//
// `store.py` documents that an unset key is *absent* rather than null, because there absence means
// "the default applies" — a real tri-state. A job record has no defaults to fall back on, so every
// key is always present and unavailable values are `null`: `threadId: null` means "no thread id
// exists yet", which is information.

import { createHash, randomBytes, randomUUID } from "node:crypto";
import { link, mkdir, readdir, readFile, rename, stat, unlink, writeFile } from "node:fs/promises";
import path from "node:path";

export const STATE_DIRNAME = ".vibe-suite-state";

/** The four keys of the one-line result contract, in contract order. */
export const RESULT_KEYS = ["jobId", "status", "threadId", "rawOutput"];

/** Terminal statuses. `cancelled` is reserved for #12, which signals via `pgid`. */
export const TERMINAL_STATUSES = new Set(["completed", "failed", "timed_out", "cancelled"]);

/**
 * An orphan temp may be reaped only past this age — set far above any possible interval between
 * creating a temp and linking it, so reaping can never race a writer about to link. A version slot
 * is never reaped at any age; see the header.
 */
export const TEMP_REAP_MIN_AGE_MS = 6 * 60 * 60 * 1000;

/** Signals an updater declined the transition. */
export const REJECT = Symbol("reject");

export class JobStoreError extends Error {}

const isTerminal = (record) => TERMINAL_STATUSES.has(record.status);

export function newJobId() {
  return `job_${randomUUID().replace(/-/g, "").slice(0, 20)}`;
}

export function jobsDir(workspace) {
  return path.join(workspace, STATE_DIRNAME, "jobs");
}

export function recordPath(workspace, jobId) {
  return path.join(jobsDir(workspace), `${jobId}.json`);
}

function slotPath(workspace, jobId, version) {
  return path.join(jobsDir(workspace), `${jobId}.v${version}.json`);
}

export function hashToken(token) {
  return createHash("sha256").update(String(token)).digest("hex");
}

export function newClaimToken() {
  return randomBytes(32).toString("hex");
}

/** A fresh record. Every field is present; unknown values are explicitly null. */
export function newRecord({ jobId, kind, sandbox, effort, model, background, timeoutMs, claimDigest }) {
  const now = new Date().toISOString();
  return {
    jobId,
    version: 1,
    kind,
    status: "running",
    sandbox,
    effort,
    model: model ?? null,          // P9: null means the CLI's own default ran
    background: Boolean(background),
    threadId: null,
    workerPid: null,
    pgid: null,                    // non-null only for background: the detached worker leads its group
    claimDigest: claimDigest ?? null,
    createdAt: now,
    startedAt: null,
    endedAt: null,
    updatedAt: now,
    heartbeatAt: null,
    timeoutMs: timeoutMs ?? null,
    exitCode: null,
    rawOutput: null,
    error: null,
    tokens: null,
  };
}

async function readCanonical(workspace, jobId) {
  const raw = await readFile(recordPath(workspace, jobId), "utf8");
  const parsed = JSON.parse(raw);
  if (typeof parsed?.version !== "number") {
    throw new JobStoreError(`${recordPath(workspace, jobId)}: record has no version`);
  }
  return parsed;
}

export async function readRecord(workspace, jobId) {
  return readCanonical(workspace, jobId);
}

/**
 * Complete an uncommitted slot left by a writer that died between `link` and `rename`.
 *
 * Only valid, protocol-produced slots are rolled forward. A slot that does not parse, or whose
 * version is not the one expected, is neither completed nor deleted — it is reported, because
 * converting a liveness stall into a silent integrity error is the worse trade. Recovery reads only
 * linked slots, never temps: an incomplete temp never becomes a slot.
 */
async function rollForward(workspace, jobId, version) {
  const slot = slotPath(workspace, jobId, version);
  let candidate;
  try {
    candidate = JSON.parse(await readFile(slot, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return;                       // someone completed it already
    throw new JobStoreError(
      `${slot}: uncommitted slot is unreadable (${error.message}). It is NOT deleted automatically. ` +
      `Repair: quiesce writers for this job, then move the slot aside.`);
  }
  if (candidate?.version !== version || candidate?.jobId !== jobId) {
    throw new JobStoreError(
      `${slot}: uncommitted slot is malformed (version/jobId mismatch). It is NOT deleted ` +
      `automatically. Repair: quiesce writers for this job, then move the slot aside.`);
  }
  await commit(workspace, jobId, version);
}

/**
 * Commit a claimed slot by publishing its content to the canonical path.
 *
 * **The slot is retained, never renamed away.** Renaming it would free the `v<N+1>` pathname, and a
 * delayed writer still holding a stale read at `N` could then claim that same version again and
 * publish its obsolete candidate over a newer record — including over a terminal one. Keeping the
 * slot makes `link` fail `EEXIST` for that version forever, so a stale writer is always forced back
 * through a fresh read. Slots are part of the "never deleted" rule for the same reason.
 *
 * Publication is temp + `rename`, which is atomic, and is idempotent by content: whoever performs it
 * writes the same bytes, so a winner and a recoverer racing produces one outcome.
 */
async function commit(workspace, jobId, version) {
  let content;
  try {
    content = await readFile(slotPath(workspace, jobId, version), "utf8");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    const current = await readCanonical(workspace, jobId).catch(() => null);
    if (current && current.version >= version) return true;      // already published by someone
    throw new JobStoreError(
      `${jobId}: version ${version} slot vanished without being committed (canonical is ` +
      `${current ? current.version : "unreadable"})`);
  }

  const current = await readCanonical(workspace, jobId).catch(() => null);
  if (current && current.version >= version) return true;        // a newer record already stands

  const staging = path.join(jobsDir(workspace),
    `${jobId}.pub.${process.pid}.${randomBytes(6).toString("hex")}`);
  await writeFile(staging, content, "utf8");
  await rename(staging, recordPath(workspace, jobId));
  return true;
}

/**
 * Apply `updater` to the record under compare-and-swap.
 *
 * `updater` must be **pure**: it is re-run in full against every freshly read record, so a claim or
 * heartbeat that lands mid-flight cannot be overwritten by a decision made before it existed. Return
 * `REJECT` to decline. Returns the committed record.
 */
export async function transact(workspace, jobId, updater, { attempts = 50 } = {}) {
  await mkdir(jobsDir(workspace), { recursive: true });

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const current = await readCanonical(workspace, jobId);
    // The terminal rule is an invariant of the store, not a courtesy of its callers. Enforcing it
    // only in the wrappers left `transact` itself able to reopen a finished job — which a test
    // exercising roll-forward did, and passed, because it only checked the version.
    if (isTerminal(current)) return null;
    const next = updater(current);
    if (next === REJECT) return null;

    const target = current.version + 1;
    const candidate = { ...next, version: target, updatedAt: new Date().toISOString() };
    const temp = path.join(jobsDir(workspace),
      `${jobId}.tmp.${process.pid}.${randomBytes(6).toString("hex")}`);
    await writeFile(temp, JSON.stringify(candidate, null, 2) + "\n", "utf8");

    try {
      await link(temp, slotPath(workspace, jobId, target));    // the CAS
      await unlink(temp);                                       // the slot is now the surviving link
      await commit(workspace, jobId, target);
      return candidate;
    } catch (error) {
      await unlink(temp).catch(() => {});
      if (error.code !== "EEXIST") throw error;

      // Someone else holds this version. Either they committed it, or they died before committing.
      const now = await readCanonical(workspace, jobId).catch(() => null);
      if (!now || now.version < target) await rollForward(workspace, jobId, target);
      // Either way, loop: re-read and re-run the updater against the new state.
    }
  }
  throw new JobStoreError(`${jobId}: gave up after ${attempts} contended attempts`);
}

/** Create the initial record. Distinct from `transact` because there is nothing to compare against. */
export async function createRecord(workspace, record) {
  await mkdir(jobsDir(workspace), { recursive: true });
  const target = recordPath(workspace, record.jobId);
  const temp = `${target}.tmp.${process.pid}.${randomBytes(6).toString("hex")}`;
  await writeFile(temp, JSON.stringify(record, null, 2) + "\n", "utf8");
  try {
    await link(temp, target);
  } catch (error) {
    await unlink(temp).catch(() => {});
    if (error.code === "EEXIST") throw new JobStoreError(`${record.jobId}: record already exists`);
    throw error;
  }
  await unlink(temp).catch(() => {});
  return record;
}

/** Patch fields. `transact` already refuses to leave a terminal state. */
export function updateRecord(workspace, jobId, patch) {
  return transact(workspace, jobId, (record) => ({ ...record, ...patch }));
}

/** Finalise. Returns null if already terminal, so a late writer cannot replace a verdict. */
export function finaliseRecord(workspace, jobId, patch) {
  return transact(workspace, jobId, (record) => ({
    ...record, ...patch, endedAt: patch.endedAt ?? new Date().toISOString(),
  }));
}

/**
 * Claim a job for a worker, presenting the one-time token.
 *
 * The authorisation is the token, **not** a field of the record: record data cannot be its own
 * authorization. The digest is cleared on success, so a replayed command line cannot re-claim.
 *
 * **This is an operator-deliberation interlock, not a privilege boundary.** It establishes that this
 * worker was launched by a launcher that performed confirmation in this invocation — defeating
 * replay, stale records and re-entry bugs. It does not defend against an operator who forges a record
 * and its token, because that principal can already run `codex` directly. Claiming otherwise would be
 * this repository's recurring defect: trusting a value a different actor controls when it matters.
 */
export function claimWith(workspace, jobId, token) {
  const presented = hashToken(token);
  return transact(workspace, jobId, (record) => {
    if (isTerminal(record)) return REJECT;
    if (record.workerPid !== null) return REJECT;                       // already claimed
    if (!record.claimDigest || record.claimDigest !== presented) return REJECT;
    const now = new Date().toISOString();
    return {
      ...record,
      claimDigest: null,                                                // one-time: consumed
      workerPid: process.pid,
      // `detached: true` makes the worker a process-group leader, so its pgid equals its pid. This is
      // correct by construction, not by measurement — Node exposes no getpgrp.
      pgid: process.pid,
      startedAt: now,
      heartbeatAt: now,          // a baseline from the first moment, so staleness is measurable
    };
  });
}

/**
 * Whether a background job looks abandoned.
 *
 * E1.1 **reports**; it never rewrites a record it does not own. Reaping policy belongs to
 * `/vibe-suite:jobs` (#12). Consumers must check `status` before signalling `pgid`.
 */
export function isAbandoned(record, { now = Date.now(), heartbeatMs = 30_000 } = {}) {
  if (!record.background || isTerminal(record)) return false;
  if (record.heartbeatAt === null) return false;
  if (now - Date.parse(record.heartbeatAt) <= heartbeatMs * 3) return false;
  if (typeof record.workerPid === "number") {
    try {
      process.kill(record.workerPid, 0);
      return false;                                                     // still alive
    } catch (error) {
      if (error.code === "EPERM") return false;                         // alive, not ours to signal
    }
  }
  return true;
}

/** The result line: exactly the four contract keys, in contract order. */
export function resultLine(record) {
  return JSON.stringify(Object.fromEntries(RESULT_KEYS.map((key) => [key, record[key] ?? null])));
}

/**
 * Reap orphan temps only. **Version slots are never deleted, at any age** — an uncommitted slot is
 * recoverable protocol state, and deleting it is the ABA race this design exists to remove.
 */
export async function reapOrphanTemps(workspace, { now = Date.now() } = {}) {
  const dir = jobsDir(workspace);
  let names;
  try {
    names = await readdir(dir);
  } catch {
    return 0;
  }
  let reaped = 0;
  for (const name of names) {
    if (!name.includes(".tmp.") && !name.includes(".pub.")) continue;   // never a .vN slot
    const full = path.join(dir, name);
    try {
      const info = await stat(full);
      if (now - info.mtimeMs < TEMP_REAP_MIN_AGE_MS) continue;          // when in doubt, leave it
      await unlink(full);
      reaped += 1;
    } catch {
      // A temp that vanished or cannot be stat'd is left alone.
    }
  }
  return reaped;
}
