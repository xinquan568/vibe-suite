---
slug: BayramAnnakov-claude-reflect
repo: BayramAnnakov/claude-reflect
audited: 2026-05-13
commit_sha: 8dc9db43c9bfaa53b567d63f3f48385bcf3d3084
score: 99
exemplifies:
  - R04
  - R05
  - R06
  - R08
  - R14
  - R15
  - R16
  - R30
  - R33
  - R34
  - R35
---

# Exemplar: BayramAnnakov/claude-reflect

**Score**: 99/100  |  **Date**: 2026-05-13  |  **Commit**: `8dc9db43c9bfaa53b567d63f3f48385bcf3d3084`

A Claude Code plugin that implements a two-stage self-learning system (capture via hooks, process via `/reflect`). Scores 99 because nearly every artifact — SKILL.md, four commands, CLAUDE.md, hooks config — follows the spec precisely; the one-point deduction is entirely vague quantifiers in `commands/reflect.md`.

## Per-rule evidence

### R04 — Description as trigger

`SKILL.md`'s frontmatter description packs three distinct user-query scenarios into one sentence, each specific enough to fire reliably in different conversation states.

> Real quote from `SKILL.md:4`:
>
> ```
> description: Self-learning system that captures corrections during sessions and reminds users to run /reflect to update CLAUDE.md. Use when discussing learnings, corrections, or when the user mentions remembering something for future sessions.
> ```

Three trigger phrases — "discussing learnings", "corrections", "user mentions remembering something for future sessions" — map to three different conversation entry points: reviewing captured items, handling an in-session correction, and a user's explicit request to persist something. A weaker description ("Helps Claude learn from user feedback") would only cover one of them.

### R05 — Body length

`SKILL.md` is 69 lines. The main workflow lives in the four command files; the skill acts as a routing index.

> Real quote from `SKILL.md:1-25` (structure overview):
>
> ```
> # Claude Reflect - Self-Learning System
>
> A two-stage system that helps Claude Code learn from user corrections.
>
> ## How It Works
>
> **Stage 1: Capture (Automatic)**
> Hooks detect correction patterns ("no, use X", "actually...", "use X not Y") and queue them to `~/.claude/learnings-queue.json`.
>
> **Stage 2: Process (Manual)**
> User runs `/reflect` to review and apply queued learnings to CLAUDE.md files.
>
> ## Available Commands
>
> | Command | Purpose |
> |---------|---------|
> | `/reflect` | Process queued learnings with human review |
> | `/reflect --scan-history` | Scan past sessions for missed learnings |
> ...
> ```

The 69-line skill delegates implementation detail to commands; it would balloon past 500 if it inlined even one command's workflow. The table of commands serves as the cross-reference that R07 requires without duplicating body text.

### R06 — Code examples must be runnable

`SKILL.md`'s "Example Interaction" section shows a complete user/Claude exchange ending in a runnable `/reflect` invocation. `CLAUDE.md`'s "Development Commands" section gives copy-pasteable bash one-liners for every hook test scenario.

> Real quote from `SKILL.md:58-68`:
>
> ```
> ## Example Interaction
>
> ```
> User: no, use gpt-5.1 not gpt-5 for reasoning tasks
> Claude: Got it, I'll use gpt-5.1 for reasoning tasks.
>
> [Hook captures this correction to queue]
>
> User: /reflect
> Claude: Found 1 learning queued. "Use gpt-5.1 for reasoning tasks"
>         Scope: global
>         Apply to ~/.claude/CLAUDE.md? [y/n]
> ```
> ```

> Real quote from `CLAUDE.md:58-72`:
>
> ```bash
> # Test capture hook with simulated input
> echo '{"prompt":"no, use gpt-5.1 not gpt-5"}' | python3 scripts/capture_learning.py
>
> # View current learnings queue
> cat ~/.claude/learnings-queue.json
>
> # Test session extraction
> python3 scripts/extract_session_learnings.py ~/.claude/projects/[PROJECT]/*.jsonl --corrections-only
>
> # Run tests
> python -m pytest tests/ -v
>
> # Clear queue for testing
> echo "[]" > ~/.claude/learnings-queue.json
> ```

Both are executable as-written: the SKILL.md exchange uses a real command name and real file path; the CLAUDE.md snippets pass real data shapes, not `<your-data-here>` placeholders.

### R08 — Patterns over theory

`SKILL.md`'s "Correction Detection Patterns" section teaches Claude *what to listen for* using enumerated string literals, not a prose description of correction semantics.

> Real quote from `SKILL.md:39-46`:
>
> ```
> ## Correction Detection Patterns
>
> High-confidence corrections:
> - Tool rejections (user stops an action with guidance)
> - "no, use X" / "don't use Y"
> - "actually..." / "I meant..."
> - "use X not Y" / "X instead of Y"
> - "remember:" (explicit marker)
> ```

A theory-based approach would say "Detect when a user is correcting the model's previous output." This lists the actual strings that fire. Claude can match patterns without reasoning about intent.

### R14 — Steps must be numbered

Every command uses numbered steps for its core workflow. `commands/skip-reflect.md` is a three-step destructive action with a confirmation gate; every branch is labeled.

> Real quote from `commands/skip-reflect.md:11-34`:
>
> ```
> 1. If queue is empty:
>    - Output: "Queue is already empty. Nothing to skip."
>    - Exit
>
> 2. If queue has items:
>    - Show: "You are about to discard [count] learning(s). These will be lost:"
>    - List each queued item briefly (type + first 50 chars of message)
>    - Ask: "Are you sure? [y/n]"
>
> 3. If user confirms (y/yes):
>    - Clear the project queue:
>    ...
>    - Output: "Discarded [count] learnings. Queue cleared."
>
> 4. If user declines (n/no):
>    - Output: "Aborted. Run /reflect to process learnings instead."
> ```

