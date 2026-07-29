---
name: conventions-antigravity
description: Overlay of Antigravity (plus legacy Gemini CLI) conventions — workspace skills under .agent/, the .gemini/ paths, gemini-extension.json, GEMINI.md imports, slash commands in TOML, and the Gemini-lineage hook events; the spec has not settled since Antigravity 2.0 (2026-05-19), so most tool-specific checks stay advisory.
---

# Antigravity conventions overlay

This skill is the Tier 2-Antigravity overlay in the vibe-suite knowledge
library. The universal [conventions](../conventions/SKILL.md) floor covers
everything that holds for agent artifacts regardless of tool; this overlay
adds the Antigravity- and Gemini-CLI-specific layouts, manifests, hook events,
and memory-file behavior on top of that floor. Load it when writing or scoring
artifacts aimed at Antigravity or the legacy Gemini CLI. The suite scorer
loads it once its classification step (step 3) labels an artifact
Tier 2-Antigravity, and the suite checker loads it for validation.

STATUS — advisory only for Antigravity-specific findings. Google I/O on
2026-05-19 brought the Antigravity 2.0 announcement, just six days ahead of
when the underlying research was written; the directory layout is unsettled,
and two research passes even disagreed on `.agent/` vs `.agents/`. Until the
verification pass described in §10 lands, treat Antigravity-specific checks
as guidance, not deductions.

Transition timeline:

- Now through 2026-06-18: Gemini CLI keeps serving the AI Pro, Ultra, and Free
  tiers in parallel with Antigravity.
- 2026-06-18: non-enterprise users lose the Gemini CLI (paid enterprise
  licenses keep going).
- After the sunset: the Antigravity CLI is the sole successor and `.gemini/`
  fades to legacy status.

Authoritative sources (7):

- developers.googleblog.com — Antigravity launch post
- developers.googleblog.com — Gemini-to-Antigravity transition post
- antigravity.google
- codelabs.developers.google.com — Antigravity skills codelab
- geminicli.com/docs/cli/skills/ (transitional)
- geminicli.com/docs/hooks/reference/ (transitional)
- github.com/google/skills

## 1. File system layout (three scopes)

| Artifact | Antigravity project | Gemini legacy project | User scope |
|---|---|---|---|
| Skills | `<workspace>/.agent/skills/<name>/SKILL.md` (SINGULAR, per the codelab) plus `.agents/skills/<name>/SKILL.md` (plural cross-tool alias) | `.gemini/skills/<name>/SKILL.md` | `~/.gemini/antigravity/skills/` (transitional global) or `~/.gemini/skills/` (legacy) |
| Slash commands | under-documented | `.gemini/commands/<name>.toml` | `~/.gemini/commands/` |
| Hooks | under-documented | `hooks` object in `.gemini/settings.json` | `~/.gemini/settings.json` |
| MCP | under-documented | `mcpServers` key in `.gemini/settings.json` | `~/.gemini/settings.json` |
| Extensions/plugins | becoming "Antigravity plugins"; manifest `gemini-extension.json` (rename announced, layout TBD) | `gemini-extension.json` | `~/.gemini/extensions/<name>/gemini-extension.json` |
| Memory | `GEMINI.md` inherited; filename configurable via the `context.fileName` array; workspace + ancestors | same | `~/.gemini/GEMINI.md` |
| System config | TBD | `/etc/gemini-cli/settings.json` | — |

Precedence within a tier (Gemini lineage, assumed carried over):
built-in → extension → user → workspace. Between skill paths,
`.agents/skills/` beats `.gemini/skills/` — the cross-tool path wins.

Known ambiguity: singular `.agent/skills/` vs plural `.agents/skills/`. Both
may be valid, or one may be a documentation error. Recommendation: recognize
both as valid skill paths and never penalize either.

## 2. SKILL.md

Antigravity explicitly adopts the agentskills.io open standard: as with every
other tool, `name` plus `description` is the whole required frontmatter.

Skill-related extensions specific to Antigravity/Gemini:

- `activate_skill` — an in-agent tool for loading a skill on demand.
- A mandatory user-consent prompt fires before a skill is injected, since
  injection is a filesystem-access grant.
- `/skills` — slash command inside the agent that lists whatever skills are
  installed.
- `gemini skills` — a Gemini-only terminal command covering list, install,
  and uninstall; on Antigravity the equivalent is `npx skills add`.

How installs are invoked:

- Cross-tool (per the repo page): `npx skills add github.com/google/skills`.
- Legacy Cloud Next wording: `npx skills install` — equivalent, but `add` is
  canonical.
- Gemini CLI: `gemini extensions install <github-url|path>`.

## 3. `gemini-extension.json` (extension manifest)

Required fields: `name`, `version`. Notable optional fields: `mcpServers`,
`contextFileName`, `excludeTools`.

Minimal example:

```json
{
  "name": "team-helpers",
  "version": "0.3.0",
  "mcpServers": {
    "tickets": { "command": "node", "args": ["mcp/tickets.js"] }
  },
  "contextFileName": "AGENTS.md",
  "excludeTools": ["run_shell_command"]
}
```

The rename to "Antigravity plugin" has been announced; the schema is said to
"preserve" extension semantics, but the full delta is unpublished.

## 4. `.gemini/commands/<name>.toml` slash commands

Only `prompt` is required. `description` is optional — when it is omitted,
one is auto-generated from the filename.

The template syntax below is Gemini-specific:

- `{{args}}` — injects the raw arguments.
- `!{shell command}` — executes a shell command, auto-escaping its arguments.
- `@{path}` — injects a file or a directory; `.gitignore` and `.geminiignore`
  are honored; PNG/JPEG/PDF/audio/video are all accepted.

Subdirectories create namespaces: `.gemini/commands/ns/cmd.toml` is invoked as
`/ns:cmd`.

Example:

```toml
description = "Summarize a changeset for review."
prompt = """
Summarize this change request and list its risks: {{args}}
"""
```

Whether TOML commands carry over to Antigravity is unclear — treat them as
legacy-only; the Antigravity command format is TBD.

## 5. Hook events (Gemini lineage)

The lifecycle is decomposed into Agent, Model, and Tool layers — fundamentally
different from the tool-centric model Claude and Codex share (see
[conventions-codex](../conventions-codex/SKILL.md) §6 for that side).

11 events and their triggers:

| Event | Fires |
|---|---|
| `SessionStart` | session begin |
| `BeforeAgent` | each agent turn |
| `BeforeModel` | before an LLM call |
| `BeforeToolSelection` | before the model picks a tool |
| `BeforeTool` | before tool execution, post-selection |
| `AfterTool` | after tool execution |
| `AfterModel` | after the LLM call |
| `AfterAgent` | after the agent turn |
| `SessionEnd` | session end |
| `Notification` | notification emitted |
| `PreCompress` | Gemini's name for Claude's `PreCompact` |

There is no 1:1 mapping to Claude/Codex: the `BeforeModel` vs
`BeforeToolSelection` split has no analog (both fold under Claude's
`PreToolUse`), and nothing here corresponds to `UserPromptSubmit` or
`PermissionRequest` on the Claude side.

The I/O contract:

- stdin JSON: `session_id` and `transcript_path`, plus `cwd`,
  `hook_event_name`, and `timestamp`
- stdout JSON: `systemMessage`, then `decision` (`"allow"`/`"deny"`) with its
  `reason`, plus `continue` and `suppressOutput`

Exit codes: 0 means ok; 2 means block, with the reason carried on stderr;
every other code means warning.

Antigravity's own event names are TBD — the transition post says it "preserves
hooks" yet publishes no event list, leaving the Gemini list above as the best
guess currently available.

## 6. The GEMINI.md memory file

The hierarchy runs `~/.gemini/GEMINI.md` → GEMINI.md files in the workspace
and its ancestors → GEMINI.md discovered JIT when a file is accessed. All of
it is concatenated into each prompt.

