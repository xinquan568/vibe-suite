# NLPM Audit: nexu-io/html-anything
**Date**: 2026-04-06  |  **Artifacts**: 76  |  **Strategy**: progressive
**NL Score**: 81/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 35  |  **Security Findings**: 2

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| CLAUDE.md | config | 65 | Delegates entirely to @AGENTS.md; combined content is 5 lines with no project conventions |
| src/lib/templates/skills/gamified-app/SKILL.md | skill | 73 | Body only 3 design lines; missing font, color palette, animation spec |
| src/lib/templates/skills/deck-xhs-post/SKILL.md | skill | 73 | Body only 3 lines; layout and design collapsed to single brief entry |
| src/lib/templates/skills/mobile-onboarding/SKILL.md | skill | 73 | Body only 3 lines; no design detail beyond screen names |
| src/lib/templates/skills/motion-frames/SKILL.md | skill | 73 | Body only 7 lines; no color palette, no font families, no HTML output format |
| src/lib/templates/skills/social-carousel/SKILL.md | skill | 73 | Body only 4 lines; no color/font/technical output specifics |
| src/lib/templates/skills/web-proto-brutalist/SKILL.md | skill | 73 | Body only 4 lines; no color palette, no typography, no technical output |
| src/lib/templates/skills/web-proto-editorial/SKILL.md | skill | 73 | Body only 4 lines; no technical output details |
| src/lib/templates/skills/web-proto-soft/SKILL.md | skill | 73 | Body only 4 lines; insufficient specification for consistent AI output |
| src/lib/templates/skills/dashboard/SKILL.md | skill | 75 | 4-line body; section names only; no CSS, color, or font specification |
| src/lib/templates/skills/dating-web/SKILL.md | skill | 75 | 4-line body; no design or output specifics |
| src/lib/templates/skills/deck-dir-key-nav/SKILL.md | skill | 75 | 4-line body; no color hex values or technical details |
| src/lib/templates/skills/deck-presenter-mode/SKILL.md | skill | 75 | 4-line body; missing output format details |
| src/lib/templates/skills/deck-simple/SKILL.md | skill | 75 | 5-line body; no color, font, or design specifics |
| src/lib/templates/skills/deck-tech-sharing/SKILL.md | skill | 75 | 4-line body; minimal design specification |
| src/lib/templates/skills/deck-xhs-pastel/SKILL.md | skill | 75 | 4-line body; vague layout, no hex colors |
| src/lib/templates/skills/docs-page/SKILL.md | skill | 75 | 4-line body; no color scheme or font specification |
| src/lib/templates/skills/invoice/SKILL.md | skill | 75 | 4-line body; only section names, no layout spec |
| src/lib/templates/skills/live-dashboard/SKILL.md | skill | 75 | 4-line body; minimal output specification |
| src/lib/templates/skills/meeting-notes/SKILL.md | skill | 75 | 4-line body; no design details |
| src/lib/templates/skills/mobile-app/SKILL.md | skill | 75 | 4-line body; no CSS or font specification |
| src/lib/templates/skills/pricing-page/SKILL.md | skill | 75 | 4-line body; no design specifics |
| src/lib/templates/skills/social-media-dashboard/SKILL.md | skill | 75 | 4-line body; no technical output details |
| src/lib/templates/skills/social-media-matrix/SKILL.md | skill | 75 | 4-line body; no design or font details |
| src/lib/templates/skills/team-okrs/SKILL.md | skill | 75 | 4-line body; minimal spec |
| src/lib/templates/skills/wireframe-sketch/SKILL.md | skill | 75 | 4-line body; no output format |
| src/lib/templates/skills/deck-blueprint/SKILL.md | skill | 78 | 4 body lines; missing detailed output format |
| src/lib/templates/skills/deck-course-module/SKILL.md | skill | 78 | 4 body lines; missing detailed output format |
| src/lib/templates/skills/deck-graphify-dark/SKILL.md | skill | 78 | 4 body lines; missing detailed output format |
| src/lib/templates/skills/deck-hermes-cyber/SKILL.md | skill | 78 | 4 body lines; no technical output |
| src/lib/templates/skills/deck-magazine-web/SKILL.md | skill | 78 | 6 body lines; missing explicit output format |
| src/lib/templates/skills/deck-obsidian-claude/SKILL.md | skill | 78 | 4 body lines; missing explicit output format |
| src/lib/templates/skills/deck-product-launch/SKILL.md | skill | 78 | 5 body lines; no CSS or color specification |
| src/lib/templates/skills/deck-safety-alert/SKILL.md | skill | 78 | 4 body lines; no technical details |
| src/lib/templates/skills/deck-xhs-white/SKILL.md | skill | 78 | 4 body lines; no explicit output format |
| src/lib/templates/skills/digital-eguide/SKILL.md | skill | 78 | 5 body lines; no technical output details |
| src/lib/templates/skills/eng-runbook/SKILL.md | skill | 78 | 5 body lines; no CSS or output details |
| src/lib/templates/skills/finance-report/SKILL.md | skill | 78 | 6 body lines; no color or font spec |
| src/lib/templates/skills/flowai-team-dashboard/SKILL.md | skill | 78 | 5 body lines; minimal design detail |
| src/lib/templates/skills/hr-onboarding/SKILL.md | skill | 78 | 5 body lines; no visual output details |
| src/lib/templates/skills/kanban-board/SKILL.md | skill | 78 | 4 body lines; no color or layout spec |
| src/lib/templates/skills/pm-spec/SKILL.md | skill | 78 | 6 body lines; no visual or output spec |
| src/lib/templates/skills/saas-landing/SKILL.md | skill | 78 | 7 body lines; brief relative to landing-page complexity |
| src/lib/templates/skills/sprite-animation/SKILL.md | skill | 78 | 5 body lines; animation spec too brief |
| src/lib/templates/skills/waitlist-page/SKILL.md | skill | 78 | 5 body lines; no CSS or color spec |
| src/lib/templates/skills/blog-post/SKILL.md | skill | 80 | 5 body lines; no font or color specification |
| src/lib/templates/skills/deck-pitch/SKILL.md | skill | 80 | 8 body lines; no technical output format |
| src/lib/templates/skills/email-marketing/SKILL.md | skill | 80 | 5 body lines; limited HTML email technical spec |
| src/lib/templates/skills/magazine-poster/SKILL.md | skill | 80 | 11 body lines; no explicit output format or font fallbacks |
| src/lib/templates/skills/weekly-update/SKILL.md | skill | 80 | 7 body lines; brief for a 6-8 page deck |
| src/lib/templates/skills/poster-hero/SKILL.md | skill | 82 | Tailwind classes listed but no explicit output format declaration |
| src/lib/templates/skills/article-magazine/SKILL.md | skill | 83 | 8 body lines; has example but no font or color details |
| src/lib/templates/skills/card-twitter/SKILL.md | skill | 83 | 6 body lines; has example but brief design spec |
| src/lib/templates/skills/prototype-web/SKILL.md | skill | 83 | 4 body lines; brief but has example |
| src/lib/templates/skills/deck-replit/SKILL.md | skill | 85 | Has example; 8 theme names listed with no color palettes — agent must guess theme colors |
| src/lib/templates/skills/card-xiaohongshu/SKILL.md | skill | 88 | Good spec; no explicit output format field |
| src/lib/templates/skills/ppt-keynote/SKILL.md | skill | 88 | Good spec with example; could specify font families |
| src/lib/templates/skills/resume-modern/SKILL.md | skill | 88 | Good spec; A4 sizing clear; no color hex values |
| src/lib/templates/skills/video-hyperframes/SKILL.md | skill | 88 | Good spec with example; '单文件 HTML' implicit not explicit |
| src/lib/templates/skills/data-report/SKILL.md | skill | 90 | Detailed; specific Chart.js ResizeObserver warning; has example |
| src/lib/templates/skills/deck-guizang-editorial/SKILL.md | skill | 93 | Full spec; example; -2 for "合理估算" vague quantifier (auto-estimated images) |
| src/lib/templates/skills/frame-data-chart-nyt/SKILL.md | skill | 93 | Full spec; example; -2 for "合理坐标" (reasonable coordinates) for auto-estimated data |
| src/lib/templates/skills/frame-light-leak-cinema/SKILL.md | skill | 93 | Full spec; example; -2 for "合理" (reasonable) for auto-estimated metadata |
| src/lib/templates/skills/social-reddit-card/SKILL.md | skill | 93 | Full spec; example; -2 for "合理的" (reasonable) for auto-generated subreddit/username |
| src/lib/templates/skills/deck-open-slide-canvas/SKILL.md | skill | 95 | Full spec; explicit type scale; example; explicit '单文件 HTML' |
| src/lib/templates/skills/deck-swiss-international/SKILL.md | skill | 95 | Full spec; 22-layout pool; all hex values explicit; example |
| src/lib/templates/skills/doc-kami-parchment/SKILL.md | skill | 95 | Full spec; strict design invariants; example; explicit '单文件 HTML' |
| src/lib/templates/skills/frame-flowchart-sticky/SKILL.md | skill | 95 | Full spec; exact SVG constraints; example; explicit '单文件 HTML' |
| src/lib/templates/skills/frame-glitch-title/SKILL.md | skill | 95 | Full spec; animation timing precise; example; explicit '单文件 HTML' |
| src/lib/templates/skills/frame-liquid-bg-hero/SKILL.md | skill | 95 | Full spec; three implementation tiers; palette options; example |
| src/lib/templates/skills/frame-logo-outro/SKILL.md | skill | 95 | Full spec; animation timing explicit; palette options; example |
| src/lib/templates/skills/frame-macos-notification/SKILL.md | skill | 95 | Full spec; exact CSS values; frosted-glass detail; example |
| src/lib/templates/skills/mockup-device-3d/SKILL.md | skill | 95 | Full spec; CSS 3D transforms explicit; screen-content rules; example |
| src/lib/templates/skills/social-spotify-card/SKILL.md | skill | 95 | Full spec; exact hex values; animation spec; example |
| src/lib/templates/skills/social-x-post-card/SKILL.md | skill | 95 | Full spec; both light/dark palettes explicit; SVG icon rules; example |
| src/lib/templates/skills/vfx-text-cursor/SKILL.md | skill | 95 | Full spec; timing intervals explicit; example; explicit '单文件 HTML' |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Shell scripts | 0 |
| Python scripts | 0 |
| MCP configs | 0 |
| Package manifest | package.json (no postinstall scripts) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | package.json | 17 | SEC-stale-dependency | `xlsx: ^0.18.5` — SheetJS was removed from npm's public registry in newer versions; ^0.18.5 is the last public release (~2022) and no longer receives npm security patches |
| 2 | Low | package.json | 12–28 | SEC-unpinned-semver | 23 of 25 dependencies use `^` (caret) semver ranges, allowing automatic minor/patch upgrades that could introduce regressions or supply-chain issues |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| — | — | No bugs found | — |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | package.json | `xlsx: ^0.18.5` — stale/abandoned npm package | Replace with actively maintained alternative such as `exceljs`, or use SheetJS via its official CDN with a pinned version tag |
| 2 | package.json | Unpinned `^` semver ranges on 23 dependencies | Pin exact versions for production deps, or enforce lockfile integrity with `pnpm install --frozen-lockfile` in CI |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | src/lib/templates/skills/motion-frames/SKILL.md | Body only 7 lines; no CSS/HTML output format stated, no font families, no color palette | -10 |
| 2 | src/lib/templates/skills/web-proto-soft/SKILL.md | Body only 4 lines; four bullet points with no color, font, or CSS specifications | -10 |
| 3 | src/lib/templates/skills/web-proto-brutalist/SKILL.md | Body only 4 lines; no color palette, no typography, no technical output | -10 |
| 4 | src/lib/templates/skills/web-proto-editorial/SKILL.md | Body only 4 lines; no technical output details | -10 |
| 5 | src/lib/templates/skills/gamified-app/SKILL.md | Body only 3 lines of design detail; missing font, color, and animation specs | -10 |
| 6 | src/lib/templates/skills/deck-xhs-post/SKILL.md | Body only 3 lines; layout and design collapsed to single brief entry | -10 |
| 7 | src/lib/templates/skills/mobile-onboarding/SKILL.md | Body only 3 lines; no design detail beyond screen enumeration | -10 |
| 8 | src/lib/templates/skills/social-carousel/SKILL.md | Body only 4 lines; no color/font/technical output specifics | -10 |
| 9 | src/lib/templates/skills/frame-data-chart-nyt/SKILL.md | Vague quantifier: "合理坐标" (reasonable coordinates) for auto-estimated schematic data | -2 |
| 10 | src/lib/templates/skills/social-reddit-card/SKILL.md | Vague quantifier: "合理的" (reasonable) for auto-generated subreddit/username — no fallback rule | -2 |
| 11 | src/lib/templates/skills/frame-light-leak-cinema/SKILL.md | Vague quantifier: "合理" (reasonable) for auto-estimated year/chapter/location metadata | -2 |
| 12 | CLAUDE.md | Minimal content: single `@AGENTS.md` import; AGENTS.md itself is only 4 lines with no project conventions | -5 |
| 13 | src/lib/templates/skills/deck-replit/SKILL.md | References 8 theme names without specifying any color palettes — agent must guess theme colors | -5 |
| 14 | (pattern) 18 files at score 75 | 4-line bodies with section names only (no hex colors, no font specs, no output format); representative: dashboard, dating-web, docs-page, team-okrs, pricing-page, meeting-notes | -5 each |
| 15 | (pattern) 19 files at score 78 | 4-7 line bodies with partial specs (layout described, no typography or explicit HTML output); representative: deck-blueprint, deck-graphify-dark, hr-onboarding, kanban-board, pm-spec, finance-report | -5 each |

