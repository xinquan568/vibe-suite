# NLPM Audit: Ibrahim-3d/orchestrator-supaconductor
**Date**: 2026-04-30  |  **Artifacts**: 107  |  **Strategy**: full-read
**NL Score**: 89/100
**Security**: REVIEW
**Bugs**: 3  |  **Quality Issues**: 15  |  **Security Findings**: 2

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| agents/board-meeting.md | agent | 60 | `run_shell_command` used in body but not declared in frontmatter tools list (BUG); no examples |
| agents/conductor-orchestrator.md | agent | 65 | No examples; description summarizes workflow (CSO anti-pattern) |
| agents/name-picker.md | agent | 70 | No examples; no formal output format section |
| agents/loop-execution-evaluator.md | agent | 72 | No examples |
| agents/loop-fixer.md | agent | 72 | No examples |
| agents/loop-executor.md | agent | 72 | No examples |
| agents/parallel-dispatcher.md | agent | 72 | No examples; no output format section |
| agents/task-worker.md | agent | 72 | No examples |
| agents/loop-plan-evaluator.md | agent | 75 | No examples |
| agents/loop-planner.md | agent | 75 | No examples |
| agents/code-reviewer.md | agent | 75 | `model: inherit` is not a concrete model ID (R10); examples in description field only |
| agents/ceo.md | agent | 80 | Missing output format section; 5 examples present |
| agents/cmo.md | agent | 80 | Missing output format section; 7 examples present |
| agents/cto.md | agent | 80 | Missing output format section; 7 examples present |
| agents/ux-designer.md | agent | 80 | Missing output format section; examples present |
| skills/business-docs-sync/SKILL.md | skill | 50 | No YAML frontmatter at all — missing name and description (BUG) |
| commands/ui-audit/UI-UX-AUDIT-REPORT.md | template | 50 | Template placed in commands/ with no frontmatter; not usable as a command (BUG) |
| commands/evaluate-plan.md | command | 88 | No allowed-tools; body references `/loop-plan-evaluator` (stale command name) |
| commands/loop-executor.md | command | 88 | No allowed-tools; body references `.claude/agents/orchestrator-supaconductor:loop-executor.md` (stale path) |
| commands/loop-planner.md | command | 88 | No allowed-tools; body references `.claude/agents/orchestrator-supaconductor:loop-planner.md` (stale path) |
| commands/task-worker.md | command | 88 | No allowed-tools; body references `.claude/agents/orchestrator-supaconductor:task-worker.md` (stale path) |
| commands/board-meeting.md | command | 93 | No allowed-tools |
| commands/board-review.md | command | 93 | No allowed-tools |
| commands/brainstorm.md | command | 93 | No allowed-tools; duplicate of commands/brainstorming.md |
| commands/brainstorming.md | command | 93 | No allowed-tools |
| commands/ceo.md | command | 93 | No allowed-tools |
| commands/close-track.md | command | 93 | No allowed-tools |
| commands/cmo.md | command | 93 | No allowed-tools |
| commands/conductor-implement.md | command | 93 | No allowed-tools |
| commands/conductor-new-track.md | command | 93 | No allowed-tools |
| commands/conductor-setup.md | command | 93 | No allowed-tools |
| commands/conductor-status.md | command | 93 | No allowed-tools |
| commands/cto-advisor.md | command | 93 | No allowed-tools |
| commands/cto.md | command | 93 | No allowed-tools |
| commands/evaluate-execution.md | command | 93 | No allowed-tools |
| commands/execute-plan.md | command | 93 | No allowed-tools |
| commands/executing-plans.md | command | 93 | No allowed-tools |
| commands/finishing-a-development-branch.md | command | 93 | No allowed-tools |
| commands/go.md | command | 93 | No allowed-tools |
| commands/implement.md | command | 93 | No allowed-tools |
| commands/loop-execution-evaluator.md | command | 93 | No allowed-tools; near-duplicate of evaluate-execution.md |
| commands/loop-fixer.md | command | 93 | No allowed-tools |
| commands/loop-plan-evaluator.md | command | 93 | No allowed-tools; near-duplicate of evaluate-plan.md |
| commands/new-track.md | command | 93 | No allowed-tools |
| commands/parallel-dispatcher.md | command | 93 | No allowed-tools |
| commands/phase-review.md | command | 93 | No allowed-tools |
| commands/plan-sprint.md | command | 93 | No allowed-tools |
| commands/setup.md | command | 93 | No allowed-tools |
| commands/status.md | command | 93 | No allowed-tools |
| commands/systematic-debugging.md | command | 93 | No allowed-tools |
| commands/ui-audit.md | command | 93 | No allowed-tools |
| commands/using-git-worktrees.md | command | 93 | No allowed-tools |
| commands/ux-designer.md | command | 93 | No allowed-tools |
| commands/write-plan.md | command | 93 | No allowed-tools |
| commands/writing-plans.md | command | 93 | No allowed-tools |
| skills/agent-factory/SKILL.md | skill | 88 | Good structure; Python pseudocode is illustrative only |
| skills/board-of-directors/SKILL.md | skill | 88 | `run_shell_command` instructions in Phase 5 without agent-level tools context |
| skills/context-driven-development/SKILL.md | skill | 88 | Extra `version` field in frontmatter (non-standard) |
| skills/context-loader/SKILL.md | skill | 90 | Near-perfect |
| skills/conductor-orchestrator/SKILL.md | skill | 85 | Description summarizes complex workflow rather than triggering conditions (CSO anti-pattern) |
| skills/cto-advisor/SKILL.md | skill | 86 | Extra non-standard frontmatter fields (license, metadata, python-tools); references external scripts not in repo |
| skills/cto-plan-reviewer/SKILL.md | skill | 88 | Good structure; relies on external cto-advisor frameworks |
| skills/dispatching-parallel-agents/SKILL.md | skill | 88 | Good structure |
| skills/eval-business-logic/SKILL.md | skill | 87 | Very long description (400+ chars) summarizes evaluation methodology |
| skills/eval-code-quality/SKILL.md | skill | 88 | Good structure |
| skills/eval-integration/SKILL.md | skill | 88 | Good structure |
| skills/eval-ui-ux/SKILL.md | skill | 88 | Good structure |
| skills/executing-plans/SKILL.md | skill | 90 | Good |
| skills/finishing-a-development-branch/SKILL.md | skill | 88 | Good structure |
| skills/go/SKILL.md | skill | 90 | Clear entry-point description |
| skills/knowledge/knowledge-manager/SKILL.md | skill | 88 | Good structure |
| skills/knowledge/retrospective-agent/SKILL.md | skill | 88 | Good structure |
| skills/leads/architecture-lead/SKILL.md | skill | 88 | Extra `authority_level` frontmatter field (non-standard) |
| skills/leads/product-lead/SKILL.md | skill | 88 | Extra `authority_level` frontmatter field (non-standard) |
| skills/leads/qa-lead/SKILL.md | skill | 88 | Extra `authority_level` frontmatter field (non-standard) |
| skills/leads/tech-lead/SKILL.md | skill | 88 | Extra `authority_level` frontmatter field (non-standard) |
| skills/loop-execution-evaluator/SKILL.md | skill | 88 | Good structure |
| skills/loop-executor/SKILL.md | skill | 88 | Good structure |
| skills/loop-fixer/SKILL.md | skill | 88 | Good structure |
| skills/loop-plan-evaluator/SKILL.md | skill | 88 | Good structure |
| skills/loop-planner/SKILL.md | skill | 88 | Good structure |
| skills/message-bus/SKILL.md | skill | 88 | Good structure; references utility scripts |
| skills/parallel-dispatch/SKILL.md | skill | 88 | Python pseudocode is illustrative only |
| skills/plan-critiquer/SKILL.md | skill | 88 | Good structure |
| skills/receiving-code-review/SKILL.md | skill | 90 | Good |
| skills/requesting-code-review/SKILL.md | skill | 90 | Good |
| skills/subagent-driven-development/SKILL.md | skill | 90 | Comprehensive; good process flowcharts |
| skills/systematic-debugging/SKILL.md | skill | 90 | Thorough four-phase process |
| skills/test-driven-development/SKILL.md | skill | 92 | Excellent; Iron Law, rationalization table, red flags |
| skills/track-manager/SKILL.md | skill | 88 | Good structure |
| skills/using-git-worktrees/SKILL.md | skill | 90 | Good |
| skills/using-supaconductor/SKILL.md | skill | 90 | Core entry-point skill; good EXTREMELY-IMPORTANT framing |
| skills/verification-before-completion/SKILL.md | skill | 90 | Strong discipline enforcement |
| skills/writing-plans/SKILL.md | skill | 90 | Good |
| skills/writing-skills/SKILL.md | skill | 90 | Comprehensive CSO and TDD guidance |
| skills/agent-factory/SKILL.md | skill | 88 | See above |
| skills/brainstorming/SKILL.md | skill | 90 | HARD-GATE trigger; good |
| skills/context-driven-development/SKILL.md | skill | 88 | See above |
| skills/go/SKILL.md | skill | 90 | See above |
| hooks/hooks.json | config | 95 | Valid; one SessionStart hook registered |
| hooks/session-start.sh | hook | 78 | Outbound curl on every session start (SEC-outbound-network-call); JSON construction is safe |
| scripts/setup.sh | script | 90 | Clean; uses heredocs, no user-controlled shell expansion |
| .claude-plugin/plugin.json | manifest | 95 | Well-formed; all required fields present |

