# NLPM Audit: alirezarezvani/claude-code-tresor

**Generated**: 2026-04-29  
**Auditor**: nlpm v0.1 (claude-code-tresor)  
**Target**: https://github.com/alirezarezvani/claude-code-tresor  
**Branch audited**: main (v2.7.0)  
**Risk level**: CLEAR  
**Composite NL score**: 81 / 100

---

## Security Scan

**Result**: CLEAR — no hooks, no MCP config, no executable code beyond install scripts.

| Surface | Count | Findings |
|---------|-------|----------|
| Hooks (`.claude/hooks/`) | 0 | — |
| Scripts (`scripts/`) | 2 | See below |
| MCP configs (`.mcp.json`) | 0 | — |
| `package.json` | 0 | — |
| `requirements.txt` | 0 | — |
| Critical patterns | 0 | — |
| High patterns | 0 | — |

`scripts/install.sh` and `scripts/update.sh` are straightforward shell scripts that copy files into `~/.claude/` using `mkdir`, `cp`, and `git clone`. No `curl | sh`, no `eval`, no credential exfiltration, no dynamic code execution. Risk level: **CLEAR**. These scripts are the recommended install path documented by the author.

---

## Artifact Discovery

| Category | Found | Scored | Notes |
|----------|-------|--------|-------|
| Agents | 8 | 8 | All in `agents/` (deprecated; symlinked from `subagents/core/`) |
| Commands | 24 | 24 | 17 unique + 5 duplicates + 2 missing (scored 0) |
| Skills | 8 | 8 | All in `skills/` |
| CLAUDE.md | 1 | 1 | Repository dev guide |
| **Total** | **41** | **41** | |

Two referenced command files do not exist on disk:
- `commands/documentation/docs-gen/docs-gen.md` — **missing**
- `commands/testing/test-gen/test-gen.md` — **missing**

Both are documented in CLAUDE.md as production features (v2.7.0). They score 0.

---

## Composite Score: 81 / 100

| Category | Files | Avg Score | Weighted |
|----------|-------|-----------|---------|
| Agents | 8 | 91.0 | 728 |
| Commands | 24 | 74.9 | 1798 |
| Skills | 8 | 89.0 | 712 |
| CLAUDE.md | 1 | 90.0 | 90 |
| **Total** | **41** | **81.2** | **3328** |

Threshold: 70 (default). **PASS**.

---

## Per-File Scores

### Agents

| File | Score | Key Deductions |
|------|-------|---------------|
| `agents/refactor-expert.md` | 94 | −6 vague quantifiers |
| `agents/security-auditor.md` | 92 | −8 vague quantifiers |
| `agents/root-cause-analyzer.md` | 94 | −6 vague quantifiers |
| `agents/performance-tuner.md` | 94 | −6 vague quantifiers |
| `agents/test-engineer.md` | 94 | −6 vague quantifiers |
| `agents/docs-writer.md` | 96 | −4 vague quantifiers |
| `agents/config-safety-reviewer.md` | **72** | −20 body/identity mismatch (body is old `@code-reviewer` template); −8 vague quantifiers |
| `agents/systems-architect.md` | 92 | −8 vague quantifiers |

### Commands

