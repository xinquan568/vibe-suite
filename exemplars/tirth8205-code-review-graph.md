---
slug: tirth8205-code-review-graph
repo: tirth8205/code-review-graph
audited: 2026-05-13
commit_sha: 0919071a9ba353e604981059e99ee2ed98768092
score: 95
exemplifies:
  - R04
  - R05
  - R06
  - R08
  - R27
  - R35
  - R38
---

# Exemplar: tirth8205/code-review-graph

**Score**: 95/100  |  **Date**: 2026-05-13  |  **Commit**: `0919071a9ba353e604981059e99ee2ed98768092`

A 7-skill Claude Code plugin that wraps a graph-based code-review tool; notable for writing skills that behave as tight, trigger-ready dispatchers with zero padding and concrete MCP tool call syntax throughout.

## Per-rule evidence

### R04 — Description as trigger

`review-delta` packs two distinct action phrases into a 14-word description: the scope (changes since last commit), the mechanism (impact analysis), and the benefit (blast-radius detection). A user asking "can you review just what I changed?" or "check the blast radius of my diff" will match this description cleanly. It names the outcome the user wants, not the mechanism the skill uses.

> Real quote from `skills/review-delta/SKILL.md:3-4`:
>
> ```
> description: Review only changes since last commit using impact analysis. Token-efficient delta review with automatic blast-radius detection.
> ```

This beats a mediocre description like "Perform a code review" because it draws three orthogonal trigger phrases from one sentence: delta-only scope, impact analysis, and blast-radius — each surfacing on a different class of user query.

`review-pr` follows the same pattern, naming both the input type (PR or branch diff) and the output guarantee (structural context, blast-radius analysis):

> Real quote from `skills/review-pr/SKILL.md:3-4`:
>
> ```
> description: Review a PR or branch diff using the knowledge graph for full structural context. Outputs a structured review with blast-radius analysis.
> ```

### R05 — Body length

All seven skills are short. The longest (`review-pr`) is 67 lines; the shortest (`review-changes`) is 30. None approaches the 500-line ceiling. The plugin covers distinct workflows — build, review changes, review PR, review delta, debug, explore, refactor — without any skill exceeding one scroll of content.

> Real quote from `skills/review-changes/SKILL.md` (full file, 30 lines):
>
> ```
> ---
> name: Review Changes
> description: Perform a structured code review using change detection and impact
> ---
>
> ## Review Changes
>
> Perform a thorough, risk-aware code review using the knowledge graph.
>
> ### Steps
>
> 1. Run `detect_changes` to get risk-scored change analysis.
> 2. Run `get_affected_flows` to find impacted execution paths.
> 3. For each high-risk function, run `query_graph` with pattern="tests_for" to check test coverage.
> 4. Run `get_impact_radius` to understand the blast radius.
> 5. For any untested changes, suggest specific test cases.
>
> ### Output Format
>
> Provide findings grouped by risk level (high/medium/low) with:
> - What changed and why it matters
> - Test coverage status
> - Suggested improvements
> - Overall merge recommendation
>
> ## Token Efficiency Rules
> - ALWAYS start with `get_minimal_context(task="<your task>")` before any other graph tool.
> - Use `detail_level="minimal"` on all calls. Only escalate to "standard" when minimal is insufficient.
> - Target: complete any review/debug/refactor task in ≤5 tool calls and ≤800 total output tokens.
> ```

Thirty lines covers the full behavior. The skill earns a 100/100 score at this length.

### R06 — Code examples must be runnable

`build-graph` shows the exact MCP tool invocation for both the first-time and incremental cases, including the parameter name and value — not pseudocode, not "call the build tool", the actual call:

> Real quote from `skills/build-graph/SKILL.md:17-20`:
>
> ```
>    - For first-time setup: `build_or_update_graph_tool(full_rebuild=True)`
>    - For updates: `build_or_update_graph_tool()` (incremental by default)
> ```

`review-delta` does the same for the test-coverage lookup, naming the parameter and showing a template placeholder for the variable part:

> Real quote from `skills/review-delta/SKILL.md:31`:
>
> ```
>    - Verify test coverage using `query_graph_tool(pattern="tests_for", target=<function_name>)`
> ```

Both examples are copy-pasteable by Claude into a tool call. The distinction from a pseudocode approach (`"use the build tool with full_rebuild set to true"`) is that Claude can construct the exact call without guessing the parameter name.

### R08 — Patterns over theory

