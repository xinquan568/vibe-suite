# AC-4 — loop bounds, and which half of it is reachable here

> With a stub reviewer that never returns a clean verdict, every generator-critic loop stops at its
> configured cap with the correct terminal status recorded; a malformed verdict triggers exactly one
> re-ask then degrades and records, never aborts.

## What this harness can and cannot establish

**No process in this repository executes a markdown loop.** The three loops are documents read by a
host session. `VIBE_SUITE_CODEX_BIN` substitutes the *inner codex executable*, and
`scripts/codex-runner.mjs` dispatches and returns an event stream — it does not parse a verdict and it
does not decide to re-ask. Those are the host's, from the contract's verdict-parsing rules.

So a test that dispatched, found the output unparseable, and dispatched again would be exercising
**control flow written in the test**. Counting invocations would measure the harness.

| AC-4 clause | Reachable subject | Tier |
|---|---|---|
| a stub that never returns clean exists | the stub is a program | **Executable** |
| its malformed output really does not parse | likewise | **Executable** |
| exactly one re-ask | **none** — the re-asking code is not a program | **Contract** |
| degrade and record, never abort | each loop's specification | **Contract** |
| each loop stops at *its* cap | the declarations, read from the documents | **Contract** |
| the correct terminal status | only `issue2pr` names one | **Contract**, for the loop that has it |

**What is executable is the stimulus, not the response.** Claiming otherwise is an error this chain
made twice before; this file exists partly so the third time is harder.

## The three loops do not share a vocabulary

| Loop | Cap | Declared in | Run-level terminal status |
|---|---|---|---|
| `refine-proposal` | `max_review_rounds` | a `## Round bounds` block | none named |
| `issue2pr` | `max_review_rounds` | a `## Round bounds` block | `EXIT_MAX_ROUNDS` |
| `fix` | `--max-rounds` | step 5's prose | none named |

`fix`'s `FIXED` / `NOT FIXED` / `PARTIAL` / `REGRESSED` are **per-issue verdicts**, and `NOT FIXED` and
`PARTIAL` normally *continue* the loop. Reading them as terminal statuses would invert their meaning.

## `fix` does not satisfy AC-4's re-ask clause

It cites no section of the reviewer contract — it predates it — and its unusable-verification path
falls back and stops rather than re-asking once.

That is a gap in the artifact, not in this harness. **Issue #123** is filed to close it. This harness
**characterises** the gap: it asserts `fix` does *not* cite the contract, so the test fails the day
#123 lands and the assertion is inverted then.

## `loops.json` holds nothing a document could disagree with

Only where each document is, and which extractor reads its declaration — the two shapes differ, and one
parser would have to guess. Caps, contract citations and terminal statuses are read from the documents.

## Stimuli

| Loop | Stimulus | Stub mode |
|---|---|---|
| `issue2pr` | a persistent `major` — a `blocker` **halts the round** before the update loop, so the cap is never reached | `revise` (existing) |
| `refine-proposal` | a persistent `major` at or above `--stop-severity` | `revise` (existing) |
| `fix` | a persistent `NOT FIXED` — it has no severity, and `REGRESSED` *stops* the loop | `never-fixed` |
| all three | output that does not parse | `malformed` |

An unknown mode makes the stub return a **clean** verdict, which is exactly what would make a missing
mode look like a passing one. That is why the assertions are "this mode never returns clean" rather
than "this mode exists".

## One assertion here has a strength that cannot be stated exactly

`test_fix_verdicts_carry_their_continue_or_stop_meaning` is in two halves, and they are not equally
strong. The distinction is recorded because every other claim in this directory is stated exactly, and
an unmarked weak assertion sitting among them would borrow their credibility.

| Half | Property | Strength |
|---|---|---|
| `declared-continuing` | `commands/fix.md` **must say** `NOT FIXED` and `PARTIAL` keep the loop going | **closed.** Presence — the sentence is there or it is not. No rewording satisfies it, and deleting the claim fails it. |
| `backstop` | no sentence naming those verdicts also uses stopping language | **open, and evadable by construction.** |

The backstop matches stopping verbs from a list. The set of English words meaning "stops" is not
finite, so a phrasing outside the list passes. This is not hypothetical: review iteration 3 closed
four phrasings, and iteration 4 was handed a fifth — *"PARTIAL causes the loop to exit"*. Adding
`exit` does not close the class. `cease` and `conclude` are next.

It is kept anyway, because a contradicting sentence added *alongside* the required one would satisfy
the closed half, and catching the common phrasings is worth more than nothing. It is **a backstop, not
a proof**, and no reading of a green suite should treat it as one.
