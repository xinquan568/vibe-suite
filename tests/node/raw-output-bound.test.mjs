// SPDX-License-Identifier: ISC
// Bounding `rawOutput` with a disclosed marker (vibe-274) — the Codex line-based lane.
//
// The agy character-boundary lane is #277's and is deliberately absent here.
//
// Every assertion is a BYTE COUNT or a MARKER COUNT, never a substring match on prose: the whole
// discriminator of this feature is size, so a test that asserts on text would pass with the
// allocator deleted. The fixtures are the counterexamples that defeated six designs across two
// issues; each is named for the review that produced it and each says which branch it kills.
//
// Marker width is `53 + digits(n)` including the trailing newline, so markerWidth(3)=54,
// markerWidth(40)=55, markerWidth(200)=56, markerWidth(1000)=57. Every expected total below was
// computed from that rule, not measured from an implementation.

import { strict as assert } from "node:assert";
import test from "node:test";
import {
  RAW_OUTPUT_BYTES, boundRawOutput, markerWidth, selectTopology,
} from "../../scripts/lib/render.mjs";

// ---------------------------------------------------------------------------
// Fixture helpers. `line(n)` is an n-byte line INCLUDING its trailing newline,
// so sizes in the tests are the sizes the allocator actually prices.
// ---------------------------------------------------------------------------

/** An n-byte line INCLUDING its newline. `ch` makes a line distinguishable: a run of one
 *  character contains every shorter run of it, so `includes` on same-character lines matches
 *  spuriously — that mistake made a budget test pass for the wrong reason. */
const line = (n, ch = "x") => ch.repeat(n - 1) + "\n";
const fragment = (n) => "x".repeat(n);

/** A completed agent_message event line of exactly `n` bytes, newline included. */
function controller(n, text = "ALLOW: ok") {
  const event = { type: "item.completed", item: { type: "agent_message", text } };
  const json = JSON.stringify(event);
  assert.ok(json.length + 1 <= n, `controller(${n}) too small for its own JSON`);
  // Pad inside the text so the line stays a parseable completed agent_message.
  const pad = n - 1 - json.length;
  const padded = { type: "item.completed", item: { type: "agent_message", text: text + "y".repeat(pad) } };
  const out = JSON.stringify(padded) + "\n";
  assert.equal(Buffer.byteLength(out, "utf8"), n, `controller(${n}) mis-sized`);
  return out;
}

const bytes = (s) => Buffer.byteLength(s, "utf8");
const markers = (s) => s.split("\n").filter((l) => l.startsWith(MARKER_PREFIX)).length;
const MARKER_PREFIX = "[vibe-274: ";

// ---------------------------------------------------------------------------
// Marker width — the rule every other expectation is derived from.
// ---------------------------------------------------------------------------

test("markerWidth is 53 + digits(n) and includes its trailing newline", () => {
  assert.equal(markerWidth(3), 54);
  assert.equal(markerWidth(40), 55);
  assert.equal(markerWidth(99), 55);
  assert.equal(markerWidth(100), 56);          // the digit boundary: 55 vs 56, NOT 56 vs 57
  assert.equal(markerWidth(200), 56);
  assert.equal(markerWidth(1000), 57);
  // The rendered marker is exactly as wide as it was priced, on both sides of two digit
  // boundaries. Only sizes above the marker's own width can be tested this way — a smaller source
  // is under budget and comes back byte-identical, with no marker at all.
  for (const n of [99, 100, 999, 1000]) {
    assert.ok(n > markerWidth(n), `fixture ${n} must exceed its own marker to be elidable`);
    assert.equal(bytes(renderedMarker(n)), markerWidth(n), `marker for ${n} bytes mis-priced`);
  }
});

function renderedMarker(n) {
  // The production renderer, reached through selectTopology's default seam: a one-line source
  // whose whole body is elided yields exactly one marker.
  const src = line(n);
  const out = boundRawOutput(src, markerWidth(n));
  assert.equal(markers(out), 1);
  return out;
}

test("the marker is NOT parseable JSON, so verdictFrom cannot fold it as an event", () => {
  const out = boundRawOutput(line(1000), markerWidth(1000));
  const markerLine = out.split("\n").find((l) => l.startsWith(MARKER_PREFIX));
  assert.throws(() => JSON.parse(markerLine), "marker must not be valid JSON (I5)");
});

