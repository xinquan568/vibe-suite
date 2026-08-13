---
slug: addyosmani-web-quality-skills
repo: addyosmani/web-quality-skills
audited: 2026-05-13
commit_sha: fed9617111260e19f4f54b72a2874a3f3de8ff94
score: 97
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
  - R33
  - R34
  - R35
  - R38
---

# Exemplar: addyosmani/web-quality-skills

**Score**: 97/100  |  **Date**: 2026-05-13  |  **Commit**: `fed9617111260e19f4f54b72a2874a3f3de8ff94`

Six-skill collection covering web performance, Core Web Vitals, accessibility, SEO, and best practices — two skills scored 100/100 and four others scored 92–98, dragged only by vague quantifiers in prose descriptions.

## Per-rule evidence

### R04 — Description as trigger

Every SKILL.md in this repo packs multiple quoted user phrases into its description field, making trigger matching explicit rather than leaving it to semantic guesswork. The descriptions read like a list of real user messages, not product copy.

> Real quote from `skills/core-web-vitals/SKILL.md:3-4`:
>
> ```
> description: Optimize Core Web Vitals (LCP, INP, CLS) for better page experience and search ranking. Use when asked to "improve Core Web Vitals", "fix LCP", "reduce CLS", "optimize INP", "page experience optimization", or "fix layout shifts".
> ```

> Real quote from `skills/performance/SKILL.md:3-4`:
>
> ```
> description: Optimize web performance for faster loading and better user experience. Use when asked to "speed up my site", "optimize performance", "reduce load time", "fix slow loading", "improve page speed", or "performance audit".
> ```

Six quoted trigger phrases per skill is above average. Each phrase is a verbatim user query, not a paraphrase — "fix LCP" and "speed up my site" are exactly what a developer types, not what a skill author imagines they might mean.

### R05 — Body length

Both 100-scoring skills stay well under the 500-line ceiling: `skills/core-web-vitals/SKILL.md` is 442 lines, `skills/performance/SKILL.md` is 362 lines. Depth is reached through code examples and tables, not repeated prose. The accessibility skill (98/100) handles a broader topic at a similar length by offloading reference material to `skills/accessibility/references/`.

> Real quote from `skills/accessibility/SKILL.md:1-7` (frontmatter showing version 1.1 — the only skill at a minor version bump, indicating prior trimming):
>
> ```
> ---
> name: accessibility
> description: Audit and improve web accessibility following WCAG 2.2 guidelines. Use when asked to "improve accessibility", "a11y audit", "WCAG compliance", "screen reader support", "keyboard navigation", or "make accessible".
> license: MIT
> metadata:
>   author: web-quality-skills
>   version: "1.1"
> ---
> ```

The `references/` subdirectory pattern (WCAG.md, A11Y-PATTERNS.md) is how this repo extends depth without inflating body length — overflow goes into referenced files, not the main skill body.

### R06 — Code examples must be runnable

Every issue documented in `core-web-vitals` and `performance` has a ❌/✅ pair in real syntax. The examples are not pseudocode: they show actual HTML attributes, real JavaScript APIs, and framework-specific patterns for Next.js, React, and Vue.

> Real quote from `skills/core-web-vitals/SKILL.md:46-59`:
>
> ```html
> <!-- ❌ No hints, discovered late -->
> <img src="/hero.jpg" alt="Hero">
>
> <!-- ✅ Preloaded with high priority -->
> <link rel="preload" href="/hero.webp" as="image" fetchpriority="high">
> <img src="/hero.webp" alt="Hero" fetchpriority="high">
> ```

> Real quote from `skills/performance/SKILL.md:99-107`:
>
> ```javascript
> // ❌ Imports entire library
> import _ from 'lodash';
> _.debounce(fn, 300);
>
> // ✅ Imports only what's needed
> import debounce from 'lodash/debounce';
> debounce(fn, 300);
> ```

The ❌/✅ pattern appears consistently across all six skills. A developer can copy either block into their project — neither example requires adaptation before running.

### R07 — Scope note when related skills exist

Each skill declares its boundaries and routes the reader to the appropriate sibling. The SEO skill uses a table to show scope coverage explicitly, including a cross-reference cell for the one area it defers:

> Real quote from `skills/seo/SKILL.md:16-25`:
>
> ```
> | Factor | Influence | This Skill |
> |--------|-----------|------------|
> | Content quality & relevance | ~40% | Partial (structure) |
> | Backlinks & authority | ~25% | ✗ |
> | Technical SEO | ~15% | ✓ |
> | Page experience (Core Web Vitals) | ~10% | See [Core Web Vitals](../core-web-vitals/SKILL.md) |
> | On-page SEO | ~10% | ✓ |
> ```

