# NLPM Audit: viticci/shortcuts-playground-plugin
**Date**: 2026-05-25  |  **Artifacts**: 9  |  **Strategy**: single
**NL Score**: 91/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 11  |  **Security Findings**: 7

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| claude/agents/shortcut-builder.md | agent | 85 | No example invocations (−15) |
| claude/agents/shortcut-remixer.md | agent | 85 | No example invocations (−15) |
| claude/commands/build.md | command | 85 | No allowed-tools declared; no empty-input guard |
| claude/commands/remix.md | command | 85 | No allowed-tools declared; no empty-input guard |
| claude/skills/shortcuts-playground/SKILL.md | skill | 92 | Vague quantifiers ("relevant", "unfamiliar") |
| codex/skills/shortcuts-playground/SKILL.md | skill | 92 | Vague quantifiers; missing `effort`/`allowed-tools` vs Claude version |
| claude/.claude-plugin/plugin.json | manifest | 95 | Description mentions "a build agent" but two agents ship |
| claude/hooks/hooks.json | hook | 100 | — |
| codex/hooks/hooks.json | hook | 100 | — |

**Weighted average**: (85×4 + 92×2 + 95 + 100×2) / 9 = **91/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 (false positive — by-design output write) |
| Medium | 2 |
| Low | 4 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hook scripts | claude/hooks/auto-validate.sh, codex/hooks/auto-validate.sh |
| Hook configs | claude/hooks/hooks.json, codex/hooks/hooks.json |
| Shell scripts | codex/skills/shortcuts-playground/scripts/sign_shortcut.sh |
| Python scripts | claude/skills/shortcuts-playground/scripts/validate_shortcut.py, select_shortcut_icon_color.py, test_random_mixed_shortcuts.py, test_wiring_regressions.py, generate_healthkit_reference.py |
| Python scripts (Codex mirror) | codex/skills/shortcuts-playground/scripts/ (same 5 scripts + sign_shortcut.sh) |
| MCP configs | none |
| Package manifests | none (no package.json or requirements.txt) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | HIGH (FP) | codex/skills/shortcuts-playground/scripts/sign_shortcut.sh | 93–98 | file-write-outside-repo | Script writes signed .shortcut and XML archive to `$OUTPUT_DIR` (user's Documents folder). False positive: this is the plugin's explicit and documented purpose. |
| 2 | MEDIUM | claude/skills/shortcuts-playground/scripts/test_random_mixed_shortcuts.py | 562 | env-var-access | `os.environ.get("CLAUDE_PLUGIN_OPTION_OUTPUT_DIR")` and `SHORTCUTS_PLAYGROUND_OUTPUT_DIR` read to resolve output directory. Expected configuration pattern; no credential access. |
| 3 | MEDIUM | codex/skills/shortcuts-playground/scripts/test_random_mixed_shortcuts.py | 562 | env-var-access | Same env var access pattern as claude mirror. Expected configuration pattern. |
| 4 | LOW | claude/skills/shortcuts-playground/scripts/test_random_mixed_shortcuts.py | 528 | subprocess-call | `subprocess.run(["shortcuts", "sign", ...])` — list args, no `shell=True`, no user-controlled input flows into arguments. |
| 5 | LOW | codex/skills/shortcuts-playground/scripts/test_random_mixed_shortcuts.py | 528 | subprocess-call | Same pattern as claude mirror. |
| 6 | LOW | claude/skills/shortcuts-playground/scripts/generate_healthkit_reference.py | 147 | subprocess-call | `subprocess.check_output(["xcrun", "--sdk", "iphoneos", "--show-sdk-path"])` — hardcoded args, macOS SDK path lookup, no user input. |
| 7 | LOW | codex/skills/shortcuts-playground/scripts/generate_healthkit_reference.py | 147 | subprocess-call | Same xcrun pattern as claude mirror. |

## Bugs (PR-worthy)
No bugs found. All agents have required frontmatter (`name`, `description`, `model`, `tools`, `skills`). All referenced skill files, data files, golden-shortcut indexes, and bin wrappers exist on disk. Cross-references from agents to skill names and from commands to agent `subagent_type` names resolve correctly.

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | claude/skills/.../test_random_mixed_shortcuts.py | Reads `CLAUDE_PLUGIN_OPTION_OUTPUT_DIR` and `SHORTCUTS_PLAYGROUND_OUTPUT_DIR` env vars for output dir config | No change needed; behavior is correct. Consider adding an inline comment noting these are plugin-config vars, not credentials. |
| 2 | codex/skills/.../test_random_mixed_shortcuts.py | Same as above | Same. |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | claude/agents/shortcut-builder.md | No `## Examples` block; no sample user prompts or expected outputs | −15 |
| 2 | claude/agents/shortcut-remixer.md | No `## Examples` block; no sample user prompts or expected outputs | −15 |
| 3 | claude/commands/build.md | Frontmatter has no `allowed-tools` field; Agent tool usage undeclared | −5 |
| 4 | claude/commands/build.md | No empty-input guard for `$ARGUMENTS`; agent receives empty prompt if user omits the brief | −10 |
| 5 | claude/commands/remix.md | Frontmatter has no `allowed-tools` field; Agent tool usage undeclared | −5 |
| 6 | claude/commands/remix.md | No empty-input guard for `$ARGUMENTS`; remixer agent receives empty prompt | −10 |
| 7 | claude/skills/shortcuts-playground/SKILL.md | "relevant" used ×3 as a vague selection qualifier ("load only the relevant reference files", etc.) | −6 |
| 8 | claude/skills/shortcuts-playground/SKILL.md | "unfamiliar" used ×1 as vague difficulty qualifier ("complex or unfamiliar external APIs") | −2 |
| 9 | codex/skills/shortcuts-playground/SKILL.md | Same "relevant" ×3 occurrences as Claude mirror | −6 |
| 10 | codex/skills/shortcuts-playground/SKILL.md | Same "unfamiliar" ×1 as Claude mirror | −2 |
| 11 | claude/.claude-plugin/plugin.json | `description` says "a build agent" (singular) but two agents ship (`shortcut-builder` and `shortcut-remixer`) | −5 |

## Cross-Component
**Manifest underrepresents capabilities**: `plugin.json` description names only "a build agent" and "a PostToolUse hook." The plugin actually ships two agents (`shortcut-builder`, `shortcut-remixer`), two commands (`build`, `remix`), and one hook. The omission does not break registration (Claude Code discovers agents/commands/skills by path convention, not manifest declaration) but misleads users reading the marketplace listing.

**Codex SKILL.md missing `effort` and `allowed-tools` vs Claude SKILL.md**: The Claude `SKILL.md` frontmatter declares `effort: max` and `allowed-tools: Read, Write, Edit, Bash, Glob, Grep`; the Codex mirror omits both. This is intentional platform adaptation (Codex does not use the same frontmatter schema), not an oversight — the Codex skill's body text correctly redirects to direct script paths. No fix needed; the divergence is explained and correct.

**Skill cross-references fully resolve**: All 18 markdown reference files linked from `SKILL.md` (`ACTIONS.md`, `APPINTENTS.md`, `BEST_PRACTICES.md`, `CHANGELOG.md`, `CONTROL_FLOW.md`, `DATE_TIME.md`, `EXAMPLES.md`, `FILTERS.md`, `HEALTHKIT.md`, `ICONS_AND_COLORS.md`, `JAVASCRIPT_WEBPAGE.md`, `PARAMETER_TYPES.md`, `PLIST_FORMAT.md`, `THIRD_PARTY_ACTIONS.md`, `TOOLKIT_SNAPSHOT.md`, `URL_SCHEMES.md`, `VARIABLES.md`) exist on disk in both the claude and codex packages. `data/toolkit-v63-tool-ids.json` and the `golden-shortcuts/` library are present in both. All three Claude bin wrappers (`resolve-icon`, `sign-shortcut`, `validate-shortcut`) exist at `claude/bin/`. No broken references.

**Agent → skill binding resolves**: Both agents declare `skills: shortcuts-playground` and the skill lives at `claude/skills/shortcuts-playground/SKILL.md`. The `subagent_type` values in `build.md` (`shortcut-builder`) and `remix.md` (`shortcut-remixer`) match the `name:` fields in the respective agent frontmatter exactly.

## Recommendation
CLEAR — no critical or high-severity security findings (the one HIGH is a verified false positive: by-design output-dir writes). Submit quality-improvement PRs for the two agents (add example blocks) and two commands (add `allowed-tools` + empty-input guards). Vague-language fixes in the SKILL.md are low-value but worth a single pass to replace "relevant reference files" with explicit enumeration. The manifest description fix (add remixer to the description) is a one-liner worth including in the same PR.
