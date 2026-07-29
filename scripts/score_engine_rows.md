# Score-engine row ledger (E3.3 / vibe-28)

Every row of every penalty table in skills/scoring/SKILL.md, classified for
scripts/score_engine.py:

- `mechanical` — the engine deducts; the Predicate column quotes or states the
  objective predicate from the owning text.
- `advisory-zero` — the engine never deducts on the row, because no objective
  predicate exists in the owning text **that the engine can evaluate from the
  scored file's own bytes and path**. Four honest sub-reasons appear below:
  the condition is a judgment word with no stated criteria; the condition is a
  cross-file or whole-plugin fact a per-file evaluation cannot observe; the
  owning text itself marks the row advisory; or no type produced by the
  deterministic path classifier routes to the table at all (most Tier
  2-Codex/-Antigravity sidecar tables — their artifacts classify as
  `document`/`framework-agent` under commands/shared/classify.md, and type
  tables apply per type).

For each scored file the engine emits every advisory-zero row of the file's own
type tables (including the tier-conditioned rows of its tier) as a zero-penalty
advisory; rows of unrouted tables are emitted for no one, because no scored
file belongs to them.

Ground truth for the Skills classifications: the hand-computed worksheet
tests/fixtures/nl-audit/defective-skill/README.md (cited as "worksheet #n").

## Type routing

The engine classifies each record's path with the same first-match rules as
commands/shared/classify.md (a record may instead carry an explicit type). The
tables below bind to types like this:

