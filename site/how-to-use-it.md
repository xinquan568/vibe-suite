# How to use it

Start with a score. It is the cheapest signal and it tells you whether anything else is worth
running:

```
/vibe-suite:score
```

The output is a per-file table with a penalty attached to every deduction. Penalties are fixed and
published, so the number does not drift between runs and two people reading the same report reach
the same conclusion.

## When the score is low

Run `/vibe-suite:check` next. Scores measure a file against the rules; `check` measures files
against *each other* — a skill referenced by an agent that no longer exists, a command whose shared
partial was renamed, terminology that means two different things in two directories.

## When you want the fix, not the finding

`/vibe-suite:fix` applies the repairs that are mechanically safe — missing frontmatter fields,
absent headings, renamed fields — and leaves the judgement calls alone. It reports what it changed
and what it deliberately did not.

## When you are writing something new

Write the specification first. `/vibe-suite:test` runs `.spec.md` files against the artifacts they
describe, so you can watch a prompt fail its own trigger test before you write the prompt. That is
the same red-green loop you would use for code, applied to the part of the system that is prose.
