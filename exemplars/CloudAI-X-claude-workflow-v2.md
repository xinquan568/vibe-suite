---
slug: CloudAI-X-claude-workflow-v2
repo: CloudAI-X/claude-workflow-v2
audited: 2026-05-13
commit_sha: b6952dd3cd31b548d57ea88352c84692030e5480
score: 93
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
  - R12
  - R16
  - R30
---

# Exemplar: CloudAI-X/claude-workflow-v2

**Score**: 93/100  |  **Date**: 2026-05-13  |  **Commit**: `b6952dd3cd31b548d57ea88352c84692030e5480`

Full-stack Claude Code plugin (7 agents, 20 commands, 13 skills, 14 hooks) notable for skill descriptions that pack multiple distinct trigger conditions per sentence, runnable multi-language code examples, and mandatory structured output templates in both agents and commands.

## Per-rule evidence

### R04 — Description as trigger

The `error-handling` skill packs 5 distinct trigger conditions into a 2-sentence description — "designing error handling", "setting up logging", "implementing retries", "adding error tracking", and "asked about error boundaries, log aggregation, alerting, or resilience patterns." Each phrase matches a different real user query; none is a paraphrase of another.

> Real quote from `skills/error-handling/SKILL.md:2-3`:
>
> ```
> description: Implements error handling patterns, structured logging, retry strategies, circuit breakers, and graceful degradation. Use when designing error handling, setting up logging, implementing retries, adding error tracking, or when asked about error boundaries, log aggregation, alerting, or resilience patterns.
> ```

The contrast with a weak description is clear: "Helpful for errors" would trigger on nothing specific. These 5 conditions load the skill on substantively different user intents and keep it dormant on everything else.

### R05 — Body length

`skills/error-handling/SKILL.md` is 480 lines — at the limit — and earns every line: custom error hierarchy in 3 languages, structured logging with correlation IDs, exponential backoff, a full CircuitBreaker class, Sentry integration, and a 12-row anti-pattern summary table. No padding.

> Real quote from `skills/error-handling/SKILL.md:463-480`:
>
> ```
> AVOID                              DO INSTEAD
> -------------------------------------------------------------------
> Empty catch blocks                 Log and handle or re-throw
> Bare `except:` in Python           Catch specific exceptions
> console.log for production         Structured logger (pino, winston)
> Logging passwords/tokens           Redact sensitive fields
> Retry without backoff              Exponential backoff with jitter
> Retry on all errors                Only retry transient/network errors
> No circuit breaker                 Circuit breaker for external calls
> Exposing stack traces to users     Generic user messages, detailed logs
> No correlation IDs                 Propagate correlation ID across services
> One giant try/catch                Granular error handling per operation
> Logging inside tight loops         Log summaries/aggregates
> No error boundaries in React       Wrap independent sections separately
> ```

480 lines at full density is what the limit exists for. Padding to 600 "for completeness" would add nothing and burn context on every load.

### R06 — Code examples must be runnable

The `error-handling` skill provides real TypeScript, Python, and Go examples for every pattern — not pseudocode. The Python bare-except pair is importable-and-testable. The Go error-wrapping example uses `%w` (the real Go idiom), not a simplified stand-in.

> Real quote from `skills/error-handling/SKILL.md:130-145`:
>
> ```python
> # WRONG: Bare except
> try:
>     result = process(data)
> except:  # catches SystemExit, KeyboardInterrupt too!
>     pass
>
> # CORRECT: Specific exceptions, proper logging
> try:
>     result = process(data)
> except ValidationError as e:
>     logger.warning("Validation failed", extra={"errors": e.errors})
>     raise
> except DatabaseError as e:
>     logger.error("Database error during processing", exc_info=True)
>     raise AppError("Processing failed", "PROCESS_FAILED") from e
> ```

The comment on the WRONG example — "catches SystemExit, KeyboardInterrupt too!" — names the specific consequence, not a vague warning. That precision is what makes the example instructive rather than decorative.

### R07 — Scope note when related skills exist

Every skill opens with a "When to Load" block that has both a **Trigger** line and a **Skip** line. The Skip line prevents Claude from loading the skill in adjacent but irrelevant contexts.

> Real quote from `skills/parallel-execution/SKILL.md:9-12`:
>
> ```
> ### When to Load
>
> - **Trigger**: Multi-agent tasks, concurrent operations, spawning subagents, parallelizing independent work
> - **Skip**: Single-step tasks or sequential workflows with no parallelization opportunity
> ```

Without the Skip line, a user asking about sequential database migrations could plausibly trigger a "parallel execution" skill. The Trigger alone doesn't draw the boundary; the Skip line does.

### R08 — Patterns over theory

The `parallel-execution` skill teaches via named, numbered patterns with slot-fill templates — not a description of what parallelism is. Pattern 1 is Task-Based, Pattern 2 is Directory-Based, Pattern 3 is Perspective-Based. Each maps a plan to a spawn list with concrete values.

