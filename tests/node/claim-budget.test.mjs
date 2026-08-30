// SPDX-License-Identifier: ISC
// The claim-handshake budget seam and its failure message (vibe-209 / grill P4 · A14).
//
// `awaitWorkerClaim` waited a hard-coded 5 s and, on expiry, reported "worker did not start, or was
// terminated before claiming" — a sentence naming neither how long it waited nor which process it
// waited for. Grill A14: *"Cold Node start on a loaded box can exceed it."* So the budget becomes an
// operator seam that adjusts **upward**, and the message names both facts.
//
// **Why the seam lives in `scripts/lib/claim-budget.mjs` rather than in the runner.**
// `scripts/codex-runner.mjs` calls `main()` at module scope and exports nothing, so importing it
// would dispatch a job. The ten-case input table below cannot be written against a self-executing
// script — the same constraint that moved vibe-208's gate reader into a lib module.
//
// **Upward, not shrink-only.** The Stop hook's `VIBE_TEST_GATE_BUDGET_MS` is one-way by design
// (`Math.min(900_000, …)`) because a *gate* deadline must not be extendable by the thing it gates.
// A claim handshake is the opposite situation: the operator is the one who knows their machine is
// slow, and refusing to let them wait longer preserves exactly the defect A14 filed.

import { strict as assert } from "node:assert";
import test from "node:test";

import {
  CLAIM_BUDGET_DEFAULT_MS, CLAIM_BUDGET_MAX_MS, claimFailureMessage, resolveClaimBudget,
} from "../../scripts/lib/claim-budget.mjs";

const notices = [];
const collect = (message) => notices.push(message);

test("R14: the whole input space resolves to one of two answers, and only one rule (vibe-209)", () => {
  // Fall back, never clamp. Clamping hands an operator a budget they did not ask for and says
  // nothing; falling back with a notice tells them their setting was ignored. One rule, no second
  // branch, and every rejected shape lands in the same place.
  const D = CLAIM_BUDGET_DEFAULT_MS;
  const cases = [
    ["unset", undefined, D, false],
    ["empty", "", D, true],
    ["zero", "0", D, true],
    ["negative", "-1", D, true],
    ["fractional", "2.5", D, true],
    ["non-numeric", "abc", D, true],
    ["whitespace-padded valid", "  9000  ", 9000, false],
    ["a valid raise", "60000", 60000, false],
    ["a valid lower", "250", 250, false],
    ["at the maximum", String(CLAIM_BUDGET_MAX_MS), CLAIM_BUDGET_MAX_MS, false],
    ["over the maximum", String(CLAIM_BUDGET_MAX_MS + 1), D, true],
  ];
  for (const [label, raw, expected, expectNotice] of cases) {
    notices.length = 0;
    const env = raw === undefined ? {} : { VIBE_SUITE_CLAIM_BUDGET_MS: raw };
    assert.equal(resolveClaimBudget(env, collect), expected, label);
    assert.equal(notices.length > 0, expectNotice,
      `${label}: a rejected value must say so; an accepted one must be silent`);
    if (expectNotice) {
      assert.match(notices[0], /VIBE_SUITE_CLAIM_BUDGET_MS/,
        `${label}: the notice must name the variable the operator set`);
    }
  }
});

test("R12/R13: a raise is honoured as well as a lower — the point of the seam (vibe-209)", () => {
  assert.ok(resolveClaimBudget({ VIBE_SUITE_CLAIM_BUDGET_MS: "60000" }, collect)
    > CLAIM_BUDGET_DEFAULT_MS, "A14 asks for a LONGER wait on a loaded box");
  assert.ok(resolveClaimBudget({ VIBE_SUITE_CLAIM_BUDGET_MS: "250" }, collect)
    < CLAIM_BUDGET_DEFAULT_MS, "and a shorter one keeps the tests fast");
});

test("R11: the message names the EXACT budget and the ACTUAL pid, both variants (vibe-209)", () => {
  // The Step-3 correction this pins: the budget is a default parameter local to `awaitWorkerClaim`,
  // so it has to TRAVEL to where the message is built. A message that always says 5000 would satisfy
  // any assertion written as `within \d+ms`, which is what the plan first proposed.
  for (const [budget, pid] of [[5000, 4242], [60000, 99], [250, 7]]) {
    const reaped = claimFailureMessage({ budgetMs: budget, pid, reaped: true });
    assert.match(reaped, new RegExp(`within ${budget}ms`), `budget ${budget} must appear verbatim`);
    assert.match(reaped, new RegExp(`\\(pid ${pid}\\)`), `pid ${pid} must appear verbatim`);
    assert.match(reaped, /terminated before claiming/, "the reaped variant keeps its meaning");

    const unconfirmed = claimFailureMessage({ budgetMs: budget, pid, reaped: false });
    assert.match(unconfirmed, new RegExp(`within ${budget}ms`));
    assert.match(unconfirmed, new RegExp(`\\(pid ${pid}\\)`));
    assert.match(unconfirmed, /could not be confirmed reaped/,
      "the unconfirmed-reap variant is a DIFFERENT outcome and must stay distinguishable");
    assert.notEqual(reaped, unconfirmed, "the two variants must not collapse into one sentence");
  }
});

test("R11b: a pid that is not known is said so, never fabricated (vibe-209)", () => {
  const message = claimFailureMessage({ budgetMs: 5000, pid: null, reaped: true });
  assert.match(message, /within 5000ms/);
  assert.ok(!/\(pid \d+\)/.test(message),
    `an unknown pid must not be invented: ${message}`);
});
