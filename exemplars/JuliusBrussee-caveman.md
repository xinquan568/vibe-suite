---
slug: JuliusBrussee-caveman
repo: JuliusBrussee/caveman
audited: 2026-05-13
commit_sha: HEAD
score: 92
exemplifies:
  - R04
  - R06
  - R08
  - R10
  - R11
  - R12
  - R49
---

# Exemplar: JuliusBrussee/caveman

**Score**: 92/100  |  **Date**: 2026-05-13  |  **Commit**: `HEAD`

A Claude Code plugin that compresses AI output to caveman-style prose; the skill collection (7 SKILL.md files, 3 agent definitions) demonstrates multi-trigger descriptions, runnable multi-level examples, and tight tool/model scoping that make each artifact immediately actionable without reading the README.

## Per-rule evidence

### R04 — Description as trigger

`skills/caveman/SKILL.md` packs seven activation phrases into its 156-character frontmatter description — slash command, mode-name variants, and intent signals — so the runtime can trigger it without the user knowing its name.

> Real quote from `skills/caveman/SKILL.md:3-8`:
>
> ```
> description: >
>   Ultra-compressed communication mode. Cuts token usage ~75% by speaking like caveman
>   while keeping full technical accuracy. Supports intensity levels: lite, full (default), ultra,
>   wenyan-lite, wenyan-full, wenyan-ultra.
>   Use when user says "caveman mode", "talk like caveman", "use caveman", "less tokens",
>   "be brief", or invokes /caveman. Also auto-triggers when token efficiency is requested.
> ```

What makes this strong over a mediocre example: each trigger phrase matches a realistic user utterance ("less tokens", "be brief") rather than restating the skill's internal name. The same pattern repeats in `skills/caveman-commit/SKILL.md` ("write a commit", "commit message", "generate commit", "/commit", "staging changes") and `skills/caveman-review/SKILL.md` ("review this PR", "code review", "/review").

### R06 — Code examples must be runnable

The main caveman skill covers six intensity levels and provides two fully worked examples, each showing all six levels applied to the same input so the agent can calibrate its output for any mode without guesswork.

> Real quote from `skills/caveman/SKILL.md:39-52`:
>
> ```
> Example — "Why React component re-render?"
> - lite: "Your component re-renders because you create a new object reference each render. Wrap it in `useMemo`."
> - full: "New object ref each render. Inline object prop = new ref = re-render. Wrap in `useMemo`."
> - ultra: "Inline obj prop → new ref → re-render. `useMemo`."
> - wenyan-lite: "組件頻重繪，以每繪新生對象參照故。以 useMemo 包之。"
> - wenyan-full: "物出新參照，致重繪。useMemo .Wrap之。"
> - wenyan-ultra: "新參照→重繪。useMemo Wrap。"
>
> Example — "Explain database connection pooling."
> - lite: "Connection pooling reuses open connections instead of creating new ones per request. Avoids repeated handshake overhead."
> - full: "Pool reuse open DB connections. No new connection per request. Skip handshake overhead."
> - ultra: "Pool = reuse DB conn. Skip handshake → fast under load."
> - wenyan-full: "池reuse open connection。不每req新開。skip handshake overhead。"
> - wenyan-ultra: "池reuse conn。skip handshake → fast。"
> ```

`skills/caveman-commit/SKILL.md` and `skills/caveman-review/SKILL.md` repeat the pattern with ❌/✅ pairs using real diff descriptions and concrete output ready to paste. No pseudocode appears in any of the seven skill files.

### R08 — Patterns over theory

The caveman skill body opens with a pattern template and an anti-pattern/good-pattern pair rather than explaining what "terseness" means. The agent is given a shape to fill, not a concept to interpret.

> Real quote from `skills/caveman/SKILL.md:20-26`:
>
> ```
> Drop: articles (a/an/the), filler (just/really/basically/actually/simply), pleasantries (sure/certainly/of course/happy to), hedging. Fragments OK. Short synonyms (big not extensive, fix not "implement a solution for"). Technical terms exact. Code blocks unchanged. Errors quoted exact.
>
> Pattern: `[thing] [action] [reason]. [next step].`
>
> Not: "Sure! I'd be happy to help you with that. The issue you're experiencing is likely caused by..."
> Yes: "Bug in auth middleware. Token expiry check use `<` not `<=`. Fix:"
> ```

The caveman-review skill mirrors this: the `Format:` line gives a slot-filling template (`L<line>: <problem>. <fix>.`) and the severity prefix table specifies exactly when to add each emoji. No prose explanation of what "clear" or "actionable" means.

