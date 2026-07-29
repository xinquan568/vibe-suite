---
name: patterns
description: Use when authoring or reviewing NL programming artifacts (agents, skills, commands, rules, hooks) — applies proven patterns and flags anti-patterns such as monolithic prompts, oversized skills, vague quantifiers, Write/Edit on read-only agents, prohibitions without alternatives, and linter-duplicating rules.
---

# NL Programming Patterns

A catalog of best practices and anti-patterns for natural-language programming artifacts, applicable to Claude Code, Codex CLI, and Antigravity alike. Every pattern below carries a rationale and a concrete example. The guidance is tool-agnostic — it is about the craft of NL instructions, not about any single tool's schemas. Use it while authoring or reviewing skills, agents, commands, rules, and hooks.

## Patterns (Use These)

### P1. Trigger-Optimized Descriptions (R04)

- **Problem.** A generic one-line description makes an agent or skill trigger unreliably — the model has nothing distinctive to match against.
- **Structure.** Put 3+ specific trigger phrases in every agent and skill description. The model matches description text when deciding what to invoke, so a richer vocabulary directly improves recall.
- **Example.** Good: a lint agent whose description is a multi-clause sentence enumerating four situations that should invoke it ("checking style on changed files, reviewing a PR diff for lint findings, pre-commit lint sweeps, fixing lint warnings the CI reported"). Bad: the two-word description "Analyzes files" — too broad and too vague to match anything reliably.
- **When to use.** Every time you write or revise a `description` field.

### P2. Example-Driven Agents (R09)

- **Problem.** Descriptions alone leave invocation behavior to inference; triggering drifts between sessions.
- **Structure.** Give every agent description 2+ `<example>` blocks. Each block contains a Context line, a user turn, and an assistant response. Diversify them: at minimum, one where the user invokes the agent directly and one where a command drives it as orchestrator, when applicable.
- **Example.**

  ```
  <example>
  Context: User asks for a lint pass on files they just changed.
  user: "Can you lint the files I touched in this branch?"
  assistant: "I'll dispatch the lint agent on the changed files."
  </example>
  ```

- **When to use.** Every agent definition; examples anchor behavior and improve trigger consistency.

### P3. Imperative + Rationale Rules (R03, R21)

- **Problem.** Bare prohibitions are hard to obey under inference load, and negations prime the very thing they forbid — the Pink Elephant effect.
- **Structure.** Write rules as "Do X because Y" instead of "Don't do Z". State the positive action, then attach the reason.
- **Example.** Good: "Use `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths because it keeps the plugin portable across install locations." Bad: "Don't hardcode absolute paths."
- **When to use.** Any rule, constraint, or instruction that would otherwise start with "don't" or "never".

### P4. Layered Prompts (R40)

- **Problem.** Complex command and agent bodies that interleave concerns produce degraded output — especially when the task statement is buried inside the constraints.
- **Structure.** Order complex bodies in five fixed layers: (1) role/persona, (2) context, (3) task, (4) constraints, (5) output format.
- **When to use.** Any command or agent body long enough to have distinguishable parts; check that no layer's content has leaked into another.

### P5. Graduated Model Selection (R10)

- **Problem.** One model tier for everything wastes tokens on mechanical work or produces unreliable judgment on nuanced work.
- **Structure.** Map the model tier to the task class:

  | Tier | Task class |
  |------|------------|
  | `haiku` | parsing, formatting, file discovery, classification, pattern matching |
  | `sonnet` | analysis, reasoning, code review, multi-step judgment, scoring |
  | `opus` | deep-synthesis judgment, orchestrating many agents |

- **Rationale.** `opus` on a glob scan is wasted tokens; `haiku` on nuanced scoring is unreliable.
- **When to use.** Every `model` field in an agent or command.

### P6. Scoped Skills (R05, R07)

- **Problem.** A skill that tries to cover everything bloats the context and is hard to update.
- **Structure.** Bound the scope and hold each skill under 500 lines, closing with a "Scope Note" that names the covered ground and the explicitly excluded ground, cross-referenced in `plugin:skill` format.
- **Benefits.** (1) Avoids context bloat when multiple skills are loaded at once; (2) localizes updates to one file; (3) enables precise skill selection in agent frontmatter.
- **When to use.** Whenever you create a skill or notice one growing past its original scope.

