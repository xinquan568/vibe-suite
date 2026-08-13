# NLPM Audit: gotalab/cc-sdd

**Date**: 2026-04-19  |  **Artifacts**: 102  |  **Strategy**: progressive
**NL Score**: 60/100
**Security**: CLEAR
**Bugs**: 5  |  **Quality Issues**: 42  |  **Security Findings**: 0

---

## NL Score Summary

Scored 102 NL artifacts across 8 platform subdirectories under `tools/cc-sdd/templates/agents/`.
Platforms: `claude-code` (12), `antigravity-skills` (3), `opencode` (9), `github-copilot` (12), `windsurf` (12), `codex` (12), `gemini-cli-skills` (22), `windsurf-skills` (20).

| Score | File | Primary Issues |
|------:|------|----------------|
| 20 | `tools/cc-sdd/templates/agents/claude-code/docs/CLAUDE.md` | No frontmatter; `{{DEV_GUIDELINES}}` unfilled |
| 30 | `tools/cc-sdd/templates/agents/antigravity-skills/docs/AGENTS.md` | No frontmatter; `{{DEV_GUIDELINES}}` unfilled |
| 30 | `tools/cc-sdd/templates/agents/github-copilot/docs/AGENTS.md` | No frontmatter; `{{DEV_GUIDELINES}}` unfilled |
| 30 | `tools/cc-sdd/templates/agents/windsurf/docs/AGENTS.md` | No frontmatter; `{{DEV_GUIDELINES}}` unfilled |
| 30 | `tools/cc-sdd/templates/agents/codex/docs/AGENTS.md` | No frontmatter; `{{DEV_GUIDELINES}}` unfilled |
| 30 | `tools/cc-sdd/templates/agents/gemini-cli-skills/docs/GEMINI.md` | No frontmatter; `{{DEV_GUIDELINES}}` unfilled |
| 30 | `tools/cc-sdd/templates/agents/windsurf-skills/docs/AGENTS.md` | No frontmatter; `@` path notation bug |
| 30 | `tools/cc-sdd/templates/agents/gemini-cli-skills/gemini-agents/spec-reviewer.md` | No frontmatter; no structure (BUG) |
| 45 | `tools/cc-sdd/templates/agents/claude-code/commands/spec-status.md` | No name, no model, no examples; Write/Edit on read-only (BUG) |
| 45 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-impl/templates/implementer-prompt.md` | No frontmatter; sub-agent template |
| 45 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-impl/templates/debugger-prompt.md` | No frontmatter; sub-agent template |
| 45 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-impl/templates/reviewer-prompt.md` | No frontmatter; sub-agent template |
| 45 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-impl/templates/implementer-prompt.md` | No frontmatter; sub-agent template |
| 45 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-impl/templates/debugger-prompt.md` | No frontmatter; sub-agent template |
| 45 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-impl/templates/reviewer-prompt.md` | No frontmatter; sub-agent template |
| 49 | `tools/cc-sdd/templates/agents/claude-code/commands/spec-design.md` | No name, no model, no examples |
| 49 | `tools/cc-sdd/templates/agents/claude-code/commands/validate-gap.md` | No name, no model, no examples |
| 50 | `tools/cc-sdd/templates/agents/opencode/kiro-spec-design.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/opencode/kiro-validate-impl.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/opencode/kiro-validate-gap.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/opencode/kiro-spec-requirements.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/opencode/kiro-validate-design.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/opencode/kiro-spec-tasks.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/opencode/kiro-spec-impl.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/github-copilot/kiro-spec-design.prompt.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/github-copilot/kiro-validate-impl.prompt.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/github-copilot/kiro-validate-gap.prompt.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/github-copilot/kiro-spec-requirements.prompt.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/github-copilot/kiro-validate-design.prompt.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/github-copilot/kiro-spec-tasks.prompt.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/github-copilot/kiro-spec-impl.prompt.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/github-copilot/kiro-spec-init.prompt.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/github-copilot/kiro-spec-status.prompt.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-spec-design.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-validate-impl.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-validate-gap.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-spec-requirements.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-validate-design.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-spec-tasks.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-spec-impl.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-spec-init.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-spec-status.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/codex/kiro-spec-design.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/codex/kiro-validate-impl.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/codex/kiro-validate-gap.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/codex/kiro-spec-requirements.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/codex/kiro-validate-design.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/codex/kiro-spec-tasks.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/codex/kiro-spec-impl.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/codex/kiro-spec-init.md` | No name, no model, no allowed-tools, no examples |
| 50 | `tools/cc-sdd/templates/agents/codex/kiro-spec-status.md` | No name, no model, no allowed-tools, no examples |
| 55 | `tools/cc-sdd/templates/agents/claude-code/commands/validate-design.md` | No name, no model, no examples |
| 55 | `tools/cc-sdd/templates/agents/claude-code/commands/spec-impl.md` | No name, no model, no examples |
| 55 | `tools/cc-sdd/templates/agents/claude-code/commands/spec-init.md` | No name, no model, no examples |
| 55 | `tools/cc-sdd/templates/agents/claude-code/commands/validate-impl.md` | No name, no model, no examples |
| 55 | `tools/cc-sdd/templates/agents/claude-code/commands/spec-tasks.md` | No name, no model, no examples |
| 55 | `tools/cc-sdd/templates/agents/claude-code/commands/spec-requirements.md` | No name, no model, no examples |
| 63 | `tools/cc-sdd/templates/agents/claude-code/commands/steering.md` | No name, no model; wrong tool names in guidance (BUG) |
| 65 | `tools/cc-sdd/templates/agents/opencode/kiro-steering-custom.md` | No name, no model, no allowed-tools |
| 65 | `tools/cc-sdd/templates/agents/opencode/kiro-steering.md` | No name, no model, no allowed-tools |
| 65 | `tools/cc-sdd/templates/agents/github-copilot/kiro-steering.prompt.md` | No name, no model, no allowed-tools |
| 65 | `tools/cc-sdd/templates/agents/github-copilot/kiro-steering-custom.prompt.md` | No name, no model, no allowed-tools |
| 65 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-steering-custom.md` | No name, no model, no allowed-tools |
| 65 | `tools/cc-sdd/templates/agents/windsurf/commands/kiro-steering.md` | No name, no model, no allowed-tools |
| 65 | `tools/cc-sdd/templates/agents/codex/kiro-steering-custom.md` | No name, no model, no allowed-tools |
| 65 | `tools/cc-sdd/templates/agents/codex/kiro-steering.md` | No name, no model, no allowed-tools |
| 70 | `tools/cc-sdd/templates/agents/claude-code/commands/steering-custom.md` | No name, no model |
| 70 | `tools/cc-sdd/templates/agents/antigravity-skills/skills/kiro-spec-status/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/antigravity-skills/skills/kiro-validate-gap/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-spec-status/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-validate-gap/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-verify-completion/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-debug/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-validate-design/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-spec-batch/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-spec-tasks/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-impl/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-review/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-spec-init/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-spec-quick/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-validate-impl/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-spec-design/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-discovery/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-spec-requirements/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-spec-status/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-validate-gap/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-verify-completion/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-debug/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-validate-design/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-spec-tasks/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-impl/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-review/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-spec-init/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-spec-quick/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-validate-impl/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-spec-design/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-discovery/SKILL.md` | No model, no examples |
| 80 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-spec-requirements/SKILL.md` | No model, no examples |
| 95 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-steering-custom/SKILL.md` | No model |
| 95 | `tools/cc-sdd/templates/agents/gemini-cli-skills/skills/kiro-steering/SKILL.md` | No model |
| 95 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-steering-custom/SKILL.md` | No model |
| 95 | `tools/cc-sdd/templates/agents/windsurf-skills/skills/kiro-steering/SKILL.md` | No model |

