---
name: conventions-codex
description: Overlay of Codex CLI conventions — the config.toml grammar, the .codex-plugin/plugin.json manifest, the .agents/skills/ layout, the agents/openai.yaml sidecar, hook events, the AGENTS.md hierarchy, and marketplace.json; facts checked 2026-06-07 versus Codex 0.137.0 (a 2026-06-04 release).
---

# Codex CLI conventions overlay

This skill is the Tier 2-Codex overlay in the vibe-suite knowledge library. The
universal [conventions](../conventions/SKILL.md) floor states what every agent
artifact must satisfy no matter which tool runs it; this overlay stacks the
Codex-specific file layout, manifest schemas, config.toml grammar, hook events,
and version caveats on top of that floor. Load it whenever you are writing or
scoring an artifact aimed at the Codex CLI. The suite scorer pulls it in when
its classification step (step 3) labels an artifact Tier 2-Codex, and the suite
checker loads it for cross-component validation. Penalty weights are not
defined here — they live with the suite scoring rules; this file records facts.

Refresh state: verified 2026-06-07 against Codex CLI 0.137.0 (released
2026-06-04; pre-releases existed up to 0.138.0-alpha.6 at refresh time).

Authoritative sources (7):

- developers.openai.com/codex
- developers.openai.com/codex/skills
- developers.openai.com/codex/guides/agents-md
- developers.openai.com/codex/config-reference
- developers.openai.com/codex/hooks
- developers.openai.com/codex/plugins
- github.com/openai/codex

## 1. File system layout

The core mental-model shift from Claude Code: Codex splits its surface into a
cross-tool directory (`.agents/`) and a Codex-private directory (`.codex/`).
Claude's single-tool-directory model does not transfer.

| Artifact | Project scope | User scope |
|---|---|---|
| Skills | `.agents/skills/<name>/SKILL.md` (scanned CWD up to repo root) | `~/.agents/skills/` (admin: `/etc/codex/skills/`) |
| Plugin manifest | `<plugin-root>/.codex-plugin/plugin.json` | — (project only) |
| Marketplace | `.agents/plugins/marketplace.json` (legacy: `.claude-plugin/marketplace.json`) | `~/.agents/plugins/marketplace.json` |
| Memory | `AGENTS.md` files from git root down to CWD | `~/.codex/AGENTS.override.md`, then `~/.codex/AGENTS.md` |
| Config | `.codex/config.toml` (trust-gated) | `~/.codex/config.toml` |
| Hooks | `.codex/hooks.json` OR inline `[hooks]` in config.toml | `~/.codex/hooks.json` |
| Slash prompts | — (user-only per the layout docs; but see §8) | `~/.codex/prompts/<name>.md` |
| MCP servers | `[mcp_servers.<id>]` table in config.toml | same table in user config.toml |
| Skill sidecar | `<skill>/agents/openai.yaml` next to SKILL.md | — (project only) |

Per-directory AGENTS.md precedence: `AGENTS.override.md` → `AGENTS.md` →
configured fallback names, at most one file per directory, with files closer to
CWD overriding earlier ones.

Trust gate: project-scope hooks only load once the `.codex/` directory has been
trusted. Enforcement runs through the `/hooks` surface plus the
`allow_managed_hooks_only` key in `requirements.toml`.

## 2. SKILL.md and the agents/openai.yaml sidecar

Skills are read from `.agents/skills/`, NOT from `.codex/skills/`. Only the
agentskills.io baseline frontmatter — `name` and `description` — is required.
Anything Codex-specific belongs in the sidecar file `agents/openai.yaml`
living beside SKILL.md rather than inside its frontmatter. The sidecar acts as
metadata layered onto the open spec, not a departure from it.

Keys the sidecar accepts:

- `interface`: `display_name`, `short_description` (added 2026-06),
  `default_prompt`, `icon_small`, `icon_large` (added 2026-06), `brand_color`
- `policy.allow_implicit_invocation`: defaults to true; set false to keep the
  skill out of automatic selection
- `dependencies.tools`: an ARRAY of tool objects, each carrying a `type`, a
  `value`, a `description`, and a `transport` — never a bare string list (a
  2026-06-07 correction to the earlier string form)

Illustrative sidecar (placeholder values):

```yaml
interface:
  display_name: Release Notes
  short_description: Drafts release notes from merged PRs.
  default_prompt: Draft release notes for the latest tag.
  icon_small: icons/icon-16.png
  icon_large: icons/icon-128.png
  brand_color: "#0a7cff"
policy:
  allow_implicit_invocation: false
dependencies:
  tools:
    - type: mcp
      value: github
      description: Reads merged pull requests.
      transport: stdio
```

