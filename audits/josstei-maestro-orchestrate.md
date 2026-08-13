# NLPM Audit: josstei/maestro-orchestrate
**Date**: 2026-04-30  |  **Artifacts**: 296  |  **Strategy**: progressive
**NL Score**: 87/100
**Security**: BLOCKED
**Bugs**: 0  |  **Quality Issues**: 15  |  **Security Findings**: 8

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| claude/agents/analytics-engineer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/cloud-architect.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/cobol-engineer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/coder.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/content-strategist.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/data-engineer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/database-administrator.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/db2-dba.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/debugger.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/design-system-engineer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/devops-engineer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/i18n-specialist.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/ibm-i-specialist.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/mobile-engineer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/observability-engineer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/product-manager.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/prompt-engineer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/refactor.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/seo-specialist.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/site-reliability-engineer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/solutions-architect.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/technical-writer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/ux-designer.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/zos-sysprog.md | agent | 75 | No body examples (in YAML only), no output format |
| claude/agents/hlasm-assembler-specialist.md | agent | 75 | No body examples (in YAML only), no output format |
| src/agents/design-system-engineer.md | agent | 79 | "appropriate" ×4 in commentary and body (-10 vague) |
| claude/src/agents/tester.md | agent | 83 | No output format (-10), "comprehensive" (-2) |
| claude/src/agents/coder.md | agent | 85 | "appropriate" ×2, "proper" ×2, "necessary" (-10 vague) |
| claude/src/agents/data-engineer.md | agent | 85 | "appropriate" ×2, "proper", "ensure", "necessary" (-10 vague) |
| claude/src/agents/ml-engineer.md | agent | 85 | No output format specification (-10) |
| claude/src/agents/mlops-engineer.md | agent | 85 | No output format specification (-10) |
| claude/src/agents/platform-engineer.md | agent | 85 | No output format specification (-10) |
| plugins/maestro/src/agents/tester.md | agent | 85 | "appropriate", "comprehensive" ×2, "proper", "relevant" (-10 vague) |
| claude/src/agents/db2-dba.md | agent | 87 | "appropriate" ×2, "proper", "necessary" (-8 vague) |
| claude/src/agents/ibm-i-specialist.md | agent | 87 | "appropriate" ×2, "proper", "necessary" (-8 vague) |
| claude/src/agents/refactor.md | agent | 87 | "appropriate", "proper" ×2, "necessary" (-8 vague) |
| claude/src/agents/ux-designer.md | agent | 87 | "appropriate" ×2, "efficient", "necessary" (-8 vague) |
| claude/src/agents/cobol-engineer.md | agent | 89 | "appropriate", "proper", "necessary" (-6 vague) |
| claude/src/agents/design-system-engineer.md | agent | 89 | "proper", "appropriate", "necessary" (-6 vague) |
| claude/src/agents/devops-engineer.md | agent | 89 | "appropriate", "proper", "necessary" (-6 vague) |
| claude/src/agents/prompt-engineer.md | agent | 89 | "appropriate", "robust", "necessary" (-6 vague) |
| plugins/maestro/src/agents/data-engineer.md | agent | 89 | "appropriate", "proper", "ensure" (-6 vague) |
| plugins/maestro/src/agents/performance-engineer.md | agent | 89 | "appropriate" ×3 in commentary and body (-6 vague) |
| plugins/maestro/src/agents/security-engineer.md | agent | 89 | "appropriate" ×2, "proper" (-6 vague) |
| src/agents/coder.md | agent | 89 | "appropriate", "proper", "necessary" (-6 vague) |
| src/agents/debugger.md | agent | 89 | "appropriate" ×2, "necessary" (-6 vague) |
| src/agents/devops-engineer.md | agent | 89 | "appropriate", "proper", "necessary" (-6 vague) |
| src/agents/hlasm-assembler-specialist.md | agent | 89 | "appropriate" ×2, "necessary" (-6 vague) |
| src/agents/observability-engineer.md | agent | 89 | "appropriate" ×2, "necessary" (-6 vague) |
| src/agents/refactor.md | agent | 89 | "appropriate" ×2, "necessary" (-6 vague) |
| src/agents/site-reliability-engineer.md | agent | 89 | "appropriate" ×2, "necessary" (-6 vague) |
| claude/src/agents/analytics-engineer.md | agent | 91 | "proper", "necessary" (-4 vague) |
| claude/src/agents/cloud-architect.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/content-strategist.md | agent | 91 | "comprehensive", "necessary" (-4 vague) |
| claude/src/agents/database-administrator.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/debugger.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/hlasm-assembler-specialist.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/i18n-specialist.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/integration-engineer.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/mobile-engineer.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/observability-engineer.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/seo-specialist.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/site-reliability-engineer.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/solutions-architect.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/technical-writer.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/zos-sysprog.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| src/agents/cobol-engineer.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| src/agents/db2-dba.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| src/agents/solutions-architect.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| src/agents/technical-writer.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| src/agents/ux-designer.md | agent | 91 | "appropriate", "necessary" (-4 vague) |
| claude/src/agents/compliance-reviewer.md | agent | 93 | "necessary" ×1 (-2 vague) |
| claude/src/agents/copywriter.md | agent | 93 | "necessary" ×1 (-2 vague) |
| claude/src/agents/product-manager.md | agent | 93 | "necessary" ×1 (-2 vague) |
| plugins/maestro/src/agents/accessibility-specialist.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/api-designer.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/architect.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/code-reviewer.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/compliance-reviewer.md | agent | 93 | "necessary" ×1 (-2 vague) |
| plugins/maestro/src/agents/database-administrator.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/i18n-specialist.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/integration-engineer.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/ml-engineer.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/mlops-engineer.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/mobile-engineer.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/platform-engineer.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/release-manager.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/seo-specialist.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| plugins/maestro/src/agents/zos-sysprog.md | agent | 93 | "appropriate" ×1 (-2 vague) |
| src/agents/analytics-engineer.md | agent | 93 | "necessary" ×1 in Output Contract (-2 vague) |
| src/agents/content-strategist.md | agent | 93 | "necessary" ×1 in Output Contract (-2 vague) |
| claude/src/agents/accessibility-specialist.md | agent | 95 | No model declared (-5 only) |
| claude/src/agents/api-designer.md | agent | 95 | No model declared (-5 only) |
| claude/src/agents/architect.md | agent | 95 | No model declared (-5 only) |
| claude/src/agents/code-reviewer.md | agent | 95 | No model declared (-5 only) |
| claude/src/agents/performance-engineer.md | agent | 95 | No model declared (-5 only) |
| claude/src/agents/release-manager.md | agent | 95 | No model declared (-5 only) |
| claude/src/agents/security-engineer.md | agent | 95 | No model declared (-5 only) |
| plugins/maestro/src/agents/copywriter.md | agent | 95 | No model declared (-5 only) |
| plugins/maestro/src/agents/product-manager.md | agent | 95 | No model declared (-5 only) |

