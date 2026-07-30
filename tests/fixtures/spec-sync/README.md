# vibe-33 worksheet — hand-derived expectations for `/vibe-suite:spec-sync`

Authored BEFORE the artifacts (T0 of the frozen plan, round-3 step-6 iter-3). Citations
are to that plan's decisions.

## D3 tag precedence — worked example per tag, plus the two named overlaps

| Order | Tag | Overlay state | Source state | Worked example (seeded in the fixture) |
|---|---|---|---|---|
| 1 | RESOLVED | explicit hedge about X | now settles X | overlay hedges "path unsettled, treat as advisory"; source fixes the path |
| 2 | REMOVE | states X | X withdrawn/absent, NO replacement | overlay documents a removed `legacy_mode` flag |
| 3 | FIX | states X | states not-X, WITH replacement | overlay says events are lowercase; source says PascalCase |
| 4 | ADD | silent on X (in scope) | states X | source documents a `PostToolBatch` event the overlay lacks |
| 5 | CONFIRM | states X definitely (no hedge) | states X | overlay's `.tool/skills/` path matches the source |

Overlap resolution (both named by the step-5 review):
- **A documented withdrawal** reaches rule 2 and STOPS — it cannot be FIX, because rule 3
  requires a replacement fact and rule 2 requires its absence.
- **A settled hedged claim** reaches rule 1 and STOPS — CONFIRM requires an un-hedged
  claim; FIX requires the source to state not-X.

## D4 confidence and UNCLASSIFIED

`high` = explicit first-party statement; `medium` = indirect (example/changelog/
inference). Insufficient evidence is NOT a grade: `UNCLASSIFIED` with reason
`source-silent` or `source-conflict`, reported and never written. Threshold flag
`--min-confidence <high|medium>`, default `medium`. Withheld rows print
`(withheld: below --min-confidence)` and do NOT count toward CHANGES (D2).

## D5 correction notes

`<!-- spec-sync <run-date>: <tag> — <source label>, <URL> (confidence: high|medium) -->`
Body claims: line immediately after. Frontmatter claims: first entry of a
`## Correction notes` body section naming the key — NOT inside the YAML block (an HTML
comment is not valid YAML for conforming parsers; `bin/vibe-check`'s `frontmatter_keys`
would tolerate it, but that is not the standard being met).
Retirement: a later `--apply` CONFIRM at `high` against a source dated ≥ the note's date
deletes it — and that CONFIRM row IS writable, so retirement is reachable.

**Replacement example** (one note per claim, never accumulating). A 2026-06-10 run FIXes
the event-case claim; a 2026-07-14 run FIXes the same claim again when the source adds a
second event. The later run REPLACES the note — it does not append a second one:

```
before (after the 2026-06-10 run)
  Hook events are PascalCase: `PreToolUse`, `PostToolUse`.
  <!-- spec-sync 2026-06-10: FIX — code.claude.com/docs/en/hooks, https://code.claude.com/docs/en/hooks (confidence: high) -->

after (the 2026-07-14 run)
  Hook events are PascalCase: `PreToolUse`, `PostToolUse`, `PostToolBatch`.
  <!-- spec-sync 2026-07-14: FIX — code.claude.com/docs/en/hooks, https://code.claude.com/docs/en/hooks (confidence: high) -->
```

The 2026-06-10 note is gone, not stacked above the new one. Two notes on one claim is the
defect this rule exists to prevent.

## D6 freshness normalization — pre/post for all four occurrences

Four freshness statements existed across three overlays (two of them in
`conventions-codex`), in three prose shapes and two placements. Pre-state quoted from
`2bbcef5`; post-state is the shipped canonical line, which is the first content after
each H1.

Each PRE cell is the complete statement as it stood at `2bbcef5`, not a fragment of it —
the qualifying second sentence is where the content that must survive normalization
lives, so truncating it would hide exactly what this table exists to check.

