---
description: "Drive a tracked work item to a reviewed pull request through a nine-step, three-phase pipeline: analyze, plan, execute, each a worker pass followed by an independent review and a bounded update-and-verify loop. Every project-bound fact comes from a profile, so the same machinery works on any repository that delivers through reviewed pull requests. Ships with no usable profile; a run without one refuses and points at the scaffolder. Arguments: a work-item id, plus --profile, --review-mode, --max-review-rounds and --scenario, or a subcommand."
argument-hint: "<item-id> [--profile <id>] [--review-mode none|single|full] [--max-review-rounds N] [--scenario auto|new-feature|bug-fix|docs] | profile init | resume <run-id> | list"
---

# /vibe-suite:issue2pr — a tracked item to a reviewed PR

Nine steps in three phases, each phase a worker pass, an independent review, and a bounded
update-and-verify loop. The reasoning is recorded alongside the change, so the PR carries why as well
as what.

## What to do

Load [`skills/issue2pr/SKILL.md`](../skills/issue2pr/SKILL.md) and follow it. The skill owns the
machinery; the **profile** owns everything about your project.

The loop's shared rules — backends, review modes, the round cap, verdict parsing, the closure machine,
the same-model refusal, model resolution, provenance and anti-sycophancy — belong to
[the shared reviewer contract](../skills/vibe-core/references/reviewer-contract.md), cited section by
section rather than restated.

## First run

There is no usable profile in the box. Start with:

```
/vibe-suite:issue2pr profile init
```

A run without a resolvable profile refuses and says the same thing. That is deliberate: a default
profile would be a wrong answer that runs.

## Arguments

| Argument | Meaning |
|---|---|
| `<item-id>` | the work item, matched by the profile's `id_pattern` |
| `--profile <id>` | overrides `issue2pr_profile` in `.vibe-suite.md` |
| `--review-mode none\|single\|full` | how much review runs; default `full` |
| `--max-review-rounds N` | the update+verify cap; see the skill's `## Round bounds` |
| `--scenario` | overrides scenario detection |

Subcommands: `profile init`, `resume <run-id>`, `list`.

## What you get

A run folder holding the frozen work item, each phase's worker output and review, the findings and how
each was closed, an append-only timeline, and the pull request.

## What this does not do

- **It does not create the work item.** The pipeline works against one that exists.
- **It does not run without a profile**, and will not invent one.
- **It does not deliver anywhere but a pull request.** A source system without PRs needs a different
  machine, not a different profile — that boundary is recorded in the skill's boundary inventory
  rather than pretended away.
