# NLPM Audit: mem0ai/mem0
**Date**: 2026-04-06  |  **Artifacts**: 11  |  **Strategy**: single
**NL Score**: 91/100
**Security**: REVIEW
**Bugs**: 1  |  **Quality Issues**: 8  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| openclaw/skills/memory-triage/SKILL.md | skill | 82 | Vague quantifiers (×7, −14); duplicate example headings |
| skills/mem0-integrate/SKILL.md | skill | 88 | Complex pipeline; vague quantifiers (×4, −8); minor structure gaps |
| skills/mem0/SKILL.md | skill | 90 | Cross-component name collision with plugin-bundled copy (v3.0.0 vs v0.1.1) |
| mem0-plugin/skills/mem0-mcp/SKILL.md | skill | 92 | Vague quantifiers: "appropriate", "significant", "relevant" (×3, −6) |
| skills/mem0-test-integration/SKILL.md | skill | 91 | Minor vague quantifiers; otherwise clean pipeline skill |
| mem0-plugin/hooks/hooks.json | hook config | 91 | Valid structure; `TaskCompleted` event support should be confirmed |
| skills/mem0-cli/SKILL.md | skill | 92 | Minor vague: "common", "deeper" (−4) |
| mem0-plugin/skills/mem0/SKILL.md | skill | 93 | Version out of sync with standalone (v0.1.1 vs v3.0.0); GitHub-URL refs vs. local |
| openclaw/skills/memory-dream/SKILL.md | skill | 93 | Vague quantifiers (×2, −4); auto-trigger claim lacks backing hook |
| skills/mem0-vercel-ai-sdk/SKILL.md | skill | 94 | Minimal vague; "common" in edge cases section (−2) |
| mem0-plugin/.claude-plugin/plugin.json | plugin manifest | 96 | None significant |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 4 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks (JSON config) | `mem0-plugin/hooks/hooks.json`, `mem0-plugin/hooks/cursor-hooks.json`, `mem0-plugin/hooks/codex-hooks.json` |
| Hook scripts (.sh) | `on_session_start.sh`, `on_user_prompt.sh`, `on_stop.sh`, `on_stop_codex.sh`, `on_pre_compact.sh`, `on_task_completed.sh`, `block_memory_write.sh`, `_identity.sh` |
| Hook scripts (.py) | `capture_compact_summary.py`, `on_pre_compact.py`, `_identity.py`, `setup_coding_categories.py`, `install_codex_hooks.py` |
| Migration script | `scripts/oss-to-platform-migrate.sh` (shell wrapper + inline Python) |
| Doc search script | `mem0-plugin/skills/mem0/scripts/mem0_doc_search.py`, `skills/mem0/scripts/mem0_doc_search.py` |
| MCP config | `mem0-plugin/.mcp.json` |
| Package manifests | `mem0-ts/package.json`, `openclaw/package.json` (no postinstall scripts) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | medium | scripts/oss-to-platform-migrate.sh | 31 | SEC-hardcoded-analytics-key | PostHog project capture key hardcoded in migration script; public analytics key, not a secret, but indicates undisclosed telemetry dependency |
| 2 | medium | scripts/oss-to-platform-migrate.sh | 240–288 | SEC-undisclosed-telemetry | Migration script sends authenticated user email + OS info + Python version to PostHog (`us.i.posthog.com`) without UX disclosure; opt-out via `MEM0_TELEMETRY=false` exists but is not mentioned in script output or help text |
| 3 | medium | mem0-plugin/scripts/capture_compact_summary.py | 122 | SEC-network-call-in-hook | HTTP POST to `api.mem0.ai/v1/memories/` from `SessionStart` hook, sending session transcript content and API key; intended plugin behavior but transmits conversation data outbound |
| 4 | medium | mem0-plugin/scripts/on_pre_compact.py | 196 | SEC-network-call-in-hook | HTTP POST to `api.mem0.ai/v1/memories/` from `Stop`/`PreCompact` hooks, sending parsed transcript and API key in background; same category as finding 3 |
| 5 | low | mem0-plugin/.mcp.json | 7 | SEC-api-key-in-header | `Authorization: Token ${MEM0_API_KEY}` in MCP server config template; standard MCP auth pattern, but makes the key's use surface explicit |

