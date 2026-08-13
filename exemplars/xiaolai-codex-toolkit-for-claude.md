---
slug: xiaolai-codex-toolkit-for-claude
repo: xiaolai/codex-toolkit-for-claude
audited: 2026-05-13
commit_sha: HEAD
score: 96
exemplifies:
  - R08
  - R09
  - R11
  - R12
  - R13
  - R17
  - R30
  - R35
---

# Exemplar: xiaolai/codex-toolkit-for-claude

**Score**: 96/100  |  **Date**: 2026-05-13  |  **Commit**: `HEAD`

A Claude Code plugin that delegates audit, implement, verify, and debug work to OpenAI Codex via MCP — notable for a clean cross-provider knowledge architecture, tight agent design, and a CLAUDE.md that reads like an operator manual.

## Per-rule evidence

### R08 — Patterns over theory

The `claude-code-conventions` skill is almost entirely schema tables, JSON/Bash code blocks, and naming patterns — no abstract explanations of _why_ conventions exist. It teaches what to do in specific situations.

> Real quote from `skills/codex-toolkit/claude-code-conventions/SKILL.md:141-162`:
>
> ```
> ## hooks.json Format
>
> ```json
> {
>   "hooks": {
>     "PostToolUse": [
>       {
>         "matcher": "Write|Edit",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format-code.sh"
>           }
>         ]
>       }
>     ]
>   }
> }
> ```
>
> Multiple hook config files are supported in the `hooks/` directory.
> ```

The skill packs 7 sections — plugin.json schema, command frontmatter, shared partial frontmatter, agent frontmatter, skill structure, hook events, and hook/MCP/marketplace formats — into 288 lines, all as runnable templates, zero prose theory.

### R09 — `<example>` blocks are mandatory

The `cross-validator` agent embeds two `<example>` blocks in its frontmatter `description` field, each with clear context and a concrete assistant response showing how the agent announces itself.

> Real quote from `agents/cross-validator.md:3-18`:
>
> ```yaml
> description: |
>   Cross-validate Codex audit findings against Claude's native knowledge of Claude Code conventions. Use after any audit command to catch false positives and hallucinated conventions.
>   <example>
>   Context: Codex returned an audit report flagging a plugin's frontmatter as invalid
>   assistant: "I'll use the cross-validator to verify these findings against Claude's native knowledge."
>   </example>
>   <example>
>   Context: User wants to double-check a Codex audit before acting on it
>   user: "Can you verify these audit findings are correct?"
>   assistant: "I'll dispatch the cross-validator agent to check each finding."
>   </example>
> ```

Both examples give a trigger situation, not just a task description — the first covers the automatic post-audit dispatch case, the second covers the explicit user-invoked case.

### R11 — Tools follow least-privilege

The `cross-validator` agent lists exactly one tool: `Read`. It reads audit reports and artifact files to verify findings — nothing else. Write, Bash, and MCP tools are absent because the agent's job is verification, not mutation.

> Real quote from `agents/cross-validator.md:13-17`:
>
> ```yaml
> model: sonnet
> color: yellow
> tools: Read
> skills:
>   - codex-toolkit:claude-code-conventions
> ```

A Read-only verifier that declares itself Read-only is the correct outcome of applying least-privilege. The `sonnet` model assignment (not `haiku`) is also correct — finding false positives in a structured audit report requires reasoning, not counting.

### R12 — Output format defined in body

The `cross-validator` body includes a complete output template: a markdown table with fixed columns, two detail sections for disputed and confirmed findings, an accuracy-rate calculation, and a conditional recommendation based on the numeric threshold.

> Real quote from `agents/cross-validator.md:65-93`:
>
> ```markdown
> ## Cross-Validation Results
>
> **Audit reviewed**: {audit report identifier}
> **Findings checked**: {N}
>
> | # | Finding | Codex Verdict | Cross-Validation | Notes |
> |---|---------|--------------|------------------|-------|
> | 1 | Missing description in X | Critical | CONFIRMED | description is indeed required |
> | 2 | Unknown field 'color' in agent | Medium | DISPUTED | 'color' IS a valid agent field |
>
> ### Disputed Findings (Codex was wrong)
> {detailed explanation for each DISPUTED finding}
>
> ### Confirmed Findings
> {count} of {total} findings confirmed accurate.
>
> ### Accuracy Rate
> {confirmed}/{total} = {pct}%
>
> ### Recommendation
> {If accuracy < 90%: "Codex knowledge may be stale. Run /codex-toolkit:refresh-knowledge --update"}
> {If accuracy >= 90%: "Codex findings are reliable for this audit."}
> ```

The conditional recommendation line (`< 90%` / `>= 90%`) turns the threshold into a concrete branch — the agent can't drift into vague "your findings seem mostly okay."

### R13 — System prompt structure: mission → steps → boundaries → format

The `cross-validator` body follows the four-layer structure exactly. Two-sentence mission ("accuracy safety net… cross-validate using YOUR native understanding"). Four numbered what-to-check sections. An explicit "What You Do NOT Check" boundary section. Then a numbered process. Then the output template.

