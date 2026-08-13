---
slug: OthmanAdi-planning-with-files
repo: OthmanAdi/planning-with-files
audited: 2026-05-13
commit_sha: HEAD
score: 91
exemplifies:
  - R04
  - R05
  - R07
  - R08
  - R16
  - R32
---

# Exemplar: OthmanAdi/planning-with-files

**Score**: 91/100  |  **Date**: 2026-05-13  |  **Commit**: `HEAD`

A 25-artifact planning skill (11 IDEs, 6 languages) that teaches LLMs to use markdown files as persistent working memory — notable for decision matrices that replace theory with specific per-situation action triggers, precise hook event semantics, and an exact output template in its status command.

## Per-rule evidence

### R04 — Description as trigger

The canonical SKILL.md description packs five distinct action conditions into one sentence, including a hard quantifier ("5+ tool calls") that gives the model an evaluable criterion rather than a subjective judgment call.

> Real quote from `skills/planning-with-files/SKILL.md:3`:
>
> ```
> Implements Manus-style file-based planning to organize and track progress on complex tasks.
> Creates task_plan.md, findings.md, and progress.md. Use when asked to plan out, break down,
> or organize a multi-step project, research task, or any work requiring 5+ tool calls.
> Supports automatic session recovery after /clear.
> ```

"5+ tool calls" is a decision criterion. A model can evaluate it against the current task; "complex tasks" cannot be evaluated.

### R05 — Body length

The canonical `skills/planning-with-files/SKILL.md` is 278 lines — well inside the 500-line ceiling. Coverage is multiplied across 11 IDEs and 6 languages by syncing from a single canonical source via `scripts/sync-ide-folders.py`, keeping each IDE variant near the same size rather than growing them independently.

### R07 — Scope note when related skills exist

The "When to Use This Pattern" section explicitly names skip conditions, preventing the skill from loading planning overhead on every interaction.

> Real quote from `skills/planning-with-files/SKILL.md:185-197`:
>
> ```markdown
> ## When to Use This Pattern
>
> **Use for:**
> - Multi-step tasks (3+ steps)
> - Research tasks
> - Building/creating projects
> - Tasks spanning many tool calls
> - Anything requiring organization
>
> **Skip for:**
> - Simple questions
> - Single-file edits
> - Quick lookups
> ```

The "Skip for" list is the R07 pass. Without it, the skill loads its full 278-line body on single-file edits.

### R08 — Patterns over theory

The skill provides three immediately-actionable decision tools rather than abstract advice: a read/write decision matrix keyed to specific situations, a 3-strike error protocol with per-attempt instructions, and an anti-patterns table with "Do Instead" columns.

> Real quote from `skills/planning-with-files/SKILL.md:162-171` (Read vs Write Decision Matrix):
>
> ```markdown
> | Situation | Action | Reason |
> |-----------|--------|--------|
> | Just wrote a file | DON'T read | Content still in context |
> | Viewed image/PDF | Write findings NOW | Multimodal → text before lost |
> | Browser returned data | Write to file | Screenshots don't persist |
> | Starting new phase | Read plan/findings | Re-orient if context stale |
> | Error occurred | Read relevant file | Need current state to fix |
> | Resuming after gap | Read all planning files | Recover state |
> ```

> Real quote from `skills/planning-with-files/SKILL.md:138-160` (3-Strike Error Protocol):
>
> ```
> ATTEMPT 1: Diagnose & Fix
>   → Read error carefully
>   → Identify root cause
>   → Apply targeted fix
>
> ATTEMPT 2: Alternative Approach
>   → Same error? Try different method
>   → Different tool? Different library?
>   → NEVER repeat exact same failing action
>
> ATTEMPT 3: Broader Rethink
>   → Question assumptions
>   → Search for solutions
>   → Consider updating the plan
>
> AFTER 3 FAILURES: Escalate to User
>   → Explain what you tried
>   → Share the specific error
>   → Ask for guidance
> ```

Each row or step gives one situation → one action. "Handle errors well" gives none.

### R16 — Define output format

The status command specifies an exact output template with literal placeholder tokens, leaving no structural ambiguity about spacing, ordering, or which fields to show.

> Real quote from `commands/status.md:22-37`:
>
> ```
> ## Output Format
>
> ```
> 📋 Planning Status
>
> Current: Phase {N} of {total} ({percent}%)
> Status: {status_icon} {status_text}
>
>   {icon} Phase 1: {name}
>   {icon} Phase 2: {name} ← you are here
>   {icon} Phase 3: {name}
>   ...
>
> Files: task_plan.md {✓|✗} | findings.md {✓|✗} | progress.md {✓|✗}
> Errors logged: {count}
> ```
> ```

The empty-state path at `commands/status.md:39-45` covers R17 as a byproduct — "If No Planning Files Exist" gives a specific fallback output rather than leaving the model to invent one.

### R32 — Block on PreToolUse, advise on PostToolUse

The `PreToolUse` hook injects plan context before a tool call fires — where it can shape tool selection. The `PostToolUse` hook fires after a write is already committed and correctly limits itself to an advisory ("Update progress.md with what you just did").

> Real quote from `skills/planning-with-files/SKILL.md:16-20` (PostToolUse — advisory only):
>
> ```yaml
> PostToolUse:
>   - matcher: "Write|Edit"
>     hooks:
>       - type: command
>         command: "if [ -f task_plan.md ]; then echo '[planning-with-files] Update progress.md
>           with what you just did. If a phase is now complete, update task_plan.md status.'; fi"
> ```

> Real quote from `skills/planning-with-files/SKILL.md:11-15` (PreToolUse — injects plan state before action):
>
> ```yaml
> PreToolUse:
>   - matcher: "Write|Edit|Bash|Read|Glob|Grep"
>     hooks:
>       - type: command
>         command: "if [ -f task_plan.md ]; then ... echo '---BEGIN PLAN DATA---';
>           cat task_plan.md 2>/dev/null | head -30; echo '---END PLAN DATA---'; fi"
> ```

PostToolUse says "do this next"; PreToolUse says "here is what to consider now." Correct event semantics for each hook stage.

## Worth adopting

**Pattern: Hash-attested injection gate.** Evidence: `skills/planning-with-files/SKILL.md:253-255`. The skill stores a SHA-256 of `task_plan.md` after user approval; hooks compare the live hash on every firing and emit `[PLAN TAMPERED — injection blocked]` on mismatch, preventing the file from reaching model context. Why it would be a useful rule: When a hook auto-injects a user-editable file on every firing, any tool that writes to that file (search results, browser output) becomes an amplified injection surface. A hash gate is implementable in POSIX shell with no dependencies and requires zero changes to skill content. Candidate rule form: "**Attest auto-injected files with a content hash.** If a PreToolUse or UserPromptSubmit hook injects a user-editable file on every firing, store a SHA-256 at approval time and block injection on hash mismatch. Without this, any tool that writes to the file — including search and browser tools — can poison the injection surface on every subsequent tool call."

**Pattern: Labeled delimiter framing for injected context.** Evidence: `skills/planning-with-files/SKILL.md:249`. Injected plan content is wrapped in `---BEGIN PLAN DATA---` / `---END PLAN DATA---` markers with an explicit note that content is structured data. Why it would be a useful rule: LLMs conflate injected file content with instructions unless the boundary is named. Delimiters reduce (but do not eliminate) that conflation. Candidate rule form: "**Wrap auto-injected content in named data delimiters.** Use `---BEGIN <NAME> DATA---` / `---END <NAME> DATA---` markers and prefix a note that content is structured data. Without delimiters, injected file content is indistinguishable from hook instructions in the model's attention."