`review-delta` teaches by situation, not abstraction. Each step names the concrete tool, names what it returns, and names what to do with that return value. Step 3 is a model of the pattern:

> Real quote from `skills/review-delta/SKILL.md:23-26`:
>
> ```
> 3. **Analyze the blast radius** by reviewing the `impacted_nodes` and `impacted_files` in the context. Focus on:
>    - Functions whose callers changed (may need signature/behavior verification)
>    - Classes with inheritance changes (Liskov substitution concerns)
>    - Files with many dependents (high-risk changes)
> ```

It does not say "analyze impact carefully." It says which fields to read, and it names three specific sub-cases (caller changes, inheritance changes, high-fan-out files) with the concern that applies to each. The contrast between "check the blast radius" (theory) and "review `impacted_nodes` and `impacted_files`, focusing on callers / inheritance / high-fan-out" (pattern) is the whole point of R08.

### R27 — Event names are case-sensitive

`hooks.json` uses `SessionStart` and `PostToolUse` — the exact casing Claude Code expects. The file is 100/100 with no hook correctness issues.

> Real quote from `hooks/hooks.json:1,14`:
>
> ```json
> {
>   "SessionStart": [
>     ...
>   ],
>   "PostToolUse": [
>     ...
>   ]
> }
> ```

The hook fires on every `Write|Edit|Bash` tool use to keep the graph current. An incorrect casing (`postToolUse`, `posttooluse`) would silently drop all graph updates after file edits — the hardest class of hook bugs to notice because no error is raised.

### R35 — Include architecture overview

CLAUDE.md's Architecture section maps every module in the core package with a one-line purpose for each, plus the VS Code extension and the SQLite database location. A new contributor (or Claude on a fresh session) can locate any functional area without running `find` or reading imports.

> Real quote from `CLAUDE.md:16-37` (excerpt):
>
> ```
> - **Core Package**: `code_review_graph/` (Python 3.10+)
>   - `parser.py` — Tree-sitter multi-language AST parser (19 languages including Vue SFC, Solidity, Dart, R, Perl, Lua + Jupyter/Databricks notebooks)
>   - `graph.py` — SQLite-backed graph store (nodes, edges, BFS impact analysis)
>   - `tools.py` — 22 MCP tool implementations
>   - `main.py` — FastMCP server entry point (stdio transport), registers 22 tools + 5 prompts
>   - `incremental.py` — Git-based change detection, file watching
>   - `embeddings.py` — Optional vector embeddings (Local sentence-transformers, Google Gemini, MiniMax)
>   ...
> - **Database**: `.code-review-graph/graph.db` (SQLite, WAL mode)
> ```

Each line names the file, its layer, and its behavioral contract in ≤15 words. This is R35 compliance at above the minimum: not just "where things are" but "what they do."

### R38 — More instructive than descriptive

CLAUDE.md front-loads five numbered behavioral rules before any description of what the project is. The token-efficiency section does not describe a feature — it tells Claude what to call first, what parameter to pass, and sets a numeric target:

> Real quote from `CLAUDE.md:7-13`:
>
> ```
> When using code-review-graph MCP tools, follow these rules:
> 1. First call: `get_minimal_context(task="<description>")` — costs ~100 tokens, gives you the full picture.
> 2. All subsequent calls: use `detail_level="minimal"` unless you need more.
> 3. Prefer `query_graph` with a specific target over broad `list_*` calls.
> 4. The `next_tool_suggestions` field in every response tells you the optimal next step.
> 5. Target: ≤5 tool calls per task, ≤800 total tokens of graph context.
> ```

The Security Invariants section follows the same pattern — eight lines listing what never appears in the codebase (`eval()`, `exec()`, `shell=True`, etc.) alongside the positive invariants that replaced them (`_validate_repo_root()`, `_sanitize_name()`, list-form subprocess args). No prose explanation of why security matters; just the rules.

## Worth adopting

Pattern: **Output format template in skill body.** Evidence: `skills/review-pr/SKILL.md:36-60` (literal markdown template with `## PR Review`, `### Risk Assessment`, `### File-by-File Review`, `### Missing Tests`, `### Recommendations` sections), `skills/review-changes/SKILL.md:19-24` (grouped-by-risk-level format), `skills/review-delta/SKILL.md:35-39` (named sections with type annotations). All three 98–100-scoring skills include an explicit output format; all three 88-scoring skills omit it and take a -10 penalty. Why it would be a useful rule: "**Include an output format section in every skill body.** Without it, Claude's response structure varies between invocations of the same skill, making downstream parsing and user expectations unreliable."
