# NLPM Audit: team-attention/plugins-for-claude-natives
**Date**: 2026-04-06  |  **Artifacts**: 46  |  **Strategy**: batched
**NL Score**: 92/100
**Security**: CLEAR
**Bugs**: 3  |  **Quality Issues**: 28  |  **Security Findings**: 6

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| plugins/google-calendar/.claude-plugin/plugin.json | plugin.json | 70 | Missing author, repository, license fields |
| plugins/gmail/.claude-plugin/plugin.json | plugin.json | 70 | Missing author, repository, license fields |
| plugins/session-wrap/commands/wrap.md | command | 75 | Missing `name` frontmatter field |
| plugins/session-wrap/agents/followup-suggester.md | agent | 77 | Zero examples (-15), vague terms |
| plugins/session-wrap/agents/learning-extractor.md | agent | 77 | Zero examples (-15), vague terms |
| plugins/session-wrap/agents/duplicate-checker.md | agent | 77 | Zero examples (-15), vague terms |
| plugins/session-wrap/agents/doc-updater.md | agent | 79 | Zero examples (-15), vague terms |
| plugins/session-wrap/agents/automation-scout.md | agent | 79 | Zero examples (-15), vague terms |
| plugins/youtube-digest/.claude-plugin/plugin.json | plugin.json | 80 | Missing license, repository fields |
| .claude-plugin/plugin.json | plugin.json | 85 | Missing license, keywords |
| plugins/agent-council/SKILL.md | skill | 90 | Missing output format, stale duplicate |
| plugins/agent-council/skills/agent-council/SKILL.md | skill | 90 | Missing output format |
| plugins/agent-council/CLAUDE.md | CLAUDE.md | 90 | Brief; TodoWrite-only instruction omits context |
| plugins/interactive-review/CLAUDE.md | CLAUDE.md | 90 | Broken file path reference |
| plugins/say-summary/hooks/hooks.json | hook | 90 | Missing `matcher` field on Stop hook |
| plugins/gmail/skills/gmail/SKILL.md | skill | 91 | Incomplete output format for read operations |
| plugins/dev/agents/docs-researcher.md | agent | 94 | Minor vague terms |
| plugins/dev/agents/codebase-explorer.md | agent | 94 | Minor vague terms |
| plugins/doubt/.claude-plugin/plugin.json | plugin.json | 95 | Missing repository, license |
| plugins/doubt/hooks/hooks.json | hook | 95 | None significant |
| plugins/interactive-review/.claude-plugin/plugin.json | plugin.json | 95 | Minor: author URL absent |
| plugins/dev/CLAUDE.md | CLAUDE.md | 95 | None significant |
| plugins/dev/agents/decision-synthesizer.md | agent | 96 | Minor vague terms |
| plugins/dev/agents/tradeoff-analyzer.md | agent | 96 | Minor vague terms |
| plugins/session-wrap/skills/session-analyzer/SKILL.md | skill | 96 | Minor vague terms |
| plugins/clarify/skills/unknown/SKILL.md | skill | 96 | Minor vague terms |
| plugins/interactive-review/skills/review/SKILL.md | skill | 96 | Minor vague terms |
| plugins/podcast/skills/podcast/SKILL.md | skill | 96 | Minor vague terms |
| plugins/team-assemble/skills/team-assemble/SKILL.md | skill | 96 | Minor vague terms |
| plugins/dev/skills/dev-scan/SKILL.md | skill | 96 | Minor vague terms |
| plugins/dev/skills/tech-decision/SKILL.md | skill | 96 | Minor vague terms |
| plugins/session-wrap/skills/session-wrap/SKILL.md | skill | 98 | None significant |
| plugins/session-wrap/skills/history-insight/SKILL.md | skill | 98 | None significant |
| plugins/google-calendar/skills/google-calendar/SKILL.md | skill | 98 | None significant |
| plugins/clarify/skills/metamedium/SKILL.md | skill | 98 | None significant |
| plugins/clarify/skills/vague/SKILL.md | skill | 98 | None significant |
| plugins/kakaotalk/skills/kakaotalk/SKILL.md | skill | 98 | None significant |
| plugins/youtube-digest/skills/youtube-digest/SKILL.md | skill | 98 | None significant |
| plugins/session-wrap/.claude-plugin/plugin.json | plugin.json | 100 | None |
| plugins/agent-council/.claude-plugin/plugin.json | plugin.json | 100 | None |
| plugins/clarify/.claude-plugin/plugin.json | plugin.json | 100 | None |
| plugins/say-summary/.claude-plugin/plugin.json | plugin.json | 100 | None |
| plugins/kakaotalk/.claude-plugin/plugin.json | plugin.json | 100 | None |
| plugins/podcast/.claude-plugin/plugin.json | plugin.json | 100 | None |
| plugins/team-assemble/.claude-plugin/plugin.json | plugin.json | 100 | None |
| plugins/dev/.claude-plugin/plugin.json | plugin.json | 100 | None |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 4 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks (JSON configs) | `plugins/doubt/hooks/hooks.json`, `plugins/say-summary/hooks/hooks.json` |
| Hook scripts | `plugins/doubt/hooks/scripts/doubt-detector.sh`, `plugins/doubt/hooks/scripts/doubt-validator.sh` |
| Shell scripts | `council.sh`, `council-job.sh`, `setup.sh`, `extract-session.sh`, `find-session-files.sh`, `extract-subagent-calls.sh`, `extract-hook-events.sh`, `extract_metadata.sh`, `extract_transcript.sh` |
| Python scripts | `say-summary.py`, `setup_auth.py` (×2), `gmail_client.py`, `calendar_client.py`, `kakao_read.py`, `kakao_send.py`, `generate_tts.py`, `convert_mp4.py`, `upload_youtube.py`, and others |
| Node.js scripts | `council-job.js`, `council-job-worker.js` (×2 — both in root and nested skills/) |
| MCP configs | `plugins/interactive-review/.mcp.json` |
| Python requirements | `mcp>=1.0.0` (interactive-review), `claude-agent-sdk>=0.1.0` (say-summary) |
| Node.js package manifest | `plugins/agent-council/package.json` |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | `plugins/doubt/hooks/scripts/doubt-detector.sh` | 17 | Unvalidated input in file path | `session_id` extracted from untrusted JSON stdin is used directly in `STATE_FILE="$STATE_DIR/doubt-mode-$session_id"` without sanitization. A crafted `session_id` like `../../etc/cron.d/evil` could escape the state directory. |
| 2 | Medium | `plugins/doubt/hooks/scripts/doubt-validator.sh` | 17, 20 | Unvalidated input in file path + rm | Same `session_id` path issue as doubt-detector.sh, compounded by `rm -f "$STATE_FILE"` — a manipulated session_id could delete files outside `~/.claude/.hook-state/`. |
| 3 | Medium | `plugins/session-wrap/skills/history-insight/scripts/extract-session.sh` | 74 | User-controlled value injected into jq script string | `"$SESSION_FILE"` (shell arg) is interpolated into the jq program string: `'file: "'"$SESSION_FILE"'"'`. A filename with embedded `"` characters or jq syntax breaks the query or changes its semantics. |
| 4 | Medium | `plugins/say-summary/scripts/setup.sh` | 16 | Runtime package install, unpinned version | `pip3 install --user claude-agent-sdk` with no version pin. Package could be updated to a malicious version between installs; no hash verification. |
| 5 | Low | `plugins/interactive-review/mcp-server/requirements.txt` | 1 | Unpinned dependency | `mcp>=1.0.0` — any future `mcp` release satisfies the constraint, including potentially breaking or malicious versions. |
| 6 | Low | `plugins/say-summary/requirements.txt` | 1 | Unpinned dependency | `claude-agent-sdk>=0.1.0` — same concern as finding #5. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `plugins/interactive-review/CLAUDE.md` | Directory structure diagram shows `skills/review.md` but actual path is `skills/review/SKILL.md` | Developers following the diagram will look for a non-existent file; causes confusion during onboarding and contribution |
| 2 | `plugins/agent-council/SKILL.md` | Stale duplicate of `skills/agent-council/SKILL.md`. Root-level SKILL.md is not referenced by `plugin.json` (which correctly points to `./skills/agent-council`). No version or update discipline will keep them in sync. | Silent documentation drift — users reading the root-level file may follow outdated workflow |
| 3 | `plugins/say-summary/hooks/hooks.json` | Stop hook entry is missing the `matcher` field present in all other hooks in this repo. Absence is technically valid (implicit wildcard), but differs from the explicit `"matcher": "*"` pattern used by `doubt/hooks/hooks.json` and risks breakage if a future Claude Code schema enforces the field. | Minor registration inconsistency; easy to overlook in schema validation |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `plugins/doubt/hooks/scripts/doubt-detector.sh` | `session_id` used unsanitized in file path (line 17) | Add `session_id=$(echo "$session_id" \| tr -cd '[:alnum:]-')` after extraction to strip path characters before constructing `STATE_FILE` |
| 2 | `plugins/doubt/hooks/scripts/doubt-validator.sh` | Same path traversal + `rm -f` on tainted path (lines 17, 20) | Apply same sanitization as fix #1; additionally assert `STATE_FILE` stays within `$STATE_DIR` before calling `rm` |
| 3 | `plugins/session-wrap/skills/history-insight/scripts/extract-session.sh` | SESSION_FILE interpolated into jq source string (line 74) | Pass filename out-of-band via `--arg`: replace the inline string with `jq -c --arg f "$SESSION_FILE" '... \| {file: $f, ...}'` |
| 4 | `plugins/say-summary/scripts/setup.sh` | Unpinned `pip3 install claude-agent-sdk` | Pin to a specific version: `pip3 install --user claude-agent-sdk==<current-version>` and add a comment to update deliberately |
| 5 | `plugins/interactive-review/mcp-server/requirements.txt` | `mcp>=1.0.0` unpinned | Pin to `mcp==<tested-version>` |
| 6 | `plugins/say-summary/requirements.txt` | `claude-agent-sdk>=0.1.0` unpinned | Pin to `claude-agent-sdk==<tested-version>` |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `plugins/session-wrap/agents/followup-suggester.md` | Zero `<example>` blocks | -15 |
| 2 | `plugins/session-wrap/agents/doc-updater.md` | Zero `<example>` blocks | -15 |
| 3 | `plugins/session-wrap/agents/learning-extractor.md` | Zero `<example>` blocks | -15 |
| 4 | `plugins/session-wrap/agents/duplicate-checker.md` | Zero `<example>` blocks | -15 |
| 5 | `plugins/session-wrap/agents/automation-scout.md` | Zero `<example>` blocks | -15 |
| 6 | `plugins/session-wrap/commands/wrap.md` | Missing `name` frontmatter field (frontmatter only has `description` + `allowed-tools`) | -25 |
| 7 | `plugins/agent-council/SKILL.md` | No output format section; skill body only shows bash invocation patterns with no sample output | -10 |
| 8 | `plugins/agent-council/skills/agent-council/SKILL.md` | Same as #7 — no output format section | -10 |
| 9 | `plugins/gmail/skills/gmail/SKILL.md` | Output format covers sending workflow but not reading/searching email results — no display template for inbox summary | -10 |
| 10 | `plugins/session-wrap/agents/followup-suggester.md` | Vague terms: "relevant" (×4), "important" (×2) | -12 |
| 11 | `plugins/session-wrap/agents/doc-updater.md` | Vague terms: "relevant" (×3) | -6 |
| 12 | `plugins/session-wrap/agents/learning-extractor.md` | Vague terms: "relevant" (×3), "valuable" (×2) | -10 |
| 13 | `plugins/session-wrap/agents/duplicate-checker.md` | Vague terms: "relevant" (×2), "similar" used qualitatively (×3) | -10 |
| 14 | `plugins/session-wrap/agents/automation-scout.md` | Vague terms: "similar" (×3) | -6 |
| 15 | `plugins/dev/agents/decision-synthesizer.md` | Vague terms: "solid reasoning" | -2 |
| 16 | `plugins/dev/agents/tradeoff-analyzer.md` | Vague terms: "comprehensive" (line 31) | -2 |
| 17 | `plugins/dev/agents/docs-researcher.md` | Vague terms: "up-to-date", "balanced" | -4 |
| 18 | `plugins/dev/agents/codebase-explorer.md` | Vague terms: "relevant to the decision at hand", "similar implementations" | -4 |
| 19 | `plugins/google-calendar/.claude-plugin/plugin.json` | Missing `author`, `repository`, `license`, `keywords` fields — incomplete package metadata | -30 |
| 20 | `plugins/gmail/.claude-plugin/plugin.json` | Missing `author`, `repository`, `license`, `keywords` fields | -30 |
| 21 | `plugins/youtube-digest/.claude-plugin/plugin.json` | Missing `license`, `repository` fields | -20 |
| 22 | `.claude-plugin/plugin.json` (root) | Missing `license`, `keywords` fields | -15 |
| 23 | `plugins/doubt/.claude-plugin/plugin.json` | Missing `repository`, `license` fields | -5 |
| 24 | `plugins/dev/agents/docs-researcher.md` | `mcp__context7__resolve-library-id` and `mcp__context7__query-docs` MCP tools declared in `tools:` — these require an external Context7 MCP server not bundled with this plugin. No prerequisite note in the agent file. | Quality gap |
| 25 | `plugins/session-wrap/agents/duplicate-checker.md` | Model is `haiku` — appropriate for mechanical search, but the agent also performs functional overlap evaluation (Layer 4) which requires reasoning capacity. Consider `sonnet` if false-negative rate is high. | Model tier concern |
| 26 | `plugins/session-wrap/skills/session-analyzer/SKILL.md` | References `${baseDir}/scripts/` in multiple places, but `baseDir` is never defined in the skill. The skill assumes a shell variable that may not be set at runtime. | Runtime reliability |
| 27 | `plugins/say-summary/scripts/setup.sh` | The setup script uses `pip3 install --user` but `say-summary.py` is invoked by a Claude Code hook — it will fail silently if the user Python path doesn't include user site-packages. | Usability gap |
| 28 | `plugins/dev/skills/tech-decision/SKILL.md` | References `references/evaluation-criteria.md` and `references/report-template.md` — these paths are relative and may not resolve correctly depending on how the skill is installed. No fallback if files are absent. | Broken reference risk |