**Weighted average**: (1×20 + 7×30 + 7×45 + 2×49 + 34×50 + 6×55 + 1×63 + 8×65 + 2×70 + 30×80 + 4×95) / 102 = **60/100**

---

## Security Scan

**Severity counts**: Critical: 0  |  High: 0  |  Medium: 0  |  Low: 0

**Execution surface inventory**:
- Hooks: 0 (no `.claude/settings.json` or hook definitions found)
- Shell scripts: 0
- MCP configs: 0
- Package manifests with dependencies: 0
- Eval/exec patterns: 0
- Network egress in scripts: 0

No executable artifacts detected in `tools/cc-sdd/`. All files are pure Markdown templates. Security gate: **PASSED**.

No security findings.

---

## Bugs (PR-worthy)

| # | File | Issue | Impact | Fix |
|---|------|--------|--------|-----|
| B1 | `claude-code/commands/steering.md` | Tool guidance section references non-existent tool names: `glob_file_search`, `read_file`, `grep`, `list_dir` | Agents following this guidance will call undefined tools, causing execution failures | Replace with correct Claude Code tool names: `Glob`, `Read`, `Grep`, `LS` |
| B2 | `claude-code/commands/spec-status.md` | `allowed-tools` declares `Write`, `Edit`, `MultiEdit`, `Update` on a read-only status command | Unnecessarily broad permissions; `Update` is not a valid Claude Code tool name | Remove Write, Edit, MultiEdit, Update from allowed-tools; keep only Read, Glob, Bash |
| B3 | `gemini-cli-skills/gemini-agents/spec-reviewer.md` | No frontmatter, no name, no description — bare 12-line markdown with no structure | Gemini CLI cannot register or execute this agent; it is effectively invisible to the runtime | Add proper frontmatter with name, description, role definition, and structured instructions |
| B4 | All docs files (CLAUDE.md × 1, AGENTS.md × 5, GEMINI.md × 1) | `{{DEV_GUIDELINES}}` template placeholder is unfilled in all 7 docs | Users see raw template variable in project memory/context files; install pipeline is failing to substitute | Implement template substitution in install/setup script, or provide a safe default value for `{{DEV_GUIDELINES}}` |
| B5 | `windsurf-skills/docs/AGENTS.md` | Skill path uses `@` character (`.windsurf/skills@kiro-*/SKILL.md`) — not valid filesystem path notation | Path references fail at runtime; skill resolution breaks for all windsurf-skills | Change to standard directory separator: `.windsurf/skills/kiro-*/SKILL.md` |