### R10 — Model must match task complexity

`cavecrew-investigator.md` and `cavecrew-reviewer.md` both declare `model: haiku` for read-only, bounded-output tasks (code location and single-line review findings). `cavecrew-builder.md` has no explicit model pin, implying the default (Sonnet) for surgical editing that requires reasoning about diffs.

> Real quote from `agents/cavecrew-investigator.md:1-10`:
>
> ```
> ---
> name: cavecrew-investigator
> description: >
>   Read-only code locator. Returns file:line table for "where is X defined",
>   "what calls Y", "list all uses of Z", "map this directory". Output is
>   caveman-compressed so the main thread eats ~60% fewer tokens than
>   vanilla Explore. Refuses to suggest fixes.
> tools: [Read, Grep, Glob, Bash]
> model: haiku
> ---
> ```

Both Haiku agents produce bounded-enum or tabular output — exactly the class of task where Haiku matches Sonnet on accuracy at ~10× lower cost. The `model:` field is placed in the frontmatter (not buried in a body note), which is where the runtime reads it.

### R11 — Tools follow least-privilege

`cavecrew-investigator.md` carries `tools: [Read, Grep, Glob, Bash]` — no `Write` or `Edit` for an agent whose stated job is read-only location. `cavecrew-builder.md` closes the other gap: it explicitly names the missing tool rather than silently omitting it.

> Real quote from `agents/cavecrew-builder.md:9,18`:
>
> ```
> tools: [Read, Edit, Write, Grep, Glob]
> ```
>
> ```
> No `Bash` available — cannot shell out, cannot push, cannot delete.
> ```

Naming the absent tool in the body (rather than hoping the toollist absence is self-evident) prevents the agent from trying `Bash` calls and failing mid-task. The investigator's `Bash` allowance is similarly bounded: the body restricts it to `git diff`/`git log`/`find` only.

### R12 — Output format defined in body

All three agents specify their response structure as a literal template with a filled-in example, not a prose description of what the output should look like.

> Real quote from `agents/cavecrew-investigator.md:18-29`:
>
> ```
> ## Output
>
> ```
> <path:line> — `<symbol>` — <≤6 word note>
> <path:line> — `<symbol>` — <≤6 word note>
> ```
>
> Group with one-word header when 3+ rows: `Defs:` / `Refs:` / `Callers:` / `Tests:` / `Imports:` / `Sites:`.
> Single hit → one line, no header.
> Zero hits → `No match.`
> Last line → totals: `2 defs, 5 refs.` (omit if 0 or 1).
> ```

`cavecrew-builder.md` goes further: it names the output a "receipt" and specifies the final verification line (`verified: <re-read OK | mismatch @ path:line>`). `cavecrew-reviewer.md` closes with a live example showing three findings and a `totals:` line — the format is demonstrated, not described.

### R49 — CLAUDE.md for Claude, README for humans

The repo maintains a separate `README.md` alongside every `SKILL.md` (one per skill directory), and `CLAUDE.md` explicitly documents the audience split so agents working in the repo don't collapse them.

> Real quote from `CLAUDE.md:212-215`:
>
> ```
> Each skill has a human-facing `README.md` alongside the LLM-facing `SKILL.md`. The README explains what the skill does for users browsing GitHub; the SKILL.md is the prompt body the agent loads. Don't merge them — different audiences, different formats.
> ```

The `CLAUDE.md` itself follows R49: it contains zero product pitch, no install instructions, and no feature list. Its first section ("README is a product artifact") instructs Claude to treat the README like UI copy for non-technical users — keeping the two documents' purposes distinct even when editing one.

## Worth adopting

**Pattern: Auto-clarity sentinel.** Evidence: `skills/caveman/SKILL.md:56-63`, `agents/cavecrew-builder.md:45-47`, `agents/cavecrew-reviewer.md:47-49`. Each skill/agent declares a named section (`## Auto-Clarity`) specifying the exact conditions under which the compressed mode must drop to standard prose (security warnings, irreversible ops, ambiguous multi-step sequences, user confusion), then resume after. Why it would be a useful rule: **For communication-mode skills and any agent with a terse output persona, declare an explicit `Auto-Clarity` section listing the named exceptions where standard prose is mandatory.** Without named exceptions, a terse-mode agent either stays terse through a destructive-op warning (unsafe) or never enters terse mode out of caution (defeats the purpose).
