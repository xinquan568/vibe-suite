// SPDX-License-Identifier: ISC
// The agy → codex → manual chain (E1.7 / vibe-17). Every row of the documented state machine, with
// the observable contract asserted: which result is the caller's, whether the diagnostic header was
// emitted, and the exit code. These run regardless of whether agy exists on this machine.

import { strict as assert } from "node:assert";
import test from "node:test";

import { EXIT, isUnreachable, runWithFallback } from "../../scripts/lib/agy-fallback.mjs";

const done = (engine, output = "analysis") =>
  ({ jobId: `job_${engine}`, status: "completed", threadId: null, rawOutput: output });
const failed = (error) => ({ jobId: "job_x", status: "failed", threadId: null, rawOutput: "", error });
const timedOut = () => ({ jobId: "job_t", status: "timed_out", threadId: null, rawOutput: "", error: "deadline exceeded" });

function harness({ agy, codex }) {
  const headers = [];
  return {
    headers,
    deps: {
      runAgy: async () => agy,
      runCodex: async () => codex,
      emitHeader: (text) => headers.push(text),
    },
  };
}

test("agy answers: its result is the caller's, and no header is emitted", async () => {
  const { deps, headers } = harness({ agy: done("agy"), codex: done("codex") });
  const outcome = await runWithFallback(deps);
  assert.equal(outcome.outcome, "agy");
  assert.equal(outcome.result.jobId, "job_agy");
  assert.deepEqual(headers, [], "nothing was unreachable, so nothing is disclosed");
  assert.equal(outcome.exitCode, EXIT.ok);
});

test("every unreachable class hands off to codex WITH the header", async () => {
  for (const agy of [null, failed("agy-not-found"), failed("unauthenticated"), failed("quota"), timedOut()]) {
    const { deps, headers } = harness({ agy, codex: done("codex") });
    const outcome = await runWithFallback(deps);
    assert.equal(outcome.outcome, "codex", `agy=${JSON.stringify(agy)}`);
    assert.equal(outcome.result.jobId, "job_codex", "the caller gets exactly one result — codex's");
    assert.equal(headers.length, 1, "unreachability must be disclosed");
    assert.match(headers[0], /unreachable/);
    assert.match(headers[0], /preflight/, "the header carries an actionable remedy");
    assert.equal(outcome.exitCode, EXIT.ok);
  }
});

test("agy answered uselessly: hand off WITHOUT a header — it was reached", async () => {
  const { deps, headers } = harness({ agy: done("agy", "   "), codex: done("codex") });
  const outcome = await runWithFallback(deps);
  assert.equal(outcome.outcome, "codex-no-header");
  assert.equal(outcome.header, false);
  assert.deepEqual(headers, [],
    "announcing unreachability for an engine that answered would be a lie");
  assert.equal(outcome.exitCode, EXIT.ok);
});

test("both unreachable: a stable manual signal and a distinct exit code", async () => {
  const { deps, headers } = harness({ agy: failed("unauthenticated"), codex: null });
  const outcome = await runWithFallback(deps);
  assert.equal(outcome.outcome, "manual");
  assert.equal(outcome.result, null, "no invented result line when nothing ran");
  assert.deepEqual(outcome.signal, { fallback: "manual", reason: "no engine available" });
  assert.equal(outcome.exitCode, EXIT.manual);
  assert.notEqual(EXIT.manual, EXIT.ok, "manual must be distinguishable from success");
  assert.notEqual(EXIT.manual, 2, "…and from a usage error");
  assert.equal(headers.length, 2, "both hand-offs are disclosed");
});

test("the unreachable classification is explicit, not incidental", () => {
  assert.equal(isUnreachable(null), true);
  assert.equal(isUnreachable(timedOut()), true);
  assert.equal(isUnreachable(failed("quota")), true);
  assert.equal(isUnreachable(done("agy")), false);
  assert.equal(isUnreachable({ status: "completed", rawOutput: "" }), false,
    "an empty answer is unusable, not unreachable — a different row of the table");
});
