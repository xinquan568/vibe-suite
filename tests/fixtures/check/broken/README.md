# vibe-29 worksheet — hand-derived oracle

Authored BEFORE any engine code (the vibe-28 oracle-first lesson); revised by hand at
step-9 iteration 1 — again before the engine revision it governs — to close review findings
on edge-grammar narrowness, hook extraction, R51 registry semantics, and the missing
plugin-token cases. Every determination cites its governing text. Orphan candidates are the
non-root components — skills, agents, shared partials, scripts (commands, hooks.json, and
CLAUDE.md are reference ROOTS per `commands/shared/plugin-discover.md`'s map: edges run
command→agent, command→partial, agent→skill, hook→script; CLAUDE.md listings add
root→target edges per F4.3).

## Edge grammar (per `commands/shared/plugin-discover.md`, the map's owning text)

1. **Command → agent** — "an agent named or dispatched from a command's body": an edge
   exists when the body (below frontmatter) contains the agent's `agents/<name>.md` path in
   any form (Markdown link, inline code, plain text) OR the agent's name as a whole word.
   **Orphan-input only** — F4.3's reportable list does not include this direction, so a
   dangling agent name is never a reference-integrity issue.
2. **Command → shared partial** — "a `commands/shared/<name>.md` path referenced in a
   body": any body token matching `(commands/)?shared/<name>.md` — Markdown link target,
   inline code, or plain text — normalized to `commands/shared/<name>.md`. Reportable
   (F4.3 `command-partial`). One issue per distinct (source, target) pair.
3. **Agent → skill** — "skills declared in an agent's frontmatter or referenced by name in
   its body": frontmatter `skills:` entries (comma-separated scalar or YAML list form) AND
   body tokens `skills/<name>` / `skills/<name>/SKILL.md`. Both create inbound edges;
   **only the frontmatter `skills:` entries are the reportable F4.3 direction**
   (`agent-skills` — "agent `skills:`→SKILL.md"); body references are orphan-input only.
