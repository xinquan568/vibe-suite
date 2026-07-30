# vibe-29 T0 worksheet — hand-derived oracle (staged during classifier outage; place as
# tests/fixtures/check/broken/README.md after the plan verify clears)

Authored BEFORE any engine code (the vibe-28 oracle-first lesson). Every determination cites
its governing text. Orphan candidates are the non-root components — skills, agents, shared
partials, scripts (commands, hooks.json, and CLAUDE.md are reference ROOTS per
`commands/shared/plugin-discover.md`'s map: edges run command→agent, command→partial,
agent→skill, hook→script; CLAUDE.md listings add root→target edges per F4.3).

## Broken fixture seeds (tests/fixtures/check/broken/)

| # | Class | Seed | Direction / rule | Expected issue |
|---|---|---|---|---|
| 1 | reference-integrity | `commands/go.md` references `commands/shared/missing-partial.md` (absent) | command→partial (F4.3; partial's map) | dangling, source go.md |
| 2 | reference-integrity | `agents/helper.md` frontmatter `skills: util, absent-skill`; `skills/absent-skill/SKILL.md` absent | agent `skills:`→SKILL.md (F4.3) | dangling, source helper.md |
| 3 | reference-integrity | `hooks/hooks.json` names `${CLAUDE_PLUGIN_ROOT}/scripts/missing-hook.sh` (absent) | hook→script (F4.3; partial's map) | dangling, source hooks.json |
| 4 | reference-integrity | `CLAUDE.md` list item `docs/missing-doc.md` (absent); sibling item `commands/go.md` resolves | CLAUDE.md listing (F4.3; the partial's gap — grammar below) | dangling, source CLAUDE.md |
| 5 | orphan | `skills/orphaned/SKILL.md` registered in the manifest, zero inbound edges | inbound-edge orphan (plugin-discover map; NOT manifest-claims — F4.4's row) | orphan |
| 6 | r51-drift | `commands/go.md` uses deprecated "utilize" once; fixture ships `.vibe-suite.md` enabling R51 with `vocabulary_skill: skills/util` and `skills/util/registry.yaml` (canonical "use", deprecated "utilize") | R51 preconditions per skills/vocabulary/SKILL.md | one occurrence |
| 7 | behavioral-contradiction (judgment) | `commands/go.md`: "Always run the checks before committing."; `agents/helper.md`: "Never run the checks before committing." | checker-agent contract lane | judgment finding (not in mechanical oracle) |
| 8 | terminology-drift (judgment) | the same report artifact is "the audit report" in go.md and "the review dossier" in helper.md | checker-agent contract lane | judgment finding (not in mechanical oracle) |

**CLAUDE.md-listing grammar (the independent oracle for the partial's gap):** a Markdown
list item in a CLAUDE.md file whose item text is a relative path (contains `/` or ends
`.md`/`.json`/`.sh`) or a `plugin:component` token must resolve against the plugin root.
Resolving case: `commands/go.md`. Non-resolving case: `docs/missing-doc.md`. Prose list
items (no path shape) are not listings. Source: F4.3 "CLAUDE.md listings".

**Anti-seeds (must NOT fire):** `skills/util/SKILL.md` has an inbound edge (helper's
`skills:`) → not orphan; the CLAUDE.md item `commands/go.md` resolves → no issue;
"utilize" appears exactly once (no cap interplay); with R51 config ABSENT the same fixture
yields exactly issues 1–5 (the disabled-default test).

## Mechanical oracle (engine alone)

Issues 1–6 exactly; verdict `6 issues`. See `expected-mechanical.json` (shapes finalized to
the engine schema at T0-final; classes/sources/targets are fixed here).

## Composed oracle (engine + the checker's judgment file)

Judgment file carries findings 7–8 in the `--judgment` schema; composed report = issues 1–8,
verdict `8 issues`. CLEAN is emitted only when the composed list is empty. See
`expected-composed.json`.

## Clean fixture (tests/fixtures/check/clean/)

Two-artifact consistent mini-plugin: `commands/hello.md` (references `agents/buddy.md`
conceptually and no missing targets), `agents/buddy.md` (`skills: tool` → present
`skills/tool/SKILL.md`), manifest registering exactly what exists, CLAUDE.md listing only
resolving items, no R51 config, no deprecated terms, one name per concept, no conflicting
obligation pairs ("Run the checks before committing." appears in both artifacts with the
same polarity). Expected verdict both modes: `CLEAN`. No-finding conditions (the judgment
lanes' clean expectations): zero obligation pairs with opposite polarity; zero
multi-name concept clusters.
