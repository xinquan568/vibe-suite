// SPDX-License-Identifier: ISC
// Event-stream parsing (E1.1 / vibe-11).
//
// These live in `node:test` rather than the Python suite because the unit under test is a pure
// function over text: driving it through a subprocess would test the runner's plumbing instead of
// the parser, and would make a malformed-line case indistinguishable from a spawn failure.

import { strict as assert } from "node:assert";
import test from "node:test";

import { billableTokens, readEventStream } from "../../scripts/lib/events.mjs";

const line = (value) => JSON.stringify(value) + "\n";

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
  const { terminal } = readEventStream(line({ type: "item.completed", text: "partial" }));
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
