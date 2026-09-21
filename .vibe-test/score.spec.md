---
artifact: commands/score.md
type: command
min_score: 80
---

# score — suite spec (vibe-229 / M35)

Source: `commands/score.md` as shipped. This spec restates what the artifact already
documents — its arguments, the deterministic engine as sole penalty authority, the rendered
table and bands, and the second-opinion lanes — as a test; nothing here is an invention the
artifact does not state.

## Triggers On
- "/vibe-suite:score"
- "/vibe-suite:score skills/"
- "/vibe-suite:score --changed"
- "/vibe-suite:score commands/ --engine both"
- "score this command file on the 100-point rubric"
- "lint the NL artifacts in this plugin"

## Does Not Trigger On
- "how have my artifact scores changed since the last run"   (trend's job — commands/trend.md)
- "check reference integrity across my plugin's components"  (check's job — commands/check.md)
- "run my .vibe-test specs"                                 (test's job — commands/test.md)
- "give me a judgment audit of this skill's design"          (nl-audit's job — commands/nl-audit.md)

## Frontmatter Valid
- `description` present, naming the deterministic scoring engine and the history snapshot
- `argument-hint` offering `[--changed]`
- `argument-hint` offering `[--engine claude|codex|both]`
- `model` absent — no pinned model id (P9)

## Output Contains
- the findings table header `| # | Sev | Rule | Line | Issue | Penalty | Fix |`
- a score band: Excellent, Good, Adequate, Weak or Rewrite
- the pass verdict against `score_threshold` in the run summary
- where the history snapshot went (`.claude/vibe-history.json`)
- the score labelled `computed`
- a disagreement listing under `--engine both`

## Output Format
1. Per file, the findings table with the exact header, then the score and band
2. Severities derived from penalty magnitude
3. Advisories rendered below the table at zero penalty

## Handles Input
| Input | Expected Behavior |
|-------|-------------------|
| (empty) | defaults to the current working directory |
| path that is not a readable directory or file | refused |
| `--changed` | target set restricted to artifacts modified per `git status --porcelain` |
| `--changed` outside a git repository | refused |
| no `--engine` | `claude` — the deterministic engine only, one `computed` score |
| no `.vibe-suite.md` in the target | scored with the suite defaults, never refused |
| vague-scanner count disagrees with the engine | the engine's count stands; an advisory line names both counts |
| second opinion not in record shape, or `check` outside the catalog | reported as an unusable second opinion, with no diagnostic header |
