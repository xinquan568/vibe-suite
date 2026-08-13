# NLPM Audit: alizarion/openclaw-claude-code-plugin
**Date**: 2026-04-06  |  **Artifacts**: 1  |  **Strategy**: single
**NL Score**: 92/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 4  |  **Security Findings**: 3

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/claude-code-orchestration/SKILL.md | skill | 92 | Vague quantifiers: "accordingly", "reasonable", "obvious", "too many" (-8) |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 3 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | none |
| Scripts | none |
| MCP configs | none |
| Package manifests | package.json |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Low | package.json | 24 | SEC-unpinned-semver | devDependency `esbuild` uses `^0.27.3` semver range — not pinned to an exact version |
| 2 | Low | package.json | 25 | SEC-unpinned-semver | devDependency `@sinclair/typebox` uses `^0.34.48` semver range — not pinned to an exact version |
| 3 | Low | package.json | 26 | SEC-unpinned-semver | devDependency `nanoid` uses `^3.3.7` semver range — not pinned to an exact version |

## Bugs (PR-worthy)
No bugs found.

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | package.json | Three devDependencies use `^` semver ranges, allowing minor/patch updates to pull in unvetted code during `npm install` | Pin to exact versions: `"esbuild": "0.27.3"`, `"@sinclair/typebox": "0.34.48"`, `"nanoid": "3.3.7"` |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/claude-code-orchestration/SKILL.md | Vague quantifier "accordingly" (line 31): "Adjust accordingly" gives no actionable criterion | -2 |
| 2 | skills/claude-code-orchestration/SKILL.md | Vague quantifier "reasonable" (line 152): "when only one is reasonable" leaves determination undefined | -2 |
| 3 | skills/claude-code-orchestration/SKILL.md | Vague quantifier "obvious" (line 152): "Respond with the obvious choice" is reader-dependent | -2 |
| 4 | skills/claude-code-orchestration/SKILL.md | Vague quantifier "too many" (line 252): "Don't launch too many sessions in parallel" — the numeric limit (default: 5) is stated one line earlier but not referenced here | -2 |

## Cross-Component
- `skills/claude-code-orchestration/SKILL.md` references `../../docs/AGENT_CHANNELS.md` (line 206) — file exists at `docs/AGENT_CHANNELS.md` ✓
- `metadata.openclaw.requires.plugins` names `openclaw-claude-code-plugin` — consistent with `package.json` name `@betrue/openclaw-claude-code-plugin` (scoped npm name; the unscoped plugin ID is conventional) ✓
- No orphaned components or stale counts detected across the single-artifact scope.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

The skill is well-structured with comprehensive examples, numbered checklists, and actionable anti-pattern tables. No frontmatter bugs, no broken references, no executable surfaces beyond the build-only devDependencies. The only actionable PR opportunity is pinning the three devDependency semver ranges in `package.json`. The four vague quantifiers are informational; the highest-value fix is replacing "too many" at line 252 with an inline reference to the `maxSessions` default already stated at line 249.
