# NLPM Audit: Chat2AnyLLM/awesome-claude-plugins
**Date**: 2026-04-06  |  **Artifacts**: 10  |  **Strategy**: single
**NL Score**: 69/100
**Security**: BLOCKED
**Bugs**: 10  |  **Quality Issues**: 11  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude/commands/speckit.specify.md | command | 58 | 6 vague quantifiers (reasonable ×3, appropriate, user-friendly, meaningful): −12 |
| .claude/commands/speckit.tasks.md | command | 68 | Missing `name:` frontmatter (−25), missing allowed-tools (−5) |
| .claude/commands/speckit.analyze.md | command | 70 | Missing `name:` frontmatter (−25), missing allowed-tools (−5) |
| .claude/commands/speckit.checklist.md | command | 70 | Missing `name:` frontmatter (−25), missing allowed-tools (−5) |
| .claude/commands/speckit.clarify.md | command | 70 | Missing `name:` frontmatter (−25), missing allowed-tools (−5) |
| .claude/commands/speckit.constitution.md | command | 70 | Missing `name:` frontmatter (−25), missing allowed-tools (−5) |
| .claude/commands/speckit.implement.md | command | 70 | Missing `name:` frontmatter (−25), missing allowed-tools (−5) |
| .claude/commands/speckit.plan.md | command | 70 | Missing `name:` frontmatter (−25), missing allowed-tools (−5) |
| .claude/commands/speckit.taskstoissues.md | command | 73 | Missing `name:` frontmatter (−25); has allowed-tools ✅ |
| CLAUDE.md | project-context | 75 | Malformed commands section with unfilled template placeholders (−20), duplicate entries (−5) |

**Weighted average**: (70+70+70+70+70+70+58+68+73+75) / 10 = **69/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 2 |
| Medium | 1 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | None |
| Scripts (Python) | scripts/\_\_init\_\_.py, scripts/config.py, scripts/marketplace\_scraper.py, scripts/metadata\_catalog.py |
| Scripts (Bash) | .specify/scripts/bash/check-prerequisites.sh, .specify/scripts/bash/common.sh, .specify/scripts/bash/create-new-feature.sh, .specify/scripts/bash/setup-plan.sh, .specify/scripts/bash/update-agent-context.sh, run\_tests.sh |
| MCP configs | None |
| Package manifests | requirements.txt |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Critical | scripts/metadata_catalog.py | 14 | SEC-credential-exfil | `_jget()` appends `Authorization: Bearer {token}` to every HTTP request, including calls with config-sourced `source["url"]` (line 22); no domain validation ensures token only goes to github.com; a malicious or compromised config.yaml (or the upstream awesome-repo-configs source it fetches from) can direct the GITHUB_TOKEN to an attacker-controlled host |
| 2 | High | .specify/scripts/bash/check-prerequisites.sh | 82 | SEC-new-function-eval | `eval $(get_feature_paths)` evaluates a heredoc that interpolates `$SPECIFY_FEATURE` env var via single-quoted assignment lines; a value containing `'` breaks heredoc single-quote delimiters and injects arbitrary shell commands; also reachable via a crafted git branch name if git's naming restrictions are bypassed |
| 3 | High | .specify/scripts/bash/update-agent-context.sh | 56 | SEC-new-function-eval | Same `eval $(get_feature_paths)` pattern; additionally writes output to CLAUDE.md and all other agent context files, meaning successful injection could backdoor agent context files served to developers |
| 4 | Medium | scripts/marketplace_scraper.py | 92 | SEC-path-traversal | `--output` CLI argument is passed directly to `open(output_file, 'w')` with no path validation; a value like `../../.claude/commands/evil.md` writes outside the intended directory |
| 5 | Low | requirements.txt | 1 | SEC-unpinned-semver | `PyYAML>=6.0` uses a non-pinned lower-bound constraint; future major-version releases or a PyPI compromise could silently introduce breaking changes or malicious code |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude/commands/speckit.analyze.md | Missing `name:` frontmatter field | Command unindexable by NLPM registry and tooling that requires explicit name metadata |
| 2 | .claude/commands/speckit.checklist.md | Missing `name:` frontmatter field | Same as above |
| 3 | .claude/commands/speckit.clarify.md | Missing `name:` frontmatter field | Same as above |
| 4 | .claude/commands/speckit.constitution.md | Missing `name:` frontmatter field | Same as above |
| 5 | .claude/commands/speckit.implement.md | Missing `name:` frontmatter field | Same as above |
| 6 | .claude/commands/speckit.plan.md | Missing `name:` frontmatter field | Same as above |
| 7 | .claude/commands/speckit.specify.md | Missing `name:` frontmatter field | Same as above |
| 8 | .claude/commands/speckit.tasks.md | Missing `name:` frontmatter field | Same as above |
| 9 | .claude/commands/speckit.taskstoissues.md | Missing `name:` frontmatter field | Same as above |
| 10 | CLAUDE.md | Commands section contains unfilled template placeholder `[ONLY COMMANDS FOR ACTIVE TECHNOLOGIES]` repeated four times between valid command fragments | Commands section is non-functional; developers receive invalid build/test instructions |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/marketplace_scraper.py | `--output` arg allows path traversal to files outside the repo | Validate output path is within repo root: `os path.abspath(output_file).startswith(os.getcwd())` |
| 2 | requirements.txt | `PyYAML>=6.0` unpinned | Pin to exact known-good version (e.g., `PyYAML==6.0.2`) |

