// SPDX-License-Identifier: ISC
// Event-stream parsing (E1.1 / vibe-11).
//
// These live in `node:test` rather than the Python suite because the unit under test is a pure
// function over text: driving it through a subprocess would test the runner's plumbing instead of
// the parser, and would make a malformed-line case indistinguishable from a spawn failure.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { QUOTA_CODES, QUOTA_PHRASES, billableTokens, classifyFailure, readEventStream, verdictFromResult,
  verdictLineOf } from "../../scripts/lib/events.mjs";

const line = (value) => JSON.stringify(value) + "\n";
const EMITTER = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "fixtures", "fake-codex", "emitter.mjs");

test("captures the thread id from thread.started", () => {
  const { threadId } = readEventStream(line({ type: "thread.started", thread_id: "t_1" }));
  assert.equal(threadId, "t_1");
});

test("turn.completed is the only success signal", () => {
  const { terminal } = readEventStream(line({ type: "turn.completed", usage: {} }));
  assert.equal(terminal, "completed");
});

test("turn.failed is a failure even when the process exits 0", () => {
  const stream = line({ type: "thread.started", thread_id: "t_2" })
    + line({ type: "turn.failed", error: { message: "circuit open" } });
  const result = readEventStream(stream);
  assert.equal(result.terminal, "failed");
  assert.equal(result.errorMessage, "circuit open");
  assert.equal(result.threadId, "t_2");
});

test("a stream with no terminal event is not success", () => {
  const { terminal } = readEventStream(line({ type: "item.completed", item: { type: "agent_message", text: "partial" } }));
  assert.equal(terminal, null);
});

test("malformed and blank lines are counted, not fatal, and do not mask a terminal event", () => {
  const stream = "not json\n\n   \n" + line({ type: "turn.completed", usage: {} }) + "also not json\n";
  const result = readEventStream(stream);
  assert.equal(result.terminal, "completed");
  assert.equal(result.malformedLines, 2);
});

test("the first terminal event wins — a stream cannot un-fail", () => {
  const stream = line({ type: "turn.failed", error: { message: "first" } })
    + line({ type: "turn.completed", usage: {} });
  assert.equal(readEventStream(stream).terminal, "failed");
});

test("billing charges uncached input plus output, never the cached total", () => {
  // The real observation behind this: 4,399,535 input with 4,230,656 cached. Charging the total
  // overstates spend by an order of magnitude and trips budget stops that are false positives.
  assert.equal(billableTokens({ input_tokens: 100, cached_input_tokens: 60, output_tokens: 10 }), 50);
  assert.equal(billableTokens(null), null);
});

// vibe-202 (M27): the agent_message / errorCode / turn.usage / threadId-alt-key branches, and a
// meta-test that the canonical success fixture (emitter.mjs) actually DRIVES verdict capture.

test("agent_message: the LAST one wins as the verdict text", () => {
  const stream = line({ type: "item.completed", item: { type: "agent_message", text: "first" } })
    + line({ type: "item.completed", item: { type: "agent_message", text: "second" } });
  assert.equal(readEventStream(stream).agentMessage, "second");
});

test("agent_message: an empty message is captured as '', an absent one stays null", () => {
  // The distinction the Output-capture obligation preserves: "" (arrived, empty) is not null (never arrived).
  assert.equal(readEventStream(line({ type: "item.completed", item: { type: "agent_message", text: "" } })).agentMessage, "");
  assert.equal(readEventStream(line({ type: "turn.completed", usage: {} })).agentMessage, null);
});

test("errorCode: error.code wins over error.type, falls back to type, else null", () => {
  const both = readEventStream(line({ type: "turn.failed", error: { message: "m", code: "E_CIRCUIT", type: "circuit_open" } }));
  assert.equal(both.errorCode, "E_CIRCUIT");                       // code wins when BOTH present
  const typeOnly = readEventStream(line({ type: "turn.failed", error: { message: "m", type: "circuit_open" } }));
  assert.equal(typeOnly.errorCode, "circuit_open");               // falls back to type
  const neither = readEventStream(line({ type: "turn.failed", error: { message: "m" } }));
  assert.equal(neither.errorCode, null);                          // neither -> null
});

test("usage: event.usage wins over event.turn.usage, falls back to turn.usage", () => {
  const both = readEventStream(line({ type: "turn.completed", usage: { input_tokens: 1 }, turn: { usage: { input_tokens: 9 } } }));
  assert.deepEqual(both.usage, { input_tokens: 1 });              // direct wins when BOTH present
  const nestedOnly = readEventStream(line({ type: "turn.completed", turn: { usage: { input_tokens: 9 } } }));
  assert.deepEqual(nestedOnly.usage, { input_tokens: 9 });        // falls back to turn.usage
  const directOnly = readEventStream(line({ type: "turn.completed", usage: { input_tokens: 3 } }));
  assert.deepEqual(directOnly.usage, { input_tokens: 3 });
});

