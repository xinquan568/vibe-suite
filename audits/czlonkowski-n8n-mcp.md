# NLPM Audit: czlonkowski/n8n-mcp
**Date**: 2026-04-06  |  **Artifacts**: 9  |  **Strategy**: single
**NL Score**: 81/100
**Security**: BLOCKED
**Bugs**: 4  |  **Quality Issues**: 15  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude/agents/mcp-backend-engineer.md | agent | 65 | Missing model (-5), missing output format (-10), vague quantifiers capped (-20) |
| .claude/agents/context-manager.md | agent | 75 | Missing model (-5), vague quantifiers capped (-20) |
| .claude/agents/deployment-engineer.md | agent | 75 | Missing model (-5), vague quantifiers capped (-20) |
| .claude/agents/technical-researcher.md | agent | 75 | Missing model (-5), vague quantifiers capped (-20) |
| .claude/agents/test-automator.md | agent | 75 | Missing model (-5), vague quantifiers capped (-20) |
| .claude/agents/debugger.md | agent | 91 | Missing model (-5), minor vague terms (-4) |
| .claude/agents/n8n-mcp-tester.md | agent | 91 | Undeclared tool names in body (-5), minor vague terms (-4) |
| CLAUDE.md | project-doc | 92 | Minor vague terms (-8) |
| .claude/agents/code-reviewer.md | agent | 94 | Minor vague terms (-6) |

**Weighted average**: (65+75+75+75+75+91+91+92+94) / 9 = **81/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 1 |
| Medium | 1 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts (.sh) | scripts/test-http.sh, scripts/test-single-session.sh, scripts/deploy-http.sh, scripts/publish-npm.sh, scripts/test-docker-config.sh, scripts/extract-nodes-docker.sh, scripts/test-docker-optimization.sh, scripts/demo-optimization.sh, scripts/test-docker.sh, scripts/test-optimized-docker.sh, scripts/build-optimized.sh, scripts/deploy-to-vm.sh, scripts/analyze-optimization.sh, scripts/extract-nodes-simple.sh, scripts/update-and-publish-prep.sh, scripts/test-n8n-integration.sh, monitor_fetch.sh, test-reinit-fix.sh (~18 .sh files) |
| Scripts (.js) | scripts/generate-initial-release-notes.js, scripts/generate-release-notes.js, scripts/extract-changelog.js, scripts/generate-detailed-reports.js, scripts/update-readme-version.js, scripts/prepare-release.js, scripts/test-release-automation.js, scripts/extract-from-docker.js, scripts/test-node-info.js, scripts/update-n8n-deps.js, scripts/test-expression-format-validation.js, scripts/sync-runtime-version.js, scripts/test-error-validation.js, scripts/http-bridge.js, scripts/mcp-http-client.js, scripts/generate-test-summary.js (~16+ .js files) |
| MCP configs | 0 (.mcp.json not found) |
| Package manifests | package.json |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | CRITICAL | scripts/test-http.sh | 51 | eval-with-variable | `eval "$cmd"` executes a dynamically built curl command; `$cmd` incorporates `$1` (user-supplied server URL) and `$4` (headers) without sanitization, enabling shell injection via script argument |
| 2 | HIGH | scripts/test-n8n-integration.sh | 89 | sudo-usage | `sudo apt-get install`, `sudo gpg --dearmor`, `sudo tee`, `sudo usermod` used in Docker auto-installer; elevated privilege execution triggered by running the script on an unprovisioned host |
| 3 | MEDIUM | scripts/deploy-to-vm.sh | 30 | source-external-file | `source .env` loads an arbitrary file from the working directory before using its values; a maliciously crafted `.env` could inject shell commands executed with the deployer's privileges |
| 4 | LOW | package.json | 104 | postinstall-script | `"prepare": "husky"` runs automatically on `npm install`; any attacker controlling this package could execute code at install time |
| 5 | LOW | package.json | — | unpinned-semver | Multiple devDependencies use `^` ranges (e.g. `"express": "^5.1.0"`, `"nodemon": "^3.1.14"`) allowing unintended version upgrades on fresh installs |

> **Note on pre-scan false positive**: The pre-scan flagged `scripts/test-code-node-enhancements.ts:78` as a second CRITICAL eval match. That line is a JavaScript *string literal* (`jsCode: 'const result = eval(item.json.code);...'`) representing test payload for the n8n Code node — it is data, not an executed eval call. Confirmed false positive.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude/agents/n8n-mcp-tester.md | Body references `get_node_info` (line 33) but this tool is not in the declared `tools` frontmatter; closest declared tool is `mcp__n8n-mcp-testing__get_node` | LLM following body instructions will call a non-existent tool name and receive an error |
| 2 | .claude/agents/n8n-mcp-tester.md | Body references `get_node_essentials` (line 34) but not in declared tools | Same as above — tool call will fail at runtime |
| 3 | .claude/agents/n8n-mcp-tester.md | Body references `validate_node_config` (lines 35, 67, 68) but not in declared tools; declared tools have `mcp__n8n-mcp-testing__validate_node` and `mcp__n8n-mcp-testing__validate_workflow` | Tool call will fail; agent cannot complete its stated test steps |
| 4 | .claude/agents/n8n-mcp-tester.md | Body references `get_node_example` (line 37) but not in declared tools | Tool call will fail; agent cannot retrieve node examples as documented |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/deploy-to-vm.sh | `source .env` at line 30 executes arbitrary file content | Validate the `.env` file exists and contains only `KEY=value` lines before sourcing; alternatively use `set -a; . .env; set +a` with a `grep -qvP '^[A-Z_]+=.*$'` pre-check |
| 2 | package.json | `"prepare": "husky"` runs on install in published packages | Move to `postinstall` guarded by `INIT_CWD` check: `node -e "if (process.env.INIT_CWD !== process.cwd()) process.exit(0)" && husky` |
| 3 | package.json | Unpinned `^` ranges in devDependencies for build tooling | Pin exact versions for devDependencies used in CI builds (`nodemon`, `ts-node`, `typescript`) to prevent silent upgrades breaking the build |

