---
slug: evo-hq-evo
repo: evo-hq/evo
audited: 2026-05-13
commit_sha: e2dc7c42fcce9f9ee1fb1e9a66c1eb41310fa1aa
score: 98
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
  - R13
---

# Exemplar: evo-hq/evo

**Score**: 98/100  |  **Date**: 2026-05-13  |  **Commit**: `e2dc7c42fcce9f9ee1fb1e9a66c1eb41310fa1aa`

A three-skill plugin for autonomous LLM-optimization loops (`discover`, `optimize`, `subagent`) that earns its score by being a procedure manual, not a concept explainer — every section tells the agent what to run and what to do with the result.

## Per-rule evidence

### R04 — Description as trigger

The `discover` description doesn't summarize the skill; it is the skill's activation surface. It packs a slash-command match, two intent phrases, and a broader catch-all into one sentence, giving the host four distinct paths to load it.

> `plugins/evo/skills/discover/SKILL.md:3-4`:
>
> ```
> description: Initialize evo for the current repository by exploring the codebase,
> proposing unexplored optimization dimensions, constructing the benchmark inside a
> baseline worktree, and running the first experiment. Use when the user invokes
> /evo:discover, mentions setting up evo, wants to instrument a codebase for
> autonomous optimization, or asks to start a new evo run on a project.
> ```

Five trigger phrases in 481 characters: task summary + explicit slash command + two user-intent matches + fallback. The `subagent` skill explicitly marks itself non-user-invocable (`disable-model-invocation: true`) so it only fires via orchestrator delegation — no false positive activations.

### R05 — Body length

All three skills stay well under 500 lines despite covering multi-stage workflows: `discover` is 383 lines (13 numbered steps), `optimize` is 250 lines (7-step loop), `subagent` is 192 lines (7-step iteration protocol). Length discipline is maintained by externalizing long procedural references rather than inlining them.

> `plugins/evo/skills/discover/SKILL.md:70-71`:
>
> ```
> See `references/proposing-dimensions.md` for the full rubric, project-type
> examples, and presentation format. Short version:
> ```

And at line 237:
> `plugins/evo/skills/discover/SKILL.md:237`:
>
> ```
> If the selected benchmark is new, build it in the worktree. See
> `references/constructing-benchmark.md` for the full procedure:
> ```

The skills give the agent enough to follow the happy path, then offload the deep reference material to sidecar files rather than embedding it inline. The 500-line budget forces this discipline.

### R06 — Code examples must be runnable

The validation section in `discover` gives a complete executable script — not a diagram, not pseudocode — with env vars, mktemp, and the validator call, all resolved to concrete absolute paths before the shell sees them.

> `plugins/evo/skills/discover/SKILL.md:272-289`:
>
> ```bash
> # from main repo root
> WORKTREE="<...>"
> TARGET="$WORKTREE/<...>"
> VALIDATOR="<...>/scripts/validate_result.py"
>
> mkdir -p .evo/validate
> ATTEMPT="$(mktemp -d .evo/validate/run-XXXXXX)"
> mkdir -p "$ATTEMPT/traces"
>
> EVO_TRACES_DIR="$ATTEMPT/traces" \
> EVO_RESULT_PATH="$ATTEMPT/result.json" \
> EVO_EXPERIMENT_ID=validate \
>   python3 "$WORKTREE/benchmark.py" --target "$TARGET" \
>   >"$ATTEMPT/stdout.log" 2>"$ATTEMPT/stderr.log"
>
> python3 "$VALIDATOR" "$ATTEMPT/result.json"
> ```

The comment immediately before it explains why `{worktree}` must be expanded before the shell runs: `evo run` substitutes placeholders, a plain shell call does not. Code example + causal explanation in the same breath — exactly what distinguishes a runnable example from a code block.

### R07 — Scope note when related skills exist

`optimize` reaches into `subagent` rather than re-explaining the worker protocol. The scope note appears at the exact moment a reader would need it — after describing the dispatch path that forks from the explorer session.

> `plugins/evo/skills/optimize/SKILL.md:54`:
>
> ```
> **Trace instrumentation style**: `.evo/meta.json`'s `instrumentation_mode` records
> `sdk` vs `inline`. Subagents must stay consistent with it (see
> `skills/subagent/SKILL.md` for details).
> ```

Discover does the same for its reference files: `references/proposing-dimensions.md` for dimension-ranking rubric, `references/constructing-benchmark.md` for harness construction procedure. No redundant duplication; the cross-reference tells the agent where to look, not what it will find.

### R08 — Patterns over theory

The gate semantics section in `discover` teaches two named patterns — test-suite gate and score-threshold gate — each with a runnable example before the abstract rule is stated.

> `plugins/evo/skills/discover/SKILL.md:196-206`:
>
> ```bash
> # Test-suite gate: pytest already exits non-zero on failures (use uv run --with if
> # pytest isn't already a dep)
> evo gate add root --name core_tests --command "uv run --with pytest pytest tests/core/ -x"
>
> # Score-threshold gate: benchmark exits 1 if pass rate on protected tasks drops below 0.9
> evo gate add root --name refund_flow --command \
>   "python3 {worktree}/benchmark.py --target {target} --task-ids 5 --min-score 0.9"
>
> # Custom validation: smoke test that crashes (non-zero exit) on broken target
> evo gate add root --name no_crash --command "python3 smoke_test.py --target {target}"
> ```

The theory ("gate decided by exit code: 0 = pass, non-zero = fail") appears at lines 191–192 — but after the motivation ("A benchmark-style command that just prints `{"score": 0.0}` and exits 0 **passes the gate**. That defeats the purpose."). Pattern first, rule second, named categories throughout.

### R13 — System prompt structure: mission → steps → boundaries → format

`subagent/SKILL.md` hits all four layers in order with no structural debt.

**Mission** (lines 9–18): "You are an evo optimization subagent. The orchestrator has given you a brief with four fields." Roles and inputs stated in the first two sentences.

**Steps** (lines 52–151): "First Steps" then "Iteration Loop" — a numbered 7-step procedure. Each step is named and imperative.

**Boundaries** (lines 167–171):
> `plugins/evo/skills/subagent/SKILL.md:167-171`:
>
> ```
> ## Rules
> - Do NOT run `evo init` or `evo reset`
> - `evo discard <your_exp_id> --reason "..."` is your explicit "abandon" action ...
> - Always annotate your experiments, especially before discarding ...
> - Stay within your brief's objective and boundaries -- don't drift into unrelated changes
> ```

**Format** (lines 175–191): A literal `## Results` / `## Changes` / `## Learnings` / `## Suggestions` template the subagent fills on exit.

Mission and boundaries use concise imperative sentences; no fluffy explanation of why format matters. The format section is a template, not a description of a template.

## Worth adopting

**Pattern: Exhaustive exit-code enumeration for CLI tools.** Evidence: `plugins/evo/skills/discover/SKILL.md:29-36` — four numbered outcomes for `evo-version-check`, each with the exact exit code, the string produced on stderr, and the agent's required response (continue / stop + show verbatim / stop + tell user / fallback). Why it would be a useful rule: **When a skill calls an external CLI tool, enumerate every documented exit code with the required handler.** Without this, the agent either ignores non-zero exits or writes ad hoc error checks that miss cases the tool distinguishes. Exit-code enumeration is verifiable (does the list cover the tool's documented outcomes?), specific (no vague quantifiers), and directly reduces agent error rates on CLI-dependent skills.
