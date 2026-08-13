---
slug: ykdojo-claude-code-tips
repo: ykdojo/claude-code-tips
audited: 2026-05-13
commit_sha: 7ebc93b5f9fd678909a669d8f67069bf39dbfb32
score: 94
exemplifies:
  - R04
  - R05
  - R06
  - R08
---

# Exemplar: ykdojo/claude-code-tips

**Score**: 94/100  |  **Date**: 2026-05-13  |  **Commit**: `7ebc93b5f9fd678909a669d8f67069bf39dbfb32`

A six-skill developer-tools plugin (GitHub Actions debugging, conversation cloning, Reddit research) where the standout quality is pattern-richness: each skill teaches *how to handle the surprising cases*, not just the happy path.

## Per-rule evidence

### R04 — Description as trigger

The `reddit-fetch` skill packs three distinct failure-mode triggers into a single description line, making it unambiguous when to activate.

> Real quote from `skills/reddit-fetch/SKILL.md:3-4`:
>
> ```
> description: Fetch content from Reddit using Gemini CLI or curl JSON API fallback. Use when accessing Reddit URLs, researching topics on Reddit, or when Reddit returns 403/blocked errors.
> ```

Three trigger phrases ("accessing Reddit URLs", "researching topics on Reddit", "Reddit returns 403/blocked errors") cover both proactive and reactive invocation. A description that only said "Reddit access helper" would trigger on neither.

### R05 — Body length

The `handoff` skill delivers a complete, multi-step workflow in 19 lines. The `clone` skill delivers another in 16. Both are used verbatim without needing an "overview" section.

> Real quote from `skills/handoff/SKILL.md` (entire body):
>
> ```
> Write or update a handoff document so the next agent with fresh context can continue this work.
>
> Steps:
> 1. Check if HANDOFF.md already exists in the project
> 2. If it exists, read it first to understand prior context before updating
> 3. Create or update the document with:
>    - **Goal**: What we're trying to accomplish
>    - **Current Progress**: What's been done so far
>    - **What Worked**: Approaches that succeeded
>    - **What Didn't Work**: Approaches that failed (so they're not repeated)
>    - **Next Steps**: Clear action items for continuing
>
> Save as HANDOFF.md in the project root and tell the user the file path so they can start a fresh conversation with just that path.
> ```

Completeness without bloat: the skill covers the full decision tree (file exists? read first), the output schema (5 named fields), and the final user-facing action in fewer lines than most skill frontmatter sections.

### R06 — Code examples must be runnable

The `reddit-fetch` skill's curl commands include a working User-Agent header, `old.reddit.com` URL structure, `-L` flag rationale, and real jq field paths — not pseudocode placeholders.

> Real quote from `skills/reddit-fetch/SKILL.md:77-80`:
>
> ```bash
> curl -s -L -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
>   "https://old.reddit.com/r/SUBREDDIT/hot.json?limit=15"
> ```

And the jq pipeline that follows names the exact field path (`.data.children[] | .data | "\(.title)\n..."`), not a generic "parse as needed". The `review-claudemd` skill matches this — it gives a complete bash pipeline to locate project conversation history, not a description of what such a pipeline would do.

> Real quote from `skills/review-claudemd/SKILL.md:14-19`:
>
> ```bash
> # Find the project folder (replace / with -)
> PROJECT_PATH=$(pwd | sed 's|/|-|g' | sed 's|^-||')
> CONVO_DIR=~/.claude/projects/-${PROJECT_PATH}
> ls -lt "$CONVO_DIR"/*.jsonl | head -20
> ```

Both examples run as-is; neither requires the reader to fill in implementation details.

### R08 — Patterns over theory

The `reddit-fetch` skill handles a notoriously tricky UI ambiguity — whether a tmux `send-keys` command actually submitted — by showing *exactly what the terminal looks like* in each state, not by explaining the mechanics.

> Real quote from `skills/reddit-fetch/SKILL.md:36-56`:
>
> ```
> **Enter NOT sent** - your query is INSIDE the box:
> ```
> ╭─────────────────────────────────────╮
> │ > Your actual query text here       │
> ╰─────────────────────────────────────╯
> ```
>
> **Enter WAS sent** - your query is OUTSIDE the box, followed by activity:
> ```
> > Your actual query text here
>
> ⠋ Our hamsters are working... (processing)
>
> ╭────────────────────────────────────────────╮
> │ >   Type your message or @path/to/file     │
> ╰────────────────────────────────────────────╯
> ```
>
> Note: The empty prompt `Type your message or @path/to/file` always appears in the box - that's normal.
> ```

A theory-based version would say "check whether the prompt box is active." This version renders two ASCII screenshots and points to the distinguishing pixel. Claude can match the pattern directly rather than reason about it.

The `review-claudemd` skill applies the same instinct to conversation batching — instead of "adjust batch size based on file size", it gives three explicit size tiers with counts:

> Real quote from `skills/review-claudemd/SKILL.md:72-74`:
>
> ```
> - Large (>100KB): 1-2 per agent
> - Medium (10-100KB): 3-5 per agent
> - Small (<10KB): 5-10 per agent
> ```

## Worth adopting

**Pattern: ASCII screenshot pairs for UI ambiguity.** Evidence: `skills/reddit-fetch/SKILL.md:36-56`. When a skill invokes an interactive CLI tool where the state is visually ambiguous (tmux panes, TUI prompts, progress spinners), include two ASCII screenshots — one for each state — with a one-line label. Why it would be a useful rule: visual state matching requires zero reasoning from Claude; a rule that instructs "show two-state screenshots for interactive CLIs, not procedural descriptions" would eliminate a class of stuck-in-the-box failures that prose descriptions cannot prevent.