> **Critical/High findings (eval-with-variable, sudo-usage) require private disclosure — do NOT submit public PRs.**

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .claude/agents/mcp-backend-engineer.md | No `model` field declared; task involves reasoning-level MCP analysis and code generation — haiku fallback would produce weak results (R10) | -5 |
| 2 | .claude/agents/mcp-backend-engineer.md | No output format defined in body; agent has no response template, output structure will vary per invocation (R12) | -10 |
| 3 | .claude/agents/mcp-backend-engineer.md | Vague quantifiers throughout: "comprehensive knowledge" (line 8), "proper TypeScript types" (line 24), "appropriate comments" (line 25), "proper error handling" (line 27), "clean, maintainable" (line 27), "high reliability" (line 58) — 8+ instances (R01) | -20 (capped) |
| 4 | .claude/agents/context-manager.md | No `model` field declared; context management across large projects needs reliable reasoning — model tier unknown (R10) | -5 |
| 5 | .claude/agents/context-manager.md | Vague quantifiers: "relevant" appears 8 times (lines 24, 25, 50, 65, 71, 73, 87); "appropriate categorization" (line 42); "clear, concise language" (line 70) — 10 instances (R01) | -20 (capped) |
| 6 | .claude/agents/deployment-engineer.md | No `model` field declared; CI/CD and IaC generation requires sonnet-level reasoning (R10) | -5 |
| 7 | .claude/agents/deployment-engineer.md | Vague quantifiers: "proper" appears 7+ times, "appropriate" 3+ times, "comprehensive deployment strategies" (line 10), "relevant" — 12+ instances (R01) | -20 (capped) |
| 8 | .claude/agents/technical-researcher.md | No `model` field declared; multi-source synthesis research is a reasoning task (R10) | -5 |
| 9 | .claude/agents/technical-researcher.md | Vague quantifiers: "comprehensive" 5+ times, "appropriate" twice (lines 10, 44), "relevant" 3 times (lines 15, 27, 47), "diverse sources" (line 22) — 10+ instances (R01) | -20 (capped) |
| 10 | .claude/agents/test-automator.md | No `model` field declared; test suite design across frameworks is a reasoning task (R10) | -5 |
| 11 | .claude/agents/test-automator.md | Vague quantifiers: "appropriate" 6 times (lines 32, 38, 57, 62, 72, 87), "proper" 3 times, "comprehensive" 3 times, "reasonable execution time" (line 89) — 12+ instances (R01) | -20 (capped) |
| 12 | .claude/agents/debugger.md | No `model` field declared; root-cause analysis and fix generation is a reasoning task (R10) | -5 |
| 13 | .claude/agents/debugger.md | Minor vague quantifiers: "minimal side effects" (line 51), "broader impact" (line 51), "systematic" (line 36) — 2 instances clearly qualifying (R01) | -4 |
| 14 | .claude/agents/code-reviewer.md | Vague quantifiers: "Comprehensive Review" (line 15), "Adequate test coverage" (line 20), "relevant best practices" (line 32) — 3 instances (R01) | -6 |
| 15 | .claude/agents/n8n-mcp-tester.md | Step numbering error in "Example Test Execution": two consecutive items labeled "6." (lines 67–68); second should be "7." (R14) | -2 |

## Cross-Component
- **n8n-mcp-tester.md runtime dependency undocumented**: The agent requires an MCP server named `n8n-mcp-testing` (inferred from `mcp__n8n-mcp-testing__*` tool names) and an `mcp__supabase-telemetry__*` server, plus `mcp__plugin_postgres-best-practices_supabase__*`. None of these server configurations are documented in CLAUDE.md setup instructions. Users who configure the agent without these servers will get silent tool failures.
- **Supabase tools in n8n testing agent**: `mcp__supabase-telemetry__*` (21 tools) and `mcp__plugin_postgres-best-practices_supabase__authenticate` are declared in n8n-mcp-tester.md. The agent's stated purpose is testing n8n MCP server functionality; Supabase schema/branch management tools appear tangential. If these are genuinely needed for testing n8n Supabase workflow nodes, the rationale should be documented in the agent description.
- **CLAUDE.md attribution instruction**: Line 210 instructs all commits and PRs to include "Concieved by Romuald Członkowski" with a link to www.aiadvisors.pl/en. This is a behavioral instruction in a public OSS repo's CLAUDE.md — while not a structural bug, it embeds a marketing instruction in a file meant for technical guidance (R38: more instructive than descriptive).
- **No broken file references found**: All file paths mentioned in mcp-backend-engineer.md (`mcp/server.ts`, `mcp/tools.ts`, `mcp/tools-documentation.ts`, `mcp/index.ts`) are confirmed present in the CLAUDE.md architecture map. No orphaned references detected.

## Recommendation
BLOCKED — do not submit PRs. File private security report for the eval-with-variable finding in `scripts/test-http.sh` and the sudo chain in `scripts/test-n8n-integration.sh`. After the security issues are resolved, re-audit to confirm CLEAR status, then submit NL fix PRs for the four undeclared tool names in n8n-mcp-tester.md and the medium/low security fixes.