---

## Security Fixes

No security fixes required. Security scan returned CLEAR.

---

## Quality Issues

Issues grouped by type and platform. Each row is a distinct (platform × issue-type) pattern.

| # | Platform | Issue | Files Affected | Penalty/file | Action |
|---|----------|--------|----------------|-------------|--------|
| Q01 | claude-code | No `name` field in command frontmatter | 11/11 commands | −25 | Add `name:` to all command YAML frontmatter |
| Q02 | claude-code | No model declared | 11/11 commands | −5 | Add `model: claude-sonnet-4-5` or appropriate model |
| Q03 | claude-code | No examples (zero examples) | 8/11 commands | −15 | Add at least 2 input/output examples per command |
| Q04 | opencode | No `name` field in command frontmatter | 9/9 commands | −25 | Add `name:` to all opencode command YAML frontmatter |
| Q05 | opencode | No model declared | 9/9 commands | −5 | Add model declaration |
| Q06 | opencode | No `allowed-tools` declared | 9/9 commands | −5 | Add platform-appropriate tool list |
| Q07 | opencode | No examples (zero examples) | 7/9 commands | −15 | Add at least 2 examples to all commands |
| Q08 | github-copilot | No `name` field in prompt frontmatter | 11/11 prompts | −25 | Add `name:` field to all .prompt.md frontmatter |
| Q09 | github-copilot | No model declared | 11/11 prompts | −5 | Add model declaration appropriate for Copilot |
| Q10 | github-copilot | No `allowed-tools` declared | 11/11 prompts | −5 | Add tools list to each prompt |
| Q11 | github-copilot | No examples (zero examples) | 9/11 prompts | −15 | Add examples to all prompts lacking them |
| Q12 | windsurf-commands | No `name` field in command frontmatter | 11/11 commands | −25 | Add `name:` to all Windsurf command YAML frontmatter |
| Q13 | windsurf-commands | No model declared | 11/11 commands | −5 | Add model declaration |
| Q14 | windsurf-commands | No `allowed-tools` declared | 11/11 commands | −5 | Add tool list; `auto_execution_mode: 3` is not a substitute |
| Q15 | windsurf-commands | No examples (zero examples) | 9/11 commands | −15 | Add examples to commands lacking them |
| Q16 | codex | No `name` field | 11/11 commands | −25 | Add `name:` to all codex command `<meta>` blocks or YAML |
| Q17 | codex | No model declared | 11/11 commands | −5 | Add model declaration |
| Q18 | codex | No `allowed-tools` declared | 11/11 commands | −5 | Add tool list |
| Q19 | codex | No examples (zero examples) | 9/11 commands | −15 | Add examples to commands lacking them |
| Q20 | codex | No YAML frontmatter — uses `<meta>` block only | 11/11 commands | qualitative | Consider adding YAML frontmatter for standard field support |
| Q21 | gemini-cli-skills | No model declared in SKILL.md | 17/17 skills | −5 | Add `model:` field to skill metadata |
| Q22 | gemini-cli-skills | No examples in SKILL.md | 15/17 skills | −15 | Add concrete usage examples to each skill |
| Q23 | gemini-cli-skills | Sub-agent template files lack frontmatter | 3/3 templates | −25+−25 | Add name + description frontmatter to implementer/debugger/reviewer templates |
| Q24 | windsurf-skills | No model declared in SKILL.md | 16/16 skills | −5 | Add `model:` field to skill metadata |
| Q25 | windsurf-skills | No examples in SKILL.md | 14/16 skills | −15 | Add usage examples to each skill |
| Q26 | windsurf-skills | Sub-agent template files lack frontmatter | 3/3 templates | −25+−25 | Add name + description frontmatter to implementer/debugger/reviewer templates |
| Q27 | antigravity-skills | No model declared | 2/2 skills | −5 | Add model declaration |
| Q28 | antigravity-skills | No examples | 2/2 skills | −15 | Add usage examples |
| Q29 | all-docs | All 7 docs files have no frontmatter structure | 7/7 | qualitative | These are memory/context docs — consider adding structured YAML header for tooling |
| Q30 | claude-code | `spec-design.md` and `validate-gap.md` declare WebSearch/WebFetch in allowed-tools but instructions do not explicitly guide when to use them | 2 files | qualitative | Either add explicit web-research steps or remove WebSearch/WebFetch |
| Q31 | claude-code | `spec-requirements.md` declares WebSearch/WebFetch but provides no structured research step | 1 file | qualitative | Add explicit web research phase or remove web tools from allowed-tools |
| Q32 | claude-code | Most commands missing empty-input / missing-argument handling | 8/11 commands | −10 | Add Safety & Fallback section covering the case where no feature name is provided |
| Q33 | windsurf-commands | `auto_execution_mode: 3` is present in all commands but its semantics are undocumented | 11 files | qualitative | Add comment or doc entry explaining what mode 3 means and its implications |
| Q34 | github-copilot | `agent: 'agent'` field value is quoted (should be unquoted per YAML spec) | 11 files | qualitative | Change `agent: 'agent'` → `agent: agent` |
| Q35 | opencode | All commands missing `argument-hint` | 9/9 commands | qualitative | Add `argument-hint:` to each command for better IDE completion |
| Q36 | gemini-cli-skills | `kiro-spec-batch/SKILL.md` describes multi-spec batch creation but has no example of a batch workflow invocation | 1 file | −15 | Add example showing batch workflow with a roadmap.md |
| Q37 | windsurf-skills | Skills path notation in docs uses `@` separator inconsistently with gemini-cli-skills path style | qualitative | Standardize skill path documentation across platforms |
| Q38 | claude-code | `spec-status.md` has no argument-hint despite taking a mandatory feature name argument | 1 file | qualitative | Add `argument-hint: <feature-name>` to frontmatter |
| Q39 | all-commands | `{{KIRO_DIR}}` template variable is used correctly in skill/command bodies but is never documented in any README or install guide | cross-cutting | qualitative | Document `{{KIRO_DIR}}` substitution variable and default value in project README |
| Q40 | gemini-cli-skills | `gemini-agents/spec-reviewer.md` has no numbered steps despite multi-step review process | 1 file | −10 | Add numbered execution steps (this file is also Bug B3) |
| Q41 | windsurf-skills | Sequential-only constraint (no sub-agent dispatch) is documented in AGENTS.md but not reflected per-skill — skills do not warn when they reference parallel patterns | 16 files | qualitative | Add platform constraint note to each windsurf skill referencing sub-agent dispatch |
| Q42 | all-platforms | No platform consistently declares a target model — leaves model selection to runtime defaults, reducing determinism | 102 files | −5/file | Establish a model recommendation per platform and add to all skill/command files |

