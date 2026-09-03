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
// ## What is deleted, and when (vibe-204)
//
// **A slot of a non-terminal job is never deleted**, and neither is any job's top slot: they are the
// CAS protocol state above. Once a record is TERMINAL its history below the top slot is committed
// and is compacted away at that commit (`compactSlots`), leaving canonical + one slot; a terminal
// job old enough is deleted whole by `pruneTerminalJobs` — an explicit operator action, never a
// hook. Two consequences are handled explicitly rather than assumed away:
//
//   * Freeing a version means a won `link` no longer proves first claim, so `commit` **confirms**
//     every win before publishing — against the job's highest OTHER slot (the retained top is the
//     authority; the canonical can be lowered by a paused publisher) and against the canonical.
//   * `rename` onto the canonical path cannot be made conditional, so a publisher paused between
//     confirming and renaming could recreate a canonical after prune deleted it. Prune therefore
//     leaves a **tombstone: a 0700 directory at the canonical path**, holding this store's stamp
//     for the job, staged elsewhere and renamed into place atomically so it never exists without
//     that provenance. `rename(file, dir)` fails `EISDIR`, `publishNew` refuses a directory, every
//     read reports the job gone — the late publication fails instead of resurrecting the job.
//     Tombstones expire after `PRUNE_TOMBSTONE_TTL_MS`; a publisher paused longer than that is the
//     declared boundary. A directory WITHOUT that provenance is foreign: never accepted as a
//     tombstone, never expired, reported.
//   * The tombstone cannot be created while the canonical file occupies its path, so entombing is
//     two steps with a crash window between them. Prune therefore first publishes a durable
//     **marker** (`<jobId>.pruning`, stamped) — *before* it unlinks anything — and removes it only
//     after the tombstone stands and the slots are gone. Every later prune completes an interrupted
//     one from its marker, readers and `commit` treat a validly marked job as gone, and
//     `createRecord` refuses a marked or entombed id: the deletion is durable from the marker on,
//     whatever crashes after it. Authority is never a name — a marker counts only with this store's
//     stamp for that job id, read without following symlinks — and two prunes may race: a removal
//     that finds nothing is a lost race, never a refusal, so a shared marker is never withdrawn by
//     the loser. The marker names the record INCARNATION it commits to delete — the `incarnation`
//     the record was minted with, because an id can be lived twice and two creations in one
//     millisecond share a `createdAt` — and that identity is applied BY the unlink, on the document
//     that call reads through its own handle, not by an earlier call whose answer a later mutation
//     inherits. A record published in the gap is a different life and is refused, not deleted.
//     `createRecord` re-checks the marker AFTER publishing and proves ITS OWN record still stands at
//     the canonical path: the marker is the linearisation point, a creation that lost to it
//     withdraws exactly what it published, and a creation whose record no longer stands is never
//     reported as landed. The marker also opens a deletion ATTEMPT, and the tombstone carries the
//     attempt it was installed under, so any prune adopting a marker can tell "the deletion I am
//     completing reached its tombstone" from "this job was already deleted, and reported, under a
//     different attempt, and this marker was published over the result" — the second, read as the
//     first, would give an already-reported job a second line in a later run.
//   * Removal of a directory of ours (an expired tombstone) VACATES the path first, in one atomic
//     rename to a staging name, and is taken apart there. A concurrent prune therefore sees the
//     tombstone whole or an absent path — never a directory of ours stripped of the provenance that
//     would let it be proven, which is the one state a peer could neither finish nor honestly
//     report. A crash inside the staging name leaves an EMPTY directory, and an empty directory
//     wearing the staging shape, past the reap age, is removed by `rmdir` alone — the one removal
//     that cannot destroy anything, since `rmdir` refuses a directory that holds so much as one
//     entry.
//
// **The canonical is the job**: with no canonical (or a tombstone) there is no job, and a slot beside
// that gap is a stale writer's orphan — removed by the writer itself when it learns the job is
// gone, or by prune's sweep.
//
// ## Nullability differs deliberately from the toggle store
//
// `store.py` documents that an unset key is *absent* rather than null, because there absence means
// "the default applies" — a real tri-state. A job record has no defaults to fall back on, so every
// key is always present and unavailable values are `null`: `threadId: null` means "no thread id
// exists yet", which is information.

import { createHash, randomBytes, randomUUID } from "node:crypto";
// Only the read side is imported directly: every mutation goes through `./write.mjs`, and an
// unused raw mutator binding is a capability kept for no reason (vibe-103).
import { lstat, readdir, readFile } from "node:fs/promises";

import {
  assertInside, assertRoot, classify, ensureDirAt, publishDirAt, publishNew, readOwned,
  removeEmptyDirAt, removeOwnedDirAt, secureDirAt, unlinkOwned, writeAtomic, openSinkAt,
  PRIVATE_FILE_MODE, STAMP_KEY,
} from "./write.mjs";
import { randomBytes as tombstoneNonce } from "node:crypto";
import path from "node:path";

export const STATE_DIRNAME = ".vibe-suite-state";

/** The five keys of the one-line result contract, in contract order.
 *
 * `verdictState` was **appended** rather than inserted (vibe-46): four assertions compare
 * `Object.keys(...)` with `deepEqual`, so position is part of this contract, not a detail.
 * `verdictText` is deliberately absent — the event stream in `rawOutput` already carries the agent
 * message, and putting it here would ship the same content twice in one record.
 */
export const RESULT_KEYS = ["jobId", "status", "threadId", "rawOutput", "verdictState"];

/** Terminal statuses. `cancelled` is reserved for #12, which signals via `pgid`. */
export const TERMINAL_STATUSES = new Set(["completed", "failed", "timed_out", "cancelled"]);

/**
 * An orphan temp may be reaped only past this age — set far above any possible interval between
 * creating a temp and linking it, so reaping can never race a writer about to link. The temp reaper
 * never touches a version slot at any age; slots of a TERMINAL job go at compaction and at prune —
 * see the header.
 */
export const TEMP_REAP_MIN_AGE_MS = 6 * 60 * 60 * 1000;

/** Signals an updater declined the transition. */
export const REJECT = Symbol("reject");

export class JobStoreError extends Error {}

const isTerminal = (record) => TERMINAL_STATUSES.has(record.status);

export function newJobId() {
  return `job_${randomUUID().replace(/-/g, "").slice(0, 20)}`;
}

/**
 * The canonical id shape `newJobId` produces. Consumers validate BEFORE any filesystem access:
 * `recordPath` interpolates the id into a path, so an unvalidated operator-supplied id is a
 * traversal vector (E1.2 / vibe-12).
 */
export const JOB_ID_RE = /^job_[0-9a-f]{20}$/;

export function isValidJobId(id) {
  return typeof id === "string" && JOB_ID_RE.test(id);
}

export function jobsDir(workspace) {
  return path.join(workspace, STATE_DIRNAME, "jobs");
}

/**
 * The background worker's own stderr sink (vibe-182 / grill H7): `<jobId>.log` beside the record,
 * 0600, opened by the launcher before the spawn. Not a record, not a slot, not a scratch temp — the
 * reaper's candidate rule (`isReapCandidate`) never matches it and `listRecords` never reads it.
 */
export function workerLogPath(workspace, jobId) {
  return path.join(jobsDir(workspace), `${jobId}.log`);
}

/**
 * Spawn the worker with a private log as its stderr (vibe-182 / grill H7) — the whole sink lifecycle
 * in one testable place. `spawnWith(stderr)` receives the sink's descriptor (or `"ignore"`) and
 * returns the child. The sink is opened through the audited primitive; the launcher's handle is
 * closed as soon as `spawnWith` returns (or throws) — the child holds its own descriptor from the
 * spawn. A sink that cannot be opened degrades to `"ignore"` and is reported in `warning` rather
 * than failing a launch over its diagnostics. Returns `{ child, logPath, warning }`.
 */
