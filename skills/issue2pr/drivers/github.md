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
gh api -X GET repos/<repo_id>/issues/<n>/comments -f since=<since> --paginate
gh issue view <n> --repo <repo_id> --json title,body,updatedAt
```

**New comments come from the listing's own `since`.** `title_changed` and `body_changed` cannot: GitHub
exposes no per-field history on this path, and `updatedAt` moves for any edit including a new comment.

So the protocol carries `previous_snapshot`, and the driver compares against it. That is a
protocol input, not hidden driver state, because the alternative is a driver that remembers — and a
driver that remembers is one whose answers depend on which process asked. The core already freezes a
snapshot per run; handing it back is what makes the delta derivable at all.

Without that input this operation cannot return the declared `source-delta`, and saying so would have
been the honest alternative to computing it somewhere invisible.

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
gh api -X GET repos/<repo_id>/issues/<n>/comments -f since=<since> --paginate
gh api -X GET repos/<repo_id>/pulls/<n>/comments  -f since=<since> --paginate
gh api repos/<repo_id>/pulls/<n>/reviews --paginate
gh api repos/<repo_id>/commits/<sha>/check-runs --paginate
gh pr view <n> --repo <repo_id> --json state,mergeable,mergedAt,updatedAt
```

Five calls: four independent collections plus the change itself.

**`-X GET` is required on the two that take `since`.** `gh api` switches to POST as soon as a field is
added, so the obvious spelling turns a read into a write. Omitting it is not a style slip — it is the
difference between listing comments and attempting to create one.

**Three of the five cannot filter at the source, so the driver filters them.** Reviews, check-runs and
the change view take no time parameter, so the driver applies the predicate itself:

| Collection | Predicate applied against `since` |
|---|---|
| reviews | `submitted_at > since` |
| check-runs | `completed_at > since`, or `started_at > since` when a run is still in progress |
| the change | `updatedAt > since` decides whether `state` and `mergeable` are reported as changed |

`state` and `mergeable` are **current values, not deltas** — a change is open or it is not — and
`updatedAt` is what says whether that value moved within the window. Reporting them unconditionally
would make every poll look like a transition.

That asymmetry is exactly why the contract says *the driver filters* rather than *the source filters*.
A rule written from the two convenient cases would have been wrong about the other three.

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
| no response — connection error, DNS failure, timeout | `unavailable` | retry |
| HTTP 429 | `rate_limited` | wait for `Retry-After`, then retry |
| HTTP 403 carrying `Retry-After` | `rate_limited` | wait for `Retry-After`, then retry |
| HTTP 403 with `x-ratelimit-remaining: 0` **and** a reset | `rate_limited` | wait for the reset, then retry |
| any other HTTP 401 or 403 | `unauthorized` | stop and tell the operator |
| HTTP 2xx whose body is not the documented shape | `unusable` | stop; the system answered and the answer is the problem |

**Rate-limit headers accompany ordinary responses**, so their mere presence proves nothing. A 403
carrying `x-ratelimit-remaining: 4998` is a permission failure, and classifying it as throttling would
retry it forever. Only `remaining: 0` with a reset is the primary limit.

**A secondary limit arrives as either 403 or 429**, and the 403 form is the trap: it carries
`Retry-After` while leaving `remaining` non-zero, so the primary-limit test does not see it and a rule
that mapped every other 403 to `unauthorized` would stop a run that would have succeeded after the
stated wait. `Retry-After` is what distinguishes it from a permission failure.

**Both throttling forms carry when to retry**, and that is not optional — without a time the class is
indistinguishable from `unavailable`, and a wait becomes a spin. **Retries are bounded**: the classes
say whether to retry, not to retry indefinitely.

## What this driver does not do

- **It runs no gate.** Gates are the pipeline's.
- **It writes nothing to the worktree.**
- **It decides nothing.** It reports that a comment arrived; whether that starts a round is the core's.