4. **Hook → script** — "the script path in each hook definition's `command` field, read
   from the parsed `hooks/hooks.json`": walk the PARSED object; every `{"type": "command",
   "command": <string>}` hook contributes each `${CLAUDE_PLUGIN_ROOT}/<path>` occurrence in
   its command string, where `<path>` ends at the first quote or whitespace — so an
   interpreter prefix (`node "…"`), surrounding quotes, and trailing arguments
   (`--event stop`) never leak into the target. Reportable (F4.3 `hook-script`).
5. **CLAUDE.md listing** (F4.3's direction; the partial's gap — grammar owned here): a
   Markdown list item in a CLAUDE.md file whose item text (after stripping backticks) is
   (a) a relative path — contains `/` or ends `.md`/`.json`/`.sh` — resolving against the
   plugin root, or (b) a `plugin:component` token — `<plugin>:<component>` with both parts
   `[a-z0-9-]+` — resolving iff `commands/<component>.md` exists under the root (the
   plugin namespace prefixes commands). Prose items (no path shape, no token shape) are
   not listings. Reportable (`claude-md-listing`).

## R51 semantics (per `skills/vocabulary/SKILL.md` — preconditions AND registry format)

- Fires only when the project config (read fail-closed through `scripts/lib/config.py` —
  a malformed or invalid config is a refusal, exit 2, never a silent default) has
  `rule_overrides.R51.enabled: true` (structurally under R51 — another rule's `enabled`
  never arms R51), R51 is not suppressed, `vocabulary_skill` is set and inside the root,
  and `<vocabulary_skill>/registry.yaml` exists. Any precondition unmet → the class is
  absent (advisory, not an error).
- The registry follows the documented six-key schema. Deprecated terms come from `verbs`
  (keyed by scope id; each entry `{canonical, deprecated[], …}` — flagged only in files
  matching that scope's `paths` globs) and from `nouns.artifact_class` /
  `nouns.output_class` entries (unscoped). `deferred_pending_warrant` terms are NEVER
  flagged ("they are not synonyms"); `rejected_by_higher_principle` terms are never
  entered; canonical terms are never flagged. A registry that does not parse against this
  schema is a refusal (exit 2), fail-closed like the config.

## Broken fixture seeds (tests/fixtures/check/broken/)

| # | Class | Seed | Direction / rule | Expected issue |
|---|---|---|---|---|
| 1 | reference-integrity | `commands/go.md` references `commands/shared/missing-partial.md` (absent) via a Markdown link | command→partial (F4.3) | dangling, source go.md |
| 2 | reference-integrity | `agents/helper.md` frontmatter `skills: util, absent-skill`; `skills/absent-skill/SKILL.md` absent | agent `skills:`→SKILL.md (F4.3) | dangling, source helper.md |
| 3 | reference-integrity | `hooks/hooks.json` PostToolUse names `${CLAUDE_PLUGIN_ROOT}/scripts/missing-hook.sh` (absent), unquoted plain form | hook→script (F4.3) | dangling, target exactly `scripts/missing-hook.sh` |
| 4 | reference-integrity | `CLAUDE.md` list item `docs/missing-doc.md` (absent) | CLAUDE.md listing, path shape | dangling, source CLAUDE.md |
| 5 | reference-integrity | `CLAUDE.md` list item `fixture-broken:absent`; `commands/absent.md` absent | CLAUDE.md listing, plugin-token shape | dangling, target `fixture-broken:absent` |
| 6 | orphan | `skills/orphaned/SKILL.md` registered in the manifest, zero inbound edges | inbound-edge orphan (plugin-discover map; NOT manifest-claims — F4.4's row) | orphan |
| 7 | r51-drift | `commands/go.md` uses deprecated "utilize" once; `.vibe-suite.md` enables R51 with `vocabulary_skill: skills/util`; registry scopes the `use` verb entry to `commands/**` | R51 preconditions + scope (vocabulary skill) | one occurrence, source go.md |
| 8 | behavioral-contradiction (judgment) | `commands/go.md`: "Always run the checks before committing."; `agents/helper.md`: "Never run the checks before committing." | checker-agent contract lane | judgment finding (not in mechanical oracle) |
| 9 | terminology-drift (judgment) | the same report artifact is "the audit report" in go.md and "the review dossier" in helper.md | checker-agent contract lane | judgment finding (not in mechanical oracle) |

**Anti-seeds (must NOT fire):**

- `skills/util/SKILL.md` has an inbound edge (helper's frontmatter `skills:`) → not orphan.
- `agents/helper.md` is dispatched from go.md's body (link AND name) → not orphan.
- `scripts/present-hook.mjs` is named by the Stop hook in the REAL nested hooks shape, with
  an interpreter prefix, a quoted path, and trailing arguments
  (`node "${CLAUDE_PLUGIN_ROOT}/scripts/present-hook.mjs" --event stop`) → the target is
  extracted exactly (no quote, no backslash, no arguments), resolves, and the script is not
  an orphan.
- The CLAUDE.md items `commands/go.md` (path) and `fixture-broken:go` (plugin token →
  `commands/go.md` exists) resolve → no issue; the prose item "Fixture project
  instructions." has no path or token shape → not a listing.
- "utilize" also appears in `agents/helper.md`, which is OUTSIDE the `use` entry's scope
  (`commands/**`) → not flagged (scope rule).
- "triage" appears in go.md and is a `deferred_pending_warrant` registry term → never
  flagged (deferred exemption).
- "report" (canonical noun) appears in both artifacts → canonical terms are never flagged.
- "utilize" appears exactly once in go.md (no per-file cap interplay).
- With the R51 config ABSENT (or R51 explicitly disabled, or `vocabulary_skill` missing, or
  the registry missing) the same fixture yields exactly issues 1–6: verdict `6 issues`.

## Mechanical oracle (engine alone)

Issues 1–7 exactly, in the engine's deterministic order (class, then F4.3 direction order,
then source, then target — the two claude-md rows order `docs/missing-doc.md` before
`fixture-broken:absent`); verdict `7 issues`. The complete output object, including the
`checked` inventory counts `{agent: 1, claude-md: 1, command: 1, hook-config: 1,
partial: 0, script: 1, skill: 2}`, is pinned in `expected-mechanical.json`.

## Composed oracle (engine + the checker's judgment file)

Judgment file carries findings 8–9 in the `--judgment` schema; composed report = issues
1–9 (mechanical block first, judgment in file order), verdict `9 issues`, same `checked`
map. CLEAN is emitted only when the composed list is empty. See `expected-composed.json`.

## Clean fixture (tests/fixtures/check/clean/)

Two-artifact consistent mini-plugin: `commands/hello.md` dispatches the buddy agent BY NAME
(no Markdown link — the name-dispatch edge grammar is what keeps buddy non-orphan),
`agents/buddy.md` (`skills: tool` → present `skills/tool/SKILL.md`), manifest registering
exactly what exists, CLAUDE.md listing only resolving items, no R51 config, no deprecated
terms, one name per concept, no conflicting obligation pairs ("Run the checks before
committing." appears in both artifacts with the same polarity). Expected verdict both
modes: `CLEAN`, issues empty, `checked` `{agent: 1, claude-md: 1, command: 1,
hook-config: 0, partial: 0, script: 0, skill: 1}`. No-finding conditions (the judgment
lanes' clean expectations): zero obligation pairs with opposite polarity; zero multi-name
concept clusters.