> Real quote from `agents/cross-validator.md:21-53`:
>
> ```markdown
> ## Your Mission
>
> You are the accuracy safety net for the codex-toolkit. Codex (an OpenAI model) has no native
> knowledge of Claude Code conventions — it relies on injected knowledge that may be incomplete
> or stale. Your job is to cross-validate Codex's audit findings using YOUR native understanding
> of Claude Code.
>
> ## What You Check
> ...
> ### 1. Convention Accuracy
> ### 2. False Positives
> ### 3. Severity Accuracy
> ### 4. Missing Context
>
> ## What You Do NOT Check
>
> - Code quality, logic, or implementation correctness (that's Codex's domain)
> - Whether the plugin is well-designed (subjective judgment)
> - Anything outside Claude Code plugin conventions
>
> ## Process
>
> 1. Receive the audit report (as text or file path)
> 2. Read the `claude-code-conventions` skill for reference
> 3. For each finding: ...
> ```

The "What You Do NOT Check" section is the rarest part of R13 to see done right. Boundaries prevent scope creep without requiring negative framing throughout the body.

### R17 — Specify error paths

`commands/shared/codex-call.md` Error Handling section gives 5 numbered steps for every Codex failure mode — covering errors, empty results, and internal MCP errors — with explicit instructions not to retry and explicit fallback routing.

> Real quote from `commands/shared/codex-call.md:51-63`:
>
> ```markdown
> If ANY Codex call (ping or main) returns an error, empty result, or fails with
> `[Tool result missing due to internal error]`:
>
> 1. **Do NOT retry the same call.** MCP errors are usually transient server issues,
>    not fixable by retrying.
> 2. **Do NOT wait or poll.** If the tool returned an error, it has already failed.
> 3. **Report the failure clearly:**
>    ```
>    Codex call failed: {error message or "internal MCP error"}
>    Falling back to manual analysis.
>    ```
> 4. **Skip immediately to the calling command's Fallback section.**
> 5. **If this was a multi-step workflow** (audit→fix→verify) and a middle step fails,
>    report what completed successfully so far, then fall back for the remaining steps.
> ```

The explicit "Do NOT retry" and "Do NOT wait or poll" lines are what transforms a generic error handler into a tight contract. Every command that includes `codex-call.md` inherits this behavior without restating it.

### R30 — Use `${CLAUDE_PLUGIN_ROOT}` for paths

Every script path in `hooks/hooks.json` uses `${CLAUDE_PLUGIN_ROOT}` — no hardcoded absolute paths or relative paths from an assumed working directory.

> Real quote from `hooks/hooks.json:9-10`:
>
> ```json
> "command": "node \"${CLAUDE_PLUGIN_ROOT}/scripts/session-lifecycle-hook.mjs\" SessionStart"
> ```

All three hooks (SessionStart, SessionEnd, Stop) follow this pattern. The Stop hook also has a `"timeout": 900` — correct for a Codex review gate that may take several minutes.

### R35 — Include architecture overview

The CLAUDE.md project structure section annotates every file and directory inline, making it a navigable operator manual rather than a directory listing.

> Real quote from `CLAUDE.md:7-66`:
>
> ```markdown
> ## Project structure
>
> ```
> commands/               Slash command definitions (*.md with YAML frontmatter)
>   shared/
>     model-selection.md    Shared partial — dynamic model discovery (user-invocable: false)
>     codex-call.md         Shared partial — availability test, call pattern, thread/job handling
>     scope-parse.md        Shared partial — scope parsing, trivial check, skip patterns
>     fallback.md           Shared partial — manual fallback rules
>     plugin-discover.md    Shared partial — plugin artifact discovery for plugin directories
>   ...
> agents/
>   cross-validator.md    Cross-validate Codex audit findings against Claude's native knowledge
> skills/
>   codex-toolkit/
>     claude-code-conventions/
>       SKILL.md          Canonical Claude Code artifact schemas, injected into Codex developer-instructions
> scripts/
>   codex-preflight.sh      Model discovery script (reads ~/.codex/models_cache.json)
>   codex-runner.mjs        Background/foreground job runner (spawns codex CLI, tracks state)
>   ...
> ```
> ```

Each entry has a purpose annotation that matches what the file actually does — not a generic "utility script" placeholder. A reader can orient in under 60 seconds without opening any files.

## Worth adopting

**Pattern: Cross-provider knowledge injection with drift detection.** Evidence: `CLAUDE.md:119-129`, `commands/shared/codex-call.md:24-33`, `commands/refresh-knowledge.md`. The plugin solves an AI cross-provider knowledge gap with three coordinated layers: a skill as the single source of truth, a partial that injects the skill into the foreign model's context at call time, and a separate agent that cross-validates the foreign model's output using the host model's native knowledge. A `/refresh-knowledge` command detects drift between the skill and live docs. Why it would be a useful rule: when a command delegates to a third-party model or API that lacks native domain knowledge, this three-layer pattern (canonical skill → injection partial → verification agent) is reusable and prevents hallucinated findings from reaching users.
