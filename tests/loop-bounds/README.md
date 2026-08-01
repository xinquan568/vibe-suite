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
| `declared-continuing` | one **whole sentence** of `commands/fix.md` equals `REQUIRED_CONTINUE_DECLARATION` | **bounded, and its one hole is named below.** No edit *to that sentence* survives. |
| `backstop` | no sentence naming `NOT FIXED`/`PARTIAL` also uses stopping language | **open, and evadable by construction.** |

### Four attempts to infer meaning, and why they were abandoned

The first half was rewritten three times, each time as a cleverer regex, and each version passed on
text that inverted the semantics it was written to protect:

| Attempt | Check | Beaten by |
|---|---|---|
| 1 | no stopping phrase *after* the verdict | putting the phrase in front |
| 2 | no stopping verb stem in the sentence | "causes the loop to **exit**" |
| 3 | a continuing word *near* the verdict | "**continue** to reporting; any `NOT FIXED` or `PARTIAL` **prevents another round**" |

| 4 | the exact clause appears (`assertIn`, substring) | prefixing **"It is false that"**, which preserves the substring |

Attempts 3 and 4 were each claimed closed when submitted for review, and each was refuted with a
counterexample. Attempt 3's reasoning was that presence cannot be faked; attempt 4's was that a string
equality has no meaning to get wrong. Both were wrong in the same direction — a substring says nothing
about the sentence containing it.

Attempts 1–3 matched **lexical proximity rather than the relation** between verdict and verb, so each
fell to a sentence with the right words in the wrong relation. Attempt 4 removed the inference but
compared against the whole document, so a prefix rode along.

The check is now **whole-sentence equality**: `norm()`-ed text is split on sentence boundaries and one
sentence must *equal* the constant. A prefix lengthens the sentence and fails. This is the
golden-fixture approach the rest of this repository uses for things that must not drift.

**Rewording that clause fails the suite.** That is the cost and it is deliberate: loop semantics cannot
change as a side effect of an edit, and whoever rewords it updates the constant on purpose.

### The hole that remains, stated because four rounds of claiming closure did not survive

**A contradicting *neighbour* sentence is not caught.** Leaving the required sentence intact and adding
`The preceding sentence is void.` after it passes the suite. This is verified, not theoretical — it is
one of the mutation cases.

No prose check closes it. Catching a contradiction anywhere in a document is the meaning-detection that
attempts 1–3 established cannot be done reliably, and every attempt to approximate it was evaded within
one review round. So it is **documented rather than claimed closed**, and the honest statement of what
this assertion buys is:

> `commands/fix.md` **declares** the loop semantics AC-4 expects, in fixed words that cannot be edited
> silently. It does **not** establish that the document is free of contradictions.

That is worth having — the declaration is what every other contract-tier check in this directory reads
— but it is less than the assertion's name suggests, and the name is the reason this section exists.

### What the backstop is, and is not

It catches common stopping phrasings in the same sentence as a verdict. `prevents another round` — the
phrasing that beat attempt 3 — is **still not caught**, deliberately: adding it would restart the
enumeration this test abandoned.

It is **a backstop, not a proof**, and no reading of a green suite should treat it as one.
