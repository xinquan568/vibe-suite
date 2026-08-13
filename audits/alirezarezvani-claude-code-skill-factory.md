# NLPM Audit: alirezarezvani/claude-code-skill-factory
**Date**: 2026-04-29  |  **Artifacts**: 46  |  **Strategy**: full
**NL Score**: 80/100
**Security**: REVIEW
**Bugs**: 10  |  **Quality Issues**: 4  |  **Security Findings**: 3

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude/agents/hooks-guide.md | agent | 83 | Hardcoded developer absolute path `/Users/rezarezvani/…` in Steps 5–6 bash blocks; 5 vague quantifiers (comprehensive×3, seamless, well-structured) |
| .claude/agents/skills-guide.md | agent | 89 | 4 vague quantifiers (comprehensive×3, seamless) |
| .claude/agents/factory-guide.md | agent | 87 | Single conversation example; no failure or edge-case scenario; 3 vague quantifiers |
| .claude/agents/prompts-guide.md | agent | 88 | 3 vague quantifiers (comprehensive, effective, optimal) |
| .claude/agents/agents-guide.md | agent | 88 | 4 vague quantifiers (comprehensive×2, thorough, effective) |
| .claude/agents/README.md | doc | 75 | Navigation documentation only; not a registerable agent |
| .claude/commands/ci-guard.md | command | 89 | No `allowed-tools` field; 2 vague quantifiers |
| .claude/commands/sync-branch.md | command | 89 | No `allowed-tools` field; 2 vague quantifiers |
| .claude/commands/run-release.md | command | 88 | No `allowed-tools` field; 3 vague quantifiers (comprehensive, clean, smooth) |
| .claude/commands/sync-todos-to-github.md | command | 82 | No `allowed-tools`; uses positional `$1`/`$2` instead of `$ARGUMENTS`; 3 vague quantifiers |
| .claude/commands/review.md | command | 91 | No `allowed-tools` field; 2 vague quantifiers |
| .claude/commands/security-scan.md | command | 90 | No `allowed-tools` field; 2 vague quantifiers |
| .claude/commands/git/rv.md | command | 90 | No `allowed-tools` field; 1 vague quantifier |
| .claude/commands/git/cp.md | command | 90 | No `allowed-tools` field; 1 vague quantifier |
| .claude/commands/git/sc.md | command | 90 | No `allowed-tools` field; 1 vague quantifier |
| .claude/commands/git/cm.md | command | 90 | No `allowed-tools` field; 1 vague quantifier |
| .claude/commands/git/pr.md | command | 89 | No `allowed-tools` field; 2 vague quantifiers |
| .claude/commands/test-factory.md | command | 67 | No YAML frontmatter; `description` absent; command will not register with Claude Code |
| .claude/commands/codex-exec.md | command | 65 | No YAML frontmatter; `description` absent; well-documented content wasted |
| .claude/commands/factory-status.md | command | 66 | No YAML frontmatter; `description` absent |
| .claude/commands/validate-output.md | command | 67 | No YAML frontmatter; `description` absent |
| .claude/commands/install-hook.md | command | 65 | No YAML frontmatter; `description` absent |
| .claude/commands/build.md | command | 67 | No YAML frontmatter; `description` absent |
| .claude/commands/build-hook.md | command | 64 | No YAML frontmatter; `description` absent |
| .claude/commands/sync-agents-md.md | command | 65 | No YAML frontmatter; `description` absent |
| .claude/commands/install-skill.md | command | 66 | No YAML frontmatter; `description` absent |
| .claude/commands/README.md | doc | 76 | Navigation documentation; not a registerable command |
| generated-skills/tdd-guide/SKILL.md | skill | 84 | 7 vague quantifiers (comprehensive×4, intelligent×2, complex); multi-language support well-documented |
| generated-skills/ms365-tenant-manager/SKILL.md | skill | 85 | 5 vague quantifiers; PowerShell generation use cases clear |
| generated-skills/claude-md-enhancer/SKILL.md | skill | 87 | 5 vague quantifiers; 7-step interactive workflow precisely described |
| generated-skills/hook-factory/SKILL.md | skill | 87 | 5 vague quantifiers; 10 templates with event types clearly enumerated |
| generated-skills/social-media-analyzer/SKILL.md | skill | 80 | 4 vague quantifiers (comprehensive, actionable, accurate, reliable); output format section does not show example output shape |
| generated-skills/app-store-optimization/SKILL.md | skill | 88 | 4 vague quantifiers; JSON input examples are concrete and exemplary |
| generated-skills/scrum-master-agent/SKILL.md | skill | 84 | 6 vague quantifiers; outbound notification integration documented but opt-in mechanics unclear |
| generated-skills/slash-command-factory/SKILL.md | skill | 86 | 5 vague quantifiers; three official Claude Code patterns accurately documented |
| generated-skills/tech-stack-evaluator/SKILL.md | skill | 83 | 8 vague quantifiers (comprehensive×6, intelligent, data-driven); high-density vague language despite rich content |
| generated-skills/aws-solution-architect/SKILL.md | skill | 84 | 6 vague quantifiers; architecture patterns and use cases clear |
| generated-skills/agent-factory/SKILL.md | skill | 83 | 5 vague quantifiers; generation patterns described but output validation criteria vague |
| generated-skills/codex-cli-bridge/SKILL.md | skill | 84 | 4 vague quantifiers; Codex CLI bridge use cases concrete |
| generated-skills/prompt-factory/SKILL.md | skill | 88 | 4 vague quantifiers; 69 presets with domain taxonomy highly specific |
| generated-skills/content-trend-researcher/SKILL.md | skill | 84 | 5 vague quantifiers; multi-platform coverage clearly enumerated |
| CLAUDE.md | doc | 83 | Orchestration layer; modular architecture well-explained; some vague terms (seamless, focused) |
| .github/CLAUDE.md | doc | 82 | GitHub workflow requirements; task hierarchy specific; vague escalation criteria |
| claude-skills-examples/CLAUDE.md | doc | 81 | Skill architecture reference; well-structured with clear patterns |
| generated-skills/CLAUDE.md | doc | 76 | Catalog documents 9 of 14 present skills; 5 skills (tdd-guide, tech-stack-evaluator, social-media-analyzer, scrum-master-agent, codex-cli-bridge) undocumented |
| documentation/CLAUDE.md | doc | 82 | Template structure guide; clear sections and cross-references |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 (1 false positive dismissed) |
| Medium | 1 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts | 69 |
| MCP configs | 0 |
| Package manifests | 1 |

