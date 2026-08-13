# NLPM Audit: refly-ai/refly
**Date**: 2026-05-05  |  **Artifacts**: 4  |  **Strategy**: single
**NL Score**: 89/100
**Security**: BLOCKED
**Bugs**: 0  |  **Quality Issues**: 6  |  **Security Findings**: 6

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| packages/cli/commands/refly-login.md | Command | 75 | Missing allowed-tools, output format, and empty-input handling |
| packages/cli/commands/refly-upgrade.md | Command | 85 | Missing allowed-tools and output format |
| packages/cli/commands/refly-status.md | Command | 95 | Missing allowed-tools |
| packages/cli/skill/SKILL.md | Skill | 100 | — |

Weighted average: (75 + 85 + 95 + 100) / 4 = **89/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 3 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts (.sh) | scripts/wait-for-container-health.sh, scripts/cli-deploy/deploy-cli.sh, scripts/cli-deploy/quick-start.sh, deploy/docker/elasticsearch-entrypoint.sh, apps/api/load-tests/run-all.sh, apps/web/scripts/analyze-workflow-chunks.sh, packages/sandbox-agent/verify-setup.sh |
| Scripts (.js) | scripts/pm2-api-wrapper.js, scripts/check-i18n-consistency.js, scripts/cleanup-node-modules.js, scripts/copy-package-dist.js, scripts/upload-config.js, deploy/docker/prepare-deploy.js, apps/api/scripts/build.js, apps/web/scripts/generate-sitemap.js, docs/scripts/convert-webp.js |
| Scripts (.py) | specs/current/ptc/scripts/ptc_common.py, specs/current/ptc/scripts/ptc_debug_billing.py, specs/current/ptc/scripts/ptc_debug_calling.py, specs/current/ptc/scripts/ptc_verify.py |
| MCP configs | 0 |
| Package manifests | package.json, docs/package.json |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | High | scripts/check-i18n-consistency.js | 91 | eval-equivalent (new Function) | `new Function(\`return ${str}\`)()` evaluates translation file content as JavaScript; if a translation file is maliciously crafted, arbitrary code executes in the developer's environment |
| 2 | High | package.json | 42 | postinstall-script | `"prepare": "husky"` runs automatically on `npm install`; standard husky pattern but executes code on install — see false_positive note in sidecar |
| 3 | Medium | scripts/upload-config.js | 6–11 | credential-env-var | MinIO access key and secret key sourced from `MINIO_EXTERNAL_ACCESS_KEY` / `MINIO_EXTERNAL_SECRET_KEY`; if env is misconfigured or leaked, credentials are exposed alongside the config upload |
| 4 | Medium | specs/current/ptc/scripts/ptc_common.py | 155 | credential-env-var | Full database connection URL read from `REFLY_DATABASE_URL_LOCAL`; embedded credentials in a URL string are easily logged or leaked |
| 5 | Medium | scripts/cli-deploy/deploy-cli.sh | 23 | env-var-repo-override | `REFLY_REPO` env var controls the git clone URL; an attacker who can set this var could redirect the clone to a malicious repository before install |
| 6 | Low | package.json | 47–63 | unpinned-semver | Most devDependencies use `^` ranges (e.g., `"@biomejs/biome": "^1.9.0"`, `"commitizen": "^4.2.4"`, `"husky": "^9.1.6"`); minor/patch updates resolve automatically, allowing supply-chain drift |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| — | — | No bugs found | — |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/upload-config.js | MinIO credentials in env vars without validation | Add a guard at startup: check that `MINIO_EXTERNAL_ACCESS_KEY` and `MINIO_EXTERNAL_SECRET_KEY` are non-empty and fail-fast with a clear error rather than passing empty strings to the client |
| 2 | specs/current/ptc/scripts/ptc_common.py | Database URL contains embedded credentials | Document that `REFLY_DATABASE_URL_LOCAL` must not be logged; consider redacting the URL in error output (replace credentials segment before printing) |
| 3 | scripts/cli-deploy/deploy-cli.sh | `REFLY_REPO` override allows arbitrary clone target | Add a URL allowlist check (e.g., assert the URL starts with `https://github.com/refly-ai/`) before running `git clone` |
| 4 | package.json | Unpinned semver ranges for devDependencies | Pin critical tools (`@biomejs/biome`, `husky`, `turbo`) to exact versions and use a lockfile-only install in CI (`pnpm install --frozen-lockfile`) |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | packages/cli/commands/refly-login.md | Missing `allowed-tools` frontmatter field | -5 |
| 2 | packages/cli/commands/refly-login.md | No output format specified — success/failure messages to the user are undefined | -10 |
| 3 | packages/cli/commands/refly-login.md | No empty-input handling — what should happen if the user provides no API key and `REFLY_API_KEY` is unset? | -10 |
| 4 | packages/cli/commands/refly-status.md | Missing `allowed-tools` frontmatter field | -5 |
| 5 | packages/cli/commands/refly-upgrade.md | Missing `allowed-tools` frontmatter field | -5 |
| 6 | packages/cli/commands/refly-upgrade.md | No output format specified — success/failure messages to the user after upgrade are undefined | -10 |

## Cross-Component
- **Reference path mismatch**: `SKILL.md` §References cites `rules/execution.md`, `rules/workflow.md`, etc., matching the deployed path `~/.refly/skills/base/rules/`. However, the source files live at `packages/cli/skill/references/*.md` (directory named `references/`, not `rules/`). The `refly upgrade` command is responsible for copying these files into the correct deployed location. If the install/upgrade logic maps `references/` → `rules/` correctly, there is no runtime problem — but the mismatch between source layout and documented deployed layout is a silent fragility: anyone browsing the repo sees `references/`, anyone reading SKILL.md sees `rules/`.
- **Commands consistently omit `allowed-tools`**: All three command files lack this field. Claude Code will not restrict tool usage, which is benign for read-only CLI invocations but leaves the commands under-specified.

## Recommendation
BLOCKED — do not submit PRs. File a private security report for the HIGH finding in `scripts/check-i18n-consistency.js` (eval-equivalent code execution via `new Function()` on translation file content). Once that is addressed or confirmed as acceptable risk, submit PRs for the Medium/Low security fixes and quality improvements listed above. The `prepare: husky` HIGH match is standard practice and can be treated as a false positive after maintainer confirmation.
