# NLPM Audit: wuji-labs/nopua
**Date**: 2026-04-06  |  **Artifacts**: 13  |  **Strategy**: single
**NL Score**: 80/100
**Security**: CLEAR
**Bugs**: 3  |  **Quality Issues**: 12  |  **Security Findings**: 0

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| commands/nopua-en.md | command | 65 | No frontmatter (description missing), no allowed-tools |
| commands/nopua-ja.md | command | 65 | No frontmatter (description missing), no allowed-tools |
| commands/nopua.md | command | 65 | No frontmatter (description missing), no allowed-tools |
| .claude-plugin/plugin.json | manifest | 60 | 6 skill paths reference non-existent directories; wrong language label |
| agents/nopua-mentor-en.md | agent | 75 | No example blocks; no output format section |
| agents/nopua-mentor-ja.md | agent | 75 | No example blocks; no output format section |
| agents/nopua-mentor.md | agent | 75 | No example blocks; no output format section |
| SKILL.md | skill | 90 | Root-level duplicate of skills/nopua-zh content; minor redundancy |
| codex/nopua/SKILL.md | skill | 95 | Platform copy — no unique issues |
| kiro/skills/nopua/SKILL.md | skill | 95 | Platform copy — no unique issues |
| skills/nopua-lite/SKILL.md | skill | 95 | No issues |
| skills/nopua-zh/SKILL.md | skill | 95 | No issues |
| skills/nopua/SKILL.md | skill | 95 | No issues |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Plugin scripts | 0 |
| MCP configs | 0 |
| Package manifests | 0 |
| Benchmark scripts (non-execution surface) | 34 Python files in benchmark/test-project/ |

> Note: The 34 Python files detected by the pre-scan are located in `benchmark/test-project/`, a mock ML project used as a target for academic benchmarking of the NoPUA methodology. They are not hooks, plugin scripts, or any execution surface installed with the plugin. The plugin itself is 100% markdown with no executable code.

### Security Findings
No security findings.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude-plugin/plugin.json | Declares 6 skills with paths that do not exist: `skills/nopua-en/SKILL.md`, `skills/nopua-ja/SKILL.md`, `skills/nopua-ko/SKILL.md`, `skills/nopua-es/SKILL.md`, `skills/nopua-pt/SKILL.md`, `skills/nopua-fr/SKILL.md`. Only `skills/nopua/`, `skills/nopua-lite/`, and `skills/nopua-zh/` exist. | Broken skill registration for 6 of 7 declared skills; install fails to load multilingual skills |
| 2 | .claude-plugin/plugin.json | `skills/nopua/SKILL.md` is labeled `"language": "zh-CN"` but the file contains English content (`# NoPUA — Wisdom Over Whips`). The actual zh-CN content lives at `skills/nopua-zh/SKILL.md`. | Users requesting the zh-CN skill variant receive English content |
| 3 | .claude-plugin/plugin.json | `agents/nopua-mentor-en.md` and `agents/nopua-mentor-ja.md` exist in the repo but are not registered in the `agents` array (only `nopua-mentor.md` is registered). | EN/JA mentor agents are undiscoverable via plugin registry |

## Security Fixes (PR-worthy, Medium/Low only)
No security fixes required.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | commands/nopua.md | No YAML frontmatter — `description` field absent; command shows no description in `/help` listings | -25 |
| 2 | commands/nopua-en.md | No YAML frontmatter — `description` field absent | -25 |
| 3 | commands/nopua-ja.md | No YAML frontmatter — `description` field absent | -25 |
| 4 | commands/nopua.md | No `allowed-tools` declaration | -5 |
| 5 | commands/nopua-en.md | No `allowed-tools` declaration | -5 |
| 6 | commands/nopua-ja.md | No `allowed-tools` declaration | -5 |
| 7 | agents/nopua-mentor.md | No example blocks — no concrete before/after demonstrating mentor intervention | -15 |
| 8 | agents/nopua-mentor-en.md | No example blocks | -15 |
| 9 | agents/nopua-mentor-ja.md | No example blocks | -15 |
| 10 | agents/nopua-mentor.md | No explicit output format section — mentor guidance messages have no defined structure | -10 |
| 11 | agents/nopua-mentor-en.md | No explicit output format section | -10 |
| 12 | agents/nopua-mentor-ja.md | No explicit output format section | -10 |

## Cross-Component
**Broken references (3):** plugin.json declares skill paths for `nopua-en`, `nopua-ja`, `nopua-ko`, `nopua-es`, `nopua-pt`, `nopua-fr` that have no corresponding directories under `skills/`. The plugin description ("7 languages, 7 platforms") is accurate in intent but the skill files for 6 of those languages are absent from the repository.

**Unregistered agents (2):** `agents/nopua-mentor-en.md` and `agents/nopua-mentor-ja.md` are present in the repo but absent from plugin.json's `agents` array. They reference platform-specific skill paths (`.claude/skills/nopua-en/SKILL.md`, `.claude/skills/nopua-ja/SKILL.md`) that only exist after the corresponding skills are installed — creating a circular dependency with Bug #1.

**Language/path mismatch (1):** plugin.json maps `skills/nopua/SKILL.md` → `"zh-CN"`. The file's content is English. The zh-CN version is at `skills/nopua-zh/SKILL.md`. The root `SKILL.md` (which is the canonical zh-CN version) is not registered in plugin.json at all.

**Platform copies consistent:** `codex/nopua/SKILL.md`, `kiro/skills/nopua/SKILL.md`, and the root-level `SKILL.md` are consistent with their respective platform targets. No content contradictions among them.

**Core skill content quality:** All skill files (`skills/nopua/`, `skills/nopua-zh/`, `skills/nopua-lite/`) are high-quality, with precise behavioral criteria, numbered steps, concrete action tables, and specific output formats. No vague quantifier saturation. The philosophy-driven framing is distinctive and well-executed.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

**Priority order:**
1. **Bug #1 (critical path):** Either add the 6 missing skill directories (`nopua-en`, `nopua-ja`, `nopua-ko`, `nopua-es`, `nopua-pt`, `nopua-fr`) with translated SKILL.md files, or remove the unimplemented languages from plugin.json and update the description to reflect the current 2-language state.
2. **Bug #2:** Change `skills/nopua/SKILL.md` language label from `"zh-CN"` to `"en"`, and either register `SKILL.md` (root) as the zh-CN entry or point the zh-CN entry to `skills/nopua-zh/SKILL.md`.
3. **Bug #3:** Register `nopua-mentor-en` and `nopua-mentor-ja` in plugin.json's agents array once Bug #1 is resolved (since they depend on the missing skills).
4. **Quality (commands):** Add YAML frontmatter with `description` to all three command files so they appear usefully in `/help`.
5. **Quality (mentor agents):** Add at least one example block per agent showing a concrete mentor intervention (teammate input → mentor guidance output).
