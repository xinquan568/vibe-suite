---
slug: vladikk-modularity
repo: vladikk/modularity
audited: 2026-05-13
commit_sha: bcdca9a595764b9aa88d5d8d6020f52e7f5f1f52
score: 98
exemplifies:
  - R04
  - R05
  - R07
  - R08
---

# Exemplar: vladikk/modularity

**Score**: 98/100  |  **Date**: 2026-05-13  |  **Commit**: `bcdca9a595764b9aa88d5d8d6020f52e7f5f1f52`

A four-skill plugin for modularity analysis that earns near-perfect score by packing precise trigger phrases, using `skills:` frontmatter for dependency injection, and converting abstract guidance into lookup tables Claude can follow mechanically.

## Per-rule evidence

### R04 — Description as trigger

The `balanced-coupling` reference skill packs 10 specific trigger phrases in its `description` field, each matching a distinct user query type. The description closes with a one-line summary of what the skill provides, so it both triggers and previews in a single block.

> Real quote from `skills/balanced-coupling/SKILL.md:3-11`:
>
> ```yaml
> description: >
>   The Balanced Coupling model for software design. Use when: designing modular architectures,
>   evaluating coupling between components, reviewing code modularity, deciding whether to split
>   or merge modules/services, assessing integration patterns, classifying coupling as balanced
>   or unbalanced, applying DDD strategic and tactical patterns, reasoning about cohesion vs
>   coupling trade-offs, identifying distributed monolith risks, or explaining why a system
>   is hard to change. Provides the three-dimensional framework (integration strength, distance,
>   volatility) and the balance rule for making coupling decisions.
> ```

What separates this from a mediocre description: each trigger phrase is a distinct use case, not a synonym of the one before it. "Deciding whether to split or merge modules/services" and "applying DDD strategic and tactical patterns" fire on different user prompts — the breadth is real, not padded.

### R05 — Body length

All four SKILL.md files stay well under 500 lines. The largest (`balanced-coupling`) covers a full three-dimensional framework in ~330 lines by using boolean expressions and an ASCII summary grid rather than prose repetition.

| Skill | Lines |
|-------|-------|
| `skills/balanced-coupling/SKILL.md` | ~330 |
| `skills/design/SKILL.md` | ~248 |
| `skills/document/SKILL.md` | ~154 |
| `skills/review/SKILL.md` | ~89 |

The compression in `balanced-coupling` is most visible at the balance rule: the full three-dimensional model with its four extreme combinations collapses into two lines of boolean logic.

> Real quote from `skills/balanced-coupling/SKILL.md:212-215`:
>
> ```
> MODULARITY = STRENGTH XOR DISTANCE
> COMPLEXITY = STRENGTH AND DISTANCE
> ```
>
> And at line 229:
>
> ```
> BALANCE = (STRENGTH XOR DISTANCE) OR NOT VOLATILITY
> ```

These three lines replace the conceptual model that would need several paragraphs in prose. The rest of the 330 lines is the rationale and context for those expressions — none of it is filler.

### R07 — Scope note when related skills exist

Both active skills (`review` and `design`) declare their dependencies in `skills:` frontmatter, and then repeat the dependency in body prose with the annotation `(preloaded from the balanced-coupling skill)`. The double declaration — machine-readable in frontmatter, human-readable in body — means Claude knows both which skills to load and why they're already in context.

> Real quote from `skills/review/SKILL.md:1-11`:
>
> ```yaml
> ---
> name: review
> description: >
>   Analyzes a codebase's modularity imbalances using the Balanced Coupling model...
> skills:
>   - balanced-coupling
>   - document
> ...
> ---
> ```

> Real quote from `skills/review/SKILL.md:16`:
>
> ```
> You analyze codebases for modularity imbalances using the Balanced Coupling model by Vlad Khononov (preloaded from the balanced-coupling skill).
> ```

> Real quote from `skills/review/SKILL.md:78`:
>
> ```
> Using the document skill (preloaded), produce the modularity review in both Markdown and HTML formats.
> ```

The `(preloaded from the balanced-coupling skill)` annotation is the key detail: it tells Claude the knowledge is already in context, preventing it from searching for it or loading it twice. The reference skill itself is correctly marked `user-invocable: false` (`balanced-coupling/SKILL.md:11`) so it never surfaces as a standalone command.

### R08 — Patterns over theory

The `document` skill avoids abstract link-writing guidance ("always link coupling concepts"). Instead it provides a lookup table mapping every coupling concept to its exact `coupling.dev` URL — a concrete pattern Claude follows mechanically without interpreting intent.

> Real quote from `skills/document/SKILL.md:96-119`:
>
> ```markdown
> | Concept mentioned                                                                                           | Link to                                                                 |
> | ----------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
> | Balanced coupling, the balance rule, the balance formula, `STRENGTH XOR DISTANCE`, modularity vs complexity | https://coupling.dev/posts/core-concepts/balance/                       |
> | Integration strength, shared knowledge, levels of coupling strength                                         | https://coupling.dev/posts/dimensions-of-coupling/integration-strength/ |
> | Intrusive coupling, private interfaces, implementation detail leakage                                       | https://coupling.dev/posts/dimensions-of-coupling/integration-strength/ |
> | Functional coupling, duplicated business logic, shared functional requirements                              | https://coupling.dev/posts/dimensions-of-coupling/integration-strength/ |
> ...
> | Domain-driven design, DDD, bounded contexts, aggregates                                                     | https://coupling.dev/posts/related-topics/domain-driven-design/         |
>
> **Rules:**
> - Every coupling concept in the document MUST be linked at least once. If in doubt, link it.
> ```

"Link coupling concepts to coupling.dev" is theory. The lookup table converts it into a mechanical lookup with zero ambiguity — Claude cannot misinterpret which URL to use for "intrusive coupling" versus "model coupling."

## Worth adopting

**Pattern: Reference skill as injected context, not a callable command.** Evidence: `skills/balanced-coupling/SKILL.md:11` (`user-invocable: false`) combined with `skills/review/SKILL.md:8-10` (`skills: [balanced-coupling, document]`). Why it would be a useful rule: a reference knowledge base that appears in the user's skill list causes confusion — it has no invocable action. Marking it `user-invocable: false` while listing it as a dependency of active skills gives it a clear role: injected context. This pattern is reusable anywhere a large domain reference (API spec, style guide, domain model) needs to be shared across multiple active skills without polluting the user-facing skill list.

**Pattern: `(preloaded from X skill)` annotation at first body reference.** Evidence: `skills/review/SKILL.md:16` and `skills/review/SKILL.md:78`. Why it would be a useful rule: when a skill body relies on knowledge injected by another skill, the annotation prevents Claude from searching the context window for the source or treating the knowledge as something it should load separately; one parenthetical eliminates both failure modes and makes the dependency graph legible to a human reader.
