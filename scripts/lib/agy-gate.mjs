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

/** Every check that must be `passed` before the lane may be reached. */
export const MANDATORY_CHECKS = [
  "headless_invocation",
  "read_only_write_denied",
  "timeout_kill",
  "failure_signature",
  "quota_signature",
];

export const CHECK_STATES = new Set(["passed", "failed", "not_verified"]);

/** The committed record's path: plugin-relative, with a test-only override seam. */
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
  const checks = typeof record.checks === "object" && record.checks !== null ? record.checks : {};
  for (const name of MANDATORY_CHECKS) {
    const state = checks[name]?.state;
    if (!CHECK_STATES.has(state)) {
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
