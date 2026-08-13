---
slug: The-Vibe-Company-companion
repo: The-Vibe-Company/companion
audited: 2026-05-13
commit_sha: 52883144858f62d6f9b418c00432279f28d119d4
score: 91
exemplifies:
  - R04
  - R07
  - R08
  - R38
  - R41
---

# Exemplar: The-Vibe-Company/companion

**Score**: 91/100  |  **Date**: 2026-05-13  |  **Commit**: `52883144858f62d6f9b418c00432279f28d119d4`

A 19-skill frontend-design toolkit for Claude Code that earns its score through concrete trigger descriptions, consistent cross-skill routing, measurable criteria in checklists, mandatory output templates, and a CLAUDE.md that instructs rather than describes.

## Per-rule evidence

### R04 — Description as trigger

The best-scoring skills pack multiple specific action phrases into their `description` field — the exact phrases a user would type to invoke them. None reads as a summary of capabilities; each reads as a routing table.

> `.agents/skills/audit/SKILL.md:3-4`:
>
> ```
> description: Perform comprehensive audit of interface quality across accessibility, performance, theming, and responsive design. Generates detailed report of issues with severity ratings and recommendations.
> ```

> `.agents/skills/polish/SKILL.md:3-4`:
>
> ```
> description: Final quality pass before shipping. Fixes alignment, spacing, consistency, and detail issues that separate good from great.
> ```

> `.agents/skills/critique/SKILL.md:3-4`:
>
> ```
> description: Evaluate design effectiveness from a UX perspective. Assesses visual hierarchy, information architecture, emotional resonance, and overall design quality with actionable feedback.
> ```

What separates these from mediocre descriptions: each embeds 3–5 distinct action phrases ("final quality pass before shipping", "fixes alignment, spacing, consistency", "assesses visual hierarchy, information architecture, emotional resonance") that match the actual queries a developer would type. A skill named "audit" with description "Audits things" would fire on nothing; "comprehensive audit … accessibility, performance, theming, and responsive design" fires on exactly the queries it should.

---

### R07 — Scope note when related skills exist

Seven of the 18 skills open with a single mandatory routing line that tells the model which skill to load first. The pattern is identical across audit, critique, polish, animate, bolder, colorize, and quieter — meaning the shared knowledge base (frontend-design) is invoked consistently rather than re-stated in each skill.

> `.agents/skills/audit/SKILL.md:13`:
>
> ```
> **First**: Use the frontend-design skill for design principles and anti-patterns.
> ```

> `.agents/skills/critique/SKILL.md:13`:
>
> ```
> **First**: Use the frontend-design skill for design principles and anti-patterns.
> ```

> `.agents/skills/polish/SKILL.md:11`:
>
> ```
> **First**: Use the frontend-design skill for design principles and anti-patterns.
> ```

The output format for the audit skill reinforces the same pattern outward — when recommending fixes, it routes to other existing skills by name rather than re-explaining their logic:

> `.agents/skills/audit/SKILL.md:74`:
>
> ```
> **Suggested command**: Which command to use (prefer: /animate, /quieter, /optimize, /adapt, /clarify, /distill, /delight, /onboard, /normalize, /audit, /harden, /polish, /extract, /bolder, /critique, /colorize — or other installed skills you're sure exist)
> ```

This is scope-noting in both directions: skills declare what they delegate *to*, and they instruct the model to route *back* to the skill suite rather than inventing fixes inline. The guard clause ("you're sure exist") prevents hallucinated command names.

---

### R08 — Patterns over theory

The audit and polish skills replace abstract design principles with enumerated, measurable criteria. Every check is a yes/no test the model can perform against actual code, not a guideline that requires judgment.

> `.agents/skills/audit/SKILL.md:20-25`:
>
> ```
> - **Contrast issues**: Text contrast ratios < 4.5:1 (or 7:1 for AAA)
> - **Missing ARIA**: Interactive elements without proper roles, labels, or states
> - **Keyboard navigation**: Missing focus indicators, illogical tab order, keyboard traps
> - **Semantic HTML**: Improper heading hierarchy, missing landmarks, divs instead of buttons
> - **Alt text**: Missing or poor image descriptions
> - **Form issues**: Inputs without labels, poor error messaging, missing required indicators
> ```

> `.agents/skills/audit/SKILL.md:33-36`:
>
> ```
> - **Touch targets**: Interactive elements < 44x44px
> - **Horizontal scroll**: Content overflow on narrow viewports
> - **Text scaling**: Layouts that break when text size increases
> - **Missing breakpoints**: No mobile/tablet variants
> ```

> `.agents/skills/polish/SKILL.md:56-58`:
>
> ```
> - **Line length**: 45-75 characters for body text
> - **Line height**: Appropriate for font size and context
> - **Widows & orphans**: No single words on last line
> ```