| # | Overlay | Placement | Pre (complete, @2bbcef5) | Post (canonical line + where the qualification went) |
|---|---|---|---|---|
| 1 | claude | body | `Freshness: refreshed 2026-06-07 against the official docs map dated 2026-06-05, which tracks Claude Code ≥ v2.1.16x. Where earlier notes conflicted with that refresh, the newer facts below are canonical.` | `**Spec freshness:** verified 2026-06-07 against the official Claude Code docs map dated 2026-06-05 (code.claude.com/docs/en/)` — and the qualification is PRESERVED as its own body sentence: `That map tracks Claude Code ≥ v2.1.16x; where earlier notes conflicted with this refresh, the newer facts below are canonical.` |
| 2 | codex | body | `Refresh state: verified 2026-06-07 against Codex CLI 0.137.0 (released 2026-06-04; pre-releases existed up to 0.138.0-alpha.6 at refresh time).` | `**Spec freshness:** verified 2026-06-07 against Codex CLI 0.137.0, released 2026-06-04 (developers.openai.com/codex)` — and the parenthetical is PRESERVED as its own sentence: `Pre-releases existed up to 0.138.0-alpha.6 at refresh time.` |
| 3 | codex | `description:` | `facts checked 2026-06-07 versus Codex 0.137.0 (a 2026-06-04 release)` | clause removed from the description; its version pairing survives in row 2's canonical line, leaving the description undated |
| 4 | antigravity | `description:` | `the spec has not settled since Antigravity 2.0 (2026-05-19), so most tool-specific checks stay advisory` | the DATE is dropped and the clause is RETAINED, undated: `the spec has not settled since Antigravity 2.0, so most tool-specific checks stay advisory`. The dated statement moves to the canonical line: `**Spec freshness:** UNVERIFIED — research written 2026-05-25, six days after the Antigravity 2.0 announcement of 2026-05-19; the verification pass described in §10 has not landed (developers.googleblog.com)` |

Nothing is normalized away. Rows 1 and 2 preserve their qualifications as body sentences;
row 3's clause is removed only because row 2 already carries the same fact; row 4's clause
is retained verbatim minus its date. What normalization removes is the DUPLICATE DATE, not
the content — after it, exactly one dated marker exists per overlay, which is what makes an
`--apply` bump a single unambiguous edit.

Antigravity reads `UNVERIFIED` rather than a verified date because its own STATUS block
says the verification pass has not landed. Writing a date there would assert something the
overlay itself denies — the one place in this item where the honest value is the absence
of a value.

## D7 anchor measurement and the four-kind classification

**Anchor, re-measured at this HEAD** (not copied from the plan — see the note below).
Scope excludes `tests/`, `docs/`, `.github/`.

| File | Plain `conventions-<tool> §N` | Markdown-link `[conventions-<tool>](…) §N` |
|---|---|---|
| `bin/vibe-check` | 1 | 0 |
| `skills/scoring/SKILL.md` | 8 | 3 |
| `skills/conventions-antigravity/SKILL.md` | 0 | 1 |

Three anchored files, 13 citations. **The frozen plan recorded 2 plain citations in
`bin/vibe-check`; the current measurement is 1.** The plan measured at `2bbcef5`, and this
worksheet records what the tree says now — the count is a measurement, so it is re-taken
rather than transcribed. Either way the anchored SET is unchanged, which is what D7 turns
on. The matcher must accept both citation forms: the antigravity occurrence is a
link-form cross-citation of `conventions-codex §6` and is invisible to a plain-form
matcher.

**The four kinds, one example each:**

| Kind | Example | Why | `--apply` behaviour |
|---|---|---|---|
| SOURCE | `skills/conventions-claude/SKILL.md` | the overlay itself — the fact's origin | rewritten by the run |
| DOCUMENTARY | `consumer-uncited.md` restating the skills path in prose | prose repeating an overlay fact, no citation | updated ONLY if this run changed the fact it restates |
| ENCODED | `bin/vibe-check`'s `KNOWN_EVENTS` list | a machine-readable transcription of the event catalog | never edited — reported `code-change-required` with its owning test named |
| OPERATIONAL | `scripts/update.py` reading `.claude/` | code whose function is to read/write per-tool paths | never edited — reported `code-change-required` |

The ENCODED/OPERATIONAL boundary is not cosmetic: editing either changes program
behaviour, so it needs a code change with its own test, which is why this command reports
them and stops. Correcting `KNOWN_EVENTS` by text substitution would silently alter what
`bin/vibe-check` accepts.

## The fixture (`stale-overlay/`) — seven seeds

| # | Seed | Expected tag | Expected confidence/reason |
|---|---|---|---|
| 1 | hedged path claim, source settles it | RESOLVED | high |
| 2 | documented `legacy_mode` withdrawal | REMOVE | high |
| 3 | lowercase-events claim, source says PascalCase | FIX | high |
| 4 | `PostToolBatch` absent from the overlay | ADD | medium |
| 5 | `.tool/skills/` path matches the source | CONFIRM | high |
| 6 | claim the source does not mention | UNCLASSIFIED | source-silent |
| 7 | two first-party pages disagree | UNCLASSIFIED | source-conflict |

Plus: a canonical freshness line in the D6 form; a LINKED-citation consumer
(`consumer-linked.md`, citing `[conventions-claude](...) §4`); an UNCITED documentary
consumer (`consumer-uncited.md`, restating the path fact with no citation).

Expected run: `/vibe-suite:spec-sync claude --dry-run --overlay-root
tests/fixtures/spec-sync/stale-overlay` → exactly seven rows, one per seed, no others.
`expected-report.md` is the oracle; `recorded-dry-run.md` is the verbatim manual run
compared against it one-to-one by `tests/test_spec_sync.py`.
