---
slug: mattpocock-skills
repo: mattpocock/skills
audited: 2026-05-13
commit_sha: HEAD-at-2026-05-11
score: 98
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
  - R14
  - R33
  - R35
---

# Exemplar: mattpocock/skills

**Score**: 98/100  |  **Date**: 2026-05-13  |  **Commit**: `HEAD-at-2026-05-11`

A 30-skill Claude Code plugin collection covering engineering, productivity, and miscellaneous workflows — notable for tight trigger phrases, runnable step-by-step examples, and consistent use of bundled reference files in place of inlined prose.

## Per-rule evidence

### R04 — Description as trigger

Every skill in this repo packs 3+ specific action phrases that mirror how a developer actually invokes it. The descriptions read like a list of real user messages, not a summary of what the skill does.

> Real quote from `skills/engineering/diagnose/SKILL.md:2-5`:
>
> ```
> description: Disciplined diagnosis loop for hard bugs and performance regressions. Reproduce → minimise → hypothesise → instrument → fix → regression-test. Use when user says "diagnose this" / "debug this", reports a bug, says something is broken/throwing/failing, or describes a performance regression.
> ```

Seven distinct trigger surfaces in one description: the slash command (`diagnose this`), the verb (`debug this`), the symptom framing (`broken/throwing/failing`), and a separate performance track. Contrast with a weak description like "Helpful debugging skill" — this one routes correctly across all four common entry points.

---

### R05 — Body length

All 30 skills stay under 120 lines. The longest, `diagnose`, is 118 lines and earns every one of them across six distinct phases. The shortest, `grill-me`, fits its entire protocol in 11 lines.

> Real quote from `skills/productivity/grill-me/SKILL.md` (full file body):
>
> ```
> Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.
>
> Ask the questions one at a time.
>
> If a question can be answered by exploring the codebase, explore the codebase instead.
> ```

The skill does one thing and requires exactly the tokens that describe it. No theory, no background, no preamble.

---

### R06 — Code examples must be runnable

Skills that involve code show exact commands, exact file contents, and exact shell invocations — not pseudocode.

> Real quote from `skills/misc/setup-pre-commit/SKILL.md:50-55`:
>
> ```json
> {
>   "*": "prettier --ignore-unknown --write"
> }
> ```

> And `skills/misc/scaffold-exercises/SKILL.md:93-105`:
>
> ```bash
> mkdir -p exercises/05-memory-skill-building/05.01-introduction-to-memory/explainer
> mkdir -p exercises/05-memory-skill-building/05.02-short-term-memory/{explainer,problem,solution}
> mkdir -p exercises/05-memory-skill-building/05.03-long-term-memory/explainer
> ```

`scaffold-exercises` pairs the concrete `mkdir` commands with the exact output paths the linter expects. A model reading this can copy-execute without interpretation — no fill-in-the-blanks.

---

### R07 — Scope note when related skills exist

Skills that share a domain surface explicit cross-references rather than hoping the model picks the right one.

> Real quote from `skills/engineering/tdd/SKILL.md:15-17`:
>
> ```
> See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.
> ```

> Real quote from `skills/engineering/triage/SKILL.md:17-19`:
>
> ```
> ## Reference docs
>
> - [AGENT-BRIEF.md](AGENT-BRIEF.md) — how to write durable agent briefs
> - [OUT-OF-SCOPE.md](OUT-OF-SCOPE.md) — how the `.out-of-scope/` knowledge base works
> ```

Both skills delegate the "how" to companion files rather than inlining it, and name the boundary: `tdd` says "see tests.md for examples" (not "see tests.md for everything"). This keeps each SKILL.md focused while making the companion files discoverable.

---

### R08 — Patterns over theory

The `diagnose` skill spends zero lines on "what debugging is" and goes straight to an ordered list of 10 concrete loop-construction techniques:

> Real quote from `skills/engineering/diagnose/SKILL.md:19-30`:
>
> ```
> 1. **Failing test** at whatever seam reaches the bug — unit, integration, e2e.
> 2. **Curl / HTTP script** against a running dev server.
> 3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
> 4. **Headless browser script** (Playwright / Puppeteer) — drives the UI, asserts on DOM/console/network.
> 5. **Replay a captured trace.** Save a real network request / payload / event log to disk; replay it through the code path in isolation.
> 6. **Throwaway harness.** Spin up a minimal subset of the system...
> 7. **Property / fuzz loop.** If the bug is "sometimes wrong output", run 1000 random inputs...
> 8. **Bisection harness.**...
> 9. **Differential loop.**...
> 10. **HITL bash script.** Last resort...
> ```

