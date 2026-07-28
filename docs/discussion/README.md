# `docs/discussion/` — planning records

The proposal and execution plan vibe-suite was built from, preserved for traceability.

**These are historical documents.** They record decisions as they were made, including decisions
later superseded. Where a discussion document disagrees with current configuration — manifests,
workflows, or the issue2pr profile — **current configuration wins**. Each file carries a banner
noting its known divergences.

A divergence has two sources. It may be **current configuration**, as with the `/vibe:` →
`/vibe-suite:` namespace reversal, which follows from `.claude-plugin/plugin.json:name`. Or it may be
a **decision made after the document was frozen**, recorded in [`../adr/`](../adr/) — a frozen
document cannot be the authority for a decision that postdates it. Either way the banner **states
what is true now** and cites the source; the body is left as written. Rewriting a body would make the
file no longer the document that was written, which is the whole reason this directory exists.

## Lint exclusion (declared, not implicit)

This directory is **excluded from the repository-wide pinned-model-identifier scan** (principle P9)
by the `--exclude-dir=discussion` flag in `.github/workflows/ci.yml`.

The exclusion is deliberate and narrow. P9 forbids versioned model identifiers in *shipped
artifacts* — things that configure behaviour. These files configure nothing: they are verbatim
historical records, and the model names in them appear in prose *arguing for* P9. Redacting them
would make them no longer the documents that were written.

The exclusion is declared here and in the workflow so it is auditable. It applies to this directory
only; every other path in the repository is scanned without exception.