**Weighted average**: (15 agents × 73.3 + 49 commands × 93.7 + 43 skills × 87.9) / 107 = 9471 / 107 = **88.5 → 89/100**

---

## Security Scan

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks (registered in hooks.json) | hooks/session-start.sh |
| Scripts (manual-run helpers) | scripts/setup.sh |
| Scripts (development utilities) | skills/systematic-debugging/find-polluter.sh, skills/writing-skills/render-graphs.js |
| JS library | lib/skills-core.js |
| Python scripts | skills/message-bus/scripts/init-bus.py, skills/message-bus/scripts/monitor-bus.py, skills/cto-advisor/scripts/tech_debt_analyzer.py, skills/cto-advisor/scripts/team_scaling_calculator.py |
| MCP configs | None |
| Package manifests | None |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Low | hooks/session-start.sh | 25 | curl-version-check | `curl -s --max-time 3 "https://api.github.com/repos/${REPO}/releases/latest"` runs on every Claude Code session start; REPO is hardcoded so no SSRF risk, but makes an unconditional outbound network request at plugin load time with no caching |
| 2 | Medium | agents/conductor-orchestrator.md | — | shell-exec-unsanitized-input | `escalateToBoard` helper spawns `claude --print --model opus "/orchestrator-supaconductor:board-meeting {question}"` and the `invoke_superpower()` function interpolates `$superpower $params` into a shell command; track IDs and plan-file content flow into these invocations without sanitization, allowing shell metacharacter injection if a track name contains backticks, semicolons, or `$()` sequences |