### P7. Least-Privilege Tools (R11)

- **Problem.** Unused tool declarations mislead the reader and may grant unintended capability.
- **Structure.** Declare only the tools the body actually uses — `allowed-tools` on commands, `tools` on agents.
- **Example.** Good: a scanner that only needs discovery and reading declares a 2-tool list. Bad: the same scanner declaring 6 tools including Write, Edit, Bash, and WebSearch.
- **When to use.** Every tool list; audit it against what the body actually does.

### P8. Explicit Output Formats (R12, R16, R41)

- **Problem.** Output shape left to inference varies run to run.
- **Structure.** Every command and agent body defines its exact output structure — section names, table columns, how scores are displayed, where the summary goes. Never leave any of it to inference.
- **Example.** A report spec that pins down: a Summary line with totals plus counts of Pass (≥70) and Fail (<70); a Results table with columns File / Type / Score / Top Issues; and a Details section giving a per-file penalty breakdown.
- **When to use.** Every artifact that produces output a human or another artifact will consume.

### P9. Error Path Coverage (R17)

- **Problem.** Unhandled failure paths turn into silent no-ops or generic failure text.
- **Structure.** Every command and agent handles three failure modes: (1) empty input — no argument given, or no files found; (2) missing files — a referenced path does not exist; (3) malformed data — YAML parse error, invalid JSON, truncation. Each must yield a clear, actionable error.
- **When to use.** Every command and agent, checked at review time.

### P10. Numeric Anchoring of Subjective Principles (R22)

- **Problem.** A principle built on a subjective threshold ("keep it simple") is untestable on its own.
- **Structure.** Follow the principle immediately with numeric examples that cover the corners of the trade space — best case, worst case, and a neutral case — so the principle becomes testable. Keep the judgment word; anchor it.
- **Exemplar.** karpathy/autoresearch `program.md:37` (an artifact scored 90/100): "simpler is better" is anchored by three val_bpb-versus-code-complexity corner cases — a 0.001 val_bpb gain that costs 20 hacky lines is rejected; a 0.001 gain achieved by deletion is accepted; roughly zero gain that leaves the code much simpler is kept.
- **When to use.** Apply it wherever a judgment word — clean, simple, reasonable, ugly, meaningful, small — shows up in rule, constraint, or workflow text.

### P11. Paired CAN/CANNOT Contract (R03)

- **Problem.** A pile of prohibitions with no stated positive scope makes agents over-conservative and trips the Pink Elephant trap.
- **Structure.** Present any non-trivial prohibition set as paired lists — "What you CAN do" and "What you CANNOT do" — where each prohibition has a positive complement. The CAN half is a positive scope statement that prevents over-conservatism, and the pairing structurally avoids the A2 trap.
- **Exemplar.** karpathy/autoresearch `program.md:25-31`: CAN edit one named file, with everything inside it fair game; CANNOT touch the read-only prep script, add new dependencies, or edit the eval harness.
- **When to use.** More than 2 prohibitions on the same subject — file, tool, or behavior boundaries. A single prohibition is fine in inline P3 form.

### P12. Autonomy Instruction + Rationale + Fallback Ladder (R03, R17)

- **Problem.** A bare "be autonomous" produces timid, permission-seeking agents.
- **Structure.** An effective autonomy instruction has three pieces: (1) the rule plus examples of forbidden questions, (2) a concrete why, (3) a named likely failure mode with numbered recovery moves given in advance.
- **Exemplar.** karpathy/autoresearch `program.md:112`, scored 90/100 — the loop never pauses on a mid-run "continue?" prompt (its stated rationale: the human may be asleep) and names four recovery moves: re-reading in-scope files, reading the referenced papers, combining near-misses, and attempting more radical architecture changes.
- **When to use.** Any operation that must run without per-step approval — long loops, overnight runs, batch jobs, recursive workflows. Without the ladder, the agent halts the moment it runs out of obvious moves.

