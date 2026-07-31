---
name: refine-proposal
description: "Drive a written proposal through bounded rounds of independent review until it converges: freeze the input, produce a baseline, then review and revise on a shared rubric until the verdict is clean or the cap stops it. Use when a plan needs adversarial review rather than editing, or when it should be delivered bilingually. Not for reviewing code, and not for writing a first draft."
---

# refine-proposal — the proposal generator-critic loop

A proposal is frozen, reviewed by a non-worker model, revised against the findings, and reviewed again
until it converges or the round cap stops it. The worker writes; the critic never edits.

**The loop rules are not defined here.** They belong to
[the shared reviewer contract](../vibe-core/references/reviewer-contract.md), which every
generator-critic loop in the suite cites so that a `major` raised here means what a `major` means
anywhere else. This skill relies on nine of its sections:

| Concern | Contract section |
|---|---|
| which backend runs the critic | [Reviewer backends](../vibe-core/references/reviewer-contract.md#reviewer-backends) |
| what `none` / `single` / `full` mean | [Review modes](../vibe-core/references/reviewer-contract.md#review-modes) |
| the round cap and its clamp rule | [Round bounds](../vibe-core/references/reviewer-contract.md#round-bounds) |
| how a verdict is read | [Verdict parsing](../vibe-core/references/reviewer-contract.md#verdict-parsing) |
| how a finding moves between states | [The closure machine](../vibe-core/references/reviewer-contract.md#the-closure-machine) |
| worker ≠ critic, and the escape | [Same-model refusal and self-review](../vibe-core/references/reviewer-contract.md#same-model-refusal-and-self-review) |
| which model the critic runs on | [Model resolution](../vibe-core/references/reviewer-contract.md#model-resolution) |
| the disclosure every prompt opens with | [Provenance](../vibe-core/references/reviewer-contract.md#provenance) |
| how a critic must not soften | [Anti-sycophancy](../vibe-core/references/reviewer-contract.md#anti-sycophancy) |

What follows is only what is this loop's own.

## Invocation

```
/vibe-suite:refine-proposal "<proposal text>" | --file <path>
    [--review-mode none|single|full]
    [--max-review-rounds N]
    [--stop-severity blocker|major|minor]
    [--second-language "<language>"] [--review-translation | --no-review-translation]
    [--allow-self-review] [--dry-run] [--checkpoint]
/vibe-suite:refine-proposal iterate <slug> [same flags]
/vibe-suite:refine-proposal resume <slug>
/vibe-suite:refine-proposal list
```

An input is required: free text or `--file`. Both, or neither, is a refusal — a run whose subject is
ambiguous would produce a document nobody asked for.

## Round bounds

floor **1**, ceiling **5**, default **3**.

The floor is 1 because a single review round is a complete unit of work for this loop: a review round
produces findings and a revision answers them, and nothing is left dangling if the run stops there.
Loops whose round pairs an update with a separate verification cannot stop at 1, which is why theirs is
2.

## `--stop-severity`

Stops early when no **open** finding sits at or above the named severity: `blocker` | `major` |
`minor`, default `major`.

This is not the closure machine restated. That machine says how a finding moves between states; this
says which states still justify another round. A run may stop with `minor` findings open and say so.

## The loop

1. **Freeze the input.** The proposal is copied once into the run folder and never edited in place.
   Every later artifact is derived from the frozen copy, so a re-read is reproducible.
2. **Baseline.** `plan-i<N>.md` — the worker's first pass, before any review.
3. **Review round `r<M>`.** Dispatch the critic through
   [`scripts/codex-runner.mjs`](../../scripts/codex-runner.mjs) at `read-only`. The prompt carries the
   frozen input, the current plan, and [`references/review-rubric.md`](references/review-rubric.md).
   The round writes **`review.md`** (the critic's prose) and **`review.json`** (its findings).
4. **Revise.** The worker answers every finding. How a finding moves between states, and the stable
   ids a challenge depends on, are
   [the closure machine](../vibe-core/references/reviewer-contract.md#the-closure-machine)'s.
5. **Stop** when the verdict is clean, when no open finding meets `--stop-severity`, or when the cap is
   reached — recording which.
6. **Finalize.** Assemble `FINAL.md`, then render it.

`--dry-run` performs steps 1 and 2 and stops before any dispatch. It exists to check that the input was
understood before spending a review on it.

`--checkpoint` writes state after every round rather than at the end, so an interrupted run resumes
from its last completed round instead of its first.

## Bilingual output

`--second-language "<language>"` appends a full translation **after** the English. **English is always
first**, and the combined document is `final-bilingual.md`, which becomes the render source.

One critic pass over the translation runs by default (`--review-translation`;
`--no-review-translation` skips it). Its contract is deliberately simpler than the main loop's: findings
are applied as fixes, with no closure machine and no challenges — a translation is either faithful or
it is corrected, and there is nothing for a decline to mean.

**The translation review is an advisory pass, not a gating review** — finalize's conclusions are the
same with and without it — so it takes the contract's
[advisory branch](../vibe-core/references/reviewer-contract.md#gating-reviews-and-advisory-passes)
rather than the refusal that governs the main loop:

- **with `--allow-self-review`** → the pass is self-reviewed and marked as the contract requires:
  `reviewer: "self"`, no usage figures, said so in the summary;
- **without it** → a **recorded skip**: finalize continues and the summary states that the translation
  went unreviewed.

Either way the document is produced. A translation review that could fail the whole finalize would make
an optional feature load-bearing.

## Folder layout

```
docs/discussion/<date>-<slug>/
  iter-<N>/
    input.md                  the frozen proposal
    plan-i<N>.md              baseline
    round-<M>/
      review.md               the critic's prose
      review.json             its findings
      changes.md              what the revision did with each
    FINAL.md | final-bilingual.md
    FINAL.html                or FINAL.md, when pandoc is absent
  state.json
  summary.md
```

## State — `schema_version` 6

```json
{
  "schema_version": 6,
  "slug": "<date>-<slug>",
  "review_mode": "full",
  "max_review_rounds": 3,
  "stop_severity": "major",
  "second_language": null,
  "review_translation": true,
  "translation_review": {"status": "not_run", "reviewer": null},
  "rounds": [
    {"id": "r1", "reviewer": "codex", "verdict": "approve_with_revisions", "usage": {}}
  ],
  "carried_forward": [],
  "findings": {}
}
```

`reviewer` is per round because a single run can mix a dispatched critic with a self-reviewed round,
and a summary that reported only one of them would misdescribe the run. `carried_forward` holds
findings that outlived their round — open at the cap, or deliberately deferred.

## Rendering

[`scripts/render_final.py`](../../scripts/render_final.py) takes the assembled markdown and produces a
self-contained `FINAL.html` with a metadata banner — timestamp, word count, character count.

**Pandoc is optional.** Without it the script writes a markdown pointer and warns, and finalize
succeeds. The renderer is handed whichever source finalize chose; picking between `final.md` and
`final-bilingual.md` is this skill's decision, not the script's.

## `iterate`

`iterate <slug>` starts a fresh iteration on an existing run, inheriting its configuration with
per-flag override, and re-freezing the input so a changed proposal is picked up. The previous
iteration's unresolved findings arrive as `carried_forward` rather than being silently dropped.

## Guards

Only this loop's own. Everything shared is governed by the contract sections cited above and is not
restated here — a second statement of a rule is the beginning of two rules.

- **No input, or two inputs** → refuse. A run whose subject is ambiguous would produce a document
  nobody asked for.
- **A run folder that already exists** → refuse unless `iterate` or `resume` was asked for.
- **An input that is empty after freezing** → refuse. There is nothing to review, and a round against
  nothing would still cost one.

Backend availability, the self-review escape, and what happens to a malformed verdict are the
contract's:
[Same-model refusal and self-review](../vibe-core/references/reviewer-contract.md#same-model-refusal-and-self-review)
and [Verdict parsing](../vibe-core/references/reviewer-contract.md#verdict-parsing).
