// SPDX-License-Identifier: ISC
// vibe-302: a suite that plants a job record or slot by hand writes it through here, so a positive carries exactly
// the stamp `jobs.mjs`'s `stamped()` produces and an UNSTAMPED twin is an explicit choice, never an accident. The
// store's authoritative reads refuse anything else (ADR-0004).
import { writeFileSync } from "node:fs";
import path from "node:path";
import { jobsDir } from "../../scripts/lib/jobs.mjs";
import { STAMP_KEY, STAMP_SCHEMA } from "../../scripts/lib/write.mjs";

export const STAMP = Object.freeze({ [STAMP_KEY]: { kind: "job-scratch", schema: STAMP_SCHEMA } });

/** The record with this store's stamp, exactly as the store writes it. */
export function withStamp(record) {
  return { ...record, ...STAMP };
}

/** Bytes for a planted record: stamped by default; `{ stamped: false }` is the explicit twin. */
export function slotBytes(record, { stamped = true, pretty = false } = {}) {
  const doc = stamped ? withStamp(record) : record;
  return pretty ? JSON.stringify(doc, null, 2) + "\n" : JSON.stringify(doc);
}

export function writeSlot(ws, jobId, version, record, opts = {}) {
  const file = path.join(jobsDir(ws), `${jobId}.v${version}.json`);
  writeFileSync(file, slotBytes({ ...record, version }, opts), "utf8");
  return file;
}

export function writeCanonical(ws, jobId, record, opts = {}) {
  const file = path.join(jobsDir(ws), `${jobId}.json`);
  writeFileSync(file, slotBytes(record, opts), "utf8");
  return file;
}
