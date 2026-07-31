# Review rubric — what a proposal is reviewed against

The critic receives this file with every dispatch. It is the shared vocabulary that makes two rounds
comparable and two runs comparable: a finding named `measurability` in round 1 means the same thing in
round 4.

Severity comes from [`vibe-core`](../../vibe-core/SKILL.md) — the same scale every reviewing artifact in
the suite uses. This file adds only the dimensions.

## Dimensions

A finding names exactly one. Where two fit, pick the one that fails first if the proposal is acted on.

| Dimension | The question it asks |
|---|---|
| **measurability** | Can anyone tell afterwards whether this worked? A success criterion with no baseline, no window, or no threshold cannot be evaluated, so the proposal can never be said to have failed. |
| **risk coverage** | What happens when a step does not work? A named risk with no response, or a rollback that a later step removes, is worse than an acknowledged gap because it reads as covered. |
| **sequencing** | Does each step have what it needs when it runs? A comparison that justifies a decision must precede the decision; a dependency introduced after its dependant is an ordering error whatever the prose says. |
| **scope** | Is the boundary stated, and does the work stay inside it? Both directions count: work implied but never scoped, and work described that the goal does not require. |
| **feasibility** | Can this be done as written, by the people and systems named, with the constraints given? |
| **clarity** | Would two competent readers act on this the same way? An ambiguity that survives to execution becomes two implementations. |
| **evidence** | Is a claim that carries weight supported? A number with no source, or an assertion about current behaviour with no citation, is a decision resting on nothing. |

## What a finding contains

Beyond the fields the finding contract fixes: a **stable id** (`F1`, `F2`, …) that survives across
rounds, and the **line or section** it attaches to. An id that changes between rounds makes the closure
machine meaningless, because a challenge could no longer refer to the finding it answers.

## What is not a finding

- **A preference with no consequence.** If the proposal works either way, say so in prose or say
  nothing.
- **A rewrite.** The critic reports what is wrong; the worker decides what to write instead.
- **A restatement of the proposal's own caveat.** A plan that already names a risk has not failed
  `risk coverage`; it fails only if the risk has no response.
- **Padding.** Three real findings beat three real findings and four invented ones, because the
  invented ones cost the reader's trust in all seven.

## Translation review

Only when `--second-language` is in play, and against one question: **does the translation say what the
English says?** Not whether it reads well, not whether the English was right — those are the main
loop's business, and re-opening them here would relitigate a settled document in a second language.

Findings are applied as fixes. There is no closure machine and no challenge: a translation is either
faithful or it is corrected.
