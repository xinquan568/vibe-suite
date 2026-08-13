# NLPM Audit: stablyai/orca
**Date**: 2026-04-20  |  **Artifacts**: 9  |  **Strategy**: single
**NL Score**: 96/100
**Security**: REVIEW
**Bugs**: 1  |  **Quality Issues**: 7  |  **Security Findings**: 4

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/orca-cli/SKILL.md | skill | 88 | Broken doc references (3 missing files) + 6 vague quantifiers |
| .agents/skills/typescript/SKILL.md | skill | 94 | "complex" and "when applicable" vague quantifiers (-6) |
| CLAUDE.md | config | 95 | Minor vague language ("non-obvious") |
| .agents/skills/auto-review-fix/SKILL.md | skill | 96 | "relevant" vague quantifiers (-4) |
| .agents/skills/react-useeffect/SKILL.md | skill | 96 | "expensive" and "when possible" vague quantifiers (-4) |
| .agents/skills/auto-pr-merge/SKILL.md | skill | 98 | "when appropriate" vague quantifier (-2) |
| .agents/skills/auto-submit/SKILL.md | skill | 98 | "catastrophically" vague qualifier (-2) |
| .agents/skills/electron/SKILL.md | skill | 100 | None |
| .claude/skills/review-and-submit/SKILL.md | skill | 100 | None |

**Weighted average**: (88+94+95+96+96+98+98+100+100) / 9 = **96/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 |
| Medium | 1 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Scripts | scripts/build-relay.mjs, config/scripts/run-electron-vite-dev.mjs, config/scripts/run-electron-vite-build.mjs, config/scripts/verify-macos-release-env.mjs, config/scripts/terminal-e2e-helpers.mjs |
| Package manifest | package.json |
| Hooks | None |
| MCP configs | None |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | HIGH | package.json | 32 | postinstall script | `postinstall` runs `pnpm rebuild electron && electron-builder install-app-deps` on every `pnpm install`. Standard Electron practice to rebuild native modules (node-pty, @parcel/watcher) for the correct Electron ABI — not malicious, but matches HIGH postinstall pattern. Verify no additional commands were added. |
| 2 | MEDIUM | config/scripts/run-electron-vite-dev.mjs | 15 | env var overrides binary path | `ORCA_ELECTRON_VITE_CLI` env var can substitute the electron-vite CLI binary. Intentional for tests (comment present), but allows process injection if attacker controls the environment. |
| 3 | LOW | package.json | 45–100 | unpinned dependency versions | All runtime and dev dependencies use `^` semver constraints, enabling automatic minor/patch updates. Increases supply chain attack surface. |
| 4 | LOW | package.json | 41–44 | release scripts auto-push | `release:rc/patch/minor/major` scripts run `git push --follow-tags` automatically. Unintended invocation would push a version tag to origin. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/orca-cli/SKILL.md | References three non-existent docs: `docs/orca-cli-focused-v1-status.md`, `docs/orca-cli-v1-spec.md`, `docs/orca-runtime-layer-design.md` (lines 178–180). None of these files exist in the repository. | Agents following the skill will hit dead links when trying to resolve ambiguous CLI behavior, silently losing important guidance. |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | config/scripts/run-electron-vite-dev.mjs | `ORCA_ELECTRON_VITE_CLI` overrides binary without validation | Add a check that the resolved path exists and is within the project root, or restrict to test environments via a `NODE_ENV === 'test'` guard. |
| 2 | package.json | Unpinned `^` dependency versions across all deps | Consider pinning critical native dependencies (`node-pty`, `electron`, `@parcel/watcher`) to exact versions; use `pnpm audit` in CI to catch vulnerable ranges. |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/orca-cli/SKILL.md | "significant checkpoint" (lines 93, 157), "meaningful progress checkpoints" (line 93), "meaningful checkpoint" (line 157), "meaningful implementation slice" (line 158), "whenever useful" (line 5) — 6 vague quantifiers | -12 |
| 2 | .agents/skills/typescript/SKILL.md | "complex type definitions" (line 14), "when applicable" (lines 42, 43) — 3 vague quantifiers | -6 |
| 3 | .agents/skills/auto-review-fix/SKILL.md | "relevant to that review type" (line 216), "relevant files only" (table) — 2 vague quantifiers | -4 |
| 4 | .agents/skills/react-useeffect/SKILL.md | "Expensive calculations" (line 12), "when possible" (line 25) — 2 vague quantifiers | -4 |
| 5 | .agents/skills/auto-pr-merge/SKILL.md | "when appropriate" (line 91) — 1 vague quantifier | -2 |
| 6 | .agents/skills/auto-submit/SKILL.md | "fails catastrophically" (line 47) — 1 vague qualifier (no observable threshold defined) | -2 |
| 7 | CLAUDE.md | "non-obvious constraint" (line 7) — subjective threshold for when to add a comment | -2 |

## Cross-Component
- **Broken references in orca-cli**: The skill's "References" section (lines 178–180) points to three docs (`docs/orca-cli-focused-v1-status.md`, `docs/orca-cli-v1-spec.md`, `docs/orca-runtime-layer-design.md`) that do not exist in the repository. These are likely planned or deleted docs. The skill is otherwise self-contained and functional.
- **CLAUDE.md → AGENTS.md**: The `See also: AGENTS.md` reference resolves correctly; `AGENTS.md` exists.
- **auto-submit orchestrates auto-review-fix + auto-pr-merge**: Both skills exist and their names match the invocations in auto-submit. Skill chain is consistent.
- **review-and-submit references create-pr**: This sub-skill reference cannot be verified from the scanned artifacts alone; `create-pr` is not in the audited file list but is expected to exist based on usage in both `auto-pr-merge` and `review-and-submit`.
- **typescript/SKILL.md → references/**: All 46 referenced files in `references/` exist. Full integrity confirmed.
- **react-useeffect/SKILL.md → anti-patterns.md, alternatives.md**: Both referenced files exist in the same directory.

## Recommendation
REVIEW — submit NL fix PRs for Bug #1 (broken orca-cli doc references). Flag Security Finding #1 (postinstall) as a known-safe Electron pattern in a tracking issue rather than private disclosure — it is standard boilerplate, not a vulnerability. Implement Security Fixes #1 and #2 as low-priority PRs. The postinstall HIGH pattern match should be annotated in the repo's security notes to prevent false positives on future audits.