// ---------------------------------------------------------------------------
// The two absent cases (decision 2) — `undefined` and `""` are NOT normalised.
// ---------------------------------------------------------------------------

test("a nullish input is returned unchanged, undefined distinct from null", () => {
  assert.equal(boundRawOutput(undefined, 100), undefined);
  assert.equal(boundRawOutput(null, 100), null);
});

test("under budget is byte-identical with no marker (acceptance bullet 5)", () => {
  // The trailing fragment is the discriminator. Re-assembling this source would place a marker
  // where the fragment is — the fragment is never retainable — so a result identical to the input
  // proves the under-cap fast path returned it verbatim rather than rebuilding it.
  const src = line(50) + line(50) + fragment(20);
  const out = boundRawOutput(src, 1000);
  assert.equal(out, src, "under-cap input must be returned verbatim, not reassembled");
  assert.equal(markers(out), 0);
});

test('an empty input returns "" through the identity fast path, not by synthesis', () => {
  assert.equal(boundRawOutput("", 100), "");
  assert.equal(markers(boundRawOutput("", 100)), 0);
});

// ---------------------------------------------------------------------------
// CM1 — drop `all` from the pre mode set.  cap 161.
// pre [2,2] · controller 100 · 1000-byte fragment
//   (all,empty)     2+2+100+57 = 161   ACCEPTED
//   (partial,empty) 2+54+100+57 = 213  over
//   (empty,empty)   54+100+57  = 211   over
// ---------------------------------------------------------------------------

const CM1 = line(2) + line(2) + controller(100) + fragment(1000);

test("CM1: pre-`all` is selected when only the whole pre side fits (cap 161)", () => {
  const out = boundRawOutput(CM1, 161);
  assert.equal(bytes(out), 161);
  assert.equal(markers(out), 1);
  assert.ok(out.startsWith(line(2) + line(2)), "the whole pre side is retained verbatim");
});

// ---------------------------------------------------------------------------
// CM2 / CM9 / F7 — cap 293.
// pre [80,100] · controller 100 · 1000-byte fragment
//   (all,empty)     80+100+100+57 = 337  over
//   (partial,empty) 80+56+100+57  = 293  ACCEPTED
//   (empty,empty)   56+100+57     = 213  fits, but lower retention
// ---------------------------------------------------------------------------

const CM2 = line(80) + line(100) + controller(100) + fragment(1000);

test("CM2: a partial pre side is selected, and it beats the empty topology (cap 293)", () => {
  const out = boundRawOutput(CM2, 293);
  assert.equal(bytes(out), 293, "must be 293 (partial), not 213 (empty)");
  assert.equal(markers(out), 2, "one marker for the omitted pre line, one for the fragment");
  assert.ok(out.startsWith(line(80)), "the retained pre prefix is byte-identical");
});

test("CM9: candidates are tried in DESCENDING retention (cap 293 gives 293, not 213)", () => {
  assert.equal(bytes(boundRawOutput(CM2, 293)), 293);
});

test("F7: a partial side is priced with its boundary line already fixed (cap 293)", () => {
  // Priced before fixing, the 80-byte residual's head allocation misses the boundary and the
  // result falls through to the 213-byte empty topology. 293 is only reachable when the boundary
  // line is part of the candidate's fixed content BEFORE it is priced.
  const out = boundRawOutput(CM2, 293);
  assert.notEqual(bytes(out), 213, "fell through to the empty topology — boundary not fixed first");
  assert.equal(bytes(out), 293);
});

// ---------------------------------------------------------------------------
// CM3 / CM4 — cap 6000, the production-sized fixed-point case (acceptance bullet 1).
// pre [4400,1000] · controller 2000 · post [3000]
//   (all,all)     4400+1000+2000+3000 = 10400 over
//   (partial,all) 4400+57+2000+3000   =  9457 over
//   (empty,all)   57+2000+3000        =  5057 ACCEPTED
//   (empty,empty) 57+2000+57          =  2114 the fallback when post-`all` is removed
// ---------------------------------------------------------------------------