---

## Cross-Component

**Template placeholder consistency**: `{{KIRO_DIR}}`, `{{FEATURE_NAME}}`, `{{TIMESTAMP}}`, `{{PROJECT_DESCRIPTION}}` are used consistently across all platform command bodies. However, `{{DEV_GUIDELINES}}` is present in all 7 docs files and is *not* substituted — this is a systemic install-pipeline gap (Bug B4).

**Platform parity**: The SDD workflow (steering → spec-init → spec-requirements → validate-gap → spec-design → validate-design → spec-tasks → spec-impl → validate-impl) is uniformly implemented across all 6 command platforms. Quality gaps are symmetric: every platform is missing `name`, model declarations, and most examples at the same severity. This suggests the commands were generated from a shared template without completing the platform-specific fields.

**Skill parity**: `gemini-cli-skills` and `windsurf-skills` mirror each other structurally. Key difference: windsurf-skills enforces a sequential-only constraint (no parallel sub-agent dispatch). The cross-cutting quality skills (`kiro-verify-completion`, `kiro-review`, `kiro-debug`) are present in both platforms — good consistency. Both platforms have highest-scoring artifacts (`kiro-steering` and `kiro-steering-custom` at 95/100).

**Sub-agent template files**: `kiro-impl/templates/implementer-prompt.md`, `debugger-prompt.md`, and `reviewer-prompt.md` are present identically in both gemini-cli-skills and windsurf-skills. These templates function as runtime-injected sub-agent prompts and arguably should not require NLPM frontmatter. However, since they contain structured instructions, adding minimal frontmatter would improve discoverability.

