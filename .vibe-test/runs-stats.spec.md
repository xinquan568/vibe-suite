---
artifact: skills/runs-stats/SKILL.md
type: skill
min_score: 80
---

# runs-stats — suite spec (vibe-52 / E6.6)

Source: F8.5 (`/vibe-suite:runs-stats` — time-bucketed statistics over issue2pr runs),
narrowed by E6.6. This spec restates the proposal's expectations as a test; the artifact's
author inherits these, not inventions. The skill is a direct port of the workspace
runs-stats skill with three changes: profile-aware ticket identity, reviewer labels from
run metadata, vendored (inlined) chart library.

## Triggers On
- "/vibe-suite:runs-stats"
- "summarize the issue2pr runs this month"
- "generate the runs statistics dashboards"
- "how many review tokens did the runs use over time"
- "build an ad-hoc report for one ticket's runs"

## Does Not Trigger On
- "score this command file"                       (scoring, not run statistics)
- "watch the open PR for this run"                 (issue2pr's own watcher)
- "render the quality report blob"                 (/vibe-suite:report's job)

## Frontmatter Valid
- description present, naming the runs/ tree, the bucketed dashboards, and the frozen-bucket model
- no pinned model id anywhere (reviewer labels come from run metadata)
- description names the profile-supplied id pattern (the generator refuses without one)

## Output Contains
- an invocation of scripts/generate_runs_stats.py with --id-pattern threaded from the resolved issue2pr profile
- the freeze/refresh rules (past buckets frozen; --force-regenerate / --period for surgical rebuilds)

## Behavior
- **Identity**: the skill resolves the issue2pr profile's `id_pattern` and passes it as
  `--id-pattern`; a missing pattern is the generator's refusal (exit 2 with the profile
  pointer), never a silent generic fallback.
- **Offline charts**: generated pages inline the vendored Chart.js — no CDN reference, no
  network needed to render.
- **Labels**: token panels label each run from recorded metadata (model field, else
  backend, else "(unrecorded)") — no hardcoded model name anywhere in the skill.
- **Isolation**: ad-hoc filtered runs (`--ticket/--scenario/--since/--until`) write one
  `--out` report and leave the canonical history byte-identical.
- **Timezone**: bucketing follows `--tz`, default `Asia/Shanghai`.
