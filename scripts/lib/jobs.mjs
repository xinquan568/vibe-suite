// SPDX-License-Identifier: ISC
// The job record store (E1.1 / vibe-11).
//
// Records live at `<workspace>/.vibe-suite-state/jobs/<jobId>.json` — one file per job, beside the
// toggle store's `state.json`, never inside it. `/vibe-suite:jobs` (#12) and the agy runner (#17)
// both read this layout, so the schema below is a shared contract rather than an implementation
// detail, and the fields are documented here because six later items build against them.
//
// Writes go through a temporary file and a rename, matching `store.py`'s pattern for the same
// reason: a record is written at least three times (launch, worker handshake, termination) plus once
// per heartbeat, and a reader must never observe a half-written file.
//
// **Nullability differs deliberately from the toggle store.** `store.py` documents that an unset key
// is *absent* rather than null, because there absence means "the default applies" — a real
// tri-state. A job record has no defaults to fall back on: `threadId: null` means "no thread id
// exists yet", which is information. So every key is always present and unavailable values are
// `null`. This is a decision, not an oversight.

import { randomUUID } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";

export const STATE_DIRNAME = ".vibe-suite-state";

/** The four keys of the one-line result contract, in contract order. */
export const RESULT_KEYS = ["jobId", "status", "threadId", "rawOutput"];

/** Terminal statuses. `cancelled` is reserved for #12, which signals via `pgid`. */
export const TERMINAL_STATUSES = new Set(["completed", "failed", "timed_out", "cancelled"]);

export function newJobId() {
  return `job_${randomUUID().replace(/-/g, "").slice(0, 20)}`;
}

export function jobsDir(workspace) {
  return path.join(workspace, STATE_DIRNAME, "jobs");
}

export function recordPath(workspace, jobId) {
  return path.join(jobsDir(workspace), `${jobId}.json`);
}

/** A fresh record. Every field is present; unknown values are explicitly null. */
export function newRecord({ jobId, kind, sandbox, effort, model, background, timeoutMs }) {
  const now = new Date().toISOString();
  return {
    jobId,
    kind,
    status: "running",
    sandbox,
    effort,
    model: model ?? null,          // P9: null means the CLI's own default ran
    background: Boolean(background),
    threadId: null,
    workerPid: null,
    pgid: null,
    createdAt: now,
    startedAt: null,
    endedAt: null,
    updatedAt: now,
    heartbeatAt: null,
    timeoutMs: timeoutMs ?? null,
    exitCode: null,
    rawOutput: null,
    error: null,
  };
}

export async function writeRecord(workspace, record) {
  const target = recordPath(workspace, record.jobId);
  await mkdir(path.dirname(target), { recursive: true });
  const updated = { ...record, updatedAt: new Date().toISOString() };
  // Rename is atomic within a directory, so a concurrent reader sees either the old file or the new
  // one — never a partial write. The temp name is per-process to keep two writers from colliding.
  const temporary = `${target}.${process.pid}.tmp`;
  await writeFile(temporary, JSON.stringify(updated, null, 2) + "\n", "utf8");
  await rename(temporary, target);
  return updated;
}

export async function readRecord(workspace, jobId) {
  const raw = await readFile(recordPath(workspace, jobId), "utf8");
  return JSON.parse(raw);
}

export async function updateRecord(workspace, jobId, patch) {
  const current = await readRecord(workspace, jobId);
  return writeRecord(workspace, { ...current, ...patch });
}

/** The result line: exactly the four contract keys, in contract order. */
export function resultLine(record) {
  return JSON.stringify(Object.fromEntries(RESULT_KEYS.map((key) => [key, record[key] ?? null])));
}

/**
 * Wait until a background worker has claimed the record.
 *
 * Bounded on purpose. A worker that dies before writing its pid must not hang the launcher, so the
 * wait ends and the caller reports a failed job rather than blocking forever.
 */
export async function awaitWorkerClaim(workspace, jobId, { timeoutMs = 5000, pollMs = 25 } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const record = await readRecord(workspace, jobId);
      if (record.workerPid !== null) return record;
    } catch {
      // The record may not exist for a moment; keep polling until the bound expires.
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  return null;
}
