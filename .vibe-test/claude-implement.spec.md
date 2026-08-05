---
artifact: codex-src/claude-implement/SKILL.md
type: skill
min_score: 80
---

# claude-implement — codex-src source spec (vibe-53 / E7.1)

Source: F9.6(d) reverse-delegation source set — Codex delegates autonomous implementation to Claude via the pinned server. This spec states the contract before the
artifact exists (NL-TDD RED); the author inherits these expectations.

## Triggers On

- delegating an implementation task to Claude end to end
- "have Claude implement this"
- changes needing large-codebase understanding before writing
- multi-file interdependent edits better done autonomously
- applying fixes a review or plan already scoped

## Does Not Trigger On

- planning without writing code (claude-plan's job)
- read-only review of existing code (claude-review's job)
- diagnosing a failing test without a scoped fix (claude-debug's job)

## Output Contains

- a report of files changed with reasons, test results, and deferred items
- an iteration path via the saved implementation session

## Frontmatter Valid

- name matches the directory name and description is non-empty