What sets GEMINI.md apart from AGENTS.md/CLAUDE.md is `@file.md` import
support through the Memory Import Processor — checked against
geminicli.com/docs/reference/memport/ on 2026-05-26. Nesting works (max depth
configurable, 5 by default), no filename restriction applies, and both
relative and absolute paths are accepted. Put only `@AGENTS.md` in a
GEMINI.md and it resolves to the complete AGENTS.md contents. Imports are
confined to allowed directories by `validateImportPath` (siblings of the
repo root are OK).

`context.fileName` in settings.json accepts an ARRAY (e.g. AGENTS.md,
CONTEXT.md, GEMINI.md) — the official interop hook for AGENTS.md (the Codex
canonical memory file) and CLAUDE.md (the Claude canonical).

For multi-tool repos the recommended move is `context.fileName:
["AGENTS.md"]` inside `.gemini/settings.json` — NOT the @-import shim. Why:
design decision #5 of the suite names AGENTS.md as the canonical universal
memory file, and that exact settings file ships with the suite. The shim works per the docs, but every
documented example uses explicit `@./` / `@../` prefixes — the bare
`@AGENTS.md` form (Claude-native style) is unconfirmed on a live Gemini run,
while `context.fileName` has zero ambiguity: a direct read with no import
resolution.

## 7. MCP integration

Server definitions come from the `mcpServers` key — in
`.gemini/settings.json` at project scope, or `~/.gemini/settings.json` at
user scope — never from a separate `.mcp.json`. The shape is the
standard `command`, `args`, `env`. Extension-bundled servers may also be
declared inside `gemini-extension.json`.

Slash commands: `/mcp list`, `/mcp auth`.

Antigravity's MCP layout: TBD.

## 8. Plugin marketplace

There is no central JSON marketplace manifest for the Gemini CLI. Discovery
runs through the Extensions Gallery at geminicli.com/extensions/ (community,
partner, and Google entries, ranked by GitHub stars); installation via
`gemini extensions install <github-url|path>`. The Antigravity marketplace
layout is TBD.

Google's official skills registry lives at github.com/google/skills; it is
organized under `skills/cloud/...` and installed via
`npx skills add google/skills`. The tools it targets span Claude Code,
Codex CLI, the Gemini CLI, Cursor, Antigravity, and others.

## 9. Notable recent changes

| Date | Event |
|---|---|
| 2025-11-20 | Original Antigravity public preview |
| 2026-04 (Cloud Next) | google/skills official registry launched; `npx skills` cross-agent installer |
| 2026-05 | Extensions Gallery launched (partners: Dynatrace, Elastic, Figma, Harness) |
| 2026-05-19 (Google I/O) | Antigravity 2.0 announced; Antigravity CLI GA; Gemini CLI deprecation announced |
| 2026-06-18 (pending) | Gemini CLI stops serving AI Pro/Ultra/Free tiers |

## 10. Scope and uncertainties

Out of scope here: tool-agnostic rules stay in the
[conventions](../conventions/SKILL.md) floor; penalty tables stay with the
suite scoring rules; the Antigravity desktop IDE and the Antigravity SDK are
different artifact surfaces and are not covered.

Seven open uncertainties (defer deep audits on these):

1. Singular `.agent/` vs plural `.agents/` — recognize both.
2. The `npx skills` verb — `add` is canonical; `install` is legacy blog
   wording.
3. The directory-rename spec — "not 1:1 parity" per the transition post, with
   the gaps unenumerated; watch for a migration guide.
4. Antigravity hook event names — assumed inherited from Gemini, unconfirmed.
5. A `github.com/google-antigravity/antigravity-cli` org/repo surfaced during
   research, but the namespace differs from `google/` — verify before citing.
6. The "Antigravity plugins" manifest schema delta is unpublished.
7. MCP support in Antigravity is neither contradicted nor confirmed.

Upgrade trigger: once a stable Antigravity directory-layout spec comes out of
Google, OR real-world repository counts show Antigravity ahead of the Gemini
CLI, this overlay graduates from advisory to authoritative and the suite
scoring rules gain Antigravity-specific penalty rows.