test("threadId: accepts the threadId alt-key as well as thread_id", () => {
  assert.equal(readEventStream(line({ type: "thread.started", threadId: "t_alt" })).threadId, "t_alt");
  assert.equal(readEventStream(line({ type: "thread.started", thread_id: "t_snake" })).threadId, "t_snake");
});

test("the canonical emitter fixture DRIVES verdict capture (real agent_message item shape)", () => {
  // Spawn the ACTUAL fixture so this test is coupled to emitter.mjs's shape, not a copied line:
  // `exec` satisfies assertArgvContract; closed stdin lets probeStdin() return at EOF.
  const r = spawnSync(process.execPath, [EMITTER, "exec"], { input: "", encoding: "utf8" });
  assert.equal(r.status, 0, `the fixture must exit 0: ${r.stderr}`);
  const parsed = readEventStream(r.stdout);
  assert.equal(parsed.terminal, "completed", "the fixture is a success stream");
  assert.equal(parsed.malformedLines, 1, "the fixture still exercises one malformed line");
  assert.equal(parsed.agentMessage, "fixture output",
    "the canonical success fixture must emit the real agent_message item so it drives verdict capture");
});


// ---- M6 / vibe-218: the one quota table and the classifier over it (vibe-301 deleted the plain-text markers)
test("classifyFailure: an error code in QUOTA_CODES is quota; a phrase hit is quota; neither is failure", () => {
  assert.equal(classifyFailure({ errorCode: "insufficient_quota", errorMessage: "" }), "quota");
  assert.equal(classifyFailure({ errorCode: null, errorMessage: "You have exceeded your usage cap" }), "quota");
  assert.equal(classifyFailure({ errorCode: "server_error", errorMessage: "boom" }), "failure");
  assert.ok(QUOTA_CODES.has("rate_limit_exceeded")); assert.equal(QUOTA_PHRASES.length, 7);
});

test("QUOTA_PHRASES: every regex is the DECIDING match for some input, and each such input classifies as quota", () => {
  // vibe-301 — coverage re-expressed, not deleted. `QUOTA_PHRASES.some(...)` stops at the FIRST match, so a regex is
  // exercised only when it decides an input. The deleted mentionsQuota test reached some of these only through strings
  // its plain markers caught first; two regexes (`quota`, `exceeded your`) decided no input anywhere. Each row below is
  // decided by its own regex and classifies as `failure` with that regex removed, so no row can pass through another.
  const decides = [
    [0, "quota reached for this API key"],
    [1, "rate-limited: retry after 30s"],
    [2, "usage cap hit for the billing period"],
    [3, "you have exceeded your monthly allowance"],
    [4, "HTTP 429: Too Many Requests"],
    [5, "resource exhausted on the shard"],
    [6, "account is out of credit"],
  ];
  for (const [index, message] of decides) {
    assert.equal(QUOTA_PHRASES.findIndex((pattern) => pattern.test(message)), index,
      `"${message}" is not decided by QUOTA_PHRASES[${index}]`);
    assert.equal(classifyFailure({ errorCode: null, errorMessage: message }), "quota", message);
  }
  assert.deepEqual(decides.map(([index]) => index), QUOTA_PHRASES.map((_, index) => index),
    "every regex in QUOTA_PHRASES needs a row that it decides");
});

// ---------------------------------------------------------------------------
// vibe-305 — the verdict rule, and result-line precedence.
// ---------------------------------------------------------------------------

test("vibe-305: verdictLineOf keeps only a line that already carries a verdict", () => {
  assert.equal(verdictLineOf(null), null, "absent");
  assert.equal(verdictLineOf(""), null, "empty");
  assert.equal(verdictLineOf("thinking out loud"), null, "present but not a verdict");
  assert.equal(verdictLineOf("\n\n  ALLOW: ok  \ntrailing"), "ALLOW: ok", "first non-empty line, trimmed");
  // `.` cannot cross a line terminator, so this does not match — and MUST NOT, or bounding it
  // later could produce a verdict the engine never gave.
  assert.equal(verdictLineOf("ALLOW: ok then more"), null, "U+2028 line is not a verdict");
});

test("vibe-305: precedence is by property PRESENCE, not truthiness", () => {
  const capture = JSON.stringify({ type: "item.completed", item: { type: "agent_message", text: "BLOCK: stale" } }) + "\n";

  // legacy line — no `verdictLine` property at all — falls back to the capture
  assert.deepEqual(verdictFromResult({ rawOutput: capture }), { verdict: "BLOCK", reason: "stale" });

  // authoritative null must NOT resurrect the capture's verdict
  assert.equal(verdictFromResult({ verdictLine: null, rawOutput: capture }), null,
    "an authoritative null is an answer, not a gap");

  // a carried verdict wins over a different parseable capture
  assert.deepEqual(verdictFromResult({ verdictLine: "ALLOW: fresh", rawOutput: capture }),
    { verdict: "ALLOW", reason: "fresh" }, "the carried verdict wins");

  // neither source yields one
  assert.equal(verdictFromResult({ verdictLine: null, rawOutput: "" }), null);
});
