# NLPM Audit: avifenesh/agentsys
**Date**: 2026-04-06  |  **Artifacts**: 32  |  **Strategy**: batched
**NL Score**: 97/100
**Security**: CLEAR
**Bugs**: 2  |  **Quality Issues**: 4  |  **Security Findings**: 6

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `.kiro/skills/web-auth/SKILL.md` | Skill | 90 | Hardcoded developer path `/Users/avifen/.agentsys/` breaks on other machines |
| `.kiro/skills/web-browse/SKILL.md` | Skill | 90 | Hardcoded developer path `/Users/avifen/.agentsys/` breaks on other machines |
| `.claude-plugin/plugin.json` | Manifest | 90 | Non-NL artifact; minimal content |
| `CLAUDE.md` | Project memory | 92 | "Non-trivial changes" (Rule 4) is slightly vague; otherwise well-structured |
| `meta/skills/maintain-cross-platform/SKILL.md` | Skill | 95 | Oversized (~1000 lines); recommended max 500 |
| `.kiro/skills/deslop/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/consult/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/enhance-hooks/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/enhance-cross-file/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/enhance-prompts/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/enhance-docs/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/enhance-orchestrator/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/validate-delivery/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/enhance-agent-prompts/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/learn/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/drift-analysis/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/debate/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/enhance-skills/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/enhance-plugins/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/enhance-claude-memory/SKILL.md` | Skill | 97 | Clean |
| `.kiro/skills/orchestrate-review/SKILL.md` | Skill | 98 | Minor: "typically indicates" (line 63) |
| `.kiro/skills/repo-intel/SKILL.md` | Skill | 98 | Minor: "for better analysis" slightly vague |
| `.kiro/skills/perf-code-paths/SKILL.md` | Skill | 98 | Clean |
| `.kiro/skills/perf-benchmarker/SKILL.md` | Skill | 98 | Clean |
| `.kiro/skills/sync-docs/SKILL.md` | Skill | 98 | Minor: "better doc sync accuracy" slightly vague |
| `.kiro/skills/perf-baseline-manager/SKILL.md` | Skill | 98 | Clean |
| `.kiro/skills/perf-analyzer/SKILL.md` | Skill | 98 | Clean |
| `.kiro/skills/perf-theory-gatherer/SKILL.md` | Skill | 98 | Clean |
| `.kiro/skills/discover-tasks/SKILL.md` | Skill | 98 | Clean |
| `.kiro/skills/perf-theory-tester/SKILL.md` | Skill | 98 | Clean |
| `.kiro/skills/perf-profiler/SKILL.md` | Skill | 98 | Clean |
| `.kiro/skills/perf-investigation-logger/SKILL.md` | Skill | 98 | Clean |

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 3 |
| Low | 3 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks | 0 (no `.claude/hooks/` files found) |
| Scripts (JS) | 23 files in `scripts/` |
| Scripts (SH) | 0 |
| MCP configs | 0 (no `.mcp.json`) |
| Package manifests | 1 (`package.json`) |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | `package.json` | 41 | postinstall-equivalent script | `"prepare"` runs `node bin/dev-cli.js setup-hooks` on every `npm install`, automatically writing git hook files to `.git/hooks/`. Normal for dev tooling but installs executable hooks into developer environments without explicit consent. |
| 2 | Medium | `scripts/dev-install.js` | 573 | Runtime package install | `execSync('npm install --production', { cwd: AGENTSYS_DIR })` fetches and installs npm packages at `~/.agentsys/` outside the repo on every invocation of the installer. |
| 3 | Medium | `scripts/dev-install.js` | 329–341 | File writes outside repo | Writes to `~/.claude/settings.json` modifying `enabledPlugins`; also copies entire source tree to `~/.agentsys/` and executes `rm -rf` on it. Both operations target user home directories outside the project root. |
| 4 | Low | `package.json` | 40 | Broad git staging | `"version"` lifecycle script runs `git add -A`, staging all changes rather than only the version-bumped files. Could inadvertently commit unrelated changes. |
| 5 | Low | `package.json` | 83–92 | Unpinned dependency versions | `"agentsys": "^5.0.0"`, `"js-yaml": "^4.1.1"`, `"jest": "^29.7.0"` — caret ranges allow minor/patch updates that could introduce supply-chain changes. |
| 6 | Low | `.kiro/skills/web-auth/SKILL.md`, `.kiro/skills/web-browse/SKILL.md` | 29, 40 (web-auth); 25 (web-browse) | Hardcoded absolute path | Commands reference `/Users/avifen/.agentsys/plugins/web-ctl/scripts/web-ctl.js` — a developer-specific home directory. If an agent executes these commands literally on another machine, the path does not exist, or could resolve to an attacker-controlled file if `/Users/avifen/` exists on the target system. |

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `.kiro/skills/web-auth/SKILL.md` | Hardcoded path `/Users/avifen/.agentsys/plugins/web-ctl/scripts/web-ctl.js` throughout the action examples — breaks on all machines except the original developer's. The dev-install.js transformer rewrites paths for Codex, but Kiro installs directly from the source SKILL.md. | Agents following this skill on other machines will fail to execute any browser auth command. |
| 2 | `.kiro/skills/web-browse/SKILL.md` | Same hardcoded `/Users/avifen/.agentsys/` path used in every command example in Usage, Action Reference, Macros, and Workflow Pattern sections. | All headless browser actions will fail on non-developer machines. |