const CM3 = line(4400) + line(1000) + controller(2000) + line(3000);

test("CM3/CM4: pre-`empty` with post-`all` (cap 6000) — bullet 1, production marker", () => {
  const out = boundRawOutput(CM3, 6000);
  assert.equal(bytes(out), 5057, "57 + 2000 + 3000");
  assert.equal(markers(out), 1);
  assert.ok(out.endsWith(line(3000)), "the whole post side is retained, not just a marker");
  // The controller appears exactly once, in source order, after the marker.
  const ctrl = controller(2000);
  assert.equal(out.split(ctrl).length - 1, 1, "controller exactly once");
  assert.ok(out.indexOf(ctrl) > out.indexOf(MARKER_PREFIX), "in source order");
});

// ---------------------------------------------------------------------------
// CM5 — drop `partial` from the post mode set.  cap 250.
// controller 100 (first) · post [100,80]
//   (·,all)     100+100+80 = 280  over
//   (·,partial) 100+56+80  = 236  ACCEPTED
//   (·,empty)   100+56     = 156  fits, but lower retention
// ---------------------------------------------------------------------------

const CM5 = controller(100) + line(100) + line(80);

test("CM5: a partial post side is selected over the empty one (cap 250)", () => {
  const out = boundRawOutput(CM5, 250);
  assert.equal(bytes(out), 236, "must be 236 (partial), not 156 (empty)");
  assert.equal(markers(out), 1);
  assert.ok(out.endsWith(line(80)), "the retained post suffix is byte-identical");
});

// ---------------------------------------------------------------------------
// CM6 — drop `empty` from the post mode set.  cap 160.
// controller 100 (first) · post [200,200]
//   (·,all)     100+200+200 = 500  over
//   (·,partial) 100+56+200  = 356  over
//   (·,empty)   100+56      = 156  ACCEPTED — the only feasible candidate
// ---------------------------------------------------------------------------

const CM6 = controller(100) + line(200) + line(200);

test("CM6: post-`empty` is the only feasible candidate and is reached (cap 160)", () => {
  const out = boundRawOutput(CM6, 160);
  assert.equal(bytes(out), 156, "100 + markerWidth(400)");
  assert.equal(markers(out), 1);
  assert.ok(out.startsWith(controller(100)), "the controller survives");
});

// ---------------------------------------------------------------------------
// CM7 / CM8 — the two regimes.
// ---------------------------------------------------------------------------

test("CM7: BOTH regimes are evaluated per mode pair, and the better one is taken", () => {
  // pre [100,400] · controller 100 · post [300,40,60], cap 412.
  // Under head-first the head reserves half the residual and cannot spend it, stranding those
  // bytes: the result is 372. Under head-empty the tail receives the whole residual and reaches
  // 412. Taking whichever regime is merely tried FIRST would return 372 and make the regime
  // distinction inert — the candidate key carries the regime precisely so both are priced.
  const src = line(100) + line(400) + controller(100) + line(300) + line(40) + line(60);
  const out = boundRawOutput(src, 412);
  assert.equal(bytes(out), 412, "372 means only the first regime was considered");
  assert.ok(bytes(out) <= 412, "never over cap");
});

test("CM8/F5: an empty head transfers its whole allocation to the tail (bullet 8)", () => {
  // The pre side cannot hold anything, so head-empty must give the tail the entire residual.
  const src = line(500) + controller(100) + line(40) + line(40);
  const cap = 100 + markerWidth(500) + 80;
  const out = boundRawOutput(src, cap);
  assert.equal(bytes(out), cap, "the tail received the entire residual");
  assert.ok(out.endsWith(line(40)));
});

test("F6: an empty tail does NOT transfer back to the head (bullet 8)", () => {
  // pre [100,100,100] · controller 100 · post [500], cap 420.
  //   (all,empty)     300+100+56 = 456  over — so the head MUST be partial
  //   (partial,empty) 100+56+100+56 = 312, residual 108
  // The head's own allocation is ceil(108/2) = 54, and the next line costs 100. It therefore
  // cannot be taken. Were the empty tail's 54 bytes transferred back, the head would have 108,
  // the line would fit, and the result would be 412. It must stay 312.
  const src = line(100) + line(100) + line(100) + controller(100) + line(500);
  const out = boundRawOutput(src, 420);
  assert.equal(bytes(out), 312, "412 means the empty tail transferred its allocation back");
  assert.equal(markers(out), 2);
});

