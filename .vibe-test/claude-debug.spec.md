---
artifact: codex-src/claude-debug/SKILL.md
type: skill
min_score: 80
---

# claude-debug — codex-src source spec (vibe-53 / E7.1)

Source: F9.6(d) reverse-delegation source set — Codex sends a bug with its reproduction to Claude for root-cause and fix. This spec states the contract before the
artifact exists (NL-TDD RED); the author inherits these expectations.

## Triggers On

- a failing test whose cause is unclear
- "have Claude debug this"
- an error trace pointing deep into framework code
- wrong behavior with the cause buried in the codebase
- obvious fixes already tried and ruled out

## Does Not Trigger On

- broad quality assessment without a specific symptom (audit's job)
- implementing a feature (claude-implement's job)
- confirming earlier findings were fixed (verify's job)

## Output Contains

- a root cause, the fix at file:line, and the verification result
- adjacent issues found near the reported symptom

## Frontmatter Valid

- name matches the directory name and description is non-empty
