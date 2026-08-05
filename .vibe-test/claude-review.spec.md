---
artifact: codex-src/claude-review/SKILL.md
type: skill
min_score: 80
---

# claude-review — codex-src source spec (vibe-53 / E7.1)

Source: F9.6(d) reverse-delegation source set — Codex delegates a read-only code review to Claude via the pinned server. This spec states the contract before the
artifact exists (NL-TDD RED); the author inherits these expectations.

## Triggers On

- a Codex session that just wrote code and wants Claude's independent review
- "get Claude to review this"
- wanting a second opinion on architecture, security, correctness, or test coverage
- a review needing a fresh session's deep context
- pre-commit judgment on files just modified

## Does Not Trigger On

- applying fixes autonomously (claude-implement's job)
- tracing a specific bug to root cause (claude-debug's job)
- a structured multi-dimension audit with severity summary (audit's job)

## Output Contains

- a findings table with File:line, Severity, Category, Issue, and Suggested fix columns
- a severity summary and a recommended action

## Frontmatter Valid

- name matches the directory name and description is non-empty
