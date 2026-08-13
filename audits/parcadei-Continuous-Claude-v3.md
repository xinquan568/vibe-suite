# Audit: parcadei/Continuous-Claude-v3

**Date:** 2026-04-29  
**Commit:** d07ff4b06b62f43771bc0c927d0211b734d6149e  
**Artifacts audited:** 94 (32 agents, 62 skills)  
**NL Score:** 78/100  
**Security verdict:** BLOCKED  
**Threshold:** 70 (default)  
**Score vs threshold:** PASS (but contribution blocked by security gate)

---

## Executive Summary

Continuous-Claude-v3 is a sophisticated multi-agent system built on top of Claude Code. It extends Claude Code with hooks, skills, agents, a PostgreSQL-backed memory system, TLDR code-intelligence tooling, handoff/continuity infrastructure, and a sandbox runner for math proofs. The architecture is genuinely impressive and the skills are well-written on average (score 80/100). Agents score lower (74/100) primarily because every single agent is missing a formal `## Examples` block.

Two issues prevent contribution:

1. **Security gate (BLOCKED):** `prove/SKILL.md` contains a live `curl ... | sh` invocation that instructs Claude to pipe a remote shell script directly to the interpreter. This pattern is CRITICAL regardless of intent.

2. **Systemic quality gap:** 31 of 32 agents (97%) lack any examples block. This is a single-pass fix that would bring the agent average from ~74 to ~89.

---

## Security Scan

### CRITICAL

**`curl` piped to shell in NL artifact**

| | |
|---|---|
| File | `.claude/skills/prove/SKILL.md` |
| Line | 22 |
| Rule | `SEC-curl-pipe-sh` |
| Pattern | `curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf \| sh` |

A skill file — loaded into Claude's context and followed as instructions — contains a bare `curl ... | sh` command. When this skill is active, Claude is instructed to download and execute an unsigned, remote shell script. Even though the intent is legitimate Lean installation, any compromise of the GitHub-hosted script becomes a supply-chain risk with no verification step. The same instruction appears in `opc/scripts/setup/math_features.py:143` (in a `print()` docstring, lower risk) and `wizard.py:229,560,1136` (print statements, lower risk).