**Bugs B1 and B2 are claude-code specific**: Other platforms don't have these issues because they use different tool reference conventions or don't declare allowed-tools at all (which is itself a quality issue).

**Bug B5 is windsurf-skills specific**: The `@` path notation does not appear in gemini-cli-skills, confirming this is a copy-paste or platform-specific error.

---

## Recommendation

**CLEAR — security gate passed. Submit PRs for all 5 bugs.**

Score 60/100 is below the default 70 threshold. The repo demonstrates strong structural design (consistent 8-phase SDD workflow, cross-platform skill parity, well-organized directory layout) but has systemic frontmatter gaps across all platforms that suppress the score. The gemini-cli-skills and windsurf-skills layers are the healthiest at 80-95/100; the command layers for all six platforms cluster at 50-65/100 due to universal missing `name`, model, examples, and `allowed-tools` fields.

**Prioritized actions**:
1. **Fix Bug B4 first** (unfilled `{{DEV_GUIDELINES}}`): affects all 7 docs files and indicates the install pipeline is incomplete.
2. **Fix Bug B1** (wrong tool names in `steering.md`): will cause runtime failures for Claude Code users.
3. **Fix Bug B2** (read-only command with write permissions): security hygiene.
4. **Fix Bug B3** (missing `spec-reviewer.md` frontmatter): Gemini CLI agent is non-functional.
5. **Fix Bug B5** (`@` path notation): breaks windsurf-skills path resolution.
6. **Quality pass**: Add `name` and model fields to all command frontmatter across all platforms — this alone would raise the NL score to approximately 75/100 and push above threshold.
