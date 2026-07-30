---
name: conventions-claude
description: Claude Code overlay on the conventions floor — schemas and conventions for plugin.json, commands, skills, agents, rules, hooks, .mcp.json, marketplace.json, CLAUDE.md, memory, and settings at .claude/ canonical paths.
---

# Claude Code Conventions Overlay

Overlay on the universal [conventions floor](../conventions/SKILL.md). Floor
rules always apply; the rules below bind only to artifacts at Claude Code's
canonical paths (`.claude/`, `plugin.json`, and plugin component
directories).

**Spec freshness:** verified 2026-06-07 against the official Claude Code docs map dated 2026-06-05 (code.claude.com/docs/en/)

That map tracks Claude Code ≥ v2.1.16x; where earlier notes conflicted with this
refresh, the newer facts below are canonical.

Deep-detail tables live in [references/reference.md](references/reference.md):
hook context fields, the settings field table, auto-memory details, the LSP
server schema, the monitor schema, the built-in tool catalog, and the plugin
directory layout tree.

## When to use

Load this overlay when: validating frontmatter of commands, agents, skills,
or rules; checking hook event names or hook JSON shapes; authoring any
`.claude/` artifact or plugin component; or auditing a Claude Code plugin.

## 1. plugin.json (`.claude-plugin/plugin.json`)

- The whole manifest is optional. When present, only `name` is required
  (kebab-case; it is the namespacing id).
- Recommended: `version` (semver) and `description`. With `version` omitted,
  the commit SHA is used instead.
- Optional metadata: `author` `{name, email, url}`, `homepage`,
  `repository`, `license` (SPDX), `keywords` (array), `$schema`.
- Component path fields: `commands`, `agents`, `skills`, `hooks`,
  `mcpServers`, `lspServers`, `outputStyles`. When omitted, components are
  auto-discovered from conventional directories. Defaults: `./commands/`,
  `./agents/`, `./skills/`, `./hooks/hooks.json`, `./.mcp.json`,
  `./.lsp.json`. `hooks` and `mcpServers` may also be INLINE objects.
- Version-gated fields: `displayName` (v2.1.143+), `defaultEnabled`
  (v2.1.154+).
- `userConfig` declares per-key prompts shown at enable time; values are
  read back via `${user_config.<key>}`.
- Also recognized: `channels`; `dependencies` (semver constraints);
  `experimental.themes` and `experimental.monitors` (both were top-level
  once — top-level still works, `claude plugin validate` warns, and the
  `experimental.*` form becomes mandatory in a coming release).
- Unrecognized fields produce a warning only; they error only under
  `claude plugin validate --strict`.
- NOT manifest fields: `agent` is a settings.json key (a plugin's
  settings.json allows only `agent` and `subagentStatusLine`); `category`
  belongs in the marketplace.json entry.
- When marketplace.json and plugin.json disagree on version, plugin.json
  wins.

## 2. Commands and skills — merged surfaces

As of v2.1.x, commands and skills share ONE architecture with identical
frontmatter and semantics. For new development, prefer
`.claude/skills/<name>/SKILL.md`; the `.claude/commands/<name>.md` form is
equivalent, and the legacy skills-inside-`commands/` layout works
identically.

### Frontmatter

| Key | Notes |
|---|---|
| `description` | required |
| `name` | optional — falls back to the filename or directory name |
| `argument-hint` | invocation hint shown to the user |
| `arguments` | named arguments, substituted via `$name` |
| `allowed-tools` | space-separated string OR array (e.g. `Read Grep Bash(git status:*)`); omit to allow all tools |
| `disallowed-tools` | deny-list counterpart |
| `model` | `haiku` / `sonnet` / `opus`, a full model identifier, or `inherit` |
| `effort` | `low` / `medium` / `high` / `xhigh` / `max` |
| `user-invocable: false` | hides from users — REQUIRED on shared partials |
| `disable-model-invocation` | blocks programmatic invocation by the model |
| `when_to_use` | appended to the description for triggering |
| `context: fork` | runs in a forked context |
| `agent` | executing agent: `Explore`, `Plan`, or `general-purpose` |
| `hooks` | skill-scoped hooks |
| `paths` | glob list; matching files auto-load the skill |
| `shell` | `bash` or `powershell` |