| File | Score | Key Deductions |
|------|-------|---------------|
| `commands/development/scaffold/scaffold.md` | 91 | −4 vague quantifiers; −5 missing empty-arg guard |
| `commands/workflow/review/review.md` | 82 | −8 vague quantifiers; −5 missing `name:` in frontmatter; −5 no arg-handling text for empty scope |
| `commands/workflow/handoff-create/handoff-create.md` | 81 | −8 vague quantifiers; −3 `WebSearch` declared but usage not evident; −8 minor inconsistency in output header |
| `commands/workflow/add-to-todos/add-to-todos.md` | 90 | −6 vague quantifiers; −4 minor |
| `commands/workflow/check-todos/check-todos.md` | 90 | −6 vague quantifiers; −4 minor |
| `commands/workflow/run-prompt/run-prompt.md` | 90 | −6 vague quantifiers; −4 minor |
| `commands/workflow/create-prompt/create-prompt.md` | 88 | −8 vague quantifiers; −4 minor |
| `commands/workflow/todo-check/todo-check.md` | 90 | **DUPLICATE** of `check-todos.md` |
| `commands/workflow/todo-add/todo-add.md` | 90 | **DUPLICATE** of `add-to-todos.md` |
| `commands/workflow/prompt-run/prompt-run.md` | 90 | **DUPLICATE** of `run-prompt.md` |
| `commands/workflow/whats-next/whats-next.md` | 81 | **NEAR-DUPLICATE** of `handoff-create.md` (header text differs) |
| `commands/workflow/prompt-create/prompt-create.md` | 88 | **NEAR-DUPLICATE** of `create-prompt.md` (header text differs) |
| `commands/security/audit/audit.md` | 77 | −3 `SlashCommand` invalid tool; −10 `TodoWrite` used but not declared; −10 vague quantifiers |
| `commands/performance/profile/profile.md` | 77 | −3 `SlashCommand` invalid; −10 `TodoWrite` undeclared; −10 vague |
| `commands/performance/benchmark/benchmark.md` | 77 | −3 `SlashCommand` invalid; −10 `TodoWrite` undeclared; −10 vague |
| `commands/operations/deploy-validate/deploy-validate.md` | 77 | −3 `SlashCommand` invalid; −10 `TodoWrite` undeclared; −10 vague |
| `commands/operations/health-check/health-check.md` | 77 | −3 `SlashCommand` invalid; −10 `TodoWrite` undeclared; −10 vague |
| `commands/operations/incident-response/incident-response.md` | 75 | −3 `SlashCommand` invalid; −10 `TodoWrite` undeclared; −10 vague; −2 JS syntax error lines 712–713 |
| `commands/quality/debt-analysis/debt-analysis.md` | 62 | −10 missing output format; −10 no numbered phase steps; −3 `SlashCommand` invalid; −10 `TodoWrite` undeclared; −5 underdeveloped body |
| `commands/quality/code-health/code-health.md` | 71 | −3 `SlashCommand` invalid; −10 `TodoWrite` undeclared; −16 vague; references stale `@code-reviewer` name |
| `commands/security/compliance-check/compliance-check.md` | 77 | −3 `SlashCommand` invalid; −10 `TodoWrite` undeclared; −10 vague |
| `commands/security/vulnerability-scan/vulnerability-scan.md` | 77 | −3 `SlashCommand` invalid; −10 `TodoWrite` undeclared; −10 vague |
| `commands/documentation/docs-gen/docs-gen.md` | **0** | **FILE NOT FOUND** |
| `commands/testing/test-gen/test-gen.md` | **0** | **FILE NOT FOUND** |

### Skills

| File | Score | Key Deductions |
|------|-------|---------------|
| `skills/development/git-commit-helper/SKILL.md` | 90 | −6 vague quantifiers; −4 minor |
| `skills/development/code-reviewer/SKILL.md` | 84 | −8 vague; −8 stale `@code-reviewer` and `@architect` agent names |
| `skills/development/test-generator/SKILL.md` | 90 | −6 vague; −4 minor |
| `skills/documentation/readme-updater/SKILL.md` | 90 | −6 vague; −4 minor |
| `skills/documentation/api-documenter/SKILL.md` | 90 | −6 vague; −4 minor |
| `skills/security/security-auditor/SKILL.md` | 90 | −6 vague; −4 minor |
| `skills/security/secret-scanner/SKILL.md` | 93 | −4 vague; −3 minor |
| `skills/security/dependency-auditor/SKILL.md` | 85 | −6 vague; −9 stale `@architect` agent name reference |

### CLAUDE.md

| File | Score | Notes |
|------|-------|-------|
| `CLAUDE.md` | 90 | Comprehensive, well-structured repo guide. Architecture, workflows, usage examples all present. −10 minor: some sections use stale v2.4 agent names in code examples. |

---

## Findings Summary

### CRITICAL

_None_. No security-blocking findings.

### HIGH

| # | Finding | Files | Penalty |
|---|---------|-------|---------|
| H1 | `SlashCommand` declared in `allowed-tools` but is not a valid Claude Code tool | 10 commands | −3 per file |
| H2 | `agents/config-safety-reviewer.md` body is the old `@code-reviewer` template — name, description, and body are mismatched | 1 agent | −20 |
| H3 | Two commands referenced in CLAUDE.md do not exist on disk: `docs-gen.md`, `test-gen.md` | 2 commands | −100 each |
| H4 | Five pairs of duplicate command files under different directory paths | 5 commands | — |

### MEDIUM

| # | Finding | Files | Penalty |
|---|---------|-------|---------|
| M1 | `TodoWrite` used in command body pseudo-code but not declared in `allowed-tools` | 10 commands | Informational |
| M2 | Stale v2.4 agent names in README files: `@code-reviewer` (config-safety-reviewer/README.md), `@debugger` (root-cause-analyzer/README.md), `@architect` (systems-architect/README.md) | 3 READMEs | Not scored (READMEs not NL artifacts) |
| M3 | Stale v2.4 agent references inside scored skill bodies: `@code-reviewer` and `@architect` in `code-reviewer/SKILL.md`; `@architect` in `dependency-auditor/SKILL.md` | 2 skills | −8, −9 |
| M4 | `commands/quality/debt-analysis/debt-analysis.md` is significantly underdeveloped (65 lines) vs all other orchestration commands (700–1100 lines) | 1 command | −15 |
| M5 | JS pseudo-code syntax error in `incident-response.md` lines 712–713 (`activeForm":` stray quote) | 1 command | −2 |

