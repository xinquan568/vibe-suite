# Recorded dry run — provenance

- Recorded: 2026-07-31
- Executed by: Claude Opus 5 (manual judgment-lane execution; CI performs no network
  fetch — see tests/test_spec_sync.py's module docstring)
- Command: `/vibe-suite:spec-sync claude --dry-run --overlay-root tests/fixtures/spec-sync/stale-overlay`
- Overlay target: the fixture overlay at `tests/fixtures/spec-sync/stale-overlay`
- Sources: the fixture declares its own source states inline (SEED annotations); no
  live fetch was performed against a real vendor domain for this recording, because the
  fixture exists precisely to make the tagging deterministic.

## Gap report — conventions-fixturetool (fixture)

| Seed | Section | Tag | Confidence / reason |
|---|---|---|---|
| 1 | §2 Directory placement | RESOLVED | high |
| 2 | §3 Legacy switches | REMOVE | high |
| 3 | §4 Hook events | FIX | high |
| 4 | §4 Hook events | ADD | medium |
| 5 | §1 Skill layout | CONFIRM | high |
| 6 | §5 Telemetry | UNCLASSIFIED | source-silent |
| 7 | §6 Config precedence | UNCLASSIFIED | source-conflict |

## Propagation

- `consumer-linked.md` — REQUIRED target: cites §4, which rows 3 and 4 change.
- `consumer-uncited.md` — DOCUMENTARY: restates §1's skill-layout path with no citation.

## Verify

Skipped: this is a dry run — no file was written, no freshness bump, no propagation
edit, and no verify invocation.
