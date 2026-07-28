// SPDX-License-Identifier: ISC
// The contract probe's RECORDER (E1.7 / vibe-17) — driven with injected outcomes, so every
// fail-closed state is provable without a real agy and without CI ever touching one.
//
// The property under test is epistemic: the probe may only record what it observed. Its most
// important refusal is the one that looks like success — a model claiming it was denied a write.

import { strict as assert } from "node:assert";
import test from "node:test";

import { probeContract, SENTINEL } from "../../scripts/agy-contract-probe.mjs";
import { resolveAgyGate } from "../../scripts/lib/agy-gate.mjs";

const OK = { stdout: "ok\n", stderr: "", spawnFailed: false };
const UNAUTH = {
  stdout: "Authentication required. Please visit the URL to log in:\n", stderr: "", spawnFailed: false,
};
const MISSING = { stdout: "", stderr: "spawn agy ENOENT", spawnFailed: true };

const probe = (opts) => probeContract({
  run: async () => opts.outcome,
  sentinelExists: () => opts.landed ?? false,
  now: () => "2026-07-28T00:00:00Z",
  version: "1.1.2",
  ...opts.extra,
});

test("a model CLAIMING it was denied is not evidence — the check stays not_verified", async () => {
  // The unauthenticated CLI never ran a turn, so the sentinel's absence proves nothing about
  // enforcement. This is the exact reasoning error the gate exists to prevent.
  const record = await probe({ outcome: UNAUTH, landed: false });
  assert.equal(record.checks.read_only_write_denied.state, "not_verified");
  assert.match(record.checks.read_only_write_denied.note, /proves nothing about enforcement/);
  assert.equal(record.status, "not_passed");
});

test("a write that LANDS fails the check outright", async () => {
  const record = await probe({ outcome: OK, landed: true });
  assert.equal(record.checks.read_only_write_denied.state, "failed");
  assert.ok(record.checks.read_only_write_denied.note.includes(SENTINEL));
  assert.equal(record.status, "not_passed");
});

test("an authenticated turn whose write does not land passes that check", async () => {
  const record = await probe({ outcome: OK, landed: false });
  assert.equal(record.checks.read_only_write_denied.state, "passed");
  assert.equal(record.checks.headless_invocation.state, "passed");
});

test("unprovoked failure and quota signatures stay not_verified, and keep the gate shut", async () => {
  const record = await probe({ outcome: OK, landed: false, extra: { timeoutKillProven: true } });
  assert.equal(record.checks.failure_signature.state, "not_verified");
  assert.equal(record.checks.quota_signature.state, "not_verified");
  assert.equal(record.status, "not_passed", "not seeing a quota error is not handling one");
  assert.equal(resolveAgyGate(record).passed, false);
});

test("only a fully observed run records passed — and the resolver then agrees", async () => {
  const record = await probe({
    outcome: OK, landed: false,
    extra: { timeoutKillProven: true, provokedFailure: "5xx", provokedQuota: "resource exhausted" },
  });
  assert.equal(record.status, "passed");
  for (const check of Object.values(record.checks)) assert.equal(check.state, "passed");
  assert.equal(resolveAgyGate(record).passed, true);
});

test("a missing binary and an unauthenticated CLI both fail headless invocation", async () => {
  assert.equal((await probe({ outcome: MISSING })).checks.headless_invocation.state, "failed");
  const unauth = await probe({ outcome: UNAUTH });
  assert.equal(unauth.checks.headless_invocation.state, "failed");
  assert.match(unauth.checks.failure_signature.note, /UNAUTHENTICATED/);
});

test("the record is schema-1 shaped and timestamped from the injected clock", async () => {
  const record = await probe({ outcome: OK, landed: false });
  assert.equal(record.schema, 1);
  assert.equal(record.recorded_at, "2026-07-28T00:00:00Z");
  assert.equal(record.agy_version, "1.1.2");
});
