# The source-driver contract

What implementing the core's driver protocol means.

The protocol is declared in [`../SKILL.md`](../SKILL.md)'s `driver-protocol` block. This document says
what a driver must do to satisfy it, and records the response mapping the fixtures under
[`tests/fixtures/issue2pr/gh-responses/`](../../../tests/fixtures/issue2pr/gh-responses/) establish.

## The mapping, and what it overturned

This table is the spike's output, produced **before** the protocol was refined. It exists because the
first draft of this issue's plan proposed three refinements and called them implementation-driven while
scheduling the implementation afterwards. The fixtures were built to settle those questions, and they
settled two of them **against** the proposal.

| Scenario | Invocation | Observation | What it decided |
|---|---|---|---|
| new general comment | issue-comments listing | a comment exists after T | listing **accepts** a time parameter |
| new review comment | pull-review-comments listing | a review comment exists after T | a **different collection**; also accepts a time parameter |
| review submitted | reviews listing | state changed with **no comment** | listing does **not** accept a time parameter |
| check failed | check-runs listing | a check moved to failure | does **not** accept a time parameter |
| merged | change view | the change landed | not a listing; no time parameter |
| transport failure | any | could not ask | retryable |
| auth failure | any | refused, permanently | **not** retryable |
| rate limit | any | declined now, allowed later | retryable **after** a stated time |
| malformed | any | answered, unusably | not retryable |

### `since` — kept, and its meaning fixed by the evidence

Only two of the five observation scenarios can filter at the source. Reviews, checks and the merge
state cannot.

So `since` stays an input to `read_change_state`, and the contract fixes what it means: **the driver
filters, by whatever means its system allows.** Where the source supports a time parameter the driver
uses it; where it does not, the driver fetches and filters. What the core never does is receive
everything and diff — that is the driver's work relocated, and relocating it is how a seam stops
holding.

### `updated_at` — rejected, because a single timestamp cannot say what moved

This was the review's objection and the fixtures confirm it. Comments, review comments, reviews and
checks are **four independent collections** with their own timestamps. One `change_state.updated_at`
would say that something changed while leaving the caller to re-read everything to find out what —
which is the diffing this seam exists to prevent.

`change_state` instead carries **what is new since the requested time**, per collection. The caller
asks a question with a time in it and gets an answer scoped to that time, rather than a snapshot plus a
hint.

### `unavailable` — rejected as a single error, because it conflates three decisions

The four failure fixtures produce three distinct classes, and the difference is **what the caller
should do next**:

| Class | Retryable | What the core does differently |
|---|---|---|
| `unavailable` | yes | retry |
| `rate_limited` | yes, **after a stated time** | wait, then retry |
| `unauthorized` | no | stop and tell the operator |
| `unusable` | no | the system answered; the answer is the problem |

Collapsing these into one error would make the core unable to distinguish "wait and try again" from
"stop, this will never work" — and the second, presented as the first, is an infinite retry loop.

`unusable` is the one worth naming separately even though it is also non-retryable: the system was
reachable and did answer, so it is not an availability problem at all, and reporting it as one sends
someone to look at the wrong thing.

## Obligations

Every driver, whatever system it fronts.

### Per operation

One row per operation in the protocol. A driver that cannot satisfy a row does not implement the
protocol; there is no partial conformance, because a caller cannot know which half it has.

| Operation | Obligation |
|---|---|
| `fetch_item` | Return the declared snapshot for an existing item. Distinguish an item that does not exist from one that exists and is not a work item — a pull request is not an issue, and treating one as the other starts a run against the wrong thing. Errors: `not_found`, `not_an_item`, plus the failure classes. |
| `refresh_item` | Return the declared delta relative to the given time. Errors: `not_found`, plus the failure classes. |
| `open_change` | Publish a change from a branch and return its `change_ref`. Distinguish "one already exists" from "this was refused". Errors: `exists`, `rejected`, plus the failure classes. |
| `update_change` | Replace the change's body. Errors: `not_found`, `rejected`, plus the failure classes. |
| `read_change_state` | Return the declared state, **scoped to `since`**, filtering wherever the source cannot. Errors: `not_found`, plus the failure classes. |
| `link_closure` | Record that the change closes the item. Errors: `not_found`, plus the failure classes. |

### Cross-cutting

- **A driver never runs a gate and never writes to the worktree.** It answers about the source system
  and publishes to it. Gates are the pipeline's, and a driver that ran one would be a second
  implementation of the machine.
- **A driver maps its system's failures onto the declared classes**, all four of them. They are not
  optional, and they are not interchangeable: their whole content is what the caller does next.
- **A driver returns the declared shapes and nothing more.** An extra field is an invitation, and a
  caller that learns to read it has bound itself to one driver — at which point there is no seam,
  only a habit.
- **A driver decides nothing.** Whether a new comment should trigger a round, whether a merge should
  advance a chain — those are the core's. The driver reports; the core acts. What the core does with
  each report is stated in [operational-modes.md](operational-modes.md); the watcher exit→chain
  action map there is the merge case in full.

## What the core decides, and what a driver reports

The line, from both sides, because #46 tests it:

| | Driver | Core |
|---|---|---|
| a new comment exists | reports | decides whether to start a round |
| a check failed | reports | decides whether that blocks |
| the change merged | reports | decides whether a chain advances |
| the system is rate-limited | reports, with the reset time | decides whether to wait or stop |

Every core decision above is made from fields the protocol declares. That is the property this
document exists to establish: a decision needing information the protocol does not carry is a protocol
gap, and it is found here rather than two links later.