The repository's 69 scripts span `.github/`, `generated-hooks/`, and `generated-skills/`. The pre-scan flagged 3 HIGH-pattern matches. All three were investigated by reading the relevant source files:

1. **`generated-skills/codex-cli-bridge/codex_executor.py`** — pre-scan matched on `subprocess.run`. Investigation confirms the call uses list form (`cmd` is a `list[str]`) with `shell=False` (default). No injection surface. **False positive.**

2. **`generated-skills/scrum-master-agent/notify_channels.py`** — makes outbound HTTP calls via `urllib.request.urlopen()` to Slack/Teams webhook URLs. URLs are read from `SLACK_WEBHOOK_URL` / `TEAMS_WEBHOOK_URL` env vars or a config file. Feature is opt-in and documented in SKILL.md. Severity downgraded from HIGH to **MEDIUM** (expected outbound network, not an injection surface).

3. **`.github/EMERGENCY_CLEANUP.sh`** — uses `gh issue close $issue_num` in a loop where `$issue_num` comes from `gh api` JSON output via `jq`. The pipeline is `gh api ... | jq '.[]'` → `while read issue_num; do gh issue close $issue_num`. Variable should be double-quoted (`"$issue_num"`) to prevent word-splitting. Severity: **LOW**. Also has a `read -p` confirmation gate that mitigates exploitation risk.

