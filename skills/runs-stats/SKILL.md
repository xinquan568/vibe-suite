---
name: runs-stats
description: "Generate time-bucketed static HTML statistics dashboards over the issue2pr runs/ tree: all-time plus day/week/month reports, index.html, and history.json under runs/_reports/, with vendored Chart.js inlined so charts render offline from file://. Past buckets are frozen snapshots refreshed once when their data changed (--force-regenerate/--period rebuild surgically); buckets follow --tz (default Asia/Shanghai). Requires --id-pattern from the resolved issue2pr profile and refuses without it; reviewer token panels are labeled from run metadata, never a hardcoded model name. Ad-hoc filters write one isolated report, never touching canonical history. Use when asked to summarize, visualize, or track issue2pr runs, AI-review activity, or token usage over time."
---

# /vibe-suite:runs-stats — time-bucketed statistics dashboards for issue2pr runs

Produces a set of **static HTML dashboards** over everything under `runs/`, bucketed by
**day / week / month / all-time**, so the latest activity and its history are visible by just
opening files. Every generated page **inlines the vendored Chart.js**
(`vendor/chart.umd.min.js`, see `vendor/VENDORED.md`) — no CDN, no network; charts render from
`file://`. Pages follow the OS light/dark setting automatically. Read-only over `runs/`; no
MCP, no git; **Python standard library only** (uses `zoneinfo`, no pip/venv).

Ported from the workspace runs-stats skill per F8.5 with three changes: profile-aware ticket
identity, reviewer labels from run metadata, vendored chart library.

## When to use

"show stats for the runs", "how many work items this week / this month", "token usage over
time", "build a dashboard over `runs/`", "weekly/monthly history of the AI-review pipeline",
"which runs stopped/failed".

## How to run

From the workspace root (the directory containing `./runs/`), **thread the resolved issue2pr
profile's `id_pattern`** into the generator — resolve the profile per the issue2pr skill
(`.vibe-suite.md` `issue2pr_profile:` → `profiles/<name>.md`) and read its `id_pattern` field:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/runs-stats/scripts/generate_runs_stats.py" \
  --id-pattern '<the profile id_pattern, e.g. ^vibe-(\d+)$>'
