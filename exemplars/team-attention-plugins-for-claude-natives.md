---
slug: team-attention-plugins-for-claude-natives
repo: team-attention/plugins-for-claude-natives
audited: 2026-05-13
commit_sha: fd9c20754dba0b0ab040f3f2cd2cb533fc43347d
score: 92
exemplifies:
  - R04
  - R07
  - R08
  - R12
  - R43
---

# Exemplar: team-attention/plugins-for-claude-natives

**Score**: 92/100  |  **Date**: 2026-05-13  |  **Commit**: `fd9c20754dba0b0ab040f3f2cd2cb533fc43347d`

A Korean-developer-focused collection of 10+ Claude Code plugins (calendar, Gmail, session management, tech decisions, etc.) that shows how to write skill descriptions that fire reliably and how to cross-reference a family of related skills so Claude picks the right one.

## Per-rule evidence

### R04 — Description as trigger

The clarify plugin's `vague` skill packs 9 action phrases into a single description, including bilingual Korean/English triggers and the explicit slash command alias `/clarify`. Every phrase matches a real user query pattern — none are category labels.

> Real quote from `plugins/clarify/skills/vague/SKILL.md:3`:
>
> ```
> description: This skill should be used when the user's request or requirement is ambiguous and needs iterative questioning to become actionable. Trigger on "clarify requirements", "refine requirements", "요구사항 명확히", "요구사항 정리", "뭘 원하는 건지", "make this clearer", "spec this out", "scope this", "/clarify". Turns vague inputs into concrete specs. For strategy blind spots use unknown; for content-vs-form reframing use metamedium.
> ```

The `session-wrap` skill does the same for its domain, covering 7 distinct user phrasings including informal shorthands like "/wrap" alongside natural-language variants like "what should I commit":

> Real quote from `plugins/session-wrap/skills/session-wrap/SKILL.md:3`:
>
> ```
> description: This skill should be used when the user asks to "wrap up session", "end session", "session wrap", "/wrap", "document learnings", "what should I commit", or wants to analyze completed work before ending a coding session.
> ```

What makes these better than average: the descriptions end with scoped cross-references (telling Claude what *not* to do here), so the trigger doubles as a disambiguation fence.

### R07 — Scope note when related skills exist

The clarify plugin ships three related skills (`vague`, `metamedium`, `unknown`) that each carry cross-references pointing to the other two. This creates a closed disambiguation loop — no matter which skill Claude loads, it learns where to route queries that belong elsewhere.

> Real quote from `plugins/clarify/skills/metamedium/SKILL.md:3-4`:
>
> ```
> description: This skill should be used when the user is building, planning, or strategizing and the key question is whether to optimize content (what) or change form (how/medium). Trigger on "내용 vs 형식", "content vs form", "metamedium", "형식을 바꿔볼까", "새로운 포맷", "관점 전환", "perspective shift", "다른 방법 없을까", "같은 방식이 안 먹혀", "diminishing returns". Applies Alan Kay's metamedium concept to surface form-level alternatives. For requirement clarification use vague; for strategy blind spots use unknown.
> ```

And from inside the body, the scope note repeats at the usage-decision point:

> Real quote from `plugins/clarify/skills/metamedium/SKILL.md:30`:
>
> ```
> For requirement clarification, use the **vague** skill. For strategy blind spot analysis, use the **unknown** skill.
> ```

The scope note appears twice — in the frontmatter description (fires when Claude selects the skill) and at the top of the body (fires when Claude reads the skill). Belt-and-suspenders disambiguation.

### R08 — Patterns over theory

The `tech-decision` skill's quick-execution guide gives three concrete invocation patterns at increasing complexity rather than describing the framework abstractly. Each pattern is a user quote → numbered execution sequence pairing.

> Real quote from `plugins/dev/skills/tech-decision/SKILL.md:157-183`:
>
> ```
> ### 1. 간단한 비교 (A vs B)
>
> ```
> 사용자: "React vs Vue 뭐가 나을까?"
>
> 실행:
> 1. Task docs-researcher + Task codebase-explorer (병렬)
> 2. Skill: dev-scan
> 3. Task tradeoff-analyzer
> 4. Task decision-synthesizer
> ```
>
> ### 2. 깊은 분석 (복잡한 의사결정)
>
> ```
> 사용자: "우리 프로젝트에 상태관리 라이브러리 뭘 쓸지 고민이야"
>
> 실행:
> 1. Task codebase-explorer (현재 상태 분석)
> 2. 병렬 실행:
>    - Task docs-researcher (Redux, Zustand, Jotai, Recoil 등)
>    - Skill: dev-scan
>    - Skill: agent-council
> 3. Task tradeoff-analyzer
> 4. Task decision-synthesizer
> ```
> ```

