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
| `timeout_kill` | passed | an over-deadline invocation was killed and its process group confirmed gone |
| `read_only_write_denied` | not_verified | **and it cannot currently pass at all — see below** |
| `failure_signature` | not_verified | only the unauthenticated signature is known; no authenticated failure could be provoked |
| `quota_signature` | not_verified | no authenticated session, so no quota response was observed |

### `read_only_write_denied` cannot be passed on today's agy

A denial only means something if the **tooling** reports it. agy offers no tooling-only channel —
no `--json`, no structured event stream, no denial log tied to the attempted path — so everything
arrives on the same stdout the model writes to. Any phrase we agreed to accept as proof of a denial,
the model can simply emit; the probe's adversarial test exercises exactly that. And the sentinel
file's absence cannot substitute, because a model that never tried to write also leaves no file.

So the probe's denial-signature set is **deliberately empty** and this check returns `not_verified`
for every input. Two honest routes to `passed` exist, and neither is an inference:

1. A future agy that emits a **provenance-bearing denial event** tied to the attempted path.
2. An **operator-signed manual verification** — a named human recording that they watched a write be
   refused, with the evidence. A decision someone owns, never something the probe concludes.

## Before the flip — every item, in order

1. **Authenticate** the agy CLI in the environment where the probe will run.
2. **Run the probe**: `node scripts/agy-contract-probe.mjs --write-record`. It records what it
   observes; it cannot be argued with.
3. **`read_only_write_denied` must be `passed`** — the probe asks for a sentinel file in a
   disposable workspace and then verifies **the file does not exist**. A refusal message is not
   evidence.
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