```

**A run with no `--id-pattern` refuses (exit 2) and points at the profile** — a generic guess
would bucket runs wrongly, so there is no silent fallback. The pattern is anchored (it
recognizes a whole work-item id); when a run's metadata carries no id, the generator searches
the pattern's unanchored core inside the run-folder name as the fallback.

Then point the user at the index and relay the headline numbers the script prints:

```bash
open runs/_reports/index.html      # navigate every bucket; or open all-time.html directly
```

A normal run writes: `all-time.html`, `index.html`, `history.json`, plus a `day/`, `week/`,
and `month/` file **for each period that has runs** — the current ones (refreshed live) and
any missing past ones (backfilled). A period with no runs gets no file, and existing
past-period files are left untouched (frozen).

## Output layout (`runs/_reports/`)

```
runs/_reports/
├── index.html            ← landing page: links every bucket + monthly trend (from history.json)
├── history.json          ← per-bucket KPI rollups + config_key; the durable history record
├── all-time.html         ← full dashboard over all runs
├── day/2026-07-30.html …
├── week/2026-W31.html …
└── month/2026-07.html …
```

## Freeze / history model (important)

- **Bucketing:** each run is placed by its `run_started_at` converted to `--tz` (default
  **Asia/Shanghai**). Weeks are ISO (`YYYY-Www`, Monday-start); months `YYYY-MM`; days
  `YYYY-MM-DD`.
- **A period file exists iff that period has ≥ 1 run.** Empty periods get no file, no history
  row, no index entry. `all-time.html` + `index.html` always regenerate (the entry points).
- **Current buckets** that have runs and **all-time** are regenerated every run (live).
- **Past buckets freeze once their data is complete.** Each bucket's `history.json` row stores
  a content **signature** of its run-set. On every run, a past bucket is **refreshed once** if
  its current signature differs from the snapshot's — runs were added or a run gained data
  after the bucket was last generated — and then it freezes again. A past bucket whose data is
  unchanged is left untouched (shows a "❄ Archived snapshot" banner with its `as_of`).
- **To force-refresh a frozen bucket**: `--force-regenerate` (rewrites every archived bucket)
  or, surgically, `--period <id>` (rewrites just that one, touching nothing else).
- **history.json** preserves the row (and signature) of any bucket it didn't regenerate. It
  records a `config_key` = `{tz, include_archived, include_legacy, id_pattern}`; a run whose
  config differs **refuses to merge** (use a different `--reports-dir` or `--reset-history`).
  The id pattern is part of the key because past pages frozen under one grouping must never
  silently disagree with live pages built under another.
- **Ad-hoc filtered runs** (`--ticket` / `--scenario` / `--since` / `--until`) produce a
  **single** `--out` report and **never touch** the canonical history/index/buckets — a
  filtered view cannot corrupt the comparable history.
- **Undated runs** appear in all-time only and are noted in each period footer.

## Options

| Flag | Default | Purpose |
|------|---------|---------|
| `--id-pattern <regex>` | — (**required**) | The resolved issue2pr profile's anchored `id_pattern`. Part of `config_key`. Refuses when absent. |
| `--tz <IANA>` | `Asia/Shanghai` | Timezone for day/week/month boundaries. Part of `config_key`. |
| `--reports-dir <dir>` | `runs/_reports` | Root of the canonical bucketed tree + history + index. |
| `--force-regenerate` | off | Overwrite **archived** (frozen) period files too — to fix mistakes. |
| `--period <id>` | — | Surgically (re)generate one bucket id, e.g. `2026-W31`, `2026-07`, `2026-07-30`. |
| `--reset-history` | off | Rebuild `history.json` under the current `config_key` (e.g. after a `--tz` or pattern change). |
| `--days-only` / `--weeks-only` / `--months-only` / `--all-time-only` | off | Restrict which kinds are produced. |
| `--include-archived` | off | Include `runs/_archived/**` (part of `config_key`). |
| `--include-legacy` | off | Include the `runs/jira/` legacy-attempts directory (part of `config_key`). |
| `--ticket K[,K…]` / `--scenario s[,s…]` / `--since YYYY-MM-DD` / `--until …` | — | **Ad-hoc** filter → single `--out` report, never touches canonical history. |
| `--out <file>` | none (canonical) / `runs/_reports/runs-stats-adhoc.html` (ad-hoc) | Optional extra copy (canonical) / ad-hoc output path. |
| `--reviewer-rate input=<n>,output=<n>[,cached_input=<n>,reasoning=<n>]` | off → tokens only | Enable a cost estimate (cached & reasoning priced explicitly). |

## What each report contains

Headline KPIs (tasks vs runs, success/stopped/failed, reviewer tokens with cache %, worker ≈
estimate, active time, PRs, commits, findings, tool calls) · status & composition charts ·
throughput over time · a sortable **Tasks table** (each row → attempt runs → per-run
timing/tokens/verdicts + timeline) · tokens & cost · review quality · reliability (stop
reasons, tests) · a **Containers** section (batch/epic, not counted as tasks) · a
data-quality footer. **Reviewer token panels label each run from its recorded metadata** —
the run's model field when present, else its backend, else `(unrecorded)` — never a
hardcoded model name.

## Correctness guarantees (verified by tests/test_runs_stats.py)

Tz-aware bucketing (a 17:30 UTC run buckets to the next day in Asia/Shanghai) · accurate
reviewer tokens from backend event streams · timing de-duplicated across summary/iter/per-repo
logs · `</` escaped so a `</script>` in any timeline can't break the page · a single malformed
file becomes a warning, never aborts · immutability: past files frozen, only
`--force-regenerate`/`--period` overwrite them · ad-hoc isolation leaves `history.json`
byte-identical · generated pages carry no external resource references.

## Quick checks

```bash
GEN="${CLAUDE_PLUGIN_ROOT}/skills/runs-stats/scripts/generate_runs_stats.py"
PATTERN='^vibe-(\d+)$'                     # example — read the real one from the profile
python3 "$GEN" --id-pattern "$PATTERN"                                    # live buckets + index
python3 "$GEN" --id-pattern "$PATTERN" --force-regenerate --period 2026-07  # fix one month
python3 "$GEN" --id-pattern "$PATTERN" --ticket vibe-52 --out /tmp/t.html   # ad-hoc, isolated
```

`--ticket` accepts full work-item ids under the profile's pattern; the script buckets a
metadata-less run by the id found in its folder name.