Duplicate skill names across scopes are not merged: both entries appear in
selectors, and the repo-level copy wins for local workflows.

## 3. `.codex-plugin/plugin.json` (plugin manifest)

Three fields are required: `name` (kebab-case), `version` (semver), and
`description`.

Component paths are optional and must be relative `./` paths: `skills`,
`mcpServers`, `apps`, `hooks`.

Identity fields (optional; added 2026-06): `author` (an object holding
`name`, `email`, `url`) plus `homepage`, `repository`, `license`, and
`keywords`.

The optional `interface` block groups presentation fields: naming via
`displayName`, `shortDescription`, `longDescription`, and `developerName`;
classification via `category` and `capabilities`; `defaultPrompt` (an ARRAY
of starter prompts, never a single string); links via `websiteURL`,
`privacyPolicyURL`, and `termsOfServiceURL`; and branding via `brandColor`,
`composerIcon`, `logo`, `screenshots`.

Minimal-but-complete example:

```json
{
  "name": "review-helpers",
  "version": "1.0.0",
  "description": "Shared review skills, hooks, and MCP registrations.",
  "skills": "./skills",
  "mcpServers": "./mcp-servers.json",
  "apps": "./review.app.json",
  "hooks": "./hooks.json",
  "interface": {
    "displayName": "Review Helpers",
    "longDescription": "Bundles the review skills, hook scripts, and MCP registrations this team shares across repositories."
  }
}
```

## 4. `.agents/plugins/marketplace.json`

Three marketplace tiers:

1. Official Curated — OpenAI-managed; self-serve submission was "coming soon"
   as of May 2026.
2. Repository — `<repo-root>/.agents/plugins/marketplace.json`.
3. Personal — `~/.agents/plugins/marketplace.json`.

Schema shape: top-level `name`, `interface.displayName`, and a `plugins[]`
array. Each plugin entry carries `name`, `source` (object with `source` and
`repo`), `policy` (object with `installation` and `authentication`),
`category`, and `interface.displayName`. Valid `source.source` values:
`"github"`, `"git"`, `"local"`.

## 5. `.codex/config.toml`

The format is TOML, not JSON. Key tables:

- `[features]` — breaking rename around 2026-04 (CLI 0.129+): `codex_hooks`
  became `hooks` (boolean; enables hooks.json or inline `[hooks]`). The old key
  survives as a deprecated alias that prints a warning — flag configs still
  using `codex_hooks`.
- `[mcp_servers.<id>]` — launch fields `command`, `args`, and `cwd`; a `url`
  field; the toggles `enabled`, `enabled_tools`, and `disabled_tools`; an
  `env` map; `startup_timeout_sec`; and `tool_timeout_sec` (a per-tool limit,
  60s by default, added 2026-06).
- `[hooks.<event>]` — declares hooks inline rather than in `.codex/hooks.json`.
- `[agents.<name>]` — defines subagents; its keys are `config_file`,
  `description`, and `nickname_candidates`.
- `[permissions.*]` — permission policy.
- Two keys govern AGENTS.md: `project_doc_max_bytes` and, for alternate
  filenames, `project_doc_fallback_filenames`.
- An optional model-catalog JSON path can be supplied at startup and overridden
  per profile.

REMOVED: 0.134.0 (2026-05-26) dropped the `[profiles.*]` tables. Each profile
is now a standalone file, `~/.codex/<name>.config.toml`, chosen via
`--profile <name>`. Any config still carrying a `[profiles.foo]` table should
be flagged as stale.

There is no repo-root `.mcp.json` support — MCP registration lives in
config.toml. Translating `.mcp.json` entries into `[mcp_servers.*]` tables is a
common porting pattern; in this suite, `/vibe-suite:bridge` performs that kind
of mirroring.

## 6. Hook events

Codex hook names mostly mirror Claude's, which makes porting easier than the
Antigravity divergence (see [conventions-antigravity](../conventions-antigravity/SKILL.md)).

Present in both Codex and Claude: `SessionStart` (also in Antigravity),
`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PermissionRequest`,
`PreCompact` (Antigravity's name is `PreCompress`), `PostCompact` (added to
Claude's 2026-06 event set — see the [conventions-claude](../conventions-claude/SKILL.md)
overlay §7), `SubagentStart` (a 2026-05-21 addition to Codex, in 0.133.0),
`SubagentStop`, and `Stop`.

Four Claude events have no Codex counterpart: `Notification`, `SessionEnd`,
`FileChanged`, `StopFailure`.

I/O contract — same shape as Claude:

- stdin JSON: `session_id` and `cwd`, then `hook_event_name`, `tool_name`,
  and `tool_input`
- stdout JSON: `continue`, `stopReason`, `systemMessage`, `hookSpecificOutput`

Exit codes: 0 with JSON on stdout = success with directives; 0 with plain text
= the text is added as context; 2 = block (reason read from stderr); any other
code = warning.

Caveats observed 2026-06:

- `SubagentStart`/`SubagentStop` inputs carry subagent identity, including
  `permission_mode` (since 0.134.0).
- A `continue: false` returned from `SubagentStart` will NOT halt the subagent.
- Async command hooks get parsed yet remain unsupported — declaring a hook
  async makes it a no-op.

## 7. AGENTS.md (canonical memory file)

Read before every turn. Every applicable file is stitched together from the
root downward, with a blank line between each; precedence is purely positional
(whichever file sits closer to CWD wins), no marker separates the global layer
from the project layer, and the walk ends at CWD.

- Per-directory order: `AGENTS.override.md` → `AGENTS.md` → fallback
  filenames; at most one file per directory.
- Global layer: `~/.codex/AGENTS.override.md`, then `~/.codex/AGENTS.md`.
- Each file is capped at 32 KiB by default, via `project_doc_max_bytes`.
- In mixed-tool repos, `project_doc_fallback_filenames` is the official
  interop hook — cover AGENTS.md, CLAUDE.md, and GEMINI.md in the array.
- Common (unenforced) body headings: `## Working agreements`,
  `## Repository expectations`.

Unlike GEMINI.md, there is NO `@file.md` import support here; lean on the
concatenation behavior instead. The popular pattern of a CLAUDE.md that imports
`@AGENTS.md` fails under Codex — put the shared content in AGENTS.md and have
CLAUDE.md import from it, not the other way around.

## 8. Slash commands / prompts

Prompt files live at `~/.codex/prompts/<name>.md`; a project form
`.codex/prompts/` also exists even though the layout table in §1 lists prompts
as user-only. The claim that prompts are "deprecated in favor of skills" was
NOT confirmed in current docs as of 2026-06-07 — apply no penalty for their
presence, and treat any migration advice as advisory/soft only.

Legacy placeholder set: `$1..$9`, `$ARGUMENTS`, `$FILE`, `$TICKET_ID`, `$$`.

## 9. Recent breaking and material changes

| Date | Version | Change |
|---|---|---|
| 2026-03-26 | — | Plugin marketplace launched (new artifact class) |
| ~2026-04 | 0.129.0 | `[features].codex_hooks` → `[features].hooks` (deprecation warning) |
| 2026-05-18 | 0.131.0 | Plugin hooks on by default; legacy shell tools and built-in MCPs removed; `codex doctor` added |
| 2026-05-21 | 0.133.0 | Goals on by default; `SubagentStart` observable |
| 2026-05-26 | 0.134.0 | `[profiles.*]` dropped → per-profile files + `--profile`; MCP OAuth for HTTP servers + per-server env; read-only MCP tools run concurrently (`readOnlyHint`); subagent identity in hook inputs |
| 2026-05-28 | 0.135.0 | `/permissions` named permission profiles; expanded `codex doctor`; `CODEX_NON_INTERACTIVE=1` |
| 2026-06-01 | 0.136.0 | Session archive (`/archive`, `codex archive`/`unarchive`); `CODEX_API_KEY` remote-exec registration; 4 security fixes |
| 2026-06-04 | 0.137.0 | `codex plugin list --json`; Multi-agent v2 per-thread runtime persistence; plugin skill manifest validation improvements; cloud-managed config bundles |

Scoring implications: flag MCP configs that name the removed built-in MCPs
(silent regression under 0.131+), and flag `[profiles.*]` configs as stale
under 0.134+.

## 10. Scope and open items

Out of scope here: the tool-agnostic rules stay in the
[conventions](../conventions/SKILL.md) floor; penalty tables stay with the
suite scoring rules; cross-component validation belongs to the suite checker
agent.

Resolved at the 2026-06-07 refresh:

- A `child_agents_md` flag could not be found in any doc — treat it as removed
  or never shipped, and do not score against it.
- The AGENTS.md merge-boundary question is settled: override is positional,
  each directory contributes at most one file, and the walk ends at CWD.

Remaining unknowns:

- The full `.app.json` schema behind the plugin `apps` field is unpublished.
  The field itself is documented: a relative `.app.json` at the plugin root
  holding app/connector mappings.
- OpenAI's contributor/CLA policy for openai/codex-ecosystem PRs is
  undocumented — research it before scaling up upstream-PR work.
