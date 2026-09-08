# `templates/` — Scaffolding templates

Templates copied or rendered into a target project: advisor personas, the
issue2pr profile contract, pre-commit and CI templates.

- `pre-commit` — git hook invoking `bin/vibe-check` on the repo root; copy to
  `.git/hooks/pre-commit` and mark executable.
- `ci-vibe-check.yml` — GitHub workflow running `bin/vibe-check .`; copy into
  `.github/workflows/` to activate (activation is the release gate's decision, P7).
- `runs-stats/` — the two HTML shells (`dashboard.html`, `index.html`) that the
  `/vibe-suite:runs-stats` generator (`scripts/runs_stats/`) renders, plus its vendored Chart.js
  under `vendor/` (provenance in `vendor/VENDORED.md`). Not copied into target projects: every
  generated page inlines them.
