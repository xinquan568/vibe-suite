# Source-boundary inventory

Every project-bound fact found in the ported source, and where it went.

This exists because §11.3's rule — *core is project-neutral* — is applied hundreds of times across a
large port and checked in one grep. A grep catches **values**. It cannot catch a project-shaped
**assumption** written in prose, because there is no literal to match. This table is where those are
recorded, and the `assumption` rows are the ones a human has to read.

**The dispositions:**

| | Meaning |
|---|---|
| `profile-field` | maps onto a field the contract already defines |
| `contract-extension` | needed a new field, so the contract's version moved |
| `example-only` | belongs in `examples/`, never in core |
| `assumption` | project-shaped, carries no literal, and no test will ever raise it |

**§11.3's list is a minimum, not a maximum.** A fact it does not name still leaves core — it maps onto
an existing field or forces an extension. What it may never do is stay because nobody wrote it down.

## Values

| Source fact | disposition | field / note |
|---|---|---|
| repository identifier | profile-field | `repo_id` |
| local checkout path | profile-field | `repo_path` |
| branch cut from | profile-field | `base_branch` |
| issue-id shorthand pattern | profile-field | `id_pattern` |
| issue URL pattern | profile-field | `url_regex` |
| work-branch naming | profile-field | `branch_template` |
| `--repo` value on every source call | profile-field | derived from `repo_id`; the Step-9 PATCH endpoint uses the same value rather than a second literal |
| build and test commands | profile-field | `gates` |
| how the gates are run, in prose | profile-field | `gate_mechanics` |
| PR body layout | profile-field | `pr_body_template`, defaulting to the generic template |
| whether tests precede code | profile-field | `tdd_policy` |
| house rules a reviewer enforces | profile-field | `anti_patterns` |
| documents a reviewer should read first | profile-field | `mental_model_refs` |
| extra per-step finding categories | profile-field | `category_extensions` |
| words that select a scenario | profile-field | `scenario_overrides` |
| preferred reviewer backend | profile-field | `reviewer_backend`, domain deferred to the configuration schema |
| which system holds the work item | profile-field | `source_driver` |
| a human-readable project name | profile-field | `project_id` |
| the worked example set | example-only | `examples/profiles/roamex.md` |
| the second shipped profile | example-only | not carried at all — it is this repository's operational configuration, not a plugin deliverable |

## Contract extensions

Two facts had no field in §11.3's list. Both are recorded here rather than left in core, and both moved
`contract_version` to **1** as this contract's first published shape.

| Source fact | Why no existing field fit | New field |
|---|---|---|
| the workspace layout a run expects — where checkouts live relative to the run folder | §11.3 names `repo_path` for *one* repository; a run that touches several needs the shape, not one path | `repo_path` accepts a list, and the multi-repo case is a documented shape of the same field rather than a new one |
| the contract's own version | not a project fact at all, but without it an extension is invisible | `contract_version` |

The first is deliberately **not** a new field. Adding one would have been easier and wrong: a list is
the same fact at a different arity, and a second field would let a profile set both.

## Assumptions — the rows no test will raise

Project-shaped statements carried in prose. None has a literal to grep, so each is either
parameterised, or stated in the core as an assumption a profile may override.

| Assumption in the source | disposition | Resolution |
|---|---|---|
| the default branch is `main` | assumption | parameterised as `base_branch`; core names no branch |
| issue ids are numeric with a project prefix | assumption | `id_pattern` decides; core matches whatever it compiles |
| the work item lives on GitHub | assumption | `source_driver` names it; the github driver is the only one implemented, and #43 extracts the seam |
| one repository per run | assumption | `repo_path` accepts a list; core never assumes arity |
| a PR is the unit of delivery | assumption | **not** parameterised. The nine-step machine terminates in a reviewed PR, and a source system without PRs would need a different machine, not a different profile. Stated in core as a scope boundary rather than pretended away. |
| the reviewer is reached as a subprocess | assumption | **not** parameterised. It follows from the backend contract, which the reviewer contract owns. |

The last two are the honest ones: they are project-shaped, they were **not** removed, and the reason is
stated. An inventory that classified everything as parameterised would be a claim that the core is
universal, which it is not — it is neutral across projects that deliver through reviewed pull requests.


## Source literals — the enumerated set the check ranges over

Machine-readable, because the zero-literals test derives its forbidden set from here rather than from a
list maintained separately in the test file. Two statements of one set is how they diverge.

<!-- source-literals -->
```json
[
  "roam-",
  "example-org/roamex",
  "codes/roamex",
  "chromium_src",
  "xinquan568/vibe-suite",
  "codes/vibe-suite",
  "vibe-suite-pr-body",
  "acme/fixture-repo",
  "fx-",
  "acme/ai/"
]
```

**What this set is, exactly.** Every target-project value that passed through this port: Roamex's, this
repository's *in its role as a target* in the source skill, and the fixture's. It is **enumerated, not
inferred** — a literal from some fourth project would pass the check, and the check claims only that
these left nothing behind.

**What is deliberately absent.** The bare word `roamex`: core legitimately points at
`examples/profiles/roamex.md`, and a filename is not a configuration value. Likewise `vibe-suite` — the
plugin namespace, the config filename, and a component of every core path. The distinction throughout
is *value a profile would supply* versus *name the product goes by*.