export async function withWorkerSink(workspace, jobId, spawnWith) {
  const logPath = workerLogPath(workspace, jobId);
  let sink = null;
  let warning = null;
  try {
    sink = await openSinkAt(jobsDir(workspace), logPath);
  } catch (error) {
    warning = `worker log unavailable for ${jobId} (${String(error?.message ?? error)}); the worker's stderr is discarded`;
  }
  try {
    const child = spawnWith(sink ? sink.fd : "ignore");
    return { child, logPath: sink ? logPath : null, warning };
  } finally {
    if (sink) await sink.close().catch(() => {});
  }
}

export function recordPath(workspace, jobId) {
  return path.join(jobsDir(workspace), `${jobId}.json`);
}

function slotPath(workspace, jobId, version) {
  return path.join(jobsDir(workspace), `${jobId}.v${version}.json`);
}

/**
 * The prune marker (vibe-204): `<jobId>.pruning`, a stamped file published BEFORE the canonical is
 * touched, removed only once the tombstone stands and the slots are gone. Its presence means "this
 * job is being deleted": `commit` reports the job gone, `createRecord` refuses the id, and the next
 * prune finishes the job. Not a record (`listRecords` enumerates `<jobId>.json` only), not a slot,
 * not a scratch temp (the reaper's candidate rule never matches it).
 */
const PRUNE_MARKER_KIND = "job-prune-marker";
/** The tombstone's provenance: a stamped file INSIDE the tombstone directory, put there before the
 * directory is renamed into place, so no directory of ours ever exists without it. */
const TOMBSTONE_KIND = "job-tombstone";
const TOMBSTONE_STAMP = ".vibe-suite-tombstone";
const STAGING_NAME = /^\.tomb\.[0-9a-f]{12}\.vibe-tmp$/;

function markerName(jobId) {
  return `${jobId}.pruning`;
}

function markerPath(workspace, jobId) {
  return path.join(jobsDir(workspace), markerName(jobId));
}

/**
 * What stands at a job's marker path: `{ state, doc }` with `state` one of `absent`, `valid` (a
 * regular file — never a symlink, never a directory — carrying this store's marker stamp for THIS
 * job id and the identity of the record it commits to delete), or `foreign` (anything else). Read
 * through `readOwned`, which opens without following and checks the file type through the handle.
 * A name is not authority, and neither is what a name points at.
 */
async function inspectMarker(dir, jobId) {
  const kind = await classify(path.join(dir, markerName(jobId)));
  if (kind === "absent") return { state: "absent", doc: null };
  if (kind !== "file") return { state: "foreign", doc: null };
  const doc = await readOwned(dir, markerName(jobId), [PRUNE_MARKER_KIND]);
  if (doc === null || doc.jobId !== jobId || typeof doc.createdAt !== "string"
      || !(doc.incarnation === null || doc.incarnation === undefined || isIncarnation(doc.incarnation))) {
    return { state: "foreign", doc: null };
  }
  return { state: "valid", doc };
}

/**
 * The DELETION ATTEMPT a marker opened (vibe-204 round 6, step 3). The marker says which record is
 * being deleted; the attempt says which marker's deletion the tombstone standing at the canonical
 * path belongs to. Without it, a prune that adopts a marker cannot tell "the deletion I am
 * completing got as far as its tombstone" from "the job was already deleted by someone else's
 * attempt and this marker was published afterwards over the tombstone" — and the second case, read
 * as the first, gives an already-reported job a second line in a later run's report.
 */
const attemptOf = (doc) => (typeof doc?.attempt === "string" ? doc.attempt : null);

/** The tombstone standing at a job's canonical path, or null. */
async function tombstoneAt(dir, jobId) {
  const p = path.join(dir, `${jobId}.json`);
  if (await classify(p) !== "dir") return null;
  const doc = await readOwned(p, TOMBSTONE_STAMP, [TOMBSTONE_KIND]);
  return doc !== null && doc.jobId === jobId ? doc : null;
}

const isIncarnation = (value) => typeof value === "string" && /^[0-9a-f]{32}$/.test(value);

/**
 * The identity a deletion commits to (vibe-204 round 6): this record's `incarnation` when it has
 * one, and otherwise the `createdAt` of a record written before incarnations existed.
 */
function identityOf(doc) {
  return {
    incarnation: isIncarnation(doc?.incarnation) ? doc.incarnation : null,
    createdAt: typeof doc?.createdAt === "string" ? doc.createdAt : null,
  };
}

/**
 * Do these two identities name the same record incarnation?
 *
 * An incarnation matches only itself. A legacy identity (no incarnation) matches only another
 * legacy identity with the same `createdAt` — so a record CREATED SINCE, which always carries an
 * incarnation, can never be mistaken for the legacy record a marker judged, however the clock
 * behaved. The asymmetry is the point: the direction that must never resolve in favour of deletion
 * is "an old commitment meets a new record", and that direction is closed by construction.
 */
function sameIncarnation(a, b) {
  if (a.incarnation !== null || b.incarnation !== null) return a.incarnation === b.incarnation;
  return a.createdAt !== null && a.createdAt === b.createdAt;
}

/** The stamped record at `dir/name`, or null: read without following, regular file only. */
async function ownedRecordAt(dir, name) {
  return readOwned(dir, name, [SCRATCH_KIND]);
}

/**
 * What stands at a job's canonical path: `absent`, `file`, `tombstone` (a real directory carrying
 * our tombstone stamp for this job id), or `foreign` (a directory without that provenance, a
 * symlink, anything else). Only a `tombstone` is ever accepted as one, removed as one, or expired.
 */
async function inspectCanonicalPath(dir, jobId) {
  const p = path.join(dir, `${jobId}.json`);
  const kind = await classify(p);
  if (kind === "absent" || kind === "file") return kind;
  if (kind !== "dir") return "foreign";
  const doc = await readOwned(p, TOMBSTONE_STAMP, [TOMBSTONE_KIND]);
  return doc !== null && doc.jobId === jobId ? "tombstone" : "foreign";
}

/**
 * Remove one of our files, answering what actually happened: `removed`, `absent` (nothing there —
 * or a concurrent actor removed it first: a lost race is not a refusal), or `refused` (present but
 * not ours, or not removable). A boolean here was the round-3 blocker: a prune that lost the unlink
 * race read `false` as "not ours" and withdrew a marker two prunes shared.
 */
async function removeOwned(dir, name, kinds, predicate = null) {
  const p = path.join(dir, name);
  if (await classify(p) === "absent") return "absent";
  if (await unlinkOwned(dir, name, kinds, { predicate }).catch(() => false)) return "removed";
  return (await classify(p)) === "absent" ? "absent" : "refused";
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
    // vibe-204: this record's INCARNATION — the identity a deletion commits to. An id can be lived
    // twice (a pruned id whose tombstone expired, a caller that re-creates one), and `createdAt`
    // cannot tell the two lives apart: two creations in the same millisecond carry the same string,
    // which is exactly the collision a prune must not resolve in favour of deleting. Minted once at
    // creation and carried by every version of this record, never re-minted by an update.
    incarnation: randomBytes(16).toString("hex"),
    version: 1,
    kind,
    status: "running",
    sandbox,
    effort,
    model: model ?? null,          // P9: null means the CLI's own default ran
    background: Boolean(background),
    threadId: null,
    // vibe-46: declared at creation so a running record and an early terminal failure — a spawn
    // fault, a worker-handshake failure — satisfy the same schema as a completed one. A field that
    // only exists on the happy path is a schema the unhappy paths quietly violate.
    verdictText: null,
    verdictState: "absent",
    errorClass: null,
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
    // vibe-181: whether the engine child's stdio pipes were still held open past its exit (a
    // descendant inherited them). null until the run settles; declared here so early-terminal and
    // completed records keep one schema (the vibe-46 rule above).
    pipesLeaked: null,
    // vibe-182: what the engine said on stderr (last 8 KB, control-stripped), the signal that ended
    // it, and how many event-stream lines did not parse. null until the run settles; declared here
    // so early-terminal and completed records keep one schema (the vibe-46 rule above).
    stderrTail: null,
    signal: null,
    malformedLines: null,
  };
}

