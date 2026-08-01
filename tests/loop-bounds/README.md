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

## The verdict-semantics assertion, and what it is worth

`test_fix_verdicts_carry_their_continue_or_stop_meaning` is in two halves of unequal strength. The
difference is recorded because every other claim in this directory states its strength exactly, and an
unmarked weak assertion sitting among them would borrow their credibility.

| Half | Property | Strength |
|---|---|---|
| `declared-continuing` | `commands/fix.md` declares the round loop in **exactly** the words held in `REQUIRED_CONTINUE_DECLARATION` | **closed**, because it is a string equality. No sentence satisfies it while meaning something else. |
| `backstop` | no sentence naming `NOT FIXED`/`PARTIAL` also uses stopping language | **open, and evadable by construction.** |

### Three attempts to infer meaning, and why they were abandoned

The first half was rewritten three times, each time as a cleverer regex, and each version passed on
text that inverted the semantics it was written to protect:

| Attempt | Check | Beaten by |
|---|---|---|
| 1 | no stopping phrase *after* the verdict | putting the phrase in front |
| 2 | no stopping verb stem in the sentence | "causes the loop to **exit**" |
| 3 | a continuing word *near* the verdict | "**continue** to reporting; any `NOT FIXED` or `PARTIAL` **prevents another round**" |

Attempt 3 was claimed in review to be closed, on the reasoning that presence cannot be faked. It can:
the counterexample contains `continue` and `another round` within the window while asserting the exact
opposite, and `prevents` belongs to no stop-list.

Every attempt matched **lexical proximity rather than the relation** between the verdict and the verb,
so each fell to a sentence with the right words in the wrong relation. A string equality has no
relation to get wrong, which is why the check is now golden text — the approach the rest of this
repository already uses for things that must not drift.

**Rewording that clause fails the suite.** That is the cost and it is deliberate: loop semantics cannot
change as a side effect of an edit, and whoever rewords it updates the constant on purpose.

### What the backstop is, and is not

The anchor fixes what the document *declares*. It cannot stop a contradiction being added elsewhere in
the file, and catching that needs the meaning-detection the three attempts above established cannot be
done reliably here. `prevents another round` is **still not caught**, deliberately — adding it would
restart the enumeration this test just abandoned.

It is **a backstop, not a proof**, and no reading of a green suite should treat it as one.
