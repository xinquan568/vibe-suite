# NLPM Audit: ZeframLou/call-me
**Date**: 2026-04-06  |  **Artifacts**: 3  |  **Strategy**: single
**NL Score**: 80/100
**Security**: CLEAR
**Bugs**: 2  |  **Quality Issues**: 5  |  **Security Findings**: 4

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `skills/phone-input/SKILL.md` | Skill | 46/100 | Missing YAML frontmatter (name + description) |
| `hooks/hooks.json` | Hook | 94/100 | R01 vague quantifiers ("significant", "genuinely", "Trivial") |
| `.claude-plugin/plugin.json` | Plugin manifest | 100/100 | — |

**Weighted average**: (46 + 94 + 100) / 3 = **80/100**

Scoring notes:
- `SKILL.md`: −25 missing `name` frontmatter, −25 missing `description` frontmatter, −4 for two R01 vague words → 46/100
- `hooks/hooks.json`: −6 for three R01 vague words on line 8 → 94/100
- `plugin.json`: JSON manifest; no applicable NL penalties → 100/100

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | `hooks/hooks.json` (1 prompt-type hook) |
| Scripts | None |
| MCP configs | Defined in `.claude-plugin/plugin.json` (`mcpServers.callme`) |
| Package manifests | `server/package.json` |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | `server/package.json` | 8 | runtime-autoinstall | `prestart` script runs `bun install --silent` on every server start, fetching remote packages from the registry each invocation; combined with `^`-pinned deps, the installed set can drift between starts |
| 2 | Medium | `server/package.json` | 14 | network-tunnel | `@ngrok/ngrok` creates an outbound public tunnel to the internet; this is intentional for Twilio webhook delivery but means every server start opens an externally reachable endpoint |
| 3 | Low | `server/package.json` | 20 | unpinned-semver | `bun-types` pinned to `"latest"` — no semver range at all; will resolve to whatever bun-types version is current at install time |
| 4 | Low | `server/package.json` | 13–17 | unpinned-semver | Four runtime dependencies (`@modelcontextprotocol/sdk`, `@ngrok/ngrok`, `openai`, `ws`) use `^` ranges; minor/patch upgrades are pulled automatically on each `bun install` |

No `command`-type hooks found. The single `Stop` hook uses `"type": "prompt"` — no shell execution surface. No `.mcp.json`, no `scripts/` directory, no Python/JS scripts outside the MCP server. No hardcoded credentials in any file.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `skills/phone-input/SKILL.md` | Missing YAML frontmatter `name` field | Without machine-readable `name`, the Claude Code skill loader cannot reliably index this skill; discovery and `[[skill-ref]]` cross-linking will fail |
| 2 | `skills/phone-input/SKILL.md` | Missing YAML frontmatter `description` field | Without `description`, the skill cannot surface in `/help` or be matched by trigger-phrase resolution |

Both bugs are fixed by adding a frontmatter block at the top of the file:

```yaml
---
name: phone-input
description: "Call the user for real-time voice input, status reporting, or blocked-task clarification via Twilio phone calls."
---
```

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `server/package.json` | `prestart: "bun install --silent"` auto-installs on every start | Move to a one-time install step in the plugin's setup docs; remove `prestart` and rely on the user running `bun install` once after cloning |
| 2 | `server/package.json` | `bun-types: "latest"` unpinned | Replace `"latest"` with a concrete version range, e.g. `"^1.1.38"` |
| 3 | `server/package.json` | `^` semver ranges on four runtime deps | Pin to exact versions (e.g. `"1.0.4"`) or at minimum document which version was last tested; the ngrok tunnel dependency is especially sensitive to minor-version behavior changes |

Note: The ngrok finding (finding #2) is by design — the plugin requires a public URL for Twilio webhooks. No fix needed for the architectural choice; the low/medium flags are for disclosure completeness only.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `hooks/hooks.json` | R01: "significant work" — no measurable threshold | −2 |
| 2 | `hooks/hooks.json` | R01: "genuinely blocked" — no definition of "genuine" blockage vs. ordinary uncertainty | −2 |
| 3 | `hooks/hooks.json` | R01: "Trivial tasks" — "trivial" is in the eye of the beholder; reading files is given as the only example | −2 |
| 4 | `skills/phone-input/SKILL.md` | R01: "completed a significant task" (line 9) — no size/scope criterion | −2 |
| 5 | `skills/phone-input/SKILL.md` | R01: "complex decisions" (line 12) — no definition of complexity threshold | −2 |

Suggested rewrites for hooks.json prompt:
- "significant work" → "wrote or modified at least one file, or executed a command with observable side-effects"
- "genuinely blocked" → "cannot proceed without a decision the user must make (e.g., choosing between two implementation approaches)"
- "Trivial tasks" → "read-only tasks (file reads, searches, status checks)"

## Cross-Component
**Skills path resolution**: `plugin.json` is at `.claude-plugin/plugin.json` with `"skills": "./skills"`. If paths resolve relative to the `.claude-plugin/` subdirectory, this would point to `.claude-plugin/skills/` (which does not exist); actual skills live at `skills/` at the repo root. In practice, Claude Code appears to resolve plugin-relative paths from the repo root (the NLPM plugin uses the same pattern), so this is likely benign — but worth confirming against Claude Code plugin loader documentation.

**Hook ↔ Skill consistency**: `hooks/hooks.json` references `initiate_call` by name in its reason string. The tool is defined by the MCP server and documented in `skills/phone-input/SKILL.md`. Reference is consistent.

**MCP server ↔ Skill consistency**: `SKILL.md` documents four tools (`initiate_call`, `continue_call`, `speak_to_user`, `end_call`). These must all be exposed by `server/src/index.ts`. Not verified (server source not in scope), but naming is internally consistent.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

Priority order:
1. **Bug PR**: Add YAML frontmatter to `skills/phone-input/SKILL.md` (two missing fields, one-line fix each).
2. **Security PR**: Remove `prestart` auto-install and pin `bun-types` to a concrete version.
3. **Quality PR**: Tighten the three vague quantifiers in the `hooks/hooks.json` prompt (optional but improves hook reliability).
