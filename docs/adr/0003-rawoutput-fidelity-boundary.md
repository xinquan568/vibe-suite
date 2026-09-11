# ADR-0003 — A capped `rawOutput` carries only what the engine emitted

**Date:** 2026-09-11 · **Issue:** [#264](https://github.com/xinquan568/vibe-suite/issues/264) (the question) · [#307](https://github.com/xinquan568/vibe-suite/issues/307) (this record)

## Status

Accepted.

## Context

vibe-274 bounded the persisted `rawOutput` (`RAW_OUTPUT_BYTES`, `scripts/lib/render.mjs:289`). Its
**Decision 8** settled what happens when the event carrying the verdict is itself too large to retain:
the capture keeps no parseable completed `agent_message` at all, and the Stop gate takes its declared
no-verdict route. The reasoning recorded there is that *surfacing a stale earlier verdict is worse
than surfacing none*.

That decision is load-bearing in code, not merely written down. `isCompletedAgentMessage`
(`render.mjs:322`) matches a parseable completed `agent_message` **whatever its `text`**, and is
deliberately wider than `isControllingLine` (`:331`), which matches only a message that would control
the verdict. The wider predicate is what draws suppression-run boundaries, so no completed
`agent_message` — not even one with nullish text — survives inside a suppressed capture. Two tests
pin it: `S3: suppression never retains an earlier, stale controlling event (I3)`
(`tests/node/raw-output-bound.test.mjs:286`) at the unit level, and
`vibe-274: an OVERSIZED controlling verdict leaves no parseable agent_message (bullet 3)`
(`tests/node/stop-gate.test.mjs:1073`) end-to-end through the real hook.

**#264 tested whether that boundary holds under pressure.** It asked for a "gate-equivalent NDJSON
verdict projection" — valid NDJSON, inside the budget, that would let the gate reach the verdict the
untruncated stream carried. The request is reasonable on its face and the motivating gap is real: a
controlling message larger than the bound means the gate falls open for a verdict the runner had
already read cleanly.

It is nonetheless unbuildable, because the gate reads exactly one thing. `verdictFrom`
(`scripts/stop-review-gate-hook.mjs:247`) delegates to `readEventStream`
(`scripts/lib/events.mjs:35`) and takes its `agentMessage`. So **any projection the gate can see is a
synthesized completed `agent_message` inside `rawOutput`** — precisely what Decision 8 and invariant
I3 forbid. The two requirements are the same bytes viewed from opposite ends; no encoding satisfies
both.

What makes this worth an ADR is not the conclusion but how close it came to being reversed by
accident. #264 never mentions Decision 8 — it predates vibe-274 — and would have overturned it as a
side effect of an implementation. What caught it was a reviewer reading a comment in a test file. The
decision was discoverable only by already knowing where to look.

## Decision

**May a capped `rawOutput` ever contain content the engine did not emit, other than the elision
marker? — No.** (Xinquan, 2026-09-11.)

Three grounds:

1. **An accepted property is not generalized away by a downstream issue.** Decision 8 took six review
   rounds and shipped with code and tests behind it. An issue that predates it does not get to reverse
   it by implication.
2. **A transcript must not contain content the engine never emitted.** `rawOutput` is evidence. Once
   it can carry synthesized events, no reader — the gate, an operator reading `jobs show`, a later
   auditor — can distinguish what the model said from what the runner decided it would have said.
   Truncation loses information; synthesis destroys the ability to tell that anything was lost.
3. **A declared fail-open beats a fabricated answer.** `applyFailPolicy(gate, "no parseable
   ALLOW/BLOCK verdict")` (`stop-review-gate-hook.mjs:408`, defined `:296`) is visible, configurable
   and auditable. A synthesized verdict is none of those, and its fidelity cannot be checked
   afterwards by anyone.

**Forbidden:** any synthesized event the gate's fold can visit — which, because
`isCompletedAgentMessage` is the wider predicate, means any parseable completed `agent_message`
regardless of its `text`.

**Permitted:** carrying a fact the runner already derived from the untruncated stream to its consumer
**out-of-band**, leaving `rawOutput` untouched. The runner folds the stream once and persists
`verdictText` and `verdictState ∈ absent | empty | present` before any capping. Moving that to the
consumer adds no second reader and no synthesis — it stops one fact being derived twice, the second
time from a lossy copy. [#305](https://github.com/xinquan568/vibe-suite/issues/305) is that work.

**Sole exemption:** the elision marker (`MARKER_PREFIX`, `render.mjs:291`), per vibe-274 Decision 13.
It is deliberately not valid NDJSON, so it is never an event any reader can visit — it is a disclosure
that bytes were removed, which is the opposite of synthesis.

This answer **confirms** Decisions 8 and 13 and invariants I1 and I3. It does not revisit them, and it does
not settle the byte budget — `RAW_OUTPUT_BYTES` is justified by a file that no longer exists, which is
[#306](https://github.com/xinquan568/vibe-suite/issues/306), deliberately left open here.

## Consequences

#264 is closed as unimplementable-as-written rather than re-scoped, and the gap it named is addressed
out-of-band by #305.

Reopening this decision means changing four artifacts **together**. A change touching only some of
them looks complete and is not:

| Artifact | What it holds |
|---|---|
| `scripts/lib/render.mjs:322`, `:331` | `isCompletedAgentMessage`, deliberately wider than `isControllingLine`, and the suppression-run boundary it draws |
| invariant **I3** | no parseable completed `agent_message` survives suppression — whatever its `text` |
| invariant **I1** + vibe-274 Decision 13 | byte-identical source provenance (`tests/node/raw-output-bound.test.mjs:363`, enforced at `:366`), with the elision marker as its single exemption |
| `tests/node/raw-output-bound.test.mjs:286` | `S3: suppression never retains an earlier, stale controlling event (I3)` |
| `tests/node/stop-gate.test.mjs:1073` | `vibe-274: an OVERSIZED controlling verdict leaves no parseable agent_message (bullet 3)` |

**Procedure for reopening, as #307 specifies it:** a dedicated issue naming Decision 8 in its `Do`,
reviewed on its own merits — **never as a side effect of a downstream change**. The cost of the
alternative is already recorded above: #264 would have reversed a settled decision without ever
naming it.

Line numbers here are anchored to symbol and test names on purpose. A line number goes stale
silently; a name does not.
