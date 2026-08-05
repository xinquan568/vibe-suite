---
description: "Read-only health check for a vibe-suite installation: bridge integrity, sentinels in both stores, symlinks, pins, hook wiring, config validity, provenance, and leftover legacy stores. Reports an issues table with auto-fixable flags and a separate capability table for checks that cannot run yet. Changes nothing. No arguments."
argument-hint: ""
---

# /vibe-suite:doctor — health check

Diagnoses an installation and **changes nothing**. Anything it marks auto-fixable is
`/vibe-suite:repair`'s job, not this command's — that separation is what makes doctor safe to run on
a project you do not yet understand.

## What to do

### 1. Run the diagnosis

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --workspace .
```

Add `--json` when you need the structured form; the command itself takes no arguments.

### 2. Present both tables, and keep them apart

**Findings** are defects in *this project*. **Capabilities** are checks that cannot run yet in *this
installation* — F4.4 pending #30, mirror staleness live against codex/MIRROR-MANIFEST.json (E7.2), cross-manifest version coherence,
and §7A row 9.

Do not merge them. `vibe-core` makes `[GOOD]` **exclusive**: a report containing it contains exactly
that one entry. Filing an unavailable capability as a finding would mean no project could ever
report clean, which is half of what this command exists to say.

A check that is absent from the output is indistinguishable from one that passed, so every check
named by F1.2 appears in one table or the other.

### 3. Interpret the state

| State | Meaning |
|---|---|
| `uninitialised` | Nothing is installed. The missing-component cascade is suppressed — but legacy stores and capabilities are still reported, because a project holding a `.cc-suite.md` needs that said precisely because it has **not** been migrated. |
| `partial` | Owned artefacts exist but provenance is absent or malformed. Say plainly that `/vibe-suite:unbridge` **cannot restore what provenance does not describe**. |
| `installed` | Provenance is present and every entry can restore. |

### 4. Offer repair, do not perform it

Where any finding is auto-fixable, point at `/vibe-suite:repair`. Never edit a file from this
command.

## Connectivity

Codex and agy connectivity belong to `/vibe-suite:preflight`, which already computes a normalised
result for both lanes. Doctor cites it rather than probing again — a second opinion on the same
question is worse than one. agy's `available` verdict stays **pending** behind its contract gate; the
version, smoke and model probes still run there.

## Knowledge freshness

The refresh date lives **beside the skill it describes**, at
`${CLAUDE_PLUGIN_ROOT}/skills/<skill>/refreshed.json` as `{"refreshed": "<ISO-8601 date>"}` — plugin
level, not project level, because one shared skill cannot have two projects disagreeing about when it
was refreshed. **`/vibe-suite:refresh-knowledge` (E6.5/#51) writes it.** A missing record means the
overlay was **never refreshed** — the producer exists and simply has not been run — so the check
reports `unavailable` with that wording. A present record surfaces its date
(`refreshed <YYYY-MM-DD>`) and, when the overlay's canonical `**Spec freshness:**` prose line
carries a comparable date, names whichever refresh path is staler (`/vibe-suite:spec-sync` when the
prose is older, `/vibe-suite:refresh-knowledge` when the record is). A record whose date is not a
real dashed `YYYY-MM-DD` is a `[LOW]` finding, not a capability — a corrupt date must not read as
fresh.