### Body

- Imperative instructions FOR Claude — not documentation shown to a user.
- Use numbered steps; reference shared partials by full relative path.
- Dynamic context: a !`cmd` span runs before delivery and injects its
  output; a fenced code block whose info string is `!` runs multi-line
  commands. Both are disabled by the setting
  `disableSkillShellExecution: true`.
- Substitutions that are always valid (never flag them): `$ARGUMENTS`,
  `$ARGUMENTS[N]`, `$N`, `$name`, `${CLAUDE_SESSION_ID}`, `${CLAUDE_EFFORT}`,
  and the path tokens `${CLAUDE_SKILL_DIR}` and `${CLAUDE_PLUGIN_ROOT}`.

### Shared partials

Live in `commands/shared/`; MUST set `user-invocable: false`; MUST carry a
`description`; are referenced by full relative path.

## 3. Agents

Auto-discovered from `.claude/agents/` or a plugin's `agents/` directory.

| Key | Notes |
|---|---|
| `name` | agent id |
| `description` | drives triggering — include 3+ trigger phrases and at least 2 diverse `<example>` blocks |
| `tools` | array or comma-separated string; `allowed-tools` is a community-convention alternative |
| `disallowedTools` | the correct deny key — there is no `tool-restrictions: {allow, deny}` |
| `skills` | preloads `plugin:skill` ids at startup (vs on-demand loading) |
| `model` | defaults to `inherit`; tier aliases or full model identifiers OK |
| `effort` | as for commands |
| `color` | valid: red, blue, green, yellow, purple, orange, pink, cyan — `magenta` is NOT valid |
| `permissionMode` | `default` / `acceptEdits` / `auto` / `dontAsk` / `bypassPermissions` / `plan` |
| `isolation` | only `"worktree"` |
| `memory` | `user` / `project` / `local` |
| `maxTurns` | integer |
| `background` | boolean |
| `initialPrompt` | first message on launch |
| `mcpServers`, `hooks` | agent-scoped servers and hooks |

- The markdown body IS the system prompt (surfaced as the `prompt` key in
  `--agents` JSON). No `system-prompt` frontmatter key exists, so reporting
  one as missing is itself a bug.
- Security: for plugin-shipped agents, `hooks`, `mcpServers`, and
  `permissionMode` are IGNORED, even though the fields exist.
- Model-to-task fit: haiku for mechanical passes, sonnet for reasoning, opus
  for judgment.

## 4. Skill structure and discovery

- Layouts: `skills/<name>/SKILL.md` and `skills/<plugin>/<name>/SKILL.md`;
  project scope `.claude/skills/`; user scope `~/.claude/skills/`.
- Required frontmatter: `name` + `description` (the description is the
  auto-load trigger). Optional: `version`; community `globs` key for
  file-pattern scoping.
- Supporting directories: `references/`, `examples/`, `scripts/`; link
  companions from the SKILL.md body. Body under 500 lines.
- v2.1.x discovery: parent-directory scanning plus monorepo nested scanning
  (`parent/.claude/skills`, `packages/*/.claude/skills`) plus `--add-dir`
  paths.
- An agent's `skills:` list preloads at startup; everything else loads
  on demand.

## 5. Rules (`.claude/rules/`)

- Frontmatter: `description` required; `paths` optional glob array.
- Total budget under 500 lines across all rule files.
- Style: bold-imperative lead sentence, then rationale; positive framing;
  enforceable means testable, specific, observable.
- Do not duplicate what linters, formatters, or CI already enforce.
- Ordered-set naming: `NN-kebab-name.md`.

