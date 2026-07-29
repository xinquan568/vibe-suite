# Score-engine row ledger (E3.3 / vibe-28)

Every row of the scoring skill's Skills penalty table (skills/scoring/SKILL.md), plus the two R01 rows from its "All types: vague quantifiers" table, classified for scripts/score_engine.py:

- `mechanical` — the engine deducts; the Predicate column quotes or states the
  objective predicate from the owning text.
- `advisory-zero` — the engine reports the class as an advisory and never deducts,
  because no objective predicate exists in the owning text.

Ground truth for every classification: the hand-computed worksheet
tests/fixtures/nl-audit/defective-skill/README.md (cited as "worksheet #n").

## Penalty-table rows

| Rule | Check | Condition | Class | Predicate / justification |
|------|-------|-----------|-------|---------------------------|
| -- | name present | missing | mechanical | the parsed frontmatter has no `name` key — objective, mechanically checkable (worksheet #1) |
| -- | name matches parent dir | frontmatter name differs from parent directory name (conventions §5; open-spec MUST) | mechanical | quoted predicate: "a single-line diff of the frontmatter name against the basename of the containing directory" (rubric's name-matches-parent-dir note); with no frontmatter name there is nothing to diff, so the row cannot fire (worksheet #1) |
| R04 | description present | missing | mechanical | the parsed frontmatter has no `description` key — objective, mechanically checkable |
| R04 | trigger quality | generic description (at most one specific phrase) | advisory-zero | worksheet #2: "'Generic' is a judgment word" and "specific phrase" has "no mechanical definition anywhere in the rubric" — deciding whether a phrase is specific is not mechanical |
| R04 | description length | 500–800 chars | mechanical | counted in CHARACTERS of the description value: fires when 500 <= chars <= 800 (worksheet #2 measures the fixture's description in characters: 38) |
| R04 | description length | over 800 chars | mechanical | counted in CHARACTERS of the description value: fires when chars > 800; mutually exclusive with the 500-800 band |
| R05 | body length | 400–500 lines | mechanical | counted in physical lines of the whole file: fires when 400 <= lines <= 500 — worksheet #3: "Objective line count"; "a mutually exclusive band" that never stacks |
| R05 | body length | over 500 lines | mechanical | counted in physical lines of the whole file: fires when lines > 500 — the fixture's 583-line file takes exactly this -10 (worksheet #3) |
| R06 | code examples | complex concepts but no examples | advisory-zero | worksheet #5: the row penalizes only absence and "complex concepts" is a judgment call with no stated criteria in the owning text |
| R06 | code examples | no examples at all in a technical skill | advisory-zero | worksheet #5: "technical skill" is a judgment call with no stated criteria in the owning text |
| R06 | example blocks | zero `<example>` blocks on a `user_invocable: true` skill | mechanical | implemented: fires when the parsed frontmatter sets `user_invocable: true` and the file contains zero literal `<example>` blocks — both facts are mechanically checkable (worksheet #5 notes the row "cannot fire" without `user_invocable: true`) |
| R07 | scope note | no scope note / cross-references | mechanical | worksheet #8: "Absence is mechanically checkable" — fires when the file has no heading naming scope and no `](../` cross-reference to a sibling skill; the penalty is -3, never conflated with example blocks (rubric's scope-note-discipline note) |
| R01 | vague quantifier | each occurrence of: appropriate, relevant, as needed, sufficient, adequate, reasonable, properly, correctly, some, several, various — without measurable criteria | mechanical | token-bounded count of the 11 listed words, -2 per occurrence — worksheet #10 verified the fixture's 12 occurrences "identical under substring and word-boundary matching" |
| R01 | cap | cap on total vague-quantifier penalty | mechanical | the summed vague-quantifier penalty clamps at -20: the fixture's 12 x -2 = -24 lands at -20 (worksheet #10: "cap binds") |

## Worksheet defect classes with no penalty-table row

The rubric's closing principle: "any finding with no specific penalty-table row to
cite gets dropped." These seeded classes therefore deduct nothing; the engine emits
each as an advisory so the narrating agent sees them without a penalty existing.

| Rule | Check | Source | Class | Justification |
|------|-------|--------|-------|---------------|
| -- | broken references link | worksheet #4 | advisory-zero | no Skills-table row penalizes a dead link inside a skill body; the dead-reference rows belong to other artifact types or scopes (R36, R29, Cross-component), and the closing principle drops any finding with no row to cite |
| -- | pseudocode example | worksheet #5 | advisory-zero | the anti-pseudocode wording ("Use real syntax, never pseudocode") lives only in R06's rule text with no penalty row in the Skills table |
| -- | domain mixing | worksheet #6 | advisory-zero | no row in any table carries a "mixing" condition for skills; "mixing" is a judgment word with no stated criteria in the owning text |
| -- | redundant content | worksheet #7 | advisory-zero | "redundant" is a judgment word with no stated criteria; R02 has no penalty row in any table |
| -- | orphaned registration | worksheet #9 | advisory-zero | orphan and broken-registration rows sit only in the Cross-component table (whole-plugin lint, not per-file) — a different scoring scope than this per-file score |
