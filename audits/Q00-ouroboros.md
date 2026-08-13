# NLPM Audit: Q00/ouroboros
**Date**: 2026-04-06  |  **Artifacts**: 58  |  **Strategy**: batched
**NL Score**: 69/100
**Security**: BLOCKED
**Bugs**: 45  |  **Quality Issues**: 64  |  **Security Findings**: 8

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| src/ouroboros/agents/research-agent.md | agent | 20 | Missing name+description frontmatter, no model, no examples, no output format |
| src/ouroboros/agents/ontologist.md | agent | 20 | Missing name+description frontmatter, no model, no examples, no output format |
| src/ouroboros/agents/analysis-agent.md | agent | 20 | Missing name+description frontmatter, no model, no examples, no output format |
| src/ouroboros/agents/breadth-keeper.md | agent | 20 | Missing name+description frontmatter, no model, no examples, no output format |
| src/ouroboros/agents/code-executor.md | agent | 20 | Missing name+description frontmatter, no model, no examples, no output format |
| src/ouroboros/agents/seed-closer.md | agent | 20 | Missing name+description frontmatter, no model, no examples, no output format |
| src/ouroboros/agents/semantic-evaluator.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/advocate.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/hacker.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/simplifier.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/codebase-explorer.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/contrarian.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/consensus-reviewer.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/socratic-interviewer.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/judge.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/architect.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/evaluator.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/qa-judge.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/ontology-analyst.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/seed-architect.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| src/ouroboros/agents/researcher.md | agent | 30 | Missing name+description frontmatter, no model, no examples |
| commands/evolve.md | command | 85 | No allowed-tools; takes {{ARGUMENTS}} without empty-input handling |
| commands/interview.md | command | 85 | No allowed-tools; takes {{ARGUMENTS}} without empty-input handling |
| commands/welcome.md | command | 85 | No allowed-tools; takes {{ARGUMENTS}} without empty-input handling |
| skills/setup/SKILL.md | skill | 90 | Stale counts (15 skills, 9 agents) in success message; curl-pipe-sh instruction |
| skills/pm/SKILL.md | skill | 90 | pbcopy in Step 4 is macOS-only; mixed-language output string (Korean) |
| skills/publish/SKILL.md | skill | 90 | "logical implementation units" vague grouping guidance in Step 6 |
| skills/evolve/SKILL.md | skill | 92 | Minor: MCP tool prefix docs may drift vs actual registered names |
| skills/brownfield/SKILL.md | skill | 92 | Minor quality |
| skills/update/SKILL.md | skill | 92 | Minor quality |
| skills/help/SKILL.md | skill | 92 | Minor quality |
| .claude-plugin/plugin.json | manifest | 92 | Minor: no version constraints on mcpServers |
| skills/tutorial/SKILL.md | skill | 93 | Minor quality |
| skills/ralph/SKILL.md | skill | 93 | Minor quality |
| commands/run.md | command | 95 | No allowed-tools declared |
| commands/tutorial.md | command | 95 | No allowed-tools declared |
| commands/evaluate.md | command | 95 | No allowed-tools declared |
| commands/cancel.md | command | 95 | No allowed-tools declared |
| commands/setup.md | command | 95 | No allowed-tools declared |
| commands/seed.md | command | 95 | No allowed-tools declared |
| commands/status.md | command | 95 | No allowed-tools declared |
| commands/unstuck.md | command | 95 | No allowed-tools declared |
| commands/ralph.md | command | 95 | No allowed-tools declared |
| commands/help.md | command | 95 | No allowed-tools declared |
| tests/fixtures/router/skills/frontmatter-body/run/SKILL.md | skill | 95 | Test fixture — intentional body mismatch |
| skills/welcome/SKILL.md | skill | 95 | Clean |
| skills/qa/SKILL.md | skill | 95 | Clean |
| skills/resume-session/SKILL.md | skill | 95 | Clean |
| skills/status/SKILL.md | skill | 95 | Clean |
| skills/run/SKILL.md | skill | 95 | Minor: frontmatter mcp_tool=ouroboros_execute_seed vs step 3 uses ouroboros_start_execute_seed |
| skills/unstuck/SKILL.md | skill | 95 | Clean |
| skills/seed/SKILL.md | skill | 95 | Clean |
| skills/cancel/SKILL.md | skill | 95 | Clean |
| skills/evaluate/SKILL.md | skill | 95 | Clean |
| skills/interview/SKILL.md | skill | 95 | Clean |
| skills/auto/SKILL.md | skill | 95 | Clean |
| CLAUDE.md | config | 88 | Dev-only file; includes stale agent list (omits wonder/reflect referenced elsewhere) |
| hooks/hooks.json | hook | 95 | Clean |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 1 |
| Medium | 4 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | hooks/hooks.json (3 hook entries: SessionStart, UserPromptSubmit, PostToolUse) |
| Scripts | scripts/drift-monitor.py, scripts/keyword-detector.py, scripts/session-start.py, scripts/version-check.py, scripts/sync-plugin-version.py, scripts/ralph.py, scripts/ralph-rewind.py, scripts/ralph.sh, scripts/mcp-serve.sh, scripts/install.sh |
| MCP configs | .mcp.json (repo-level), plugin.json references .mcp.json |
| Package manifest | pyproject.toml (no postinstall scripts found) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Critical | skills/setup/SKILL.md | 185 | curl-pipe-sh | Skill instructs Claude to present `curl -LsSf https://astral.sh/uv/install.sh \| sh` inside a Bash code block. Claude Code may execute this directly when the user chooses "set up now", piping an external shell script into sh without integrity verification. |
| 2 | Critical | scripts/install.sh | 3 | curl-pipe-bash | The script is designed to be invoked via `curl -fsSL https://raw.githubusercontent.com/Q00/ouroboros/main/scripts/install.sh \| bash` (documented in line 3 comment and confirmed by project README). Any compromise of the GitHub repository or CDN delivers arbitrary code to installing users. |
| 3 | High | scripts/install.sh | 118 | curl-pipe-sh (echo) | `echo "Or switch to uv (recommended): curl -LsSf https://astral.sh/uv/install.sh \| sh"` — script instructs users to pipe a second external script into sh, compounding supply-chain risk. |
| 4 | Medium | scripts/version-check.py | 74 | network-call | `urllib.request.urlopen('https://pypi.org/pypi/ouroboros-ai/json', ...)` — outbound HTTPS call to PyPI on every session start (via session-start.py). Benign intent but creates a mandatory external dependency in the hook path. |
| 5 | Medium | scripts/session-start.py | 27 | network-call | Dynamically loads and executes version-check.py on every SessionStart hook, triggering a PyPI network call; failure modes are silently swallowed. |
| 6 | Medium | skills/interview/SKILL.md | 33 | network-call | `curl -s --max-time 3 https://api.github.com/repos/Q00/ouroboros/releases/latest \| grep ...` — outbound curl to GitHub API (not piped to shell, but introduces a network dependency into every interview invocation). |
| 7 | Medium | .mcp.json | 4 | unpinned-dependency | `"--from", "ouroboros-ai[mcp,claude]"` — no version constraint. A future breaking release of ouroboros-ai will silently break existing installs. |
| 8 | Low | hooks/hooks.json | 9,18,29 | path-interpolation | Hook commands use `${CLAUDE_PLUGIN_ROOT}` without quoting in the JSON value; a CLAUDE_PLUGIN_ROOT containing spaces or special characters could alter script resolution. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | src/ouroboros/agents/research-agent.md | Missing `name` frontmatter field | Agent will not register; orchestrators cannot reference it by name |
| 2 | src/ouroboros/agents/research-agent.md | Missing `description` frontmatter field | Agent discovery and help text broken |
| 3 | src/ouroboros/agents/semantic-evaluator.md | Missing `name` frontmatter field | Agent not registerable |
| 4 | src/ouroboros/agents/semantic-evaluator.md | Missing `description` frontmatter field | Agent discovery broken |
| 5 | src/ouroboros/agents/advocate.md | Missing `name` frontmatter field | Agent not registerable |
| 6 | src/ouroboros/agents/advocate.md | Missing `description` frontmatter field | Agent discovery broken |
| 7 | src/ouroboros/agents/hacker.md | Missing `name` frontmatter field | Agent not registerable |
| 8 | src/ouroboros/agents/hacker.md | Missing `description` frontmatter field | Agent discovery broken |
| 9 | src/ouroboros/agents/simplifier.md | Missing `name` frontmatter field | Agent not registerable |
| 10 | src/ouroboros/agents/simplifier.md | Missing `description` frontmatter field | Agent discovery broken |
| 11 | src/ouroboros/agents/ontologist.md | Missing `name` frontmatter field | Agent not registerable |
| 12 | src/ouroboros/agents/ontologist.md | Missing `description` frontmatter field | Agent discovery broken |
| 13 | src/ouroboros/agents/codebase-explorer.md | Missing `name` frontmatter field | Agent not registerable |
| 14 | src/ouroboros/agents/codebase-explorer.md | Missing `description` frontmatter field | Agent discovery broken |
| 15 | src/ouroboros/agents/contrarian.md | Missing `name` frontmatter field | Agent not registerable |
| 16 | src/ouroboros/agents/contrarian.md | Missing `description` frontmatter field | Agent discovery broken |
| 17 | src/ouroboros/agents/consensus-reviewer.md | Missing `name` frontmatter field | Agent not registerable |
| 18 | src/ouroboros/agents/consensus-reviewer.md | Missing `description` frontmatter field | Agent discovery broken |
| 19 | src/ouroboros/agents/analysis-agent.md | Missing `name` frontmatter field | Agent not registerable |
| 20 | src/ouroboros/agents/analysis-agent.md | Missing `description` frontmatter field | Agent discovery broken |
| 21 | src/ouroboros/agents/breadth-keeper.md | Missing `name` frontmatter field | Agent not registerable |
| 22 | src/ouroboros/agents/breadth-keeper.md | Missing `description` frontmatter field | Agent discovery broken |
| 23 | src/ouroboros/agents/socratic-interviewer.md | Missing `name` frontmatter field | Agent not registerable; skills/interview/SKILL.md references it by name |
| 24 | src/ouroboros/agents/socratic-interviewer.md | Missing `description` frontmatter field | Agent discovery broken |
| 25 | src/ouroboros/agents/judge.md | Missing `name` frontmatter field | Agent not registerable |
| 26 | src/ouroboros/agents/judge.md | Missing `description` frontmatter field | Agent discovery broken |
| 27 | src/ouroboros/agents/architect.md | Missing `name` frontmatter field | Agent not registerable |
| 28 | src/ouroboros/agents/architect.md | Missing `description` frontmatter field | Agent discovery broken |
| 29 | src/ouroboros/agents/evaluator.md | Missing `name` frontmatter field | Agent not registerable; skills/evaluate/SKILL.md references it |
| 30 | src/ouroboros/agents/evaluator.md | Missing `description` frontmatter field | Agent discovery broken |
| 31 | src/ouroboros/agents/qa-judge.md | Missing `name` frontmatter field | Agent not registerable; skills/qa/SKILL.md references it |
| 32 | src/ouroboros/agents/qa-judge.md | Missing `description` frontmatter field | Agent discovery broken |
| 33 | src/ouroboros/agents/ontology-analyst.md | Missing `name` frontmatter field | Agent not registerable |
| 34 | src/ouroboros/agents/ontology-analyst.md | Missing `description` frontmatter field | Agent discovery broken |
| 35 | src/ouroboros/agents/code-executor.md | Missing `name` frontmatter field | Agent not registerable |
| 36 | src/ouroboros/agents/code-executor.md | Missing `description` frontmatter field | Agent discovery broken |
| 37 | src/ouroboros/agents/seed-architect.md | Missing `name` frontmatter field | Agent not registerable; skills/seed/SKILL.md references it |
| 38 | src/ouroboros/agents/seed-architect.md | Missing `description` frontmatter field | Agent discovery broken |
| 39 | src/ouroboros/agents/researcher.md | Missing `name` frontmatter field | Agent not registerable |
| 40 | src/ouroboros/agents/researcher.md | Missing `description` frontmatter field | Agent discovery broken |
| 41 | src/ouroboros/agents/seed-closer.md | Missing `name` frontmatter field | Agent not registerable; skills/interview/SKILL.md references it |
| 42 | src/ouroboros/agents/seed-closer.md | Missing `description` frontmatter field | Agent discovery broken |
| 43 | skills/setup/SKILL.md | CLAUDE.md preview block references `wonder` and `reflect` agents that have no corresponding files in src/ouroboros/agents/ | If users copy the preview block, the agent references resolve to nothing |
| 44 | skills/run/SKILL.md | Frontmatter declares `mcp_tool: ouroboros_execute_seed` but Step 3 instructs calling `ouroboros_start_execute_seed` | Name mismatch — one will fail depending on which the router uses |
| 45 | skills/pm/SKILL.md | Step 4 uses `pbcopy` which is macOS-only; no cross-platform fallback | Skill silently fails on Linux/Windows users |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/version-check.py | Outbound PyPI call on every session start adds latency and a network dependency to the hook path | Move the version check to a background thread or increase cache TTL; consider making it opt-in via a prefs flag |
| 2 | skills/interview/SKILL.md | curl to GitHub API on every interview invocation for a version check | Move this check to session-start.py where caching is already implemented; remove from interview skill |
| 3 | .mcp.json | `ouroboros-ai[mcp,claude]` unpinned | Pin to a minimum version range: `"ouroboros-ai[mcp,claude]>=0.36.0,<1.0.0"` |
| 4 | hooks/hooks.json | `${CLAUDE_PLUGIN_ROOT}` unquoted in command string | Wrap the path in double-quotes: `"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/...\""`  — already partially done, verify all three hook entries |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | src/ouroboros/agents/* (all 21) | No `model` declared; runtime uses default | -5 each |
| 2 | src/ouroboros/agents/* (all 21) | No example blocks; zero invocation examples | -15 each |
| 3 | src/ouroboros/agents/research-agent.md | No output format defined | -10 |
| 4 | src/ouroboros/agents/ontologist.md | No output format defined | -10 |
| 5 | src/ouroboros/agents/analysis-agent.md | No output format defined | -10 |
| 6 | src/ouroboros/agents/breadth-keeper.md | No output format defined; only lists questions | -10 |
| 7 | src/ouroboros/agents/code-executor.md | No output format defined | -10 |
| 8 | src/ouroboros/agents/seed-closer.md | No output format defined | -10 |
| 9 | commands/* (all 13) | No `allowed-tools` field in frontmatter | -5 each |
| 10 | commands/evolve.md | Takes {{ARGUMENTS}} without empty-input handling | -10 |
| 11 | commands/interview.md | Takes {{ARGUMENTS}} without empty-input handling | -10 |
| 12 | commands/welcome.md | Takes {{ARGUMENTS}} without empty-input handling | -10 |
| 13 | skills/setup/SKILL.md | Success message says "Skills Registered: 15 workflow skills" but 20+ skills exist | stale count |
| 14 | skills/setup/SKILL.md | Step 4 verification comment says "Should show 12+ skills"; actual count is 21 | stale count |
| 15 | skills/setup/SKILL.md | Success message says "Agents Available: 9 specialized agents"; actual bundled count is 21 | stale count |
| 16 | skills/pm/SKILL.md | Korean string `(Clipboard에 복사되었습니다)` in English-facing output; inconsistent locale | cosmetic |
| 17 | skills/publish/SKILL.md | "logical implementation units" grouping in Step 6 is vague; no grouping heuristics given | -2 |
| 18 | skills/run/SKILL.md | `view: "summary"` / `view: "compact"` / `view: "full"` naming inconsistency — step 6 uses all three without defining which is default for ouroboros_job_wait | cosmetic |

## Cross-Component
**Broken references:**
- `skills/setup/SKILL.md` CLAUDE.md preview block lists `wonder` and `reflect` as core agents (agents directory contains neither). These appear to be internal MCP Python module roles, not standalone agent markdown files. Every copy of the setup block propagates the stale reference.
- `skills/interview/SKILL.md` cites `src/ouroboros/agents/seed-closer.md` as the closure readiness source of truth. The file exists and is well-formed, but lacks the required `name`/`description` frontmatter, so a plugin router that validates frontmatter before loading would reject it.

**Stale counts:**
- `skills/setup/SKILL.md` reports 15 skills and 9 agents in its completion message; actual counts are 21 skills and 21 agents.
- `skills/help/SKILL.md` agent table lists 9 agents; 21 are present.

**MCP tool name drift:**
- `skills/run/SKILL.md` frontmatter: `mcp_tool: ouroboros_execute_seed`; body Step 3: `ouroboros_start_execute_seed`. These are different tool names — the router and the skill body are inconsistent.

**Consistency wins:**
- All skills that reference agents load them from `src/ouroboros/agents/<name>.md`, matching `CLAUDE.md` dev-mode instructions. ✓
- `.mcp.json` exists and is well-formed; `plugin.json` correctly points to it. ✓
- All command files delegate to matching `skills/<name>/SKILL.md`; all skill files exist. ✓

## Recommendation

**BLOCKED — do not submit PRs. File private security report.**

The `curl -LsSf https://astral.sh/uv/install.sh | sh` instruction in `skills/setup/SKILL.md` will be directly executed by Claude Code when a user chooses to set up the MCP backend. The `install.sh` curl-pipe-bash design exposes all installers to supply-chain compromise. Both findings must be addressed (e.g., move uv install to a documented out-of-band step, add checksum verification, and add a subresource integrity check) before any PR activity.

Once the Critical and High findings are resolved, the large volume of NL bugs (missing agent frontmatter) are straightforward mechanical fixes that would benefit significantly from a single PR adding `name` and `description` to all 21 agent files. That fix alone would raise the NL score by ~15 points.