Three patterns for three complexity levels, each with a real user quote as the entry condition. A reader can match their situation to a pattern without reading the full orchestration diagram above it.

### R12 — Output format defined in body

The `tradeoff-analyzer` agent defines an exact output template spanning per-option pros/cons tables with source attribution columns, a confidence rating system (five percentage bands with criteria), and a weighted comparison table. A reader knows exactly what output to expect before running the agent.

> Real quote from `plugins/dev/agents/tradeoff-analyzer.md:97-116`:
>
> ```markdown
> ## Output Format
>
> ```markdown
> ## 트레이드오프 분석 결과
>
> ### 평가 기준
>
> | 기준 | 가중치 | 근거 |
> |------|--------|------|
> | [기준 1] | X% | [왜 이 가중치인지] |
>
> ---
>
> ### Option A: [이름]
>
> #### 장점 (Pros)
> | 장점 | 중요도 | 출처 | 신뢰도 |
> |------|--------|------|--------|
> | [장점 1] | 높음 | 공식 문서 | 95% |
> | [장점 2] | 중간 | Reddit + HN | 75% |
> ```
> ```

The source column and confidence percentage on every pros/cons row is the differentiating detail — it forces the agent to surface where each claim came from, not just what the claim is.

### R43 — Parallel when independent, sequential when dependent

The `session-wrap` skill diagrams its 5-agent pipeline explicitly, labeling Phase 1 as parallel (4 agents with no cross-dependency) and Phase 2 as sequential (1 validation agent that depends on Phase 1 results). The dependency constraint is stated in prose immediately after the diagram.

> Real quote from `plugins/session-wrap/skills/session-wrap/SKILL.md:12-36`:
>
> ```
> ## Execution Flow
>
> ┌─────────────────────────────────────────────────────┐
> │  2. Phase 1: 4 Analysis Agents (Parallel)           │
> │     ┌─────────────────┬─────────────────┐           │
> │     │  doc-updater    │  automation-    │           │
> │     │  (docs update)  │  scout          │           │
> │     ├─────────────────┼─────────────────┤           │
> │     │  learning-      │  followup-      │           │
> │     │  extractor      │  suggester      │           │
> │     └─────────────────┴─────────────────┘           │
> ├─────────────────────────────────────────────────────┤
> │  3. Phase 2: Validation Agent (Sequential)          │
> │     ┌───────────────────────────────────┐           │
> │     │       duplicate-checker           │           │
> │     │  (Validate Phase 1 proposals)     │           │
> │     └───────────────────────────────────┘           │
> ```

And the rationale is stated explicitly:

> Real quote from `plugins/session-wrap/skills/session-wrap/SKILL.md:95-97`:
>
> ```
> ## Step 3: Phase 2 - Validation Agent (Sequential)
>
> Run after Phase 1 completes (dependency on Phase 1 results).
> ```

The ASCII flow diagram gives Claude the topology without requiring it to infer phase structure from prose. The "(dependency on Phase 1 results)" rationale prevents Claude from accidentally parallelizing the validation step.

## Worth adopting

**Pattern: Complexity-tiered quick reference.** Evidence: `plugins/dev/skills/tech-decision/SKILL.md:155-196`. The skill provides three named execution tiers ("simple comparison", "deep analysis", "architecture decision"), each paired with a representative user quote and a numbered agent-call sequence. Why it would be a useful rule: skills that orchestrate multiple agents across varying input complexity benefit from tier-labeled invocation patterns — Claude can match the user's apparent scope to the right execution path without reading the full workflow specification.

**Pattern: Mandatory tool call declared in skill body.** Evidence: `plugins/clarify/skills/vague/SKILL.md:8` (`**ALWAYS use the AskUserQuestion tool** — never ask clarifying questions in plain text`) and `plugins/clarify/skills/metamedium/SKILL.md:34` (same sentinel). Why it would be a useful rule: when a skill's protocol requires a specific tool call that Claude might otherwise skip (interactive questions as plain text instead of structured UI), an ALL-CAPS constraint in the body's first instructional sentence measurably reduces drift.
