# ADR-0001 — Audit-report schema validation belongs to `bin/vibe-check`

**Date:** 2026-07-28 · **Issue:** [#71](https://github.com/xinquan568/vibe-suite/issues/71)

## Status

Accepted

## Context

[`schemas/audit-output.schema.json`](../../schemas/audit-output.schema.json) is the machine-readable
form of the finding contract. [`skills/vibe-core/SKILL.md`](../../skills/vibe-core/SKILL.md) makes it
governing: *"**JSON is canonical**; the Markdown below is its rendering. Where the two appear to
disagree, the schema governs."*

Three planning statements disagreed about who checks documents against it.

- **F9.1** assigns the job: *"The orphaned cc-suite `audit-output.schema.json` is revived as the
  machine-readable schema for this contract; **F4.4 validates reports against it**."*
- **F4.4** does not claim it. Its heading reads *"`vibe-check` — deterministic CI validator (**Python,
  stdlib-only**)"*, and its check list — manifest-vs-disk, unregistered skills, frontmatter presence,
  name/dir match, hook event case, monorepo detection, version coherence, mirror staleness — has no
  schema entry.
- **E3.5** (issue [#30](https://github.com/xinquan568/vibe-suite/issues/30)), which implements F4.4,
  omits it too.

The stdlib constraint is what makes this more than an unassigned duty. **Python's standard library
contains no JSON Schema implementation.** `jsonschema`, `ajv`, and `check-jsonschema` are all absent
from the development environment, and CI's JSON handling is `jq empty`, a syntax check. The component
F9.1 named was, by its own specification, unable to do the job F9.1 gave it.

What already exists is
[`scripts/validate_audit_output.py`](../../scripts/validate_audit_output.py), shipped by PR #66. It
implements the thirteen-keyword subset the schema actually uses and raises `UnsupportedSchemaError` on
anything else, so a schema that outruns the checker halts it rather than being partially checked. An
invariant test derives both keyword sets from the artefacts, which makes extending the schema and
extending the checker one change rather than two.

## Decision

**F4.4 — `bin/vibe-check` — owns audit-report schema validation, performed as fail-closed subset
checking, within its stdlib-only constraint.** F9.1 stands unamended; it was right.

The available alternatives, and why each was rejected:

| Option | Rejected because |
|---|---|
| F4.4 gains a JSON Schema dependency | Contradicts its stdlib-only specification and adds an install step to a markdown-first plugin. Gate-ladder rung 3 is `bin/vibe-check` exit 0; a pip dependency makes that gate contingent on an install having happened. |
| Validation moves to a separate tool or CI step | Makes the contract uncheckable locally and drops it out of rung 3. |
| The assignment is dropped; validation is per-consumer | Leaves the schema decorative — close to the orphaned state that produced this defect. |

### What this decision settles, and what it leaves open

Ownership alone is not enough for E3.5 to write a check class, so the surrounding questions are
answered here or deferred by name rather than left silent.

| Question | Answer |
|---|---|
| **Owner** | `bin/vibe-check`, as above. |
| **Serialization** | Already settled, and **not re-decided here**: `skills/vibe-core/SKILL.md` makes JSON canonical. This ADR cites that rule rather than restating it, so there is one authority and not two. |
| **Invocation** | `bin/vibe-check --report <path>` — explicit, always available. This is implementable at E3.5's own landing time against `tests/fixtures/sample-report.json`, which gives the check class a working case and a mutable failing fixture without waiting on anything. |
| **Discovery** | **Deferred.** A pass that finds reports by scanning a tree needs a component that writes conforming JSON. Unblocked when one exists — the same form E3.5 already uses for `--mirrors` staleness, *"live after E7.2"*. |
| **Producer** | **Deferred, and flagged for the F3 stage.** The schema's `agent` enum admits exactly six values — `vibe-suite:recon`, `:architecture`, `:error-handling`, `:edge-cases`, `:security`, `:testing` — so the F3 review agents are where a producer is expected. No F3 item currently specifies JSON emission: F4.9 preserves a findings-table output contract, F3.1 writes a Markdown report, and F10.1's diagnosis-report format is unstated. **Today, nothing emits a document this schema accepts.** |

## Consequences

**`bin/vibe-check` inherits the subset limitation, deliberately.** It will validate only the keyword
subset this project's own schema uses. That subset is bounded by a schema this project controls, and
the fail-closed design turns any gap into a loud `UnsupportedSchemaError` instead of a silent pass.
Adding a keyword to the schema requires adding it to the checker in the same change.

**E3.5 (#30) grows.** It gains an audit-report schema-validation check class and, per its existing
acceptance pattern (*"each check class has a failing fixture"*), a fixture that fails. Its `size:M`
estimate should be read as covering that.

**The contract is not enforced end-to-end, and this ADR does not pretend otherwise.** With no producer
emitting conforming JSON, `--report <path>` validates documents that are written by hand or by a
future component. The gate ladder's rung 3 does not exist yet either.

**Nothing mechanically binds a future `bin/vibe-check` to this decision**, and nothing checks this
record either. `tests/test_audit_output_schema.py` compares the schema's keywords against the
checker's implemented set and is silent on ownership. A structural guard over this ADR series was
written alongside this record and withdrawn from the same pull request as disproportionate to a
documentation change; it is not in the tree. So both obligations — that `bin/vibe-check` honours this
decision, and that this ADR stays well-formed and correctly referenced — are carried in writing, and
a reviewer has to check them by reading. That residue is stated rather than papered over.

**The two planning documents are not edited.** `docs/discussion/` holds frozen historical records;
each carries a banner where later divergence is noted, and both banners now state this decision
inline and cite this ADR. Their bodies are unchanged, as the D1-revised namespace reversal left its
hundred `/vibe:` occurrences standing.
