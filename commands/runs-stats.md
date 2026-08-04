---
description: "Generate time-bucketed static HTML statistics dashboards over the issue2pr runs/ tree: an all-time dashboard plus day/week/month reports, index.html, and history.json under runs/_reports/, charts inlined for offline file:// rendering. Past buckets freeze once complete and refresh exactly once when their data changed; ad-hoc filters write one isolated report without touching the canonical history. Requires the resolved issue2pr profile's id_pattern and refuses without it. Arguments: optional generator flags (--tz, --force-regenerate, --period, --ticket, --scenario, --since, --until, --out)."
argument-hint: "[--tz <IANA>] [--force-regenerate] [--period <id>] [--ticket K[,K…]] [--scenario s] [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--out <file>]"
---

# /vibe-suite:runs-stats — statistics dashboards over issue2pr runs

Time-bucketed static HTML dashboards over everything under `runs/` — day / week / month /
all-time — with the frozen-bucket history model and offline-rendering charts.

## What to do

Load [`skills/runs-stats/SKILL.md`](../skills/runs-stats/SKILL.md) and follow it. The skill
owns the whole surface: profile resolution for `--id-pattern` (and the refusal when no
profile resolves), the generator invocation, the freeze/history rules, ad-hoc isolation, and
what to relay to the user afterwards. Pass any flags the user supplied through to the
generator unchanged.