### Security Findings
| # | File | Severity | Pattern | Finding |
|---|------|----------|---------|---------|
| 1 | generated-skills/scrum-master-agent/notify_channels.py | Medium | outbound-webhook-calls | Makes outbound HTTP POST to caller-supplied Slack/Teams webhook URLs. URLs come from env vars/config, not user input — low injection risk, but any skill making external network calls should disclose this in SKILL.md and handle failures gracefully. |
| 2 | .claude/agents/hooks-guide.md | Low | hardcoded-developer-path | Steps 5–6 embed `/Users/rezarezvani/projects/claude-code-skills-factory` — leaks developer username and local filesystem layout to anyone who reads the agent file. Also breaks execution for all non-developer environments. |
| 3 | generated-skills/codex-cli-bridge/codex_executor.py | High (false positive) | subprocess-shell-true | Pre-scan matched subprocess.run; investigation confirms list-form invocation with shell=False. **Dismissed as false positive.** |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude/commands/test-factory.md | No YAML frontmatter block. The `description` field required for slash command registration is absent. | Command is not registered by Claude Code; `/test-factory` cannot be invoked. |
| 2 | .claude/commands/codex-exec.md | No YAML frontmatter block. The `description` field is absent. | Command not registered; invocation fails silently. |
| 3 | .claude/commands/factory-status.md | No YAML frontmatter block. The `description` field is absent. | Command not registered. |
| 4 | .claude/commands/validate-output.md | No YAML frontmatter block. The `description` field is absent. | Command not registered. |
| 5 | .claude/commands/install-hook.md | No YAML frontmatter block. The `description` field is absent. | Command not registered. |
| 6 | .claude/commands/build.md | No YAML frontmatter block. The `description` field is absent. | Command not registered. |
| 7 | .claude/commands/build-hook.md | No YAML frontmatter block. The `description` field is absent. | Command not registered. |
| 8 | .claude/commands/sync-agents-md.md | No YAML frontmatter block. The `description` field is absent. | Command not registered. |
| 9 | .claude/commands/install-skill.md | No YAML frontmatter block. The `description` field is absent. | Command not registered. |
| 10 | .claude/agents/hooks-guide.md | Lines 253 and 259 hardcode `/Users/rezarezvani/projects/claude-code-skills-factory` as the working directory for bash execution steps. Any user who installs this agent will get a non-existent path error on Steps 5–6. | Hook generation steps silently fail on all non-developer machines. |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Severity | Finding | Fix |
|---|------|----------|---------|-----|
| 1 | generated-skills/scrum-master-agent/notify_channels.py | Medium | Undisclosed outbound network calls to third-party webhook services. | Add a `### Network Access` section to SKILL.md declaring the outbound calls. Wrap `urlopen()` in try/except with a timeout (`timeout=10`) and log failures instead of propagating exceptions. |
| 2 | .claude/agents/hooks-guide.md | Low | Hardcoded developer absolute path leaks username and breaks cross-environment execution. | Replace `/Users/rezarezvani/projects/claude-code-skills-factory` with `$CLAUDE_PROJECT_DIR` or `$(pwd)`. If the agent needs the factory repo path, prompt the user for it in Step 1 and store in a variable. |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .claude/commands/ci-guard.md (representative) | **Missing `allowed-tools`** — 11 of 11 slash commands with valid frontmatter omit the `allowed-tools` field. Without this field Claude Code cannot enforce tool boundaries, and the command may silently acquire tools beyond its intended scope. Affects: ci-guard, sync-branch, run-release, sync-todos-to-github, review, security-scan, and all five git/* commands. | -5 per file |
| 2 | generated-skills/tech-stack-evaluator/SKILL.md (representative) | **High-density vague quantifiers in skills** — all 14 SKILL.md files use 4–8 instances of "comprehensive", "intelligent", "seamless", "data-driven", "advanced", "actionable" without measurable criteria. Worst offender: tech-stack-evaluator (8 instances). Pattern is systematic across the factory's generation templates. | -8 to -16 per file (avg -10) |
| 3 | .claude/agents/hooks-guide.md (representative) | **Vague quantifiers in agents** — all 5 agent files use 3–5 instances of "comprehensive", "seamless", "effective", "thorough". The phrases add length without adding precision about what the agent actually delivers. | -6 to -10 per file (avg -8) |
| 4 | .claude/commands/sync-todos-to-github.md | **Positional argument references** — the command body uses `$1` and `$2` to extract `PLAN_TITLE` and a secondary argument. Claude Code slash commands receive all arguments as a single `$ARGUMENTS` string; `$1`/`$2` are not set. At runtime the variables expand to empty, silently corrupting the GitHub issue title. | -5 (broken argument handling) |

## Cross-Component
The `generated-skills/CLAUDE.md` catalog documents 9 skills in its "Available Skills" section and "Skill Size Reference" table. The repository contains at least 14 `SKILL.md` files. Five confirmed skills — `tdd-guide`, `tech-stack-evaluator`, `social-media-analyzer`, `scrum-master-agent`, and `codex-cli-bridge` — are absent from the catalog. A sixth (`app-store-optimization`) was scored by this audit but also appears absent from the catalog. Users browsing `generated-skills/CLAUDE.md` to discover available skills will miss roughly one-third of the catalog.

The five registered agents in `.claude/agents/` are internally consistent: their tool lists and model pins are correctly declared. The eleven registered slash commands reference no agents or skills, so no broken cross-references exist there. The nine unregistered commands contain no cross-references (they cannot be invoked at all).

## Recommendation
REVIEW — submit the nine missing-frontmatter PRs as a single batch fix; they are mechanical and high-impact. Flag the `hooks-guide.md` hardcoded-path fix as a separate PR since it requires manual path strategy (env var vs. user prompt). Hold the `sync-todos-to-github.md` argument bug for the same batch.

**Immediate PR batch (bugs 1–9)**: For each of the nine commands missing frontmatter, prepend a YAML block:
```yaml
---
description: <one-line description of what this command does>
allowed-tools:
  - Bash
  - Read
---
```
This unblocks registration for nearly half the command catalog in one sweep.

**Follow-up PR (bug 10 + security fix 2)**: Replace the two hardcoded paths in `hooks-guide.md` with `$CLAUDE_PROJECT_DIR` or equivalent, and add a `### Network Access` note to `scrum-master-agent/SKILL.md`.

**Quality sweep**: Add `allowed-tools` to all 11 commands with frontmatter (bug-quality #1). Update `generated-skills/CLAUDE.md` to add the five undocumented skills. Replacing "comprehensive / intelligent / seamless" with measurable alternatives would lift the repo-wide average from 80 to approximately 86+.
