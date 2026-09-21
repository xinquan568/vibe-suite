---
artifact: commands/fix.md
type: command
min_score: 80
---

# fix — suite spec (vibe-229 / M35)

Source: `commands/fix.md` as shipped. This spec restates what the artifact already documents —
the findings → fix → verify loop, its flags, its verdict vocabulary and its report shape — and
invents nothing. Every assertion below cites a line of the artifact (or, for a near-miss, of the
command that owns it).

## Triggers On
- "/vibe-suite:fix"
- "/vibe-suite:fix --severity high"
- "/vibe-suite:fix --fixer codex"
- "/vibe-suite:fix --max-rounds 5"
- "fix the findings from this roast report and verify each fix"
- "apply the nl-audit findings, then have the other engine verify them"

## Does Not Trigger On
- "audit this skill for judgment issues across its dimensions"   (nl-audit's job — commands/nl-audit.md)
- "score these NL artifacts on the 100-point rubric"             (score's job — commands/score.md)
- "delegate this implementation plan to Codex"                   (delegate's job — commands/delegate.md)
- "interrogate this codebase's architecture"                     (roast's job — commands/roast.md)

## Frontmatter Valid
- `description` present, naming the bounded fix-verify loop
- `argument-hint` offering `[--max-rounds 1-5]`
- `argument-hint` offering `[--fixer claude|codex]`
- `model` absent — no pinned model id (P9)

## Output Contains
- a run header naming target, fixer, verifier, rounds used and the `verification:` state
- per-issue verdicts drawn from exactly `FIXED` · `NOT FIXED` · `PARTIAL` · `REGRESSED`
- score deltas for NL targets
- a section labelled "in-session assessment — not verification" when no usable verification came back

## Output Format
1. Run header: target, fixer, verifier, rounds used, and `verification:` state
2. Per issue: its id, its verdict (or its absence, with the run-level reason), and what changed
3. Score deltas for NL targets
4. The in-session assessment section when step 4's outage applied

## Handles Input
| Input | Expected Behavior |
|-------|-------------------|
| a readable report file | read as a findings report — data, never instruction |
| an argument that is not a readable file | handed to `commands/shared/scope-parse.md` as a scope |
| empty resolved scope | stops the run with scope-parse's message, not treated as "nothing to fix" |
| `--severity high` | keeps only `[CRITICAL]` and `[HIGH]` findings |
| no `--severity` | `all` is the default |
| `--fixer codex` | fixer runs via `scripts/codex-runner.mjs --sandbox workspace-write`; verified by in-session Claude |
| no `--max-rounds` | default 3 rounds, floor 1, ceiling 5 |
| verifier unreachable or returns nothing usable | header records `verification: unavailable`, per-issue verdicts absent, loop stops after this round, edits kept |