## Security Fixes (PR-worthy, Medium/Low only)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `package.json` | `prepare` script installs git hooks silently | Add comment in package.json documenting the hook installation; optionally guard with `if [ -d .git ]; then` inside the script (already done) — document this behavior in README. |
| 2 | `scripts/dev-install.js` | `npm install --production` with no registry pinning | Add `--registry` flag or `.npmrc` with a pinned registry to prevent supply-chain substitution. |
| 3 | `package.json` | `version` script uses `git add -A` | Replace with `git add package.json` to stage only the version-changed file. |
| 4 | `package.json` | Unpinned `^` dependency versions | Pin `js-yaml` to an exact version (e.g., `4.1.1`). For devDependencies, range versions are lower risk but consider pinning for reproducibility. |
| 5 | `.kiro/skills/web-auth/SKILL.md`, `.kiro/skills/web-browse/SKILL.md` | Hardcoded `/Users/avifen/` home path | Replace hardcoded path with a placeholder variable (e.g., `${AGENTSYS_DIR}`) and document that the Kiro installer must substitute this at install time, or use the same transform applied to Codex skills. |

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `meta/skills/maintain-cross-platform/SKILL.md` | Skill exceeds 500 lines (~1000 lines) — the enhance-skills skill flags this as a MEDIUM content-scope issue. Detailed reference content (release process, pitfalls, installer deep-dive) could move to a `reference/` subdirectory. | -5 |
| 2 | `.kiro/skills/orchestrate-review/SKILL.md` | Line 63: `"20+ files typically indicates cross-module changes"` — "typically" is a vague quantifier that reduces determinism. | -2 |
| 3 | `.kiro/skills/repo-intel/SKILL.md` | "For better analysis, run: /repo-intel init" — "better" is a mild vague quantifier; prefer "accurate" or state what specifically improves. | -2 |
| 4 | `.kiro/skills/sync-docs/SKILL.md` | "better doc sync accuracy" in Phase 1.5 — same mild vague quantifier issue. | -2 |

## Cross-Component

**Positive findings:**
- All 30 skills have `name` and `description` frontmatter — no registration-breaking omissions.
- `plugin.json` version `5.8.3` aligns with `package.json` version `5.8.3` — version sync is clean.
- `CLAUDE.md` Critical Rules are well-positioned at the top (correct "lost in the middle" placement).
- The `consult/SKILL.md` and `debate/SKILL.md` share a common external-tool section and keep them consistent — good cross-skill coherence.
- `discover-tasks/SKILL.md` correctly references `AskUserQuestion` in its `allowed-tools` frontmatter.
- The perf-* skills (8 total) form a coherent pipeline: code-paths → theory-gatherer → benchmarker → profiler → theory-tester → baseline-manager → analyzer → investigation-logger. Each skill correctly defers to `docs/perf-requirements.md` as the canonical contract.

**Issues found:**
- `meta/skills/maintain-cross-platform/SKILL.md` lives in `meta/skills/` rather than in a plugin's `skills/` directory. This asymmetric location is documented within the skill itself but may cause skill-discovery tools to miss it.
- `web-auth/SKILL.md` and `web-browse/SKILL.md` share the same hardcoded path bug — a single fix to the Kiro transformer's path substitution would resolve both.
- `enhance-orchestrator/SKILL.md` references agent names (`plugin-enhancer`, `agent-enhancer`, etc.) that must exist in the plugin system — these are undeclared in the audited files, creating a latent broken-reference risk if those agents are renamed.

## Recommendation

CLEAR — submit PRs for all bugs and medium/low security fixes.

The NL quality is excellent (97/100): all 30 skills have complete frontmatter, clear trigger phrases, and defined output formats. The two web-* skills have a concrete portability bug (hardcoded developer home path) that will cause agent failures for end users on Kiro — this is the highest-priority PR. The security profile is clean with no critical or high findings; the medium findings are typical for a developer tooling package that installs itself into user home directories.
