# Oracle Worksheet -- defective-skill fixture

Hand-derived ground truth for /vibe-suite:score (vibe-28). Every number below was
computed manually from the rubric text in skills/scoring/SKILL.md (penalty source)
and skills/rules/SKILL.md (rule wording) -- no scoring engine produced any figure
here. The engine built later must reproduce expected.json exactly.

Transcription note: this fixture is pure ASCII, so em/en dashes and section marks
inside quoted rubric rows are rendered as ASCII hyphens and "[section]"; the
check/condition/penalty content of every quote is otherwise verbatim.

## Scored artifact

`skills/defective/SKILL.md` -- artifact type: **skill**, so the "Skills" penalty
table plus the "All types: vague quantifiers" (R01) table apply. R51 is opt-in and
no `.vibe-suite.md` exists in this fixture, so R51 stays at zero by
rule.

File facts (measured):

- Total lines: **583**; frontmatter: lines 1-3; body: **580** lines. Both counts
  exceed 500.
- Frontmatter is valid YAML, contains `description` only -- no `name` key, no
  `user_invocable` key.
- Description value: `A helpful skill for working with data.` -- 38 characters.
- Flagged R01 words: exactly **12** lexical occurrences, one per line at lines
  11-22 (`as needed`, `appropriate`, `relevant`, `sufficient`, `adequate`,
  `reasonable`, `properly`, `correctly`, `some`, `several`, `various`, `some`).
  Verified identical under substring and word-boundary matching; zero
  occurrences elsewhere in the file. Under the measurable-criterion carve-out
  (class 10) the line-21 `various` is excluded, leaving **11 counted**.
- One pseudocode fence (lines 40-45) and one runnable Python example (lines 49-56).
- One link, to `references/missing.md` (line 60) -- the target does not exist on
  disk. It points inside the skill's own directory; the file contains no
  cross-reference to any sibling skill and no scope note.
- `.claude-plugin/plugin.json` is valid JSON with `name`, semver `version`, and
  `description`; its `skills` array registers `./skills/ghost` (absent from disk)
  and does not register `./skills/defective`.

## Per-class determinations

### 1. Missing name -- DEDUCTS -25

Skills table row (verbatim): `| -- | name present | missing | -25 |`

The frontmatter has no `name` key. Objective, mechanically checkable: **-25**.

Note on the adjacent row `| -- | name matches parent dir | frontmatter name differs
from parent directory name (conventions [section] 5; open-spec MUST) | -15 |`: the
rubric's own note defines its predicate as "a single-line diff of the frontmatter
name against the basename of the containing directory". With no frontmatter name
there is nothing to diff, so that row cannot fire; only the name-present row does.
No double-count.

### 2. Generic description -- ADVISORY-ZERO

Skills table row (verbatim): `| R04 | trigger quality | generic description (at
most one specific phrase) | -15 |`

Determination: advisory-zero -- no objective predicate in the owning text.
"Generic" is a judgment word, and its parenthetical unit "specific phrase" has no
mechanical definition anywhere in the rubric; R04's own wording makes it a judgment
about user behavior: "Write a minimum of 3 specific action phrases **matching
queries real users actually type**". Counting lines or listed words is mechanical;
deciding whether a phrase is "specific" is not.

(The two R04 length rows do not fire either: the description is 38 characters, far
below the `500-800 chars | -5` and `over 800 chars | -10` thresholds.)

### 3. Body over 500 lines -- DEDUCTS -10

Skills table row (verbatim): `| R05 | body length | over 500 lines | -10 |`

Body is 580 lines (whole file 583) -- over 500 under any counting convention.
Objective line count: **-10**. The lower tier `| R05 | body length | 400-500 lines
| -5 |` is a mutually exclusive band and does not stack.

### 4. Broken references/ link -- ADVISORY-ZERO

Determination: advisory-zero -- no objective predicate in the owning text: the
Skills table contains no row for a dead link inside a skill body. Rows that
penalize dead references all belong to other artifact types or scopes: R36
`valid @ imports` (CLAUDE.md table: "an @ import references a nonexistent file"),
R29 `scripts exist` (Hooks table: "referenced script missing"), and the broken-ref
rows of the Cross-component table, which is headed "(`--plugin` flag; whole-plugin
lint, not per-file)". Type tables apply per type. Closing principle (verbatim):
"any finding with no specific penalty-table row to cite gets dropped."

### 5. Pseudocode example -- ADVISORY-ZERO

The three R06 Skills rows (verbatim) penalize only absence:
`| R06 | code examples | complex concepts but no examples | -5 |`,
`| R06 | code examples | no examples at all in a technical skill | -10 |`,
`| R06 | example blocks | zero <example> blocks on a user_invocable: true skill | -10 |`.

Determination: advisory-zero -- the file contains examples (including a runnable
Python one), so no absence row fires, and the anti-pseudocode wording lives only in
R06's rule text ("Use real syntax, never pseudocode") with no penalty row in the
Skills table. The third row also cannot fire because the frontmatter does not set
`user_invocable: true`.

### 6. Domain mixing -- ADVISORY-ZERO

The body mixes SQL query tuning, CSS page styling, team email etiquette, and CSV
validation. Determination: advisory-zero -- no row in the Skills table (or any
table) carries a "mixing" condition for skills; "mixing" is a judgment word with no
stated criteria in the owning text. (R49's audience-mixing concern targets
CLAUDE.md/README, a different artifact type, and has no penalty row either.)

