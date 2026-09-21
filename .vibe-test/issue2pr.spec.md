---
artifact: skills/issue2pr/SKILL.md
type: skill
min_score: 80
---

# issue2pr — suite spec (vibe-229 / M35)

Source: `skills/issue2pr/SKILL.md` as shipped. This spec restates what the skill already
documents — its description, its pipeline, its state and its refusals — as a test; it adds
no invented expectations.

## Triggers On
- "turn issue #42 into a reviewed pull request"
- "run the nine-step analyze, plan, execute pipeline on this work item"
- "/vibe-suite:issue2pr profile init"
- "resume the issue2pr run that stopped mid-round"
- "start a fresh round on the same branch and PR"
- "run these three issues serially, advancing on merge"

## Does Not Trigger On
- "review this design proposal until it converges"          (refine-proposal's job — skills/refine-proposal/SKILL.md)
- "summarize the issue2pr runs from this month"             (runs-stats' job — skills/runs-stats/SKILL.md)
- "take this findings report and drive a fix-verify loop"   (fix's job — commands/fix.md)
- "delegate this plan to Codex for implementation"          (delegate's job — commands/delegate.md)

## Frontmatter Valid
- `name` equal to `issue2pr`
- `description` present, naming the nine-step, three-phase pipeline
- `description` names the profile as the source of every project-bound fact
- `description` trigger-style — "Use when an issue should become a reviewed PR"

## Output Contains
- the refusal line `issue2pr: no profile resolved.` when no profile resolves
- a run `state.json` carrying `"schema_version": 2`
- a per-step `job.json` written after every reviewer dispatch, whatever its status
- the terminal state `EXIT_MAX_ROUNDS` when the cap is reached with a `major` still open
- the resumable `quota_paused` status when the reviewer did not answer
- the closure-record heading `## Direct read of enumerated lists`
- the closure-record heading `## Decision↔consequence sweep`
- a reviewed pull request and no merge — the pipeline does not merge
