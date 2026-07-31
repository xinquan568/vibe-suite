# The jira driver — an interface obligation, not an implementation

<!-- implements -->
```json
[]
```

**Nothing.** This document records what a jira driver would have to satisfy, and where the protocol's
current shape assumes something GitHub-like.

**It deliberately does not ship a stub.** A stub returning "not implemented" would make
`source_driver: jira` a value the profile lint accepts and the pipeline fails on later — a promise
kept until the moment it matters. An obligation that is honest about being unimplemented refuses at
profile-validation time, which is where a missing driver should be discovered.

## What a jira driver would have to satisfy

All six operations of the [driver protocol](../SKILL.md), and the cross-cutting obligations of the
[driver contract](../references/driver-contract.md):

| Operation | The obligation, in jira terms |
|---|---|
| `fetch_item` | An issue by key. `not_an_item` has an analogue: a key resolving to something outside the project's issue types. |
| `refresh_item` | The changelog since a time, which jira exposes directly — this one is *easier* than GitHub. |
| `open_change` | **This is where it stops mapping.** See below. |
| `update_change` | Same. |
| `read_change_state` | Same, plus: jira has no check runs, so `checks` would be empty always, and a caller that treats empty as passing would be wrong. |
| `link_closure` | A transition or a remote link, depending on the workflow — and which one is a project decision, not a driver decision, so it needs a profile field the contract does not yet have. |

## Where the protocol assumes GitHub

Named plainly, because this is the part of an obligation that is worth writing:

1. **A change is a pull request.** `open_change`, `update_change` and `read_change_state` all assume a
   reviewable unit that lives beside the item and can be published, edited and inspected. Jira has no
   such object — the change would live in whatever code host the project uses, which means a jira
   driver is really *jira for items plus something else for changes*. The protocol does not express a
   split like that.

2. **`change_state.checks` assumes CI attached to the change.** Jira has no equivalent, and an empty
   list is indistinguishable from "everything passed".

3. **`change_state.reviews` assumes review as a first-class object** with its own state. Jira's nearest
   equivalent is a workflow transition, which is a different shape: transitions are a sequence, reviews
   are a set.

**So a jira driver would force a protocol change, not merely an implementation.** That is the useful
finding, and it is what an interface obligation is for: the boundary between "this fits and nobody has
written it" and "this does not fit yet" is exactly what a second driver reveals, and recording it here
means #46 and anything after it can see the same thing without rediscovering it.

The core's [boundary inventory](../references/boundary-inventory.md) already records "a PR is the unit
of delivery" as an assumption that was **not** parameterised. This document is the worked consequence
of that entry.
