# Audit: LigphiDonk/Oh-my--paper

**NL Score**: 65/100
**Security**: REVIEW
**Audited**: 2026-04-30
**Artifacts**: 63 canonical (10 agents, 16 commands, 36 skills, 1 CLAUDE.md) + 34-file skill mirror

---

## NL Score Summary

| Category | Files | Avg Score | Range | Key Issues |
|----------|-------|-----------|-------|------------|
| Agents — templates | 5 | 30/100 | 30–30 | No `name`, no `description` frontmatter, no `model`, no `examples` |
| Agents — plugin | 5 | 30/100 | 30–30 | Same as template agents; plugin versions are near-identical copies |
| Commands — templates | 7 | 60/100 | 60–60 | No `name` frontmatter; well-structured numbered steps, good AskUserQuestion gates |
| Commands — plugin | 9 | 61/100 | 55–65 | No `name` frontmatter; `setup.md` gets −5 extra for inline settings.json mutation |
| Skills — src-tauri | 35 | 77/100 | 62–88 | Rich YAML frontmatter from dr-claw upstream; isolated weak spots listed below |
| Skills — mirror (skills/) | 34 | 77/100 | 62–88 | Structural duplicate of src-tauri; same per-file scores; duplication itself is a cross-component finding |
| CLAUDE.md (templates/research) | 1 | 65/100 | — | No frontmatter registration; good content but role is ambiguous CLAUDE.md vs agent file |

**Canonical weighted average** (63 unique files, mirror excluded): **65/100**

### Per-agent scores

| File | Score | Missing |
|------|-------|---------|
| templates/harness/agents/reviewer.md | 30 | name, description, model, examples |
| templates/harness/agents/experiment-driver.md | 30 | name, description, model, examples |
| templates/harness/agents/literature-scout.md | 30 | name, description, model, examples |
| templates/harness/agents/conductor.md | 30 | name, description, model, examples |
| templates/harness/agents/paper-writer.md | 30 | name, description, model, examples |
| plugins/oh-my-paper/agents/reviewer.md | 30 | name, description, model, examples |
| plugins/oh-my-paper/agents/experiment-driver.md | 30 | name, description, model, examples |
| plugins/oh-my-paper/agents/literature-scout.md | 30 | name, description, model, examples |
| plugins/oh-my-paper/agents/conductor.md | 30 | name, description, model, examples |
| plugins/oh-my-paper/agents/paper-writer.md | 30 | name, description, model, examples |

### Per-command scores

| File | Score | Notes |
|------|-------|-------|
| templates/harness/commands/idea-forge.md | 60 | 5 numbered steps, AskUserQuestion gates, missing `name` |
| templates/harness/commands/research-plan.md | 60 | 3 steps, omp_memory_sync output, missing `name` |
| templates/harness/commands/experiment-loop.md | 60 | 4 steps, clear loop logic, missing `name` |
| templates/harness/commands/review-gate.md | 60 | 4 steps, uses reviewer agent, missing `name` |
| templates/harness/commands/survey-blitz.md | 60 | 4 steps, codex dispatch, missing `name` |
| templates/harness/commands/paper-sprint.md | 60 | 3 steps, per-section dispatch, missing `name` |
| templates/harness/commands/delegate.md | 60 | 5 steps, context injection pattern, missing `name` |
| plugins/oh-my-paper/commands/plan.md | 60 | Mirror of research-plan with /omp: prefix, missing `name` |
| plugins/oh-my-paper/commands/survey.md | 65 | PDF OCR workflow, 5 steps, extra polish; missing `name` |
| plugins/oh-my-paper/commands/setup.md | 55 | Inline Node.js mutates .claude/settings.json; missing `name` |
| plugins/oh-my-paper/commands/review.md | 60 | 4 steps, reviewer agent, missing `name` |
| plugins/oh-my-paper/commands/write.md | 60 | Named skill references, missing `name` |
| plugins/oh-my-paper/commands/experiment.md | 60 | 4 steps, /codex:rescue, missing `name` |
| plugins/oh-my-paper/commands/delegate.md | 60 | Polling loop (seq 1 60), missing `name` |
| plugins/oh-my-paper/commands/ideate.md | 65 | 6 steps, OCR paper reading, AskUserQuestion; missing `name` |
| plugins/oh-my-paper/commands/sync.md | 65 | 6 steps, force-sync pipeline docs; missing `name` |

