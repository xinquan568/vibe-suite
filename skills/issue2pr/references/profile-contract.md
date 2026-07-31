# The issue2pr profile contract — version 1

A profile supplies every project-bound fact the pipeline needs. The core supplies the machinery and
knows none of them.

The split exists so that pointing the pipeline at a new project is a new profile rather than a fork.
That only holds if the contract is **versioned**: a field added without a version bump is a field older
profiles silently lack, and a field removed without one breaks profiles that still set it.

**`profile init` generates against this document; `scripts/profile_lint.py` validates against it.**
Where the two disagree the lint is what runs, so a change here that the lint does not enforce is
documentation of an intention rather than a contract.

## Required fields

A run cannot start without these. The test is whether the pipeline can *fetch, branch and check*: a run
needs to know what to work on, where to cut from, and what must pass.

| Field | Type | What it is |
|---|---|---|
| `contract_version` | integer | which version of this document the profile targets |
| `project_id` | string | a human-readable name, used in messages |
| `repo_id` | string | the repository's identity in its source system, e.g. `owner/name` |
| `repo_path` | string or list | the local checkout, relative to the workspace. A list when a run touches several |
| `base_branch` | string | what the work branch is cut from |
| `source_driver` | enum | which system holds the work item. `github` is implemented |
| `id_pattern` | regex | recognises a work-item id, e.g. `^proj-(\d+)$` |
| `url_regex` | regex | recognises a work-item URL and extracts its number |
| `branch_template` | string | the work branch, with `{id}` and `{slug}` placeholders |
| `gates` | list of strings | commands that must pass before a PR opens |

## Optional fields

Absent means the core's default applies. **A profile carrying none of these is valid** — that is the
shape a freshly scaffolded profile has, before any judgement has been recorded.

| Field | Type | What it is |
|---|---|---|
| `gate_mechanics` | prose | how the gates are actually run, when the commands alone do not say |
| `pr_body_template` | path | overrides the generic template |
| `tdd_policy` | prose | whether tests precede code, and what counts as covered |
| `anti_patterns` | list of prose | house rules a reviewer enforces |
| `mental_model_refs` | list of paths | documents a reviewer reads before judging |
| `category_extensions` | map | extra finding categories per step, added to the core set |
| `scenario_overrides` | map | words that select a scenario, overriding the core's keywords |
| `reviewer_backend` | enum | preferred backend. **Domain deferred** to the configuration schema in [`vibe-core`](../../vibe-core/SKILL.md) — this contract does not restate it, because two statements of an enum is how they diverge |

## Validation has two contexts, and they are not interchangeable

| Context | Checks | Needs |
|---|---|---|
| **structural** | fields present, types right, domains right, regexes compile, version known | nothing but the file |
| **environmental** | `repo_path` resolves, `base_branch` exists, the source system answers | a checkout |

`profile_lint.py --structural-only` runs the first. A **shipped reference profile can only be validated
structurally** — `examples/profiles/roamex.md` names a repository nobody reading this has checked out,
and a lint that failed it would be demanding that every reader clone someone else's project.

Full validation is what a *run* performs at start-up, where the checkout exists by definition.

## Unknown fields are an error

Not a warning. An optional field is the only kind that can be misspelled without consequence —
`tdd_polcy` would simply never apply, and the profile would look complete while silently doing nothing
about it. Refusing an unknown key is what makes the optional fields real.

## Extending the contract

Adding a field is a version bump, and this document is the record. The prior question is whether the
fact is project-bound at all: if it would be the same for every project, it belongs in the core.

If it is project-bound and no field fits, prefer **widening an existing field's type** to adding a
neighbour. `repo_path` accepting a list is the worked example: a second `repo_paths` field would have
let a profile set both, and then something would have to decide which wins.