**Score distribution:** 25 files @ 75 · 1 @ 79 · 1 @ 83 · 6 @ 85 · 4 @ 87 · 14 @ 89 · 20 @ 91 · 20 @ 93 · 9 @ 95
**Weighted average:** 8676 / 100 = 86.76 → **87/100**

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
| Hooks | hooks/hooks.json, hooks/hook-runner.js, hooks/adapters/qwen-adapter.js, hooks/adapters/gemini-adapter.js |
| Scripts | 5 files in scripts/: check-layer-boundaries.js, update-versions.js, install-git-hooks.js, install-codex-plugin.js, generate.js |
| MCP Configs | claude/.mcp.json |
| Package Manifests | package.json |

> **Note:** Pre-scan reported 339 script files. Detailed scan of `scripts/` found 5. Remaining count likely includes `node_modules/` or generated output directories not scanned for security patterns.

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | High | package.json | 25 | SEC-postinstall-script | `prepare` lifecycle script runs `node scripts/install-git-hooks.js` automatically on `npm install`, silently reconfiguring `git core.hooksPath` |
| 2 | High | scripts/install-codex-plugin.js | 10 | file-write-outside-repo | Writes plugin files to `~/.codex/plugins/maestro/` and modifies `~/.agents/plugins/marketplace.json` outside repo |
| 3 | High | scripts/install-git-hooks.js | 30 | subprocess-shell-exec | `execSync` runs git subprocesses automatically via `prepare` lifecycle hook on every `npm install` |
| 4 | Medium | scripts/install-git-hooks.js | 42 | git-config-mutation | Modifies `core.hooksPath` to `.githooks/`; if `.githooks/` is compromised, all future git operations execute attacker code |
| 5 | Medium | hooks/hooks.json | 8 | env-var-path-injection | Hook commands resolve binary path from `${extensionPath}` env var; attacker-controlled var redirects hook execution |
| 6 | Medium | claude/.mcp.json | 5 | env-var-path-injection | MCP server binary path and cwd resolved from `${CLAUDE_PLUGIN_ROOT}`; poisoned var redirects MCP server execution |
| 7 | Low | package.json | 34 | SEC-unpinned-semver | devDependency `c8` pinned with caret (`^10.1.3`) allows automatic minor/patch upgrades |
| 8 | Low | mcp/maestro-server.js | 3 | env-var-access | `MAESTRO_RUNTIME` env var selects platform adapter at runtime; untrusted input could load unexpected adapter |

## Bugs (PR-worthy)

No NL bugs found. All 100 scored agents have valid `name` and `description` frontmatter, no broken cross-references, and no Write/Edit tools declared on read-only agents.

## Security Fixes (PR-worthy, Medium/Low only)

