---
name: issue2pr
description: "Drive a tracked work item to a reviewed pull request through a nine-step, three-phase pipeline: analyze, plan, execute, each phase a worker pass followed by an independent review and a bounded update-and-verify loop. Every project-bound fact comes from a profile, so the machinery is the same whichever repository it points at. Use when an issue should become a reviewed PR with its reasoning recorded, not when a quick edit will do."
---

# issue2pr — a tracked work item to a reviewed pull request

Nine steps in three phases. Each phase is the same shape: the **worker** produces, an independent
**reviewer** critiques, and a bounded **update-and-verify** loop closes what the review raised.

| Phase | Steps | Produces |
|---|---|---|
| Analyze | 1–3 | what the work item actually asks for, and what constrains it |
| Plan | 4–6 | decisions, a work breakdown, a test strategy, acceptance mapping |
| Execute | 7–9 | the change, its tests, and a reviewed pull request — **not** a merge |

<!-- phases -->
```json
{"analyze": [1, 3], "plan": [4, 6], "execute": [7, 9]}
```

**This core knows nothing about your project.** Every project-bound fact — the repository, the branch
naming, what the gates are, what a reviewer should read first — comes from a **profile**. That is what
makes pointing the pipeline at a new project a new profile rather than a fork.

## The loop rules are not defined here

They belong to [the shared reviewer contract](../vibe-core/references/reviewer-contract.md), which
every generator-critic loop in the suite cites so that a `major` raised here means what it means
anywhere else. This pipeline relies on nine of its sections:

