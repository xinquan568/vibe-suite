# Subtask brief — widget cache eviction

The body a manifest-mode run works from when its parent is a brief file rather than a tracked issue.
`subtask.body_path` in the manifest beside this file points here, which is why the example is a pair:
the contract makes `body_path` required, so a manifest shipped alone would reference nothing.

**Placeholder, deliberately.** The repository id and base branch in the manifest belong to no real
project — manifest mode is project-neutral, and an example carrying a real one would teach the
opposite.

## What the subtask asks for

Evict cached widgets on write rather than on a timer, so a reader never sees a value the writer has
already replaced.

## Constraints

- The cache is shared across requests; eviction must be safe under concurrent writes.
- No behavioural change when the cache is cold.
