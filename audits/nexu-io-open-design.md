# Audit: nexu-io/open-design

**Date:** 2026-05-04
**Artifacts:** 63 (61 `SKILL.md` files + 1 `CLAUDE.md` + 1 example `SKILL.md`)
**Strategy:** Full NL scan — all skills, root CLAUDE.md, and docs/examples. Security scan of all executable surfaces (hooks, scripts, package manifests, MCP configs).
**NL Score:** 91/100
**Security:** REVIEW

| Category | Count |
|---|---|
| Bugs | 2 |
| Quality Issues | 22 |
| Security Findings | 6 (1 false positive) |

---

## NL Score Summary

Sorted ascending. Score = 100 − penalties (missing required frontmatter field −25 each, missing output contract −10, vague quantifiers −2/each capped at −20, structural issues −5).

| Score | File | Name | Primary Deductions |
|---|---|---|---|
| 78 | `skills/editorial-collage-deck/SKILL.md` | editorial-collage-deck | Non-standard frontmatter (od fields scattered); triggers implicit in od body only |
| 78 | `skills/pptx-html-fidelity-audit/SKILL.md` | pptx-html-fidelity-audit | Partial od block (mode/scenario only, no platform/preview/design_system); no explicit output contract |
| 80 | `CLAUDE.md` | — | Single-line `@AGENTS.md` redirect; no NLPM frontmatter; not skill-shaped but included as root instruction file |
| 83 | `skills/html-ppt-presenter-mode-reveal/SKILL.md` | html-ppt-presenter-mode | **BUG:** `name` field is `html-ppt-presenter-mode`; folder and master skill reference `presenter-mode-reveal`; no example_prompt |
| 83 | `skills/invoice/SKILL.md` | invoice | 4-bullet workflow; sparse output contract; vague: "some", "appropriate" |
| 83 | `skills/meeting-notes/SKILL.md` | meeting-notes | 3-bullet workflow; sparse output contract; vague: "some", "relevant" |
| 83 | `skills/pm-spec/SKILL.md` | pm-spec | 4-bullet workflow; sparse output contract; vague: "some", "appropriate" |
| 83 | `skills/team-okrs/SKILL.md` | team-okrs | 3-bullet workflow; sparse output contract; vague: "some" |
| 85 | `skills/audio-jingle/SKILL.md` | audio-jingle | No explicit output contract (dispatch, no artifact tag spec); vague: "some", "various" |
| 85 | `skills/eng-runbook/SKILL.md` | eng-runbook | Minimal workflow; sparse output contract; vague: "some" |
| 85 | `skills/hr-onboarding/SKILL.md` | hr-onboarding | Minimal workflow; sparse output contract; vague: "some" |
| 85 | `skills/image-poster/SKILL.md` | image-poster | Explicitly suppresses artifact tag; vague: "some", "various" |
| 85 | `skills/kanban-board/SKILL.md` | kanban-board | 4-bullet workflow; sparse output contract; vague: "some" |
| 85 | `skills/mobile-onboarding/SKILL.md` | mobile-onboarding | 5-bullet workflow; sparse output contract; vague: "some" |
| 85 | `skills/video-shortform/SKILL.md` | video-shortform | Inline dispatch, no standalone output contract; vague: "some" |
| 85 | `skills/weekly-update/SKILL.md` | weekly-update | 4-bullet workflow; sparse output contract |
| 87 | `skills/web-prototype-taste-brutalist/SKILL.md` | web-prototype-taste-brutalist | Pure style ref: no `triggers`, no `od` block (intentional but uncontracted) |
| 88 | `docs/examples/saas-landing-skill/SKILL.md` | saas-landing | **BUG:** duplicate `name: saas-landing` conflicts with `skills/saas-landing/SKILL.md` |
| 88 | `skills/html-ppt-course-module/SKILL.md` | html-ppt-course-module | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-dir-key-nav-minimal/SKILL.md` | html-ppt-dir-key-nav-minimal | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-graphify-dark-graph/SKILL.md` | html-ppt-graphify-dark-graph | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-hermes-cyber-terminal/SKILL.md` | html-ppt-hermes-cyber-terminal | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-knowledge-arch-blueprint/SKILL.md` | html-ppt-knowledge-arch-blueprint | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-obsidian-claude-gradient/SKILL.md` | html-ppt-obsidian-claude-gradient | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-pitch-deck/SKILL.md` | html-ppt-pitch-deck | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-product-launch/SKILL.md` | html-ppt-product-launch | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-tech-sharing/SKILL.md` | html-ppt-tech-sharing | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-testing-safety-alert/SKILL.md` | html-ppt-testing-safety-alert | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-weekly-report/SKILL.md` | html-ppt-weekly-report | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-xhs-pastel-card/SKILL.md` | html-ppt-xhs-pastel-card | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-xhs-post/SKILL.md` | html-ppt-xhs-post | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/html-ppt-xhs-white-editorial/SKILL.md` | html-ppt-xhs-white-editorial | Focused-entry: no standalone output contract; defers to master |
| 88 | `skills/saas-landing/SKILL.md` | saas-landing | **BUG:** duplicate `name: saas-landing` conflicts with `docs/examples/saas-landing-skill/SKILL.md` |
| 88 | `skills/web-prototype-taste-editorial/SKILL.md` | web-prototype-taste-editorial | Pure style ref: no `triggers`, no `od` block (intentional but uncontracted) |
| 88 | `skills/web-prototype-taste-soft/SKILL.md` | web-prototype-taste-soft | Pure style ref: no `triggers`, no `od` block (intentional but uncontracted) |
| 89 | `skills/html-ppt-taste-brutalist/SKILL.md` | html-ppt-taste-brutalist | Pure style ref: no `triggers`, no `od` block (intentional but uncontracted) |
| 89 | `skills/html-ppt-taste-editorial/SKILL.md` | html-ppt-taste-editorial | Pure style ref: no `triggers`, no `od` block (intentional but uncontracted) |
| 92 | `skills/guizang-ppt/SKILL.md` | magazine-web-ppt | `name` (magazine-web-ppt) doesn't match folder (guizang-ppt); no od.example_prompt |
| 93 | `skills/hatch-pet/SKILL.md` | hatch-pet | Vague: "some", "appropriate"; subagent script paths partially hardcoded |
| 93 | `skills/hyperframes/SKILL.md` | hyperframes | Vague: "some"; dispatch output partially implicit |
| 95 | `skills/html-ppt/SKILL.md` | html-ppt | Exemplary master skill; minor: vague "some" once |
| 95 | `skills/tweaks/SKILL.md` | tweaks | Comprehensive; no od.featured field |
| 96 | `skills/critique/SKILL.md` | critique | Exemplary: 5-dimension scoring, evidence requirements, output contract clear |
| 96 | `skills/design-brief/SKILL.md` | design-brief | Exemplary: I-Lang protocol, token resolution tables, DESIGN.md generation |
| 96 | `skills/editorial-collage/SKILL.md` | editorial-collage | Exemplary: typed input schema, compose.ts integration, 16-slot image library |
| 96 | `skills/replit-deck/SKILL.md` | replit-deck | Exemplary: 8 themes, snapshot date, daemon verification step |
| 100 | `skills/blog-post/SKILL.md` | blog-post | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/dashboard/SKILL.md` | dashboard | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/dating-web/SKILL.md` | dating-web | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/digital-eguide/SKILL.md` | digital-eguide | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/docs-page/SKILL.md` | docs-page | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/email-marketing/SKILL.md` | email-marketing | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/finance-report/SKILL.md` | finance-report | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/gamified-app/SKILL.md` | gamified-app | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/magazine-poster/SKILL.md` | magazine-poster | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/mobile-app/SKILL.md` | mobile-app | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/motion-frames/SKILL.md` | motion-frames | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/pricing-page/SKILL.md` | pricing-page | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/simple-deck/SKILL.md` | simple-deck | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/social-carousel/SKILL.md` | social-carousel | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/sprite-animation/SKILL.md` | sprite-animation | All required fields; complete output contract; no vague quantifiers |
| 100 | `skills/web-prototype/SKILL.md` | web-prototype | All required fields; complete output contract; resource map; no vague quantifiers |
| 100 | `skills/wireframe-sketch/SKILL.md` | wireframe-sketch | All required fields; complete output contract; self-check section; no vague quantifiers |

**Total:** 5,732 pts across 63 artifacts → **91/100**

---

## Security Scan

### Execution Surface Inventory

| Surface | Files | Notes |
|---|---|---|
| Shell scripts | `skills/html-ppt/scripts/render.sh` | Renders HTML via Chrome headless |
| Python scripts | `skills/hatch-pet/scripts/generate_pet_images.py`, `skills/hatch-pet/scripts/finalize_pet_run.py` | Image gen + run finalization |
| Node scripts | `scripts/postinstall.mjs`, `scripts/check-residual-js.ts` | Build hooks |
| Hooks | None in `.claude/hooks/` or `hooks/` | N/A |
| Package manifest hooks | `package.json` → `"postinstall": "node ./scripts/postinstall.mjs"` | Runs on `pnpm install` |
| MCP configs | None found | N/A |

### Severity Counts

| Severity | Count | False Positives |
|---|---|---|
| Critical | 0 | — |
| High | 1 | 1 |
| Medium | 3 | 0 |
| Low | 2 | 0 |

### Findings

| Severity | File | Line | Pattern | Description | FP? |
|---|---|---|---|---|---|
| HIGH | `package.json` | 1 | `postinstall-script` | `"postinstall": "node ./scripts/postinstall.mjs"` fires on every `pnpm install`. Script content confirmed: runs `pnpm build` on 5 internal workspace packages only — no network access, no remote code. | YES |
| MEDIUM | `skills/html-ppt/scripts/render.sh` | 55 | `--no-sandbox` | Chrome launched with `--no-sandbox` flag. Reduces renderer isolation; acceptable for local CI but should be gated behind an explicit `ALLOW_NO_SANDBOX` env var to prevent accidental production use. | NO |
| MEDIUM | `skills/hatch-pet/scripts/generate_pet_images.py` | 83–143 | `subprocess-external-api` | `subprocess.run(["curl", ...])` calls `https://api.openai.com/v1/images/edits` and `/generations` with `OPENAI_API_KEY` from `os.environ`. Key logged into process args visible to `ps`. Use Python's `requests` library or redirect key via stdin instead. | NO |
| MEDIUM | `skills/hatch-pet/scripts/finalize_pet_run.py` | 1–80 | `out-of-repo-write` | Writes to `~/.codex/` and accesses `os.environ.get("CODEX_HOME")`, expanding beyond the project root. Side-effects persist after run completion. | NO |
| LOW | `skills/html-ppt/scripts/render.sh` | 12 | `hardcoded-platform-path` | Chrome path hardcoded to `/Applications/Google Chrome.app/...` (macOS only). Silently fails on Linux/Windows. Add a cross-platform discovery fallback. | NO |
| LOW | `scripts/postinstall.mjs` | 1–40 | `spawnSync-shell` | Uses `spawnSync` to invoke `pnpm build`. Low risk (internal packages only) but any future addition to the package list could introduce supply-chain exposure without re-review. | NO |

