## Summary

{summary}

## Closes

Closes #{number}

Item: **{id}** — {title}

## Acceptance check

{acceptance}

## Test plan

{test_plan}

Gates run: {gates}

## AI-generated code disclosure

{disclosure}

{guardrails}

<!--
`{disclosure}` is **rendered per mode**, because one fixed sentence is false in two of the three.

  none    Produced by the nine-step `/vibe-suite:issue2pr` pipeline **with no independent review**
          (review-mode `none`). Worker: the session. No reviewer was dispatched.

  single  Produced by the nine-step `/vibe-suite:issue2pr` pipeline with one independent review per
          phase and **self-reported** finding closure (review-mode `single`). Worker: the session.
          Reviewer: a non-worker model via the `{backend}` backend, no model id pinned.

  full    Produced by the nine-step `/vibe-suite:issue2pr` pipeline with independent review and
          **reviewer-verified** finding closure (review-mode `full`). Worker: the session. Reviewer: a
          non-worker model via the `{backend}` backend, no model id pinned.

A fixed sentence claiming independent review and verified closure is a false claim under `none`, where
no reviewer exists, and an overstatement under `single`, where closure is self-reported and nobody
checked it. A disclosure that is wrong is worse than none, because it is the part a reader trusts in
order to know what to distrust.

`{backend}` is omitted entirely under `none` — naming a backend that was never dispatched implies one
ran.

When any round was self-reviewed, the disclosure names those rounds, per the shared contract's rule
that an unmarked self-review is the failure that rule exists to prevent.
-->