### Notable skill scores

| File | Score | Notes |
|------|-------|-------|
| src-tauri/resources/skills/ml-paper-writing/SKILL.md | 88 | 50 templates, 3 examples, NeurIPS/ICML/ICLR coverage |
| src-tauri/resources/skills/inno-grant-proposal/SKILL.md | 85 | NSF/NIH/NSFC formats, 5 phases, full examples |
| src-tauri/resources/skills/inno-idea-eval/SKILL.md | 85 | Multi-persona eval, full JSON schemas, novelty verification |
| src-tauri/resources/skills/inno-pipeline-planner/SKILL.md | 82 | Interactive planning, generates research_brief.json |
| src-tauri/resources/skills/inno-idea-generation/SKILL.md | 82 | SCAMPER/SWOT/Mind Map, 2 full examples, subagent strategy |
| src-tauri/resources/skills/inno-paper-writing/SKILL.md | 82 | IEEE/ACM format, 2 examples |
| src-tauri/resources/skills/inno-code-survey/SKILL.md | 82 | Repo acquisition + code survey, Phase A+B |
| src-tauri/resources/skills/inno-experiment-dev/SKILL.md | 82 | Implementation plan + ML dev iteration |
| src-tauri/resources/skills/research-idea-convergence/SKILL.md | 82 | Interactive selection, user checkpoint pattern |
| src-tauri/resources/skills/codex-dispatch/SKILL.md | 70 | --approval-mode full-auto (security concern) |
| src-tauri/resources/skills/claude-code-dispatch/SKILL.md | 72 | --dangerously-skip-permissions (security concern) |
| src-tauri/resources/skills/research-news/SKILL.md | 72 | Hardcoded path server/scripts/research-news/ |
| src-tauri/resources/skills/inno-rclone-to-overleaf/SKILL.md | 68 | Personalized content ("Eason's Workflow Requirements") |
| src-tauri/resources/skills/research-literature-trace/SKILL.md | 68 | Missing description; minimal content |
| src-tauri/resources/skills/research-pipeline-planner/SKILL.md | 65 | Minimal frontmatter; non-standard tool `update_pipeline` |
| src-tauri/resources/skills/research-paper-handoff/SKILL.md | 65 | Missing description; near-empty content |
| src-tauri/resources/skills/research-experiment-driver/SKILL.md | 65 | Missing description; minimal frontmatter |
| src-tauri/resources/skills/bioinformatics-init-analysis/SKILL.md | 62 | Description field is the title repeated as Markdown heading |

---

## Security Scan

**Verdict: REVIEW** — 3 HIGH findings, 1 MEDIUM. No CRITICAL patterns (no curl-pipe-sh, no eval with variables, no credential exfiltration, no reverse shells). The HIGH findings are permission-bypass instructions in SKILL.md files and an inline config-mutation in a command.

### HIGH

**[SEC-H1]** `src-tauri/resources/skills/claude-code-dispatch/SKILL.md`
- **Pattern**: `--dangerously-skip-permissions` passed to `claude` CLI
- **Evidence**: Skill instructs agents to invoke `claude --dangerously-skip-permissions` when dispatching tasks. Any agent that reads and follows this skill will bypass Claude Code's tool-use permission checks for the entire session.
- **Risk**: Maliciously crafted task inputs could exploit unrestricted tool access to read/write arbitrary files, execute shell commands, or exfiltrate data without per-tool confirmation.
- **Fix**: Replace with `--permission-mode default` or omit the flag and document that users must opt-in to permission bypass explicitly.

**[SEC-H2]** `src-tauri/resources/skills/codex-dispatch/SKILL.md`
- **Pattern**: `--approval-mode full-auto` passed to `codex` CLI
- **Evidence**: Skill instructs agents to invoke Codex with `--approval-mode full-auto`, which disables all interactive approval prompts during code execution.
- **Risk**: Same class as SEC-H1. A compromised or confused task description can cause Codex to execute arbitrary code modifications without any human checkpoint.
- **Fix**: Remove the flag or use `--approval-mode suggest`. Document the tradeoff explicitly if automation is intentional.

