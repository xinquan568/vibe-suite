# NLPM Audit: MemPalace/mempalace
**Date**: 2026-05-13  |  **Artifacts**: 15  |  **Strategy**: single
**NL Score**: 90/100
**Security**: CLEAR
**Bugs**: 1  |  **Quality Issues**: 13  |  **Security Findings**: 1

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude-plugin/commands/mine.md | command | 70 | Multi-step body, no output format, no empty input handling |
| .claude-plugin/commands/init.md | command | 80 | Multi-step body lacks numbered steps, no output format |
| .claude-plugin/commands/search.md | command | 80 | No output format, no empty input handling |
| .claude-plugin/plugin.json | manifest | 85 | `commands: []` while 5 command files exist |
| .claude-plugin/commands/help.md | command | 90 | No output format specified |
| .claude-plugin/commands/status.md | command | 90 | No output format specified |
| .claude-plugin/skills/mempalace/SKILL.md | skill | 94 | Vague: "short", "often", "significant" |
| integrations/openclaw/SKILL.md | skill | 94 | Stale version (3.3.0 vs 3.3.5); vague quantifiers |
| CLAUDE.md | project-doc | 94 | Vague: "real understanding", "instant", "vast amounts" |
| .claude-plugin/hooks/hooks.json | hook-config | 95 | Clean |
| .codex-plugin/skills/help/SKILL.md | skill | 95 | Clean |
| .codex-plugin/skills/init/SKILL.md | skill | 95 | Clean |
| .codex-plugin/skills/mine/SKILL.md | skill | 95 | Clean |
| .codex-plugin/skills/search/SKILL.md | skill | 95 | Clean |
| .codex-plugin/skills/status/SKILL.md | skill | 95 | Clean |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hook scripts (root) | hooks/mempal_save_hook.sh, hooks/mempal_precompact_hook.sh |
| Hook scripts (claude-plugin) | .claude-plugin/hooks/mempal-stop-hook.sh, .claude-plugin/hooks/mempal-precompact-hook.sh |
| Hook scripts (codex-plugin) | .codex-plugin/hooks/mempal-hook.sh |
| MCP config | .claude-plugin/.mcp.json |
| Package manifest | website/package.json |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Low | website/package.json | null | SEC-unpinned-semver | Five dev dependencies use caret ranges (^1.8.0, ^11.14.0, ^1.6.4, ^2.0.17, ^3.5.32); private docs package so supply-chain exposure is minimal |

**Hook review notes**: The two root hooks (mempal_save_hook.sh, mempal_precompact_hook.sh) demonstrate deliberate security hardening: they use `mapfile` + single-pass Python sanitization to avoid `eval`, validate transcript paths for `.json`/`.jsonl` suffix and absence of `..` traversal, and pass the transcript file via `sys.argv` to the Python inline script rather than interpolating into the command string. The `.claude-plugin` and `.codex-plugin` wrapper hooks are thin CLI delegates with no logic of their own. No critical or high patterns detected.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | integrations/openclaw/SKILL.md | `version: 3.3.0` in frontmatter is stale; plugin.json declares `3.3.5` | OpenClaw registries that key on skill version will advertise the wrong version; users on auto-update pipelines may receive a mismatched SKILL.md |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | website/package.json | Five dev dependencies use unpinned caret ranges | Pin to exact versions (remove `^`) or lock via `npm ci` with a committed lockfile; low urgency since this is a private docs package |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .claude-plugin/commands/help.md | No output format specified — reader cannot tell what format the help output takes | -10 |
| 2 | .claude-plugin/commands/init.md | Multi-step operation (install, init, configure MCP, verify) but command body has no numbered steps | -10 |
| 3 | .claude-plugin/commands/init.md | No output format specified | -10 |
| 4 | .claude-plugin/commands/mine.md | Multi-step operation (classify source, mine, store) but command body has no numbered steps | -10 |
| 5 | .claude-plugin/commands/mine.md | No output format specified | -10 |
| 6 | .claude-plugin/commands/mine.md | Has `argument-hint` but no empty-input handling — if user invokes with no argument, behavior is undefined | -10 |
| 7 | .claude-plugin/commands/search.md | No output format specified | -10 |
| 8 | .claude-plugin/commands/search.md | Has `argument-hint` but no empty-input handling — silent failure if query is omitted | -10 |
| 9 | .claude-plugin/commands/status.md | No output format specified | -10 |
| 10 | .claude-plugin/skills/mempalace/SKILL.md | Vague "short" (line 51): "keep it short" gives no concrete guidance on query length | -2 |
| 11 | .claude-plugin/skills/mempalace/SKILL.md | Vague "often" / "significant" (line 57): "often catches more near-duplicates without significant false positives" — unquantified tradeoff | -4 |
| 12 | integrations/openclaw/SKILL.md | Same vague terms as #10–11 at equivalent lines (query "short", threshold "often"/"significant") | -6 |
| 13 | CLAUDE.md | Vague "real understanding" (line 5), "instant" (line 27), "vast amounts" (line 12) in design-principle prose | -6 |

## Cross-Component
**Empty `commands` array in plugin.json**: `plugin.json` declares `"commands": []` while five command files exist under `.claude-plugin/commands/`. If Claude Code auto-discovers commands from the `commands/` directory the empty array is harmless; if explicit registration is required, none of the five commands would be registered. The correct behavior depends on the Claude Code plugin spec version — worth confirming.

**Version drift between plugin surfaces**: `integrations/openclaw/SKILL.md` carries `version: 3.3.0` in its YAML frontmatter while `plugin.json` declares `3.3.5`. These should be kept in sync on every release. No other broken references were found: hook script paths in `hooks.json` resolve correctly, the `.mcp.json` MCP command name matches `plugin.json`, and the CLAUDE.md project structure listing matches the files present on disk.

**Dual-implementation architecture**: `.claude-plugin/skills/mempalace/SKILL.md` is a single monolithic skill while `.codex-plugin/skills/` breaks the same surface into five per-command skills. Both approaches are valid and internally consistent; the asymmetry is not a defect but a deliberate cross-harness adaptation.

## Recommendation
CLEAR — submit PRs for the one bug (stale version in openclaw SKILL.md) and the low-severity security fix (pin dev deps). Quality improvements to command output formats and empty-input handling are informational and can be batched into a follow-up PR.