**Pre-scan false positives (noted for record):**
- `scripts/oss-to-platform-migrate.sh` line 9 (`exec python3 - "$@" <<'PY'`): static inline Python heredoc, not dynamic code construction — **false positive** for eval/exec patterns.
- `urllib.request.urlopen` in hook scripts: matched "credential exfiltration" pattern; these are the plugin's designed API calls to the user's own mem0 account — **false positive** for that pattern specifically.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | mem0-plugin/skills/mem0/SKILL.md | Declares `name: mem0` (version 0.1.1), identical to `skills/mem0/SKILL.md` (version 3.0.0); two skills with the same name exist in the same repository | When both skill paths are on the load path, the skill loader cannot distinguish them by name — one silently shadows the other, causing stale v0.1.1 content to be served instead of the current v3.0.0 |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/oss-to-platform-migrate.sh | PostHog telemetry sends authenticated email and OS data without disclosing this to the user during the migration flow | Add a brief disclosure line in `print_info()` before `capture_migration_event("oss.migrate.started", ...)` noting that anonymous telemetry is collected and can be disabled with `MEM0_TELEMETRY=false` |
| 2 | scripts/oss-to-platform-migrate.sh | Hardcoded PostHog project key at line 31 | Move to a named constant with a comment explaining it is a public analytics capture key (not a secret); add to the project's documented configuration surface |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | openclaw/skills/memory-triage/SKILL.md | Vague quantifiers: "relevant" (×2), "significant" (×2), "important" (×2), "genuinely" (×3), "notable" (×1), "comprehensive" (×1) — 11 distinct vague instances before cap | −20 (cap) |
| 2 | openclaw/skills/memory-triage/SKILL.md | Duplicate example headings: "Example 11" appears twice (mixed-categories and consolidation) and "Example 12" appears twice (generic greeting); makes numbered examples unreliable for cross-reference | −4 |
| 3 | openclaw/skills/memory-dream/SKILL.md | Description says "Also triggers automatically after sufficient activity (configurable)" but no hook in `mem0-plugin/hooks/hooks.json` invokes this skill; the auto-trigger is unimplemented | −5 (misleading description) |
| 4 | openclaw/skills/memory-dream/SKILL.md | Vague quantifiers: "sufficient" (description line), "obvious" (Phase 1 step 4) | −4 |
| 5 | mem0-plugin/skills/mem0/SKILL.md | Plugin-bundled version 0.1.1 is significantly older than standalone version 3.0.0; content diverges (GitHub URL references vs. local paths) with no documented sync mechanism | −3 |
| 6 | mem0-plugin/skills/mem0-mcp/SKILL.md | Vague quantifiers: "appropriate" (line 51), "significant" (line 61 resumed session), and multiple uses of "relevant" | −6 |
| 7 | skills/mem0-integrate/SKILL.md | Vague quantifiers: "relevant" (×2), "plausible" (plan section), "non-trivial" (description); complex skill would benefit from tightening these | −8 |
| 8 | skills/mem0/SKILL.md | Cross-component note: same `name: mem0` as plugin-bundled copy; if not addressed, both copies will conflict on load — quality flag until Bug #1 is resolved | −6 |

## Cross-Component
**Skill name collision (confirmed):** `mem0-plugin/skills/mem0/SKILL.md` declares `name: mem0` at metadata version 0.1.1; `skills/mem0/SKILL.md` also declares `name: mem0` at version 3.0.0. Both files coexist in the same repository. Skill loaders that deduplicate by `name` will silently serve whichever is loaded last, making the effective version non-deterministic. The fix is to either rename the plugin-bundled copy (e.g., `name: mem0-plugin-bundled`) or establish the plugin-bundled copy as the authoritative source and remove the top-level duplicate.

**Version drift (related):** The two `mem0` skill copies have diverged in content — the plugin-bundled copy uses GitHub raw URL cross-references (`https://github.com/mem0ai/mem0/tree/main/skills/...`) while the standalone uses local relative paths (`../mem0-cli/SKILL.md`). There is no documented sync procedure. As the API evolves, the plugin-bundled copy will fall further behind.

**Auto-trigger claim without hook backing:** `openclaw/skills/memory-dream/SKILL.md` promises automatic invocation after "sufficient activity (configurable)" but `mem0-plugin/hooks/hooks.json` has no hook that triggers this skill. The Stop, TaskCompleted, and PreCompact hooks inject text prompting Claude to use MCP tools directly — they do not invoke the memory-dream skill. Either the claim should be removed from the description, or a hook should be added to back it.

**Internal references are valid:** `${CLAUDE_SKILL_DIR}/scripts/mem0_doc_search.py` is referenced in both `mem0-plugin/skills/mem0/SKILL.md` and `skills/mem0/SKILL.md`; both corresponding script files exist (`mem0-plugin/skills/mem0/scripts/mem0_doc_search.py` and `skills/mem0/scripts/mem0_doc_search.py`). No broken path references.

## Recommendation
REVIEW — submit NL fix PRs for Bug #1 (skill name collision) and the security fixes for the undisclosed PostHog telemetry (Medium findings). Quality issues in `memory-triage` and `memory-dream` are informational but worth a follow-up PR. No Critical or High security findings block contribution.
