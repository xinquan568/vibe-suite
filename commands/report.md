---
description: "Self-contained HTML quality report: fresh score + consistency check (mechanical, plus the composed judgment lane when agents ran) + vocab-drift (when the corpus holds ≥5 artifacts) + score history, assembled into one typed JSON blob and rendered by bin/vibe-report into .claude/vibe-reports/index.html plus a timestamped archive. Single-file output: the vendored AntV G6 bundle and the data are inlined, so reports open over file:// with no network. Argument: an optional path narrowing the corpus."
argument-hint: "[path]"
---

# /vibe-suite:report — self-contained HTML quality report

Assemble the blob in the session scratchpad — **always `mktemp`, never a fixed path** (two
concurrent reports must never share a blob file):

```bash
BLOB=$(mktemp "${SCRATCHPAD:-${TMPDIR:-/tmp}}/vibe-report-blob.XXXXXX")
```

## Collect the six sections (typed per `tests/test_report.py`'s pinned contract)

1. **score** — frame the target's discovery records and run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/score_engine.py" --root "<abs-target>"` (NO
   `--history`: a report is **read-only** toward the history; the trend command owns appends).
   The record count is also the **≥5 gate's** basis: fewer than 5 framed artifacts →
   `vocab_drift.available: false` with the count in `reason`.
2. **check** — `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_engine.py" --root "<abs-target>"
   --graph` fills both `check.mechanical` and the blob's `graph` section (nodes/edges). Then
   **attempt** the composed lane: dispatch the checker agent as `/vibe-suite:check` does and pass
   its judgment file back via `--judgment`; on success set `judgment.status: "composed"` with the
   full envelope (judgment-origin issues carry `sources: [str]`, never `source`); if the agent
   cannot run, `status: "skipped"` with the reason — never omit the lane silently.
3. **vocab_drift** — when the gate passes, dispatch the vocab-drift-scanner agent (as
   `/vibe-suite:vocab drift`) and shape its prose: each distinct near-synonym cluster becomes
   `{terms: [..], rationale: "one sentence"}` in `candidates`, the full text goes to `prose`.
4. **vocabulary** — project `skills/vocabulary/registry.yaml` verbatim (scopes with paths; scoped
   verbs; noun groups with their real fields), and slice
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vocab_extract.py" --root "<abs-target>"` to the top
   **30** terms by count (ties: term ascending), dropping `files`.
5. **history** — read `<target>/.claude/vibe-history.json` **read-only**: normalize via the trend
   engine's reader, set `status` (present/missing/malformed), and compute the stored trajectory
   (`trend_engine.trajectory_from_entries`) — the report never appends, so the history file's
   bytes are untouched.
6. Write the blob to `$BLOB` and render:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/vibe-report" --data "$BLOB" \
  --out-dir "<abs-target>/.claude/vibe-reports"
```

## Report to the user

The index path and archive name the renderer printed, the score/verdict headline, and any honest
absences (skipped judgment, unavailable drift, missing history). On a refusal (exit 2) relay the
schema violation verbatim — the renderer writes nothing on refusal.

## Notes

- Every emitted report is a single self-contained file (inlined G6 5.1.1 + data); archives are
  `report-<UTC>-<pid>-<hex>.html`, `index.html` is replaced atomically — concurrent runs never
  interleave.
- `templates/report/vendor/VENDORED.md` records the bundle's provenance; the integrity test pins
  its sha256.
