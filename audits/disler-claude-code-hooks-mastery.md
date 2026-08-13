# NLPM Audit: disler/claude-code-hooks-mastery
**Date**: 2026-04-06  |  **Artifacts**: 41  |  **Strategy**: batched
**NL Score**: 77/100
**Security**: REVIEW
**Bugs**: 13  |  **Quality Issues**: 35  |  **Security Findings**: 10

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| CLAUDE.md | config | 65 | Essentially empty — no project context |
| .claude/commands/agent_prompts/crypto_investment_plays_agent_prompt.md | command | 68 | No frontmatter; vague quantifiers |
| .claude/commands/agent_prompts/crypto_coin_analyzer_agent_prompt.md | command | 68 | No frontmatter; vague quantifiers |
| .claude/commands/cook.md | command | 70 | No frontmatter at all |
| .claude/commands/prime_tts.md | command | 70 | No frontmatter at all |
| .claude/commands/all_tools.md | command | 70 | No frontmatter at all |
| .claude/commands/update_status_line.md | command | 70 | No frontmatter at all |
| .claude/commands/agent_prompts/crypto_price_check_agent_prompt.md | command | 70 | No frontmatter |
| .claude/commands/agent_prompts/crypto_movers_agent_prompt.md | command | 70 | No frontmatter |
| .claude/commands/agent_prompts/crypto_market_agent_prompt.md | command | 70 | No frontmatter |
| .claude/commands/agent_prompts/crypto_news_scanner_agent_prompt.md | command | 70 | No frontmatter |
| .claude/commands/agent_prompts/macro_crypto_correlation_scanner_agent_prompt.md | command | 70 | No frontmatter |
| .claude/commands/cook_research_only.md | command | 70 | No frontmatter at all |
| .claude/agents/crypto/crypto-market-agent-opus.md | agent | 72 | No examples; no output format; Write likely unused |
| .claude/agents/crypto/crypto-coin-analyzer-opus.md | agent | 72 | No examples; no output format; Write likely unused |
| .claude/agents/crypto/crypto-market-agent-sonnet.md | agent | 72 | No examples; no output format; Write likely unused |
| .claude/agents/crypto/crypto-coin-analyzer-sonnet.md | agent | 72 | No examples; no output format; Write likely unused |
| .claude/agents/crypto/crypto-market-agent-haiku.md | agent | 72 | No examples; no output format; Write likely unused |
| .claude/agents/crypto/crypto-coin-analyzer-haiku.md | agent | 72 | No examples; no output format; Write likely unused |
| .claude/agents/crypto/crypto-investment-plays-haiku.md | agent | 75 | No examples; no output format in agent file |
| .claude/agents/crypto/macro-crypto-correlation-scanner-opus.md | agent | 75 | No examples; no output format in agent file |
| .claude/agents/crypto/macro-crypto-correlation-scanner-sonnet.md | agent | 75 | No examples; no output format in agent file |
| .claude/agents/crypto/crypto-investment-plays-sonnet.md | agent | 75 | No examples; no output format in agent file |
| .claude/agents/crypto/crypto-investment-plays-opus.md | agent | 75 | No examples; no output format in agent file |
| .claude/agents/crypto/macro-crypto-correlation-scanner-haiku.md | agent | 75 | No examples; no output format in agent file |
| .claude/agents/crypto/crypto-movers-haiku.md | agent | 75 | No examples; no output format in agent file |
| .claude/agents/llm-ai-agents-and-eng-research.md | agent | 75 | No model; no examples; WebSearch used but not declared |
| .claude/agents/work-completion-summary.md | agent | 80 | No model declared; no examples |
| .claude/agents/hello-world-agent.md | agent | 80 | No model declared; no examples |
| .claude/agents/meta-agent.md | agent | 83 | No examples; vague "relevant" |
| .claude/agents/team/validator.md | agent | 85 | No examples |
| .claude/agents/team/builder.md | agent | 85 | No examples |
| .claude/commands/plan.md | command | 85 | No allowed-tools; vague quantifiers |
| .claude/commands/plan_w_team.md | command | 85 | No explicit allowed-tools; vague quantifiers |
| .claude/commands/git_status.md | command | 90 | Missing explicit output format |
| .claude/commands/prime.md | command | 90 | Minimal output format spec |
| .claude/commands/sentient.md | command | 90 | Misleading description vs. actual rm -rf demo purpose |
| .claude/commands/build.md | command | 95 | No allowed-tools declared |
| .claude/commands/question.md | command | 96 | Minor vague terms |
| .claude/commands/crypto_research_haiku.md | command | 100 | Clean |
| .claude/commands/crypto_research.md | command | 100 | Clean |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 9 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Claude Code hooks (.py) | `.claude/hooks/pre_tool_use.py`, `.claude/hooks/post_tool_use.py`, `.claude/hooks/session_start.py`, `.claude/hooks/session_end.py`, `.claude/hooks/setup.py`, `.claude/hooks/stop.py`, `.claude/hooks/notification.py`, `.claude/hooks/pre_compact.py`, `.claude/hooks/user_prompt_submit.py`, `.claude/hooks/subagent_start.py`, `.claude/hooks/subagent_stop.py`, `.claude/hooks/permission_request.py`, `.claude/hooks/post_tool_use_failure.py` |
| Hook validators (.py) | `.claude/hooks/validators/ruff_validator.py`, `.claude/hooks/validators/ty_validator.py`, `.claude/hooks/validators/validate_file_contains.py`, `.claude/hooks/validators/validate_new_file.py` |
| LLM utilities (.py) | `.claude/hooks/utils/llm/anth.py`, `.claude/hooks/utils/llm/oai.py`, `.claude/hooks/utils/llm/ollama.py`, `.claude/hooks/utils/llm/task_summarizer.py` |
| TTS utilities (.py) | `.claude/hooks/utils/tts/openai_tts.py`, `.claude/hooks/utils/tts/elevenlabs_tts.py`, `.claude/hooks/utils/tts/pyttsx3_tts.py`, `.claude/hooks/utils/tts/tts_queue.py` |
| Package manifests | `apps/task-manager/package.json` |
| MCP configs | None |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | medium | .claude/commands/sentient.md | 17 | destructive-command-instructions | Command instructs Claude to run `rm -rf` 3 times; description says "Manage, organize and ships your codebase" obscuring true purpose; relies on pre_tool_use.py hook being active to block |
| 2 | medium | .claude/hooks/setup.py | 107 | runtime-package-install | `subprocess.run(['npm', 'ci'])` / `['npm', 'install']` executes npm package installation at session setup; malicious package.json in CWD would install attacker-controlled packages |
| 3 | medium | .claude/hooks/setup.py | 119 | runtime-package-install | `subprocess.run(['pip', 'install', '-r', 'requirements.txt'])` installs Python packages from requirements.txt at session setup without signature verification |
| 4 | medium | .claude/hooks/setup.py | 134 | runtime-package-install | `subprocess.run(['uv', 'sync'])` / `['pip', 'install', '-e', '.']` installs packages from pyproject.toml at session setup |
| 5 | medium | .claude/hooks/utils/llm/anth.py | 34 | network-call-with-env-key | Makes outbound Anthropic API call using `ANTHROPIC_API_KEY` from environment on every Stop hook invocation |
| 6 | medium | .claude/hooks/utils/llm/oai.py | 36 | network-call-with-env-key | Makes outbound OpenAI API call using `OPENAI_API_KEY` from environment on every Stop hook invocation |
| 7 | medium | .claude/hooks/utils/tts/openai_tts.py | 68 | network-call-with-env-key | Makes outbound OpenAI TTS streaming call using `OPENAI_API_KEY`; triggered on task completion |
| 8 | medium | .claude/hooks/utils/tts/elevenlabs_tts.py | 65 | network-call-with-env-key | Makes outbound ElevenLabs TTS call using `ELEVENLABS_API_KEY`; triggered on task completion |
| 9 | medium | .claude/hooks/session_start.py | 89 | ambient-credential-use | `gh issue list` called via subprocess using ambient GitHub CLI credentials at every session start |
| 10 | low | apps/task-manager/package.json | 10 | unpinned-semver | Dependencies use `^` semver ranges (`chalk: ^5.3.0`, `yargs: ^17.7.2`); minor/patch updates install automatically without review |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude/commands/cook.md | No frontmatter — missing `description` field | Command not discoverable; no help text in Claude Code UI |
| 2 | .claude/commands/prime_tts.md | No frontmatter — missing `description` and `allowed-tools` | Command not discoverable; no tool restrictions |
| 3 | .claude/commands/all_tools.md | No frontmatter — missing `description` and `allowed-tools` | Command not discoverable |
| 4 | .claude/commands/update_status_line.md | No frontmatter — missing `description` and `allowed-tools` | Command not discoverable; can use any tool without restriction |
| 5 | .claude/commands/cook_research_only.md | No frontmatter — missing `description` and `allowed-tools` | Command not discoverable |
| 6 | .claude/commands/agent_prompts/crypto_price_check_agent_prompt.md | No frontmatter — missing `description` | Registered as slash command but undiscoverable |
| 7 | .claude/commands/agent_prompts/crypto_movers_agent_prompt.md | No frontmatter — missing `description` | Registered as slash command but undiscoverable |
| 8 | .claude/commands/agent_prompts/crypto_market_agent_prompt.md | No frontmatter — missing `description` | Registered as slash command but undiscoverable |
| 9 | .claude/commands/agent_prompts/crypto_news_scanner_agent_prompt.md | No frontmatter — missing `description` | Registered as slash command but undiscoverable |
| 10 | .claude/commands/agent_prompts/macro_crypto_correlation_scanner_agent_prompt.md | No frontmatter — missing `description` | Registered as slash command but undiscoverable |
| 11 | .claude/commands/agent_prompts/crypto_investment_plays_agent_prompt.md | No frontmatter — missing `description` | Registered as slash command but undiscoverable |
| 12 | .claude/commands/agent_prompts/crypto_coin_analyzer_agent_prompt.md | No frontmatter — missing `description` | Registered as slash command but undiscoverable |
| 13 | .claude/agents/llm-ai-agents-and-eng-research.md | `WebSearch` called in step 2 instructions but not declared in `tools` | WebSearch calls will fail at runtime; agent breaks on first search attempt |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | .claude/commands/sentient.md | Misleading description masks rm -rf demo content | Change description to `Demo command: tests hook blocking of destructive rm -rf commands` or add `# WARNING: demo only` banner |
| 2 | .claude/hooks/setup.py | Runtime package install runs automatically on `--install-deps` flag at session setup | Gate behind explicit user confirmation or remove `--install-deps` from default settings.json invocation |
| 3 | apps/task-manager/package.json | Pinned semver ranges with `^` allow unreviewed minor/patch updates | Pin to exact versions (`"chalk": "5.3.0"`) or add `package-lock.json` to version control |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .claude/agents/llm-ai-agents-and-eng-research.md | No model declared | -5 |
| 2 | .claude/agents/work-completion-summary.md | No model declared | -5 |
| 3 | .claude/agents/hello-world-agent.md | No model declared | -5 |
| 4 | .claude/agents/llm-ai-agents-and-eng-research.md | No example invocations | -15 |
| 5 | .claude/agents/meta-agent.md | No example invocations | -15 |
| 6 | .claude/agents/work-completion-summary.md | No example invocations | -15 |
| 7 | .claude/agents/hello-world-agent.md | No example invocations | -15 |
| 8 | .claude/agents/team/validator.md | No example invocations | -15 |
| 9 | .claude/agents/team/builder.md | No example invocations | -15 |
| 10 | All 13 thin crypto agents (Read-and-Execute pattern) | No example invocations in each agent file | -15 each |
| 11 | .claude/agents/crypto/crypto-market-agent-opus.md | No output format defined in agent body (deferred to prompt file) | -10 |
| 12 | .claude/agents/crypto/crypto-market-agent-sonnet.md | No output format defined in agent body | -10 |
| 13 | .claude/agents/crypto/crypto-market-agent-haiku.md | No output format defined in agent body | -10 |
| 14 | .claude/agents/crypto/crypto-coin-analyzer-opus.md | No output format defined in agent body | -10 |
| 15 | .claude/agents/crypto/crypto-coin-analyzer-sonnet.md | No output format defined in agent body | -10 |
| 16 | .claude/agents/crypto/crypto-coin-analyzer-haiku.md | No output format defined in agent body | -10 |
| 17 | .claude/agents/crypto/crypto-investment-plays-opus.md | No output format defined in agent body | -10 |
| 18 | .claude/agents/crypto/crypto-investment-plays-sonnet.md | No output format defined in agent body | -10 |
| 19 | .claude/agents/crypto/crypto-investment-plays-haiku.md | No output format defined in agent body | -10 |
| 20 | .claude/agents/crypto/macro-crypto-correlation-scanner-opus.md | No output format defined in agent body | -10 |
| 21 | .claude/agents/crypto/macro-crypto-correlation-scanner-sonnet.md | No output format defined in agent body | -10 |
| 22 | .claude/agents/crypto/macro-crypto-correlation-scanner-haiku.md | No output format defined in agent body | -10 |
| 23 | .claude/agents/crypto/crypto-movers-haiku.md | No output format defined in agent body | -10 |
| 24 | .claude/agents/crypto/crypto-market-agent-opus.md | `Write` declared in tools but not used by delegated prompt | -3 |
| 25 | .claude/agents/crypto/crypto-market-agent-sonnet.md | `Write` declared in tools but not used by delegated prompt | -3 |
| 26 | .claude/agents/crypto/crypto-market-agent-haiku.md | `Write` declared in tools but not used by delegated prompt | -3 |
| 27 | .claude/agents/crypto/crypto-coin-analyzer-opus.md | `Write` declared in tools but not used by delegated prompt | -3 |
| 28 | .claude/agents/crypto/crypto-coin-analyzer-sonnet.md | `Write` declared in tools but not used by delegated prompt | -3 |
| 29 | .claude/agents/crypto/crypto-coin-analyzer-haiku.md | `Write` declared in tools but not used by delegated prompt | -3 |
| 30 | .claude/commands/plan.md | No `allowed-tools` declared; uses vague quantifiers ("comprehensive", "relevant", "appropriate") | -5 / -10 |
| 31 | .claude/commands/plan_w_team.md | No explicit `allowed-tools`; uses vague quantifiers ("comprehensive", "relevant", "appropriate") | -5 / -10 |
| 32 | .claude/commands/build.md | No `allowed-tools` declared | -5 |
| 33 | .claude/commands/sentient.md | Description "Manage, organize and ships your codebase" does not match actual rm -rf demo content | -10 |
| 34 | CLAUDE.md | File is effectively empty (1 line); provides no project context, conventions, or guidance to Claude | -25 |
| 35 | .claude/agents/meta-agent.md | "relevant to its specific domain" — vague quantifier | -2 |

