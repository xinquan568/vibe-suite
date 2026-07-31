# Expected findings — `seeded-plugin/` (hand-derived oracle)

Authored by reading `skills/security/SKILL.md` against the fixture, before any scan was run.
Severities are **post-capping**. Any finding not listed here is an extra and fails the
comparison.

| # | Severity | File | Line | Pattern | Description |
|---|---|---|---|---|---|
| 1 | [CRITICAL] | scripts/install.sh | 3 | Pipe to shell | fetches remote code and runs it unreviewed |
| 2 | [HIGH] | scripts/install.sh | 14 | sudo | escalates privilege during install |
| 3 | [HIGH] | package.json | 4 | postinstall script | runs on every install, before review |
| 4 | [MEDIUM] | hooks/hooks.json | 4 | Hook references a script | hook command invokes a shell script |
| 5 | [MEDIUM] | hooks/hooks.json | 4 | Hook without a tool filter | PostToolUse with no matcher fires on every tool call |
| 6 | [LOW] | commands/notes.md | 5 | Pipe to shell | capped: a Critical signature inside a `.md` file |

## Required absences

Each is a capping or suppression rule with its own seed, asserted by absence:

| Seed | Where | Rule | Why it must not appear |
|---|---|---|---|
| D1 | `scripts/install.sh:6` | echo drop | the signature is inside an `echo` string, not executed |
| D2 | `scripts/install.sh:10` | heredoc drop | the signature is inside a quoted heredoc body |
| L1 | `package.json:3` (`left-pad: "*"`) | lockfile suppression | `package-lock.json` is present, so unpinned findings are suppressed entirely |

**No `.mcp.json` is seeded, deliberately.** Every MCP server this fixture could carry is
either local — firing nothing — or remote, and a remote server is simultaneously subject to
`Remote server (url not localhost)`, the safe-list check, the `auth` check, AND the skill's
unpinned-MCP rule, which has no name in the family's six. A seed that triggers an unnameable
finding cannot be recorded with a permitted `Pattern`, so it would make the oracle wrong
whichever way it was written. The four severity bands and all four capping rules are
exercised without it.

**The pinning distinction is therefore half-seeded, and the worksheet says so.**
`package.json`'s unpinned `left-pad` is suppressed by the lockfile (L1); the `.mcp.json`
counterpart is not seeded, for the reason above. Naming that check belongs to whoever next
edits the skill.

The `.md` cap is asserted as a **presence** at row 7 rather than an absence: the finding is
reported, at Low, not dropped. Confusing "capped" with "dropped" is the mistake this row
exists to prevent.

## Derived report values

- Severity counts — Critical 1, High 2, Medium 2, Low 1
- Highest severity present — Critical
- `Risk level: CRITICAL`
- `Recommendation: BLOCK` (ladder: any Critical or High → BLOCK)
- Gate banner — `SECURITY GATE: BLOCKED`
