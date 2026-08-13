---
slug: fivetaku-fablize
repo: fivetaku/fablize
audited: 2026-06-27
commit_sha: d338460454c340736c16648df0920ca9eea6acea
score: 95
exemplifies:
  - R04
  - R05
  - R06
  - R08
  - R27
  - R30
---

# Exemplar: fivetaku/fablize

**Score**: 95/100  |  **Date**: 2026-06-27  |  **Commit**: `d338460454c340736c16648df0920ca9eea6acea`

A four-artifact Claude Code plugin (skill + command + hook config + plugin manifest) that enforces completion, evidence, and verification as procedure; the skill scores 96/100 and the hook config scores 100/100, making the artifact set a strong reference for trigger design, runnable examples, and portable path handling.

## Per-rule evidence

### R04 — Description is a trigger, not a summary

The SKILL.md frontmatter description packs five independent trigger phrases covering distinct user situations — session type ("multi-step task"), work style ("long autonomous work"), task class ("debugging or root-cause investigation"), output type ("building render/executable artifacts"), and explicit user vocabulary ("when the user says 'fablize', 'see it through', 'verify as you go', 'split into goals'").

> From `skills/fablize/SKILL.md:3`:
>
> ```
> description: A harness that makes Opus (or any Claude model) behave like Fable — it enforces
> seeing a task through to the end, with evidence and verification, as procedure. Use when
> starting a multi-step task (2+ sequential stories), long autonomous work, debugging or
> root-cause investigation, building render/executable artifacts (HTML, SVG, games, charts), or
> when the user says "fablize", "see it through", "verify as you go", "split into goals".
> ```

A mediocre description would stop at "A harness that makes Opus behave like Fable." This one lists five separate trigger phrases, each matching a distinct real query shape — the multi-part list is what lets Claude pick the skill reliably from diverse user phrasings.

### R05 — Under 500 lines

The SKILL.md covers four distinct task disciplines (multi-story loop, deep investigation, render verification, capability escalation) plus a self-onboarding §0 and an always-on install instruction, all in 70 lines. No padding, no repetition of the principle after its first statement.

> From `skills/fablize/SKILL.md:1-70` (full file is 70 lines):
>
> ```
> ## 0. First run — set up automatically (once)
> ## 1. Multi-story loop (2+ sequential stories)
> ## 2. Deep investigation (debugging / unknown cause / review)
> ## 3. Verification grounding (render/executable artifacts — always)
> ## 3-1. Working style (always)
> ## 4. At the capability ceiling (escalate)
> ## Install (always-on, optional)
> ```

Four behavioral disciplines, one onboarding flow, one install note, 70 lines. The section titles signal what's inside without restating it in the body — every line is doing work.

### R06 — Code examples must be runnable

Every section that requires shell execution gives actual commands with real argument names, not placeholders or pseudocode. The multi-story loop in §1 shows the full goals.py lifecycle — create, next, checkpoint, status — with real flag names and a note on what the engine refuses.

> From `skills/fablize/SKILL.md:39-46`:
>
> ```bash
> python3 ${CLAUDE_PLUGIN_ROOT}/scripts/goals.py create --brief "<summary>" \
>   --goal "title::verifiable objective" --goal "title::..."   # the last goal must be a verification story
> python3 ${CLAUDE_PLUGIN_ROOT}/scripts/goals.py next         # activate a story + handoff
> # ... work that story only ...
> python3 ${CLAUDE_PLUGIN_ROOT}/scripts/goals.py checkpoint --id G001 --status complete --evidence "<concrete evidence>"
> # the final story is a verification gate: --verify-cmd "<command>" --verify-evidence "<result>" are required
> python3 ${CLAUDE_PLUGIN_ROOT}/scripts/goals.py status       # first command when resuming
> ```

The checkpoint call shows the real flags (`--id`, `--status`, `--evidence`), the constraint that `complete` requires non-empty evidence, and the special requirement on the final story — all in six lines. Pseudocode would omit the flags and the enforcement notes, leaving Claude to guess the actual invocation.