### LOW

| # | Finding | Files |
|---|---------|-------|
| L1 | Vague quantifiers ("comprehensive", "various", "multiple", "robust", "detailed") appear throughout all artifacts | All 41 files |
| L2 | Agent README files for 3 of 8 agents use deprecated v2.4 names (not scored as NL artifacts but affect UX) | 3 READMEs |
| L3 | `commands/workflow/review/review.md` missing `name:` frontmatter field | 1 command |

---

## Detailed Findings

### H1 — `SlashCommand` is not a valid Claude Code tool

**Severity**: HIGH  
**Files**: `audit.md`, `profile.md`, `benchmark.md`, `deploy-validate.md`, `health-check.md`, `incident-response.md`, `debt-analysis.md`, `code-health.md`, `compliance-check.md`, `vulnerability-scan.md`  
**Line**: 5 (in each `allowed-tools:` frontmatter)

All 10 orchestration commands declare `SlashCommand` in their `allowed-tools` list. `SlashCommand` is not a tool in the Claude Code API (confirmed: not in standard tool list, not in the deferred tools list). The commands use it in pseudo-code like:

```javascript
await SlashCommand({ command: `/todo-add "..."` });
```

This is a conceptual placeholder that will never execute. Users invoking these commands will not get the advertised automatic `/todo-add` integration. The commands should either:
1. Remove `SlashCommand` from `allowed-tools` (and document the integration as manual), or
2. Replace with the correct tool invocation pattern (`TodoWrite` for todo management, or explicit instructions to the model to invoke the slash command as text)

**Suggested fix**: Remove `SlashCommand` from `allowed-tools`. Use `TodoWrite` (already used correctly in the body) for task capture. Update documentation to clarify the integration model.

---

### H2 — `config-safety-reviewer.md` body/identity mismatch

**Severity**: HIGH  
**File**: `agents/config-safety-reviewer.md`  
**Line**: 10+

The agent's frontmatter declares:
```yaml
name: config-safety-reviewer
description: Configuration safety specialist...
```

But the body opens with:
> "You are an expert code reviewer..."

And proceeds to describe a general code review workflow (SOLID principles, PR review patterns, etc.) with no mention of configuration safety, database timeouts, environment-specific settings, or any of the configuration safety domain expertise described in the `description:` field.

This agent was renamed from `@code-reviewer` to `@config-safety-reviewer` in v2.5, but only the frontmatter fields were updated — the body was not rewritten to match the new identity. A user invoking `@config-safety-reviewer` for config safety analysis will get a generic code reviewer instead.

**Suggested fix**: Rewrite the agent body to focus on configuration safety: database connection strings, timeout values, environment variable validation, deployment config review, production vs development config drift, and infrastructure capacity matching.

---

### H3 — Missing command files

**Severity**: HIGH  
**Files**: `commands/documentation/docs-gen/docs-gen.md`, `commands/testing/test-gen/test-gen.md`

CLAUDE.md documents both as production v2.7.0 features with usage examples:
```bash
/docs-gen api --format openapi --include-examples
/test-gen --file utils.js --framework jest --coverage 90
```

The directories exist (`commands/documentation/docs-gen/` and `commands/testing/test-gen/`) with `README.md` files, but the actual command `.md` files are absent. Users who invoke these commands will get a "command not found" error.

**Suggested fix**: Create the missing `.md` command files, or remove the directories and references from CLAUDE.md until implemented.

---

### H4 — Duplicate command files

**Severity**: HIGH  
**Duplicates**:

| Canonical | Duplicate | Difference |
|-----------|-----------|------------|
| `workflow/check-todos/check-todos.md` | `workflow/todo-check/todo-check.md` | Identical |
| `workflow/add-to-todos/add-to-todos.md` | `workflow/todo-add/todo-add.md` | Identical |
| `workflow/run-prompt/run-prompt.md` | `workflow/prompt-run/prompt-run.md` | Identical |
| `workflow/handoff-create/handoff-create.md` | `workflow/whats-next/whats-next.md` | Header text only ("Tresor Workflow Framework" vs "TÂCHES workflow framework") |
| `workflow/create-prompt/create-prompt.md` | `workflow/prompt-create/prompt-create.md` | Header text only |

This appears to be a migration artifact — the canonical names were introduced in v2.7 to replace earlier names, but both versions exist on disk. Having two commands with the same behavior confuses users and bloats the command list. Fixes diverge between the duplicates will create behavioral divergence.

**Suggested fix**: Remove the duplicate files (`todo-check`, `todo-add`, `prompt-run`, `whats-next`, `prompt-create`). Update CLAUDE.md and any documentation that references the old names.

---

