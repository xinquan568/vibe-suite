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

## The round-loop declaration is frozen, and that is all it is

`commands/fix.md`'s `## Step 5 — the round loop` section is compared byte-for-byte against
`tests/fixtures/loop-bounds/fix-step5-section.md`. Editing the section fails the suite until the golden
is updated in the same commit.

**It is drift detection, not an adversarial guarantee.** That sentence is the deliverable of a long
detour and is worth more than the check itself.

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

So the check asserts what a golden fixture asserts anywhere in this repository: **the text has not
changed.** It catches loop semantics altered as a side effect of an edit, which is the realistic
failure. It does not catch a document built to defeat it.

### What is genuinely closed, and what is not

| Claim | Status |
|---|---|
| the `## Step 5` section cannot change without failing | **holds** — byte equality, fence-aware extraction, heading uniqueness asserted |
| the verdict literals stay uppercase code literals | **holds** — checked across the whole document, so a rename outside the section is caught |
| the document as a whole is free of contradictions | **not claimed.** Content outside the section is not read. |
| the document cannot be constructed to defeat the check | **not claimed**, and the eight attempts above are why |

Closing the last row needs a **structured declaration** `fix.md` does not have — a parsed field has no
neighbouring prose to contradict it, so the arms race ends: the test reads values, not sentences.

**Issue #125 is filed** for it, and it says the golden fixture is *deleted* when that lands rather than
kept alongside — two mechanisms for one property is how the weaker one gets read as the stronger. It
changes a shipped command's document, which is why it is not done inside a test-harness issue; #123 is
the adjacent change bringing `fix` under the reviewer contract, and the two touch the same file.
