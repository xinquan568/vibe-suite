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
