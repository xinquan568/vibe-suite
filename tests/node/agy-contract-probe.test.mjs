// SPDX-License-Identifier: ISC
// The contract probe's RECORDER (E1.7 / vibe-17), driven with injected outcomes.
//
// The harness answers DIFFERENT calls DIFFERENTLY. That is not a stylistic choice: round 1's harness
// returned one outcome for every invocation, which is exactly why it could not detect the blocker —
// a check reading a *different* call's context looks correct when every call says the same thing.
//
// The property under test is epistemic. `read_only_write_denied` can only be `passed` on positive,
// tooling-originated evidence of a refused write; agy offers no such channel, so it never passes —
// and no amount of the model *saying* it was denied changes that.

import { strict as assert } from "node:assert";
import test from "node:test";

import { classifyWriteProbe, probeContract, SENTINEL } from "../../scripts/agy-contract-probe.mjs";
import { resolveAgyGate } from "../../scripts/lib/agy-gate.mjs";

const ok = (stdout = "ok\n") => ({ stdout, stderr: "", timedOut: false, spawnFailed: false, groupReaped: true });
const UNAUTH = ok("Authentication required. Please visit the URL to log in:\n");
const MISSING = { stdout: "", stderr: "ENOENT", timedOut: false, spawnFailed: true };
const TIMED_OUT = { stdout: "", stderr: "", timedOut: true, spawnFailed: false, groupReaped: true };

/** Answer per PHASE: `--version`-less print calls are told apart by their prompt text. */
function phased({ headless = ok(), write = ok(), fallback = ok() }) {
  return async (args) => {
    const prompt = String(args.at(-1) ?? "");
    if (prompt.includes(SENTINEL)) return write;
    if (prompt.includes("Reply with exactly")) return headless;
    return fallback;
  };
}

const record = (opts) => probeContract({
  run: phased(opts),
  sentinelExists: () => opts.landed ?? false,
  now: () => "2026-07-28T00:00:00Z",
  version: "1.1.2",
  ...opts.extra,
});

test("THE BLOCKER: a healthy headless call cannot vouch for a failed write call", async () => {
  // Round 1 recorded `passed` here: the headless probe authenticated fine, the write probe timed
  // out, the sentinel was absent (nothing ran), and absence was read as enforcement.
  for (const write of [TIMED_OUT, MISSING, UNAUTH, ok(""), ok("Error: something generic\n")]) {
    const result = await record({ headless: ok(), write, landed: false });
    assert.equal(result.checks.read_only_write_denied.state, "not_verified",
      `write outcome ${JSON.stringify(write).slice(0, 60)} must not pass`);
    assert.equal(result.status, "not_passed");
    assert.equal(resolveAgyGate(result).passed, false);
  }
});

test("ADVERSARIAL: the model saying it was denied is not the tooling denying it", async () => {
  // Every phrase a signature scanner might have accepted, emitted as ordinary model output.
  const claims = [
    "The sandbox denied the write.",
    "permission denied: read-only filesystem",
    "Tool permission request rejected — write blocked by sandbox policy.",
    "I attempted to write the file and the sandbox denied it.",
    "operation not permitted (EACCES)",
  ];
  for (const claim of claims) {
    const result = await record({ headless: ok(), write: ok(`${claim}\n`), landed: false });
    assert.equal(result.checks.read_only_write_denied.state, "not_verified",
      `a model claim must never pass the check: ${claim}`);
    assert.match(result.checks.read_only_write_denied.note, /provenance|model's own words/);
  }
});

test("a write that LANDS fails the check outright — that IS positive evidence", async () => {
  const result = await record({ headless: ok(), write: ok(), landed: true });
  assert.equal(result.checks.read_only_write_denied.state, "failed");
  assert.ok(result.checks.read_only_write_denied.note.includes(SENTINEL));
});

test("classifyWriteProbe never returns passed on today's agy surface", () => {
  const inputs = [null, MISSING, TIMED_OUT, UNAUTH, ok(""), ok("anything at all")];
  for (const input of inputs) {
    assert.notEqual(classifyWriteProbe(input, false).state, "passed",
      `no input may pass while there is no tooling-only denial channel: ${JSON.stringify(input)}`);
  }
  assert.equal(classifyWriteProbe(ok(), true).state, "failed");
});

test("timeout_kill is observed, not asserted: it needs a real kill AND a confirmed reap", async () => {
  const unconfirmed = await record({
    extra: { timeoutProbe: { timedOut: true, groupReaped: false } },
  });
  assert.equal(unconfirmed.checks.timeout_kill.state, "not_verified");
  assert.match(unconfirmed.checks.timeout_kill.note, /groupReaped=false/);

  const asserted = await record({ extra: { timeoutProbe: { timedOut: false, groupReaped: true } } });
  assert.equal(asserted.checks.timeout_kill.state, "not_verified",
    "an invocation that was never killed cannot evidence the kill");

  const real = await record({ extra: { timeoutProbe: { timedOut: true, groupReaped: true } } });
  assert.equal(real.checks.timeout_kill.state, "passed");
});

test("signature checks need a provoked outcome the runner's own classifier agrees with", async () => {
  const none = await record({});
  assert.equal(none.checks.failure_signature.state, "not_verified");
  assert.equal(none.checks.quota_signature.state, "not_verified");

  const provoked = await record({
    extra: {
      failureProbe: { stdout: "", stderr: "ENOENT", spawnFailed: true },
      quotaProbe: { stdout: "Error: resource exhausted — quota exceeded\n", groupReaped: true },
    },
  });
  assert.equal(provoked.checks.quota_signature.state, "passed");
  assert.match(provoked.checks.quota_signature.note, /quota/);
  assert.equal(provoked.checks.failure_signature.state, "passed");

  const mislabelled = await record({ extra: { quotaProbe: ok("all good") } });
  assert.equal(mislabelled.checks.quota_signature.state, "not_verified",
    "a caller cannot label a healthy response as a quota signature");
});

test("the record stays schema-1 shaped, and no combination graduates the gate today", async () => {
  const result = await record({
    headless: ok(), write: ok("permission denied"), landed: false,
    extra: {
      timeoutProbe: { timedOut: true, groupReaped: true },
      failureProbe: { spawnFailed: true },
      quotaProbe: { stdout: "quota exceeded", groupReaped: true },
    },
  });
  assert.equal(result.schema, 1);
  assert.equal(result.recorded_at, "2026-07-28T00:00:00Z");
  assert.equal(result.status, "not_passed",
    "four of five checks can pass; the write check cannot, so the lane stays shut");
  assert.equal(resolveAgyGate(result).passed, false);
});