| Table | Engine type(s) |
|---|---|
| Skills | `skill` |
| Agents | `agent` |
| Commands | `command`, `user-command` |
| Shared Partials | `shared-partial` |
| Rules | `rule` |
| Hooks — universal + Hooks (Claude Code) | `hook-config` at tier 2-Claude |
| Hooks (Codex CLI) | `hook-config` at tier 2-Codex (explicit-type records only — no classify.md path routes there) |
| Hooks (Antigravity) | `hook-config` at tier 2-Antigravity — advisory by its owning text |
| plugin.json (Claude) | `manifest` (content rows tier-conditioned to 2-Claude) |
| .mcp.json | `mcp-config` (server-command row tier-conditioned to 2-Claude) |
| .lsp.json | `lsp-config` |
| Settings files | `settings` (hook-definitions row tier-conditioned to 2-Claude) |
| CLAUDE.md | `claude-md` |
| Memory files | `memory` |
| All types: vague quantifiers (R01) | every scored file |
| .codex-plugin/plugin.json, .agents/plugins/marketplace.json, agents/openai.yaml, gemini-extension.json, .gemini/commands/*.toml, .codex/config.toml, monitors/monitors.json | no route — see the advisory-zero definition above |
| All types: vocabulary drift (R51) | ship-disabled; advisory only |
| Cross-component | whole-plugin lint, not per-file — no per-file route |

Types with no table (`marketplace`, `plugin-config`, `prompt`, `framework-*`,
`design-doc`, `document`) take only the all-types R01 rows, per the rubric's
closing principle: "any finding with no specific penalty-table row to cite gets
dropped."

## Tier classification

Each files[] entry carries a `tier`, classified deterministically per file from
its canonical path — the scoring skill's tier classifier ("**Tier 1** —
open-spec artifacts. **Tier 1.5** — open-spec corpora. **Tier 2** — overlays
specific to each tool: 2-Claude, 2-Codex, 2-Antigravity.") applied through the
conventions overlay table ("classify its target tool from the canonical path it
lives under"):

| Tier | Path / tool markers (first match wins) |
|---|---|
| `2-Claude` | a `.claude/` or `.claude-plugin/` tree; the Claude-marked per-file names `CLAUDE.md`, `.mcp.json`, `.lsp.json`, `monitors/monitors.json`; `hooks/**/*.json` (the Claude plugin hooks config the Tier 2-Claude hook table binds to) |
| `2-Codex` | a `.codex/`, `.codex-plugin/`, or `.agents/` tree; `AGENTS.md` (conventions overlay table); `agents/openai.yaml` (the scoring skill's own heading) |
| `2-Antigravity` | a `.gemini/` or `.agent/` tree; `gemini-extension.json` |
| `1` | everything else — an open-spec artifact |

Tier 1.5's entire definition in the owning text is the quoted sentence above —
"**Tier 1.5** — open-spec corpora." — and that is a property of a *collection*:
a corpus is a set of artifacts, and no sentence anywhere in the owning texts
states a predicate a single file's bytes or path could satisfy to be "a
corpus". Of the definition's two markers, "open-spec" is per-file observable
(the file sits under no tool tree — the same marker as Tier 1) and "corpora"
is not, so the per-file classifier has no per-file predicate to implement and
never emits `1.5`. The boundary is explicit rather than silent: every tier-`1`
files[] entry carries a zero-penalty tier-boundary advisory ("tier boundary:
emitted 1 (open-spec artifact); Tier 1.5 (open-spec corpora) is a collection
property with no per-file predicate, so whether this file belongs to an
open-spec corpus stays with the narrating agent"), and the 1-vs-1.5 judgment
belongs to the narrating agent. The tier conditions tool-specific rows — the
scorer gauntlet's do-not-penalize principle: "a row from another type's table
or another tool's overlay does not apply". A row bound to one tool's tier
never fires on another tier's artifacts; the tier-conditioned rows are marked
in their Predicate cells below.

## File-level parse semantics (not a table row)

The rubric's file-level semantics assign every artifact type a parse-failure
penalty: "Malformed frontmatter or config (YAML/JSON/TOML that fails to parse)
takes the parse-failure penalty for that artifact type: **-25**." The engine
implements it as the `frontmatter parse` finding on markdown types whose
opening `---` fence fails to parse (a file with no fence has no frontmatter —
its presence rows fire instead), and as the `valid JSON` finding on JSON types
with no dedicated parse row (the Claude plugin.json table). Rows that need the
parsed structure are skipped after a parse failure; rows that do not (body
length, R01, command safety) are still scored. Artifact frontmatter is parsed
by the engine's own permissive stdlib parser — every schema-conforming shape
parses: nested block mappings (`metadata:`), sequences, flow mappings
(`{author: x}`) including multiline flow mappings and sequences
(bracket-matched across lines), hyphenated keys (`allowed-tools`), quoted
scalars, block scalars — and -25 fires ONLY on a true structural failure: no
closing `---` fence, a non-mapping top level, unbalanced quotes or brackets,
tab-broken indentation, or trailing text after a closed flow collection
(`key: {a: b} garbage` has no reading under the schema space, so accepting it
would be a false parse). (`.vibe-suite.md` itself keeps the strict fail-closed
grammar of scripts/lib/config.py; the permissive grammar exists because
artifacts are scored, not refused.)

## Skills

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | name present | missing | mechanical | the parsed frontmatter has no `name` key — objective, mechanically checkable (worksheet #1) |
| -- | name matches parent dir | frontmatter name differs from parent directory name (conventions §5; open-spec MUST) | mechanical | quoted predicate: "a single-line diff of the frontmatter name against the basename of the containing directory" (rubric's name-matches-parent-dir note); with no frontmatter name there is nothing to diff, so the row cannot fire (worksheet #1) |
| R04 | description present | missing | mechanical | the parsed frontmatter has no `description` key — objective, mechanically checkable |
| R04 | trigger quality | generic description (at most one specific phrase) | advisory-zero | worksheet #2: "'Generic' is a judgment word" and "specific phrase" has "no mechanical definition anywhere in the rubric" — deciding whether a phrase is specific is not mechanical |
| R04 | description length | 500–800 chars | mechanical | counted in CHARACTERS of the description value: fires when 500 <= chars <= 800 (worksheet #2 measures the fixture's description in characters: 38) |
| R04 | description length | over 800 chars | mechanical | counted in CHARACTERS of the description value: fires when chars > 800; mutually exclusive with the 500-800 band |
| R05 | body length | 400–500 lines | mechanical | counted in lines of the MARKDOWN BODY — the frontmatter block, fences included, is excluded (the table and conventions call this body length): fires when 400 <= body lines <= 500; "a mutually exclusive band" that never stacks (worksheet #3). A config `threshold: N` replaces the 500 upper boundary only; the 400 lower boundary stays |
| R05 | body length | over 500 lines | mechanical | fires when body lines > 500 (or > the overridden upper boundary) — the fixture's 580-line body takes exactly this -10 (worksheet #3) |
| R06 | code examples | complex concepts but no examples | advisory-zero | worksheet #5: the row penalizes only absence and "complex concepts" is a judgment call with no stated criteria in the owning text |
| R06 | code examples | no examples at all in a technical skill | advisory-zero | worksheet #5: "technical skill" is a judgment call with no stated criteria in the owning text |
| R06 | example blocks | zero `<example>` blocks on a `user_invocable: true` skill | mechanical | implemented: fires when the parsed frontmatter sets `user_invocable: true` and the file contains zero literal `<example>` blocks — both facts are mechanically checkable (worksheet #5 notes the row "cannot fire" without `user_invocable: true`) |
| R07 | scope note | no scope note / cross-references | advisory-zero | worksheet #8: the rubric's scope-note discipline says R07 fires only "even though related skills exist", and whether skills are related is a judgment with no stated criteria; the rubric also never defines what a scope note looks like, so any detector (heading text, `../` links) would be an invented predicate |

## Agents

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| R09 | description present | missing | mechanical | the parsed frontmatter has no `description` key — objective |
| R09 | example blocks | exactly 1 example | mechanical | the count of literal `<example>` blocks in the file equals 1 — objective (the -5 band of the same count as the next row) |
| R09 | example blocks | zero examples | mechanical | the count of literal `<example>` blocks in the file equals 0 — objective; R09's own text pins the minimum at 2 |
| R10 | model declared | not declared | mechanical | the parsed frontmatter has no `model` key — objective |
| R10 | model appropriate | wrong tier for the task (e.g. opus for parsing) | advisory-zero | "wrong tier for the task" requires judging what the task is; R10's haiku/sonnet/opus guidance states no mechanical criteria |
| R11 | tools declared | not declared | mechanical | the parsed frontmatter has no `tools` key — objective |
| R11 | unused tools | each declared-but-unused tool | advisory-zero | whether a natural-language body "uses" a declared tool is a judgment call — the engine cannot execute the prose to find out |
| R12 | output format | no output format spec in body | mechanical | R12 (verbatim): "Define the agent's output format in its body", and conventions §3: "the body of each command and agent spells out its exact output structure" — the engine tests the stated section's presence: a markdown heading whose text contains "output" (case-insensitive); absent → -10 |
| R11 | write on read-only | audit/review/scan agent declares Write or Edit | advisory-zero | deciding that an agent IS an audit/review/scan agent is a judgment about its purpose with no stated criteria (a name probe would misfire on any differently-named reviewer) |

## Commands

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | description present | missing | mechanical | the parsed frontmatter has no `description` key — objective |
| R18 | argument-hint present | takes input but no hint | advisory-zero | "takes input" is a judgment about the command's semantics; no mechanical definition exists in the owning text |
| R14 | steps numbered | multi-step body without numbered steps | advisory-zero | "multi-step body" is a judgment call with no stated criteria |
| R15 | empty input handling | none | advisory-zero | whether prose handles an empty `$ARGUMENTS` is a semantic reading, not a mechanical check |
| R16 | output format | none defined | advisory-zero | R16 (verbatim) demands the template itself: "'Show the results' is not a specification; give the report template itself" — whether inline prose or a fenced block constitutes the template is a judgment; a section-name probe would misfire on commands that define output by template without a named section (this suite's own score.md does exactly that) |
| R17 | error paths | no handling for missing files / bad data | advisory-zero | whether error handling is "defined" in prose is a semantic judgment with no stated criteria |

## Shared Partials

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| R19 | `user-invocable: false` | missing or true | mechanical | the parsed frontmatter's `user-invocable` key is absent or not `false` — objective (the hyphenated key parses under the artifact key alphabet) |
| R20 | purpose clear | description does not state it is a partial | advisory-zero | whether a description "states it is a partial" is a semantic judgment; a substring probe would misfire on this suite's own partials, whose descriptions open with "Shared:" |

## Rules

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| R21 | description present | missing frontmatter description | mechanical | the parsed frontmatter has no `description` key — objective |
| R21 | bold imperative | no bold imperative opening | advisory-zero | whether bold text is an imperative is a grammatical judgment with no stated criteria |
| R21 | rationale | no rationale after the imperative | advisory-zero | recognizing a rationale is a semantic judgment |
| R22 | enforceability | not specific/testable | advisory-zero | R22 itself defines enforceability by what "a reviewer" can verify — a judgment |
| R23 | budget | rule file over 500 lines | mechanical | the file's physical line count exceeds 500 (the condition names the rule file); a config `threshold: N` replaces the 500 boundary (conventions §6 example: "R23 `threshold: 800` (rules budget, from 500 lines)") |
| R26 | conflicts | direct contradiction with another rule in the same set | advisory-zero | detecting a semantic contradiction across rules is judgment, and cross-file |
| R24 | duplicates tooling | restates eslint/ruff/clippy checks | advisory-zero | deciding that prose restates a linter's check is a semantic judgment |

## Hooks — universal (all tools)

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid syntax | config fails to parse (JSON or TOML per tool) | mechanical | `hooks/**/*.json` is JSON: json.loads fails → -25; rows needing the parsed structure are then skipped, text-level rows still fire |
| R29 | scripts exist | referenced script missing | advisory-zero | the owning text never defines how "the referenced script" is extracted from a free-form command string (`python3 -m pkg` has no script path; env-var-prefixed paths resolve at runtime); the Hook → script edge belongs to plugin-discover's whole-plugin cross-reference map |
| -- | command safety | dangerous patterns (`rm -rf`, `git push --force`, `DROP TABLE`) | mechanical | the condition quotes its own predicate: the file text contains any of the three literal patterns |
| -- | matcher regex valid | does not compile | mechanical | every string value under a `matcher` key anywhere in the parsed JSON must compile as a regex; any failure → -10 |
| -- | timeout reasonable | timeout over 30s | mechanical | any numeric value under a `timeout` key anywhere in the parsed JSON exceeding 30 → -5 |

## Hooks (Claude Code, Tier 2-Claude)

Tier-conditioned: these rows bind to `hook-config` artifacts of tier
**2-Claude** only (the path route `hooks/**/*.json` is the Claude plugin hooks
config and classifies 2-Claude; an explicit-type record under another tool's
tree never takes these rows).

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| R27 | event names valid | unrecognized event; confirmed Claude events: SessionStart, SessionEnd, UserPromptSubmit, PreToolUse, PostToolUse, PermissionRequest, Stop, StopFailure, FileChanged | mechanical | on a 2-Claude-tier hook-config: event names are the string values of `event` keys plus the keys of any mapping under a `hooks` key; a name outside the confirmed list (and not merely a case variant of one) → -15 |
| R27 | case correct | wrong case (e.g. lowercase pretooluse) | mechanical | on a 2-Claude-tier hook-config: an extracted event name that case-insensitively equals a confirmed event but differs in case → -10 |
| -- | hook type valid | unrecognized type; confirmed types: command, http, mcp_tool, prompt, agent | mechanical | on a 2-Claude-tier hook-config: any string value under a `type` key outside the confirmed list → -10 |
| -- | MCP matcher format | targets an MCP tool without the `mcp__<server>__<tool>` pattern | advisory-zero | whether a matcher "targets an MCP tool" when it does not already carry the `mcp__` pattern is not objectively decidable from the config |

## Hooks (Codex CLI, Tier 2-Codex)

Tier-conditioned: no classify.md path yields a Codex hook-config type, but the
record protocol admits an explicit-type `hook-config` record for a config under
a Codex tree (e.g. `.codex/hooks.json`, tier 2-Codex). On such an artifact the
two R27 rows carry the same objective list-membership predicate as the Claude
table — against the Codex event list — and are mechanical; they never fire on
another tier's artifacts.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| R27 | event names valid | unrecognized event; confirmed Codex events: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PermissionRequest, PreCompact, PostCompact, SubagentStart, SubagentStop, Stop | mechanical | on a 2-Codex-tier hook-config: an extracted event name outside the confirmed Codex list (and not merely a case variant of one) → -15 |
| R27 | case correct | wrong case | mechanical | on a 2-Codex-tier hook-config: an extracted event name that case-insensitively equals a confirmed Codex event but differs in case → -10 |
| -- | hooks config key | config.toml uses deprecated `[features].codex_hooks` instead of `[features].hooks` (renamed around CLI 0.129) | advisory-zero | the owning text itself marks the penalty "(advisory)"; the condition also names config.toml, a different file — emitted as an advisory on 2-Codex-tier hook-configs |

## Hooks (Antigravity/Gemini lineage, Tier 2-Antigravity)

The owning text marks the entire table ADVISORY with `confidence: low`
(multi-tool design decision #3): even on a 2-Antigravity-tier hook-config
(explicit-type record under `.gemini/` or `.agent/`) the engine deducts
nothing and emits the two rows as advisories.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| R27 | event names valid | unrecognized event; confirmed events: SessionStart, BeforeAgent, BeforeModel, BeforeToolSelection, BeforeTool, AfterTool, AfterModel, AfterAgent, SessionEnd, Notification, PreCompress | advisory-zero | the owning text holds every Antigravity hook finding advisory |
| R27 | case correct | wrong case | advisory-zero | same — advisory by the owning text |

## plugin.json (Claude, `.claude-plugin/plugin.json`)

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | name present | missing | mechanical | on a 2-Claude-tier manifest (the table heading names `.claude-plugin/plugin.json`): the parsed JSON object has no `name` value — objective (parse failure itself takes the file-level -25 and skips these rows) |
| -- | version is semver | present but invalid | mechanical | on a 2-Claude-tier manifest: a present `version` value that does not match the semver.org `MAJOR.MINOR.PATCH[-prerelease][+build]` shape → -10; an absent version never fires ("present but invalid") |
| -- | description present | missing | mechanical | on a 2-Claude-tier manifest: the parsed JSON object has no `description` value — objective |

## .codex-plugin/plugin.json (Tier 2-Codex)

No route: the file's parent is `.codex-plugin`, not `.claude-plugin`, so
classify.md's manifest row does not match and the path classifies `document`;
type tables apply per type. Every row is advisory-zero as unrouted.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid JSON | parse fail | advisory-zero | unrouted — see the table note |
| -- | name present | missing | advisory-zero | unrouted |
| -- | name kebab-case | mixed case or underscores | advisory-zero | unrouted |
| -- | version semver | invalid | advisory-zero | unrouted |
| -- | description present | missing | advisory-zero | unrouted |
| -- | component paths relative | skills/mcpServers/apps/hooks paths absolute or missing the `./` prefix | advisory-zero | unrouted |

## .agents/plugins/marketplace.json (Tier 2-Codex)

No route: classify.md's marketplace row requires the `.claude-plugin` parent;
`.agents/plugins/marketplace.json` classifies `document`. (The Claude
`marketplace` type itself has NO table in the rubric — it takes only the R01
rows.) Every row is advisory-zero as unrouted.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid JSON | parse fail | advisory-zero | unrouted — see the table note |
| -- | name present | missing | advisory-zero | unrouted |
| -- | plugins array present | missing or empty | advisory-zero | unrouted |
| -- | per-plugin source valid | source.source not one of github/git/local, or a required repo/path missing | advisory-zero | unrouted |
| -- | per-plugin category present | missing (informational) | advisory-zero | unrouted; the owning text marks it informational |

## agents/openai.yaml (Codex skill sidecar, Tier 2-Codex)

No route to this table: `agents/openai.yaml` matches classify.md's
`**/agents/*.yaml` row and classifies `framework-agent`, a type with no table.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid YAML | parse fail | advisory-zero | unrouted — see the table note |
| -- | sidecar colocated | not in the same directory as a SKILL.md | advisory-zero | unrouted |
| -- | interface.display_name present | missing | advisory-zero | unrouted; the owning text marks it informational |

## gemini-extension.json (Tier 2-Antigravity)

No route: classifies `document`; the owning text also holds the table ADVISORY
until the spec stabilizes.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid JSON | parse fail | advisory-zero | unrouted — see the table note |
| -- | name present | missing | advisory-zero | unrouted |
| -- | version present | missing | advisory-zero | unrouted |
| -- | contextFileName includes AGENTS.md | multi-tool config should include AGENTS.md, not just GEMINI.md | advisory-zero | unrouted; the owning text marks it "(advisory; multi-tool nudge)" |

## .gemini/commands/*.toml (legacy/transitional, Tier 2-Antigravity)

No route: classifies `document`.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid TOML | parse fail | advisory-zero | unrouted — see the table note |
| -- | prompt field present | missing (required) | advisory-zero | unrouted |
| -- | description field present | missing (auto-generated from filename; explicit is better) | advisory-zero | unrouted |

## .mcp.json (Claude, repo root)

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid JSON | parse fail | mechanical | json.loads fails → -25 |
| -- | server command present | MCP entry missing its command field | mechanical | on a 2-Claude-tier mcp-config (the table heading says "Claude, repo root"): any entry under the parsed `mcpServers` mapping without a truthy `command` value → -15 |

## .codex/config.toml (Tier 2-Codex)

No route: classifies `document`.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid TOML | parse fail | advisory-zero | unrouted — see the table note |
| -- | deprecated `[features].codex_hooks` | should be `[features].hooks` (~CLI 0.129) | advisory-zero | unrouted; the owning text marks it "(advisory)" |
| -- | per-MCP command present | `[mcp_servers.<id>]` missing command | advisory-zero | unrouted |

## .lsp.json (Tier 2-Claude)

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid JSON | parse fail | mechanical | json.loads fails → -25; the owning text scopes this table to JSON-parse-only until detailed schemas land |

## monitors/monitors.json (Tier 2-Claude)

No route: `monitors/monitors.json` matches no classify.md row and classifies
`document`.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid JSON | parse fail | advisory-zero | objective predicate, but unrouted — see the table note |

## Settings files (.claude/settings.json, .claude/settings.local.json)

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | valid JSON | parse fail | mechanical | json.loads fails → -25 |
| -- | no hardcoded secrets | API keys/tokens/passwords present | advisory-zero | recognizing a secret is a judgment; the owning text states no pattern list |
| -- | permission mode sanity | bypassPermissions enabled in SHARED project settings (not .local) | advisory-zero | "enabled" requires knowledge of the settings schema's permission structure that the owning text does not supply; a substring probe cannot tell an enabled mode from a mention |
| -- | recognized keys | unknown top-level keys | advisory-zero | the owning text supplies no list of recognized settings keys to diff against |
| -- | hook definitions valid | hooks key present → check event names + case | mechanical | on a 2-Claude-tier settings file (the table heading names `.claude/settings*.json`; the row checks Claude events): when the parsed object carries a top-level `hooks` mapping, each key that is not a confirmed Claude event (the Hooks Claude table's list) → -10 per invalid, per the row's own "per invalid" |

## CLAUDE.md

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| R49 | file exists | no CLAUDE.md in plugin root | advisory-zero | the row penalizes the FILE's absence; a per-file evaluation only ever sees files that exist — a whole-plugin fact, not observable from the scored file |
| -- | under 200 lines | exceeds 200 lines | mechanical | the file's physical line count exceeds 200 → -5 |
| R38 | actionable content | no actionable guidance (filler only) | advisory-zero | "actionable" and "filler" are judgment words with no stated criteria |
| R33 | build/run command | absent | advisory-zero | recognizing that prose contains a build/run command is a semantic judgment |
| R34 | test command | absent | advisory-zero | same as R33 — semantic judgment |
| R35 | architecture overview | no what-lives-where description | advisory-zero | "what-lives-where description" is a judgment with no stated criteria |
| R36 | valid `@` imports | an `@` import references a nonexistent file | mechanical | a line consisting solely of `@<path>` is the documented import form; a relative import whose target does not exist beside the file → -10 (absolute and `~` imports are outside the scan root and are not judged) |
| R37 | no stale file refs | mentions removed files/functions | advisory-zero | knowing a mentioned file was "removed" needs repository history, not the file's bytes |
| R38 | actionability ratio | more than 60% description vs instruction | advisory-zero | classifying each line as description or instruction is a judgment; the owning text defines no procedure |
| -- | prerequisites section | no required-tools/versions/setup section | advisory-zero | what counts as such a section is a judgment; no section name is pinned by the owning text |
| R39 | no rule conflicts | CLAUDE.md says X while a .claude/rules/ file says not-X | advisory-zero | semantic contradiction across files — judgment, and cross-file |

## Memory files (`.md` under `~/.claude/projects/*/memory/`)

The table carries no Condition column: each check fails or passes. A memory
file reaches the engine only when its path is scan-root-relative and contains
`/memory/` — the record protocol refuses `~`-anchored paths.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | has YAML frontmatter | — | mechanical | the file does not open with a `---` fence → -15 (an opening fence that fails to parse is the file-level -25 instead) |
| -- | name in frontmatter | — | mechanical | the parsed frontmatter has no `name` key → -10 |
| -- | description in frontmatter | — | mechanical | the parsed frontmatter has no `description` key → -10 |
| -- | type in frontmatter (values: user/feedback/project/reference) | — | mechanical | the `type` key is absent or its value is outside the closed four-value list → -5 |
| -- | content matches declared type | — | advisory-zero | whether content "matches" a type is a semantic judgment |
| -- | referenced in MEMORY.md index | — | advisory-zero | a cross-file fact; the owning text also never defines what form a reference in the index takes |
| R37 | no stale content (refs to removed files/functions) | — | advisory-zero | needs repository history, not the file's bytes |

## All types: vague quantifiers

The carve-out passage, quoted verbatim and in full from
skills/conventions/SKILL.md §4:

> Carve-outs (no penalty):
>
> - `relevant` inside a markdown header;
> - `relevant to <named-scope>`;
> - any listed term followed by a measurable-criterion clause.

The passage names its own form for each of the first two carve-outs and
enumerates NO example form for the third — no numeric example, no
spelled-quantity example, no status-value example, nothing at all. The owning
text's carve-out is therefore open-ended; the engine encodes its enumerated
forms exactly and no others: the two `relevant` forms as written, and for the
third a closed quantity reading — a digit, or a spelled-out cardinal from the
engine's `_NUMBER_WORDS` list, in the remainder of the term's own sentence on
its line. A counted term is by definition one where none of the encoded forms
follow. Because the third carve-out's wording admits readings the closed
encoding cannot decide (a criterion stated as an explicit status value, say),
the residual ambiguity is surfaced rather than absorbed: every file with a
kept R01 finding carries one borderline advisory — "R01 counted; carve-out
forms absent -- if this is measurable-in-context, suppress via
rule_overrides.R01" — and the rubric's own config override mechanism is the
sanctioned escape. Widening the encoding itself (a unit lexicon, a status-word
list, next-line context) would be inventing carve-out forms the owning text
never wrote.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| R01 | vague quantifier | each occurrence of: appropriate, relevant, as needed, sufficient, adequate, reasonable, properly, correctly, some, several, various — without measurable criteria | mechanical | token-bounded count of the 11 listed words, -2 per occurrence, minus the three conventions §4 carve-outs exactly as stated and no further contextual rules: `relevant` on a markdown heading line; `relevant to <named-scope>` (the term followed by `to` and a named scope); and the third, quoted verbatim — "any listed term followed by a measurable-criterion clause". The owning text supplies no finer definition or example of that clause, so its mechanical encoding is closed and exactly this: the remainder of the term's own sentence on its line carries a quantity — a digit, or a spelled-out cardinal from the engine's closed `_NUMBER_WORDS` list (zero–twenty, the tens thirty–ninety, hundred, thousand, million). "appropriate timeout of one minute" and "at most 3 retries" are carved out; "appropriate handling" deducts. The encoding is deliberately no wider: no unit lexicon, no next-line context, no part-of-speech judgment — a cardinal used as a pronoun ("until one loads") is mechanically indistinguishable from a quantity, and the encoding errs on the rubric's own closing principle (no citable criterion → no finding, so ambiguity resolves toward not deducting). Every kept R01 finding is accompanied by the borderline advisory described above this table, with `rule_overrides.R01` as the sanctioned escape. Worksheet #10 records the fixture's 12 lexical occurrences, 11 counted after this carve-out |
| R01 | cap | cap on total vague-quantifier penalty | mechanical | the summed vague-quantifier penalty clamps at -20 (or the R01 `threshold` override): the fixture's 11 counted x -2 = -22 lands at -20 (worksheet #10: "cap binds") |

## All types: vocabulary drift (R51) — opt-in, disabled by default

Ship-disabled: without `enabled: true` in the config the penalty is zero by
rule. The engine ships no registry.yaml reader — the owning text never defines
the registry's schema (how canonical and deprecated terms are declared) — so
even when enabled, the misconfigured row's own "0 (advisory only)" applies and
the engine emits one R51 advisory.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| R51 | deprecated term | each occurrence of a `deprecated:` term from registry.yaml, within the artifact's scope | advisory-zero | the registry.yaml schema is undefined in the owning text, so term extraction has no objective definition; ship-disabled besides |
| R51 | drift cap | cap per file | advisory-zero | caps a penalty that never accrues — see the previous row |
| R51 | misconfigured | enabled but vocabulary_skill unset / no registry.yaml | advisory-zero | the row's own penalty is "0 (advisory only)"; the engine emits it whenever R51 is enabled |

## Cross-component (`--plugin` flag; whole-plugin lint, not per-file)

The table's own heading scopes it to whole-plugin lint — a different scoring
scope than the per-file score this engine produces (worksheet #9). No per-file
route exists.

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | broken partial refs | a command references a nonexistent commands/shared/X.md | advisory-zero | whole-plugin scope — see the table note |
| -- | broken skill refs | an agent references an uninstalled plugin skill | advisory-zero | whole-plugin scope |
| -- | missing scripts | a hook references a nonexistent script | advisory-zero | whole-plugin scope |
| -- | orphaned files | agent/command/skill referenced by nothing | advisory-zero | whole-plugin scope (worksheet #9) |
| -- | contradictions | two rules/instructions in the same plugin directly contradict | advisory-zero | whole-plugin scope, and semantic judgment besides |

## Worksheet defect classes with no penalty-table row

The rubric's closing principle: "any finding with no specific penalty-table row to
cite gets dropped." These seeded classes therefore deduct nothing; the engine emits
each as an advisory on every scored skill so the narrating agent sees them without
a penalty existing.

| Rule | Check | Source | Class | Justification |
|------|-------|--------|-------|---------------|
| -- | broken references link | worksheet #4 | advisory-zero | no Skills-table row penalizes a dead link inside a skill body; the dead-reference rows belong to other artifact types or scopes (R36, R29, Cross-component), and the closing principle drops any finding with no row to cite |
| -- | pseudocode example | worksheet #5 | advisory-zero | the anti-pseudocode wording ("Use real syntax, never pseudocode") lives only in R06's rule text with no penalty row in the Skills table |
| -- | domain mixing | worksheet #6 | advisory-zero | no row in any table carries a "mixing" condition for skills; "mixing" is a judgment word with no stated criteria in the owning text |
| -- | redundant content | worksheet #7 | advisory-zero | "redundant" is a judgment word with no stated criteria; R02 has no penalty row in any table |
| -- | orphaned registration | worksheet #9 | advisory-zero | orphan and broken-registration rows sit only in the Cross-component table (whole-plugin lint, not per-file) — a different scoring scope than this per-file score |