---

## Bugs

These findings will cause silent registration failures or runtime misdispatch.

| ID | File | Issue | Suggested Fix |
|---|---|---|---|
| BUG-01 | `skills/html-ppt-presenter-mode-reveal/SKILL.md` | `name: html-ppt-presenter-mode` does not match folder name `html-ppt-presenter-mode-reveal`. The master `skills/html-ppt/SKILL.md` references this as `presenter-mode-reveal`; daemon will register the wrong name and the full-deck template will never activate. | Change `name` to `html-ppt-presenter-mode-reveal` |
| BUG-02 | `skills/saas-landing/SKILL.md` + `docs/examples/saas-landing-skill/SKILL.md` | Both files declare `name: saas-landing`. Whichever loads second silently shadows the first. The daemon skill registry requires unique names. | Rename the example to `saas-landing-example` or move it out of skills-loadable paths |

---

## Security Fixes

Addressing MEDIUM and LOW findings (HIGH was a false positive).

| Severity | File | Fix |
|---|---|---|
| MEDIUM | `skills/html-ppt/scripts/render.sh:55` | Gate `--no-sandbox` behind `CHROME_NO_SANDBOX=1` env var; default off |
| MEDIUM | `skills/hatch-pet/scripts/generate_pet_images.py:83–143` | Replace `subprocess.run(["curl", ...])` with Python `requests` library; pass `OPENAI_API_KEY` via header dict, never via process args |
| MEDIUM | `skills/hatch-pet/scripts/finalize_pet_run.py` | Confine writes to `$CODEX_HOME` only when that env var is explicitly set; document the side-effect in SKILL.md output contract |
| LOW | `skills/html-ppt/scripts/render.sh:12` | Add cross-platform Chrome discovery: check `google-chrome`, `chromium-browser`, and macOS path in order |
| LOW | `scripts/postinstall.mjs` | Add a comment listing the exact allowed packages; add a lint check (e.g., `check-residual-js`) to catch unauthorized additions |