## Cross-Component

### Reference Integrity
- **`interactive-review/CLAUDE.md`** shows `skills/review.md` in the directory tree; actual file is at `skills/review/SKILL.md`. Stale since the skill was reorganized into a subdirectory.
- **`agent-council/SKILL.md`** is identical to `agent-council/skills/agent-council/SKILL.md`. The `plugin.json` points only to the nested version (`"skills": "./skills/agent-council"`). The root file is orphaned and will not be automatically kept in sync.
- **`session-analyzer/SKILL.md`** uses `${baseDir}` variable for script paths (e.g., `${baseDir}/scripts/find-session-files.sh`) but this variable is never defined in the skill file itself. Skills in Claude Code do not automatically receive a `baseDir` variable; the script references will fail unless the invoking context defines it.
- **`dev/skills/tech-decision/SKILL.md`** references `references/report-template.md` and `references/evaluation-criteria.md` as relative paths, suggesting they should exist in the `dev/` plugin directory. These were not included in the audit file list — their existence and accuracy should be confirmed.
- **`docs-researcher.md`** declares MCP tools (`mcp__context7__resolve-library-id`, `mcp__context7__query-docs`) not provided by this plugin, with no prerequisite warning. Users without Context7 MCP configured will silently get a degraded agent.

### Duplicate Content
- `plugins/agent-council/SKILL.md` ≡ `plugins/agent-council/skills/agent-council/SKILL.md` — identical content, 35 lines each. Should either be removed (root) or differentiated.