### 7. Redundant content -- ADVISORY-ZERO

The "Batch Sizing" paragraph (lines 62-64) is repeated verbatim as "Batch Sizing
Reminder" (lines 66-68). Determination: advisory-zero -- "redundant" is a judgment
word with no stated criteria; R02 ("Every line earns its token cost") has no
penalty row in any table.

### 8. Missing scope note -- ADVISORY-ZERO

Skills table row (verbatim): `| R07 | scope note | no scope note / cross-references | -3 |`

Determination: advisory-zero -- the row's own applicability condition is not
mechanically decidable. The rubric's scope-note-discipline note (verbatim): "R07
means one thing only: a scope note is missing even though related skills exist."
The condition therefore requires related skills to exist, and this fixture ships
exactly one skill -- there is no sibling skill on disk, let alone a *related*
one; whether two skills are "related" is a judgment word with no stated criteria
in the owning text. Any mechanical detector (for example "a heading naming scope,
or a `../` cross-reference link") would be an invented predicate: no such
definition of a scope note appears anywhere in the rubric. The absence of a
scope note is recorded as an advisory at zero penalty; the -3 deducts only when
an objective definition of relatedness and of a scope note enters the owning
text. (The note's second half still holds: missing example blocks is the R06 row
above, at -10 -- never -15 -- and never conflated with R07.)

### 9. Orphaned registration -- ADVISORY-ZERO

The manifest registers `./skills/ghost` (no such directory) and omits
`./skills/defective` (so the shipped skill is referenced by nothing).
Determination: advisory-zero for this per-file score -- the only rows covering
orphans and broken registrations sit in the Cross-component table, headed
(verbatim) "Cross-component (`--plugin` flag; whole-plugin lint, not per-file)" --
e.g. `| orphaned files | agent/command/skill referenced by nothing | -5 per file |`.
That is a different scoring scope than the per-file skill score recorded here, and
the per-type plugin.json table has rows only for `name present`, `version is
semver`, and `description present`, all of which pass. Type tables apply per type.

### 10. Vague quantifiers -- DEDUCTS -20 (cap binds)

R01 rows (verbatim): `| R01 | vague quantifier | each occurrence of: appropriate,
relevant, as needed, sufficient, adequate, reasonable, properly, correctly, some,
several, various -- without measurable criteria | -2 each |` and
`| R01 | cap | cap on total vague-quantifier penalty | max -20 |`

12 lexical occurrences (lines 11-22, listed above). The conventions [section] 4
carve-outs, applied exactly as stated: no flagged word sits on a heading line;
the single `relevant` (line 13) is "the relevant columns", not "relevant to
<named-scope>"; and the third carve-out -- quoted verbatim, "any listed term
followed by a measurable-criterion clause" -- is encoded, since the owning text
supplies no finer definition, as a quantity in the remainder of the term's own
sentence on its line: a digit, or a spelled-out cardinal from a closed list
(zero-twenty, the tens thirty-ninety, hundred, thousand, million). No digit
appears in any of lines 11-22; one cardinal does: line 21 reads "Try various
encodings until one loads.", so the line-21 `various` is carved out. A
mechanical encoding cannot tell pronoun-`one` from quantity-`one`, and the
ambiguity resolves toward not deducting (the rubric's closing principle: no
citable criterion, no finding). Counted occurrences: **11** x -2 = -22, capped
at **-20**. The first counted occurrence stays line 11, so the finding's line
anchor and the deduction are both unchanged by the carve-out.

## Kept-clean checklist (why nothing else fires)

- Frontmatter parses (no -25 parse-failure penalty).
- `description` present (no `R04 | description present | missing | -25`).
- Description 38 chars (no R04 length rows).
- Runnable example present (no R06 rows).
- No `user_invocable: true` (no `<example>`-blocks row).
- R51 opt-in config absent, so R51 is zero by rule.
- Flagged-word count is exactly 12 lexical / 11 counted in the whole file,
  verified by grep under both substring and word-boundary conventions (the cap
  binds at either count, so the R01 deduction is -20 regardless).

## Arithmetic

```
base                = 100
name present        =  -25
R05 body length     =  -10
R01 vague (capped)  =  -20
total penalty       =  -55
final = max(0, min(100, 100 + (-55))) = 45
```

(R07 scope note is advisory-zero per class 8 above and contributes nothing.)

Band table (verbatim row): `| <60 | Rewrite | fundamental problems; rewrite from scratch |`

**Score: 45 -- Band: Rewrite -- Total penalty: -55.**

45 sits well inside the Rewrite band (boundary zones are 58-62, 68-72, 88-92), so
no calibration-example consultation is required. With no config present the pass
threshold is the default 70, so the verdict is **fail**.

## expected.json shape

`expected.json` is the engine's `files[0]` object verbatim, so the acceptance
test can compare the two for exact equality: `path`, `tier` (`"1"` -- an
open-spec artifact: `skills/defective/SKILL.md` sits under no tool tree, per
the scoring skill's tier classifier and the conventions overlay table),
`score`, `band`, `verdict`, `findings` (each `{rule, check, line, penalty}`;
R01's line is 11, the first counted occurrence; frontmatter and body findings
carry line 1), and `advisories` (each `{rule, note}`, one per advisory-zero
Skills-table row plus one per seeded worksheet defect class, in ledger order).
