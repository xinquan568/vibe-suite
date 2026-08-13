# NLPM Audit: diet103/claude-code-infrastructure-showcase
**Date**: 2026-04-13  |  **Artifacts**: 22  |  **Strategy**: batched
**NL Score**: 81/100
**Security**: BLOCKED
**Bugs**: 1  |  **Quality Issues**: 24  |  **Security Findings**: 6

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `.claude/agents/README.md` | doc | 20/100 | No frontmatter at all — not registerable as an agent |
| `.claude/agents/auto-error-resolver.md` | agent | 68/100 | No model, no examples in frontmatter, no output format section |
| `.claude/commands/dev-docs.md` | command | 75/100 | No allowed-tools, no empty-input guard |
| `.claude/agents/frontend-error-fixer.md` | agent | 75/100 | No model declared, no output format section |
| `.claude/agents/documentation-architect.md` | agent | 80/100 | Vague language at cap (-20): "comprehensive" ×5, "appropriate" ×2 |
| `.claude/agents/code-architecture-reviewer.md` | agent | 82/100 | Heavy vague language (-18): "comprehensive" ×3, "appropriate" ×3 |
| `.claude/agents/web-research-specialist.md` | agent | 82/100 | Heavy vague language (-18): "relevant" ×3, "thorough" ×2 |
| `.claude/agents/refactor-planner.md` | agent | 83/100 | No model declared (-5), vague language (-12) |
| `.claude/agents/auth-route-debugger.md` | agent | 83/100 | No model declared (-5), vague language (-12) |
| `.claude/commands/dev-docs-update.md` | command | 83/100 | No allowed-tools (-5), vague language (-12) |
| `.claude/skills/skill-developer/SKILL.md` | skill | 84/100 | Vague language (-16): "appropriate" ×3, "critical" ×2 |
| `.claude/agents/code-refactor-master.md` | agent | 88/100 | Vague language (-12): "comprehensive" ×2, "proper" ×2 |
| `.claude/agents/plan-reviewer.md` | agent | 88/100 | Vague language (-12): "thorough" ×2, "comprehensive" ×2 |
| `.claude/skills/backend-dev-guidelines/SKILL.md` | skill | 88/100 | Vague language (-12): "comprehensive" ×2, "proper" ×2 |
| `.claude/skills/error-tracking/SKILL.md` | skill | 90/100 | Vague language (-10): "appropriate" ×3 |
| `.claude/agents/auth-route-tester.md` | agent | 90/100 | Vague language (-10): "proper" ×2, "best practices" ×1 |
| `.claude/skills/frontend-dev-guidelines/SKILL.md` | skill | 92/100 | Vague language (-8): "appropriate" ×2 |
| `.claude/commands/route-research-for-testing.md` | command | 95/100 | BUG: `Task` tool called in step 3 but absent from `allowed-tools` |
| `.claude/skills/route-tester/SKILL.md` | skill | 94/100 | Vague language (-6): "proper" ×3 |
| `.claude/hooks/package.json` | config | N/A | Infrastructure file — no NL requirements |
| `.claude/hooks/tsconfig.json` | config | N/A | Infrastructure file — no NL requirements |
| `.claude/hooks/package-lock.json` | config | N/A | Infrastructure file — no NL requirements |

