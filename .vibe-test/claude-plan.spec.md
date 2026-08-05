---
artifact: codex-src/claude-plan/SKILL.md
type: skill
min_score: 80
---

# claude-plan — codex-src source spec (vibe-53 / E7.1)

Source: F9.6(d) reverse-delegation source set — Codex asks Claude for a read-only implementation plan via the pinned server. This spec states the contract before the
artifact exists (NL-TDD RED); the author inherits these expectations.

## Triggers On

- a complex task needing a plan before code is written
- "have Claude plan this" or "have Claude figure out the design"
- work touching multiple interconnected files with an unclear approach
- unclear requirements needing decomposition
- wanting numbered steps with exact file paths before implementing

## Does Not Trigger On

- executing the plan's edits (claude-implement's job)
- reviewing already-written code (claude-review's job)
- verifying fixes landed (verify's job)

## Output Contains

- a numbered plan with per-step files, interfaces, and dependencies
- trailing risk areas, open questions, and recommended test scenarios

## Frontmatter Valid

- name matches the directory name and description is non-empty
