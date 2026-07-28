// SPDX-License-Identifier: ISC
// Heartbeat cadence (E1.1 / vibe-11).
//
// The production interval is 30 s, which no test should ever wait for. `VIBE_SUITE_HEARTBEAT_MS`
// makes the interval injectable so the cadence is observable in milliseconds — and so the
// *cessation* of beats at termination is observable at all, which is the half a subprocess test
// cannot see cleanly.

import { strict as assert } from "node:assert";
import test from "node:test";

import { DEFAULT_HEARTBEAT_MS, heartbeatInterval, runWithDeadline } from "../../scripts/lib/process.mjs";

test("defaults to the 30 s production interval", () => {
  assert.equal(heartbeatInterval({}), DEFAULT_HEARTBEAT_MS);
  assert.equal(heartbeatInterval({ VIBE_SUITE_HEARTBEAT_MS: "not-a-number" }), DEFAULT_HEARTBEAT_MS);
  assert.equal(heartbeatInterval({ VIBE_SUITE_HEARTBEAT_MS: "0" }), DEFAULT_HEARTBEAT_MS);
});

test("honours an injected interval", () => {
  assert.equal(heartbeatInterval({ VIBE_SUITE_HEARTBEAT_MS: "25" }), 25);
});

test("beats while the child runs and stops once it exits", async () => {
  let beats = 0;
  await runWithDeadline({
    command: process.execPath,
    args: ["-e", "setTimeout(() => {}, 220)"],
    timeoutMs: 5000,
    heartbeatMs: 30,
    onHeartbeat: () => { beats += 1; },
  });
  const atExit = beats;
  assert.ok(atExit >= 2, `expected repeated beats while running, saw ${atExit}`);

  await new Promise((resolve) => setTimeout(resolve, 150));
  assert.equal(beats, atExit, "the heartbeat interval outlived the child");
});

test("a deadline escalates to SIGKILL against a child that ignores SIGTERM", async () => {
  const outcome = await runWithDeadline({
    command: process.execPath,
    args: ["-e", "process.on('SIGTERM', () => {}); setInterval(() => {}, 50);"],
    timeoutMs: 150,
    graceMs: 150,
  });
  assert.equal(outcome.timedOut, true);
  assert.equal(outcome.killedHard, true, "SIGTERM was ignored; SIGKILL must have followed");
});