**[SEC-H3]** `plugins/oh-my-paper/commands/setup.md`
- **Pattern**: Inline Node.js script writes to `.claude/settings.json`
- **Evidence**: Step 3 of setup.md embeds a multi-line `node -e "..."` invocation that reads the existing `.claude/settings.json`, injects a `SessionStart` hook entry pointing to `${CLAUDE_PLUGIN_ROOT}/scripts/on-session-start.mjs`, and overwrites the file. This self-modifies Claude Code's settings from within a command execution.
- **Risk**: (a) The hook script `on-session-start.mjs` runs on every future session start without further user confirmation, making it a persistent side-effect of running `/omp:setup`. (b) The inline script does not validate the JSON it reads; malformed settings.json will throw an unhandled exception. (c) `${CLAUDE_PLUGIN_ROOT}` interpolated into a shell `node -e` call is an injection vector if the path contains shell metacharacters.
- **Fix**: Register the hook in `hooks.json` (already present in the plugin at `plugins/oh-my-paper/hooks/hooks.json`) and remove the inline Node.js block from setup.md. The hook is already declared in hooks.json — setup.md is redundantly duplicating it via a dangerous side-channel.

### MEDIUM

**[SEC-M1]** `plugins/oh-my-paper/hooks/hooks.json`
- **Pattern**: Three hooks registered (SessionStart, Stop, PostToolUse:Write) running unreviewed Node.js scripts
- **Evidence**: `on-session-start.mjs`, `on-task-complete.mjs`, `on-stage-transition.mjs` are referenced but their source was not accessible during this audit. Hook scripts run automatically and are not subject to per-invocation user approval.
- **Risk**: Without reviewing script contents, data exfiltration, credential access, or persistent state mutation cannot be ruled out.
- **Fix**: Publish the hook scripts in the repo with clear documentation of what each does. Add input validation (hook receives tool-use data that could contain attacker-controlled content in multi-user deployments).

---

## Bugs

Bugs are findings that break registration or cause referential failures. All require fixes before the plugin is usable.

**[BUG-01]** All 10 agent files are missing YAML frontmatter entirely.

Claude Code agent registration requires at minimum a `name` and `description` field in YAML frontmatter (`---\nname: ...\ndescription: ...\n---`). Without this, agents cannot be discovered or invoked by Claude Code's plugin registry. Affected files:

- `templates/harness/agents/reviewer.md`
- `templates/harness/agents/experiment-driver.md`
- `templates/harness/agents/literature-scout.md`
- `templates/harness/agents/conductor.md`
- `templates/harness/agents/paper-writer.md`
- `plugins/oh-my-paper/agents/reviewer.md`
- `plugins/oh-my-paper/agents/experiment-driver.md`
- `plugins/oh-my-paper/agents/literature-scout.md`
- `plugins/oh-my-paper/agents/conductor.md`
- `plugins/oh-my-paper/agents/paper-writer.md`

**Fix**: Add frontmatter to each agent. Minimum viable:
```yaml
---
name: reviewer
description: Peer-reviews a research paper draft against declared contributions and experiment results.
model: claude-sonnet-4-5
---
```

**[BUG-02]** All 16 command files are missing the `name` frontmatter field.

Claude Code slash commands require a `name` field for the command to be registered under its intended `/name` path. All 16 commands have a `description` field but no `name`. Without `name`, the plugin manifest cannot bind the command to its invocation key.

Affected files: all 7 under `templates/harness/commands/` and all 9 under `plugins/oh-my-paper/commands/`.

**Fix**: Add `name: <command-slug>` to each command's frontmatter. Example for `idea-forge.md`:
```yaml
---
name: idea-forge
description: 生成并评估创新点，每步展示中间结果等用户参与决策
---
```

**[BUG-03]** `src-tauri/resources/skills/research-news/SKILL.md` references hardcoded path `server/scripts/research-news/`.

The skill's execution instructions reference `server/scripts/research-news/` as if it exists in the user's working directory. This path is an upstream project artifact that will not be present in a standard Oh My Paper install. Agents following this skill will fail to find the referenced scripts.

**Fix**: Either bundle the script in the skill directory and reference it as `.claude/skills/research-news/scripts/...`, or remove the hardcoded path and describe the workflow without filesystem dependencies.

**[BUG-04]** `src-tauri/resources/skills/research-pipeline-planner/SKILL.md` lists `update_pipeline` as an available tool.

`update_pipeline` is not a standard Claude Code tool. The skill declares it in its tools list, which will cause agents to attempt to call a tool that does not exist, resulting in a tool-not-found error.