> **Note:** High findings (#1–#3) require private disclosure, not public PRs. Medium/Low fixes below are ready for PRs once the High issues are resolved or risk-accepted.

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/install-git-hooks.js | `core.hooksPath` mutation runs without user consent | Gate with `if (process.env.SKIP_HOOKS) return;`; document that `npm install` modifies git config |
| 2 | hooks/hooks.json | `${extensionPath}` path resolved from env var without validation | Validate `MAESTRO_EXTENSION_PATH` is absolute and under a known prefix before hook registration |
| 3 | claude/.mcp.json | `${CLAUDE_PLUGIN_ROOT}` used for MCP binary path without validation | Add startup check: verify `CLAUDE_PLUGIN_ROOT` resolves to expected directory |
| 4 | package.json | `c8` devDependency uses caret range (`^10.1.3`) | Pin to exact version: `"c8": "10.1.3"` |
| 5 | mcp/maestro-server.js | `MAESTRO_RUNTIME` env var selects adapter without allowlist | Validate against known adapter names: `['qwen', 'gemini', 'default']` before loading |

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | src/agents/, plugins/maestro/src/agents/, claude/src/agents/ (75 files) | No `model` field in frontmatter | −5 each |
| 2 | claude/agents/ (25 files) | No output format specification in agent body (single-sentence stub) | −10 each |
| 3 | claude/agents/ (25 files) | Zero standalone `<example>` blocks in body; examples embedded in YAML description only | −15 each |
| 4 | src/agents/design-system-engineer.md | "appropriate" ×4 (2 commentary + 2 body) + "necessary" ×1 = 5 vague hits | −10 |
| 5 | plugins/maestro/src/agents/tester.md | "appropriate", "comprehensive" ×2, "proper", "relevant" = 5 vague hits | −10 |
| 6 | claude/src/agents/coder.md | "appropriate" ×2, "proper" ×2, "necessary" = 5 vague hits | −10 |
| 7 | claude/src/agents/data-engineer.md | "appropriate" ×2, "proper", "ensure", "necessary" = 5 vague hits | −10 |
| 8 | claude/src/agents/tester.md | No Output Format section (Testing Standards + Test Types present but no output spec) | −10 |
| 9 | claude/src/agents/ml-engineer.md | No Output Format section (body has Methodology, Work Areas, Constraints only) | −10 |
| 10 | claude/src/agents/platform-engineer.md | No Output Format section (body has Methodology, Work Areas, Constraints only) | −10 |
| 11 | claude/src/agents/mlops-engineer.md | No Output Format section (body has Methodology, Work Areas, Constraints only) | −10 |
| 12 | claude/src/agents/refactor.md | "appropriate", "proper" ×2, "necessary" = 4 vague hits | −8 |
| 13 | claude/src/agents/ux-designer.md | "appropriate" ×2, "efficient", "necessary" = 4 vague hits | −8 |
| 14 | claude/src/agents/db2-dba.md | "appropriate" ×2, "proper", "necessary" = 4 vague hits | −8 |
| 15 | claude/src/agents/ibm-i-specialist.md | "appropriate" ×2, "proper", "necessary" = 4 vague hits | −8 |

**Systemic patterns:**
- "appropriate" appears in `<commentary>` boilerplate ("X is appropriate for…") across ~70% of agents. These commentary blocks are selection hints and the word choice is formulaic, but it still counts toward the vague-word cap.
- "necessary" appears in the shared Output Contract template ("additional necessary work discovered") across all agents that use the template. Removing it from the template would eliminate the per-file −2 penalty for ~75 agents.

## Cross-Component

**Three parallel implementations with quality divergence.** The repo ships the same 15 core agent roles in three forms: `src/agents/` (original, scores ~89), `claude/src/agents/` (expanded set with additional agents, scores ~90), and `claude/agents/` (MCP-deferred stubs, scores uniformly 75). The stub pattern trades quality metrics for runtime flexibility but the score drop is significant (−14 points vs. the full-body variants).

**MCP runtime dependency in claude/agents/ stubs.** All 25 stub agents body-text reads: "Agent methodology loaded via MCP tool `get_agent`." The MCP server is configured in `claude/.mcp.json` with `${CLAUDE_PLUGIN_ROOT}` as the binary path. If `CLAUDE_PLUGIN_ROOT` is unset or the MCP server is unavailable, all 25 agents operate as empty shells. No graceful degradation or fallback is documented.

No broken cross-references detected within individual agent files. Tool declarations are consistent with capability declarations across all scanned agents.

## Recommendation

**BLOCKED — do not submit PRs. File private security report.**

Three High-severity security findings (postinstall hook mutating `core.hooksPath`, out-of-repo file writes, and automatic shell subprocess execution via lifecycle hook) require private disclosure to the maintainer before any public PR activity. The NL quality score of 87/100 is strong, and zero NL bugs were found, so the repo is PR-ready on the NL side once the security gate clears.

After private disclosure and risk acceptance or remediation:
- The 5 Medium/Low security fixes are ready for PRs.
- No NL bug PRs needed (score above threshold, no missing frontmatter).
- Consider a separate issue suggesting the `claude/agents/` stubs add body-level output format and example blocks to close the 14-point quality gap with their full-body equivalents.