**Fix:** Replace with a pinned, content-verified install step (pin the script SHA, or vendor a local copy, or use `elan`'s documented package manager paths).

### HIGH

**`subprocess.run(cmd, shell=True)` with user-controlled string**

| | |
|---|---|
| File | `opc/scripts/repoprompt_async.py` |
| Line | 47 |
| Rule | `SEC-shell-true` |
| Pattern | `subprocess.run(cmd, shell=True, capture_output=True, text=True)` |

The helper `run_cmd(cmd: str)` passes its string argument directly to the shell interpreter. Call sites construct `cmd` using f-strings that embed command-line arguments (workspace names, task descriptions) provided by the user. A workspace name containing shell metacharacters (`; rm -rf ~`, backticks, `$()`) executes as a separate shell command.

**Fix:** Build `cmd` as a list and set `shell=False`, or at minimum sanitize/quote user-provided segments via `shlex.quote`.

### MEDIUM

**Unpinned `npx -y` packages in MCP config**

| | |
|---|---|
| File | `.claude/mcp_config.json` |
| Lines | 22–45 |
| Rule | `SEC-curl-pipe-sh` (analogue: auto-execute unsigned package) |
| Pattern | `npx -y firecrawl-mcp`, `npx -y @morphllm/morphmcp`, `npx -y @perplexity-ai/mcp-server`, `npx -y @anthropic/mcp-ast-grep` |

Four MCP servers are configured with `npx -y` (auto-install, no version pin). These are all `"disabled": true` in the checked-in config, reducing actual exposure. However, the config ships as a template and `disabled: false` is one edit away. If enabled, npm resolves the latest version at runtime — a compromised package release would auto-execute.

**Fix:** Pin package versions (`npx -y firecrawl-mcp@1.2.3`) or switch to `npx firecrawl-mcp@<pinned-version>`.

### Summary

| Severity | Count | Files |
|----------|-------|-------|
| Critical | 1 | `prove/SKILL.md:22` |
| High | 1 | `opc/scripts/repoprompt_async.py:47` |
| Medium | 2 | `mcp_config.json`, `math_features.py` |
| Low | 0 | — |

**Verdict: BLOCKED** — critical pattern `SEC-curl-pipe-sh` found in an NL skill artifact. Contribution workflow will label `security-blocked` and skip PR creation pending manual review.

Positive signal: `opc/docker/sandbox_runner.py` implements CPU/RAM resource limits, a timeout signal handler, and restricted `exec` builtins — showing genuine security awareness in the math sandbox subsystem.

---

## NL Quality Scoring

### Scoring Methodology

Base 100, deduct:
- Missing `examples` block: −15 (zero examples), −5 (exactly one)
- Missing `tools` frontmatter field on an agent: −5 per field
- Agent uses a tool in its prompt but does not declare it: −10 (BUG, affects usability)
- Broken cross-reference (skill/agent path does not exist): −10 (BUG)
- Vague quantifiers: −2 each, capped at −20
- Model violation (haiku when prohibited): −10

### Agent Scores

| Agent | Score | Primary deductions |
|-------|-------|--------------------|
| memory-extractor | 90 | None significant |
| kraken | 82 | No examples (−15), content otherwise strong |
| arbiter | 82 | No examples (−15) |
| atlas | 82 | No examples (−15) |
| architect | 82 | No examples (−15) |
| aegis | 82 | No examples (−15) |
| spark | 82 | No examples (−15) |
| phoenix | 82 | No examples (−15) |
| herald | 82 | No examples (−15) |
| critic | 82 | No examples (−15) |
| sleuth | 82 | No examples (−15) |
| profiler | 80 | No examples (−15) |
| pathfinder | 80 | No examples (−15) |
| scout | 80 | No examples (−15) |
| oracle | 75 | No examples (−15), non-standard `llm_service` field (−5) |
| agentica-agent | 75 | Has inline examples, broken skill ref BUG (−10) |
| plan-reviewer | 75 | Has examples, undeclared Bash BUG (−10) |
| onboard | 75 | No tools field (−5), no examples (−15) |
| scribe | 72 | No examples (−15), implicit bash without declaration (−5) |
| chronicler | 72 | No examples (−15), minimal content |
| review-agent | 72 | No tools field (−5), no examples (−15) |
| surveyor | 65 | No examples (−15), undeclared bash BUG (−10) |
| maestro | 65 | No examples (−15), broken agent refs BUG (−10) |
| judge | 65 | No examples (−15), undeclared bash BUG (−10) |
| liaison | 70 | No examples (−15), undeclared bash (−5) |
| context-query-agent | 65 | No tools field (−5), undeclared bash BUG (−10), no examples (−15) |
| braintrust-analyst | 60 | No tools field (−5), undeclared tools BUG (−10), no examples (−15) |
| debug-agent | 60 | No tools field (−5), broken skill ref BUG (−10), no examples (−15) |
| plan-agent | 60 | No tools field (−5), broken skill ref BUG (−10), no examples (−15) |
| session-analyst | 60 | No tools field (−5), broken skill ref BUG (−10), no examples (−15) |
| research-codebase | 60 | No tools field (−5), broken agent refs BUG (−10), one example (−5) |
| validate-agent | 62 | Model: haiku violation (−10), no tools field (−5), no examples (−15) |

**Agent mean: 74/100**  
**Agents below threshold (70): 9** — braintrust-analyst, debug-agent, plan-agent, session-analyst, research-codebase, validate-agent, maestro, judge, context-query-agent

### Skill Scores (representative sample)

| Skill | Score | Notes |
|-------|-------|-------|
| tldr-code | 90 | Comprehensive, allowed-tools, real examples |
| perplexity-search | 88 | Good structure, allowed-tools |
| tdd-migrate | 88 | Comprehensive, allowed-tools, examples |
| tdd-migration-pipeline | 88 | Comprehensive, allowed-tools |
| debug-hooks | 88 | Allowed-tools, real examples |
| trace-claude-code | 88 | Plugin skill, comprehensive |
| morph-apply | 88 | 3 real code examples, allowed-tools |
| compound-learnings | 88 | AskUserQuestion, allowed-tools |
| cli-reference | 88 | Comprehensive reference |
| fix | 88 | Orchestrator with examples, allowed-tools |
| dead-code | 85 | Allowed-tools, keywords |
| math-unified | 85 | Good examples, allowed-tools |
| sub-agents | 85 | Good examples, allowed-tools |
| agentica-server | 85 | Allowed-tools |
| implement_task | 85 | Comprehensive |
| implement_plan | 85 | Comprehensive |
| repoprompt | 85 | Allowed-tools, good examples |
| tdd | 82 | Keywords, no allowed-tools |
| mcp-chaining | 82 | Allowed-tools |
| repo-research-analyst | 82 | Good content, no allowed-tools |
| opc-architecture | 82 | Conceptual reference, useful |
| parallel-agents | 82 | Clear pattern examples |
| hooks | 82 | Code examples |
| braintrust-tracing | 82 | Structured reference |
| discovery-interview | 82 | user-invocable, hardcoded model version (unusual) |
| agentic-workflow | 80 | Reference doc, no allowed-tools |
| agent-context-isolation | 80 | Reference doc |
| parallel-agent-contracts | 80 | Good type patterns |
| agentica-prompts | 82 | No allowed-tools |
| workflow-router | 78 | No allowed-tools |
| create_handoff | 78 | No allowed-tools |
| system_overview | 78 | No allowed-tools |
| security | 78 | No allowed-tools |
| git-commits | 78 | No allowed-tools |
| idempotent-redundancy | 78 | No allowed-tools |
| modular-code | 78 | No allowed-tools |
| no-polling-agents | 78 | No allowed-tools |
| recall-reasoning | 78 | No allowed-tools |
| explicit-identity | 78 | No allowed-tools |
| router-first-architecture | 78 | No allowed-tools |
| completion-check | 78 | No allowed-tools |
| mcp-scripts | 78 | No allowed-tools |
| qlty-during-development | 78 | No allowed-tools |
| environment-triage | 78 | No allowed-tools |
| math-router | 78 | No allowed-tools |
| llm-tuning-patterns | 78 | No allowed-tools |
| tldr-stats | 78 | No allowed-tools |
| loogle-search | 75 | No allowed-tools |
| onboard (skill) | 75 | user-invocable: true, no allowed-tools |
| implement_plan_micro | 75 | Complex formal spec, no allowed-tools |
| tour | 75 | No allowed-tools, no user-invocable |
| build | 75 | `user_invocable` field name error (should be `user-invocable`) |
| plan-agent (skill) | 68 | Name mismatch: frontmatter says `planning-agent`, folder says `plan-agent` |
| validate-agent (skill) | 72 | Invocation example uses `model: "haiku"` (violates project rule) |
| async-repl-protocol | 72 | Minimal content |
| continuity_ledger | 82 | Alias skill for create_handoff |
| index-at-creation | 72 | Very short, session IDs as "source" citations |
| complete-skill | 60 | Only 2 instruction lines, minimal content |

**Skill mean: 80/100**

### Overall NL Score

```
Agents: 74.0 × 32 = 2368
Skills: 80.4 × 62 = 4985
Total: 7353 / 94 = 78.2 → 78
```

**NL Score: 78/100** (above default threshold of 70)

---

## Bug Findings

These are deterministic, verifiable bugs suitable for PR contributions (pending security gate clearance).

### Broken Cross-References (6)

1. **`research-codebase.md`** — References three non-existent agents: `codebase-locator`, `codebase-analyzer`, `codebase-pattern-finder`. None exist in `.claude/agents/`.

2. **`maestro.md`** — Agent Reference table lists "turbo", "pioneer", "nexus" as available agents. None exist in `.claude/agents/`. These appear to be legacy names from an earlier version.

3. **`debug-agent.md`** — Instructs loading `.claude/skills/debug/SKILL.md`. No `debug/` skill folder exists.

4. **`plan-agent.md` (agent)** — Instructs loading `.claude/skills/create_plan/SKILL.md`. No `create_plan/` skill folder exists.

5. **`agentica-agent.md`** — Instructs loading `.claude/skills/agentica-sdk/SKILL.md`. No `agentica-sdk/` skill folder exists.

6. **`session-analyst.md`** — Instructs loading `.claude/skills/braintrust-analyze/SKILL.md`. No `braintrust-analyze/` skill folder exists.

### Undeclared Tools (6)

Agents whose prompt bodies use tools not declared in their frontmatter `tools:` field. Claude Code respects the declared tool list as a permission boundary; undeclared tools will be unavailable.

7. **`braintrust-analyst.md`** — No `tools:` field but the prompt body uses Bash (runs Python scripts) and implicitly Write. Any execution will silently fail or fall back to main-agent tools.

8. **`context-query-agent.md`** — No `tools:` field but runs `artifact_query.py` via Bash. Bash is never accessible to an agent with no tools declaration.

9. **`judge.md`** — Tools: `[Read, Grep, Glob]`. Prompt body shows `git diff HEAD` and `uv run pytest` commands. Neither git nor pytest are reachable without Bash.

10. **`surveyor.md`** — Tools: `[Read, Grep, Glob]`. Prompt shows `rp-cli snapshot`, `rp-cli switch` bash commands. Bash not declared.

11. **`liaison.md`** — Tools: `[Read, Grep, Glob]`. Shows `cat FILE` and `rp-cli` invocations requiring Bash.

12. **`plan-reviewer.md`** — Tools: `[Read, Grep, Glob]`. "Verification Commands" section shows bash commands that cannot run without Bash in tools.

### Name Mismatches (2)

13. **`.claude/skills/plan-agent/SKILL.md`** — Frontmatter declares `name: planning-agent` but the skill lives at `plan-agent/SKILL.md`. Any agent that references this skill by folder name (`plan-agent`) will be loading a skill whose declared name is different. Confusing for orchestration and skill activation.

14. **`.claude/skills/build/SKILL.md`** — Uses `user_invocable: true` (underscore) rather than the standard `user-invocable: true` (hyphen). Most Claude Code parsers that check for the canonical field name will silently ignore this.

### Model Rule Violation (1)

15. **`.claude/agents/validate-agent.md`** — Frontmatter declares `model: haiku`. The project's own `.claude/rules/no-haiku.md` explicitly prohibits this: "Never use `model: haiku` when spawning agents via the Task tool." Additionally, `.claude/skills/validate-agent/SKILL.md` (the skill counterpart) contains an invocation example with `model: "haiku"`, spreading the violation to documentation.

---

## Quality Findings (Systemic)

### No Examples Block (31/32 agents)

Every agent except `memory-extractor` and `agentica-agent` (which has inline code) is missing a formal `## Examples` section. This −15 penalty per agent accounts for the bulk of the quality deficit. Adding a 3–5 line example to each agent would raise the agent average from 74 to approximately 89.

Pattern:
```markdown
## Examples

**Investigate slow startup:**
> "Use pathfinder to analyze the build pipeline for performance bottlenecks"

**Cross-repo dependency check:**
> "Pathfinder: compare auth module patterns between our monorepo and the upstream library"
```

### Missing `tools:` Field (9 agents)

The following agents have no `tools:` frontmatter field, meaning they inherit all tools from the parent context:

- `onboard.md`, `research-codebase.md`, `debug-agent.md`, `plan-agent.md`, `session-analyst.md`, `review-agent.md`, `braintrust-analyst.md`, `context-query-agent.md`, `validate-agent.md`

For read-only analysis agents, inheriting all tools is a security over-grant. The principle of least privilege recommends declaring only the tools actually used.

### Missing `allowed-tools:` in Skills (≈25 skills)

Approximately 25 of 62 skills lack `allowed-tools:` frontmatter. While skills are reference documents and not agents, the field signals to skill-loading infrastructure which tools the skill's instructions expect to be available. Notable gaps:

- `workflow-router`, `system_overview`, `security`, `create_handoff`, `loogle-search`, `opc-architecture`, `parallel-agents`, `hooks`, `tdd`, `git-commits`

---

## What's Working Well

1. **Architecture documentation:** `opc-architecture/SKILL.md` clearly explains the OPC extension model, how agents are subprocess-spawned, and how coordination works via PostgreSQL. Rare to see this clearly documented.

2. **Hook ecosystem:** 30+ shell+TypeScript hook wrappers with a build pipeline (esbuild, vitest tests). The hook test suite (`dist/__tests__/`) is non-trivial. The `hook_launcher.py` auto-selects Node vs uv vs Python fallback.

3. **Memory system:** PostgreSQL + pgvector with BGE embeddings for hybrid RRF recall is production-grade. The `recall_learnings.py` / `store_learning.py` pair provides a clean API.

4. **Math sandbox:** `sandbox_runner.py` properly implements CPU/RAM resource limits, timeout, and restricted builtins — a thoughtful security design for code execution.

5. **TLDR integration:** 4 skill files (`tldr-code`, `tldr-stats`, `session-start-tldr-cache.sh`) wrap the TLDR CLI intelligence layer coherently.

6. **Handoff continuity:** The ledger format is well-specified (`continuity_ledger/SKILL.md`), the YAML schema is precise, and the statusline fields (`goal:`, `now:`) are documented.

7. **Best-in-class skills:** `compound-learnings`, `fix`, `tdd-migrate`, `debug-hooks`, `morph-apply` are all >85 quality and would serve as templates for the weaker agents.

---

## Recommended PRs (Post-Security-Gate)

If the security gate is cleared, the following PRs are high-value and low-risk:

| PR | Files | Fix | Confidence |
|----|-------|-----|------------|
| Fix broken agent references | `maestro.md`, `research-codebase.md` | Remove/update stale agent names in reference tables | high |
| Fix missing skill references | `debug-agent.md`, `plan-agent.md`, `agentica-agent.md`, `session-analyst.md` | Either create stub skills or remove references | high |
| Fix undeclared Bash tool | `judge.md`, `surveyor.md`, `liaison.md`, `plan-reviewer.md` | Add `Bash` to each agent's `tools:` list | high |
| Fix braintrust-analyst tools | `braintrust-analyst.md` | Add `tools: [Bash, Write, Read, Grep, Glob]` | high |
| Fix name mismatch in plan-agent skill | `.claude/skills/plan-agent/SKILL.md` | Change `name: planning-agent` to `name: plan-agent` | high |
| Fix user_invocable field | `.claude/skills/build/SKILL.md` | Rename `user_invocable` → `user-invocable` | high |
| Fix validate-agent model | `.claude/agents/validate-agent.md` | Remove `model: haiku` line | high |
| Add examples to top-tier agents | `maestro.md`, `scout.md`, `kraken.md`, `arbiter.md`, `sleuth.md`, `architect.md` | Add 2–3 line Examples section | medium |