---

## Quality Issues

| File | Score | Issue | Rule | Penalty |
|---|---|---|---|---|
| `skills/editorial-collage-deck/SKILL.md` | 78 | `od` block fields scattered across body rather than structured frontmatter; `triggers` absent from YAML header | R01 | −22 |
| `skills/pptx-html-fidelity-audit/SKILL.md` | 78 | `od` block contains only `mode` and `scenario`; missing `platform`, `preview`, `design_system`; no explicit output contract section | R01, R10 | −22 |
| `skills/invoice/SKILL.md` | 83 | 4-bullet workflow is insufficient for an output as structured as an invoice; output contract does not specify field list or file format; vague: "some", "appropriate" | R10, R15 | −17 |
| `skills/meeting-notes/SKILL.md` | 83 | 3-bullet workflow; output contract missing required field inventory; vague: "some", "relevant" | R10, R15 | −17 |
| `skills/pm-spec/SKILL.md` | 83 | 4-bullet workflow; no output schema for the spec document; vague: "some", "appropriate" | R10, R15 | −17 |
| `skills/team-okrs/SKILL.md` | 83 | 3-bullet workflow; output contract omits OKR structure; vague: "some" | R10, R15 | −17 |
| `skills/audio-jingle/SKILL.md` | 85 | No artifact tag in output contract — skill dispatches to external tool without specifying the returned artifact shape; vague: "some", "various" | R10, R15 | −15 |
| `skills/image-poster/SKILL.md` | 85 | Explicitly suppresses `<artifact>` tag emission without documenting the alternative delivery path; vague: "some", "various" | R10, R15 | −15 |
| `skills/video-shortform/SKILL.md` | 85 | Inline dispatch with no standalone output contract; consumer cannot determine artifact type without reading dispatcher | R10 | −15 |
| `skills/web-prototype-taste-brutalist/SKILL.md` | 87 | No `triggers` or `od` block — pure style reference; acceptable intent but undocumented as a non-dispatchable reference skill | R01, R05 | −13 |
| `skills/html-ppt-taste-brutalist/SKILL.md` | 89 | No `triggers` or `od` block — pure style reference (same pattern as above) | R01, R05 | −11 |
| `skills/html-ppt-taste-editorial/SKILL.md` | 89 | No `triggers` or `od` block — pure style reference | R01, R05 | −11 |
| `skills/web-prototype-taste-editorial/SKILL.md` | 88 | No `triggers` or `od` block — pure style reference | R01, R05 | −12 |
| `skills/web-prototype-taste-soft/SKILL.md` | 88 | No `triggers` or `od` block — pure style reference | R01, R05 | −12 |
| `skills/html-ppt-course-module/SKILL.md` (×14 focused-entry skills) | 88 | All 14 focused-entry html-ppt skills lack a standalone output contract; they delegate to the master skill without documenting the delegation explicitly; no `od.example_prompt` | R10 | −12 |
| `skills/guizang-ppt/SKILL.md` | 92 | `name: magazine-web-ppt` does not match folder name `guizang-ppt`; inconsistency will confuse skill registry lookups even if not a hard collision | R01 | −8 |
| `skills/hatch-pet/SKILL.md` | 93 | Script paths in workflow partially assume Codex environment; cross-environment portability not documented; vague: "some", "appropriate" | R15, R20 | −7 |
| `skills/hyperframes/SKILL.md` | 93 | Dispatch output is partially implicit; the artifact hand-off from the hyperframes engine is not contracted; vague: "some" | R10, R15 | −7 |
| `CLAUDE.md` | 80 | Single-line `@AGENTS.md` redirect; acceptable for the actual instruction content (delegated to AGENTS.md), but provides no NLPM metadata or project summary for skill-discovery indexing | R01 | −20 |

