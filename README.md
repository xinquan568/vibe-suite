# `auditor-data` — ops-data branch (D9)

This orphan branch carries the auditor unit's accumulated operational data, kept off `main` so
plugin installs stay lean (decision D9; merge proposal §7A row 9). It shares no history with `main`.

## Layout (managed by `tools/migrate-auditor-data.sh`)

The migration/ops tooling manages these paths — do not hand-edit them:

- `reports/`, `exemplars/`, `audits/`, `ledgers/`, `articles/` — the five §7A data categories
- `.vibe-suite-migration/` — reserved provenance prefix owned by `tools/migrate-auditor-data.sh`;
  the tool refuses to touch it unless its own `provenance.json` proves ownership

Ops data arrives via E8.5 (`tools/migrate-auditor-data.sh`, count+hash-verified, idempotent).
Only regular files belong on managed paths — the tooling refuses symlinks/gitlinks there.

Provisioned by E8.1 (vibe-58); runbook: `auditor/README.md` on `main`.
