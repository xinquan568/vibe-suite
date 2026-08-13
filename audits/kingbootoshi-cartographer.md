# NLPM Audit: kingbootoshi/cartographer
**Date**: 2026-06-20  |  **Artifacts**: 2  |  **Strategy**: single
**NL Score**: 85/100
**Security**: REVIEW
**Bugs**: 1  |  **Quality Issues**: 3  |  **Security Findings**: 3

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| plugins/cartographer/.claude-plugin/plugin.json | plugin manifest | 75/100 | Missing `version` field (BUG: breaks marketplace registration) |
| plugins/cartographer/skills/cartographer/SKILL.md | skill | 94/100 | Vague quantifiers: "significant", "notable", "non-obvious" (-6) |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 2 |

> **Note on pre-scan CRITICAL flag**: The pre-scan matched `curl -LsSf https://astral.sh/uv/install.sh | sh` in `scan-codebase.py`. After reading the file, this string appears inside a `print(..., file=sys.stderr)` statement at line 26 — advisory text the script emits when tiktoken is missing, not executed code. The CRITICAL classification is a false positive; the script never calls `subprocess`, `os.system`, or any shell. Reclassified as LOW (recommends insecure install pattern to users).

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Scripts (Python) | plugins/cartographer/skills/cartographer/scripts/scan-codebase.py |
| Package manifest | package.json |
| Hooks | none |
| MCP configs | none |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | LOW (FP at CRITICAL) | plugins/cartographer/skills/cartographer/scripts/scan-codebase.py | 26 | curl-pipe-sh | `curl \| sh` string in a `print(..., file=sys.stderr)` advisory; not executed by script — false positive at CRITICAL; recommends insecure install pattern to users |
| 2 | MEDIUM | plugins/cartographer/skills/cartographer/SKILL.md | 53 | unpinned-runtime-install | `pip install tiktoken` with no version constraint; agent may install a future breaking or malicious version |
| 3 | LOW | plugins/cartographer/skills/cartographer/scripts/scan-codebase.py | 4 | unpinned-dependency | Inline UV script dependency `tiktoken` has no version pin; arbitrary future versions allowed at runtime |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | plugins/cartographer/.claude-plugin/plugin.json | Missing `version` field | Plugin cannot be published to or resolved by the Claude Code marketplace; versioned installs (`nlpm@0.x`) break without this field |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | plugins/cartographer/skills/cartographer/SKILL.md | `pip install tiktoken` without version pin (lines 53, 291) | Replace with `pip install 'tiktoken>=0.7,<1.0'` to prevent supply-chain drift |
| 2 | plugins/cartographer/skills/cartographer/scripts/scan-codebase.py | Inline UV dependency `tiktoken` unpinned (line 4) | Change to `"tiktoken>=0.7,<1.0"` in the `# dependencies = [...]` inline spec |
| 3 | plugins/cartographer/skills/cartographer/scripts/scan-codebase.py | Error message recommends `curl \| sh` (line 26) | Replace with a versioned release download or `pip install tiktoken` (already shown on the next lines) |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | plugins/cartographer/skills/cartographer/SKILL.md | Vague quantifier "significant" in step 1 update check: "If significant changes detected" — threshold undefined | -2 |
| 2 | plugins/cartographer/skills/cartographer/SKILL.md | Vague quantifier "notable" in subagent prompt template (line 109): "Notable dependencies" — scope undefined | -2 |
| 3 | plugins/cartographer/skills/cartographer/SKILL.md | Vague term "non-obvious" in subagent prompt template (line 115) and output template (line 229): subjective without definition | -2 |

## Cross-Component
- **Script reference resolves**: SKILL.md references `${CLAUDE_PLUGIN_ROOT}/skills/cartographer/scripts/scan-codebase.py`; the file exists at `plugins/cartographer/skills/cartographer/scripts/scan-codebase.py` ✓
- **plugin.json does not advertise skills or commands**: The manifest has only `name`, `description`, and `author`. No `skills` or `commands` array. Claude Code plugins that use directory-based discovery may omit these, but the underspecified manifest is the same root cause as the missing `version` bug (manifest not following full schema).
- **package.json is unrelated to the plugin surface**: It describes a standalone TypeScript CLI/library (`@kingbootoshi/cartographer`) with pinned dependencies. No postinstall scripts. Not a security concern.
- **No orphaned components or broken cross-references detected.**

## Recommendation
REVIEW — submit NL fix PRs, flag security findings in issue.

Submit one PR for the `version` field bug in `plugin.json`. Pair it with version-pinning fixes for the two unpinned `tiktoken` references (SKILL.md lines 53/291 and scan-codebase.py line 4) — these are low-risk, high-clarity changes that will merge cleanly. The `curl | sh` advisory text in the error message is worth a comment in the PR noting the recommended alternative (`pip install tiktoken` already appears two lines later), but the risk is low enough that it need not block the PR. No critical or high findings; private security disclosure is not required.