// ---------------------------------------------------------------------------
// F4 — an odd residual gives the HEAD the extra byte, and it is the byte that
// decides. pre [100,60,1000] · controller 100 · post [500], cap 432.
//   (all,*) and (partial,all) are all far over cap
//   (partial,empty) floor 100+57+100+56 = 313, residual 119
//   head budget ceil(119/2) = 60, and the next head line costs exactly 60
// With floor(119/2) = 59 the line does not fit and the result stays 313.
// ---------------------------------------------------------------------------

test("F4: ceil, not floor — the odd byte is what admits the next head line", () => {
  const src = line(100) + line(60) + line(1000) + controller(100) + line(500);
  const out = boundRawOutput(src, 432);
  assert.equal(bytes(out), 373, "313 means the head was given floor(residual/2)");
  assert.ok(out.startsWith(line(100) + line(60)), "the 60-byte line was admitted");
});

// ---------------------------------------------------------------------------
// F5 — a head that can hold nothing transfers its WHOLE allocation to the tail.
// pre [200] · controller 100 · post [500,60,100], cap 575.
//   (all,all) 960 over; (all,partial) floor 200+100+56+100 = 456, residual 119
//   the head pool is empty, so the tail's budget is the full 119 and the
//   60-byte line (delta 60) fits. Split evenly the tail would get 59 and it would not.
// ---------------------------------------------------------------------------

test("F5: an empty head gives the tail the entire residual, not half (bullet 8)", () => {
  const src = line(200) + controller(100) + line(500) + line(60) + line(100);
  const out = boundRawOutput(src, 575);
  assert.equal(bytes(out), 516, "456 means the empty head kept half the residual");
  assert.ok(out.endsWith(line(60) + line(100)), "the tail grew backward from its boundary");
});

// ---------------------------------------------------------------------------
// S3 — a suppression run must never cross a controlling line. An EARLIER
// controller carries a stale verdict, and decision 8 calls surfacing that worse
// than surfacing none: the gate would present a superseded answer as current.
// ---------------------------------------------------------------------------

test("S3: suppression never retains an earlier, stale controlling event (I3)", () => {
  const stale = controller(100, "BLOCK: superseded");
  const current = controller(2000, "ALLOW: current");
  const src = stale + line(400) + current;
  // 2000 bytes cannot fit, so the controller stage fails and suppression runs. The stale 100-byte
  // event WOULD fit — it must still be excluded, because its run may not cross a controlling line.
  const out = boundRawOutput(src, 300);
  assert.ok(!out.includes(stale), "the stale controller must not survive suppression");
  assert.ok(!out.includes(current), "nor the oversized current one");
  assert.equal(markers(out), 1);
  assert.equal(bytes(out), markerWidth(bytes(src)));
});

// ---------------------------------------------------------------------------
// Suppression (I3) — cap 116.  Two markers around a retained suffix.
// forbidden 200 · keep 5 · fragment 40
//   markerWidth(200) + 5 + markerWidth(40) = 56 + 5 + 55 = 116  EXACTLY
// The source is 245 bytes, so it is genuinely over cap and cannot take the identity fast path.
// ---------------------------------------------------------------------------

const SUP = controller(200) + line(5) + fragment(40);

test("suppression retains a suffix between TWO omitted intervals (cap 116)", () => {
  assert.equal(bytes(SUP), 245, "fixture must be over cap, or it takes the identity path");
  const out = boundRawOutput(SUP, 116);
  assert.equal(bytes(out), 116, "56 + 5 + 55");
  assert.equal(markers(out), 2, "an omitted prefix and an omitted fragment are TWO intervals");
  assert.ok(out.includes(line(5)), "the allowed line between them is retained");
  for (const l of out.split("\n")) {
    if (!l.trim() || l.startsWith(MARKER_PREFIX)) continue;
    let ev = null;
    try { ev = JSON.parse(l); } catch { continue; }
    assert.ok(!(ev?.type === "item.completed" && ev.item?.type === "agent_message"),
      "no parseable completed agent_message may survive suppression (I3)");
  }
});