Steps 1 and 2 guard the happy path; steps 3 and 4 are the binary confirmation branches. All four cases are numbered, which means Claude cannot re-order or skip them by accident.

### R15 — Handle empty input

Both `commands/skip-reflect.md` and `commands/view-queue.md` define exact output for the empty-queue case — not just "if empty, do nothing."

> Real quote from `commands/view-queue.md:31-39`:
>
> ```
> If queue is empty:
> ```
> ════════════════════════════════════════════════════════════
> LEARNINGS QUEUE: Empty
> ════════════════════════════════════════════════════════════
> No learnings queued. Use "remember: <learning>" to add items,
> or corrections will be auto-detected. Run /reflect to process.
> ════════════════════════════════════════════════════════════
> ```
> ```

The empty-queue output includes next-step guidance ("Use 'remember: <learning>'""), which turns a dead-end into an actionable state. The non-empty output format is defined immediately before this block (`commands/view-queue.md:14-29`), making the two cases directly comparable.

### R16 — Define output format

`commands/view-queue.md` gives a byte-for-byte output template including separator characters, bracket notation for variable parts, and a sample line.

> Real quote from `commands/view-queue.md:14-30`:
>
> ```
> **Output format:**
> ```
> ════════════════════════════════════════════════════════════
> LEARNINGS QUEUE: [N] items
> ════════════════════════════════════════════════════════════
>
> [0.85] "use gpt-5.1 not gpt-5" (use-X-not-Y) - 2 days ago
> [0.70] "perfect, that's exactly right" (positive) - 5 days ago
> [0.90] "remember: always run tests" (explicit) - just now
>
> ════════════════════════════════════════════════════════════
> Commands:
>   /reflect        - Process and save learnings
>   /skip-reflect   - Discard all learnings
> ════════════════════════════════════════════════════════════
> ```
> ```

The template pins exact field order (`[confidence] "text" (pattern) - relative-time`), exact separator style (═ vs ─), and a literal sample row. The "Formatting rules" block below it (`commands/view-queue.md:93-98`) then specifies precision ("Always show 2 decimal places `[0.85]`"), truncation ("First 50 chars, add '...'"), and fallback values ("If patterns field is empty, show `(auto)` or `(explicit)`"). This leaves nothing to interpretation.

### R30 — Use `${CLAUDE_PLUGIN_ROOT}` for paths

All four hook script references in `hooks/hooks.json` use `${CLAUDE_PLUGIN_ROOT}` — not `./`, not `~/`, not an absolute path.

> Real quote from `hooks/hooks.json:9,15,23,32`:
>
> ```json
> "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/capture_learning.py\""
> "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/check_learnings.py\""
> "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/post_commit_reminder.py\""
> "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/session_start_reminder.py\""
> ```

Four hooks, four consistent references. The repo also documents this convention in CLAUDE.md's cross-component notes ("skip-reflect.md and reflect-skills.md consistently use `${CLAUDE_PLUGIN_ROOT}`") and flags the one command that deviates as a quality issue.

### R33 + R34 + R35 — Build/run, test command, architecture overview

`CLAUDE.md` satisfies all three in a single "Development Commands" block immediately followed by an architecture section.

> Real quote from `CLAUDE.md:57-73` (development commands):
>
> ```bash
> # Test capture hook with simulated input
> echo '{"prompt":"no, use gpt-5.1 not gpt-5"}' | python3 scripts/capture_learning.py
>
> # View current learnings queue
> cat ~/.claude/learnings-queue.json
>
> # Run tests
> python -m pytest tests/ -v
>
> # Clear queue for testing
> echo "[]" > ~/.claude/learnings-queue.json
> ```

> Real quote from `CLAUDE.md:12-19` (architecture):
>
> ```
> .claude-plugin/plugin.json  → Plugin manifest, points to hooks
> hooks/hooks.json            → Hook definitions (PreCompact, PostToolUse)
> scripts/                    → Python scripts for hooks and extraction
> scripts/lib/                → Shared utilities (reflect_utils.py)
> scripts/legacy/             → Deprecated bash scripts (for reference)
> commands/*.md               → Skill definitions for /reflect, /reflect-skills, /skip-reflect, /view-queue
> SKILL.md                    → Context provided when plugin is invoked
> tests/                      → Test suite (pytest)
> ```

Build commands are real invocations with real data shapes; architecture is a one-line-per-component map rather than prose. Both avoid the "descriptive README" trap (R38).

## Worth adopting

**Pattern: Mandatory checkpoint gate before multi-phase workflow.** Evidence: `commands/reflect.md:82-133`. The command requires Claude to call `TodoWrite` and populate the full task list *before* doing any work, enforcing this with a bold `DO NOT PROCEED` sentinel. Why it would be a useful rule: Multi-step commands with 10+ phases are common; without a checkpoint mechanism, Claude routinely skips or reorders steps when context grows long. A rule mandating TodoWrite initialization for commands with 7+ numbered steps would reduce silent phase-skipping without burdening simpler commands.

**Pattern: Explicit anti-pattern warning for known executor quirks.** Evidence: `commands/reflect.md:451-453`. The command documents `WARNING: Do NOT combine these into a single compound command with $(...)`. Claude Code's bash executor mangles subshell syntax — run each command individually.` Why it would be a useful rule: Executor-specific syntax restrictions differ from general Bash behavior. Codifying "warn about known executor quirks inline, adjacent to the affected step" would prevent silent failures that are otherwise hard to diagnose.
