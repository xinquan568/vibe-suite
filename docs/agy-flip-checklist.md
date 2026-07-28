# The agy contract-gate flip checklist

`cross_model_audit_engine` is **`codex`** and stays there until the agy lane's CLI contract is
*confirmed* — not assumed, not documented, confirmed by an executed probe whose outcome is recorded
in `tests/agy-contract/gate-status.json`. This file is what "confirmed" means, so that a future
maintainer flipping the default is executing a plan rather than making a judgement call alone.

## Why a gate exists at all

D5/D8 stage this lane deliberately: **a default execution path may not rest on an unverified
contract.** If agy became the audit default while its read-only enforcement were merely claimed,
every audit would run with a sandbox nobody had tested — and the failure would be silent, because a
model that says "I did not write the file" is not evidence that it could not.

## Current status

**`not_passed`** — agy 1.1.2 is installed in the authoring environment but **unauthenticated**.
The invocation surface is confirmed; enforcement and failure semantics are not:

The states below are what the **committed record actually holds** after running
`scripts/agy-contract-probe.mjs` against the real binary — not what the draft of this file predicted:

| Check | State | Why |
|---|---|---|
| `headless_invocation` | **failed** | the probe's own call was answered with an OAuth prompt, not a response. (`agy --print` *is* the documented one-shot form; that is a fact about the surface, not an observation of it working here.) |
| `timeout_kill` | passed | `an over-deadline invocation was killed and its process group confirmed gone` |
| `read_only_write_denied` | not_verified | `unauthenticated: no model turn ran, so nothing was denied` — **and it cannot pass at all on this surface; see below** |
| `failure_signature` | not_verified | `no failed-class response was provoked` |
| `quota_signature` | not_verified | `no quota-class response was provoked` |

### `read_only_write_denied` cannot be passed on today's agy

A denial only means something if the **tooling** reports it. agy offers no tooling-only channel —
no `--json`, no structured event stream, no denial log tied to the attempted path — so everything
arrives on the same stdout the model writes to. Any phrase we agreed to accept as proof of a denial,
the model can simply emit; the probe's adversarial test exercises exactly that. And the sentinel
file's absence cannot substitute, because a model that never tried to write also leaves no file.

So the probe has **no passing branch for this check at all** — not an empty registry, no branch. Its
outcomes are `failed` (a landed sentinel: positive evidence the sandbox did NOT prevent the write) and
`not_verified` (everything else). `classifyWriteProbe` therefore has **no passing branch at all** — not an unreached one. (An earlier
draft kept the branch behind an empty registry and called the property "can never pass"; a reviewer
opened the gate by pushing one phrase into that registry. A promised absence must be absent from the
code.) Two honest routes to `passed` exist, and both are deliberate changes someone reviews:

1. A future agy that emits a **provenance-bearing denial event** tied to the attempted path — which
   would mean adding a passing branch that consumes that typed event.
2. A **manual verification** recorded by a named maintainer who watched a write be refused, with the
   evidence attached to the PR.

### What the gate actually enforces — and what it does not

Be clear-eyed about the trust model, because overstating it is the same defect as an unverified
sandbox one level up. `resolveAgyGate` validates the record's **shape**: schema, exact keys, exact
check set, and that every check plus the top-level status says `passed`. It **cannot** validate that
a human observed anything — there is no signature scheme here, and this issue is not where one
belongs.

So the honest statement is: **the committed `gate-status.json` is the trusted authority, and
graduating the lane means editing a code-reviewed file in a pull request.** That is a human gate, but
a social one — reviewers reading a diff — not a cryptographic one. Anyone who wants a stronger
guarantee should add signed attestations deliberately, not assume the resolver already provides them.

Two consequences worth stating rather than discovering:

- **`VIBE_SUITE_AGY_GATE_FILE` overrides the record** for any process that sets it. That is a testing
  seam with the same posture as `VIBE_SUITE_CODEX_BIN`: whoever can set it already controls the
  process environment, so it confers nothing new — but it is emphatically **not** a boundary, and no
  claim here should be read as if it were.
- **This checklist and the doctor notice are coordination, not enforcement.** The resolver never reads
  them. They exist so that a graduation is done deliberately and visibly, by someone who has followed
  the steps — not because the code would stop them otherwise.

## Before the flip — every item, in order

1. **Authenticate** the agy CLI in the environment where the probe will run.
2. **Run the probe**: `node scripts/agy-contract-probe.mjs --write-record`. It records what it
   observes; it cannot be argued with.
3. **`read_only_write_denied` must be `passed` — which today it cannot be.** Passing requires
   provenance-bearing evidence from the tooling that an attempted write was refused. The sentinel
   file's absence only **corroborates** such evidence; it can never supply it, because a model that
   never tried also leaves no file. See the section above.
4. **`failure_signature` and `quota_signature` must be `passed`** — provoke each and confirm the
   runner classifies it. An unprovoked signature stays `not_verified`; the gate stays shut.
5. **Commit the record** with `status: "passed"`. `resolveAgyGate` requires the status *and* every
   check to agree, so a hand-edited status alone changes nothing.
6. **Change the config default** to `agy` in the engine-selection partial's staged table and the
   config reader's default.
7. **Ship the doctor notice** in the same PR: `/vibe-suite:doctor` must tell existing users that
   the cross-model audit engine changed, name the new default, and show how to pin `codex` in
   `.vibe-suite.md` if they prefer it. A default that changes under people without telling them is
   the same defect as an unverified sandbox, one layer up.
8. **Rollback**: reverting the record to `not_passed` closes the lane immediately — the resolver is
   the only consumer, so no other code needs touching.

## What must remain true afterwards

- `--engine agy` before graduation errors with the gate status. After graduation, an unreachable
  agy **hands off to codex** with the F9.5 diagnostic header — it does not stop the session.
- No model id is ever pinned (P9). `--model` remains an explicit per-run override.