### Orphaned Components
- `plugins/agent-council/scripts/` mirrors `plugins/agent-council/skills/agent-council/scripts/` — same four files (`council.sh`, `council-job.sh`, `council-job.js`, `council-job-worker.js`). The `plugin.json` does not reference the root `scripts/` directory. These may be installation artifacts or a layout that predates the plugin structure.

### Architecture Observations
- The `dev` plugin's `tech-decision` skill orchestrates four sub-agents (`codebase-explorer`, `docs-researcher`, `tradeoff-analyzer`, `decision-synthesizer`) plus two external skills (`dev-scan`, `agent-council`) plus optional MCP. This is a well-designed dependency graph with a clear 4-phase pipeline. Cross-plugin skill calls (`dev-scan` inside `tech-decision`) work correctly because they target installed skills by name.
- The `session-wrap` plugin's 5-agent pipeline (4 parallel + 1 sequential) is the most sophisticated orchestration in this collection. The `duplicate-checker` using `haiku` for Phase 2 validation is intentional cost optimization. However, the session-wrap agents are the only category with zero examples — a notable consistency gap.

## Recommendation

CLEAR — submit PRs for all 3 bugs and 6 medium/low security fixes.

**Priority order:**
1. **Security fixes** (findings #1–#4): path traversal and jq injection are straightforward 1-line fixes; unpinned deps are trivial to pin.
2. **Bug #1** (interactive-review CLAUDE.md path): one-line fix, improves developer onboarding.
3. **Bug #2** (agent-council root SKILL.md): delete the orphaned root file to prevent drift.
4. **Quality: session-wrap agents** (issues #1–#5): add at least one `<example>` block to each of the five agents. These are the highest-penalty quality gap and the only agent group with zero examples.
5. **Quality: plugin.json completeness** (issues #19–#23): add missing `author`/`license`/`repository` to `google-calendar` and `gmail` plugin manifests.