### P13. Vivid Closing Use-Case (R16, R35)

- **Problem.** A workflow document that never shows the workflow at scale leaves its duty cycle abstract.
- **Structure.** End the workflow doc with a one-paragraph concrete scenario — a named persona, a named time of day, and a calculated quantity — that makes the duty cycle tangible.
- **Exemplar.** karpathy/autoresearch `program.md:114`: overnight-run arithmetic — about 5 minutes per experiment means about 12 per hour, so about 100 experiments over an average night's sleep.
- **When to use.** Workflows whose value comes from repetition or duration rather than a single execution; the closing scenario shows the reader what success at scale would actually look like.

## Anti-Patterns (Avoid These)

### A1. Vague Quantifiers (R01)

- **Problem.** The words "appropriate", "relevant", "as needed", "sufficient", "adequate", and "reasonable" — used without measurable criteria — leave behavior undefined.
- **Penalty.** The [vibe-suite:scoring](../scoring/SKILL.md) rubric applies -2 per occurrence, capped at -20.
- **Fix.** Replace each with a specific criterion. Three rewrites: a fuzzy length word becomes "under 500 lines"; "relevant tools" becomes "only the tools the body uses"; a vague conditional phrase becomes an explicit condition on the input type.

### A2. Prohibitions Without Alternatives (R03)

- **Problem.** Stating a prohibition without offering an alternative breaks P3 and strands the reader without an actionable path.
- **Fix.** Give every prohibition a paired alternative plus a because-clause. Two rewrites: hardcoded paths become the portable variable form; passive-voice instructions become imperative verbs.

### A3. Oversized Skills (R05)

- **Problem.** A skill over 500 lines is context bloat, and several oversized skills loaded together shrink the context left for the task itself.
- **Fix.** Split by responsibility. Example split: schema-shape material and quality-evaluation material become two skills — conventions and scoring.

### A4. Write/Edit on Read-Only Agents (R11)

- **Problem.** Audit, review, and analysis agents must never declare Write or Edit.
- **Heuristic.** Agents named `linter`, `scanner`, `reviewer`, `auditor`, or `inspector` are read-only by nature; modification belongs to a separate agent with that responsibility.

### A5. Monolithic Prompts (R13, R40)

- **Problem.** A single unstructured block — no headings, no sections, no numbered steps — yields inconsistent output.
- **Fix.** Add headings and numbered steps, group related instructions together, and put the output format specification at the END of the body, not the beginning.

### A6. Rules Duplicating Linters (R24)

- **Problem.** A rule that restates what eslint, ruff, or clippy already catches is redundant noise.
- **Principle.** What belongs in rules is exactly what no linter can check: intent, architecture, and NL artifact quality.
- **Fix.** Reference the tool and a pre-commit run instead of restating its checks.

### A7. Agents Without Examples (R09)

- **Problem.** Zero `<example>` blocks means triggering rests on inference from the description alone, which is unreliable.
- **Penalty.** -15 for zero examples on an agent.

### A8. Opus for Mechanical Tasks (R10)

- **Problem.** File discovery, JSON parsing, pattern matching, and line counting are haiku-class tasks; running them on `opus` costs 10-30x the tokens with no quality benefit.
- **Decision rule.** A deterministic answer that needs no judgment goes to `haiku`; nuanced evaluation goes to `sonnet`; reserve `opus` for work where `sonnet` demonstrably fails.

### A9. Hardcoded Paths (R30)

- **Problem.** An absolute path breaks in three scenarios: a different installing user, a moved project, and a CI/CD container.
- **Fix.** Use `${CLAUDE_PLUGIN_ROOT}` inside a plugin, and relative paths with a well-defined base elsewhere.

## Scope Note

This skill's coverage is NL programming patterns and anti-patterns, applied across Claude Code, Codex CLI, and Antigravity. NOT covered:

- Per-artifact-type schema and syntax details — see [vibe-suite:conventions](../conventions/SKILL.md)
- The scoring rubric and penalty tables — see [vibe-suite:scoring](../scoring/SKILL.md)
- General software-engineering patterns outside NL artifacts