> `.agents/skills/polish/SKILL.md:91`:
>
> ```
> - **Consistent easing**: Use ease-out-quart/quint/expo for natural deceleration. Never bounce or elastic—they feel dated.
> ```

The contrast ratio `< 4.5:1`, touch target `< 44x44px`, and line-length `45-75 characters` are verifiable by inspection or browser tooling. The easing spec names concrete CSS functions instead of "appropriate easing." This is the difference between a checklist the model can execute and an essay it can only approximate.

---

### R38 — More instructive than descriptive

The CLAUDE.md spends the majority of its token budget on behavioral requirements for Claude, not product description. The testing section is the strongest example: it specifies what *must* happen, what is *never* allowed, and what constitutes acceptable proof — not a description of what tests exist.

> `CLAUDE.md:45-49`:
>
> ```
> - All new backend (`web/server/`) and frontend (`web/src/`) code **must** include tests when possible.
> - **Every new or modified frontend component** (`web/src/components/`) **must** have an accompanying `.test.tsx` file with at minimum: a render test, an axe accessibility scan (`toHaveNoViolations()`), and tests for any interactive behavior (clicks, keyboard shortcuts, state changes).
> - Tests use Vitest. Server tests live alongside source files (e.g. `routes.test.ts` next to `routes.ts`).
> - A husky pre-commit hook runs typecheck and tests automatically before each commit.
> - **Never remove or delete existing tests.** If a test is failing, fix the code or the test. If you believe a test should be removed, you must first explain to the user why and get explicit approval before removing it.
> ```

> `CLAUDE.md:52-54`:
>
> ```
> All UI components used in the message/chat flow **must** be represented in the Playground page (`web/src/components/Playground.tsx`, accessible at `#/playground`). When adding or modifying a message-related component (e.g. `MessageBubble`, `ToolBlock`, `PermissionBanner`, `Composer`, streaming indicators, tool groups, subagent groups), update the Playground to include a mock of the new or changed state.
> ```

Each instruction specifies: the scope (`web/src/components/`), the minimum threshold (render test + axe scan + interaction tests), the exception path (explain to user + get explicit approval), and the tool to use (Vitest, axe). No vague "ensure adequate test coverage" anywhere in this section.

---

### R41 — Specify exact output format

The audit skill defines a per-finding template with named fields and enumerated values for every field that could vary. The model cannot produce inconsistent output when the schema is this explicit.

> `.agents/skills/audit/SKILL.md:66-74`:
>
> ```
> For each issue, document:
> - **Location**: Where the issue occurs (component, file, line)
> - **Severity**: Critical / High / Medium / Low
> - **Category**: Accessibility / Performance / Theming / Responsive
> - **Description**: What the issue is
> - **Impact**: How it affects users
> - **WCAG/Standard**: Which standard it violates (if applicable)
> - **Recommendation**: How to fix it
> - **Suggested command**: Which command to use (prefer: /animate, /quieter, /optimize, /adapt, /clarify, /distill, /delight, /onboard, /normalize, /audit, /harden, /polish, /extract, /bolder, /critique, /colorize — or other installed skills you're sure exist)
> ```

The critique skill uses the same pattern at the section level — each priority issue gets a four-field entry (`What`, `Why it matters`, `Fix`, `Command`):

> `.agents/skills/critique/SKILL.md:97-101`:
>
> ```
> For each issue:
> - **What**: Name the problem clearly
> - **Why it matters**: How this hurts users or undermines goals
> - **Fix**: What to do about it (be concrete)
> - **Command**: Which command to use (prefer: /animate, /quieter, /optimize, ...)
> ```

The severity field uses a closed enum (`Critical / High / Medium / Low`), not free text. The `Suggested command` field is constrained to a named list with a guard against invention. These choices make the output parseable and auditable without post-processing.

---

## Worth adopting

**Pattern: Modular reference sub-directory for large skill bodies.** Evidence: `.agents/skills/frontend-design/` contains a root `SKILL.md` plus seven files under `reference/` (`typography.md`, `color-and-contrast.md`, `spatial-design.md`, `motion-design.md`, `interaction-design.md`, `responsive-design.md`, `ux-writing.md`). The root file stays under 500 lines; deep reference material lives in sub-documents that any skill can cross-reference. Why it would be a useful rule: R05 says "under 500 lines — split into scoped sub-skills with cross-references" but doesn't specify how to split. A `reference/` sub-directory pattern lets skills stay cohesive (one name, one invocation) while externalizing reference tables that would otherwise bloat the root file. Candidate rule: "Use a `reference/` sub-directory for lookup tables and reference material that exceeds 100 lines. The root SKILL.md stays navigable; sub-documents are loaded on demand by other skills via path reference."