> Real quote from `skills/performance/SKILL.md:360-361`:
>
> ```
> For Core Web Vitals specific optimizations, see [Core Web Vitals](../core-web-vitals/SKILL.md).
> ```

The scope table in `seo` is an unusually strong form of R07 compliance: it not only says "go there for X" but also enumerates what "there" is responsible for and what percentage of real-world SEO problems it addresses.

### R08 — Patterns over theory

The skills are organized as named issue types ("Common LCP issues", "Common INP issues", "Common CLS causes") with numbered sub-problems, each answered with a concrete fix. Theory — if present at all — appears only in service of the pattern.

> Real quote from `skills/core-web-vitals/SKILL.md:35-87` (structure, condensed):
>
> ```markdown
> ### Common LCP issues
>
> **1. Slow server response (TTFB > 800ms)**
> **2. Render-blocking resources**
> **3. Slow resource load times**
> **4. Client-side rendering delays**
>
> ### LCP optimization checklist
> - [ ] TTFB < 800ms (use CDN, edge caching)
> - [ ] LCP image preloaded with fetchpriority="high"
> ...
> ```

The pattern `numbered issue → ❌/✅ pair → checklist` repeats across LCP, INP, and CLS sections. A developer debugging a CLS regression can jump to "CLS: Cumulative Layout Shift → Common CLS causes → item 1" without reading anything else.

### R33, R34, R35 — CLAUDE.md build/run/test commands and architecture overview

The CLAUDE.md provides the exact commands Claude needs to validate and lint the project, pinned to specific tools (not "run the tests" or "check the format"):

> Real quote from `CLAUDE.md:57-64`:
>
> ```bash
> # Validate skill format
> npx skills-ref validate skills/
>
> # Lint markdown
> npx markdownlint skills/**/*.md
> ```

Architecture is conveyed through a table that maps skill name → directory → trigger phrases — the same trigger information Claude would need to route a user query to the right skill file:

> Real quote from `CLAUDE.md:13-20`:
>
> ```
> | Skill | Location | Triggers |
> |-------|----------|----------|
> | web-quality-audit | `skills/web-quality-audit/` | "audit", "quality review", "lighthouse" |
> | performance | `skills/performance/` | "speed up", "optimize", "load time" |
> | core-web-vitals | `skills/core-web-vitals/` | "LCP", "INP", "CLS", "Core Web Vitals" |
> | accessibility | `skills/accessibility/` | "a11y", "WCAG", "accessible" |
> | seo | `skills/seo/` | "SEO", "meta tags", "search" |
> | best-practices | `skills/best-practices/` | "security", "best practices", "modern" |
> ```

### R38 — More instructive than descriptive

The CLAUDE.md devotes most of its lines to thresholds, commands, and workflow steps — not to describing what the project is. The "Key thresholds" section gives numeric targets Claude can check against directly:

> Real quote from `CLAUDE.md:23-38`:
>
> ```
> **Core Web Vitals (Good):**
> - LCP ≤ 2.5s
> - INP ≤ 200ms
> - CLS ≤ 0.1
>
> **Performance Budgets:**
> - Total: < 1.5 MB
> - JS: < 300 KB
> - CSS: < 100 KB
>
> **Lighthouse Targets:**
> - Performance: ≥ 90
> - Accessibility: 100
> - Best Practices: ≥ 95
> - SEO: ≥ 95
> ```

Exact numbers throughout — no "fast enough" or "reasonable budget." A Claude session diagnosing a performance problem can read these thresholds and immediately know whether a measured value is in or out of range without asking the developer.

## Worth adopting

**Pattern: Scope-coverage table in skill descriptions.** Evidence: `skills/seo/SKILL.md:16-25`. The table shows which SEO ranking factors the skill covers (✓), explicitly doesn't cover (✗), and defers to a sibling skill (linked). Why it would be a useful rule: A skill that enumerates its non-scope teaches Claude not to invoke it for out-of-scope tasks — more precise than a prose disclaimer and harder to misread as "this skill handles everything in the list."

**Pattern: Numbered-issue organization within sections.** Evidence: `skills/core-web-vitals/SKILL.md:35-87`. Issues within a category are numbered and named ("1. Slow server response", "2. Render-blocking resources"), making it possible to reference a specific fix by number in a conversation rather than by description. Why it would be a useful rule: Numbered sub-issues let Claude say "this is LCP issue #2" rather than paraphrasing the fix name, reducing ambiguity in multi-turn sessions.
