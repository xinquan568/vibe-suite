---
artifact: commands/roast.md
type: command
min_score: 80
---

# roast — suite spec (vibe-229 / M35)

Source: `commands/roast.md` as shipped. This spec restates what the artifact already
documents — its arguments, recon-first dispatch, report layout and writing boundaries — as a
test; nothing here is an invention the artifact does not state.

## Triggers On
- "/vibe-suite:roast"
- "/vibe-suite:roast src/ --engine both"
- "/vibe-suite:roast --style 5 --mini"
- "/vibe-suite:roast . --full --output review.md"
- "interrogate this codebase and give me a fixing plan"
- "run a multi-angle code review of this repository"

## Does Not Trigger On
- "audit the skills and agents in this plugin"         (nl-audit's job — commands/nl-audit.md)
- "fix the findings in this roast report"              (fix's job — commands/fix.md)
- "find the root cause of this crash"                  (bug-analyze's job — commands/bug-analyze.md)
- "scan this plugin's hooks for security risks"        (security-scan's job — commands/security-scan.md)

## Frontmatter Valid
- `description` present, naming the recon survey and the reconciliation labels
- `argument-hint` offering `[--engine claude|codex|both]`
- `argument-hint` offering `[--mini|--full]`
- `model` absent — no pinned model id (P9)

## Output Contains
- a report at `<target>/vibe-report-<YYYY-MM-DD-HHMM>.md` unless `--output` overrides it
- `## Executive summary`
- `## Fixing plan`
- finding ids `F-1`, `F-2`, … as the first token of each finding
- reconciliation labels `both-agree`, `claude-only`, `<engine>-only` (`--engine both`)

## Output Format
1. Frontmatter with target, engine, style, generated and a version read from `.claude-plugin/plugin.json`
2. `## Executive summary`, citing finding ids but introducing none
3. Findings sections: `## [Agent: vibe-suite:<name>] Findings` in-session, `## Dimension: <name>` for cross-model lanes
4. One section per requested add-on
5. `## Fixing plan`, phased `### Phase 1 — now`, `### Phase 2 — next`, `### Phase 3 — later`

## Handles Input
| Input | Expected Behavior |
|-------|-------------------|
| (empty) | target is the current working directory |
| path that is not a readable directory | refused |
| no `--style` | style 2 |
| `--mini` | the separate mini prompt and file set; test files skipped |
| `--style 6` on more than 500 files | stops and asks, stating the file count and cost; proceeds only on an explicit yes |
| more than 20 files for the engine | sent in groups of 10, one dispatch per group |
| codex batch unreachable or returning nothing usable | falls back to the manual in-session lane for that batch |
| resolved report path (or `--output`) already exists | refuse, never overwrite |