**Fix**: Remove `update_pipeline` from the tools list and replace with the actual mechanism for pipeline updates (likely file writes via the `Write` tool to `.pipeline/tasks/tasks.json`).

---

## Security Fixes

**[SECFIX-01]** Remove `--dangerously-skip-permissions` from `claude-code-dispatch/SKILL.md`.

This flag disables all per-tool permission prompts for the delegated session. Replace with `--permission-mode default` or omit. If users need to enable full-auto for specific workflows, document the flag as an opt-in they must add manually, not as the default the skill instructs.

**[SECFIX-02]** Remove `--approval-mode full-auto` from `codex-dispatch/SKILL.md`.

Same class of risk as SECFIX-01. The Codex CLI `--approval-mode suggest` mode still enables automation while preserving checkpoints for destructive operations. Use that instead, or require an explicit user decision before escalating to full-auto.

**[SECFIX-03]** Remove the inline `node -e` settings mutation from `setup.md`.

The hook is already registered in `plugins/oh-my-paper/hooks/hooks.json`. The inline Node.js in setup.md is redundant and unsafe. Delete the Node.js block from setup.md. If the setup command needs to verify that the hook is active, it should read hooks.json and inform the user, not mutate settings.json.

**[SECFIX-04]** Publish and document the three hook scripts.

`on-session-start.mjs`, `on-task-complete.mjs`, and `on-stage-transition.mjs` are referenced in hooks.json but their source was not present in the audited tree. These scripts run with full Claude Code tool access on every session start, task stop, and Write event. Publish the scripts, add a brief docstring to each explaining what data they read/write, and ensure they do not make network calls or access credentials.

---

## Quality Issues

**[Q-01]** All 10 agents lack `model` specification.

Without a `model` field, Claude Code will use the user's default model for agent invocations. The conductor/orchestrator agent dispatches multiple sub-agents and benefits from a capable model (Sonnet or Opus); using Haiku as a default would degrade orchestration quality. Each agent should declare an explicit model appropriate to its task complexity.

Suggested assignments:
- `conductor.md` → `claude-sonnet-4-6` (orchestration requires reasoning)
- `reviewer.md` → `claude-sonnet-4-6` (peer review requires depth)
- `experiment-driver.md` → `claude-sonnet-4-6` (code generation)
- `literature-scout.md` → `claude-haiku-4-5-20251001` (mechanical search, cost-sensitive)
- `paper-writer.md` → `claude-sonnet-4-6` (academic writing)

**[Q-02]** All 10 agents lack `examples` blocks.

Agents without examples cannot be reliably invoked by Claude Code's routing layer. Examples also serve as the primary regression surface for behavioral changes. Each agent should include at least one `<example>` block showing a representative task input and expected output artifact.

**[Q-03]** `src-tauri/resources/skills/bioinformatics-init-analysis/SKILL.md` has a placeholder description.

The `description` field contains only `# bioinformatics-init-analysis` — a Markdown heading repeated as the description. This provides no information to agents choosing skills and will not match any meaningful semantic query.

**Fix**: Replace with a real description, e.g., `Initialize a bioinformatics analysis pipeline: QC raw reads, align to reference, call variants, and produce a summary report.`

**[Q-04]** `src-tauri/resources/skills/research-experiment-driver/SKILL.md`, `research-paper-handoff/SKILL.md`, and `research-literature-trace/SKILL.md` are missing `description` fields.

Three skills have minimal or absent `description` frontmatter. Without descriptions, skill routing is blind for these entries.

**[Q-05]** `src-tauri/resources/skills/inno-rclone-to-overleaf/SKILL.md` contains personalized content not suitable for general distribution.

The skill includes a section titled "Eason's Workflow Requirements" listing personal preferences (specific rclone remote names, directory paths, Overleaf project IDs). This is a personal workflow fragment that was not generalized before being committed to the plugin. Users who install this skill will receive instructions tailored to a specific person's environment that will not work in their own setup.

**Fix**: Replace the personal section with parameterized placeholders (`<your-rclone-remote>`, `<your-overleaf-project-id>`) or move the personal configuration to a separate user-local file.

**[Q-06]** `src-tauri/resources/skills/inno-paper-reviewer/SKILL.md` ends with a commercial upsell for "K-Dense Web".

