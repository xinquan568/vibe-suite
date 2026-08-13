---
slug: forrestchang-andrej-karpathy-skills
repo: forrestchang/andrej-karpathy-skills
audited: 2026-05-13
commit_sha: 2c606141936f1eeef17fa3043a72095b4765b9c2
score: 99
exemplifies:
  - R02
  - R04
  - R05
  - R08
  - R38
  - R49
---

# Exemplar: forrestchang/andrej-karpathy-skills

**Score**: 99/100  |  **Date**: 2026-05-13  |  **Commit**: `2c606141936f1eeef17fa3043a72095b4765b9c2`

A three-artifact plugin (SKILL.md, CLAUDE.md, plugin.json) that translates Karpathy's LLM pitfall observations into four concrete behavioral guidelines; notable for packing high instruction density into 68 lines with zero padding.

## Per-rule evidence

### R02 — Every line earns its tokens

The SKILL.md has no preamble, no "About this document" section, and no rationale narrative. The only non-instructional content is a one-sentence attribution and a one-sentence tradeoff caveat — both change Claude's behavior (establish source authority; bound when to relax the rules).

> `skills/karpathy-guidelines/SKILL.md:9-11`:
>
> ```
> Behavioral guidelines to reduce common LLM coding mistakes, derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.
>
> **Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.
> ```

The tradeoff line is the only conditional in the file. It prevents over-application on trivial tasks — a single token-efficient line that bounds the entire skill's scope rather than leaving Claude to infer when the guidelines apply.

### R04 — Description as trigger

The SKILL.md description field packs 7 distinct action-trigger phrases into 218 characters: writing, reviewing, refactoring code, overcomplication avoidance, surgical changes, surfacing assumptions, defining success criteria.

> `skills/karpathy-guidelines/SKILL.md:3`:
>
> ```
> description: Behavioral guidelines to reduce common LLM coding mistakes. Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria.
> ```

Compare to a weaker alternative: "Helpful coding guidelines based on Karpathy's tips." That's a summary of the file's origin. This version is a trigger — each phrase maps to a concrete user intent ("I'm writing code and it's getting complicated", "I need to refactor without breaking things") that Claude can match at load time.

### R05 — Under 500 lines

The SKILL.md is 68 lines total: 4 behavioral sections, 3 bullet groups, 1 code block, and 2 self-check sentences. All four principles with concrete examples fit in one screenful. Section 1 ("Think Before Coding") covers a complete principle in 9 lines:

> `skills/karpathy-guidelines/SKILL.md:13-21`:
>
> ```
> ## 1. Think Before Coding
>
> **Don't assume. Don't hide confusion. Surface tradeoffs.**
>
> Before implementing:
> - State your assumptions explicitly. If uncertain, ask.
> - If multiple interpretations exist, present them - don't pick silently.
> - If a simpler approach exists, say so. Push back when warranted.
> - If something is unclear, stop. Name what's confusing. Ask.
> ```

9 lines, 4 bullet directives, 0 filler — the same density holds across all four sections. The constraint is structural: every bullet specifies an observable behavior rather than an abstract quality.

### R08 — Patterns over theory

The Goal-Driven Execution section teaches through concrete task transformation examples rather than abstract descriptions. Instead of "be goal-oriented", it shows before/after pairs for three common task types, then gives a fill-in template.

> `skills/karpathy-guidelines/SKILL.md:55-65`:
>
> ```
> Transform tasks into verifiable goals:
> - "Add validation" → "Write tests for invalid inputs, then make them pass"
> - "Fix the bug" → "Write a test that reproduces it, then make it pass"
> - "Refactor X" → "Ensure tests pass before and after"
>
> For multi-step tasks, state a brief plan:
> ```
> 1. [Step] → verify: [check]
> 2. [Step] → verify: [check]
> 3. [Step] → verify: [check]
> ```
> ```

The `→ verify: [check]` template is immediately applicable — Claude fills it in without inferring structure. The three task-type transformations cover the most common imperative forms a user will write.

### R38 — More instructive than descriptive

CLAUDE.md is 65 lines, of which 1 line is the heading, 1 line is a scope description, and 63 lines are direct behavioral instructions or observable criteria. No history section, no rationale narrative, no credits.

> `CLAUDE.md:1-5`:
>
> ```
> # CLAUDE.md
>
> Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.
>
> **Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.
> ```

After these 5 lines (2 of which are blank), the file stays in instruction mode for the remaining 60 lines. The >60% instruction threshold from R38 is met at ~97%: the only non-instruction content is the 3-line closing sentinel (see "Worth adopting" below).

### R49 — CLAUDE.md for Claude, README for humans

README.md (172 lines) contains installation commands, feature tables, background quotes from Karpathy, Cursor setup instructions, and customization examples. None of this appears in CLAUDE.md. Conversely, CLAUDE.md's four behavioral sections have no installation instructions, feature descriptions, or human-facing context.

> `README.md:99-113` (install content, absent from CLAUDE.md):
>
> ```
> ## Install
>
> **Option A: Claude Code Plugin (recommended)**
>
> From within Claude Code, first add the marketplace:
> /plugin marketplace add forrestchang/andrej-karpathy-skills
>
> Then install the plugin:
> /plugin install andrej-karpathy-skills@karpathy-skills
> ```

The README explains installation, background, and why the tool exists. CLAUDE.md delivers what Claude needs to act. The split is clean: zero cross-contamination in either direction.

## Worth adopting

**Pattern: In-section verification test.** Each behavioral section ends with a grounded self-check criterion phrased as "The test:".

Evidence: `skills/karpathy-guidelines/SKILL.md:49` ("The test: Every changed line should trace directly to the user's request.") and `SKILL.md:33` ("Ask yourself: 'Would a senior engineer say this is overcomplicated?' If yes, simplify.").

This gives Claude a concrete compliance check within each instruction block instead of relying on abstract self-evaluation. Why it would be a useful rule: embedding a verification sentence at the end of each behavioral guideline section reduces post-hoc rationalization — Claude can ground-check whether it followed the instruction before proceeding.

**Pattern: Observable success-criteria sentinel.** CLAUDE.md closes with a "working if" block stating behavioral signals that confirm the instructions are being followed.

Evidence: `CLAUDE.md:65` ("**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.").

This is not a rule — it's a meta-instruction that lets Claude self-monitor compliance over a session. Why it would be a useful rule: closing CLAUDE.md with 2-4 observable behavioral signals (what changes in output when instructions are followed) gives Claude a reference for evaluating its own behavior across multiple turns, not just at the moment of reading the file.
