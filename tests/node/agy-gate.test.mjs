// SPDX-License-Identifier: ISC
// The agy contract gate (E1.7 / vibe-17): one record, one resolver, one strict predicate.
//
// The property that matters most is the one a future maintainer will be tempted to soften: the
// lane cannot open by accident. A record whose top-level status disagrees with its checks is
// corruption, not consent; an unreadable record is a closed gate, not an exception.

import { strict as assert } from "node:assert";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  agyGate, gateRecordPath, MANDATORY_CHECKS, readGateRecord, resolveAgyGate,
} from "../../scripts/lib/agy-gate.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const allPassed = () => ({
  schema: 1, status: "passed", agy_version: "1.1.2", recorded_at: "2026-07-28T00:00:00Z",
  checks: Object.fromEntries(MANDATORY_CHECKS.map((name) => [name, { state: "passed", note: "" }])),
});

function recordFile(record) {
  const dir = mkdtempSync(path.join(tmpdir(), "agy-gate-"));
  const file = path.join(dir, "gate-status.json");
  writeFileSync(file, typeof record === "string" ? record : JSON.stringify(record));
  return file;
}

test("the committed production record is not_passed, and the lane is therefore shut", () => {
  const record = readGateRecord({});
  assert.ok(record, `the committed record must exist at ${gateRecordPath({})}`);
  assert.equal(record.status, "not_passed",
    "shipping a passed gate would graduate the agy lane on an unconfirmed contract");
  const verdict = resolveAgyGate(record);
  assert.equal(verdict.passed, false);
  assert.match(verdict.reason, /not_verified|not_passed|check/);
});

test("the record resolves from the PLUGIN root, not the caller's cwd", () => {
  // The runner's cwd is the user's workspace, where no record exists. Resolving there would wedge
  // the gate closed forever and make the eventual flip unobservable.
  assert.equal(gateRecordPath({}), path.join(REPO_ROOT, "tests", "agy-contract", "gate-status.json"));
  const seam = recordFile(allPassed());
  assert.equal(gateRecordPath({ VIBE_SUITE_AGY_GATE_FILE: seam }), seam);
  assert.equal(agyGate({ VIBE_SUITE_AGY_GATE_FILE: seam }).passed, true);
});

test("every mandatory check must be exactly passed", () => {
  for (const name of MANDATORY_CHECKS) {
    for (const state of ["failed", "not_verified"]) {
      const record = allPassed();
      record.checks[name] = { state, note: "" };
      const verdict = resolveAgyGate(record);
      assert.equal(verdict.passed, false, `${name}=${state} must not pass`);
      assert.ok(verdict.reason.includes(name), verdict.reason);
    }
    const missing = allPassed();
    delete missing.checks[name];
    assert.equal(resolveAgyGate(missing).passed, false, `${name} missing must not pass`);
  }
});

test("status and checks must agree — disagreement is corruption, not consent", () => {
  const claimsPassed = allPassed();
  claimsPassed.status = "not_passed";
  assert.equal(resolveAgyGate(claimsPassed).passed, false, "checks alone do not open the gate");

  const lies = allPassed();
  lies.checks.read_only_write_denied = { state: "not_verified", note: "" };
  const verdict = resolveAgyGate(lies);            // status says passed, a check does not
  assert.equal(verdict.passed, false);
  assert.ok(verdict.reason.includes("read_only_write_denied"), verdict.reason);
});

test("unreadable, malformed and wrong-schema records are closed gates, never throws", () => {
  for (const input of [null, undefined, 42, "text", [], {}, { schema: 2, status: "passed" }]) {
    const verdict = resolveAgyGate(input);
    assert.equal(verdict.passed, false, `input ${JSON.stringify(input)} must not pass`);
    assert.equal(typeof verdict.reason, "string");
  }
  assert.equal(agyGate({ VIBE_SUITE_AGY_GATE_FILE: "/nonexistent/gate.json" }).passed, false);
  assert.equal(agyGate({ VIBE_SUITE_AGY_GATE_FILE: recordFile("{ not json") }).passed, false);
  const state = { state: "sideways", note: "" };
  const bad = allPassed();
  bad.checks.timeout_kill = state;
  assert.equal(resolveAgyGate(bad).passed, false, "an unknown check state is malformed");
});

test("the flip needs more than a record: the checklist and the doctor notice must exist", () => {
  // A single edited file must not be able to graduate the lane.
  const checklist = path.join(REPO_ROOT, "docs", "agy-flip-checklist.md");
  const text = readFileSync(checklist, "utf8");
  assert.ok(text, "docs/agy-flip-checklist.md must exist before any flip is possible");
  assert.ok(text.includes("doctor notice"), "the checklist must specify the doctor notice");
  for (const name of MANDATORY_CHECKS) {
    assert.ok(text.includes(name), `the checklist must enumerate ${name}`);
  }
});

test("the shipped cross-model audit default is still codex", () => {
  const partial = readFileSync(
    path.join(REPO_ROOT, "commands", "shared", "model-selection.md"), "utf8");
  assert.ok(/pre-gate default\s*\|\s*`?codex`?/.test(partial),
    "the staged default must read codex while the gate is shut");
});

test("extra and malformed fields fail closed — an unrecognised record is not this schema", () => {
  const withExtraTopLevel = { ...allPassed(), unexpected: true };
  assert.equal(resolveAgyGate(withExtraTopLevel).passed, false, "extra top-level key must not pass");

  const withExtraCheck = allPassed();
  withExtraCheck.checks.invented_check = { state: "passed", note: "" };
  assert.equal(resolveAgyGate(withExtraCheck).passed, false, "extra check must not pass");

  const withExtraField = allPassed();
  withExtraField.checks.timeout_kill = { state: "passed", note: "", forced: true };
  assert.equal(resolveAgyGate(withExtraField).passed, false, "extra check field must not pass");

  const nonStringNote = allPassed();
  nonStringNote.checks.timeout_kill = { state: "passed", note: 42 };
  assert.equal(resolveAgyGate(nonStringNote).passed, false);

  const missingTopLevel = allPassed();
  delete missingTopLevel.agy_version;
  assert.equal(resolveAgyGate(missingTopLevel).passed, false, "a missing key is also a shape change");
});