This is a decision tree, not a lecture. Each entry names the tool, the context to apply it in, and (where needed) why. The model can pick row N based on what's available in the environment.

`tdd` applies the same pattern to its anti-pattern section:

> Real quote from `skills/engineering/tdd/SKILL.md:32-41`:
>
> ```
> WRONG (horizontal):
>   RED:   test1, test2, test3, test4, test5
>   GREEN: impl1, impl2, impl3, impl4, impl5
>
> RIGHT (vertical):
>   RED→GREEN: test1→impl1
>   RED→GREEN: test2→impl2
>   RED→GREEN: test3→impl3
>   ...
> ```

The diagram replaces a paragraph of explanation and is unambiguous about ordering.

---

### R14 — Steps must be numbered

Every multi-step skill uses numbered headings that make the sequence unambiguous and resumable.

> Real quote from `skills/misc/setup-pre-commit/SKILL.md:17-83` (headings only):
>
> ```
> ### 1. Detect package manager
> ### 2. Install dependencies
> ### 3. Initialize Husky
> ### 4. Create `.husky/pre-commit`
> ### 5. Create `.lintstagedrc`
> ### 6. Create `.prettierrc` (if missing)
> ### 7. Verify
> ### 8. Commit
> ```

Eight steps, each with a bounded scope. Step 4 includes an explicit "Adapt" note specifying exactly when to deviate — the only conditional in the whole skill.

---

### R33 / R35 — CLAUDE.md with architecture overview

The repo's CLAUDE.md uses its entire token budget on structure that Claude needs (directory taxonomy, cross-list requirements, link requirements) and nothing else.

> Real quote from `CLAUDE.md` (full content):
>
> ```
> Skills are organized into bucket folders under `skills/`:
>
> - `engineering/` — daily code work
> - `productivity/` — daily non-code workflow tools
> - `misc/` — kept around but rarely used
> - `personal/` — tied to my own setup, not promoted
> - `in-progress/` — drafts not yet ready to ship
> - `deprecated/` — no longer used
>
> Every skill in `engineering/`, `productivity/`, or `misc/` must have a reference in the top-level `README.md` and an entry in `.claude-plugin/plugin.json`. Skills in `personal/`, `in-progress/`, and `deprecated/` must not appear in either.
>
> Each skill entry in the top-level `README.md` must link the skill name to its `SKILL.md`.
>
> Each bucket folder has a `README.md` that lists every skill in the bucket with a one-line description, with the skill name linked to its `SKILL.md`.
> ```

Six directory entries, two invariants, two structural constraints. No installation instructions, no marketing copy, no team norms that belong in a human README. Every sentence changes what Claude does when adding or moving a skill.

---

## Worth adopting

**Pattern: Companion-file delegation with named boundary.** Skills that cover complex sub-topics offload the detail into a bundled file (`tests.md`, `mocking.md`, `AGENT-BRIEF.md`) and name the boundary in a "Reference docs" section rather than inlining the content or silently relying on the file existing. Evidence: `triage/SKILL.md:17-19`, `tdd/SKILL.md:15-17`, `diagnose/SKILL.md:29`. Why it would be a useful rule: inlining companion material causes the parent skill to exceed the 500-line budget; silent bundling (no cross-reference in the skill body) means the model won't read the companion file unless it happens to notice the directory listing. The named boundary solves both.

**Pattern: Conditional step with explicit trigger.** Steps that should only execute in some environments include a bold `**Adapt**:` or `(if missing)` clause specifying exactly when to deviate, rather than writing a separate conditional branch. Evidence: `setup-pre-commit/SKILL.md:47`, `setup-pre-commit/SKILL.md:57`. Why it would be a useful rule: branching prose ("if X do Y, else do Z") doubles the reading cost; a single-line `**Adapt**` annotation on the step that varies is cheaper and harder to miss.
