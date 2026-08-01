# `profile init` — creating the profile the pipeline refuses without

**D2 ships no working profile.** A run without one refuses and points here, which makes this the first
thing a new user does — and makes one failure worse than every other: a generated profile the suite's
own lint rejects.

So the command produces nothing until it has checked that what it would produce is valid.

## The procedure

Six steps, and **the two programs are not optional**. They hold the conversions and the publication
guards; a session that assembled a profile by hand would bypass the escaping, the containment checks
and the in-memory lint — which is the whole reason they exist as programs rather than as prose.

**1. Collect the git facts.** Read-only, from the target repository:

```
git -C <path> rev-parse --is-inside-work-tree     # is_git_repository
git -C <path> remote get-url origin               # remote
git -C <path> symbolic-ref --short refs/remotes/origin/HEAD   # default_branch
gh api user --jq .login                           # login, optional
```

A command that fails contributes its fact as absent rather than aborting the collection — the
preconditions are reported together, so they have to be *gathered* together.

**2. Detect.** Feed those facts, plus the repository root, to the detector:

```
scripts/detect_profile.py --facts - [--id <profile-id>]
```

It exits non-zero with every unmet precondition named, and otherwise prints the detected fields as
JSON. Its exit code is the answer to "can this repository have a profile at all".

**3. Interview.** Ask the five questions below. Each answer is added to the detected JSON under the
field named in the table — `id_shorthand` is fed back through the detector, since it becomes a pattern
rather than a value.

> **Why this file invokes `gh` at all.** Every other part of the pipeline reaches the source system
> through the [driver](../drivers/github.md), and `scripts/gh_boundary_lint.py` enforces that. This
> command is the exception, and the reason is structural rather than convenient: the driver is chosen
> by `source_driver` **in a profile**, and this is the command that creates the profile. Routing it
> through a driver would require the thing it is being run to produce.
>
> The exemption is one file and two read-only probes — identity, and whether the repository answers. It
> publishes nothing and reads nothing about a work item.

**4. Smoke-check the source.** With a login, confirm the repository actually answers:

```
gh issue list --repo <repo_id> --limit 1
```

A failure here is reported and does **not** stop the write: the profile is still valid, and the user
learns their access is the problem rather than their configuration. **Without a login this step is
skipped**, and the skip is reported — an unrun check reported as passing would be worse than either.

**5. Write.** Hand the complete field set to the writer:

```
scripts/write_profile.py --root <workspace> --fields - [--force]
```

It refuses unknown fields, refuses values the profile grammar cannot carry, lints the candidate before
publishing, and writes profile-then-pointer.

**6. Report what happened**, including anything skipped. Exit codes: `0` written; `1` bad input; `2` a
guard refused; `3` the candidate would not lint; `4` a write failed — and on `4` the message names an
orphaned profile if there is one.

## Preconditions — reported all at once

Three, checked in one pass and reported together:

1. the path is a **git repository** — `rev-parse --is-inside-work-tree`;
2. it has an **`origin` remote on github.com** — the only implemented [source driver](../drivers/github.md);
3. it has a **resolvable default branch**, which the work branch is cut from.

**Every missing requirement is named, not the first.** Learning one requirement per attempt is three
round trips for one answer.

**Authentication is not among them.** It decides whether the source smoke check can run, not whether a
valid profile can be written — so a missing login is a **warning**, the smoke check is skipped, and the
report says which. `branch_template` is deliberately independent of it for exactly this reason: a
required field that needed a login would leave an unauthenticated user with no valid output at all.

## Detection — read-only, and converted rather than copied

An `origin` URL is not a `url_regex`. Every detected fact passes through a stated conversion:

| Detected | Becomes | The conversion |
|---|---|---|
| `origin`, either spelling | `repo_id` | `owner/name` |
| host, owner, name | `url_regex` | anchored, **escaped**, capturing the number |
| default branch | `base_branch` | as-is; no branch name is assumed |
| repository root | `repo_path` | relative — the lint refuses an absolute one |
| authenticated login *(optional)* | `branch_template` | `<login>/ai/{id}-{slug}`, or `ai/{id}-{slug}` |
| `package.json`, `Makefile`, `Cargo.toml`, `go.mod`, `pom.xml` | `gates` | commands those files **actually declare** |

**Escaping is not optional.** A repository named `a.b` produces a pattern matching `axb` without it,
and the lint only checks that a pattern compiles.

**Gate detection proposes; it never invents.** Where nothing is found, `gates` is empty and the profile
says so — a guessed gate is a command the pipeline will run.

## The interview — five questions, each naming its field

Asked only for what a repository cannot answer.

| Question | Fills |
|---|---|
| What does a work item's id look like? `proj-N`, or bare numbers? | `id_pattern` |
| Do tests precede code here, and what counts as covered? | `tdd_policy` |
| What house rules should a reviewer enforce? | `anti_patterns` |
| What should a reviewer read before judging? | `mental_model_refs` |
| Which words select a scenario? | `scenario_overrides` |

The id shorthand becomes an **anchored, escaped** pattern: `proj-N` → `^proj-(\d+)$`, bare numbers →
`^(\d+)$`. Unanchored, `proj-(\d+)` matches inside `xproj-17`, which is a different item.

### Two questions this command does not ask

Recorded because their absence is a decision, not a gap.

- **The review-iteration cap.** `max_review_rounds` is a **per-run** flag; the profile contract has no
  field for it, and unknown fields are an error — so a profile carrying the answer would be rejected.
  The cap is genuinely per-run: an operator raises it for one difficult issue and lowers it again.
- **The reviewer backend.** `reviewer_backend` is optional and its domain is **`codex` alone**, so
  omitting the field selects exactly what the only legal answer would select. A question with one legal
  answer costs attention and returns nothing.

Both were narrowed by an amendment to this command's issue. If a contract field for the cap appears, or
a second backend, this is the decision to revisit.

## Two identifiers, and they are not the same string

`--id` supplies the **profile id** — `[a-z0-9][a-z0-9-]*`, no `/` or `.` — used for `profiles/<id>.md`
and for `issue2pr_profile`. `project_id` inside the profile is the **human-readable name**.

Absent `--id`, the id is derived from the repository name and **validated**: `My_Repo!` derives
`my-repo`, and a name deriving to nothing is a refusal rather than a fallback.

## Publishing — everything that can fail happens first

1. **Pin the root**, before any read.
2. **Preflight both destinations** — resolve, refuse a symlink, apply `--force`. Both, before either.
3. **Render and lint the candidate in memory.** A profile that would not pass is never written.
4. **Write the profile, then the pointer.** A pointer to a missing profile is the worse residue.
5. **If the pointer write fails**, the orphaned profile is **named**. Rolling it back would delete a
   file the user may want; silence would be worse than either.

`--force` covers **both** files: without it, an existing profile *or* a pointer aimed elsewhere stops
the command, and the message says which.

`.vibe-suite.md` is **edited, never rewritten** — every other key and the body survive byte for byte.

## What is refused rather than escaped

Gate commands come from files and interview answers come from people. The profile is read back by a
**closed grammar**: balanced quotes, two-space indentation, no multi-line scalars, no escaping
convention.

So a value carrying a newline, a control character or an unbalanced quote is **refused before
rendering**, naming the value. An escaping scheme the parser does not implement would produce a file
that renders and will not read back.