The final section of the skill promotes a commercial product/service ("K-Dense Web") as a recommended next step after peer review. Commercial promotions have no place in a technical skill definition and violate the separation between a neutral tool and marketing content. This will also cause downstream confusion for agents that parse the skill's output instructions as authoritative guidance.

**Fix**: Remove the commercial upsell section.

**[Q-07]** `src-tauri/resources/skills/remote-experiment/SKILL.md` has an empty `stages: []` field.

The `stages` key is present but empty, meaning the skill declares no execution stages. Agents that select skills based on stage-type matching will not route to this skill even when it is the appropriate choice.

**Fix**: Populate `stages` with the actual execution phases (e.g., `[setup, launch, monitor, collect]`).

**[Q-08]** `src-tauri/resources/skills/research-pipeline-planner/SKILL.md` has minimal frontmatter and no description.

This is a planning skill that generates `research_brief.json` and `tasks.json` — central artifacts for the entire Oh My Paper pipeline. Its low discoverability due to missing description means the orchestrator may not find it during the critical planning phase.

---

## Cross-Component

**[CC-01]** Skills are duplicated verbatim across two directories with no diff.

`src-tauri/resources/skills/` and `skills/` contain the same 34 skill files (verified by matching directory listings). Having two canonical copies creates a maintenance split: a fix applied to one copy will not propagate to the other, and agents reading from different root paths will diverge in behavior. The `src-tauri/` prefix suggests the src-tauri copy exists for a desktop app build, while `skills/` serves the Claude Code plugin. This split should be explicit.

**Fix**: Designate one as the authoritative source and either symlink the other or add a CI check that errors if they diverge. Document which path is read by which runtime.

**[CC-02]** `plugins/oh-my-paper/commands/setup.md` duplicates the SessionStart hook registration that is already declared in `plugins/oh-my-paper/hooks/hooks.json`.

The hook `on-session-start.mjs` appears in both places. At plugin install time, hooks.json registers the hook. If the user then runs `/omp:setup`, the inline Node.js in setup.md will attempt to register it a second time, potentially creating duplicate entries in `.claude/settings.json`. Claude Code's hook deduplication behavior in this scenario is not guaranteed.

**Fix**: Remove the hook registration from setup.md (see SECFIX-03). Let hooks.json be the sole registration point.

**[CC-03]** All commands reference `/codex:rescue` as a dispatch mechanism, but this command is not defined anywhere in the plugin.

`/codex:rescue`, `/codex:rescue --resume`, and `/codex:status` appear across 12 of the 16 command files as the primary agent-dispatch primitive. These commands are not defined in `plugins/oh-my-paper/commands/` or `templates/harness/commands/`. They appear to belong to a separate `codex` plugin that users must install independently, but no `README`, `INSTALL`, or plugin manifest declares this dependency.

**Fix**: Add a `dependencies` section to `plugin.json` listing the `codex` plugin as a required peer dependency, and add a prerequisite check to `/omp:setup`.

**[CC-04]** Agent personas referenced in `templates/research/CLAUDE.md` (`.claude/agents/` path) are not consistent with agent file locations in the repo (`templates/harness/agents/` and `plugins/oh-my-paper/agents/`).

The CLAUDE.md references `".claude/agents/"` as the canonical agent path. The actual agents live in `templates/harness/agents/` and `plugins/oh-my-paper/agents/`. At install time these would be copied to `.claude/agents/`, but the discrepancy makes it unclear whether the CLAUDE.md is a template to be processed at install time or a file meant to be used as-is.

---

## Recommendation

**minor revision** — The skill library (35 skills, avg 77/100) is genuinely strong and represents substantial research workflow knowledge. The command structure is coherent with good user-gating patterns. However, three blocking issues prevent this plugin from being installable as-is:

1. **All 10 agents are unregisterable** (missing `name`/`description` frontmatter — BUG-01). This is the highest-priority fix; without it, the entire agent delegation system is broken.
2. **All 16 commands lack `name` frontmatter** (BUG-02). Commands cannot be invoked by their slash-command path.
3. **Three HIGH security findings** require resolution before the plugin should be distributed to users who do not fully understand the permission implications (SECFIX-01 through SECFIX-03).

The cross-component issues (CC-01 through CC-04) are medium priority but will cause silent failures and maintenance drift if not addressed before the plugin's first stable release.

Fix the bugs and security issues; the quality of the underlying content warrants distribution once the scaffolding is corrected.