async function readPublished(workspace, jobId) {
  const raw = await readFile(recordPath(workspace, jobId), "utf8");
  const parsed = JSON.parse(raw);
  // The stamp is provenance for the reaper, not part of the record contract every consumer reads.
  delete parsed[STAMP_KEY];
  if (typeof parsed?.version !== "number") {
    throw new JobStoreError(`${recordPath(workspace, jobId)}: record has no version`);
  }
  return parsed;
}

/** The slot names of one job: `<jobId>.v<N>.json`, N captured. */
function slotPattern(jobId) {
  return new RegExp(`^${jobId.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\.v(\\d+)\\.json$`);
}

/**
 * The highest committed version slot, or null. A job's TOP slot is always retained (compaction
 * removes only what lies below it; prune removes the whole job), so this is the true high-water mark.
 */
async function highestSlot(workspace, jobId, { except = null, listing = null } = {}) {
  // vibe-205: `listing` lets a caller that has just read this directory supply what it already
  // holds, so enumerating N jobs costs one readdir instead of N. It must be EVERY entry name --
  // the loop below matches names without checking file type, so a listing filtered to files would
  // silently narrow this function's authority (a slot-shaped directory would stop counting).
  // `commit` deliberately does NOT pass one: its scan is a confirmation, and must be current.
  const names = listing ?? await readdir(jobsDir(workspace)).catch(() => []);
  const pattern = slotPattern(jobId);
  let best = null;
  for (const name of names) {
    const match = pattern.exec(name);
    if (!match) continue;
    const version = Number(match[1]);
    if (version === except) continue;
    if (best === null || version > best) best = version;
  }
  return best;
}

/**
 * Read the record, resolving the **highest committed slot** rather than trusting the published file.
 *
 * Publication (`rename` onto the canonical path) cannot be made conditional, so two writers racing
 * could in principle publish out of order and leave an older record at that path. The top slot is
 * retained and versions only increase, so the highest slot is the authority; the canonical file is a
 * convenience for external readers, and a stale one is corrected here on the next read rather than
 * being able to lose a newer — possibly terminal — record.
 *
 * **The canonical IS the job** (vibe-204). `createRecord` publishes it before any slot can exist, so
 * a missing canonical means the job was deleted (pruned); a slot found beside that gap is a stale
 * writer's orphan, never a record to resurrect. An earlier revision rebuilt the canonical from the
 * highest slot here — exactly how a pruned job would have come back.
 */
