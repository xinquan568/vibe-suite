---
artifact: commands/refresh-knowledge.md
type: command
min_score: 80
---

# refresh-knowledge — suite spec (vibe-51 / E6.5)

Source: F8.4 (`/vibe-suite:refresh-knowledge` — context7-driven conventions refresh) narrowed
by E6.5. This spec restates the proposal's expectations as a test; the artifact's author
inherits these, not inventions. The command is the fast context7 path for the **Claude
overlay only** — the conventions floor and the codex/antigravity overlays belong to
`/vibe-suite:spec-sync` (F4.7).

## Triggers On
- "/vibe-suite:refresh-knowledge"
- "/vibe-suite:refresh-knowledge --check"
- "/vibe-suite:refresh-knowledge --update"
- "refresh the Claude conventions knowledge from the official docs"
- "is the Claude overlay current against the latest Claude Code docs"

## Does Not Trigger On
- "sync all three overlays against their docs"        (spec-sync's multi-overlay job)
- "score the conventions skill"                        (scoring, not refreshing)
- "diagnose this workspace"                            (doctor's job)

## Frontmatter Valid
- description present, naming the Claude-overlay scope and the doctor-read record
- argument-hint offering `[--check | --update]`
- no pinned model id anywhere (a tier alias is acceptable)

## Output Contains
- a drift report with per-area CURRENT/DRIFT status rows (`--check`)
- an update summary naming what changed (`--update`)

## Behavior
- Empty input defaults to `--check`; the doc states this in its mode table.
- **Absent context7**: the doc instructs detecting whether any context7 MCP tool is
  available (tool names containing `context7` — named ids are examples, since the prefix
  depends on the consumer's install), and when none is, printing the install instruction
  (`/plugin install context7@claude-plugins-official` or reviewing the official docs) and
  **stopping** — no refresh step is reachable from that branch.
- **Target boundary**: the refresh reads and writes `skills/conventions-claude/` only, and
  the doc says explicitly that the floor and other overlays are spec-sync's.
- **Update path**: applies drifted sections to the overlay's `SKILL.md`, rewrites the
  canonical `**Spec freshness:**` line (spec-sync's pinned format, bare-domain source
  label), and writes `skills/conventions-claude/refreshed.json` with a `"refreshed"`
  ISO-date key — the record `scripts/doctor.py` reads. The repo ships no pre-refreshed
  record; the date is written only by a real `--update` run.
