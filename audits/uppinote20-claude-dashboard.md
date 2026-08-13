# NLPM Audit: uppinote20/claude-dashboard
**Date**: 2026-04-28  |  **Artifacts**: 6  |  **Strategy**: single
**NL Score**: 99/100
**Security**: REVIEW
**Bugs**: 1  |  **Quality Issues**: 3  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| commands/setup.md | command | 97 | `Bash(cat:*)` declared but no step uses cat |
| CLAUDE.md | project-doc | 98 | "comprehensive" vague quantifier |
| commands/setup-alias.md | command | 98 | "appropriate" vague quantifier in step-2 heading |
| .claude-plugin/plugin.json | manifest | 100 | None |
| commands/check-usage.md | command | 100 | None |
| commands/update.md | command | 100 | None |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 |
| Medium | 3 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Scripts | `scripts/build.js`, `scripts/statusline.ts`, `scripts/check-usage.ts` |
| Package manifests | `package.json` |
| Hooks | None |
| MCP configs | None |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | High | commands/check-usage.md | 39 | unquoted-user-args | `$ARGUMENTS` passed unquoted to `node` shell invocation; shell metacharacters in user input execute as shell commands |
| 2 | Medium | commands/setup.md | 209 | file-write-outside-repo | Writes `~/.claude/settings.json` outside plugin repo — **false positive**: this is the command's documented purpose |
| 3 | Medium | commands/setup-alias.md | 58 | file-write-outside-repo | Appends function to `~/.zshrc` / `~/.bashrc` outside plugin repo — **false positive**: documented as a shell-alias installer |
| 4 | Medium | commands/update.md | 22 | file-write-outside-repo | Writes `~/.claude/settings.json` outside plugin repo — **false positive**: documented update path for plugin version pointer |
| 5 | Low | package.json | 23 | unpinned-semver | Four `devDependencies` use `^` ranges (`@types/node ^20`, `esbuild ^0.20`, `typescript ^5.0`, `vitest ^4.0.16`) |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | CLAUDE.md | Project structure tree (lines 21–22) lists only `setup.md` and `check-usage.md` under `commands/`, omitting `setup-alias.md` and `update.md` | Misleads contributors: two shipped commands are invisible in the authoritative structure docs |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | package.json | Unpinned `^` semver on all four devDeps | Pin to exact versions matching the lock file (e.g. `"esbuild": "0.20.2"`), or add a weekly `npm audit` CI step |

**Note**: The High finding (#1, `commands/check-usage.md`) requires targeted disclosure rather than a public PR — see Recommendation below. Medium findings #2–4 are false positives (expected config-write behavior) and need no fix.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | commands/setup.md | `Bash(cat:*)` declared in `allowed-tools` (line 5) but no task step uses `cat`; all file creation goes through `Write` and `jq` | −3 |
| 2 | CLAUDE.md | "comprehensive" on line 5 is a vague quantifier ("comprehensive status line") | −2 |
| 3 | commands/setup-alias.md | Step-2 heading reads "add the **appropriate** function" — selection criteria are fully specified below, but the heading itself contains a vague qualifier | −2 |

## Cross-Component
**CLAUDE.md structure vs. filesystem**: The project structure tree in CLAUDE.md shows exactly two command files (`setup.md`, `check-usage.md`). The actual `commands/` directory contains four: `setup.md`, `check-usage.md`, `setup-alias.md`, and `update.md`. Contributors reading CLAUDE.md will not discover the alias-setup or update commands. This is the same root cause as Bug #1 above.

No broken tool references, no orphaned agents, no contradictions in frontmatter declarations.

## Recommendation
**REVIEW** — Submit NL fix PRs for Bug #1 (CLAUDE.md structure) and the Low security fix (package.json semver pinning). For the High security finding (`$ARGUMENTS` injection in `commands/check-usage.md`), open a private issue on the target repo rather than a public PR: the fix is a one-character change (add quotes: `"$ARGUMENTS"`), but it should be disclosed to the maintainer before going public. The three Medium findings are false positives and need no action. Quality issues are informational; fixing them brings the repo to 100/100 NL score.
