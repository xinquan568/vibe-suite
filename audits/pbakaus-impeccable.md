# NLPM Audit: pbakaus/impeccable
**Date**: 2026-04-10  |  **Artifacts**: 3  |  **Strategy**: single
**NL Score**: 93/100
**Security**: REVIEW
**Bugs**: 0  |  **Quality Issues**: 3  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `.claude-plugin/plugin.json` | plugin-manifest | 100 | Clean |
| `.claude-plugin/marketplace.json` | marketplace-manifest | 100 | Clean |
| `CLAUDE.md` | claude-md | 80 | Stale reference to gitignored evals/AGENT.md (-10) |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 3 |
| Medium | 3 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | None found |
| Scripts | 8 (scripts/build.js, scripts/build-extension.js, scripts/build-sub-pages.js, scripts/lib/utils.js, scripts/lib/sub-pages-data.js, scripts/screenshot-antipatterns.js, scripts/generate-og-image.js, scripts/generate-promo-tile.js) |
| MCP configs | None found |
| Package manifests | package.json (bun.lock present) |
| Browser extension | 4 (extension/background/service-worker.js, extension/content/content-script.js, extension/devtools/panel.js, extension/devtools/sidebar.js) |
| Server | 2 (server/index.js, server/lib/api-handlers.js) |
| CLI | 2 (bin/cli.js, bin/commands/skills.mjs) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | High | scripts/build.js | 122 | new Function(dynamic-string) | Regex-extracts ANTIPATTERNS array from source, evaluates via new Function(). Runs during bun run build. |
| 2 | High | scripts/build-extension.js | 63 | new Function(dynamic-string) | Same pattern as #1. Runs during extension build. |
| 3 | High | scripts/lib/sub-pages-data.js | 107 | new Function(dynamic-string) | Same pattern as #1. Runs at dev-server boot (bun run dev) and during build. |
| 4 | Medium | extension/devtools/panel.js | 504 | eval with incomplete escaping | chrome.devtools.inspectedWindow.eval() with manual replace() escaping that only handles backslash and single-quote. Selector injection possible via crafted page. |
| 5 | Medium | bin/commands/skills.mjs | 450 | execSync with shell interpolation | Shell-interpolates tmpdir-derived paths into unzip command. Low risk (not user-controlled) but avoidable. |
| 6 | Medium | package.json | 59-69 | Unpinned semver ranges | Caret ranges on jsdom, marked, puppeteer, playwright, wrangler. **FALSE POSITIVE**: bun.lock exists and pins versions. |
| 7 | Low | scripts/generate-og-image.js | 66-228 | page.setContent with interpolation | Template string interpolation in page.setContent(). Values sourced from local filesystem, not user input. |
| 8 | Low | server/index.js | 195 | Substring path traversal guard | url.pathname.includes('..') instead of path.resolve() + prefix assertion. Dev server only; Bun normalizes URL and file().size guards missing paths. |

## Bugs (PR-worthy)
No bugs found in NL artifacts. All manifests have required fields, valid semver, and correct structure.

## Security Fixes (PR-worthy)
| # | File | Issue | PR |
|---|------|-------|----|
| 1 | scripts/build.js, scripts/build-extension.js, scripts/lib/sub-pages-data.js | new Function() eval replaceable with direct ESM import (ANTIPATTERNS already exported) | pbakaus/impeccable#92 |
| 2 | extension/devtools/panel.js | Manual selector escaping replaceable with JSON.stringify() | pbakaus/impeccable#93 |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | CLAUDE.md | References evals/AGENT.md at lines 101, 138, but evals/ is gitignored and absent from working tree | -10 |
| 2 | CLAUDE.md | No prerequisites section listing required tool versions (bun, node >= 18) | -5 |
| 3 | CLAUDE.md | 42-line Evals Framework section describes inaccessible private gitignored framework | -5 |

## Cross-Component
- **Stale command count**: plugin.json, marketplace.json, and AGENTS.md say "18 commands" but 21 non-deprecated user-invocable skills exist. The build system's generateCounts() validator should catch this.
- **Broken relative paths**: arrange/SKILL.md and typeset/SKILL.md reference relative paths (reference/spatial-design.md, reference/typography.md) that resolve to nonexistent locations. Actual files live under impeccable/reference/.
- **Agent path phantom**: .claude/agents/anti-patterns.md references source/skills/impeccable/SKILL.md (5 times). The source/ tree is authoring-only, not present in installed plugin.
- **Deprecated skill signals**: teach-impeccable and frontend-design have user-invocable: true but body refuses to execute and redirects.
- **Undocumented .agents/skills/ tree**: 23-file mirror of .claude/skills/ with no documented consumer. Build output for VS Code Copilot/Antigravity per PROVIDERS config.
- **Terminology drift**: "commands" vs "skills" across manifests and docs; "Color & Theme" vs "Color & Contrast" between skill heading and agent canonical name; hardcoded "25 patterns" count in critique/SKILL.md.

## Recommendation
REVIEW -- 2 PRs submitted for the 3 High and 1 Medium security findings. Summary issue filed as pbakaus/impeccable#94 documenting all 12 findings. The execSync shell interpolation (Medium) is low-risk (tmpdir paths) and not worth a separate PR. The unpinned semver finding is a false positive (lockfile exists). Do not auto-contribute for consistency/quality issues -- these are informational for the maintainer.