**Rating: REVIEW** — one medium risk pattern (shell injection via unsanitized track/question strings); no critical patterns (no eval-cmd-subst, no curl-pipe-sh, no base64+exec, no credential exfiltration).

---

## Bugs (PR-worthy)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | agents/board-meeting.md | Phase 5 (line 109) explicitly instructs `run_shell_command "mkdir -p conductor/tracks/{trackId}/.message-bus/board/"` but the frontmatter `tools` list only declares `read_file` and `write_file`; the mkdir will silently fail at runtime because the tool is not authorized | Add `run_shell_command` to the `tools` list in the agent frontmatter, or replace the mkdir instruction with nested `write_file` calls to create the required structure |
| 2 | skills/business-docs-sync/SKILL.md | File has no YAML frontmatter block whatsoever; both required `name` and `description` fields are missing; the skill is invisible to the Skill tool and cannot be invoked | Add frontmatter: `---\nname: business-docs-sync\ndescription: Use when ...\n---` |
| 3 | commands/ui-audit/UI-UX-AUDIT-REPORT.md | Template report file placed in `commands/` directory with no YAML frontmatter; it cannot be invoked as a command and will confuse discovery tools that scan the commands directory | Move to `docs/` or `templates/` directory and add a README note; or add frontmatter if it is meant to be invocable |

