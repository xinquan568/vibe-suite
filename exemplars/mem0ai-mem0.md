---
slug: mem0ai-mem0
repo: mem0ai/mem0
audited: 2026-05-13
commit_sha: 70bc9e51d57fe005d02b7b6d81b56476bade3cb3
score: 91
exemplifies:
  - R04
  - R05
  - R07
  - R08
  - R30
  - R32
---

# Exemplar: mem0ai/mem0

**Score**: 91/100  |  **Date**: 2026-05-13  |  **Commit**: `70bc9e51d57fe005d02b7b6d81b56476bade3cb3`

A five-skill Claude Code plugin for the Mem0 memory platform, notable for dense trigger-phrase coverage, disciplined scope routing between skills, named-pattern bodies, and correct hook event wiring.

## Per-rule evidence

### R04 — Description as trigger

Every skill in this collection treats its `description` block as a dispatch table rather than a summary. `mem0-vercel-ai-sdk` packs 11 distinct trigger phrases in the first 9 lines, each matching a concrete user query pattern. The description also lists its two sibling skills by name in a `DO NOT TRIGGER when:` clause, so the loader can route without ambiguity.

> Real quote from `skills/mem0-vercel-ai-sdk/SKILL.md:3-14`:
>
> ```
> description: >
>   Mem0 provider for Vercel AI SDK (@mem0/vercel-ai-provider).
>   TRIGGER when: user mentions "vercel ai sdk", "@mem0/vercel-ai-provider",
>   "createMem0", "retrieveMemories", "addMemories", "getMemories",
>   "searchMemories", "mem0 vercel", "AI SDK provider", "AI SDK memory",
>   or is using generateText/streamText with mem0. Also triggers for Next.js
>   apps needing memory-augmented AI.
>   DO NOT TRIGGER when: user asks about direct Python/TS SDK calls without Vercel
>   (use mem0 skill), or CLI terminal commands (use mem0-cli skill).
> ```

What makes this strong rather than mediocre: the trigger phrases are quoted user-input strings, not category labels. "createMem0" matches exactly what a developer would type; "AI SDK memory" matches the vaguer version of the same query. Together they cover the full query surface without overlap.

### R05 — Body length

The five standalone skills are each bounded under 200 lines (mem0: 191, mem0-vercel-ai-sdk: 192, mem0-cli: 153), with deeper reference material — provider API docs, usage patterns, SDK guides — split into `references/` sub-files linked from a table at the end of each skill. The top-level body covers the 80% case; the linked files are loaded only when needed.

> Real quote from `skills/mem0-vercel-ai-sdk/SKILL.md:180-186`:
>
> ```
> ## References
>
> | Topic | File |
> |-------|------|
> | Provider API (`createMem0`, `Mem0Provider`, types) | [local](references/provider-api.md) / [GitHub](...) |
> | Memory utilities (`addMemories`, `retrieveMemories`, etc.) | [local](references/memory-utilities.md) / [GitHub](...) |
> | Usage patterns and examples | [local](references/usage-patterns.md) / [GitHub](...) |
> ```

Each skill stays focused because depth is delegated, not stuffed inline. The `local` / `GitHub` link pairs mean the skill works both as an installed plugin and as a raw repo reference.

### R07 — Scope note when related skills exist

