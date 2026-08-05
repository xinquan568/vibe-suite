---
artifact: codex-src/verify/SKILL.md
type: skill
min_score: 80
---

# verify — codex-src source spec (vibe-53 / E7.1)

Source: F9.6(d) reverse-delegation source set — Claude confirms fix closure, preferring the prior audit session. This spec states the contract before the
artifact exists (NL-TDD RED); the author inherits these expectations.

## Triggers On

- confirming issues from a prior audit were fixed
- the final step of an audit-fix cycle
- checking a manual fix landed at the right location
- continuing a prior audit session for sharper verdicts
- rendering per-finding verdicts with evidence

## Does Not Trigger On

- discovering new findings (audit's job)
- applying the fixes themselves (claude-implement's job)
- planning future work (claude-plan's job)

## Output Contains

- a verdict table with FIXED, NOT FIXED, PARTIAL, or REGRESSED per issue
- result counts and explanations for every non-FIXED verdict

## Frontmatter Valid

- name matches the directory name and description is non-empty
