---
description: "Score trends over time: re-scores the target through the deterministic engine, compares against the scope-matched history (apples-to-apples), renders per-file deltas (improved / degraded / unchanged / new) and an N-snapshot trajectory, and appends this run's snapshot. Missing history means a baseline run; malformed history warns once and starts fresh. Arguments: an optional path and --changed, with the same scope meanings as /vibe-suite:score."
argument-hint: "[path] [--changed] [--limit N]"
---

# /vibe-suite:trend — score trends over time

Three dispatches, in this order — the scope derivation, the pure re-score, then the trend engine
that owns both the comparison and the history append:

```bash
SCOPE=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/scope_tag.py" --root "<abs-target>" \
  ${PATH_ARG:+--path "$PATH_ARG"} ${CHANGED:+--changed})

# Pure scoring — deliberately WITHOUT a history flag: appending here would make the trend
# compare the run against itself. trend_engine reads the pre-append history first.
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/score_engine.py" --root "<abs-target>" \
  < "<record-file>" > "<score-json>"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/trend_engine.py" --root "<abs-target>" \
  --history "<abs-target>/.claude/vibe-history.json" --scope "$SCOPE" \
  --run-id "$(date -u +%Y-%m-%dT%H:%M:%SZ)" ${LIMIT:+--limit "$LIMIT"} \
  < "<score-json>" > "<trend-json>"
```

The record file is built exactly as `/vibe-suite:score` builds it (framed
`<type-or-category>\x1f<path>\x00` records for the artifacts in scope). The scope tag comes from
the shared derivation — `full`, `path:<rel>`, `changed`, or `changed:<rel>` — never restated by
hand, so score and trend always filter the same buckets.

## Rendering

From the trend JSON, render two tables:

1. **Per-file deltas** — path, current, previous, delta, flag. Order is the engine's (by path).
2. **Trajectory** — run, mean score, file count; the current run is the last row. `--limit N`
   bounds the points (default 10).

Then one status line: history `present` (with `scope_matches`), `missing` — "first run for this
scope: baseline recorded, every file is new" — or `malformed` — relay the engine's single warning
and note the history was restarted fresh.

## Notes

- Histories written before the shared scope vocabulary may carry other tags; those entries simply
  never match the filter, and the first trend run for a scope reports the baseline case.
- Entries lacking score fields (init's baseline marker, migration markers) are preserved in the
  file and excluded from every computation.
- The engine refuses a history path outside the target root (exit 2); relay refusals verbatim.