*NL Score 81/100 = mean of 19 scored NL artifacts (config files excluded)*

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 0 |
| Medium | 2 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Shell hook scripts | `.claude/hooks/error-handling-reminder.sh`, `.claude/hooks/post-tool-use-tracker.sh`, `.claude/hooks/trigger-build-resolver.sh`, `.claude/hooks/skill-activation-prompt.sh`, `.claude/hooks/tsc-check.sh`, `.claude/hooks/stop-build-check-enhanced.sh` |
| TypeScript hook scripts | `.claude/hooks/skill-activation-prompt.ts`, `.claude/hooks/error-handling-reminder.ts` |
| Package manifests | `.claude/hooks/package.json`, `.claude/hooks/package-lock.json` |
| MCP configs | None found |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | CRITICAL | `.claude/hooks/tsc-check.sh` | 79 | `eval` with variable | `eval "$tsc_cmd"` executes content read from a user-writable cache file (`~/.claude/tsc-cache/{session_id}/{repo}-tsc-cmd.cache`). If session_id is attacker-controlled or the cache directory is poisoned, this leads to arbitrary code execution. |
| 2 | CRITICAL | `.claude/hooks/stop-build-check-enhanced.sh` | 54 | `eval` with variable | `eval "$tsc_cmd"` executes content read from `$cache_dir/commands.txt` (a project-local cache file written by `post-tool-use-tracker.sh`). Malicious content injected into this file executes with full shell privileges. |
| 3 | MEDIUM | `.claude/hooks/trigger-build-resolver.sh` | 5–6 | File write outside repo | Writes hook debug output (including raw stdin data) to `/tmp/claude-hook-debug.log`. Sensitive hook input (file paths, session IDs) is disclosed to the shared `/tmp` directory. |
| 4 | MEDIUM | `.claude/hooks/trigger-build-resolver.sh` | 66 | Unquoted variable in shell command | `claude chat "Use the build-error-resolver agent to build and fix errors in: ${services_list}"` — unquoted variable interpolation into a shell command string. Low exploitability given hardcoded source array, but dangerous pattern for future code changes. |
| 5 | LOW | `.claude/hooks/tsc-check.sh` | 8–9 | Path traversal via unvalidated input | `SESSION_ID="${session_id:-default}"` is read directly from JSON stdin without sanitization, then used to construct `CACHE_DIR="$HOME/.claude/tsc-cache/$SESSION_ID"`. A `session_id` containing `../../` could escape the intended cache directory. |
| 6 | LOW | `.claude/skills/route-tester/SKILL.md` | 162–167 | Hardcoded credentials in examples | Test credentials visible in skill documentation: `username: testuser`, `password: testpassword`, MySQL root password `password1`. Intended as dev-only examples but should use placeholders. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `.claude/commands/route-research-for-testing.md` | Step 3 instructs Claude to call the `Task` tool, but `Task` is absent from the `allowed-tools` frontmatter (only Bash sub-commands are listed). | Command cannot complete its primary objective — the route-testing sub-agent is never launched. Runtime failure on every invocation. |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `.claude/hooks/trigger-build-resolver.sh` | Writes raw hook stdin to `/tmp/claude-hook-debug.log` | Remove the `/tmp` debug log entirely or gate it behind `DEBUG=1` env var: `if [ -n "$CLAUDE_HOOK_DEBUG" ]; then ... >> /tmp/...; fi` |
| 2 | `.claude/hooks/trigger-build-resolver.sh` | Unquoted `${services_list}` interpolated into `claude chat "..."` | Quote the variable and validate it matches expected pattern: `claude chat "Fix errors in: $(printf '%s' "${services_list}" | tr -cd 'a-zA-Z0-9, ')"` |
| 3 | `.claude/hooks/tsc-check.sh` | `SESSION_ID` from JSON stdin used unvalidated in path construction | Sanitize before use: `SESSION_ID="$(printf '%s' "${session_id:-default}" | tr -cd 'a-zA-Z0-9_-')"` |
| 4 | `.claude/skills/route-tester/SKILL.md` | Hardcoded credentials (`testuser`/`testpassword`/`password1`) in documentation | Replace with `<username>`, `<password>`, `<db-password>` placeholders and add a note: "Replace with your dev environment credentials." |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `agents/README.md` | No YAML frontmatter — not registerable as Claude Code agent | -50 (name + desc) |
| 2 | `agents/README.md` | No model, no output format, no example blocks | -30 |
| 3 | `auto-error-resolver.md` | `description` is a bare 5-word string with zero example blocks | -15 |
| 4 | `auto-error-resolver.md` | No `model` declared | -5 |
| 5 | `auto-error-resolver.md` | No output format section | -10 |
| 6 | `frontend-error-fixer.md` | No `model` declared | -5 |
| 7 | `frontend-error-fixer.md` | No structured output format section | -10 |
| 8 | `refactor-planner.md` | No `model` declared | -5 |
| 9 | `auth-route-debugger.md` | No `model` declared | -5 |
| 10 | `dev-docs.md` | No `allowed-tools` in frontmatter | -5 |
| 11 | `dev-docs.md` | No empty-input guard for `$ARGUMENTS` | -10 |
| 12 | `dev-docs-update.md` | No `allowed-tools` in frontmatter | -5 |
| 13 | `documentation-architect.md` | Vague language: "comprehensive" ×5, "appropriate" ×2, "relevant" ×1, "thorough" ×1 (capped) | -20 |
| 14 | `code-architecture-reviewer.md` | Vague language: "comprehensive" ×3, "appropriate" ×3, "proper" ×2 | -18 |
| 15 | `web-research-specialist.md` | Vague language: "comprehensive" ×3, "thorough" ×2, "relevant" ×3 | -18 |
| 16 | `skill-developer/SKILL.md` | Vague language: "appropriate" ×3, "critical" ×2, "comprehensive" ×2, "relevant" ×1 | -16 |
| 17 | `auth-route-tester.md` | Placeholder text "your project" in skill description and body not customized | quality note |
| 18 | `auth-route-debugger.md` | Placeholder text "your project application" in description not customized | quality note |
| 19 | `route-tester/SKILL.md` | Placeholder text "your project" appears 5+ times — skill not adapted from template | quality note |
| 20 | `error-tracking/SKILL.md` | Placeholder text "your project" appears throughout; references `/dev/active/email-sentry-integration/` (project-specific path) | quality note |
| 21 | `documentation-architect.md` | `model: inherit` is non-standard; most agents use an explicit model tier | quality note |
| 22 | `route-research-for-testing.md` | `!cat "$CLAUDE_PROJECT_DIR/.claude/tsc-cache"/\*/edited-files.log` shell injection in template block — tsc-cache path relies on glob expansion; fragile on empty or multi-match | quality note |
| 23 | `backend-dev-guidelines/SKILL.md` | References 11 resource sub-files not audited — unclear if all exist | quality note |
| 24 | `skill-developer/SKILL.md` | References 6 reference sub-files (TRIGGER_TYPES.md etc.) not audited | quality note |