### R08 — Patterns over theory

The SKILL.md is organized by task situation, not by principle. Each of the four numbered sections names a specific task class ("Multi-story loop", "Deep investigation", "Verification grounding", "At the capability ceiling") and gives a concrete action sequence for that class, not a general description of why the discipline matters.

> From `skills/fablize/SKILL.md:52-57`:
>
> ```
> ## 3. Verification grounding (render/executable artifacts — always)
>
> For artifacts whose correctness only shows when run (HTML, SVG, games, UI, charts), follow
> `${CLAUDE_PLUGIN_ROOT}/packs/verification-grounding-pack.txt`: run it in the real renderer →
> observe the actual output → fix what the observation reveals → re-run. A static parse confirms
> well-formed, not correct.
> ```

The final sentence ("A static parse confirms well-formed, not correct") names the failure mode of skipping this step without restating the abstract principle. The trigger condition ("artifacts whose correctness only shows when run") and the concrete anti-example make this actionable rather than advisory.

### R27 — Event names are case-sensitive

The hooks.json uses `UserPromptSubmit`, `PostToolUse`, and `Stop` — all three in the exact casing Claude Code expects. No lowercase or ALL_CAPS variants.

> From `hooks/hooks.json:3,26,37`:
>
> ```json
> "UserPromptSubmit": [
>   ...
> ],
> "PostToolUse": [
>   ...
> ],
> "Stop": [
>   ...
> ]
> ```

The hooks.json scored 100/100. Getting three distinct event types right is the minimum bar; this is notable because `PostToolUse` is the most commonly miscased event (seen as `post_tool_use` or `postToolUse` in the wild).

### R30 — Use `${CLAUDE_PLUGIN_ROOT}` for paths

Every script reference in both hooks.json and SKILL.md uses `${CLAUDE_PLUGIN_ROOT}` — no hardcoded absolute paths, no `~/.claude/plugins/fablize/` variants. The pattern holds consistently across the hook config and the skill's inline bash examples.

> From `hooks/hooks.json:9,19,31,41`:
>
> ```json
> "command": "${CLAUDE_PLUGIN_ROOT}/hooks/router.sh"
> "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/gate_prompt.py\""
> "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/gate_post_tool.py\""
> "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/gate_stop.py\""
> ```

> From `skills/fablize/SKILL.md:26,29,43,53,68`:
>
> ```bash
> bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh <local|global>
> python3 ${CLAUDE_PLUGIN_ROOT}/scripts/goals.py create ...
> ${CLAUDE_PLUGIN_ROOT}/packs/investigation-protocol.txt
> ${CLAUDE_PLUGIN_ROOT}/packs/verification-grounding-pack.txt
> bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh
> ```

Nine references across two artifacts, all portable. A plugin failing R30 typically hardcodes the path in one place (the hook config) while using `${CLAUDE_PLUGIN_ROOT}` in the skill — the consistency across both files here is what makes it exemplary.

## Worth adopting

**Pattern: Self-onboarding on first skill invocation.** Evidence: `skills/fablize/SKILL.md:12-33` (§0). The skill includes a "first run" section that checks for an onboarding state file (`~/.fablize/progress.json`) and, when absent, asks a single question, runs setup, and continues with the user's original task — all without requiring the user to run `/setup` first. Why it would be a useful rule: plugin authors currently treat setup as a prerequisite the user must discover; a rule requiring skills to declare a first-run check pattern would eliminate the "installed but not working" gap class that appears in the majority of plugin bug reports.

**Pattern: Escalation anti-trigger guard.** Evidence: `skills/fablize/SKILL.md:65` ("never trigger it from risk/deep classification alone — that over-escalates simple high-risk tasks (false-escalate)"). The §4 escalation path explicitly names a false-positive class (high-risk classification triggering escalation for tasks that are merely risky, not capability-limited) and prohibits it. Why it would be a useful rule: without naming the false-escalate failure mode, authors writing escalation clauses default to "escalate when hard" rather than "escalate when capability-limited", producing over-delegation that costs tokens on routine tasks.