---

## Cross-Component

| Issue | Files Affected | Impact |
|---|---|---|
| **BUG-01 propagated:** The master `skills/html-ppt/SKILL.md` full-deck template lookup references `presenter-mode-reveal` by that exact key; the registered skill name `html-ppt-presenter-mode` will never match. All users of the presenter template get a silent fallback. | `skills/html-ppt/SKILL.md`, `skills/html-ppt-presenter-mode-reveal/SKILL.md` | High — runtime template misdispatch |
| **Focused-entry delegation contract:** 14 focused-entry skills route to the master `html-ppt` skill, but none documents the delegation. If the master skill is renamed or removed, all 14 silently break. The delegation should be declared in each focused-entry's frontmatter (e.g., `od.delegates_to: html-ppt`). | All 14 `skills/html-ppt-*/SKILL.md` files | Medium — invisible coupling |

---

## Recommendation

**REVIEW**

The repository is a high-quality, production-grade skill library (91/100 NL Score). The majority of skills are exemplary. Two bugs require immediate fixes before any daemon release:

1. Fix `name: html-ppt-presenter-mode` → `html-ppt-presenter-mode-reveal` (BUG-01).
2. Deduplicate `name: saas-landing` between `skills/` and `docs/examples/` (BUG-02).

Security posture is acceptable — no Critical findings, the sole HIGH was a confirmed false positive. The three MEDIUM findings in `hatch-pet` scripts and `render.sh` should be remediated before the hatch-pet skill is enabled in any shared or cloud environment.

No contribution is blocked. After bugs are fixed, this repo is a candidate for `contribute-approved`.
