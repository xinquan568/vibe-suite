// SPDX-License-Identifier: ISC
// The agy → codex → manual fallback chain (E1.7 / vibe-17, implements F9.5 for the audit lane).
//
// The states are explicit because "it falls back" is not a contract — a caller needs to know which
// result is theirs, where the diagnostic went, and what the exit code means.
//
// | outcome            | when                                             | caller sees                    | exit |
// |--------------------|--------------------------------------------------|--------------------------------|------|
// | `agy`              | agy reachable and completed                      | agy's result line, no header   | 0    |
// | `codex`            | agy UNREACHABLE (missing / unauthenticated /     | header on stderr, then codex's | 0    |
// |                    | timed out / quota) — an unreachable class         | result line                    |      |
// | `manual`           | codex unreachable too                            | header + a stable JSON signal  | 3    |
//
// `fallback.md` also describes a quiet hand-off for an engine that answered *uselessly*. That state
// is **not implemented here at all**, because it cannot occur: the agy runner classifies blank output
// as `failed`, so `completed` already implies usable output. Round 3 renamed the branch instead of
// deleting it, which left a state the table described, the tests exercised, and no shipped path could
// reach — a fiction with test coverage. If a future dispatcher can return a completed-but-unusable
// result, add a usability validator and a subprocess fixture together, in one deliberate change.
//
// **This chain is only legal after the contract gate passes.** Before that, `--engine agy` is
// refused outright (`fallback.md` requires refusal, not hand-off, pre-graduation), which is why
// the gate resolver — not PATH — decides whether this module is reachable at all.

export const EXIT = { ok: 0, refused: 2, manual: 3 };

/**
 * Any non-completion is a hand-off with disclosure.
 *
 * The four-key result line carries no `error` field, so a caller reading only that line cannot know
 * *why* a job failed — and guessing "it probably just answered badly" would suppress the disclosure a
 * failed engine deserves. Failing toward disclosure is the safe direction: the worst case is a header
 * the operator did not need.
 */
export function isUnreachable(outcome) {
  if (!outcome) return true;
  return outcome.status !== "completed";
}

// `completed` is the whole criterion: the runners already refuse to call a blank result completed, so
// re-checking the text here would only create a state nothing can produce.
const completed = (outcome) => outcome?.status === "completed";

/**
 * Run the chain. `deps.runAgy` / `deps.runCodex` each resolve to a job outcome (the four-key shape)
 * or null when the engine is not installed at all; `deps.emitHeader` receives the diagnostic.
 */
export async function runWithFallback(deps) {
  const { runAgy, runCodex, emitHeader, gate } = deps;

  // The gate is a REQUIRED dependency, checked before anything is dispatched. Documenting that this
  // chain is post-graduation-only and then calling runAgy unconditionally is how the round-1 code
  // claimed a rule it did not enforce.
  if (gate?.passed !== true) {
    return {
      outcome: "refused", result: null, header: false, exitCode: EXIT.refused,
      reason: `the agy lane is gated shut — ${gate?.reason ?? "no gate verdict supplied"}`,
    };
  }

  const agy = await runAgy();
  if (completed(agy)) return { outcome: "agy", result: agy, header: false, exitCode: EXIT.ok };

  const unreachable = isUnreachable(agy);
  if (unreachable) {
    emitHeader(`agy is unreachable (${agy?.error ?? agy?.status ?? "not installed"}) — handing off `
      + `to codex. Check the lane with /vibe-suite:preflight.`);
  }

  const codex = await runCodex();
  if (completed(codex)) {
    return { outcome: "codex", result: codex, header: unreachable, exitCode: EXIT.ok };
  }

  emitHeader(`codex is unreachable too (${codex?.error ?? codex?.status ?? "not installed"}) — no `
    + `engine could run this analysis. Install or authenticate one, or run it in-session.`);
  return {
    outcome: "manual",
    result: null,
    header: true,
    exitCode: EXIT.manual,
    signal: { fallback: "manual", reason: codex?.error ?? codex?.status ?? "no engine available" },
  };
}
