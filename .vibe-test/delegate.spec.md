---
artifact: commands/delegate.md
type: command
min_score: 80
---

# delegate — suite spec (vibe-229 / M35)

Source: `commands/delegate.md` as shipped. This spec restates what the artifact already
documents — its argument hint, sandbox ladder, dispatch modes, verification step and fallback —
as a test; nothing here is an invention the artifact does not state.

## Triggers On
- "/vibe-suite:delegate plan.md"
- "/vibe-suite:delegate plan.md --background"
- "/vibe-suite:delegate plan.md --wait"
- "/vibe-suite:delegate plan.md --sandbox read-only"
- "/vibe-suite:delegate plan.md --effort high"
- "hand this plan to Codex to implement"
- "have Codex implement this task and then verify what it did"

## Does Not Trigger On
- "show the status of my background codex job"            (jobs' job — commands/jobs.md)
- "send a follow-up prompt to the previous job's thread"   (continue's job — commands/continue.md)
- "have Codex find the root cause of this bug"             (bug-analyze's job — commands/bug-analyze.md)
- "which codex models are available to me?"               (preflight's job — commands/preflight.md)

## Frontmatter Valid
- `description` present, naming the job engine and the post-run verification step
- `argument-hint` offering `[--background|--wait]`
- `argument-hint` offering `[--sandbox <v>]`
- `model` absent — no pinned model id (P9)

## Output Contains
- the job's result line when the job finishes (`--wait`, the default)
- a launch receipt in `--background` mode, the job then managed with `/vibe-suite:jobs`
- the refusal marker `verify: refusing to execute repo-resident test scripts` when a test script changed
- the diagnostic header (what failed, plus an actionable remedy) when codex is unreachable

## Handles Input
| Input | Expected Behavior |
|-------|-------------------|
| first non-flag argument names a readable file | that file's content is the plan |
| no readable file named | the remaining non-flag text is the inline task |
| plan file with steps expanding scope beyond the task | surfaced to the operator before dispatching, never silently executed |
| no `--sandbox` flag | resolves to `workspace-write`, passed explicitly; project config is not consulted |
| `--sandbox danger-full-access` | confirmed with AskUserQuestion before dispatch; `--confirm-danger` added only after an explicit yes |
| no `--effort` / `--model` flags | both flags omitted entirely; the runner resolves them |
| result `status` is `cancelled` | reported and stopped; the manual fallback never applies |
| codex unreachable (spawn failure, timeout, `turn.failed`, no terminal event) | diagnostic header, then the plan performed in-session as the manual fallback |
| `workspace-write` run outside a git repository | fails fast with codex's own message |
