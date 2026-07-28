---
description: "Bridge sub-operations: skills|hooks|mcp|mirrors|all (default all). Symlinks the plugin's skills, mirrors the project's Claude hooks into .codex/ for the five events both tools share, and mirrors .mcp.json servers into config.toml — never copying secret values. mirrors regenerates the codex/ tree and lands in S7."
argument-hint: "[skills|hooks|mcp|mirrors|all]"
---

# /vibe-suite:bridge — bridge sub-operations

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge_cli.py" ${ARGUMENTS:-all} --workspace .
```

Forward the user's argument; `all` is the default. Report the per-step lines as returned.

## `mcp` — what crosses, and what never does

Servers in `.mcp.json` are mirrored into a `config.toml` sentinel block so Codex sees the same tools.
**No `env` value is ever copied.** The variable's *name* crosses as a comment, so you know what to
set; its value stays in the one file you put it in.

That is an allowlist, not a redaction. A masked value would still put the secret's shape somewhere
you did not choose to put it.

The suite's own registration is skipped — mirroring it would register the bridge into itself.

## `hooks` — the *project's* hooks, not the plugin's

Three different things are called hooks here, and this mirrors the third:

| | Where | Whose |
|---|---|---|
| the plugin's registrations | the plugin's own `hooks/hooks.json` | vibe-suite's |
| the owned `Stop` entry | your `.codex/hooks.json` | written by `/vibe-suite:init` |
| **the project's hooks** | your `.claude/settings.json` | **yours — this is what is mirrored** |

Only the five events both tools share cross: `SessionStart`, `UserPromptSubmit`, `PreToolUse`,
`PostToolUse`, `Stop`. Claude-only events are skipped and named in the output.

**Your entries are never overwritten.** Where `.codex/hooks.json` holds anything of yours, the mirror
goes to `.codex/hooks.vibe-suite.json` instead, and says so. Where it holds only our owned entry,
that entry is preserved through the mirror.

## `skills` — two links

`.claude/skills/vibe-suite` → the installed plugin's skills, and `.agents/skills` →
`../.claude/skills`. The first **leaves your project by design** — it points at the plugin. A real
directory in either place is left alone; a link that already points where it should is accepted
rather than rewritten.

## `mirrors`

Not available yet. The `codex/` mirror generator lands in **S7 (E7.2)**; until then this reports that
and regenerates nothing, rather than succeeding silently.
