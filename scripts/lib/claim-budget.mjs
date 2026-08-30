// SPDX-License-Identifier: ISC
// The claim-handshake budget, and the sentence said when it runs out (vibe-209 / grill P4 · A14).
//
// `awaitWorkerClaim` waited a hard-coded 5 s and, on expiry, reported "worker did not start, or was
// terminated before claiming" — a sentence naming neither how long it waited nor which process it
// waited for. An operator reading it learns that something did not happen, and nothing else.
//
// **Why the seam adjusts UPWARD.** Grill A14: *"Cold Node start on a loaded box can exceed it."* The
// Stop hook's `VIBE_TEST_GATE_BUDGET_MS` is deliberately one-way (`Math.min(900_000, …)`) because a
// *gate* deadline must not be extendable by the thing it gates. A claim handshake is the opposite
// situation — the operator is the one who knows their machine is slow, and a shrink-only seam would
// preserve exactly the defect A14 filed.
//
// **Why this is a module and not four lines in the runner.** `scripts/codex-runner.mjs` calls
// `main()` at module scope and exports nothing, so importing it dispatches a job. The input table
// below has eleven cases; none of them is testable against a self-executing script.

/** The wait, when nothing says otherwise. Unchanged from the value this replaces. */
export const CLAIM_BUDGET_DEFAULT_MS = 5000;

/**
 * The ceiling. A claim handshake is a local process writing its own pid into a file, so five
 * minutes is far past any cold start — the bound exists so a mistyped seam cannot park a dispatch
 * for an afternoon, not because a legitimate value would approach it.
 */
export const CLAIM_BUDGET_MAX_MS = 300_000;

/** The documented seam. */
export const CLAIM_BUDGET_ENV = "VIBE_SUITE_CLAIM_BUDGET_MS";

/**
 * Resolve the budget from `env`.
 *
 * **Falls back, never clamps.** Clamping hands an operator a budget they did not ask for and says
 * nothing about it; falling back with a notice tells them their setting was ignored and why. One
 * rule covers every rejected shape — empty, zero, negative, fractional, non-numeric, over the
 * maximum — so there is no second branch to get wrong.
 *
 * `notify` receives one line per rejection; it defaults to stderr and is injectable so tests can
 * read the notice instead of the terminal.
 */
export function resolveClaimBudget(env = process.env, notify = null) {
  const raw = env?.[CLAIM_BUDGET_ENV];
  if (raw === undefined || raw === null) return CLAIM_BUDGET_DEFAULT_MS;

  const text = String(raw).trim();
  const say = notify ?? ((message) => process.stderr.write(`${message}\n`));
  const reject = (why) => {
    say(`codex-runner: ${CLAIM_BUDGET_ENV}=${JSON.stringify(String(raw))} ${why} — `
      + `using the default ${CLAIM_BUDGET_DEFAULT_MS}ms`);
    return CLAIM_BUDGET_DEFAULT_MS;
  };

  // `/^\d+$/` on purpose: `Number("2.5")` is a fine number and `parseInt("2.5")` is 2, so both would
  // silently accept a value the operator did not write. A budget in milliseconds is a whole number.
  if (!/^\d+$/.test(text)) return reject("is not a whole number of milliseconds");
  const value = Number(text);
  if (value <= 0) return reject("must be greater than zero");
  if (value > CLAIM_BUDGET_MAX_MS) return reject(`is above the ${CLAIM_BUDGET_MAX_MS}ms maximum`);
  return value;
}

/**
 * The sentence for a claim that never arrived.
 *
 * Both facts travel in: the budget is a parameter of `awaitWorkerClaim`, not of its caller, and the
 * pid belongs to the caller — so a message built from either one alone is the one that was there
 * before. `reaped` distinguishes two genuinely different outcomes and must not collapse into one
 * sentence: a worker confirmed dead is a different situation from a worker that may still be
 * running.
 *
 * A pid that is not known is omitted rather than invented — `(pid null)` would be worse than
 * silence, because it reads like a fact.
 */
export function claimFailureMessage({ budgetMs, pid = null, reaped = true } = {}) {
  const who = Number.isInteger(pid) && pid > 0 ? ` (pid ${pid})` : "";
  const outcome = reaped
    ? "worker did not start, or was terminated before claiming"
    : "worker did not start and could not be confirmed reaped";
  return `${outcome} within ${budgetMs}ms${who}`;
}