| Concern | Contract section |
|---|---|
| which backend runs the reviewer | [Reviewer backends](../vibe-core/references/reviewer-contract.md#reviewer-backends) |
| what `none` / `single` / `full` mean | [Review modes](../vibe-core/references/reviewer-contract.md#review-modes) |
| the round cap and its clamp rule | [Round bounds](../vibe-core/references/reviewer-contract.md#round-bounds) |
| how a verdict is read | [Verdict parsing](../vibe-core/references/reviewer-contract.md#verdict-parsing) |
| how a finding moves between states | [The closure machine](../vibe-core/references/reviewer-contract.md#the-closure-machine) |
| worker ≠ reviewer, and the escape | [Same-model refusal and self-review](../vibe-core/references/reviewer-contract.md#same-model-refusal-and-self-review) |
| which model the reviewer runs on | [Model resolution](../vibe-core/references/reviewer-contract.md#model-resolution) |
| the disclosure every prompt opens with | [Provenance](../vibe-core/references/reviewer-contract.md#provenance) |
| how a reviewer must not soften | [Anti-sycophancy](../vibe-core/references/reviewer-contract.md#anti-sycophancy) |

## No profile ships, and that is the design

A run needs a profile and **the suite ships none that works**. The reference under
[`examples/profiles/`](examples/profiles/) names a repository you have not checked out; it exists to
show the shape, not to be used.

**A run with no resolvable profile refuses**, and says how to make one:

```
issue2pr: no profile resolved. Run `/vibe-suite:issue2pr profile init` to create one
          for this repository, or pass --profile <id>.
```

Resolution order: `--profile <id>`, then `issue2pr_profile` in `.vibe-suite.md`. The id is an id, not a
path — it resolves to `profiles/<id>.md`, and a `/` or `.` in it is rejected before any path is built.

Refusing is better than a default, because a default profile is a wrong answer that runs.

**The contract profiles must satisfy:** [`references/profile-contract.md`](references/profile-contract.md).
What went into it and why: [`references/boundary-inventory.md`](references/boundary-inventory.md).
How `profile init` produces one: [`references/profile-init.md`](references/profile-init.md).

## Round bounds

`max_review_rounds`, set by `--max-review-rounds`: floor **2**, ceiling **5**, default **2**. An
out-of-range integer clamps to the nearest bound with a notice naming both values; a non-integer is an
error rather than a clamp.

**The loop is bounded by the *effective* cap, not by the run-start one**, because `iterate` may raise
it for a new round. Resolution, stated here once:

```
effective cap = state.json:max_review_rounds_overrides[current_round]   # set only by `iterate`
             ?? state.json:max_review_rounds                            # mirrored at run-start
             ?? 2                                                       # a run that predates the field
```

An **absent** `max_review_rounds_overrides` is read as `{}` — runs written before the field existed
resolve rather than raise. Values in the map are already validated and clamped at write time, so
resolution reads them without re-checking. Everywhere this document writes `N` for the cap, it means
the effective cap.

The floor is 2 because this loop's round is *update + verify*: the worker answers a finding and the
reviewer checks the answer. A cap of 1 would admit an update that no reviewer ever verified, which is
the failure the loop exists to prevent — so 1 is not a smaller loop, it is a different and worse one.

## Severity decides what happens next

| Severity | Effect |
|---|---|
| `blocker` | **stops the round.** No update loop runs; the run reports and halts |
| `major` | enters the **bounded update+verify loop** |
| `minor`, `nit` | recorded; may be closed or carried forward |

A `blocker` stops rather than loops because it means the phase's output cannot be built on. Iterating
on a foundation the reviewer has rejected produces a more polished wrong answer.

When the cap is reached with a `major` still open the run stops at `EXIT_MAX_ROUNDS` — a terminal state,
not a failure. It records what remains open, and a fresh round is usually cheaper than another
iteration at the same cap.

## Review modes

`none`, `single`, `full` — defined by [the contract](../vibe-core/references/reviewer-contract.md#review-modes).
Two consequences specific to this pipeline:

- **Canonical step numbering is preserved.** Under `none` the run executes steps 1, 4 and 7 and they
  keep those numbers. State, resume, and reporting stay comparable across modes; a mode that renumbered
  its steps would make two runs of the same issue incomparable.
- `none` needs no reviewer backend, so pre-flight is skipped rather than failed. Pre-flight
  otherwise resolves the **effective cap** for the round about to run, by the rule under
  [Round bounds](#round-bounds).

## Durable state

Every run owns a folder. The pipeline is resumable because the folder, not the session, is the record.

The nine steps describe one run. What starts, resumes, repeats and enumerates runs is stated once, in
its own reference, and cited here in the shape used above:

| Concern | Where it is stated |
|---|---|
| running issues serially, advancing on merge | [`chain`](references/operational-modes.md#chain) |
| continuing a run that stopped mid-round | [`resume`](references/operational-modes.md#resume) |
| a fresh round in place, on the same branch and PR | [`iterate`](references/operational-modes.md#iterate) |
| enumerating runs and their state | [`list`](references/operational-modes.md#list) |
| what `status` may hold, and which values are terminal | [Run-status enum](references/operational-modes.md) |

A mode's precondition is stated in terms of that enum, so the enum is part of the definition rather
than a note beside it.

<!-- state-schema -->
```json
{
  "schema_version": 2,
  "run_id": "<id>-<slug>",
  "source_id": "<id>",
  "profile": "<profile-id>",
  "scenario": "new-feature",
  "review_mode": "full",
  "max_review_rounds": 2,
  "max_review_rounds_overrides": {},
  "current_step": 1,
  "current_round": 1,
  "status": "in_progress",
  "areas_confirmed": [],
  "repos_in_scope": [],
  "pr": null
}
```

`max_review_rounds_overrides` maps a **string-typed** round number to the cap that round runs
under — `{"2": 4}`, not `{2: 4}`, matching what JSON round-trips give you and the
`review_mode_overrides` mechanism it is modelled on. How a value gets there, and what it must
satisfy, is stated once under [Round bounds](#round-bounds).

`areas_confirmed` names the parts of the project a run touches. It was called `crates_confirmed` in the
source — a fossil from a project whose parts were crates. `scripts/profile_manifest.py` reads either
spelling and normalises to this one, so an existing manifest still loads; a manifest carrying **both**
is refused rather than resolved, because two disagreeing values cannot both be the answer.

<!-- timeline-entry -->
```json
{"step": 1, "phase": "analyze", "at": "<utc>", "actor": "worker", "outcome": "completed", "note": ""}
```

The timeline is append-only. An entry is never edited, because the value of a record is that it says
what happened rather than what is currently believed.

## Source snapshots and deltas

A run freezes what the work item said when it started, so a later re-read is comparable.

<!-- source-snapshot -->
```json
{"source_id": "<id>", "fetched_at": "<utc>", "title": "", "body": "", "comments": []}
```

<!-- source-delta -->
```json
{"since": "<utc>", "title_changed": false, "body_changed": false, "new_comments": []}
```

A fresh round re-fetches and diffs against the previous snapshot. The delta is what a new round is
*for* — without it, iterating means re-reading the same text and hoping to think differently.

## The source driver

Every touch of the source system goes through one **driver protocol**. The core names the operations
and what they mean; a driver implements them. `source_driver` in the profile selects which.

This seam exists so that adding a source system changes no core logic. It is also what #43 extracts
rather than invents — a boundary drawn only in a profile field would have left that issue rewriting the
pipeline instead.

<!-- driver-protocol -->
```json
{
  "fetch_item": {"in": ["source_id"], "out": "source-snapshot", "errors": ["not_found", "not_an_item", "unavailable", "rate_limited", "unauthorized", "unusable"]},
  "refresh_item": {"in": ["source_id", "since", "previous_snapshot"], "out": "source-delta", "errors": ["not_found", "unavailable", "rate_limited", "unauthorized", "unusable"]},
  "open_change": {"in": ["branch", "title", "body", "base_branch"], "out": "change_ref", "errors": ["exists", "rejected", "unavailable", "rate_limited", "unauthorized", "unusable"]},
  "update_change": {"in": ["change_ref", "body"], "out": "change_ref", "errors": ["not_found", "rejected", "unavailable", "rate_limited", "unauthorized", "unusable"]},
  "read_change_state": {"in": ["change_ref", "since"], "out": "change_state", "errors": ["not_found", "unavailable", "rate_limited", "unauthorized", "unusable"]},
  "link_closure": {"in": ["change_ref", "source_id"], "out": "change_ref", "errors": ["not_found", "unavailable", "rate_limited", "unauthorized", "unusable"]}
}
```

**The four failure classes are on every operation, and they are not interchangeable** — their whole
content is what the caller does next. `unavailable` is retried; `rate_limited` is retried *after* the
time it carries; `unauthorized` stops and tells the operator; `unusable` means the system answered and
the answer is the problem, which sends someone to look at a different place entirely. Collapsing them
into one error would make an infinite retry loop indistinguishable from a transient failure.

The two types the protocol passes around are declared here, not left for a driver to invent:

<!-- change-ref -->
```json
{"driver": "github", "id": "", "url": "", "branch": ""}
```

<!-- change-state -->
```json
{"state": "open", "mergeable": false, "comments": [], "review_comments": [], "reviews": [], "checks": []}
```

**Scoped to the `since` the caller passed.** An earlier shape carried a single `updated_at`, which says
*that* something changed and not *what* — leaving the caller to re-read everything to find out, which
is the diffing this seam exists to prevent. Comments, review comments, reviews and checks are four
independent collections; a question with a time in it gets an answer scoped to that time.

**The driver filters, using its source's own time parameter where one exists and filtering the results
itself where none does.** The obligation sits on the driver rather than on the source precisely because
sources differ — of the five collections the github driver reads, two accept a time parameter and three
do not. What the core never does is receive everything and diff.

`change_ref` identifies a change without saying what a change *is* in any particular system;
`change_state` is what step 8 reads, and what the babysit trigger polls. Both are the core's, because two drivers inventing their own
shapes is how a seam stops being one.

Every step that reaches the source system names its operation, and **no step names a command**:

| Step | Operation |
|---|---|
| 1 | `fetch_item` — the snapshot a run freezes |
| 7 | `open_change`, then `link_closure` |
| 8 | `read_change_state` — the change as the reviewer sees it, scoped to `since` |
| 9 | `update_change` — the record of what closed |
| a fresh round | `refresh_item` — the delta a new round is *for* |

**A driver never runs a gate and never writes to the worktree.** It answers about the source system and
publishes to it; everything else belongs to the pipeline. Keeping that line is what stops a driver from
becoming a second implementation of the machine.

`github` is the implemented driver. Its commands and response shapes live behind this protocol, not in
the steps.

## The nine steps

1. **Analyze.** What the item asks, what the repository currently does, what constrains the work.
   Not planning: no work breakdown, no file paths, no test strategy. Which side a given sentence
   falls on is decided by [the boundary](#the-analysis-and-planning-boundary), not by impression.
2. **Review the analysis.** An independent reviewer, read-only, judging by that same
   [boundary](#the-analysis-and-planning-boundary) — the one the worker wrote against.
3. **Update and verify.** The worker answers each finding; the reviewer confirms closure. Bounded.
   Each iteration runs [the two checks](#two-checks-before-every-closure-dispatch) before dispatch.
4. **Plan.** Decisions with their reasons, a work breakdown, a test strategy, acceptance mapping.
5. **Review the plan.**
6. **Update and verify.** As step 3, including
   [the two checks](#two-checks-before-every-closure-dispatch).
7. **Execute.** Tests first where the profile's `tdd_policy` says so, then the change, then the gates.
   Open the pull request.
8. **Review the execution.** The diff, against the frozen plan.
9. **Update and verify.** The worker closes what step 8 raised; the reviewer confirms, after
   [the two checks](#two-checks-before-every-closure-dispatch). The run then
   **stops with a reviewed change.**

**The pipeline does not merge.** Merging is a separate, materially broader action: it changes the
default branch on the strength of a review the pipeline itself produced. An earlier draft of this step
said "then merge", which contradicted the command, the phase table and the boundary inventory — all of
which say the machine terminates in a reviewed pull request. It terminates in a reviewed pull request.

## The analysis and planning boundary

Step 1 asks what constrains the work and forbids planning. An anti-pattern **is** a constraint on
implementation, so naming one sits exactly on that line. Stated once here, because the worker writes
against it and the reviewer judges by it — a criterion only one side holds is not a criterion, and
that asymmetry is what made this the most expensive finding class in the source corpus.

> **A sentence whose grammatical subject is the rule or the current state is analysis.
> A sentence whose subject is the work is planning.**

| Analysis ✓ | Planning ✗ |
|---|---|
| "The issue-link rule requires one consistent id across branch, title and body; no workflow enforces it yet." | "branch, PR title, body — carrying the id" |

Both describe one rule. Only the second directs work.

**Naming an anti-pattern is analysis; satisfying it is Phase 2.** An analysis that lists the profile's
`anti_patterns` as constraints is doing what step 1 asked, and must not draw a scope finding. The core
names the field rather than a quantity, because how many there are is the bound profile's fact.

**The rule is not sufficient on its own, and the exception is specific.** A bare noun phrase has
**no subject and no verb**, so no query keyed on modals or on grammatical subject can select it — and
that is the construction that actually recurs. One instance took five closure iterations to shift, then
reappeared with a number changed in a later run, *inside the document diagnosing the pattern*, after a
modal sweep and a subject sweep had both returned clean. It was found by reading. That is why the
enumerated lists in an artifact are **read**, not queried — see below.

## Two checks before every closure dispatch

Steps 3, 6 and 9 run these before the worker's update is dispatched for verification. They are
**procedure, not advice**: each ends with its output **pasted** into the iteration's record under the
heading named here, and a record missing either heading is treated by the reviewer as an unaddressed
finding rather than assumed to have passed.

Both were written down as techniques first and failed anyway — one of them inside the very document
that recorded it. **Documenting a technique does not cause it to run**, which is the whole reason
these are steps with visible output rather than guidance.

**`## Direct read of enumerated lists`** — open every enumerated list in the artifact and read **each
entry**, rather than querying it. The failure mode being looked for is an entry that lists artifacts
instead of stating a rule; it has no subject and no verb, so no sweep selects it. Table cells are read
individually. Paste the entries examined and the verdict on each.

**`## Decision↔consequence sweep`** — for **every claim the iteration changed**, search that claim's
subject across the whole artifact and confirm no other section still carries the superseded reading.
Paste the terms searched and what each turned up. This exists because the same defect recurred across
runs — a risk still describing the withdrawn reading after the decision moved — and once because the
sweep already existed and was skipped. Having a check and not running it is worse than lacking one:
the remedy was available and the defect shipped anyway.

## Disclosure

The PR body's disclosure is **rendered from the mode**, because one fixed sentence is false in two of
the three. The mapping is the core's:

<!-- disclosure-by-mode -->
```json
{
  "none": "with no independent review",
  "single": "with one independent review per phase and self-reported finding closure",
  "full": "with independent review and reviewer-verified finding closure"
}
```

`{backend}` is named only when a reviewer was dispatched — under `none` there was none, and naming one
implies otherwise. A round that fell back to self-review is named, per
[the contract](../vibe-core/references/reviewer-contract.md#same-model-refusal-and-self-review).

A disclosure that overstates is worse than none, because it is the part a reader trusts in order to
know what to distrust.

## Gates

The profile supplies `gates` — the commands that must pass before a PR opens — and optionally
`gate_mechanics`, prose for what the commands do not say.

**Run every gate that exists; claim only the gates you ran.** A gate with no owner is not a gate that
passed, and a report that lists it as passing is worse than one that omits it.

## Guards

Only this pipeline's own. Everything shared is the contract's, cited above and not restated.

- **No resolvable profile** → refuse, with the `profile init` pointer.
- **A profile that fails its contract** → refuse, naming the failures. `scripts/profile_lint.py`.
- **A run folder that already exists** → refuse unless `resume` or `iterate` was asked for; both are
  defined in [operational-modes.md](references/operational-modes.md), including which run statuses
  each one accepts.
- **A work item that does not exist, or is not an item** → refuse before any folder is created.
- **A blocker at any review step** → stop the round.
