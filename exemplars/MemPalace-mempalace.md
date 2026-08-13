---
slug: MemPalace-mempalace
repo: MemPalace/mempalace
audited: 2026-05-13
commit_sha: 2d6c0bf31ab8efb813a319c8cabae9e9d9990ba3
score: 90
exemplifies:
  - R04
  - R05
  - R06
  - R08
  - R30
  - R33
  - R34
  - R35
---

# Exemplar: MemPalace/mempalace

**Score**: 90/100  |  **Date**: 2026-05-13  |  **Commit**: `2d6c0bf31ab8efb813a319c8cabae9e9d9990ba3`

A five-command Claude Code and Codex CLI plugin that delegates all runtime instruction loading to a local Python CLI — skills stay under 15 lines and never go stale because they carry no content to drift.

## Per-rule evidence

### R04 — Description as trigger

The five codex-plugin skills pack a specific action verb and concrete domain nouns into a single sentence each. The descriptions mirror user queries, not feature summaries.

> `.codex-plugin/skills/search/SKILL.md:3`:
>
> ```
> Search your MemPalace — semantic search across all mined memories, projects, and conversations.
> ```

> `.codex-plugin/skills/mine/SKILL.md:3`:
>
> ```
> Mine a project or conversation into your MemPalace — extract and store memories for later retrieval.
> ```

> `.codex-plugin/skills/status/SKILL.md:3`:
>
> ```
> Show MemPalace status — room counts, storage usage, and palace health.
> ```

The monolithic `.claude-plugin` skill lists five trigger queries explicitly rather than describing the feature:

> `.claude-plugin/skills/mempalace/SKILL.md:3`:
>
> ```
> MemPalace — mine projects and conversations into a searchable memory palace. Use when asked about
> mempalace, memory palace, mining memories, searching memories, or palace setup.
> ```

Each description uses the noun the user would say ("memories", "palace", "projects") and the verb the user would type ("mine", "search", "show"). None says "this skill helps with memory management."

### R05 — Body length

Every codex-plugin skill is 12 lines total — frontmatter, heading, and body together. The monolithic claude-plugin skill is 36 lines. Both are well under the 500-line ceiling by design: the skills carry no content, only a delegation invocation.

> `.codex-plugin/skills/help/SKILL.md` (frontmatter + body, all 12 lines):
>
> ```
> ---
> name: help
> description: Show MemPalace help — available commands, usage tips, and getting started guidance.
> allowed-tools: Bash, Read
> ---
>
> # MemPalace Help
>
> Run the following command and follow the returned instructions step by step:
>
> [bash block: mempalace instructions help]
> ```

Body length is a side-effect of the CLI-delegation architecture (see "Worth adopting"), not a separate editing pass.

### R06 — Code examples are runnable

Every skill body contains exactly one code block, and it is a real bash invocation — not pseudocode, not a placeholder with angle-bracket substitutions.

> `.codex-plugin/skills/mine/SKILL.md:11-13`:
>
> ```bash
> mempalace instructions mine
> ```

> `.codex-plugin/skills/init/SKILL.md:11-13`:
>
> ```bash
> mempalace instructions init
> ```

The five commands — `help`, `init`, `mine`, `search`, `status` — map directly to the subcommands enumerated in the monolithic skill's overview section. Every example runs if `mempalace` is installed.

### R08 — Patterns over theory

The skill body teaches exactly one thing: run this command, then follow its output. There is no explanation of how semantic search works internally, no background on the AAAK compression dialect, and no narrative on the palace metaphor. All of that lives in the CLI's runtime output.

> `.codex-plugin/skills/status/SKILL.md:9-13`:
>
> ```
> Run the following command and follow the returned instructions step by step:
>
> [bash block: mempalace instructions status]
> ```

Claude receives the specific action for the specific situation. It does not need to reason from abstract principles to concrete steps — the skill body is already the step.

### R30 — `${CLAUDE_PLUGIN_ROOT}` for paths

Both hook entries in `hooks.json` use `${CLAUDE_PLUGIN_ROOT}` rather than absolute paths, and both referenced scripts exist on disk.

