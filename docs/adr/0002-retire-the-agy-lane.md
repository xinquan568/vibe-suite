# ADR-0002 — The agy cross-model lane is retired, not graduated

**Date:** 2026-09-10 · **Issue:** [#297](https://github.com/xinquan568/vibe-suite/issues/297) (decision) · [#298](https://github.com/xinquan568/vibe-suite/issues/298) (execution)

## Status

Accepted

## Context

D5 and D8 staged a second cross-model audit engine, `agy`, behind a **contract gate**: a default
execution path may not rest on an unverified CLI contract, so `cross_model_audit_engine` stayed
`codex` until a committed record showed every check passing. The gate's record lived at
`tests/agy-contract/gate-status.json` and its flip procedure at `docs/agy-flip-checklist.md`. Both are
deleted by this decision, so **the record's terminal state is restated here** — after this ADR there is
nowhere else on `main` that explains it.

**The gate's final state was `not_passed`:**

| Check | State | Why |
|---|---|---|
| `headless_invocation` | **failed** | the probe's call was answered with an OAuth prompt, not a response |
| `timeout_kill` | passed | an over-deadline invocation was killed and its process group confirmed gone |
| `read_only_write_denied` | not_verified | unauthenticated: no model turn ran, so nothing was denied |
| `failure_signature` | not_verified | no failed-class response was provoked |
| `quota_signature` | not_verified | no quota-class response was provoked |

**`read_only_write_denied` could not pass, and that is a property of the surface rather than of the
effort spent on it.** A denial only means something if the *tooling* reports it. agy offered no
tooling-only channel — no `--json`, no structured event stream, no denial log tied to the attempted
path — so every signal arrived on the same stdout the model writes to. Any phrase agreed to count as
proof of a denial is a phrase the model can simply emit. The sentinel file's absence could not
substitute either, because a model that never attempted a write also leaves no file. The probe
therefore had **no passing branch at all** for that check: its outcomes were `failed` (a landed
sentinel — positive evidence the sandbox did *not* prevent the write) and `not_verified` (everything
else). An earlier draft kept a passing branch behind an empty phrase registry and called the property
"can never pass"; a reviewer opened the gate by adding one phrase, which is why the branch was
removed rather than guarded.

Two honest routes to `passed` existed, and both were deliberate changes someone would review: a
future agy emitting a **provenance-bearing denial event** tied to the attempted path, or a **manual
verification** recorded by a named maintainer who watched a write be refused, with the evidence
attached to the PR.

The lane's release status was **"staged; unavailable in this release"**, with a decision gate at the
`v0.0.1-alpha1` cut: graduate it, or demote it.

## Decision

**The lane is retired.** `agy` leaves the `engine` and `model_overrides` domains, the runner, audit
CLI, contract probe, gate resolver and fallback chain are deleted, and no shipped surface offers or
mentions it. Graduating inside `v0.0.1-alpha1` would have meant taking the manual-verification route
knowingly; the owner declined it.

Four choices inside that decision are load-bearing:

1. **The lane is preserved, not destroyed.** Branch
   [`staging/agy-lane`](https://github.com/xinquan568/vibe-suite/tree/staging/agy-lane) — locked,
   undeletable — and tag `retired/agy-lane`, both at `5290a5c8`. The tag is a second, independent
   handle that survives even if the branch protection is ever lifted.
2. **An existing `engine: agy` fails with a generic `ConfigValueError`.** No migration path and no
   bespoke "retired" message. The lane never shipped as a default, so no working configuration
   depended on it.
3. **`cross_model_audit_engine` survives as a single-valued enum** (`codex`), the shape
   `reviewer_backend` already has. The lane was the seam's staged occupant, not the seam. Removing
   both would foreclose a decision nobody has taken.
4. **Coverage is re-expressed, not deleted.** Several tests pinned real properties — that the codex
   lane dispatches its runner directly, that a CLI's writes are contained by its workspace — through
   assertions phrased around agy. Those properties outlive the lane; deleting the tests would have
   left the suite greener and the repository less covered.

## Consequences

- `exitCodeFor` no longer carries a name-keyed exception. It read
  `row.engine !== "agy" && row.auth === "unknown"`, because agy exposed no auth *mode* and `unknown`
  was its truthful terminal answer. Every remaining engine exposes one, so `unknown` now uniformly
  means a failed probe. The exception was reachable only by an agy row, so removing it preserves
  behaviour for codex — pinned by `R-NO-EXEMPT`.
- **Runtime rows are unaffected.** They carry `auth: null`, meaning *there is nothing here to learn* —
  a distinct thing from `unknown`, and the reason `R-AUTH` exists.
- `scripts/lib/engine_resolution.py` needed no change: it receives the engine domain as a parameter,
  so narrowing the schema propagated to the resolver for free.
- The three planning records under `docs/discussion/` and `docs/grill/` still describe the staged
  lane. They are **historical records and are not rewritten**; each carries a divergence banner
  citing this ADR, per `docs/discussion/README.md`.
- **A future second audit engine is not foreclosed.** The seam remains. What this ADR asks of any
  future occupant is what agy could not supply: a read-only enforcement signal that comes from the
  tooling rather than from the model's own prose.
- `#277`, which existed only to build a character-boundary allocator for this lane, closes as moot.
