---
artifact: commands/nl-audit.md
type: command
min_score: 80
---

# nl-audit — suite spec (vibe-229 / M35)

Source: `commands/nl-audit.md` as shipped. This spec restates what the artifact already documents —
its six audit types, depth flags, engine lanes, fallback and the dimension-grouped findings table —
and invents nothing. Every assertion below cites a line of the artifact (or, for a near-miss, of
the command that owns it).

## Triggers On
- "/vibe-suite:nl-audit"
- "/vibe-suite:nl-audit --type skill skills/auditing"
- "/vibe-suite:nl-audit --type repo --mini"
- "/vibe-suite:nl-audit --engine both --background"
- "run a cross-model judgment audit of this command file"
- "audit every natural-language artifact across this whole repo"

## Does Not Trigger On
- "score these NL artifacts on the 100-point deterministic rubric"   (score's job — commands/score.md)
- "check cross-component reference integrity across these artifacts" (check's job — commands/check.md)
- "scan this plugin's hooks and scripts for security risks"          (security-scan's job — commands/security-scan.md)
- "fix the findings from the last audit and verify them"             (fix's job — commands/fix.md)

## Frontmatter Valid
- `description` present, naming the cross-model judgment audit of natural-language artifacts
- `argument-hint` offering `[--type skill|command|agent|rules|plugin|repo]`
- `argument-hint` offering `[--engine claude|codex|both]`
- `model` absent — no pinned model id (P9)

## Output Contains
- one section per dimension headed like `### D5 — Argument Safety`
- the findings table header `| # | File | Observation | Severity | Evidence | Proposed change | Tradeoff |`
- severities on the `[CRITICAL]`/`[HIGH]`/`[MEDIUM]`/`[LOW]`/`[GOOD]` scale
- the depth that ran and the engine that answered
- a `[GOOD]` signal on zero findings, never an empty table

## Output Format
1. Per artifact, one section per dimension that produced a finding, in id order
2. A findings table carrying the six fields File, Observation, Severity, Evidence, Proposed change, Tradeoff
3. Below the table: the depth that ran, the engine that answered, and on a `--mini` run the full-only dimensions not audited

## Handles Input
| Input | Expected Behavior |
|-------|-------------------|
| no `--type` | type inferred with `commands/shared/classify.md`; a target of no audited type is refused by name |
| `--mini` | audits only the `mini+full` dimension members |
| no depth flag | `--full` is the default and audits every dimension |
| empty scope | resolves to uncommitted changes via scope-parse |
| empty resolved list | stops the run with its message; not audited as a clean result |
| `--type repo` | discovery replaces the scope, over categories A–E |
| `--type plugin` | local analysis; dispatches no engine |
| `--background` | returns a launch receipt and hands the job to `/vibe-suite:jobs` |
| engine unreachable | hops with the diagnostic header to manual in-session analysis; never stops because an engine failed |
