---
slug: openai-codex-plugin-cc
repo: openai/codex-plugin-cc
audited: 2026-05-13
commit_sha: 807e03ac9d5aa23bc395fdec8c3767500a86b3cf
score: 93
exemplifies:
  - R04
  - R07
  - R08
  - R16
  - R18
  - R30
---

# Exemplar: openai/codex-plugin-cc

**Score**: 93/100  |  **Date**: 2026-05-13  |  **Commit**: `807e03ac`

A Claude Code plugin that wraps the Codex CLI as a set of review, rescue, and status commands — notable for skills that read like lookup tables rather than guidance prose, and for commands that pin every output field by name.

## Per-rule evidence

### R04 — Description as trigger

R04 requires 3+ specific action phrases matching real user queries, not a category summary. The `gpt-5-4-prompting` skill description packs four distinct task types into a single line, each one a concrete trigger phrase a user would actually type.

> From `plugins/codex/skills/gpt-5-4-prompting/SKILL.md:4`:
>
> ```
> description: Internal guidance for composing Codex and GPT-5.4 prompts for coding, review, diagnosis, and research tasks inside the Codex Claude Code plugin
> ```

Four task types — "coding", "review", "diagnosis", "research" — match the four `When to add blocks:` scenarios in the body, so the description and the skill content are structurally aligned rather than a generic label stapled to unrelated content.

### R07 — Scope note when related skills exist

R07 asks for an explicit scope note directing Claude to the right skill when multiple related skills exist. `codex-cli-runtime` narrows its audience to a single calling context in the second line of its body, before any other content.

> From `plugins/codex/skills/codex-cli-runtime/SKILL.md:9`:
>
> ```
> Use this skill only inside the `codex:codex-rescue` subagent.
> ```

The note names the exact caller rather than describing a category of callers. A skill that said "use for Codex invocations" would leave ambiguity about whether `review.md` or `rescue.md` should load it; this formulation eliminates that.

### R08 — Patterns over theory

R08 asks for situation-specific patterns, not abstract concepts. `codex-cli-runtime` is almost entirely a flag-dispatch table: every routing flag (`--resume`, `--fresh`, `--effort`, `--model`) gets its own conditional mapping with exact before/after values.

> From `plugins/codex/skills/codex-cli-runtime/SKILL.md:31-36`:
>
> ```
> - If the forwarded request includes `--resume`, strip that token from the task text and add `--resume-last`.
> - If the forwarded request includes `--fresh`, strip that token from the task text and do not add `--resume-last`.
> - `--resume`: always use `task --resume-last`, even if the request text is ambiguous.
> - `--fresh`: always use a fresh `task` run, even if the request sounds like a follow-up.
> - `--effort`: accepted values are `none`, `minimal`, `low`, `medium`, `high`, `xhigh`.
> - `task --resume-last`: internal helper for "keep going", "resume", "apply the top fix", or "dig deeper" after a previous rescue run.
> ```

The last entry maps natural-language follow-up phrases to a single canonical flag — this is the pattern style R08 is asking for: "in situation X, do exactly Y", with no room for the model to reason about which case applies.

### R16 — Define output format

R16 requires a report template with exact structure, not "show the results." `status.md` names every field the output table must contain, making the column set deterministic across invocations.

> From `plugins/codex/commands/status.md:11-13`:
>
> ```
> - Render the command output as a single Markdown table for the current and past runs in this session.
> - Keep it compact. Do not include progress blocks or extra prose outside the table.
> - Preserve the actionable fields from the command output, including job ID, kind, status, phase, elapsed or duration, summary, and follow-up commands.
> ```

Seven fields named, one layout (single table), one negative constraint (no prose outside). This leaves no ambiguity about what a conforming response looks like — contrasted with the audit's finding that `adversarial-review.md` and `rescue.md` describe multi-step flows without numbered steps (the −10 penalties), `status.md` shows what R16 compliance looks like in this codebase.

### R18 — `argument-hint` when command takes input

R18 requires `argument-hint` in frontmatter for commands that accept arguments. `rescue.md` goes further than a bare usage string: it enumerates every flag's accepted values inline in the hint itself, so `/help` output is self-contained.

> From `plugins/codex/commands/rescue.md:3`:
>
> ```
> argument-hint: "[--background|--wait] [--resume|--fresh] [--model <model|spark>] [--effort <none|minimal|low|medium|high|xhigh>] [what Codex should investigate, solve, or continue]"
> ```

Six accepted values for `--effort` are listed directly in the hint. The natural-language tail `[what Codex should investigate, solve, or continue]` signals that the trailing text is a free-form prompt, not a positional argument — a distinction that a bare `[task]` hint would leave implicit.

### R30 — Use `${CLAUDE_PLUGIN_ROOT}` for paths

R30 requires `${CLAUDE_PLUGIN_ROOT}` for all script paths in hooks and commands; hardcoded absolute paths break on other machines. All three hooks and every command that shells out use the variable consistently — zero hardcoded paths in the codebase.

> From `plugins/codex/hooks/hooks.json:9,19,29` (all three hook entries):
>
> ```
> "command": "node \"${CLAUDE_PLUGIN_ROOT}/scripts/session-lifecycle-hook.mjs\" SessionStart"
> "command": "node \"${CLAUDE_PLUGIN_ROOT}/scripts/session-lifecycle-hook.mjs\" SessionEnd"
> "command": "node \"${CLAUDE_PLUGIN_ROOT}/scripts/stop-review-gate-hook.mjs\""
> ```

And in the command bodies:

> From `plugins/codex/commands/review.md:44-46`:
>
> ```bash
> node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" review "$ARGUMENTS"
> ```

The variable appears in hooks, foreground command blocks, and background Bash call objects — every execution surface uses it. No exceptions were found in the audit.

---

## Worth adopting

**Pattern: `disable-model-invocation: true` + immediate `!command` for pure-dispatch commands.**
Evidence: `plugins/codex/commands/status.md:4` — `disable-model-invocation: true` followed immediately by the shell command on line 8.
Why it would be a useful rule: commands that are pure script dispatch (no reasoning needed) should bypass Claude's inference entirely; `disable-model-invocation: true` makes that intent explicit and prevents Claude from wrapping the output in commentary. The 50 Rules have no equivalent of "opt out of model invocation when the command is deterministic", which leaves authors without a vocabulary for this boundary.
