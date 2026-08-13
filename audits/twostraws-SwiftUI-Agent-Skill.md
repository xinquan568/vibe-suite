# NLPM Audit: twostraws/SwiftUI-Agent-Skill
**Date**: 2026-05-05  |  **Artifacts**: 3  |  **Strategy**: single
**NL Score**: 89/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 2  |  **Security Findings**: 0

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `swiftui-pro/SKILL.md` | Skill (unregistered) | 84/100 | 8 vague quantifiers (-16): "correctly", "relevant"×2, "Comprehensively", "optimally", "consistent", "brief", "modern" |
| `swiftui-pro/skills/swiftui-pro/SKILL.md` | Skill (canonical) | 84/100 | 8 vague quantifiers (-16): same words as above |
| `swiftui-pro/.claude-plugin/plugin.json` | Plugin Manifest | 100/100 | None — all required fields present, valid semver |

**Scoring notes:**
- Both SKILL.md files are nearly identical in content; each scored independently.
- plugin.json is a JSON manifest; NL prose penalties (frontmatter, examples, model) do not apply.
- Vague-word penalty applied per R01: "correctly", "relevant" (×2 each), "Comprehensively", "optimally", "consistent", "brief", "modern" × -2 each = -16/file, under the -20 cap.
- No model declaration penalty: skills (non-agent) are not expected to declare a model tier.
- Steps use repeated `1.` in ordered lists — valid CommonMark auto-increment, not penalized.

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
| Hooks | None |
| Scripts | None |
| MCP configs | None |
| Package manifests | None |

### Security Findings
No security findings.

## Bugs (PR-worthy)
No bugs found. All registered artifacts have required frontmatter (`name`, `description`). The plugin manifest contains all required fields with a valid semver version string.

## Security Fixes (PR-worthy, Medium/Low only)
No security fixes needed.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `swiftui-pro/SKILL.md` | 8 vague quantifiers (R01): "Comprehensively" (line 3), "optimally" (line 14), "correctly" (line 16), "relevant" (lines 24, 42), "modern" (line 10), "consistent" (line 35), "brief" (line 43) | -16 |
| 2 | `swiftui-pro/skills/swiftui-pro/SKILL.md` | Same 8 vague quantifiers as above (identical prose, identical lines) | -16 |

**Suggested fixes for R01 violations:**
- "Comprehensively reviews" → "Reviews … across 9 rule sets"
- "written optimally" → "written without redundant re-renders or view rebuilds"
- "configured correctly" → "follows single-source-of-truth patterns (no duplicate state)"
- "consistent project structure" → "feature-grouped project structure (no flat root dumps)"
- "relevant reference files" → name the file explicitly, or "only the reference files whose sections are applicable"
- "brief before/after code fix" → "5-line before/after code fix"
- "modern API usage" → "iOS 26+ API usage"

## Cross-Component
| # | Finding | Severity |
|---|---------|---------|
| 1 | **Duplicate / unregistered root SKILL.md.** `swiftui-pro/SKILL.md` is present with valid skill frontmatter (`name: swiftui-pro`, version `1.1`) but `plugin.json` declares `"skills": "./skills/"`, so only `skills/swiftui-pro/SKILL.md` is loaded by the plugin system. The root copy is silently ignored by the plugin but might confuse contributors or tools that look for a top-level SKILL.md. Its references (`references/api.md`) also lack the `${CLAUDE_SKILL_DIR}` prefix, so it would fail to load reference files if invoked standalone. | medium |
| 2 | **Version skew between copies.** Root SKILL.md declares `version: "1.1"` while the canonical `skills/swiftui-pro/SKILL.md` declares `version: "1.0"`. The registered (canonical) skill is the older copy. Either the root copy should be deleted or its changes (which appear to be only the removal of `argument-hint`) should be back-ported to the canonical file. | low |
| 3 | **`agents/openai.yaml` not referenced anywhere.** The file defines an OpenAI Responses API agent interface with `allow_implicit_invocation: true` but is not referenced by `plugin.json` and has no corresponding Claude Code artifact. Informational only — not a Claude Code NL artifact. | info |

## Recommendation
CLEAR — no security issues and no registration-breaking bugs. Optional PRs:

1. **Quality PR (high value):** Fix R01 vague-language violations in `skills/swiftui-pro/SKILL.md` — the 8 replacements above make review criteria unambiguous.
2. **Cleanup PR (low value):** Resolve the root `SKILL.md` vs. canonical version skew — either delete the root copy or promote the canonical to version `1.1` with the `argument-hint` field intact.
