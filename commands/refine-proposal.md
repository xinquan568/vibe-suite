---
description: "Drive a written proposal or plan through bounded rounds of independent cross-model review until it converges: freezes the input, produces a baseline, then reviews and revises on a shared rubric with stable finding ids and a closure machine, and finishes with a self-contained rendered document. Optionally delivers the result bilingually, English first, with one fidelity pass over the translation. Use when a plan needs adversarial review rather than editing. Arguments: proposal text or --file, plus --review-mode, --max-review-rounds, --stop-severity, --second-language, --allow-self-review, --dry-run and --checkpoint."
argument-hint: "\"<proposal>\" | --file <path> [--review-mode none|single|full] [--max-review-rounds N] [--stop-severity blocker|major|minor] [--second-language \"<lang>\"] [--allow-self-review] [--dry-run]"
---

# /vibe-suite:refine-proposal — harden a plan by reviewing it, not editing it

A proposal is frozen, reviewed by a model that is not the one writing it, revised against the findings,
and reviewed again until it converges or the round cap stops it.

The separation is the point. A writer editing their own plan improves the sentences; a critic that
cannot edit has to say what is wrong, and the writer has to answer it. What survives that exchange is
different from what survives a re-read.

## What to do

Load [`skills/refine-proposal/SKILL.md`](../skills/refine-proposal/SKILL.md) and follow it. The skill
owns the procedure: the freeze, the rounds, the closure of findings, the bilingual path, and finalize.

The loop's shared rules — backends, review modes, the round cap, verdict parsing, the closure machine,
the same-model refusal, model resolution, provenance and the anti-sycophancy rules — belong to
[the shared reviewer contract](../skills/vibe-core/references/reviewer-contract.md), which the skill
cites section by section rather than restating.

## Arguments

| Argument | Meaning |
|---|---|
| `"<proposal>"` or `--file <path>` | the input. Exactly one — both or neither is a refusal |
| `--review-mode none\|single\|full` | how much review runs; default `full` |
| `--max-review-rounds N` | the cap; see the skill's `## Round bounds` |
| `--stop-severity blocker\|major\|minor` | stop when no **open** finding is at or above this; default `major` |
| `--second-language "<lang>"` | append a translation after the English |
| `--review-translation` / `--no-review-translation` | one fidelity pass over the translation; on by default |
| `--allow-self-review` | permit a same-family review, and authorise the fallback when the backend is unavailable |
| `--dry-run` | freeze and baseline, then stop before any dispatch |
| `--checkpoint` | write state after every round, so an interruption resumes from the last one |

Subcommands: `iterate <slug>` for a fresh iteration on an existing run, `resume <slug>`, and `list`.

## What you get

A run folder under `docs/discussion/<date>-<slug>/` holding the frozen input, each round's review and
the changes it produced, the final document, and a self-contained `FINAL.html`. When pandoc is absent
the render degrades to a markdown pointer and finalize still succeeds.

## What this does not do

- **It does not review code.** Use `/vibe-suite:roast` for a repository or `/vibe-suite:security-scan`
  for a plugin's executable surface.
- **It does not write your first draft.** The loop hardens a proposal that exists; it has nothing to
  freeze otherwise.
- **It never reviews its own work silently.** If the backend is unavailable the run refuses, unless
  `--allow-self-review` was passed — and then every self-reviewed round is marked as such in the state
  and in the summary.
