# `profile init` — creating the profile the pipeline refuses without

**D2 ships no working profile.** A run without one refuses and points here, which makes this the first
thing a new user does — and makes one failure worse than every other: a generated profile the suite's
own lint rejects.

So the command produces nothing until it has checked that what it would produce is valid.

## Preconditions — reported all at once

Three, checked in one pass and reported together:

1. the path is a **git repository**;
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