## 6. Hook events

- Event names are case-sensitive; a wrong-case name is silently ignored.
- Core events: PreToolUse, PostToolUse, PostToolUseFailure,
  PermissionRequest, UserPromptSubmit, Stop, SubagentStop, SessionStart,
  SessionEnd, PreCompact, Notification, InstructionsLoaded.
- Additional documented events: StopFailure, FileChanged, TaskCompleted
  (exact spelling — not TaskComplete), Setup, SubagentStart,
  UserPromptExpansion, PermissionDenied, PostToolBatch, and MessageDisplay;
  also TaskCreated, TeammateIdle, ConfigChange, CwdChanged, WorktreeCreate,
  and WorktreeRemove; and PostCompact, Elicitation, ElicitationResult.
- Policy: any event name in the official hooks doc is valid even if newer
  than this overlay — verify against hooks.md, do not penalize.
- Per-event context fields: see
  [references/reference.md](references/reference.md).
- Hook types (5, lowercase in JSON): `command`, `prompt`, `agent`, `http`,
  `mcp_tool`. A command hook may set `"shell": "powershell"`.
- Blocking via stdout JSON: `hookSpecificOutput.permissionDecision`
  (`allow` | `deny`) plus `permissionDecisionReason`.
- Hooks may live in multiple files (`hooks.json`, `security-hooks.json`, …),
  inline in plugin.json, or in agent frontmatter (ignored for plugin-shipped
  agents — see §3).

### Exit codes

- `0` — success. stdout goes to debug output, EXCEPT for UserPromptSubmit,
  UserPromptExpansion, and SessionStart, where stdout is injected as
  context.
- `2` — blocking. stderr is fed back to Claude; only blockable events honor
  it — it is ignored by PostToolUse, PostToolUseFailure, Notification,
  SessionStart, SessionEnd, InstructionsLoaded, StopFailure, and
  MessageDisplay.
- `1` and `3+` — non-blocking error.

### Matchers

Exact string, pipe-separated list, or regex. MCP tools match as
`mcp__<server>__<tool>`, including wildcard-suffix forms.

## 7. hooks.json format

- Shape: top key `hooks` → event names → array of `{matcher, hooks: [...]}`
  → each entry `{type, <field named after the type>}` (the payload field
  name equals the type).
- Lives at `.claude/hooks.json` in a project, or inside a plugin at
  `<plugin>/hooks/hooks.json`.
- Script paths via `${CLAUDE_PLUGIN_ROOT}`.

## 8. .mcp.json

- A standalone repo-root file — NOT inside settings.json (as with Gemini)
  and NOT config.toml (as with Codex).
- Top key `mcpServers`; per-server `command` and `args`, plus optional `cwd`
  and `env`; `type: stdio`.
- Within a plugin the file sits at `<plugin>/.claude-plugin/.mcp.json`, or
  alternatively at `<plugin>/.mcp.json`.

## 9. marketplace.json (`.claude-plugin/marketplace.json`)

- Top level: `name` and `plugins[]`; `owner` `{name}` is required at top for
  validation.
- Entry fields: `name`; `source`, shaped as
  `{source: github, repo: <owner>/<repo>}`; then `description`, `version`,
  `author`, `category` (belongs HERE, not in plugin.json), `repository`,
  `license`.
- Source types enum: github, git, url, npm, file, directory, hostPattern.
- Archives ending in `.zip` are accepted by `--plugin-url` / `--plugin-dir`
  (v2.1.x).
- Namespacing after install: skills are namespaced `/plugin:skill`; commands
  and agents keep short names.

## 10. CLAUDE.md and memory

- Loaded from the project root, `.claude/`, `~/.claude/`, and parent
  directories; closer-to-root takes priority. `claudeMdExcludes` filters
  what loads.
- `@` import syntax; imports MUST reference existing files; topic files live
  under `.claude/memory/*.md`.
