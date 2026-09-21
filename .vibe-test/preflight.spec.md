---
artifact: commands/preflight.md
type: command
min_score: 80
---

# preflight — suite spec (vibe-229 / M35)

Source: `commands/preflight.md` as shipped. This spec restates what the artifact already documents —
the engine probes, the runtime rows, the `--json` flag and the exit codes — and invents nothing.
Every assertion below cites a line of the artifact (or, for a near-miss, of the command that owns
it).

## Triggers On
- "/vibe-suite:preflight"
- "/vibe-suite:preflight --json"
- "is the codex lane usable from here"
- "what models does codex offer right now"
- "is codex authenticated, and does an exec smoke pass"
- "check that python3, node and git are available for the suite"

## Does Not Trigger On
- "health-check my vibe-suite installation's bridge and symlinks"   (doctor's job — commands/doctor.md)
- "show the status of my codex jobs"                                (jobs's job — commands/jobs.md)
- "show my resolved engine defaults and gate toggles"               (config's job — commands/config.md)
- "re-run every bridge step without prompting"                      (repair's job — commands/repair.md)

## Frontmatter Valid
- `description` present, naming version, auth mode, exec smoke and dynamic discovery of the available models
- `description` naming the python3, node and git runtimes
- `argument-hint` offering `[--json]`
- `model` absent — no model id is named (P9)

## Output Contains
- auth reported as one of `chatgpt` · `api-key` · `not-authenticated` · `unknown`
- smoke reported as one of `ok` · `turn-failed` · `timeout` · `spawn-failed`
- models status `fresh` · `stale` · `missing` · `malformed` plus the discovered slugs
- runtime rows for `node` (18+) and `git`, beside `python3` (3.11+)
- runtime rows carrying `auth: null`, not `unknown`

## Handles Input
| Input | Expected Behavior |
|-------|-------------------|
| (empty) | runs `scripts/preflight-cli.mjs` and shows the operator the probe matrix |
| `--json` | the matrix as one JSON document, with `engines` and `runtimes` as sibling keys |
| any other argument | exit code `2` — usage; `--json` is the only accepted argument |
| every lane available and every runtime at its floor | exit code `0` |
| a probed lane or runtime unavailable, or a probe degraded | exit code `1`; the matrix still prints |
| `node` absent | cannot be reported by preflight; `/vibe-suite:doctor` carries that row |