> Real quote from `skills/parallel-execution/SKILL.md:99-117`:
>
> ```
> ### Pattern 1: Task-Based Parallelization
>
> When you have N tasks to implement, spawn N subagents:
>
> Plan:
> 1. Implement auth module
> 2. Create API endpoints
> 3. Add database schema
> 4. Write unit tests
> 5. Update documentation
>
> Spawn 5 subagents (one per task):
> - Subagent 1: Implements auth module
> - Subagent 2: Creates API endpoints
> - Subagent 3: Adds database schema
> - Subagent 4: Writes unit tests
> - Subagent 5: Updates documentation
> ```

A theory-focused version would say "Parallelism is beneficial when tasks are independent." This version shows exactly what task-based parallelization looks like in an agent orchestration context, making it actionable on first encounter.

### R12 — Output format defined in body

The `code-reviewer` agent defines a four-tier severity output format — Critical, Warning, Suggestion, Positive Observations — and specifies what each tier means and what each finding must include (WHY, current code, specific fix, reference).

> Real quote from `agents/code-reviewer.md:80-107`:
>
> ```markdown
> ## Output Format
>
> Organize findings by severity:
>
> ### 🔴 Critical (Must Fix)
>
> Issues that will cause bugs, security vulnerabilities, or data loss.
>
> ### 🟡 Warning (Should Fix)
>
> Issues that may cause problems or indicate poor practices.
>
> ### 🔵 Suggestion (Consider)
>
> Improvements for readability, performance, or maintainability.
>
> ### ✅ Positive Observations
>
> Good patterns worth highlighting for the team.
>
> ## Constructive Feedback
>
> For each issue:
>
> 1. Explain WHY it's a problem
> 2. Show the current code
> 3. Provide a specific fix
> 4. Reference relevant documentation if helpful
> ```

The Positive Observations tier prevents an agent that finds zero criticals from returning only silence or a boilerplate "looks good" — it forces the agent to surface teachable patterns even in clean code.

### R16 — Define output format in commands

`commands/refactor-guided.md` (score 98) mandates two structured output blocks: a pre-flight Refactoring Scope report before any change is made, and a final Refactoring Summary after all steps. Both templates specify exact fields including reverted attempts.

> Real quote from `commands/refactor-guided.md:35-43`:
>
> ```
> ## Refactoring Scope
> - Target: [file/directory]
> - Files affected: [count]
> - Dependencies: [list]
> - Dependents: [list]
> - Risk level: [low/medium/high]
> ```

> Real quote from `commands/refactor-guided.md:86-111`:
>
> ```
> ## Refactoring Summary
>
> ### Before
> - Files: [count and names]
> - Lines of code: [approximate]
> - Complexity: [observations]
>
> ### After
> - Files: [count and names]
> - Lines of code: [approximate]
> - Complexity: [observations]
>
> ### Changes Applied
> 1. [refactoring 1] - [commit hash]
>
> ### Reverted Attempts
> 1. [what was tried] - [why it failed]
>
> ### Test Results
> - All tests passing: [yes/no]
> - Tests added: [count]
> - Total test runs: [count]
> ```

The pre-flight scope report gates the workflow on an explicit risk-level assessment, so the command never starts refactoring without reporting blast radius.

### R30 — Use `${CLAUDE_PLUGIN_ROOT}` for paths

All 14 scripts across all 6 event categories in `hooks/hooks.json` use `${CLAUDE_PLUGIN_ROOT}` as the path prefix — no absolute paths, no relative paths that would break under a different install root.

> Real quote from `hooks/hooks.json:7-11`:
>
> ```json
> {
>   "type": "command",
>   "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/protect-files.py"
> }
> ```

This pattern is consistent across PreToolUse, PostToolUse, Notification, Stop, SessionStart, and UserPromptSubmit. A single hardcoded `/home/user/…` path would silently break every hook for every other user.

## Worth adopting

**Pattern: Adversarial self-review block in agents.** Both `code-reviewer` and `security-auditor` include an "Adversarial Self-Review" section — a checklist the agent applies to its own output before finalizing ("Am I nitpicking?", "Did I miss the forest for the trees?", "Did I verify my claims?"). Evidence: `agents/code-reviewer.md:108-116`, `agents/security-auditor.md:202-210`. Why it would be a useful rule: agents produce confident-sounding reports on code they haven't fully read; an explicit self-challenge step reduces shallow output without requiring a second agent call.

**Pattern: Effort scaling table in agents.** Both code-reviewer and security-auditor open with a 4-row Instant/Light/Deep/Exhaustive effort table mapping trigger conditions to depth of review. Evidence: `agents/code-reviewer.md:19-26`, `agents/security-auditor.md:19-26`. Why it would be a useful rule: single-line changes don't warrant the same depth as architecture PRs; without an explicit scaling table, agents default to maximum effort on every invocation.