- Multi-tool canonical form: CLAUDE.md reduced to the single line
  `@AGENTS.md` (see the floor).
- Body conventions: build/test commands, architecture, prerequisites.
- Auto memory (v2.1.59+): `~/.claude/projects/<slug>/memory/`, controlled by
  `autoMemoryEnabled` and `autoMemoryDirectory`. At startup MEMORY.md is
  read up to ~200 lines / 25 KB, and topic files load with it. MEMORY.md is a
  frontmatter-less one-line-per-entry index and is not scored; topic files
  MUST carry frontmatter `name`/`description`/`type` with `type` one of
  user | feedback | project | reference. Every file must be indexed in
  MEMORY.md (orphans get flagged), and no entry may point at a removed
  file. Details in [references/reference.md](references/reference.md).

## 11. Settings

- Layers: plugin-root `settings.json` (shipped defaults);
  `~/.claude/settings.json` (global); project `.claude/settings.json`
  (committed); `.claude/settings.local.json` (gitignored). Per-plugin
  config: `.claude/<plugin-name>.local.md` with YAML frontmatter.
- Documented keys (full table in the reference): `permissions` (including
  `additionalDirectories`), `hooks`, `model`, `disableSkillShellExecution`,
  `env`, `statusLine`, `agent`, `effortLevel`, `language`, `outputStyle`,
  `enabledPlugins`, `claudeMd`, `claudeMdExcludes`, `autoMemoryEnabled`,
  `autoMemoryDirectory`, `sandbox.enabled`, `extraKnownMarketplaces`,
  `strictKnownMarketplaces`.
- `theme` is NOT a documented key (removed 2026-06-07). The list is
  representative, not exhaustive — treat plausible unknown keys as advisory
  findings only.
- NEVER put `bypassPermissions: true` in a shared settings file.

## 12. LSP servers, monitors, tool catalog (pointers)

- **LSP servers**: `.lsp.json` or plugin.json `lspServers`; STABLE in 2026
  (experimental in 2025). Required per server: `command` and
  `extensionToLanguage`. Full schema in the reference.
- **Monitors**: `monitors/monitors.json` or `experimental.monitors`; STABLE
  in 2026; requires v2.1.105+. Full schema in the reference.
- **Tool catalog**: built-in tool names are case-sensitive; never flag a
  well-formed but unknown tool name — the catalog grows. Current list,
  renames, and removals in the reference; the authoritative source is the
  tools-reference docs page.

## 13. Naming

Plugin, command, agent, and script files are kebab-case (Python scripts may
be snake_case).

## 14. Quality checklists

- **Commands**: specific description; numbered, unambiguous steps covering
  all paths; least-privilege tool list matching `allowed-tools`; an output
  template; error fallbacks.
- **Agents**: `<example>` blocks present; model fits the task;
  least-privilege tools; body carries mission, instructions, and an output
  spec.
- **Skills**: trigger-phrase description; body under 500 lines; patterns
  over theory; runnable code examples; scope boundaries plus
  cross-references.
- **Rules**: bold-imperative lead, rationale, positive framing, specific and
  testable, no duplication of automated enforcement.

## 15. Authoritative docs

Eleven pages under `code.claude.com/docs/en/`: the docs map (overview),
skills, hooks, plugins, plugins-reference, sub-agents, settings, memory,
slash-commands, tools-reference (the authoritative tool catalog), and
plugin-marketplaces.

## 16. Scope and uncertainty

- Version gates are approximate where flagged: TodoWrite going default-off
  near v2.1.142 and `defaultEnabled` near v2.1.154 are confirmed changes
  with approximate version numbers.
- The shapes of `userConfig`, `channels`, and `dependencies` are not
  field-enumerated here.
- The full marketplace schema is not folded in.
- This overlay covers Claude Code schemas only; universal rules live in the
  [floor](../conventions/SKILL.md), and penalty values live in the suite
  scoring rubric.