*(Critical/High findings — credential exfiltration and eval injection — require private security disclosure; do not open public PRs for those.)*

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .claude/commands/speckit.analyze.md | Missing `allowed-tools` declaration; command runs Bash and Read but does not constrain its tool surface | −5 |
| 2 | .claude/commands/speckit.checklist.md | Missing `allowed-tools`; uses Bash, Read, and Write | −5 |
| 3 | .claude/commands/speckit.clarify.md | Missing `allowed-tools`; uses Bash, Read, and Write | −5 |
| 4 | .claude/commands/speckit.constitution.md | Missing `allowed-tools`; uses Bash, Read, and Write | −5 |
| 5 | .claude/commands/speckit.implement.md | Missing `allowed-tools`; uses Bash, Read, Write, and Edit | −5 |
| 6 | .claude/commands/speckit.plan.md | Missing `allowed-tools`; uses Bash, Read, and Write | −5 |
| 7 | .claude/commands/speckit.specify.md | Missing `allowed-tools`; uses Bash, Read, and Write | −5 |
| 8 | .claude/commands/speckit.tasks.md | Missing `allowed-tools`; uses Bash, Read, and Write | −5 |
| 9 | .claude/commands/speckit.specify.md | Vague quantifiers: "reasonable" (×3, lines 83/219/229), "appropriate" (line 232), "user-friendly" (line 232), "meaningful" (line 28) — six instances each suppress a measurable criterion | −12 |
| 10 | .claude/commands/speckit.tasks.md | Vague quantifier: "specific enough" (line 65) — no objective threshold stated | −2 |
| 11 | CLAUDE.md | Active Technologies and Recent Changes sections contain three near-identical duplicate entries from repeated auto-generation runs | −5 |

## Cross-Component

**Systematic name-field gap**: All 9 `.claude/commands/speckit.*.md` files share the same missing-`name:` defect. This indicates the command scaffolding template (likely `.specify/templates/` or the `update-agent-context.sh` generation path) omits the `name:` key. A single template fix would resolve all 9 bugs simultaneously.

**Root cause of CLAUDE.md malformation**: `update-agent-context.sh` line 337 uses the sed substitution `s|\[ONLY COMMANDS FOR ACTIVE TECHNOLOGIES\]|$commands|` without a `g` (global) flag. The agent-file template contains this placeholder multiple times; each successive script run replaces only the first occurrence, resulting in the interleaved malformed content visible in CLAUDE.md. Cross-component causal link: the generation script bug directly caused the CLAUDE.md content bug (Bug #10).

**Reference consistency**: All inter-command `handoffs:` references (`speckit.plan`, `speckit.clarify`, `speckit.specify`, `speckit.tasks`, `speckit.analyze`, `speckit.implement`, `speckit.checklist`) resolve to actual files on disk. No orphaned or broken handoff references found.

**Script references consistent**: All six commands that call `.specify/scripts/bash/check-prerequisites.sh` reference the same path; the script exists on disk. No broken script references found.

## Recommendation

BLOCKED — do not submit PRs. File private security report.

Two security issues require private disclosure before any public contribution:

1. **Critical** — `scripts/metadata_catalog.py`: GITHUB_TOKEN is sent to all URLs in `_jget()` including arbitrary config-sourced source URLs; no domain validation. In CI, a malicious or compromised `config.yaml` (or the upstream `awesome-repo-configs` repository it fetches from) can exfiltrate the workflow's GITHUB_TOKEN. Private fix: validate all fetched URLs are in the `api.github.com` / `raw.githubusercontent.com` domain before attaching the Authorization header.

2. **High** — `.specify/scripts/bash/{check-prerequisites.sh,update-agent-context.sh}`: `eval $(get_feature_paths)` on content interpolated from the `$SPECIFY_FEATURE` environment variable; unescaped single quotes in the env var break heredoc quoting and enable shell injection. Private fix: replace `eval $(...)` with `source <(get_feature_paths)` and use `declare` for variable assignment, or escape single quotes before interpolation.

After private fixes are merged, the NL quality bugs (missing `name:` on all 9 commands) and medium/low security fixes (path-traversal guard, pinned dependency) are clean PR candidates.