Every skill in the collection includes both a `DO NOT TRIGGER when:` line in the description (for the skill loader) and a `Related Mem0 Skills` table at the bottom (for Claude's reasoning when it has already loaded the skill). The table names each sibling, states its specific use case, and provides local and GitHub paths.

> Real quote from `skills/mem0-vercel-ai-sdk/SKILL.md:188-193`:
>
> ```
> ## Related Mem0 Skills
>
> | Skill | When to use | Link |
> |-------|-------------|------|
> | mem0 | Python/TypeScript SDK, REST API, framework integrations | [local](../mem0/SKILL.md) / [GitHub](...) |
> | mem0-cli | Terminal commands, scripting, CI/CD, agent tool loops | [local](../mem0-cli/SKILL.md) / [GitHub](...) |
> ```

The "When to use" column carries the scope signal — not just skill names, but the decision criterion. A reader who arrives at the wrong skill can self-route without guessing.

### R08 — Patterns over theory

`mem0-vercel-ai-sdk` names three distinct usage patterns — Wrapped Model, Standalone Utilities, Streaming — each with a header, a sentence stating when to choose it, a complete runnable code block, and a "What happens under the hood" numbered step list. No paragraph describes the Mem0 API in the abstract; every section answers "what do I type for situation X."

> Real quote from `skills/mem0-vercel-ai-sdk/SKILL.md:41-59`:
>
> ```
> ## Pattern 1: Wrapped Model
>
> The wrapped model approach is the simplest. `createMem0` returns a provider that wraps
> any supported LLM with automatic memory retrieval and storage.
>
> ```typescript
> import { generateText } from "ai";
> import { createMem0 } from "@mem0/vercel-ai-provider";
>
> const mem0 = createMem0();
> const { text } = await generateText({
>   model: mem0("gpt-5-mini", { user_id: "alice" }),
>   prompt: "Recommend a restaurant",
> });
> ```
>
> What happens under the hood:
> 1. The prompt is sent to Mem0 search (`POST /v3/memories/search/`) to retrieve relevant memories
> 2. Retrieved memories are injected as a system message at the start of the prompt
> 3. The underlying LLM (e.g., OpenAI gpt-5-mini) generates a response using the enriched prompt
> 4. The conversation is stored back to Mem0 (`POST /v3/memories/add/`) as a fire-and-forget async call
> ```

The numbered "What happens under the hood" block makes the pattern auditable: a developer debugging a failure knows exactly which HTTP call to check at each step.

### R30 — Use `${CLAUDE_PLUGIN_ROOT}` for paths

All six hook entries in `mem0-plugin/hooks/hooks.json` reference scripts via `${CLAUDE_PLUGIN_ROOT}`, not hardcoded absolute paths. The plugin will work on any machine where the plugin root is set, regardless of install location.

> Real quote from `mem0-plugin/hooks/hooks.json:7-11`:
>
> ```json
> {
>   "type": "command",
>   "command": "${CLAUDE_PLUGIN_ROOT}/scripts/on_session_start.sh",
>   "statusMessage": "Loading mem0 context..."
> }
> ```

Every hook entry in the file follows the same pattern consistently — there are no local-path exceptions in any of the six hook definitions.

### R32 — Block on PreToolUse, advise on PostToolUse

The hooks file uses `PreToolUse` for the one hook that needs to block an action (`block_memory_write.sh`), and lifecycle events (`Stop`, `TaskCompleted`, `UserPromptSubmit`) for all observational hooks that run after or alongside actions. No advisory hook is wired to `PreToolUse`, which would make it capable of blocking the action it only intends to observe.

> Real quote from `mem0-plugin/hooks/hooks.json:15-25`:
>
> ```json
> "PreToolUse": [
>   {
>     "matcher": "Write|Edit",
>     "hooks": [
>       {
>         "type": "command",
>         "command": "${CLAUDE_PLUGIN_ROOT}/scripts/block_memory_write.sh"
>       }
>     ]
>   }
> ],
> ```

The naming convention reinforces the intent: the script is called `block_memory_write.sh`, not `log_memory_write.sh` — the gate is clearly a guard, not an observer.

## Worth adopting

**Pattern: UTM-tagged API key URLs per skill.** Evidence: `skills/mem0-vercel-ai-sdk/SKILL.md:38` — `https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=skill-mem0-vercel-ai-sdk`; same pattern in `skills/mem0-cli/SKILL.md:51` with `utm_medium=skill-mem0-cli`. Each skill uses a unique `utm_medium` value. Why it would be a useful rule: skill authors who own the linked service can attribute installs to specific skills without any additional instrumentation — the URL itself carries the attribution signal.

**Pattern: Dual local+GitHub cross-reference links.** Evidence: `skills/mem0/SKILL.md:28-29` — `[mem0-cli](../mem0-cli/SKILL.md) ([GitHub](https://github.com/mem0ai/mem0/tree/main/skills/mem0-cli))`. Every cross-reference in the skill graph carries both a relative local path and an absolute GitHub URL. Why it would be a useful rule: a skill installed as a plugin resolves the local path; a skill read from a raw GitHub URL (by an agent browsing the repo) resolves the GitHub link — dual links make cross-references work in both contexts without duplication.
