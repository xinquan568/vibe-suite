# Expected gap report — the hand-authored oracle (vibe-33 T0)

Run: `/vibe-suite:spec-sync claude --dry-run --overlay-root tests/fixtures/spec-sync/stale-overlay`

Exactly seven rows, one per seed, in D3 precedence order then section order. No other
rows may appear.

| Seed | Section | Tag | Confidence / reason |
|---|---|---|---|
| 1 | §2 Directory placement | RESOLVED | high |
| 2 | §3 Legacy switches | REMOVE | high |
| 3 | §4 Hook events | FIX | high |
| 4 | §4 Hook events | ADD | medium |
| 5 | §1 Skill layout | CONFIRM | high |
| 6 | §5 Telemetry | UNCLASSIFIED | source-silent |
| 7 | §6 Config precedence | UNCLASSIFIED | source-conflict |

Dry run: no file is written, no freshness bump, no propagation, no verify invocation.
Propagation section reports `consumer-linked.md` as a REQUIRED target (cites §4, which
rows 3 and 4 change) and `consumer-uncited.md` as DOCUMENTARY (restates §1's path fact).