---

## Cross-Component Issues

| # | File | Issue |
|---|------|-------|
| 1 | commands/loop-planner.md | Body references `.claude/agents/orchestrator-supaconductor:loop-planner.md` — the legacy direct-path agent convention; current convention is to dispatch via the `Task` tool or `Skill` tool invocation, not by path |
| 2 | commands/task-worker.md | Body references `.claude/agents/orchestrator-supaconductor:task-worker.md` — same stale-path issue |
| 3 | commands/loop-executor.md | Body references `.claude/agents/orchestrator-supaconductor:loop-executor.md` — same stale-path issue |
| 4 | commands/evaluate-plan.md | Body says "Use `/loop-plan-evaluator`" but the canonical command under this plugin is `/evaluate-plan` (the file's own name); creates user confusion if both commands exist |
| 5 | commands/brainstorm.md + commands/brainstorming.md | Near-duplicate commands; both invoke the brainstorming skill with no functional differentiation |
| 6 | commands/evaluate-plan.md + commands/loop-plan-evaluator.md | Near-duplicate commands targeting the same loop-plan-evaluator agent |
| 7 | commands/evaluate-execution.md + commands/loop-execution-evaluator.md | Near-duplicate commands targeting the same loop-execution-evaluator agent |

---

## Quality Issues (non-PR-worthy patterns)

| Pattern | Count | Impact | Rule |
|---------|-------|--------|------|
| Commands missing `allowed-tools` field | 48/49 commands | Low — tool access is unrestricted; security posture weakened slightly | R11 |
| Agents missing example blocks | 11/15 agents | Medium — new users lack reference invocation patterns | R09 |
| Advisory agents (CEO, CMO, CTO, UX-designer) missing output format section | 4 agents | Low — advisory agents are flexible but a format helps set expectations | R12 |
| `skills/conductor-orchestrator/SKILL.md` description summarizes complex v3 workflow instead of triggering conditions | 1 skill | Medium — the description (~400 chars) describes WHAT the skill does rather than WHEN to invoke it; following the CSO anti-pattern documented in writing-skills | R01 |
| Non-standard extra fields in skill frontmatter (`authority_level`, `version`, `python-tools`, `license`) | 6 skills | Info — fields are ignored but add noise | R02 |
| `agents/code-reviewer.md` uses `model: inherit` | 1 agent | Low — executor cannot determine model tier; `inherit` is not a recognized model ID | R10 |

---

## Summary

**orchestrator-supaconductor** is a mature, comprehensive multi-agent orchestration framework (Conductor v3) with 107 NL artifacts across 15 agents, 49 commands, and 43 skills. The plugin implements a sophisticated Evaluate-Loop with DAG-based parallel execution, Board of Directors deliberation, and a knowledge learning layer.

**Strengths:**
- Skills are thorough and well-structured; all but one have valid frontmatter
- Commands are consistently structured dispatcher wrappers
- Strong methodology skills (TDD, systematic-debugging, verification-before-completion)
- Security surface is minimal — no MCP configs, no dependency manifests, no postinstall hooks
- Hooks JSON is well-formed; session-start.sh JSON construction uses safe bash escaping

**Issues that warrant PRs:**
1. `agents/board-meeting.md` — runtime bug: `run_shell_command` used without being declared in tools list
2. `skills/business-docs-sync/SKILL.md` — registration bug: no YAML frontmatter; skill is invisible
3. `commands/ui-audit/UI-UX-AUDIT-REPORT.md` — misplaced template: no frontmatter, cannot be used as a command
4. `hooks/session-start.sh` — low severity: outbound curl on every session start with no caching

**Issues that are quality improvements (not bugs):**
- All commands missing `allowed-tools` (systematic, low-impact)
- Most execution agents missing example invocations (quality gap, not a blocker)
- Three commands referencing stale agent path format (cross-component)
- Shell injection risk in conductor-orchestrator's `escalateToBoard` pattern (design-level, medium severity)