async function readCanonical(workspace, jobId, { listing = null } = {}) {
  const published = await readPublished(workspace, jobId).catch((error) => {
    if (error.code === "ENOENT" || error.code === "EISDIR") return null;   // absent, or a prune tombstone
    throw error;
  });
  if (published === null) throw new JobStoreError(`${jobId}: no record (never created, or pruned)`);
  // vibe-204: a marked job is being deleted; from the marker on it is gone to readers as well as
  // writers, so a writer looping on a fresh read stops here instead of spinning on `commit`.
  if ((await inspectMarker(jobsDir(workspace), jobId)).state === "valid") {
    throw new JobStoreError(`${jobId}: no record (pruned)`);
  }
  const top = await highestSlot(workspace, jobId, { listing });
  if (top === null || published.version >= top) return published;
  let slot;
  try {
    slot = JSON.parse(await readFile(slotPath(workspace, jobId, top), "utf8"));
  } catch (error) {
    // Same posture as rollForward: an unreadable slot blocks visibly and is never deleted, because
    // turning a stall into a silent integrity error is the worse trade.
    throw new JobStoreError(
      `${slotPath(workspace, jobId, top)}: committed slot is unreadable (${error.message}). ` +
      `It is NOT deleted automatically. Repair: quiesce writers for this job, then move it aside.`);
  }
  if (slot?.version !== top || slot?.jobId !== jobId) {
    throw new JobStoreError(
      `${slotPath(workspace, jobId, top)}: committed slot is malformed (version/jobId mismatch). ` +
      `It is NOT deleted automatically. Repair: quiesce writers for this job, then move it aside.`);
  }
  // Self-heal: republish so external readers of the canonical path converge too.
  await commit(workspace, jobId, top).catch(() => {});
  return slot;
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

/** What `commit` found when it went to publish a slot. */
const COMMIT = Object.freeze({
  PUBLISHED: "published",      // we published it
  ALREADY: "already",          // our exact bytes were already published (a recoverer rolled us forward)
  GONE: "gone",                // no canonical: the job was pruned under us
  SUPERSEDED: "superseded",    // the canonical is past this version, or at it with different bytes
});

/**
 * The canonical as bytes: `null` when it does not exist (the job is gone), otherwise `{ raw, record }`
 * with `record` null when the file is unreadable — corruption, which publishing repairs.
 */
async function readCanonicalRaw(workspace, jobId) {
  let raw;
  try {
    raw = await readFile(recordPath(workspace, jobId), "utf8");
  } catch (error) {
    if (error.code === "ENOENT" || error.code === "EISDIR") return null;   // absent, or a prune tombstone
    return { raw: null, record: null };
  }
  try {
    const parsed = JSON.parse(raw);
    return { raw, record: typeof parsed?.version === "number" ? parsed : null };
  } catch {
    return { raw, record: null };
  }
}

/**
 * Commit a claimed slot by publishing its content to the canonical path.
 *
 * **A slot of a non-terminal job is never deleted, and a job's top slot never is.** Freeing the
 * `v<N+1>` pathname would let a delayed writer still holding a stale read at `N` claim that version
 * again; keeping the top slot makes `link` fail `EEXIST` for it forever. Below the top of a TERMINAL
 * job, slots are committed history (see `compactSlots`) and do go — so a won `link` no longer proves
 * first claim, and the win is **confirmed here instead of assumed** (vibe-204):
 *
 *   * the job's highest OTHER slot must be below this version — the retained top slot is the
 *     authority, because a publisher paused before its `rename` can lower the canonical at any time,
 *     and a confirmation that trusted the canonical alone would accept a reclaimed version beneath
 *     a terminal top;
 *   * and the canonical must not be past this version, nor at it with different bytes.
 *
 * In order: a missing canonical, a tombstone or a prune marker means the job is gone (`GONE`);
 * the canonical holding the exact bytes — the winner's own candidate, or the slot being rolled
 * forward — is the one proof of success (`ALREADY`); a retained slot above this version, or a
 * canonical at or past it with other bytes, means the version had been freed and taken
 * (`SUPERSEDED`). Only then is the slot published. A slot that vanished with nothing above it is an
 * error, not a success. Publication is temp + `rename`, atomic and idempotent by content; a prune
 * tombstone makes it fail (`EISDIR`) instead of recreating the job. Publishing a terminal record
 * compacts the job's history behind it.
 */
async function commit(workspace, jobId, version, { expectedBytes = null } = {}) {
  let content = null;
  try {
    content = await readFile(slotPath(workspace, jobId, version), "utf8");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  const current = await readCanonicalRaw(workspace, jobId);
  // 1. Gone: no canonical, a tombstone, or a prune marker (the deletion is durable from the marker on).
  if (current === null) return COMMIT.GONE;
  if ((await inspectMarker(jobsDir(workspace), jobId)).state === "valid") return COMMIT.GONE;
  // 2. Already: the ONLY proof of success is that the canonical holds the exact bytes — the winner's
  //    own candidate (`expectedBytes`), or the slot a recoverer is rolling forward. A canonical at or
  //    past this version proves nothing: the version may have been freed and taken by someone else.
  const proven = expectedBytes ?? content;
  if (proven !== null && current.raw === proven) return COMMIT.ALREADY;
  // 3. Superseded: a retained slot above this version is the authority (a paused publisher can lower
  //    the canonical at any time, so the canonical alone is never trusted) …
  const others = await highestSlot(workspace, jobId, { except: version });
  if (others !== null && others > version) return COMMIT.SUPERSEDED;
  // … and so is a canonical at or past this version with other bytes.
  if (current.record !== null && current.record.version >= version) return COMMIT.SUPERSEDED;
  // 4. A slot that vanished with nothing above it and a canonical below it was deleted by something
  //    that is not this store — reported, never papered over.
  if (content === null) {
    throw new JobStoreError(
      `${jobId}: version ${version} slot vanished without being committed (canonical is ` +
      `${current.record ? current.record.version : "unreadable"})`);
  }

  // vibe-103: publication is still temp + rename, but through the audited primitive — the scratch
  // is created O_EXCL|O_NOFOLLOW at 0600, a symlinked canonical is refused instead of replaced, and
  // the mode is explicit so a record that predates this change stops being 0644.
  try {
    await writeAtomic(jobsDir(workspace), recordPath(workspace, jobId), content,
      { mode: PRIVATE_FILE_MODE });
  } catch (error) {
    // vibe-204: the tombstone barrier. Prune turned the canonical path into a directory between
    // our confirmation and our rename; `rename` (or the primitive's own refusal to publish over a
    // directory) is the late publication FAILING rather than resurrecting the job.
    if (await classify(recordPath(workspace, jobId)) === "dir") return COMMIT.GONE;
    throw error;
  }
  let published = null;
  try { published = JSON.parse(content); } catch { /* unparseable slots never reach here */ }
  if (published && isTerminal(published)) await compactSlots(workspace, jobId, version);
  return COMMIT.PUBLISHED;
}

/**
 * Compaction (vibe-204): once a TERMINAL record is published, every slot below the top is committed
 * history — the canonical reached `top` only through a writer that read `top - 1`, which existed
 * only because `top - 2` was read, and so on down — so none of them holds recoverable state, and
 * none is needed to block a re-claim: the top slot stays (it is what makes `link(v<top>)` fail
 * `EEXIST` for a writer one version stale, and what a stale canonical is resolved against), and a
 * re-claim of a freed lower version is caught by `commit`'s confirmation. Only stamped slots go,
 * through `unlinkOwned`; anything else survives for prune to report. Best-effort by design: a crash
 * mid-way leaves residue that only `pruneTerminalJobs` removes, since reads never mutate.
 */
async function compactSlots(workspace, jobId, top) {
  const dir = jobsDir(workspace);
  const pattern = slotPattern(jobId);
  let removed = 0;
  const names = await readdir(dir).catch(() => []);
  for (const name of names) {
    const match = pattern.exec(name);
    if (!match || Number(match[1]) >= top) continue;
    if (await unlinkOwned(dir, name, [SCRATCH_KIND]).catch(() => false)) removed += 1;
  }
  return removed;
}

/**
 * Apply `updater` to the record under compare-and-swap.
 *
 * `updater` must be **pure**: it is re-run in full against every freshly read record, so a claim or
 * heartbeat that lands mid-flight cannot be overwritten by a decision made before it existed. Return
 * `REJECT` to decline. Returns the committed record.
 */
export async function transact(workspace, jobId, updater, { attempts = 50, onWon = null } = {}) {
  await ensureState(workspace);

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

    // The CAS, unchanged in kind: `publishNew` stages the content and hard-links it into the slot,
    // so the slot still becomes visible with its content already whole, and EEXIST still means
    // exactly one writer won. What is new is that the scratch is exclusive, private and stamped,
    // and that its cleanup proves ownership rather than trusting the path.
    const bytes = JSON.stringify(stamped(candidate), null, 2) + "\n";
    const won = await publishNew(jobsDir(workspace), slotPath(workspace, jobId, target), bytes,
      { mode: PRIVATE_FILE_MODE });

    if (won) {
      // `onWon` is a documented test seam (the species of `cancelJob`'s `onResolved`): it runs in
      // the window between winning the link and confirming it, where the interleavings live.
      if (onWon) await onWon(jobId, target);
      const outcome = await commit(workspace, jobId, target, { expectedBytes: bytes });
      if (outcome === COMMIT.PUBLISHED || outcome === COMMIT.ALREADY) return candidate;
      // vibe-204: the version we won had been freed — by compaction (this read was stale beneath a
      // terminal top) or by prune (the job is gone). The retention rule used to make this
      // unreachable; now the win is confirmed instead of assumed, and success is never reported.
      // Our slot is removed only when the job is GONE: with no canonical nobody can have built on
      // it. When it is merely superseded it stays — a reader may already have taken it as the top
      // and linked above it, and deleting a slot someone built on is the one thing this store must
      // never do. Left beneath a terminal top it is inert residue that prune removes with the job.
      if (outcome === COMMIT.GONE) {
        await unlinkOwned(jobsDir(workspace), `${jobId}.v${target}.json`, [SCRATCH_KIND]).catch(() => false);
      }
      continue;
    }

    // Someone else holds this version. Either they committed it, or they died before committing.
    const now = await readCanonical(workspace, jobId).catch(() => null);
    if (!now || now.version < target) await rollForward(workspace, jobId, target);
    // Either way, loop: re-read and re-run the updater against the new state.
  }
  throw new JobStoreError(`${jobId}: gave up after ${attempts} contended attempts`);
}

/** Create the initial record. Distinct from `transact` because there is nothing to compare against. */
export async function createRecord(workspace, record, { onPublished = null } = {}) {
  await ensureState(workspace);
  const dir = jobsDir(workspace);
  // vibe-204: a pruned id is dead. A tombstone (or any directory) at the path makes `publishNew`
  // refuse; a valid marker means a prune has begun and the tombstone does not stand yet.
  if ((await inspectMarker(dir, record.jobId)).state === "valid"
      || await classify(recordPath(workspace, record.jobId)) === "dir") {
    throw new JobStoreError(`${record.jobId}: id is pruned (marker or tombstone present)`);
  }
  const created = await publishNew(dir, recordPath(workspace, record.jobId),
    JSON.stringify(stamped(record), null, 2) + "\n", { mode: PRIVATE_FILE_MODE });
  if (!created) throw new JobStoreError(`${record.jobId}: record already exists`);
  // The linearisation point against a concurrent prune is the MARKER, not this check: a prune that
  // published its marker before this publication landed owns the id, and this record is behind a
  // deletion commitment. So the check is repeated AFTER publishing — a marker seen now means the
  // prune won; the record is withdrawn (it is ours, just written) and creation is refused rather
  // than reported as landed. `onPublished` is a documented test seam for that window.
  if (onPublished) await onPublished(record.jobId);
  // The proof that a creation LANDED is not "no marker appeared": a prune that ran the whole way
  // through inside this window removed its marker on the way out, and the absence it leaves behind
  // looks exactly like an uncontested creation. So the proof is positive — THIS record, read back
  // through a non-following handle, still standing at the canonical path — and it is taken after
  // the marker check, so a creation is never reported as landed over a tombstone.
  const mine = identityOf(record);
  const standing = await ownedRecordAt(dir, `${record.jobId}.json`);
  const stands = standing !== null && standing.jobId === record.jobId
    && sameIncarnation(identityOf(standing), mine);
  if ((await inspectMarker(dir, record.jobId)).state === "valid") {
    // Withdraw only what we published: the identity travels into the unlink, so a record another
    // writer put at this path in the window is left exactly where it is.
    if (stands) {
      await removeOwned(dir, `${record.jobId}.json`, [SCRATCH_KIND],
        (doc) => doc.jobId === record.jobId && sameIncarnation(identityOf(doc), mine));
    }
    throw new JobStoreError(`${record.jobId}: id is pruned (a prune marked it concurrently)`);
  }
  if (!stands) {
    throw new JobStoreError(
      `${record.jobId}: creation did not stand (the record published is no longer at the canonical path)`);
  }
  return record;
}

/**
 * The state directory is private, and `ensureDirAt`'s creation mode cannot fix one that already
 * exists — an installation upgraded from before vibe-103 has it at 0755, holding records that can
 * contain raw model output. `secureDirAt` tightens it through its descriptor on every run.
 */
async function ensureState(workspace) {
  await ensureDirAt(workspace, path.join(STATE_DIRNAME, "jobs"));
  await secureDirAt(workspace, STATE_DIRNAME);
  await secureDirAt(workspace, path.join(STATE_DIRNAME, "jobs"));
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

/** The result line: exactly the five contract keys, in contract order. */
export function resultLine(record) {
  return JSON.stringify(Object.fromEntries(RESULT_KEYS.map((key) => [key, record[key] ?? null])));
}

/**
 * Reap orphan temps only. **This sweep never deletes a version slot, at any age** — an uncommitted
 * slot is recoverable protocol state, and deleting it is the ABA race this design exists to remove.
 * Slots of a TERMINAL job are removed elsewhere, deliberately: below the top at compaction (a
 * terminal commit), and as a whole job by `pruneTerminalJobs` (explicit operator action, never a hook).
 */
const SCRATCH_KIND = "job-scratch";

/** Every scratch this store publishes carries the stamp, so the reaper can prove ownership. */
function stamped(record) {
  return { ...record, [STAMP_KEY]: { kind: SCRATCH_KIND, schema: 1 } };
}

export async function reapOrphanTemps(workspace, { now = Date.now() } = {}) {
  const dir = jobsDir(workspace);
  // vibe-103: trust is anchored at the WORKSPACE, not at the final jobs directory. Checking only
  // the last component let `.vibe-suite-state` be a symlink whose `jobs` child was a real directory
  // outside the workspace — assertRoot would accept it and the reaper would work there. assertInside
  // refuses an intermediate symlinked component, so the whole chain has to be genuine.
  try {
    await assertRoot(workspace);
    await assertInside(workspace, dir);
    await assertRoot(dir);
  } catch {
    return 0;
  }
  let names;
  try {
    names = await readdir(dir);
  } catch {
    return 0;
  }
  let reaped = 0;
  let failed = 0;
  for (const name of names) {
    if (!isReapCandidate(name)) continue;                              // never a .vN slot
    try {
      // `lstat`, not `stat`: judging a symlink by its target's mtime is how an old outside file
      // qualified for deletion. And ownership is proven by the stamp inside the file, read through
      // the open handle — a name pattern is not ownership, which is the other half of the same
      // defect. An unstamped match survives; failing to collect our own temp is a leak, deleting
      // someone else's file is a defect, and the two are not the same size.
      const info = await lstat(path.join(dir, name));
      if (!info.isFile()) continue;
      if (now - info.mtimeMs < TEMP_REAP_MIN_AGE_MS) continue;         // when in doubt, leave it
      if (await unlinkOwned(dir, name, [SCRATCH_KIND])) reaped += 1;
    } catch {
      // A temp that vanished or cannot be lstat'd is left alone — but counted, because a reaper
      // that silently swallows every error reports a clean sweep it did not perform.
      failed += 1;
    }
  }
  if (failed > 0) {
    process.stderr.write(`vibe-suite: ${failed} orphan temp(s) could not be examined\n`);
  }
  return reaped;
}

/**
 * The reaper's candidate set: this suite's own scratch names, in both the current `.vibe-tmp` form
 * and the legacy `.tmp.`/`.pub.` forms a crash before vibe-103 may have left behind. Canonical
 * records and version slots are excluded by shape, so no amount of stamping brings them into range.
 */
function isReapCandidate(name) {
  if (/^job_[0-9a-f]{20}\.json$/.test(name)) return false;              // canonical
  if (/\.v\d+\.json$/.test(name)) return false;                         // version slot
  return name.endsWith(".vibe-tmp") || name.includes(".tmp.") || name.includes(".pub.");
}

// ---------------------------------------------------------------------------------------------
// Prune (vibe-204 / grill H8). The store grew without bound: every heartbeat is a full CAS
// transaction and every slot was kept forever, so a ten-minute background job left ~23 files, the
// last two carrying the whole `rawOutput`. Compaction (above) bounds a finished job to canonical +
// top slot; prune removes finished jobs whole, and only when an operator asks.

/** `jobs prune` default cutoff: terminal jobs that ended more than a week ago. */
export const DEFAULT_PRUNE_OLDER_THAN_MS = 7 * 24 * 60 * 60 * 1000;

/**
 * How long a prune tombstone stays. It bounds the publisher pause the barrier defends against: a
 * writer stalled between confirming its win and renaming the canonical for longer than this could
 * recreate the job's canonical after the tombstone is gone — a declared boundary, not a hidden one.
 */
export const PRUNE_TOMBSTONE_TTL_MS = 30 * 24 * 60 * 60 * 1000;
const TOMBSTONE_MODE = 0o700;
/** Bounded: each retry answers exactly one resurrected canonical, and a paused publisher lands at most once. */
const TOMBSTONE_ATTEMPTS = 8;

const CANONICAL_NAME = /^(job_[0-9a-f]{20})\.json$/;
const ANY_SLOT_NAME = /^(job_[0-9a-f]{20})\.v\d+\.json$/;
const MARKER_NAME = /^(job_[0-9a-f]{20})\.pruning$/;

/**
 * Stage a tombstone — a 0700 directory holding our stamp file for this job — and rename it into
 * place in one step (vibe-204). `false` means something now occupies the canonical path (a late
 * publication landed, or a directory that is not ours) and the staging directory was withdrawn.
 * A crash between staging and the rename leaves `.tomb.<nonce>.vibe-tmp/` — provenance inside —
 * for the next prune's staging sweep; it never leaves an unprovenanced directory at the canonical
 * path.
 */
async function installTombstone(dir, jobId, onStep, attempt = null) {
  const stagedName = `.tomb.${tombstoneNonce(6).toString("hex")}.vibe-tmp`;
  await ensureDirAt(dir, stagedName, TOMBSTONE_MODE);
  const stamp = JSON.stringify({ [STAMP_KEY]: { kind: TOMBSTONE_KIND, schema: 1 }, jobId, attempt }) + "\n";
  await publishNew(path.join(dir, stagedName), path.join(dir, stagedName, TOMBSTONE_STAMP), stamp,
    { mode: PRIVATE_FILE_MODE });
  if (onStep) await onStep(jobId, "staged");
  const ok = await publishDirAt(dir, stagedName, `${jobId}.json`,
    { stampName: TOMBSTONE_STAMP, kinds: [TOMBSTONE_KIND] });
  if (!ok) await removeOwnedDirAt(dir, stagedName, { stampName: TOMBSTONE_STAMP, kinds: [TOMBSTONE_KIND] });
  return ok;
}

/**
 * Delete one job durably. Steps, each observable to a crash test through `onStep`:
 *   0. `preflight` — no marker: the canonical must be a stamped record of ours whose INCARNATION is
 *                  the one eligibility was judged on, or nothing is begun; a FOREIGN
 *                  marker (unstamped, malformed, another job's, a symlink, a directory) blocks the
 *                  job and is reported — never resumed, never withdrawn;
 *   1. `marker`   — publish `<jobId>.pruning` (stamped; it names the record's incarnation and opens
 *                   a deletion attempt); losing that race to another prune means resuming from ITS
 *                   marker, or — if it already finished — nothing at all; a marker standing over a
 *                   tombstone from a DIFFERENT attempt is withdrawn and the job counted by no run,
 *                   whether this call published that marker or adopted it; from here the marker is
 *                   preserved until the tombstone stands;
 *   2. `unlinked` — remove the canonical, but only a record of ours with the marker's incarnation,
 *                   and the identity travels INTO the unlink so the record deleted is the record
 *                   judged: `absent` is a concurrent prune's win and proceeds; a different
 *                   incarnation (one `createRecord` published in the gap — it withdraws itself), a
 *                   file that is not ours, a symlink, or a directory without our provenance BLOCKS:
 *                   marker kept, both reported;
 *   3. `staged`/`entombed` — stage the stamped tombstone and rename it into place (a file that
 *                   comes back in the gap — a paused publisher's rename — is removed again, bounded);
 *   4. `slots`    — remove every slot of ours; `absent` is nothing, `refused` a leftover;
 *   then the marker is removed — an unremovable marker is a reported leftover.
 * Returns `{ ok, files, leftovers, completedByOther }`; `ok: false` = the job stays (whole, or
 * blocked behind its marker for the next prune / the operator).
 */
async function entomb(dir, jobId, names, { onStep = null, identity = null } = {}) {
  const name = `${jobId}.json`;
  const marker = markerName(jobId);
  const leftovers = [];
  let files = 0;
  let seen = await inspectMarker(dir, jobId);
  if (seen.state === "foreign") return { ok: false, files: 0, leftovers: [marker] };
  if (seen.state === "absent") {
    const record = await ownedRecordAt(dir, name);
    const judged = identity === null ? null : identityOf(identity);
    if (record === null || record.jobId !== jobId || judged === null
        || !sameIncarnation(identityOf(record), judged)) {
      return { ok: false, files: 0, leftovers: [name] };                    // not ours, or not the record judged: no marker
    }
    // The marker names the incarnation it commits to delete, not merely the moment the record was
    // created: what is being promised is "this record's life ends", and a life needs a name.
    const stamp = JSON.stringify({
      [STAMP_KEY]: { kind: PRUNE_MARKER_KIND, schema: 1 },
      jobId, createdAt: judged.createdAt, incarnation: judged.incarnation,
      attempt: tombstoneNonce(8).toString("hex"),
    }) + "\n";
    if (onStep) await onStep(jobId, "preflight");
    await publishNew(dir, path.join(dir, marker), stamp, { mode: PRIVATE_FILE_MODE });
    seen = await inspectMarker(dir, jobId);                                   // false = raced: re-inspect
    if (seen.state === "absent") return { ok: true, files: 0, leftovers: [], completedByOther: true };
    if (seen.state === "foreign") return { ok: false, files: 0, leftovers: [marker] };
  }
  const committed = identityOf(seen.doc);
  const attemptId = attemptOf(seen.doc);
  if (onStep) await onStep(jobId, "marker");
  let entombed = false;
  for (let round = 1; round <= TOMBSTONE_ATTEMPTS && !entombed; round += 1) {
    const at = await inspectCanonicalPath(dir, jobId);
    if (at === "tombstone") {
      // Whose deletion does this tombstone belong to? A tombstone carrying THIS marker's attempt is
      // the deletion this call is part of — installed by this prune or by a peer working under the
      // same marker — and finishing it is the `resumed` case. A tombstone carrying a DIFFERENT
      // attempt (or none) predates this marker: the job was already deleted and reported by another
      // attempt, and this marker was published over the result. Nothing here is left to finish, so
      // the marker is withdrawn and the job is reported by neither `pruned` nor `resumed`. The
      // attempt travels in both the marker and the tombstone precisely so that every adopter of a
      // marker — not only the prune that published it — can tell the two apart.
      const standing = await tombstoneAt(dir, jobId);
      if (standing === null) continue;            // it changed under us: re-inspect, bounded by the loop
      if (attemptId === null || attemptOf(standing) !== attemptId) {
        if (await removeOwned(dir, marker, [PRUNE_MARKER_KIND]) === "refused") leftovers.push(marker);
        return { ok: true, files, leftovers, completedByOther: true };
      }
      entombed = true;
      break;
    }
    if (at === "foreign") return { ok: false, files: 0, leftovers: [name, marker] };   // blocked; marker kept
    if (at === "file") {
      // Identity is applied BY the unlink, on the document that call reads through its own handle:
      // a record published in the gap is a different incarnation and is refused, not deleted.
      const outcome = await removeOwned(dir, name, [SCRATCH_KIND],
        (doc) => doc.jobId === jobId && sameIncarnation(identityOf(doc), committed));
      if (outcome === "refused") return { ok: false, files: 0, leftovers: [name, marker] };
      if (outcome === "removed") {
        files += 1;
        if (onStep) await onStep(jobId, "unlinked");
      }
    }
    if (await installTombstone(dir, jobId, onStep, attemptId)) entombed = true;
    // else: something appeared at the path in the gap — loop, and inspect it again.
  }
  if (!entombed) return { ok: false, files: 0, leftovers: [name, marker] };
  if (onStep) await onStep(jobId, "entombed");
  const pattern = slotPattern(jobId);
  for (const other of names) {
    if (!pattern.test(other)) continue;
    const outcome = await removeOwned(dir, other, [SCRATCH_KIND]);
    if (outcome === "removed") files += 1;
    else if (outcome === "refused") leftovers.push(other);
  }
  if (onStep) await onStep(jobId, "slots");
  if (await removeOwned(dir, marker, [PRUNE_MARKER_KIND]) === "refused") leftovers.push(marker);
  return { ok: true, files, leftovers, completedByOther: false };
}

/**
 * Delete TERMINAL jobs whole — canonical and every slot — when they ended (or, lacking `endedAt`,
 * were last updated) more than `olderThanMs` ago. Explicit only: `/vibe-suite:jobs prune` calls this;
 * no hook ever does.
 *
 * What makes it safe: a terminal record is final (`transact` refuses to reopen one), eligibility is
 * judged on the store's own slot-aware read plus `validateRecord` (a record the store cannot vouch
 * for is reported and left alone), and the **canonical goes first** — from that instant the job is
 * gone to every reader (`readCanonical` refuses to resurrect from slots) and to any writer still in
 * flight (`commit` finds no canonical and its slot is cleaned up, never published). Every deletion
 * is `unlinkOwned`: a file without this suite's stamp is not ours and survives, reported as a
 * leftover; a job whose canonical is not ours is left whole. Finally, stamped slots whose canonical
 * is absent — the residue of a prune that crashed between the two steps, or of a stale writer — are
 * swept, so successive runs converge.
 *
 * Deletion is durable from its first step: a stamped marker `<jobId>.pruning` is published before
 * the canonical is touched and removed last, so a prune interrupted at any step is completed by the
 * next one (`resumed`), and a VALIDLY marked job is already gone to readers, `commit` and
 * `createRecord`. Authority is never a filename: a marker counts only when it carries this store's
 * stamp for that job id, a canonical is only ever deleted when it carries the record stamp, and a
 * removal that finds nothing there is a lost race, not a refusal. Two prunes may run concurrently.
 * What a pruned job leaves behind: a **tombstone** — a 0700 directory at the canonical path holding
 * this store's stamp for the job, staged elsewhere and renamed into place so it never exists without
 * its provenance —
 * for `PRUNE_TOMBSTONE_TTL_MS`. It is the barrier that makes a late publication by a paused writer
 * fail (`rename` onto a directory is `EISDIR`; `publishNew` refuses a directory) instead of
 * recreating the job; readers treat it as "no job". Expired tombstones are removed here, through the
 * audited primitive, once they are proven ours by shape, mode and uid. The worker log `<jobId>.log`
 * is left in place and reported: it is an unstamped raw-stderr sink, and deleting by name alone is
 * what this store's write doctrine refuses. One bounded file per job.
 */
export async function pruneTerminalJobs(workspace, {
  olderThanMs = DEFAULT_PRUNE_OLDER_THAN_MS, now = Date.now(), onStep = null,
} = {}) {
  const dir = jobsDir(workspace);
  const report = {
    pruned: [], resumed: [], kept: 0, blocked: [], invalid: [], leftovers: [], orphanSlots: 0,
    logsLeft: [], tombstonesExpired: 0, stagingSwept: 0,
  };
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return report;
    throw error;
  }
  // Trust is anchored at the WORKSPACE (the reaper's rule) — and loudly, because prune is an explicit
  // operator action, not a hook that must stay quiet.
  await assertRoot(workspace);
  await assertInside(workspace, dir);
  await assertRoot(dir);

  const names = entries.filter((entry) => !entry.isDirectory()).map((entry) => entry.name);
  const cutoff = now - olderThanMs;
  const blockedIds = new Set();

  // Markers first. A VALID marker is a deletion that already began — completed here without an
  // eligibility re-check (that was made before the marker was published). Anything else wearing
  // the marker name — a foreign file, a symlink, a directory — is reported and blocks its job.
  const valid = [];
  for (const entry of entries) {
    const id = MARKER_NAME.exec(entry.name)?.[1];
    if (!id) continue;
    if ((await inspectMarker(dir, id)).state === "valid") valid.push(id);
    else { report.leftovers.push(entry.name); blockedIds.add(id); report.blocked.push(id); }
  }
  for (const jobId of valid.sort()) {
    const done = await entomb(dir, jobId, names, { onStep });
    report.leftovers.push(...done.leftovers);
    // A marked job the resume could not finish is BLOCKED, and is named as such. Adding it to the
    // blocked set alone would keep it out of every subsequent loop and out of every total, so the
    // one job in the store an operator most needs to see would be the one the report never counts.
    if (!done.ok) { blockedIds.add(jobId); report.blocked.push(jobId); continue; }
    if (done.completedByOther) continue;
    if (names.includes(`${jobId}.log`)) report.logsLeft.push(jobId);
    report.resumed.push(jobId);
  }

  const ids = names.map((name) => CANONICAL_NAME.exec(name)?.[1]).filter(Boolean)
    .filter((jobId) => !valid.includes(jobId) && !blockedIds.has(jobId)).sort();
  for (const jobId of ids) {
    let record;
    try {
      record = await readRecord(workspace, jobId);
    } catch (error) {
      report.invalid.push({ jobId, reason: String(error?.message ?? error) });
      continue;
    }
    const verdict = validateRecord(record, jobId);
    if (!verdict.ok) {
      report.invalid.push({ jobId, reason: verdict.reason });
      continue;
    }
    const endedAt = record.endedAt ?? record.updatedAt;
    if (!isTerminal(record) || !(Date.parse(endedAt) <= cutoff)) {
      report.kept += 1;
      continue;
    }
    const done = await entomb(dir, jobId, names, { onStep, identity: record });
    report.leftovers.push(...done.leftovers);
    if (!done.ok) {
      // Eligible, but not deletable: the canonical is not ours, it changed under us, or something
      // at one of the job's paths blocks the deletion. This is NOT `kept` — `kept` means "a job
      // this run deliberately left alone because it is running or too recent", and rendering a
      // blocked job as kept tells an operator the store made a retention decision when in fact it
      // met something it could not act on. It is its own category, and it is reported.
      report.blocked.push(jobId);
      blockedIds.add(jobId);
      continue;
    }
    if (done.completedByOther) continue;
    if (names.includes(`${jobId}.log`)) report.logsLeft.push(jobId);
    report.pruned.push({ jobId, status: record.status, endedAt, files: done.files });
  }

  // Sweeps, over a fresh listing. Every removal is tri-state: a concurrent prune's win is `absent`,
  // never a leftover.
  const after = await readdir(dir, { withFileTypes: true }).catch(() => []);
  const present = new Set(after.filter((entry) => !entry.isDirectory())
    .map((entry) => CANONICAL_NAME.exec(entry.name)?.[1]).filter(Boolean));
  const marked = new Set(after.map((entry) => MARKER_NAME.exec(entry.name)?.[1]).filter(Boolean));
  // Orphan slots: a stamped slot whose canonical path is absent or our tombstone belongs to no job.
  // A slot beside a marker (any marker) or beside a foreign directory belongs to a job that is
  // blocked or mid-deletion — left alone.
  for (const entry of after) {
    const match = ANY_SLOT_NAME.exec(entry.name);
    if (!match) continue;
    if (present.has(match[1]) || marked.has(match[1]) || blockedIds.has(match[1])) {
      // The job is live, marked, or blocked, so its slots are not this sweep's to remove — but a
      // slot-shaped entry that is not ours is still reported, because that is what the retention
      // documentation promises and because an operator whose job is quietly reading an object this
      // store never wrote has no other way to learn of it. Ownership is proven, never assumed: a
      // non-following stamped read, exactly as every other decision here makes it.
      if (await readOwned(dir, entry.name, [SCRATCH_KIND]) === null) report.leftovers.push(entry.name);
      continue;
    }
    const at = await inspectCanonicalPath(dir, match[1]);
    if (at !== "absent" && at !== "tombstone") { report.leftovers.push(entry.name); continue; }
    const outcome = await removeOwned(dir, entry.name, [SCRATCH_KIND]);
    if (outcome === "removed") report.orphanSlots += 1;
    else if (outcome === "refused") report.leftovers.push(entry.name);
  }
  // Directories at canonical paths: our tombstones expire after the TTL (provenance proven by the
  // primitive, which also refuses anything but the stamp inside); any other directory is reported.
  for (const entry of after) {
    const id = CANONICAL_NAME.exec(entry.name)?.[1];
    if (!id || !entry.isDirectory()) continue;
    const at = await inspectCanonicalPath(dir, id);
    if (at !== "tombstone") { report.leftovers.push(entry.name); continue; }
    let info;
    try {
      info = await lstat(path.join(dir, entry.name));
    } catch {
      continue;
    }
    if (now - info.mtimeMs < PRUNE_TOMBSTONE_TTL_MS) continue;
    // The canonical path is vacated by one `rename` before the tombstone is taken apart, so a
    // concurrent prune meeting this job sees either the tombstone whole or an absent path — never a
    // directory of ours stripped of the provenance that would let it be proven. The remains are
    // finished under a staging name, and a crash there leaves an empty directory the staging sweep
    // below converges.
    const outcome = await removeOwnedDirAt(dir, entry.name, {
      stampName: TOMBSTONE_STAMP, kinds: [TOMBSTONE_KIND],
      vacateAs: `.tomb.${tombstoneNonce(6).toString("hex")}.vibe-tmp`,
      onVacated: onStep === null ? null : () => onStep(id, "vacated"),
    });
    if (outcome === "removed") report.tombstonesExpired += 1;
    else if (outcome === "refused") report.leftovers.push(entry.name);
  }
  // Staging directories a crashed prune left behind, past the temp-reap age (never a live one).
  // Two shapes, and both converge: one still carrying its stamp — a crash between staging and the
  // rename that publishes a tombstone — and one that is EMPTY, which is what a crash before the
  // stamp was published, or after it was removed, leaves. An empty directory is removed by `rmdir`
  // alone, which refuses anything that holds data; under this store's declared threat model nothing
  // but this store writes inside the private state directory, so an empty directory wearing the
  // staging shape is this store's own unfinished work and not an object to be preserved for an
  // operator. A staging directory holding anything else is refused and reported, as before.
  const stagingAfter = await readdir(dir, { withFileTypes: true }).catch(() => []);
  for (const entry of stagingAfter) {
    if (!STAGING_NAME.test(entry.name) || !entry.isDirectory()) continue;
    let info;
    try {
      info = await lstat(path.join(dir, entry.name));
    } catch {
      continue;
    }
    if (now - info.mtimeMs < TEMP_REAP_MIN_AGE_MS) continue;
    const outcome = await removeOwnedDirAt(dir, entry.name, {
      stampName: TOMBSTONE_STAMP, kinds: [TOMBSTONE_KIND],
      onValidated: onStep === null ? null : () => onStep(entry.name, "staging-validated"),
      onStampJudged: onStep === null ? null : () => onStep(entry.name, "staging-stamp-judged"),
    });
    if (outcome === "removed") { report.stagingSwept += 1; continue; }
    if (outcome === "absent") continue;
    const empty = await removeEmptyDirAt(dir, entry.name);
    if (empty === "removed") report.stagingSwept += 1;
    else if (empty === "refused") report.leftovers.push(entry.name);
  }
  // A blocked job's files can be met twice — by `entomb` and again by the sweeps. One line each.
  report.leftovers = [...new Set(report.leftovers)].sort();
  return report;
}

// ---------------------------------------------------------------------------------------------
// Record validation + listing (E1.2 / vibe-12). `/vibe-suite:jobs` consumes records written by any
// engine lane (codex today, agy after #17), so what it trusts is the SCHEMA, checked here — never
// the lane, and never an unvalidated field. `pgid`/`workerPid` are control data: a forged or
// malformed handle that reaches a kill(2) signals an arbitrary process group, which is why nothing
// that fails this validator may be rendered as healthy, resolved, settled, or signalled.

const KNOWN_STATUSES = new Set(["running", ...TERMINAL_STATUSES]);

const isPid = (value) => Number.isSafeInteger(value) && value > 0;
const isTimestamp = (value) => typeof value === "string" && !Number.isNaN(Date.parse(value));
const nullOr = (check) => (value) => value === null || check(value);

/** key -> type check, mirroring `newRecord`. Extra keys are tolerated (a later lane may add its
 * own); a missing or mistyped contract key is not. */
const RECORD_SHAPE = {
  jobId: isValidJobId,
  version: (v) => Number.isSafeInteger(v) && v > 0,
  kind: (v) => typeof v === "string" && v.length > 0,
  status: (v) => KNOWN_STATUSES.has(v),
  sandbox: (v) => typeof v === "string" && v.length > 0,
  effort: nullOr((v) => typeof v === "string"),
  model: nullOr((v) => typeof v === "string"),
  background: (v) => typeof v === "boolean",
  verdictText: nullOr((v) => typeof v === "string"),
  verdictState: (v) => v === "absent" || v === "empty" || v === "present",
  errorClass: nullOr((v) => v === "quota" || v === "failure"),
  threadId: nullOr((v) => typeof v === "string"),
  workerPid: nullOr(isPid),
  pgid: nullOr(isPid),
  claimDigest: nullOr((v) => typeof v === "string"),
  createdAt: isTimestamp,
  // vibe-204: the record's incarnation. Presence is OPTIONAL (see OPTIONAL_KEYS): records written
  // before the field existed omit it and stay valid — and a prune's identity rules are written so
  // that a record without one can still be deleted, while never standing in for a record with one.
  incarnation: nullOr((v) => typeof v === "string" && /^[0-9a-f]{32}$/.test(v)),
  startedAt: nullOr(isTimestamp),
  endedAt: nullOr(isTimestamp),
  updatedAt: isTimestamp,
  heartbeatAt: nullOr(isTimestamp),
  timeoutMs: nullOr((v) => Number.isFinite(v) && v > 0),
  exitCode: nullOr((v) => Number.isSafeInteger(v)),
  rawOutput: nullOr((v) => typeof v === "string"),
  error: nullOr((v) => typeof v === "string"),
  // The runner finalises `tokens` with `billableTokens(usage)` — a non-negative number (or null
  // when no usage event arrived), NOT an object; see events.mjs.
  tokens: nullOr((v) => Number.isFinite(v) && v >= 0),
  // vibe-181: null until the run settles; boolean after. Presence is OPTIONAL (see OPTIONAL_KEYS):
  // records written before the field existed omit it and must stay valid — `validateRecord`
  // checks presence before the predicate, so optionality has to be declared there, not here.
  pipesLeaked: nullOr((v) => typeof v === "boolean"),
  // vibe-182: all three null until settle; presence OPTIONAL (OPTIONAL_KEYS) for pre-field records.
  stderrTail: nullOr((v) => typeof v === "string"),
  signal: nullOr((v) => typeof v === "string" && v.length > 0),
  malformedLines: nullOr((v) => Number.isSafeInteger(v) && v >= 0),
};

/**
 * Keys a record may omit and still validate — fields added after records existed on disk
 * (vibe-181: `pipesLeaked`; vibe-182: `stderrTail`, `signal`, `malformedLines`). Every other
 * `RECORD_SHAPE` key is required: a missing contract key is
 * a corrupt record, never a legacy one.
 */
const OPTIONAL_KEYS = new Set(["pipesLeaked", "stderrTail", "signal", "malformedLines", "incarnation"]);

/**
 * One complete verdict on a record: schema, identity, handle invariants. Returns
 * `{ ok: true }` or `{ ok: false, reason }` — a reason, because "invalid" without which field
 * failed sends the operator to a JSON diff.
 */
export function validateRecord(record, jobId) {
  if (typeof record !== "object" || record === null || Array.isArray(record)) {
    return { ok: false, reason: "record is not an object" };
  }
  for (const [key, check] of Object.entries(RECORD_SHAPE)) {
    if (!(key in record)) {
      if (OPTIONAL_KEYS.has(key)) continue;                            // pre-field record: legal
      return { ok: false, reason: `missing key: ${key}` };
    }
    if (!check(record[key])) return { ok: false, reason: `invalid ${key}: ${JSON.stringify(record[key])}` };
  }
  if (record.jobId !== jobId) {
    return { ok: false, reason: `identity mismatch: file says ${jobId}, record says ${record.jobId}` };
  }
  // Handle invariants. E1.1 sets pgid := workerPid on claim (the detached worker leads its group by
  // construction), and only background workers are ever detached — anything else is a forgery or a
  // corruption, and either way it must never reach a signal.
  if (record.background === false && record.pgid !== null) {
    return { ok: false, reason: "foreground record carries a pgid" };
  }
  if (record.pgid !== null && record.pgid !== record.workerPid) {
    return { ok: false, reason: `pgid ${record.pgid} !== workerPid ${record.workerPid}` };
  }
  return { ok: true };
}

/**
 * Every job in the store: canonical names enumerated, records loaded through the private
 * `readCanonical` — directly, so the one directory snapshot taken here can be reused (vibe-205).
 *
 * The split matters (round-1 plan review, finding 2): enumeration must see ONLY `<jobId>.json` —
 * `.vN` slots and `.tmp./.pub.` temps are CAS protocol state, not records — but the LOAD must go
 * through the store's slot-aware read, because a canonical file can be legitimately stale when a
 * writer died between `link` and `rename`. Raw-reading canonicals here would report stale status.
 *
 * Invalid records are returned separately with reasons, never silently dropped: an operator whose
 * job vanished from `status` with no trace would reasonably conclude the store lost it.
 */
export async function listRecords(workspace) {
  let entries;
  try {
    entries = await readdir(jobsDir(workspace), { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return { records: [], invalid: [] };
    throw error;
  }
  const records = [];
  const invalid = [];
  // vibe-204: a directory at a canonical path is a prune tombstone, and a `<jobId>.pruning` marker
  // means a prune has begun — both are jobs that no longer exist, not records that failed to read.
  const names = entries.filter((entry) => !entry.isDirectory()).map((entry) => entry.name);
  // vibe-205: the snapshot handed to the slot resolver is EVERY entry name, not `names` -- see the
  // note on `highestSlot`. Without it each record's resolve re-read this directory: O(jobs x entries).
  const listing = entries.map((entry) => entry.name);
  const marked = new Set();
  for (const id of names.map((name) => MARKER_NAME.exec(name)?.[1]).filter(Boolean)) {
    if ((await inspectMarker(jobsDir(workspace), id)).state === "valid") marked.add(id);   // a foreign marker hides nothing
  }
  // A directory at a canonical path is skipped only when it is this store's tombstone; any other
  // directory there is reported — a job whose record is buried under a foreign directory would
  // otherwise vanish from `status` without a trace.
  for (const entry of entries) {
    const match = CANONICAL_NAME.exec(entry.name);
    if (!match || !entry.isDirectory()) continue;
    if (await inspectCanonicalPath(jobsDir(workspace), match[1]) !== "tombstone") {
      invalid.push({ jobId: match[1], reason: "a directory that is not this store's tombstone occupies the canonical path" });
    }
  }
  for (const name of names.sort()) {
    const match = /^(job_[0-9a-f]{20})\.json$/.exec(name);
    if (!match || marked.has(match[1])) continue;
    const jobId = match[1];
    try {
      // The snapshot path stays PRIVATE: `readCanonical` directly, so the exported `readRecord`
      // never offers callers a `listing` whose completeness and freshness it cannot check.
      const record = await readCanonical(workspace, jobId, { listing });
      const verdict = validateRecord(record, jobId);
      if (verdict.ok) records.push(record);
      else invalid.push({ jobId, reason: verdict.reason });
    } catch (error) {
      invalid.push({ jobId, reason: String(error?.message ?? error) });
    }
  }
  records.sort((a, b) =>
    a.createdAt < b.createdAt ? -1 : a.createdAt > b.createdAt ? 1 : a.jobId < b.jobId ? -1 : 1);
  return { records, invalid };
}