### M1 — `TodoWrite` used but not declared in `allowed-tools`

**Severity**: MEDIUM (informational)  
**Files**: All 10 orchestration commands  
**Line**: Throughout body pseudo-code

All 10 orchestration commands use `TodoWrite` in their body (e.g., to track phase progress):
```javascript
await TodoWrite({ todos: [...] });
```

`TodoWrite` is a real Claude Code deferred tool (confirmed present in the deferred tool list). However, none of the 10 commands declare it in their `allowed-tools` frontmatter. This means:
1. Claude Code may not grant the model permission to call `TodoWrite` when executing these commands
2. The progress-tracking described in each command may silently fail

This is lower priority than `SlashCommand` because `TodoWrite` is a real tool — it just needs to be declared.

**Suggested fix**: Add `TodoWrite` to the `allowed-tools` list in all 10 orchestration commands.

---

### M3 — Stale agent name references in skill bodies

**Severity**: MEDIUM  
**Files**: `skills/development/code-reviewer/SKILL.md`, `skills/security/dependency-auditor/SKILL.md`

`code-reviewer/SKILL.md` instructs users to:
> "Invoke **@code-reviewer** sub-agent for detailed explanation"

But `@code-reviewer` was renamed to `@config-safety-reviewer` in v2.5. The referenced agent no longer exists by that name. A user following the skill's guidance will get "agent not found."

`dependency-auditor/SKILL.md` references `@architect sub-agent` which was renamed to `@systems-architect` in v2.5.

**Suggested fix**: Update both skills to reference the current agent names: `@config-safety-reviewer` and `@systems-architect`.

---

### M4 — `debt-analysis.md` significantly underdeveloped

**Severity**: MEDIUM  
**File**: `commands/quality/debt-analysis/debt-analysis.md`

This command is 65 lines total, while every other orchestration command is 700–1100+ lines. It consists of a brief 3-paragraph Phase 1 description with an example output block — no actual agent prompt templates, no output format section, no JavaScript pseudo-code showing how phases chain together, and no numbered steps. The quality is inconsistent with the rest of the orchestration command suite.

Scored: 62/100 (missing output format −10, no numbered phase steps −10, underdeveloped body −5, invalid tool −3, vague −10).

---

## Recommendations by Priority

### Immediate (before next release)

1. **Fix `config-safety-reviewer.md`** — Rewrite body to match name/description. Existing body is a liability: users trusting the agent name for config safety will get a generic code reviewer.

2. **Remove or create missing command files** — `docs-gen.md` and `test-gen.md` are documented features that don't exist. Either create them or remove references from CLAUDE.md.

3. **Deduplicate the 5 command file pairs** — Remove the obsolete aliases (`todo-check`, `todo-add`, `prompt-run`, `whats-next`, `prompt-create`). Keep the canonical names introduced in v2.7.

4. **Remove `SlashCommand` from all `allowed-tools`** — It is not a real tool. Replace the integration pattern with `TodoWrite` declarations.

### Short-term (next minor version)

5. **Add `TodoWrite` to `allowed-tools`** in all 10 orchestration commands.

6. **Update stale agent names in skills** — `@code-reviewer` → `@config-safety-reviewer`, `@architect` → `@systems-architect`.

7. **Update the 3 agent README files** that still reference v2.4 names (`@code-reviewer`, `@debugger`, `@architect`).

8. **Expand `debt-analysis.md`** to match the quality level of other orchestration commands.

### Low priority

9. **Reduce vague quantifiers** throughout. Most common offenders: "comprehensive", "various", "multiple", "robust", "detailed". These appear 3–6 times per artifact on average.

10. **Add `name:` to `review.md` frontmatter** — it's the only command missing this field.

11. **Fix JS pseudo-code syntax error** in `incident-response.md` line 712–713.

---

## What This Repo Gets Right

- **Agents**: Seven of eight are high quality (92–96). Good examples, clear numbered workflows, appropriate tool declarations, well-matched `model: inherit`.
- **Skills**: All eight skills are solid (84–93). Good trigger descriptions, multiple examples, appropriate tool scoping (skills correctly avoid Write/Edit where not needed).
- **Core workflow commands**: `scaffold`, `review`, `add-to-todos`, `check-todos`, `run-prompt`, `create-prompt` — all clean and well-structured (82–91).
- **Security scan**: Clean. The two shell scripts are simple file-copy installers with no dangerous patterns.
- **CLAUDE.md**: Excellent repository guide. Architecture, usage patterns, and multi-agent orchestration concepts are clearly explained.
- **Orchestration depth**: The 10 orchestration commands, despite the `SlashCommand`/`TodoWrite` issues, contain genuinely sophisticated multi-agent coordination logic with detailed agent prompt templates and realistic output examples. The ideas are sound; the tool declarations need fixing.
