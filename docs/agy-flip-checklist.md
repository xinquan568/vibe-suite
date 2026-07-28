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

| Check | State | Why |
|---|---|---|
| `headless_invocation` | passed | `agy --print <prompt>` is the documented non-interactive one-shot |
| `timeout_kill` | passed | our detached process-group kill, proven against a signal-ignoring fixture |
| `read_only_write_denied` | not_verified | needs an authenticated turn that *attempts* a write |
| `failure_signature` | not_verified | only the unauthenticated signature is known |
| `quota_signature` | not_verified | no authenticated session, so no quota response observed |

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
