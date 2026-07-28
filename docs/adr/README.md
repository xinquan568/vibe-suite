# `docs/adr/` — Architecture Decision Records

A decision that outlives the conversation it was made in lives here. Discussion documents under
[`../discussion/`](../discussion/) are frozen historical records; where one of them disagrees with a
decision made later, the divergence is noted in that document's banner and the banner cites the ADR
that settles it. **An ADR is live: it is the current answer, not a record of a past conversation.**

## Conventions

- **Filename** — `NNNN-kebab-slug.md`, four digits, allocated in order and never reused.
- **Reference** — `ADR-NNNN` anywhere in the repository. Every such string must resolve to a file in
  this directory, and every index row below must link to the file it names. **Nothing enforces this
  mechanically yet** — a checker was written for #71 and withdrawn from that PR as disproportionate to
  a documentation change, after review found it passing a tree where an ADR had been renamed and the
  index link left stale. Until it lands, the conventions here are maintained by reading.
- **Sections** — `## Status`, `## Context`, `## Decision`, `## Consequences`, in that order.
- **Status** — one of `Accepted`, `Proposed`, `Rejected`, `Deprecated`. A superseded decision is
  marked `Deprecated` **and its body is left standing**, with a line naming the ADR that replaced it.
  Rewriting a decision's body destroys the record of what was decided and why — the same rule
  `../discussion/README.md` states for planning documents, applied to a live series.

## Index

| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-0001](0001-audit-report-schema-validation.md) | Audit-report schema validation belongs to `bin/vibe-check` | Accepted | 2026-07-28 |