test("suppression returns the empty string only when even one marker will not fit", () => {
  const src = line(1000);
  assert.equal(boundRawOutput(src, markerWidth(1000) - 1), "");
  assert.equal(bytes(boundRawOutput(src, markerWidth(1000))), markerWidth(1000));
});

test("the controller stage signals no-candidate rather than returning a string (cap 60)", () => {
  // 200-byte controller · 2-byte line · 1-byte fragment. The controller stage's floor is
  // 200 + markerWidth(3) = 254, so it must return {ok:false}; suppression then yields 56.
  const src = controller(200) + line(2) + fragment(1);
  const stage = selectTopology({ text: src, cap: 60, mandatory: "controller" });
  assert.equal(stage.ok, false, "the controller stage must signal, not synthesize a string");
  assert.equal(bytes(boundRawOutput(src, 60)), 56, "suppression supplies the whole-source marker");
});

// ---------------------------------------------------------------------------
// P1 — the LAST controlling event wins, because that is how the Stop gate's
// verdictFrom fold resolves it (`text = event.item.text ?? text`).
// ---------------------------------------------------------------------------

test("P1: with two controlling events the LAST one is the mandatory core", () => {
  const first = controller(100, "BLOCK: stale");
  const last = controller(100, "ALLOW: current");
  const src = first + line(400) + last + line(300);
  // Only one controller can fit beside a marker for the rest; it must be the later one.
  const out = boundRawOutput(src, 100 + markerWidth(500) + 56);
  assert.ok(out.includes(last), "the last controlling event must survive");
  assert.ok(!out.includes(first), "the earlier, stale one must not");
});

test("P2: a nullish `text` is not a controlling event (acceptance bullet 4)", () => {
  const nullText = JSON.stringify(
    { type: "item.completed", item: { type: "agent_message", text: null } }) + "\n";
  const real = controller(100, "ALLOW: ok");
  const src = real + line(400) + nullText;
  const out = boundRawOutput(src, 100 + markerWidth(400 + bytes(nullText)));
  assert.ok(out.includes(real), "the real controller is the core, not the null-text event");
});

// ---------------------------------------------------------------------------
// Provenance (I1) and the fragment rule.
// ---------------------------------------------------------------------------

test("every retained line is complete and byte-identical, malformed included (bullet 6)", () => {
  // The malformed line must actually SURVIVE, or this asserts nothing about malformed lines. It
  // leads the source so a `partial` pre side fixes it as its boundary and keeps it.
  const malformed = "{not json at all\n";
  const src = malformed + line(300) + controller(100) + line(50);
  const out = boundRawOutput(src, 250);
  assert.ok(out.startsWith(malformed), "the malformed line is retained, byte-identical");
  assert.equal(bytes(out), 223, "17 + markerWidth(300) + 100 + 50");
  const sourceLines = new Set(src.split("\n").map((l) => l + "\n"));
  for (const l of out.split("\n")) {
    if (!l.trim() || l.startsWith(MARKER_PREFIX)) continue;
    assert.ok(sourceLines.has(l + "\n"), `retained line is not byte-identical: ${JSON.stringify(l)}`);
  }
});

test('bullet 4: `text: ""` IS a controlling event, `text: null` is not', () => {
  const empty = JSON.stringify(
    { type: "item.completed", item: { type: "agent_message", text: "" } }) + "\n";
  const earlier = controller(100, "ALLOW: earlier");
  // With an empty-text message last, IT is the core — it deliberately overrides the earlier verdict
  // with no verdict. With a null-text message last, the earlier one still is.
  const withEmpty = earlier + line(400) + empty;
  const outEmpty = boundRawOutput(withEmpty, bytes(empty) + markerWidth(500));
  assert.ok(outEmpty.includes(empty), "the empty-text message is the core");
  assert.ok(!outEmpty.includes(earlier), "and it displaces the earlier verdict");

  const withNull = earlier + line(400) + nullTextMessage;
  const outNull = boundRawOutput(withNull, 100 + markerWidth(400 + bytes(nullTextMessage)));
  assert.ok(outNull.includes(earlier), "a null-text message does not displace the earlier verdict");
});

