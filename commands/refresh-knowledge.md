---
name: refresh-knowledge
description: "Refresh the Claude conventions overlay from official docs via context7: --check reports drift between skills/conventions-claude/SKILL.md and the latest Claude Code documentation; --update applies the drift, rewrites the canonical freshness line, and writes the refreshed.json record scripts/doctor.py reads. Stops with install instructions when no context7 MCP tool is available. The conventions floor and the codex/antigravity overlays are /vibe-suite:spec-sync's job, not this command's."
argument-hint: "[--check | --update]"
---

# /vibe-suite:refresh-knowledge — context7 refresh of the Claude overlay

## User Input

```text
$ARGUMENTS
```

## Scope

This command reads and writes `skills/conventions-claude/` **only** — the fast context7 path
of F8.4. The conventions floor and the `conventions-codex` / `conventions-antigravity`
overlays are refreshed by `/vibe-suite:spec-sync` (F4.7), the research-agent path; when both
paths have run, `/vibe-suite:doctor` surfaces whichever is staler. Refreshing any other skill
from here would be a scope bug, not a feature.

## Step 1 — mode

| Input | Mode |
|---|---|
| `--check` | compare the overlay against the latest docs, report drift (read-only) |
| `--update` | fetch, apply drift, bump both freshness surfaces |
| (empty) | defaults to `--check` |

Any other argument: print this table and stop.

## Step 2 — context7 availability

**Prerequisite**: a context7 MCP tool must be available in this session. Detect by tool
name: any available MCP tool whose name contains `context7` (for example a
`resolve-library-id` / `query-docs` pair — the exact prefix depends on how the consumer
installed the plugin, so these names are examples, never the test). If none is available,
report:

> context7 MCP is not available. Install it with
> `/plugin install context7@claude-plugins-official`, or review the official docs at
> `code.claude.com/docs/en/` manually.

and **STOP**. No later step of this command runs without context7 — the absent-MCP branch
ends here.

## Step 3 — fetch the current documentation

Resolve the Claude Code docs library (query: "claude code"), then query the topics the
overlay's sections cover: plugin.json and manifest schemas; command, agent, and skill
frontmatter; hook events and hook types; `.mcp.json` and settings; CLAUDE.md and memory
conventions. Fetch before comparing — the overlay is never judged against recalled
knowledge.

## Step 4 — compare and report drift

Read `skills/conventions-claude/SKILL.md` and compare each of its sections against the
fetched documentation. Render the drift report:

```markdown
# Claude overlay freshness report

**Checked against**: context7 ({library ids queried})
**Overlay freshness line**: {the current **Spec freshness:** line}

| Area | Status | Details |
|---|---|---|
| plugin.json schema | CURRENT / DRIFT | {what differs, or "matches docs"} |
| Command frontmatter | CURRENT / DRIFT | … |
| Agent frontmatter | CURRENT / DRIFT | … |
| Skill structure | CURRENT / DRIFT | … |
| Hook events and types | CURRENT / DRIFT | … |
| MCP and settings | CURRENT / DRIFT | … |
| CLAUDE.md and memory | CURRENT / DRIFT | … |

**Verdict**: CURRENT — no update needed | UPDATE RECOMMENDED — {N} areas drifted
```

`--check` mode ends here.

## Step 5 — apply (`--update` only)

1. Rewrite each drifted section of `skills/conventions-claude/SKILL.md` to match the
   fetched docs, preserving the overlay's own structure and cross-references.
2. Rewrite the canonical freshness line (one line, immediately after the H1 — the same
   format `/vibe-suite:spec-sync` maintains):
   `**Spec freshness:** verified <today, ISO date> against code.claude.com/docs/en/`
3. Write `skills/conventions-claude/refreshed.json`:
   ```json
   {"refreshed": "<today, ISO date>", "source": "context7", "skill": "conventions-claude"}
   ```
   This is the record `scripts/doctor.py` reads (`knowledge_capability`): the `"refreshed"`
   key must be the dashed `YYYY-MM-DD` date. The repository ships no pre-refreshed record —
   this file exists only after a real `--update` run, so a missing record honestly means
   "never refreshed".
4. Show a diff summary:

```markdown
# Knowledge updated

| Section | Change |
|---|---|
| {area} | {added/removed/changed item} |

Freshness: **Spec freshness:** verified {date} · refreshed.json written.
Run `/vibe-suite:check` to verify the overlay's cross-references survived the edit.
```

## Failure handling

A context7 query that errors mid-run: report which topic failed and stop without writing
either freshness surface — a partial refresh stamped as fresh would be a lie doctor then
repeats. The overlay file is edited only after every planned query returned.
