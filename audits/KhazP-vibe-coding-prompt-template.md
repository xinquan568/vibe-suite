# NLPM Audit: KhazP/vibe-coding-prompt-template
**Date**: 2026-04-29  |  **Artifacts**: 7  |  **Strategy**: single
**NL Score**: 80/100
**Security**: BLOCKED
**Bugs**: 2  |  **Quality Issues**: 13  |  **Security Findings**: 2

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `.claude/skills/vibe-workflow/SKILL.md` | skill | 75 | Missing `allowed-tools`; no example blocks |
| `.claude/skills/vibe-build/SKILL.md` | skill | 78 | Missing `allowed-tools`; vague quantifiers |
| `.claude/skills/vibe-agents/SKILL.md` | skill | 80 | No model declared; no example blocks |
| `.claude/skills/vibe-prd/SKILL.md` | skill | 80 | No model declared; no example blocks |
| `.claude/skills/vibe-research/SKILL.md` | skill | 80 | No model declared; no example blocks |
| `.claude/skills/vibe-techdesign/SKILL.md` | skill | 80 | No model declared; no example blocks |
| `.claude/hooks/hooks.json` | hook-config | 90 | No NL penalties; HIGH security finding in scan |

**Score calculation (unweighted mean):** (75+78+80+80+80+80+90)/7 = 80.4 → **80/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 |
| Medium | 1 |
| Low | 0 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | `.claude/hooks/hooks.json` |
| Scripts | None |
| MCP Configs | None |
| Package Manifests | None |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | HIGH | `.claude/hooks/hooks.json` | 31 | SEC-shell-injection | PostToolUse hook builds `execSync` shell command by string-concatenating `tool_input.file_path` without sanitization; a filename containing shell metacharacters (e.g. `foo.ts"; rm -rf .`) executes arbitrary commands |
| 2 | MEDIUM | `.claude/hooks/hooks.json` | 55 | SEC-shell-injection | Notification hook concatenates `d.message` directly into `osascript`/`notify-send`/PowerShell invocations; a crafted message string can break out of the quoted context and inject shell commands |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `.claude/skills/vibe-build/SKILL.md` | Missing `allowed-tools` frontmatter field | Skill instructs Claude to read `AGENTS.md`, edit/write agent_docs files, and run `npm`/`git` Bash commands, but declares no tools; runtime may silently block execution or prompt unexpectedly |
| 2 | `.claude/skills/vibe-workflow/SKILL.md` | Missing `allowed-tools` frontmatter field | Orchestrator's Step 1 instructs Claude to read `docs/research-*.md`, `docs/PRD-*.md`, `docs/TechDesign-*.md`, and `AGENTS.md` to assess project state, but no `Read`/`Glob` tools are declared |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `.claude/hooks/hooks.json` | MEDIUM (finding #2): `d.message` concatenated into shell commands in Notification hook | Sanitize `msg` by stripping or escaping shell metacharacters before interpolation, or restructure to pass arguments as an array (e.g. `execFile('osascript', ['-e', 'display notification "' + sanitized + '"'])`) to avoid shell interpretation entirely |

*Finding #1 (HIGH) requires private disclosure — do not submit a public PR for it.*

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `.claude/skills/vibe-agents/SKILL.md` | No `model` field declared in frontmatter | −5 |
| 2 | `.claude/skills/vibe-agents/SKILL.md` | No example invocation blocks (zero input→output examples) | −15 |
| 3 | `.claude/skills/vibe-build/SKILL.md` | No `model` field declared in frontmatter | −5 |
| 4 | `.claude/skills/vibe-build/SKILL.md` | Only one example block (Good/Avoid communication style); insufficient for invocation coverage | −5 |
| 5 | `.claude/skills/vibe-build/SKILL.md` | Vague quantifiers: "relevant" (line 29), "brief" (line 41), "minimal" (line 63) | −6 |
| 6 | `.claude/skills/vibe-prd/SKILL.md` | No `model` field declared in frontmatter | −5 |
| 7 | `.claude/skills/vibe-prd/SKILL.md` | No example invocation blocks (zero input→output examples) | −15 |
| 8 | `.claude/skills/vibe-research/SKILL.md` | No `model` field declared in frontmatter | −5 |
| 9 | `.claude/skills/vibe-research/SKILL.md` | No example invocation blocks (zero input→output examples) | −15 |
| 10 | `.claude/skills/vibe-techdesign/SKILL.md` | No `model` field declared in frontmatter | −5 |
| 11 | `.claude/skills/vibe-techdesign/SKILL.md` | No example invocation blocks (zero input→output examples) | −15 |
| 12 | `.claude/skills/vibe-workflow/SKILL.md` | No `model` field declared in frontmatter | −5 |
| 13 | `.claude/skills/vibe-workflow/SKILL.md` | No example invocation blocks (zero input→output examples) | −15 |

## Cross-Component
All inter-skill references resolve correctly and form a consistent 5-step chain:

- `vibe-research` completion → `/vibe-prd` ✓
- `vibe-prd` completion → `/vibe-techdesign` ✓
- `vibe-techdesign` completion → `/vibe-agents` ✓
- `vibe-agents` completion → `/vibe-build` ✓
- `vibe-workflow` references all five sub-skills in its Quick Commands table ✓
- `vibe-build` references `/vibe-agents` as prerequisite ✓

No orphaned components, no stale counts, no terminology drift detected.

**Note:** `vibe-workflow` also relies on `Glob`/`Read` to locate `docs/` files in Step 1, which is consistent with the BUG-missing-allowed-tools finding above — cross-component and bug findings agree.

## Recommendation
BLOCKED — do not submit PRs. File a private security report for the HIGH-severity command injection in `.claude/hooks/hooks.json` line 31 (unsanitized `file_path` in `execSync`). Once that is resolved, the two missing `allowed-tools` bugs (vibe-build, vibe-workflow) are single-line frontmatter additions that are suitable for a public PR. The 13 quality items (model declarations on all six skills, example blocks on five skills, and three vague quantifiers in vibe-build) can be addressed in a follow-up cleanup PR after the security fix lands.