test("the unterminated final fragment is never retained (decision 13)", () => {
  const src = controller(100) + fragment(200);
  const out = boundRawOutput(src, 160);
  assert.ok(!out.includes("x".repeat(200)), "the fragment must be inside an omitted interval");
  assert.equal(markers(out), 1);
});

// ---------------------------------------------------------------------------
// The cap boundary itself.
// ---------------------------------------------------------------------------

test("cap versus cap+1 straddles the boundary by exactly one byte", () => {
  const src = line(80) + line(100) + controller(100) + fragment(1000);
  assert.equal(bytes(boundRawOutput(src, 293)), 293);
  assert.ok(bytes(boundRawOutput(src, 292)) <= 292, "one byte less must still be in cap");
  assert.notEqual(bytes(boundRawOutput(src, 292)), 293);
});

test("RAW_OUTPUT_BYTES is the declared 128 KiB budget", () => {
  assert.equal(RAW_OUTPUT_BYTES, 128 * 1024);
});

// ---------------------------------------------------------------------------
// The renderMarker seam — the issue's ABSTRACT worked examples, which assume a
// synthetic 10-byte marker. These pin the SELECTION logic only and carry no
// acceptance claim; acceptance is demonstrated by the production-marker fixtures above.
// ---------------------------------------------------------------------------

/** A non-JSON marker of EXACTLY n bytes, newline included — the abstract examples fix the
 *  marker width so the selection can be read off the arithmetic. Asserted, not assumed. */
const mkFixed = (n) => {
  const text = "[" + ".".repeat(n - 3) + "]\n";
  assert.equal(bytes(text), n, `mkFixed(${n}) is not ${n} bytes`);
  return () => text;
};

test("seam: the issue's counterexample SHAPE selects (empty,all) — 10+100+30 = 140", () => {
  // The issue's abstract example uses a 20-byte controller, which no real completed
  // `agent_message` can be — its own JSON envelope is larger than that. The shape is preserved
  // (a large pre line, a small one, the controller, a post line) with the smallest controller the
  // predicate actually admits. This pins SELECTION only and carries no acceptance claim.
  const src = line(44) + line(10) + controller(100) + line(30);
  const r = selectTopology({ text: src, cap: 140, mandatory: "controller", renderMarker: mkFixed(10) });
  assert.equal(r.ok, true);
  assert.equal(bytes(r.text), 140);
});

test("seam: round-1's counterexample selects (empty,all) — 61+100+10 = 171", () => {
  const src = line(5) + line(155) + controller(100) + line(10);
  const r = selectTopology({ text: src, cap: 171, mandatory: "controller", renderMarker: mkFixed(61) });
  assert.equal(r.ok, true);
  assert.equal(bytes(r.text), 171);
});

// ---------------------------------------------------------------------------
// Step-8 blocker 1 — I3 forbids EVERY parseable completed `agent_message`
// surviving suppression, whatever its `text`. Decision 4's nullish rule says
// which message CONTROLS the verdict; it does not say a nullish one stops being
// a message. Drawing the suppression boundary with the narrower predicate let a
// `text: null` message through.
// ---------------------------------------------------------------------------

const nullTextMessage =
  JSON.stringify({ type: "item.completed", item: { type: "agent_message", text: null } }) + "\n";
const noTextMessage =
  JSON.stringify({ type: "item.completed", item: { type: "agent_message" } }) + "\n";

function assertNoCompletedAgentMessage(out, why) {
  for (const l of out.split("\n")) {
    if (!l.trim() || l.startsWith(MARKER_PREFIX)) continue;
    let ev = null;
    try { ev = JSON.parse(l); } catch { continue; }
    assert.ok(!(ev?.type === "item.completed" && ev.item?.type === "agent_message"),
      `${why}: a parseable completed agent_message survived — ${JSON.stringify(l).slice(0, 90)}`);
  }
}

