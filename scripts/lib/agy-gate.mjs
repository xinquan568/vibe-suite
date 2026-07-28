// SPDX-License-Identifier: ISC
// The agy contract gate (E1.7 / vibe-17, implements the D5/D8 staged rollout).
//
// A default execution path may not rest on an unconfirmed CLI contract. This module is the ONE
// place that decides whether the agy lane is reachable, so "is the gate open?" has exactly one
// answer everywhere: the runner's pre-gate refusal, the fallback decision, preflight's exit-code
// contribution, and the invariant tests all call `resolveAgyGate`.
//
// Two properties are load-bearing:
//
// **The record is a plugin asset, resolved from THIS file's location — never the caller's CWD.**
// The runner's CWD is the user's workspace, where no record exists; resolving there would wedge
// the gate permanently closed and make the eventual flip impossible to observe.
//
// **The predicate is strict and fail-closed.** Schema, top-level status, and every mandatory check
// must agree. A record whose `status` says passed while a check says otherwise is not a graduated
// lane, it is a corrupted record — and it must read as closed. Nothing here throws: an unreadable
// gate is a closed gate, not a crash in an unrelated command.

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const GATE_SCHEMA = 1;

// The canonical definitions are PRIVATE and immutable, and the resolver reads only these. Exporting
// the arrays the predicate consumes let a reviewer delete `read_only_write_denied` from the
// mandatory set in-process and open the gate — the same defect as the mutable signature registry,
// one layer further out. `Object.freeze` on a Set is not protection either: `.add()` still works,
// so the states are a frozen array checked by `includes`.
const CANONICAL_CHECKS = Object.freeze([
  "headless_invocation",
  "read_only_write_denied",
  "timeout_kill",
  "failure_signature",
  "quota_signature",
]);
const CANONICAL_STATES = Object.freeze(["passed", "failed", "not_verified"]);
const CANONICAL_RECORD_KEYS = Object.freeze([
  "schema", "status", "agy_version", "recorded_at", "checks",
]);

// Frozen COPIES for callers that enumerate — not aliases of the canonical arrays, so even a
// successful mutation of an export cannot reach the predicate. `CHECK_STATES` is an array rather
// than a Set on purpose: `Object.freeze` does not stop `Set.prototype.add`, so a frozen Set is a
// false reassurance.
export const MANDATORY_CHECKS = Object.freeze([...CANONICAL_CHECKS]);
export const CHECK_STATES = Object.freeze([...CANONICAL_STATES]);
export const RECORD_KEYS = Object.freeze([...CANONICAL_RECORD_KEYS]);

/**
 * The committed record's path: plugin-relative, with an override seam.
 *
 * **`VIBE_SUITE_AGY_GATE_FILE` is a testing seam, not a privilege boundary** — the same posture E1.1
 * documents for `VIBE_SUITE_CODEX_BIN`. It lets a fixture inject a simulated graduated record without
 * touching the committed one, and anyone able to set it already controls this process's environment,
 * so it grants nothing they did not already have. What it must never be mistaken for is enforcement:
 * the gate's authority is the committed file plus the humans who review changes to it.
 */
export function gateRecordPath(env = process.env) {
  if (env.VIBE_SUITE_AGY_GATE_FILE) return env.VIBE_SUITE_AGY_GATE_FILE;
  const pluginRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
  return path.join(pluginRoot, "tests", "agy-contract", "gate-status.json");
}

/** Load the record, or null when it cannot be read at all. Never throws. */
export function readGateRecord(env = process.env) {
  try {
    return JSON.parse(readFileSync(gateRecordPath(env), "utf8"));
  } catch {
    return null;
  }
}

/**
 * The gate verdict. `{ passed, reason, checks }` — `passed` is true only when everything agrees.
 */
export function resolveAgyGate(record) {
  if (record === null || typeof record !== "object" || Array.isArray(record)) {
    return { passed: false, reason: "no readable contract-gate record", checks: {} };
  }
  if (record.schema !== GATE_SCHEMA) {
    return { passed: false, reason: `unknown gate schema: ${record.schema}`, checks: {} };
  }
  // Exact shape, both levels. A record carrying unknown keys, or a check carrying unknown fields, is
  // not this schema — and a predicate that shrugs at unrecognised content is how a "passed" record
  // ends up meaning something nobody verified.
  const keys = Object.keys(record).sort();
  const expected = [...CANONICAL_RECORD_KEYS].sort();
  if (keys.length !== expected.length || keys.some((key, i) => key !== expected[i])) {
    return { passed: false, reason: `record keys are ${keys.join(",")}, expected ${expected.join(",")}`, checks: {} };
  }
  if (typeof record.checks !== "object" || record.checks === null || Array.isArray(record.checks)) {
    return { passed: false, reason: "checks is not an object", checks: {} };
  }
  const checks = record.checks;
  const checkNames = Object.keys(checks).sort();
  const expectedChecks = [...CANONICAL_CHECKS].sort();
  if (checkNames.length !== expectedChecks.length
      || checkNames.some((name, i) => name !== expectedChecks[i])) {
    return { passed: false, reason: `unexpected check set: ${checkNames.join(",")}`, checks };
  }
  for (const name of CANONICAL_CHECKS) {
    const entry = checks[name];
    if (typeof entry !== "object" || entry === null || Array.isArray(entry)) {
      return { passed: false, reason: `check '${name}' is not an object`, checks };
    }
    const fields = Object.keys(entry).sort();
    if (fields.length !== 2 || fields[0] !== "note" || fields[1] !== "state") {
      return { passed: false, reason: `check '${name}' has fields ${fields.join(",")}, expected note,state`, checks };
    }
    if (typeof entry.note !== "string") {
      return { passed: false, reason: `check '${name}' has a non-string note`, checks };
    }
  }
  for (const name of CANONICAL_CHECKS) {
    const state = checks[name]?.state;
    if (!CANONICAL_STATES.includes(state)) {
      return { passed: false, reason: `check '${name}' is missing or malformed`, checks };
    }
    if (state !== "passed") {
      return { passed: false, reason: `check '${name}' is ${state}`, checks };
    }
  }
  if (record.status !== "passed") {
    // Every check passed but the record does not say so: disagreement is corruption, not consent.
    return { passed: false, reason: `record status is '${record.status}'`, checks };
  }
  return { passed: true, reason: "contract gate passed", checks };
}

/** Convenience for the four consumers: read + resolve in one call. */
export function agyGate(env = process.env) {
  return resolveAgyGate(readGateRecord(env));
}
