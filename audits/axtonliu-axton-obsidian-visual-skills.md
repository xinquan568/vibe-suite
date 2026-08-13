# NLPM Audit: axtonliu/axton-obsidian-visual-skills
**Date**: 2026-04-06  |  **Artifacts**: 3  |  **Strategy**: single
**NL Score**: 90/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 7  |  **Security Findings**: 0

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| mermaid-visualizer/SKILL.md | skill | 88/100 | Vague quantifiers: "appropriate", "balanced", "sensible" (-6) |
| obsidian-canvas-creator/SKILL.md | skill | 89/100 | Vague quantifiers: "appropriate", "subtle", "strategic" (-6); thin examples (process steps only, no JSON output shown) |
| excalidraw-diagram/SKILL.md | skill | 94/100 | No material issues; minor vague language in Chinese bilingual sections |

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
No bugs found. All frontmatter fields (`name`, `description`) are present on all three skills. All internal reference links resolve to existing files.

## Security Fixes (PR-worthy, Medium/Low only)
No security fixes needed.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | mermaid-visualizer/SKILL.md | Vague quantifier "appropriate" (line 25: "most appropriate visualization") | -2 |
| 2 | mermaid-visualizer/SKILL.md | Vague quantifier "balanced" (line 44: "balanced between simplicity and information") | -2 |
| 3 | mermaid-visualizer/SKILL.md | Vague quantifier "sensible" (line 263: "Use sensible defaults for unspecified options") | -2 |
| 4 | obsidian-canvas-creator/SKILL.md | Vague quantifier "appropriate" (line 69: "Use appropriate arrow styles") | -2 |
| 5 | obsidian-canvas-creator/SKILL.md | Vague quantifier "subtle" (line 74: "Use subtle background colors") | -2 |
| 6 | obsidian-canvas-creator/SKILL.md | Vague quantifier "Strategic" (line 201: "Strategic colors: Use colors to encode meaning") | -2 |
| 7 | obsidian-canvas-creator/SKILL.md | Example blocks show process steps only — no actual JSON Canvas output demonstrated; a reader cannot infer the exact output format from examples alone (canvas-spec.md deferred) | informational |

## Cross-Component
All three skills reference sibling `references/` files:
- `excalidraw-diagram/references/excalidraw-schema.md` — **exists** ✓
- `mermaid-visualizer/references/syntax-rules.md` — **exists** ✓
- `obsidian-canvas-creator/references/canvas-spec.md` — **exists** ✓
- `obsidian-canvas-creator/references/layout-algorithms.md` — **exists** ✓

No orphaned components. No broken relative paths. No terminology drift across the three skills (all use "canvas", "Excalidraw", "Mermaid" consistently without overlap confusion).

The `.claude-plugin/marketplace.json` registers all three skills correctly under the `obsidian-visual-skills` plugin. No `plugin.json` is present at root; the marketplace manifest appears to be the intended registration mechanism for this package.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

This is a well-structured skill pack. No bugs and no security issues. The quality deductions are minor vague-quantifier cleanups in `mermaid-visualizer` and `obsidian-canvas-creator`. The excalidraw skill is the strongest artifact: bilingual, three clearly-defined output modes, explicit file-naming conventions, and detailed design rules. Suggested improvements:
1. Replace "appropriate", "balanced", "sensible", "subtle", "strategic" with concrete criteria (e.g., "straight arrows for parent-child, curved for cross-references" instead of "appropriate arrow styles").
2. Add a minimal JSON Canvas snippet to `obsidian-canvas-creator` examples so a reader can verify format compliance without loading the reference doc.
