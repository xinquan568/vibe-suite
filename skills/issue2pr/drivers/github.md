# The github driver

Implements the core's [driver protocol](../SKILL.md) against GitHub. This is the one file in the
pipeline that invokes `gh` — `scripts/gh_boundary_lint.py` enforces that, and the enforcement is the
reason the seam holds rather than merely being described.

<!-- implements -->
```json
["fetch_item", "refresh_item", "open_change", "update_change", "read_change_state", "link_closure"]
```

All six. There is no partial conformance: a caller cannot know which half it has.

## Operations

### `fetch_item`

```sh
gh issue view <n> --repo <repo_id> --json number,title,body,comments,state
```

**`not_an_item` is a real case, not a defensive one.** A pull request and an issue share a number
space, so `gh issue view 42` against a PR number succeeds in some shapes and fails in others. The
driver checks what it got and refuses rather than starting a run against the wrong object.

### `refresh_item`

```sh
gh issue view <n> --repo <repo_id> --json comments,title,body
```

Filtered against `since` by the driver. The delta is the difference from the snapshot, not a re-read
handed upward.

### `open_change`

```sh
gh pr create --repo <repo_id> --base <base_branch> --head <branch> --title <title> --body-file -
```

An existing PR for the head branch is `exists`, which is distinct from `rejected` — the first means the
work is already published, the second means it was refused.

### `update_change`

```sh
gh api -X PATCH repos/<repo_id>/pulls/<n> -f body=@-
```

The REST endpoint rather than `gh pr edit`, because a body containing markdown that looks like a flag
survives a request body where it may not survive an argument.

### `read_change_state`

```sh
gh api repos/<repo_id>/issues/<n>/comments --paginate
gh api repos/<repo_id>/pulls/<n>/comments --paginate
gh api repos/<repo_id>/pulls/<n>/reviews
gh api repos/<repo_id>/commits/<sha>/check-runs
gh pr view <n> --repo <repo_id> --json state,mergeable,mergedAt
```

Five calls, because they are four independent collections plus the change itself.

**Two of the five accept a time parameter and three do not** — the issue-comments and
pull-review-comments listings do; reviews, check-runs and the change view do not. So the driver
filters the last three itself, against `since`. That asymmetry is why the obligation is "the driver
filters", stated in the [driver contract](../references/driver-contract.md), rather than "the source
filters": a contract written from the two convenient cases would have been wrong about the other three.

### `link_closure`

```sh
gh api -X PATCH repos/<repo_id>/pulls/<n> -f body=@-
```

The closing reference lives in the body, so this is `update_change`'s mechanism with a different
intent. It is a separate operation because a caller asking "record that this closes that" should not
have to know how the record is stored.

## Failure mapping

| GitHub signal | Class | What the core does |
|---|---|---|
| connection error, DNS failure, timeout before a response | `unavailable` | retry |
| HTTP 403 with the rate-limit headers | `rate_limited` | wait until the reset it carries, then retry |
| HTTP 401, or 403 without rate-limit headers | `unauthorized` | stop and tell the operator |
| HTTP 200 whose body is not the documented shape | `unusable` | stop; the system answered and the answer is the problem |

**`rate_limited` carries its reset time.** Without it the class is indistinguishable from
`unavailable`, and a wait becomes a spin.

**`unauthorized` and `rate_limited` are both 403 in some responses**, which is exactly why the headers
decide rather than the status. Reading the status alone would turn a permanent failure into an infinite
retry.

## What this driver does not do

- **It runs no gate.** Gates are the pipeline's.
- **It writes nothing to the worktree.**
- **It decides nothing.** It reports that a comment arrived; whether that starts a round is the core's.
