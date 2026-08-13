# NLPM Audit: tinyhumansai/openhuman
**Date**: 2026-04-06  |  **Artifacts**: 39  |  **Strategy**: batched
**NL Score**: 63/100
**Security**: BLOCKED
**Bugs**: 2  |  **Quality Issues**: 30  |  **Security Findings**: 8

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| src/openhuman/agent/agents/tools_agent/prompt.md | agent-prompt | 16 | No frontmatter + no examples + no output format |
| src/openhuman/agent/agents/archivist/prompt.md | agent-prompt | 16 | No frontmatter + no examples + no output format |
| src/openhuman/agent/agents/tool_maker/prompt.md | agent-prompt | 18 | No frontmatter + no examples + no output format |
| src/openhuman/agent/agents/researcher/prompt.md | agent-prompt | 18 | No frontmatter + no examples + no output format |
| src/openhuman/agent/agents/critic/prompt.md | agent-prompt | 20 | No frontmatter + no examples + no output format |
| src/openhuman/agent/agents/code_executor/prompt.md | agent-prompt | 20 | No frontmatter + no examples + no output format |
| src/openhuman/agent/agents/morning_briefing/prompt.md | agent-prompt | 21 | No frontmatter + no examples + partial output format |
| src/openhuman/agent/agents/integrations_agent/prompt.md | agent-prompt | 25 | No frontmatter + no examples |
| src/openhuman/agent/agents/skill_creator/prompt.md | agent-prompt | 26 | No frontmatter + no examples |
| src/openhuman/agent/agents/planner/prompt.md | agent-prompt | 26 | No frontmatter + no examples + agent ID table gap |
| src/openhuman/agent/agents/trigger_reactor/prompt.md | agent-prompt | 28 | No frontmatter + no examples |
| src/openhuman/agent/agents/summarizer/prompt.md | agent-prompt | 30 | No frontmatter + no examples |
| src/openhuman/agent/agents/orchestrator/prompt.md | agent-prompt | 39 | No frontmatter + vague quantifiers |
| src/openhuman/agent/agents/crypto_agent/prompt.md | agent-prompt | 41 | No frontmatter + vague quantifiers |
| src/openhuman/agent/agents/help/prompt.md | agent-prompt | 43 | No frontmatter |
| src/openhuman/agent/agents/trigger_triage/prompt.md | agent-prompt | 43 | No frontmatter |
| src/openhuman/agent/agents/welcome/prompt.md | agent-prompt | 43 | No frontmatter |
| .agents/agents/ship-and-babysit.md | agent | 69 | No examples + no output format |
| .agents/agents/pr-manager-lite.md | agent | 81 | No examples |
| .claude/agents/pr-manager-lite.md | agent | 83 | No examples |
| .claude/agents/qualityqueen.md | agent | 86 | Excessive vague quantifiers (-14) |
| .claude/agents/memory-keeper.md | agent | 87 | Vague quantifiers + limited examples |
| .claude/agents/build-agent.md | agent | 90 | No explicit output format |
| .claude/agents/test-agent.md | agent | 90 | No explicit output format |
| .claude/agents/dev-agent.md | agent | 90 | No explicit output format |
| .claude/agents/deploy-agent.md | agent | 90 | No explicit output format |
| .claude/agents/mobile-agent.md | agent | 90 | No explicit output format |
| .claude/agents/pr-manager.md | agent | 91 | Limited interaction examples |
| .claude/agents/designguru.md | agent | 91 | Stale model pin + limited examples |
| .agents/agents/pr-manager.md | agent | 91 | Limited examples |
| .codex/commands/ship-and-babysit.md | command | 91 | Missing allowed-tools |
| .claude/agents/codecrusher.md | agent | 92 | Vague quantifiers |
| .claude/agents/taskmaster.md | agent | 94 | Vague quantifiers |
| .claude/agents/architectobot.md | agent | 96 | Minor vague quantifiers |
| .claude/agents/pr-reviewer.md | agent | 96 | Minor vague quantifiers |
| .codex/skills/ship-and-babysit/SKILL.md | skill | 96 | Minor vague quantifiers |
| .claude/commands/ship-and-babysit.md | command | 96 | Minor vague quantifiers |
| CLAUDE.md | docs | 90 | No frontmatter (standard for project docs) |
| .claude/commands/ws-reset.md | command | 100 | None |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 1 |
| Medium | 4 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Shell scripts | 113 (scripts/*.sh, e2e/*.sh, scripts/debug/*.sh, scripts/deep-work/*.sh, scripts/shortcuts/*.sh, scripts/cef-with-codecs/*.sh) |
| JS scripts | packages/npm/install.js, scripts/prepareTauriConfig.js, scripts/diagnose-cef-runtime.mjs, scripts/check-pr-checklist.mjs, scripts/mock-api-server.mjs, scripts/codex-pr-preflight.mjs, and more |
| Hooks | 0 (hooks/ directory not present) |
| MCP configs | 0 (.mcp.json not found) |
| Package manifests | package.json (root), app/package.json, packages/npm/package.json, remotion/package.json |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | CRITICAL | scripts/install.sh | 4,58 | SEC-curl-pipe-sh | Script is designed to be executed via `curl -fsSL URL \| bash` (documented as primary install method). No verification of script integrity before execution; only downloaded binary artifacts are SHA-256 checked after the fact. |
| 2 | HIGH | scripts/build-macos-signed.sh | 52–53 | SEC-new-function-eval | `eval "$(jq -r '...\"export \(.key)=\"\(.value)\"\"' ci-secrets.json)"` — JSON key names are not shell-escaped. A tampered ci-secrets.json with a key containing shell metacharacters (`;`, `$()`, backticks) would execute arbitrary code. Values lack `@sh` quoting too. |
| 3 | MEDIUM | scripts/test-ci-local.sh | 111–116 | SEC-new-function-eval | `eval "$(jq -r '...export \(.key)=\(.value \| @sh)' $SECRETS_JSON)"` — values are `@sh` escaped and keys are filtered to `VITE_*` prefix, but the jq pipeline and `eval` still introduce risk if SECRETS_JSON path is attacker-controlled. |
| 4 | MEDIUM | scripts/load-dotenv.sh | 50 | SEC-new-function-eval | `eval "$joined"` where values are `%q`-escaped but key names from the .env file are interpolated without sanitization. A key name containing shell special characters would be injectable. |
| 5 | MEDIUM | scripts/load-env-json.sh | 28 | SEC-new-function-eval | `eval "$exports"` — the `$FILTER` argument (line 11) is a user-supplied jq expression passed directly into the jq invocation, creating a filter-injection vector if the script is called with an untrusted second argument. |
| 6 | MEDIUM | packages/npm/package.json | 26 | SEC-postinstall-script | `"postinstall": "node install.js"` automatically runs on `npm install`. `install.js` fetches a platform-specific binary from GitHub Releases and executes it after SHA-256 verification. Legitimate pattern but executes network-fetched code at install time. |
| 7 | LOW | package.json | 22 | SEC-postinstall-script | `"postinstall": "husky"` — git hooks setup runs automatically. Husky is a well-known tool with a small attack surface, but any postinstall is an execution surface. |
| 8 | LOW | scripts/ensure-tauri-cli.sh | 21 | SEC-path-traversal | `export PATH="$HOME/.cargo/bin:$INSTALL_ROOT/bin:$PATH"` prepends to PATH using `$INSTALL_ROOT` which defaults to a user-controlled path. In CI contexts, a poisoned INSTALL_ROOT could shadow system binaries. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude/agents/designguru.md | Frontmatter `model: claude-3-5-sonnet-20241022` pins a specific legacy model ID. When Anthropic retires this ID, the agent will fail to load. Current agents on this repo use `model: sonnet` (the alias). | Agent becomes unregisterable when the pinned model ID is retired; silent breakage with no fallback. |
| 2 | src/openhuman/agent/agents/planner/prompt.md | Rule 0 (line 43) says the worker tier includes `archivist`, but the "Available Agent IDs" table lists only `code_executor`, `integrations_agent`, `tool_maker`, `researcher`, `critic`. `archivist` is absent from the table, so planners cannot legally route to it. | Planner agents cannot delegate to archivist even when appropriate; tasks requiring memory distillation will fail or be routed incorrectly. |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/build-macos-signed.sh | `eval` with unescaped key names from JSON (finding #2 above is HIGH — see private disclosure note) | N/A — HIGH severity requires private disclosure, not a public PR. |
| 2 | scripts/load-dotenv.sh | Key names from .env are not sanitized before `eval` | Validate key names against `^[A-Za-z_][A-Za-z0-9_]*$` before building the exports array; reject or skip invalid keys. |
| 3 | scripts/load-env-json.sh | The `$FILTER` jq argument accepts arbitrary jq code from the caller | Document that `$FILTER` is trusted caller input only; add a comment warning against passing external/untrusted input as the filter argument. |
| 4 | packages/npm/package.json | Postinstall fetches and installs a binary automatically | Add a `OPENHUMAN_SKIP_INSTALL` env-var guard so CI/audit environments can `npm install` without triggering the binary download. |
| 5 | scripts/ensure-tauri-cli.sh | `$INSTALL_ROOT` is used in PATH without validation | Resolve `INSTALL_ROOT` to a canonical absolute path and reject values containing `..` or that point outside expected directories. |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | src/openhuman/agent/agents/critic/prompt.md | Missing name, description, model frontmatter | -55 |
| 2 | src/openhuman/agent/agents/critic/prompt.md | No examples and no output format section | -25 |
| 3 | src/openhuman/agent/agents/crypto_agent/prompt.md | Missing name, description, model frontmatter | -55 |
| 4 | src/openhuman/agent/agents/crypto_agent/prompt.md | "sensible bound" used twice (vague quantifier) | -4 |
| 5 | src/openhuman/agent/agents/integrations_agent/prompt.md | Missing name, description, model frontmatter + no examples | -70 |
| 6 | src/openhuman/agent/agents/tool_maker/prompt.md | Missing name, description, model frontmatter + no examples + no output format | -77 |
| 7 | src/openhuman/agent/agents/help/prompt.md | Missing name, description, model frontmatter | -55 |
| 8 | src/openhuman/agent/agents/trigger_triage/prompt.md | Missing name, description, model frontmatter | -55 |
| 9 | src/openhuman/agent/agents/code_executor/prompt.md | Missing name, description, model frontmatter + no examples + no output format | -80 |
| 10 | src/openhuman/agent/agents/skill_creator/prompt.md | Missing name, description, model frontmatter + no examples | -70 |
| 11 | src/openhuman/agent/agents/morning_briefing/prompt.md | Missing name, description, model frontmatter + no examples + partial output format | -74 |
| 12 | src/openhuman/agent/agents/tools_agent/prompt.md | Missing name, description, model frontmatter + no examples + no output format + vague quantifiers | -84 |
| 13 | src/openhuman/agent/agents/archivist/prompt.md | Missing name, description, model frontmatter + no examples + no output format + vague quantifiers | -84 |
| 14 | src/openhuman/agent/agents/trigger_reactor/prompt.md | Missing name, description, model frontmatter + no examples | -72 |
| 15 | src/openhuman/agent/agents/orchestrator/prompt.md | Missing name, description, model frontmatter + vague quantifiers ("as few words as possible", "relevant context", "sensible") | -61 |
| 16 | src/openhuman/agent/agents/researcher/prompt.md | Missing name, description, model frontmatter + no examples + no output format | -77 |
| 17 | src/openhuman/agent/agents/summarizer/prompt.md | Missing name, description, model frontmatter + no examples | -70 |
| 18 | src/openhuman/agent/agents/planner/prompt.md | Missing name, description, model frontmatter + no examples + vague quantifiers ("complex user goal", "simple goals") | -74 |
| 19 | src/openhuman/agent/agents/welcome/prompt.md | Missing name, description, model frontmatter | -57 |
| 20 | .claude/agents/qualityqueen.md | Excessive vague quantifiers: "comprehensive" (×2), "proper" (×2), "relevant", "best practices" | -14 |
| 21 | .claude/agents/memory-keeper.md | Vague quantifiers ("important" ×2, "relevant", "significant") + single bare example | -13 |
| 22 | .claude/agents/pr-manager-lite.md | No interaction examples (only a workflow template) | -15 |
| 23 | .agents/agents/ship-and-babysit.md | No examples + no final output format for the agent's reply | -25 |
| 24 | .agents/agents/pr-manager-lite.md | No interaction examples | -15 |
| 25 | .claude/agents/build-agent.md | No explicit output format (agent delivers builds but expected response shape is unstated) | -10 |
| 26 | .claude/agents/test-agent.md | No explicit output format (reference doc style, no agent response template) | -10 |
| 27 | .claude/agents/dev-agent.md | No explicit output format | -10 |
| 28 | .claude/agents/deploy-agent.md | No explicit output format | -10 |
| 29 | .claude/agents/mobile-agent.md | No explicit output format | -10 |
| 30 | .codex/commands/ship-and-babysit.md | Missing `allowed-tools` frontmatter field | -5 |

## Cross-Component
**Duplicate artifact sprawl**: `ship-and-babysit` has four parallel definitions (`.claude/commands/`, `.agents/agents/`, `.codex/commands/`, `.codex/skills/`) with subtle divergences. The `.claude/commands/` version is the most complete (includes `ScheduleWakeup` 270s pacing, 12-tick cap, explicit fork-owner resolution); `.agents/agents/` version mostly matches but omits some detail; `.codex/skills/` version is a thin wrapper. If the core logic changes in one, the others will drift.

**pr-manager duplication**: Three `pr-manager` variants exist (`.claude/agents/pr-manager.md`, `.agents/agents/pr-manager.md`, `.claude/agents/pr-manager-lite.md`, `.agents/agents/pr-manager-lite.md`). The `.claude/agents/` and `.agents/agents/` versions of each are substantially identical — useful for multi-tool coverage, but any behavioural fix must be applied in both places.

**Planner ↔ archivist gap**: `planner/prompt.md` references `archivist` in the worker-tier rules (line 43) but omits it from the Available Agent IDs table. Any plan that tries to delegate to `archivist` will fail.

**Orchestrator tool naming**: `orchestrator/prompt.md` delegates crypto work via `delegate_do_crypto` while the specialized agent is named `crypto_agent`. The orchestrator likely uses a higher-level delegation tool, but the naming mismatch makes it hard to audit the delegation chain.

**Internal prompt files without frontmatter**: All 17 `src/openhuman/agent/agents/*/prompt.md` files are raw text prompt files consumed via `?raw` imports by the Tauri application — they are intentionally not Claude Code agents and do not need YAML frontmatter for their runtime role. Their low NLPM scores reflect the scoring rubric's frontmatter penalties, not production defects in the application. These files are well-written internally; the penalty is a rubric artifact.

## Recommendation
BLOCKED — do not submit PRs. The `scripts/install.sh` file is designed to be executed via `curl -fsSL URL | bash`, and `scripts/build-macos-signed.sh` uses `eval` with unescaped JSON key names that could enable shell injection if `scripts/ci-secrets.json` is tampered with. File private security reports for findings #1 and #2 before any public contribution.

Once the CRITICAL and HIGH findings are resolved:
- Submit a PR fixing the stale model pin in `.claude/agents/designguru.md` (Bug #1).
- Submit a PR adding `archivist` to the `planner/prompt.md` Available Agent IDs table (Bug #2).
- Submit a PR adding key-name validation to `scripts/load-dotenv.sh` (Security Fix #2).
- Submit a PR adding an `OPENHUMAN_SKIP_INSTALL` guard to `packages/npm/install.js` (Security Fix #4).
- The 17 internal `prompt.md` files score poorly due to missing Claude Code frontmatter, but this is a rubric artifact — they work correctly as raw application prompts. Adding frontmatter to these files is optional and low-priority.
