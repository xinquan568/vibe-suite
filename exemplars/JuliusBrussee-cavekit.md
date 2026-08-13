---
slug: JuliusBrussee-cavekit
repo: JuliusBrussee/cavekit
audited: 2026-05-13
commit_sha: 028643f913996cfe1c59f261627d167d4ab5477f
score: 97
exemplifies:
  - R04
  - R06
  - R07
  - R08
  - R17
---

# Exemplar: JuliusBrussee/cavekit

**Score**: 97/100  |  **Date**: 2026-05-13  |  **Commit**: `028643f913996cfe1c59f261627d167d4ab5477f`

Spec-driven development plugin (5 skills + 3 commands); all five skills score 96–100, every description is a trigger list, and the caveman skill demonstrates bad/good example discipline that most skills at twice its length never achieve.

## Per-rule evidence

### R04 — Description as trigger

Every skill in this plugin treats its frontmatter description as a retrieval signal, not a product description. The spec skill lists 7 distinct user phrasings including literal example strings, closing the loop between what Claude reads and what users type.

> Real quote from `skills/spec/SKILL.md:3-11`:
>
> ```
> description: |
>   Create, amend, or backprop bugs into SPEC.md at repo root. Sole mutator
>   of the project spec. Triggers when the user asks to write a spec, start
>   a new spec, distill a spec from existing code, add invariants, amend
>   sections (§G, §C, §I, §V, §T, §B), or record a bug via backprop.
>   Common phrasings: "write the spec for...", "new spec", "bug: ...",
>   "amend §V.3", "distill spec from code", "spec this idea". Reads and
>   follows FORMAT.md for the caveman encoding rules and pipe-table shape
>   of §T and §B.
> ```

The "Common phrasings" tail is the distinguishing move: it mirrors exact user queries rather than paraphrasing capabilities. All five skills follow this pattern; backprop and caveman each list 3 trigger scenarios, build lists 4 including literal invocation examples (`build §T.3`, `build --next`).

### R06 — Code examples must be runnable

The caveman skill's EXAMPLES section shows three bad/good pairs in the plugin's own caveman format — no pseudocode, no ellipsis, no "something like this". Each good example is a complete record in real syntax that could be pasted into a SPEC.md unchanged.

> Real quote from `skills/caveman/SKILL.md:91-108`:
>
> ```
> **Bad**:
> > The system should ensure that every incoming request is properly authenticated before being forwarded to its corresponding handler function.
>
> **Good**:
> > V1: ∀ req → auth check before handler
>
> **Bad**:
> > We discovered that the token expiration check in the middleware was using a strict less-than comparison operator, which meant tokens were being rejected at the exact moment of their expiry.
>
> **Good**:
> > B1: token `<` not `≤` → reject @ expiry boundary.
>
> **Bad**:
> > The POST endpoint at /x accepts a JSON body and returns a 200 response with an object containing the created id.
>
> **Good**:
> > api: POST /x → 200 {id}
> ```

What makes this strong: each good example is exactly as long as it needs to be and contains a real symbol (`∀`, `≤`, `→`) used correctly, not a placeholder. A reader can copy the good examples and use them immediately.

### R07 — Scope note when related skills exist

The build skill declares its boundary in the frontmatter description, naming the skill it defers to before the user even loads the body. The check skill's description anchors its read-only constraint and names both sibling skills in one sentence.

> Real quote from `skills/build/SKILL.md:8-10`:
>
> ```
> Expects SPEC.md to exist; if not, defers to the spec skill.
> ```

> Real quote from `skills/check/SKILL.md:3-9`:
>
> ```
> description: |
>   Read-only drift detector. Diffs SPEC.md against current code and reports
>   violations grouped by severity. Writes nothing — suggests remedies via
>   the spec or build skills but never invokes them.
> ```

Both scope notes appear in the description field, which means Claude reads them at skill-selection time — before loading the body. Burying scope notes in a NON-GOALS section at the end of the body is structurally weaker; these surface first.

### R08 — Patterns over theory

The backprop skill teaches the concept by giving a 6-step numbered procedure, then a bad/good invariant pair, then an explicit list of cases where the invariant step should be skipped. There is no introductory paragraph on what spec-driven development is.

> Real quote from `skills/backprop/SKILL.md:62-78`:
>
> ```
> ## WHAT MAKES A GOOD INVARIANT
>
> - Testable in code (grep-able or assert-able).
> - Scoped to a behavior, not a file.
> - Stated positively when possible (`! hold` over `⊥ forbid`).
> - References §I surface where it applies.
>
> **Bad**: V8: code should be correct.
> **Good**: V8: ∀ pg_query ! params interpolated via driver, ⊥ string concat.
> ```

The bad example is a real failure mode — "code should be correct" is exactly what an LLM writes when it doesn't understand what a good invariant is. The good example is a concrete, grep-able rule with symbols used correctly. Together they teach by contrast, not by definition.

### R17 — Specify error paths

Both the build and check commands open with an explicit early-exit for the missing-file case, with a complete user message and a hard stop. Neither says "handle errors appropriately."

> Real quote from `commands/build.md:10-12`:
>
> ```
> ## LOAD
>
> 1. Read `SPEC.md`. If missing → tell user to run `/spec` first. Stop.
> ```

> Real quote from `commands/check.md:10-12`:
>
> ```
> ## LOAD
>
> 1. Read `SPEC.md`. If missing → "no spec, nothing to check." Stop.
> ```

The check command even provides the literal output string in quotes, leaving Claude no ambiguity about what to say. The spec command handles the no-args case with equal specificity: "no args → ask user which mode" — one of five explicitly enumerated dispatch branches.

## Worth adopting

Pattern: **NON-GOALS section in every skill and command.** Evidence: `skills/build/SKILL.md:72-76`, `skills/check/SKILL.md:86-90`, `skills/spec/SKILL.md:78-83`, `skills/backprop/SKILL.md:87-89`, `commands/build.md:65-69`, `commands/check.md:79-84`. Every artifact in this plugin ends with a NON-GOALS section that explicitly names what the artifact refuses to do ("No sub-agents. No parallel workers. Main thread only." / "Zero writes. No SPEC.md edits. No code edits."). Why it would be a useful rule: LLMs over-generalize skill scope when boundaries are implicit — a check skill with no NON-GOALS will sometimes attempt fixes. Explicit refusals in a dedicated terminal section let Claude answer "can I do X here?" without re-reading the body. Candidate rule: "**Add a NON-GOALS section as the final body section.** List 2–4 explicit refusals covering the most common over-generalizations. Without them, Claude expands scope at runtime when the body is ambiguous."
