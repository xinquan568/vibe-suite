---
description: "Bridge sub-operations: skills|hooks|mcp|mirrors|all (default all). Symlinks the plugin's skills, mirrors the project's Claude hooks into .codex/ for the five events both tools share, and mirrors .mcp.json servers into config.toml — never copying secret values. mirrors regenerates the codex/ tree via scripts/mirror-sync.py (E7.2)."
argument-hint: "[skills|hooks|mcp|mirrors|all]"
---

# /vibe-suite:bridge — bridge sub-operations

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge_cli.py" ${ARGUMENTS:-all} --workspace .
```

Forward the user's argument; `all` is the default. Report the per-step lines as returned.

## `mcp` — what crosses, and what never does

Servers in `.mcp.json` are mirrored into a `config.toml` sentinel block so Codex sees the same tools.

**A server that declares `env` contributes only names** — its own, and its variables'. Its `command`
and `args` are not mirrored, and the block says where to find them.

That rule is structural rather than a judgement about which values look secret. Trying to recognise
a secret does not work: withholding every value means a two-character entry like `on` blanks out
every occurrence of those characters, while any length threshold lets a genuinely short credential
through — and nothing in the file distinguishes a short credential from a short flag. Declaring
`env` is the one signal `.mcp.json` actually gives about which servers handle secrets, so that is
what the rule keys on.

A server with no `env` is mirrored in full.

**A variable name crosses only if it is one.** The placeholder is a comment line in the owned block,
so a name carrying a newline would end the comment and make whatever follows live TOML inside our
block. An env variable name outside `[A-Za-z0-9_]` is refused by name — the command exits 1 naming
the server and the variable — and `.codex/config.toml` is left exactly as it was.

The suite's own registration is skipped — mirroring it would register the bridge into itself.

## `hooks` — the *project's* hooks, not the plugin's

Three different things are called hooks here, and this mirrors the third:

| | Where | Whose |
|---|---|---|
| the plugin's registrations | the plugin's own `hooks/hooks.json` | vibe-suite's |
| the owned `Stop` entry | your `.codex/hooks.json` | none is written until the `vibe-suite` binary ships — an older init's bare `vibe-suite stop-gate` entry is dangling, and `/vibe-suite:repair` removes it |
| **the project's hooks** | your `.claude/settings.json` | **yours — this is what is mirrored** |

Only the five events both tools share cross: `SessionStart`, `UserPromptSubmit`, `PreToolUse`,
`PostToolUse`, `Stop`. Claude-only events are skipped and named in the output.

**Your entries are never overwritten.** Where `.codex/hooks.json` holds anything of yours, the mirror
goes to `.codex/hooks.vibe-suite.json` instead, and says so. Where it holds only an owned entry of
ours, that entry is preserved through the mirror.

## `skills`

**Mirror topology (E7.2).** When the plugin ships a generated `codex/skills` tree,
`.agents/skills` is a REAL directory of per-skill symlinks — one entry per mirrored skill
pointing into the plugin's `codex/skills/<name>` — so Codex discovers every skill at the
documented one-level depth, and the user's own entries live safely beside ours. The exact
legacy owned symlink (`.agents/skills → ../.claude/skills`) is migrated to the directory form
with per-skill links preserving everything it previously exposed; any OTHER `.agents/skills`
shape (a user-owned symlink elsewhere, a colliding user entry) is refused per entry, touching
nothing. Without a generated mirror the legacy whole-tree link stands.
 — two links

`.claude/skills/vibe-suite` → the installed plugin's skills, and `.agents/skills` →
`../.claude/skills`. The first **leaves your project by design** — it points at the plugin. A real
directory in either place is left alone; a link that already points where it should is accepted
rather than rewritten.

## `mirrors`

Regenerates the plugin's `codex/` mirror at the PLUGIN ROOT (never the user workspace) by
running `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mirror-sync.py" generate --root
"${CLAUDE_PLUGIN_ROOT}"`. A missing generator or a failing run is a loud per-leg failure and
exit 1 — never a silent skip. Regeneration is byte-idempotent; `bin/vibe-check --mirrors`
verifies the result.