## Cross-Component
**Broken references:**
- `route-research-for-testing.md` → `auth-route-tester` agent (via Task tool): command invokes the agent but Task is not in `allowed-tools`, breaking the pipeline at runtime.
- `skill-developer/SKILL.md` references `TRIGGER_TYPES.md`, `SKILL_RULES_REFERENCE.md`, `HOOK_MECHANISMS.md`, `TROUBLESHOOTING.md`, `PATTERNS_LIBRARY.md`, `ADVANCED.md` — these files exist in the repo but were not in the audit scope; references appear structurally sound.

**Security chain risk:**
- `auto-error-resolver.md` reads from `~/.claude/tsc-cache/[session_id]/last-errors.txt` — the same cache directory poisonable via the CRITICAL `eval` vulnerabilities in `tsc-check.sh` and `stop-build-check-enhanced.sh`. A compromise of the hook layer cascades into the agent layer.

**Orphaned component:**
- `agents/README.md` is a documentation-only file with no frontmatter. It will not be registered by Claude Code but sits alongside valid agent definitions, potentially causing user confusion.

**Placeholder contamination:**
- `route-tester/SKILL.md`, `error-tracking/SKILL.md`, `auth-route-debugger.md`, and `auth-route-tester.md` all contain `your project` placeholder text (referring to a project named "your project" literally). These were copied from a template and not fully customized, reducing their usefulness to consumers of this showcase.

## Recommendation

**BLOCKED — do not submit PRs. File private security report.**

Two CRITICAL `eval`-with-variable vulnerabilities exist in `.claude/hooks/tsc-check.sh` (line 79) and `.claude/hooks/stop-build-check-enhanced.sh` (line 54). In the Claude Code hook context these represent genuine arbitrary-code-execution risks: any process that can write to the tsc-cache directory (including Claude itself, via a prompt-injection attack) could inject a command that gets `eval`'d during the next file-edit cycle. These must be resolved — replacing `eval` with a safe allow-list of known TSC command patterns — before any contribution workflow is opened.

After the security issues are resolved, the single PR-worthy NL bug (`route-research-for-testing.md` missing `Task` in `allowed-tools`) plus the four Medium/Low security fixes are appropriate contributions.