for (const [label, trailer] of [["null", nullTextMessage], ["missing", noTextMessage]]) {
  test(`S4: suppression excludes a completed agent_message with ${label} text (I3)`, () => {
    const src = controller(2000, "ALLOW: current") + trailer;
    const out = boundRawOutput(src, 200);
    assertNoCompletedAgentMessage(out, `${label}-text trailer`);
    assert.equal(bytes(out), markerWidth(bytes(src)), "the whole capture is elided behind one marker");
  });
}

for (const [label, leader] of [["null", nullTextMessage], ["missing", noTextMessage]]) {
  test(`S4: the LEADING suppression run also stops at a ${label}-text message (I3)`, () => {
    // The trailing scan and the leading scan are separate code paths; a fixture that only puts the
    // message after the controller exercises one of them. Here it comes first.
    const src = leader + line(400) + controller(2000, "ALLOW: current");
    const out = boundRawOutput(src, 200);
    assertNoCompletedAgentMessage(out, `${label}-text leader`);
    assert.equal(bytes(out), markerWidth(bytes(src)), "the whole capture is elided behind one marker");
  });
}

test("a nullish-text message is still not the CONTROLLING core (decision 4)", () => {
  // The two predicates are different on purpose: this message is a completed agent_message for
  // suppression's boundary, and not a controller for core selection.
  const src = controller(100, "ALLOW: ok") + line(400) + nullTextMessage;
  const out = boundRawOutput(src, 100 + markerWidth(400 + bytes(nullTextMessage)));
  assert.ok(out.includes(controller(100, "ALLOW: ok")), "the real controller is the core");
});

// ---------------------------------------------------------------------------
// Step-8 blocker 2 — each side's budget is a ceiling on that side's TOTAL
// growth, measured from that side's own baseline. The old check compared
// cumulative growth against `spent + budget`, re-granting the allowance on every
// line, and charged head bytes against the tail's share.
// ---------------------------------------------------------------------------

test("B2: head and tail each spend their OWN budget, and both fit together", () => {
  // pre [A(100), h(40), pad(900)] · controller 100 · post [pad(900), t(40), B(100)].
  // Distinct fill characters: `h` and `t` cannot be found inside the padding by accident.
  const src = line(100, "A") + line(40, "h") + line(900, "p") + controller(100)
            + line(900, "q") + line(40, "t") + line(100, "B");
  // (partial,partial) floor = A + mk(h+p) + ctrl + mk(q+t) + B = 100+56+100+56+100 = 412.
  // A residual of 80 splits 40/40, and each side's own line costs exactly 40.
  const floor = 100 + markerWidth(940) + 100 + markerWidth(940) + 100;
  assert.equal(floor, 412, "floor arithmetic");
  const out = boundRawOutput(src, floor + 80);
  assert.equal(bytes(out), 492, "452 means one side was starved by the other");
  assert.ok(out.includes(line(40, "h")), "the head spent its own share");
  assert.ok(out.includes(line(40, "t")), "the tail spent its own share — not starved by the head");
});

test("B2: a side's budget is not re-granted per line", () => {
  // Three cheap head lines would each pass a per-line check but together exceed the head's share.
  const src = line(100) + line(40) + line(40) + line(40) + line(900) + controller(100) + line(900);
  const out = boundRawOutput(src, 400);
  assert.ok(bytes(out) <= 400, "never over cap");
  const head = out.slice(0, out.indexOf(MARKER_PREFIX));
  assert.ok(bytes(head) - 100 <= Math.ceil((400 - bytes(out) + bytes(head)) / 2) + 100,
    "the head cannot spend an allowance it was granted only once");
});

// ---------------------------------------------------------------------------
// Step-8 major 3 — candidate order is the APPROVED one: rank[pre] + rank[post],
// so a mode pair that retains something on BOTH sides outranks one that gives a
// whole side away. That is a provenance policy, not a byte-count policy: it can
// return fewer bytes, and deliberately does.
// ---------------------------------------------------------------------------

test("M3: (partial,all) outranks (all,empty) — the approved sum order", () => {
  const src = line(20) + line(180) + controller(100) + line(20) + line(80);
  const out = boundRawOutput(src, 360);
  assert.equal(bytes(out), 276,
    "356 means the base-3 order shipped: (all,empty) was reached before (partial,all)");
  assert.ok(out.endsWith(line(20) + line(80)), "the whole post side is retained");
});