## Cross-Component
- `CLAUDE.md` → `@AGENTS.md` reference: **AGENTS.md exists** (4-line Next.js caution note). Reference resolves correctly but the combined 5-line project AI configuration provides no template skill conventions, category taxonomy, or output format guidance.
- No `commands/*.md`, `hooks/**`, or `agents/*.md` files. This is a Next.js web application, not a Claude Code plugin repo — the NL artifacts are exclusively template skill descriptions under `src/lib/templates/skills/`.
- No cross-skill references or broken internal links detected among the 75 SKILL.md files.
- The well-specified "Tier 1" skills (12 files scoring 95) establish a quality bar the remaining ~37 brief skills do not reach: they consistently include hex color palettes, explicit font family stacks, canvas dimensions, and a "单文件 HTML" output declaration.

## Recommendation
CLEAR — submit PRs for all Medium/Low security fixes. No Critical or High security findings. No NL bugs.

**Priority actions for the repo owner:**
1. **Replace `xlsx`** (Medium security): the npm package is abandoned; migrate to `exceljs` or the official SheetJS CDN release.
2. **Expand ~37 brief SKILL.md files**: add 【设计细节】 sections with hex colors, font families, canvas dimensions, and `单文件 HTML` output declarations. The 12 Tier-1 skills (frame-flowchart-sticky, deck-swiss-international, etc.) demonstrate the quality bar to target.
3. **Fix three vague quantifiers** in `frame-data-chart-nyt`, `social-reddit-card`, and `frame-light-leak-cinema`: replace "合理" (reasonable) with deterministic fallback rules so the AI produces reproducible outputs.
