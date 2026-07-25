# `docs/discussion/` — planning records

The proposal and execution plan vibe-suite was built from, preserved for traceability.

**These are historical documents.** They record decisions as they were made, including decisions
later superseded. Where a discussion document disagrees with current configuration — manifests,
workflows, or the issue2pr profile — **current configuration wins**. Each file carries a banner
noting its known divergences.

## Lint exclusion (declared, not implicit)

This directory is **excluded from the repository-wide pinned-model-identifier scan** (principle P9)
by the `--exclude-dir=discussion` flag in `.github/workflows/ci.yml`.

The exclusion is deliberate and narrow. P9 forbids versioned model identifiers in *shipped
artifacts* — things that configure behaviour. These files configure nothing: they are verbatim
historical records, and the model names in them appear in prose *arguing for* P9. Redacting them
would make them no longer the documents that were written.

The exclusion is declared here and in the workflow so it is auditable. It applies to this directory
only; every other path in the repository is scanned without exception.
