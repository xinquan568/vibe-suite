# Expected findings — `seeded-plugin/` (hand-derived oracle)

Authored by reading `skills/security/SKILL.md` against the fixture, before any scan was run.
Severities are **post-capping**. Any finding not listed here is an extra and fails the
comparison.

| # | Severity | File | Line | Pattern | Description |
|---|---|---|---|---|---|
| 1 | [CRITICAL] | scripts/install.sh | 3 | Pipe to shell | fetches remote code and runs it unreviewed |
| 2 | [HIGH] | scripts/install.sh | 14 | sudo | escalates privilege during install |
| 3 | [HIGH] | package.json | 4 | postinstall script | runs on every install, before review |
| 4 | [HIGH] | .mcp.json | 1 | Remote server (`url` not localhost) | contacts a non-local MCP endpoint |
| 5 | [MEDIUM] | hooks/hooks.json | 4 | Hook references a script | hook command invokes a shell script |
| 6 | [MEDIUM] | hooks/hooks.json | 4 | Hook without a tool filter | PostToolUse with no matcher fires on every tool call |
| 7 | [LOW] | commands/notes.md | 5 | Pipe to shell | capped: a Critical signature inside a `.md` file |

## Required absences

Each is a capping or suppression rule with its own seed, asserted by absence:

| Seed | Where | Rule | Why it must not appear |
|---|---|---|---|
| D1 | `scripts/install.sh:6` | echo drop | the signature is inside an `echo` string, not executed |
| D2 | `scripts/install.sh:10` | heredoc drop | the signature is inside a quoted heredoc body |
| L1 | `package.json:3` (`left-pad: "*"`) | lockfile suppression | `package-lock.json` is present, so unpinned findings are suppressed entirely |

The `.md` cap is asserted as a **presence** at row 7 rather than an absence: the finding is
reported, at Low, not dropped. Confusing "capped" with "dropped" is the mistake this row
exists to prevent.

## Derived report values

- Severity counts — Critical 1, High 3, Medium 2, Low 1
- Highest severity present — Critical
- `Risk level: CRITICAL`
- `Recommendation: BLOCK` (ladder: any Critical or High → BLOCK)
- Gate banner — `SECURITY GATE: BLOCKED`