## Cross-Component
**Thin-agent / prompt-file split**: 13 crypto agents delegate entirely via `Read and Execute: .claude/commands/agent_prompts/<file>.md`. The referenced prompt files exist and are valid, but they carry no frontmatter themselves. This creates an asymmetric documentation layer — the agent declares capabilities (model, tools, description) but the actual instructions, output format, and workflow live in a separate undiscoverable file. If the prompt files were ever moved or renamed the agents would silently break with no error at registration time.

**Ambiguous agent tier dispatch**: `cook.md` and `cook_research_only.md` call agents by bare name (e.g., `crypto-coin-analyzer`, `crypto-market-agent`) without specifying tier (haiku/sonnet/opus). Three full tier variants exist for each. It is undefined which tier Claude will select; the call is likely resolved by description-matching, but with identical descriptions across tiers the selection is non-deterministic.

**`sentient.md` description/content contradiction**: The `description` field advertises general-purpose codebase management; the body is a documented demo of hook-blocked destructive commands. Any tooling that uses `description` for routing (including Claude itself for auto-delegation) will misroute this command.

**Empty CLAUDE.md**: The project root `CLAUDE.md` is blank. Given the depth of hooks and agent orchestration in this repo, missing project-level guidance means every new session starts without critical context about build tools (`uv`), hook configuration, or the overall agent architecture.

## Recommendation
REVIEW — submit NL fix PRs, flag security findings in issue.

**NL fix PRs are safe to submit** — add frontmatter descriptions to the 12 missing command/prompt files, add WebSearch to `llm-ai-agents-and-eng-research.md` tools list, and populate `CLAUDE.md`.

**Security findings to flag in an issue** (not PRs): The `sentient.md` misleading description and `setup.py` runtime package installs warrant a maintainer conversation. No Critical or High findings; all findings are expected for a hooks-demo repository but worth documenting. The `sentient.md` demo should carry a clearer description to prevent accidental triggering in cloned setups without the accompanying hook.
