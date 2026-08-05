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
| `fix` | `--max-rounds` | a `## Round bounds` block | none named |

`fix`'s `FIXED` / `NOT FIXED` / `PARTIAL` / `REGRESSED` are **per-issue verdicts**, and `NOT FIXED` and
`PARTIAL` normally *continue* the loop. Reading them as terminal statuses would invert their meaning.

## `fix` satisfies AC-4's re-ask clause since #123

It predated the contract, and its unusable-verification path once fell back and stopped rather than
re-asking. **Issue #123** closed that gap: `fix` is a registered consumer of the reviewer contract,
cites its verdict-parsing section, re-asks an unusable verdict exactly once before degrading, and
declares its continue/stop verdict routing in its Round bounds block. The harness test that once
characterised the gap was inverted the day #123 landed — exactly as its docstring ordered when it
recorded the gap.

## `loops.json` holds nothing a document could disagree with

Only where each document is, and which declaration shape reads it — one shape today, since #125
brought `fix`'s declaration into the same `## Round bounds` form the other two use. The selector
stays so a second shape would have to declare itself there, and bring its own parser, rather than
be guessed from the text. Caps, contract citations and terminal statuses are read from the
documents.

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

## The round-loop declaration is parsed as data, and how it got there

`commands/fix.md` now carries a `## Round bounds` block that `parse_round_bounds` reads under a
strict grammar: a closed field vocabulary, one field per bullet, duplicates and omissions rejected,
verdict sets as exact backticked literals with no trailing prose, fence-aware and
uniqueness-asserting section extraction. The tests read values, not sentences.

Before #125 landed that block, the section was **frozen byte-for-byte** against a golden fixture —
drift detection, not an adversarial guarantee. The golden was deleted when the block arrived rather
than kept alongside: two mechanisms for one property is how the weaker one gets read as the
stronger. The detour that produced the golden, and then the block, is worth keeping:

### Eight attempts to verify what the document *means*

Each was refuted by the reviewer, and each refutation was verified by running the mutation:

| # | Check | Refuted by |
|---|---|---|
| 1 | no stopping phrase *after* the verdict | putting the phrase in front |
| 2 | no stopping verb stem in the sentence | "causes the loop to exit" |
| 3 | a continuing word *near* the verdict | "…`PARTIAL` prevents another round" |
| 4 | exact clause present (substring) | prefixing "It is false that" |
| 5 | whole-sentence equality | "viz." splits the sentence |
| 6 | section golden via `norm()` | `norm()` lowercases, hiding `` `NOT FIXED` `` → `` `not fixed` `` |
| 7 | whitespace-collapsed golden | a blank line + 4-space indent makes it a code block |
| 8 | exact golden, naive extraction | a fenced-code decoy heading beats a first-match extractor |

Attempts 1–5 were bad checks — each matched **lexical proximity rather than the relation** between the
verdict and the verb, so each fell to a sentence with the right words in the wrong relation.

Attempts 6 and 7 were a *sound* check whose "only allowance" quietly re-admitted the class it was meant
to close. Both times the flaw sat in the part described as harmless and not tested.

Attempt 8 moved the surface from comparison to **extraction**.

### Why there is no attempt 9

Establishing what a prose document *means*, against a reader actively looking for a way through, is an
arms race over extraction and comparison surfaces with no natural terminus. Three of the eight
refutations were not even about the property — they were about the machinery for reading the file.

AC-4's terminal-status clause for `fix` is **Contract**-tier by this directory's own table, and Contract
tier never promised more than "the specification says so". Eight rounds were spent trying to make a
Contract-tier check adversarially airtight, which is a different and much harder goal — and noticing
that is the same discipline as the Executable/Contract/Operator split at the top of this file.

So the golden asserted what a golden fixture asserts anywhere in this repository: **the text has
not changed** — catching loop semantics altered as a side effect of an edit, never a document built
to defeat it. The structured declaration ended that arms race by removing its subject: a parsed
field has no neighbouring prose to contradict it, so there is nothing left to extract or compare
adversarially. That is what attempt 9 would have needed to be, and it required changing the shipped
document, which is why it was #125's to do and not this harness's.

### What is genuinely closed, and what is not

| Claim | Status |
|---|---|
| the `## Round bounds` declaration cannot drift without failing | **holds** — a strict-grammar parse (closed field set, exact verdict sets, fence-aware unique extraction); a changed value fails the reading tests, a changed shape fails the parse |
| each verdict appears at least once as an uppercase code literal | **holds**, and that is the entire claim — it catches the vocabulary being renamed *wholesale* |
| a verdict renamed **outside** the structured block is caught | **not claimed.** Each verdict occurs several times, so lowercasing one occurrence elsewhere satisfies the check. |
| the document as a whole is free of contradictions | **not claimed.** Prose outside the block is not read — the declared values echo in exactly one prose surface, the CLI argument-hint, and a test asserts that echo agrees with the block. |
| the document cannot be constructed to defeat the check | **holds — for the declaration.** The harness reads values, not sentences: the grammar rejects decoy headings, duplicates, unknown or compounded fields, and prose riding on verdict lines. No claim is made about prose elsewhere in the document. |

The third row previously read as **holds**. It was wrong, and a reviewer found it by lowercasing an
occurrence outside the section. That is the **third** time this link overstated an assertion, always
in the same direction — which is why the table still lists what is *not* claimed, and why the last
row's **holds** is scoped to the declaration and nothing wider.

**Issue #125 landed** that structured declaration, and the golden fixture was deleted with it rather
than kept alongside — two mechanisms for one property is how the weaker one gets read as the
stronger. **#123 then landed too**: `fix` is a registered consumer of the reviewer contract (the
re-ask clause and registry membership above), its block carries the contract's required floor
reason, and this harness's characterisation test was inverted — the sequence both issues' texts
planned, completed in order.
