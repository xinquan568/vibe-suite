---
artifact: skills/refine-proposal/SKILL.md
type: skill
min_score: 80
---

# refine-proposal — suite spec (vibe-229 / M35)

Source: `skills/refine-proposal/SKILL.md` as shipped. This spec restates what the skill
already documents — its description, invocation, loop, folder layout and state — as a test;
it adds no invented expectations.

## Triggers On
- "run this design proposal through independent review rounds until it converges"
- "this plan needs adversarial review, not just editing"
- "refine this proposal and deliver it bilingually, English plus Chinese"
- "/vibe-suite:refine-proposal --file docs/plan.md"
- "iterate on the existing proposal run with new feedback"
- "resume the interrupted proposal review run"

## Does Not Trigger On
- "turn GitHub issue #42 into a reviewed pull request"      (issue2pr's job — skills/issue2pr/SKILL.md)
- "review this pull request's code for security defects"   (the security reviewer's job — agents/security.md)
- "hand this approved plan to Codex to implement"           (delegate's job — commands/delegate.md)
- "fix the findings from this nl-audit report"              (fix's job — commands/fix.md)

## Frontmatter Valid
- `name` equal to `refine-proposal`
- `description` present, naming the freeze, baseline, and review-and-revise rounds
- `description` trigger-style — "Use when a plan needs adversarial review"
- `description` excludes code review and first drafts

## Output Contains
- round bounds of floor 1, ceiling 5, default 3
- a baseline named `plan-i<N>.md`
- per review round a `review.md` and a `review.json`
- a run folder under `docs/discussion/<date>-<slug>/`
- a `state.json` at `schema_version` 6
- a self-contained `FINAL.html` with a metadata banner
- with `--second-language`, a `final-bilingual.md` with English first
