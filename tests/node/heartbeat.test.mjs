// SPDX-License-Identifier: ISC
// Heartbeat cadence (E1.1 / vibe-11).
//
// The production interval is 30 s, which no test should ever wait for. `VIBE_SUITE_HEARTBEAT_MS`
// makes the interval injectable so the cadence is observable in milliseconds — and so the
// *cessation* of beats at termination is observable at all, which is the half a subprocess test
// cannot see cleanly.

import { strict as assert } from "node:assert";
import { readFileSync } from "node:fs";
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

// T3b (vibe-205 / W3) -----------------------------------------------------------------------------
// The cost of a beat is not visible from `DEFAULT_HEARTBEAT_MS` itself: a beat is a full record
// transaction, and someone lowering the interval needs to know that before they lower it. The
// comment is the deliverable, so the comment is what is asserted — a reader who deletes it should
// see a test fail, not discover the cost in production.
test("T3b: the beat's fsync cost and the sidecar alternative are documented at the constant", () => {
  const src = readFileSync(new URL("../../scripts/lib/process.mjs", import.meta.url), "utf8");
  // Step-9 iteration 2: substring `indexOf` bound to a COMMENT containing the declaration text,
  // which ended the slice before a citation that followed it. Anchor on real declaration lines only
  // -- `^export const` cannot match inside a `//` comment -- and require each to be unique, so a
  // duplicated or shadowed declaration fails loudly instead of silently moving the window.
  const declIndex = (name) => {
    const hits = [...src.matchAll(new RegExp(`^export const ${name}\\b`, "gm"))];
    assert.equal(hits.length, 1, `${name} must have exactly one declaration line, found ${hits.length}`);
    return hits[0].index;
  };
  const graceAt = declIndex("DEFAULT_GRACE_MS");
  const at = declIndex("DEFAULT_HEARTBEAT_MS");
  assert.ok(graceAt < at, "DEFAULT_GRACE_MS no longer precedes it; retarget the slice");
  // Step-9 finding 1: slicing from the LAST `// vibe-205` marker left a hole — a citation placed
  // just BEFORE the marker, still directly above the constant, escaped every assertion below. The
  // region is now the whole gap between the two constants, so nothing above the note can hide.
  const note = src.slice(src.indexOf("\n", graceAt) + 1, at);
  assert.ok(note.trim().startsWith("// vibe-205"),
    "the cost note is missing, or something now sits between it and DEFAULT_GRACE_MS");
  assert.match(note, /FOUR `handle\.sync\(\)`/,
    "the note no longer states the measured four-sync cost of an uncontended beat");
  assert.match(note, /publishNew/, "the note no longer names the publishing half of the transaction");
  assert.match(note, /writeAtomic/, "the note no longer names the commit half of the transaction");
  assert.match(note, /`stage`/, "the note no longer names the staging half of each sync pair");
  assert.match(note, /`syncDir`/, "the note no longer names the directory-sync half of each pair");
  // Step-8 finding 2: the note originally cited jobs.mjs:637/:572, correct at the base commit and
  // stale by the time this branch committed — this change's own edit to jobs.mjs moved them. The
  // fix was to drop line citations entirely; this assertion is what stops them coming back.
  // THE CITATION GUARD IS WHOLE-FILE, DELIBERATELY WINDOWLESS.
  // Three attempts to locate a region were each defeated by text imitating the anchor: the last
  // `// vibe-205` marker, then a substring match on the declaration, then a block-comment decoy
  // supplying the only line-anchored match while a leading space hid the real export. Every
  // text-located window can be spoofed by text. There is nothing to spoof if the property is
  // asserted over the entire file — and process.mjs legitimately carries no line citation at all,
  // so the strict form is also the honest one.
  assert.doesNotMatch(src, /\.mjs:\d+/,
    "a line-number citation appeared in process.mjs; those go stale silently when the cited file " +
    "moves, which is exactly what happened to this note's first draft");
  assert.match(note, /sidecar `<jobId>\.heartbeatAt`/, "the sidecar design note is missing");
  assert.match(note, /NOT implemented/,
    "the sidecar note must stay marked as a considered alternative, not pending work");
});
