# PRIVACY — what vibe-suite does with your code and data

Every claim below is checked against this repository's code; `tests/test_doc_accuracy.py`
anchors the named surfaces. Last verified against the tree at the commit that ships this file.

## What runs locally

Everything, by default. Scoring, checking, structural validation (`bin/vibe-check`), the NL
test runner, trend and report rendering all read your files in-process and write only to your
project (reports, run folders, config sentinels, timelines). The report renderer is an
explicitly offline path — no network, vendored assets.

## What leaves your machine, and only when you invoke it

- **Cross-model lanes.** Commands that dispatch to an external engine pass
  repository-derived prompts — file contents, diffs, findings — to the engine you configured
  (Codex CLI today; an agy lane exists behind its gate). The dispatching surfaces:
  `delegate`, `continue`, `bug-analyze`, `roast --engine codex|agy|both`,
  `fix --engine …`, `nl-audit` (cross-model audit lane), `score`/`security-scan` second
  opinions where an engine flag is passed, the `refine-proposal` and `issue2pr` workflow
  skills (their reviewer legs), and the **Stop-time review hook** — opt-in at setup, but
  once enabled it dispatches automatically at session stops until disabled. `jobs` manages
  the background jobs those dispatches create; it sends no prompts itself. Those providers'
  own terms apply to what the lanes send. No lane runs unless you invoke it (or enabled the
  hook).
- **Preflight probes.** `/vibe-suite:preflight` contacts the configured engines to test
  connectivity and discover models.
- **Knowledge refresh.** `/vibe-suite:refresh-knowledge` fetches documentation via Context7.
- **Update path.** `/vibe-suite:update` runs `npx -y claude-octopus@<pinned version>` (an npm
  registry fetch on cold cache) and boot-verifies that reverse-MCP server with a local
  handshake; the pin is exact (`scripts/lib/claude-octopus-pin.txt`) and the handshake
  rejects a server whose self-report disagrees with it.
- **Advisors.** Registered advisors execute the same pinned `claude-octopus` package, which
  spawns Claude Code sessions on your machine; prompts you send an advisor go to the model
  behind your Claude Code authentication.

## Secrets

The suite ships no credentials and writes none into your project. The `bridge` command
mirrors MCP server NAMES into `.codex/config.toml` and never copies env values — variable
names cross, values do not. The auditor unit's three secrets — `CLAUDE_CODE_OAUTH_TOKEN`,
`PAT_TOKEN`, and optional `OPENAI_API_KEY` — exist only as GitHub Actions environment
secrets in the deployment repository, never in the plugin.

## The auditor unit (future)

The `auditor/` pipeline — discovering public repositories, auditing them, submitting PRs —
is S8 machinery and is NOT active in this plugin today; its tree ships documentation only.
When it deploys, it will operate in its own GitHub Actions environment with its own data
branch, not in your projects.

## Telemetry

None. The suite has no analytics, no beacons, and no data collection of its own; the only
network traffic is the disclosed operations above (engine dispatches you invoke, preflight
probes, Context7 fetches, the pinned npm fetch), and run artifacts stay in your own tree.