> `.claude-plugin/hooks/hooks.json:9`:
>
> ```json
> "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/mempal-stop-hook.sh\""
> ```

> `.claude-plugin/hooks/hooks.json:18`:
>
> ```json
> "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/mempal-precompact-hook.sh\""
> ```

The variable-based path survives repository relocation and cross-machine installation. An absolute path like `/Users/milla/…` would silently break on any other machine — including CI.

### R33 + R34 — Build and test commands in CLAUDE.md

`CLAUDE.md` opens the "Setup" section with a single install invocation and follows it with a "Commands" section listing every development workflow.

> `CLAUDE.md` (Setup section):
>
> ```bash
> uv sync --extra dev   # recommended; or: pip install -e ".[dev]"
> ```

> `CLAUDE.md` (Commands section):
>
> ```bash
> # Run tests
> uv run pytest tests/ -v --ignore=tests/benchmarks
>
> # Run tests with coverage
> uv run pytest tests/ -v --ignore=tests/benchmarks --cov=mempalace --cov-report=term-missing
>
> # Lint
> uv run ruff check .
>
> # Format
> uv run ruff format .
> ```

Claude does not need to guess tooling. The `--ignore=tests/benchmarks` flag, the coverage flags, and the ruff mode distinction (check vs. format vs. format --check) are all provided verbatim — details that a generic "run tests" instruction would omit.

### R35 — Architecture overview

`CLAUDE.md` provides two complementary orientation tools: a dataflow diagram and a task-indexed file map.

> `CLAUDE.md` (Architecture section):
>
> ```
> User → CLI / MCP Server → Storage Backend (ChromaDB default, pluggable)
>                         → SQLite (knowledge graph)
>
> Palace structure:
>   WING (person/project)
>     └── ROOM (day/topic)
>           └── DRAWER (verbatim text chunk)
>
> Index layer (AAAK):
>   Compressed pointers → DRAWER locations
>   Scanned by LLM to find relevant drawers without reading all content
> ```

> `CLAUDE.md` (Key Files for Common Tasks section):
>
> ```
> - **Adding an MCP tool**: `mempalace/mcp_server.py` — add handler function + TOOLS dict entry
> - **Changing search**: `mempalace/searcher.py`
> - **Modifying mining**: `mempalace/miner.py` (project files) or `mempalace/convo_miner.py` (transcripts)
> - **Adding a storage backend**: subclass `mempalace/backends/base.py`, register in `backends/__init__.py`
> - **Input validation**: `mempalace/config.py` — `sanitize_name()` / `sanitize_content()`
> ```

The task-indexed file map is stronger than a plain directory listing: Claude jumps directly to the right file for the task at hand rather than scanning the project tree. Each entry names the file, the function or dict to touch, and the registration step.

## Worth adopting

**Pattern: CLI-delegation for skills.** Each skill body is `mempalace instructions <command>`, which calls the installed CLI at runtime to retrieve current instructions. Evidence: all five codex-plugin skills follow this pattern (`.codex-plugin/skills/*/SKILL.md:11`). Why it would be a useful rule: skills that delegate instruction content to a CLI binary cannot go stale — the instructions evolve with the binary, not with a SKILL.md commit. The SKILL.md becomes a dispatch stub; the binary is the single source of truth for behavior. Candidate rule: "**Delegate runtime instructions to a CLI when one owns the feature.** If the artifact calls a versioned binary, emit instructions from the binary rather than embedding them in the skill body. This keeps body length near zero and eliminates documentation drift."

**Pattern: Dual-harness implementation at different granularities.** `.claude-plugin/skills/mempalace/SKILL.md` is one monolithic skill; `.codex-plugin/skills/` splits the same surface into five per-command skills. Evidence: audit report Cross-Component section — "the asymmetry is not a defect but a deliberate cross-harness adaptation." Why it would be a useful rule: harnesses differ in how they route skills to context. A harness that selects by command name benefits from narrow per-command skills; a harness that selects by keyword match benefits from one trigger-rich description. The same feature can ship both without conflict. Candidate rule: "**Match skill granularity to harness routing strategy.** Per-command skills for name-routed harnesses; single trigger-rich skill for keyword-routed harnesses. Ship both when targeting multiple harnesses."
