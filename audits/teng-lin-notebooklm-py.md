# NLPM Audit: teng-lin/notebooklm-py
**Date**: 2026-04-06  |  **Artifacts**: 2  |  **Strategy**: single
**NL Score**: 99/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 1  |  **Security Findings**: 2

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| SKILL.md | skill | 98/100 | Vague quantifier: "vary significantly" before processing-time table (-2) |
| CLAUDE.md | system-instructions | 100/100 | None |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 0 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts (scripts/) | 19 Python files |
| MCP configs | 0 |
| Package manifests | pyproject.toml |
| Desktop extension launcher | desktop-extension/run_server.py |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | CRITICAL (FP) | desktop-extension/run_server.py | 97 | curl-pipe-sh | **FALSE POSITIVE** — `curl … \| sh` appears inside a Python string literal printed to stderr as a help message when `uvx` is not found. The string is never executed; the actual subprocess call on line 110 uses `subprocess.run(cmd, shell=False)` with a fixed argv list. |
| 2 | MEDIUM | src/notebooklm/_auth/refresh.py | 306 | shell-true-opt-in | `NOTEBOOKLM_REFRESH_CMD_USE_SHELL=1` enables `shell=True` execution of the user-controlled `NOTEBOOKLM_REFRESH_CMD` env-var string, creating a shell injection surface when the env var is sourced from untrusted CI config or container files. Default is `shell=False`; opt-in is documented with a SECURITY note in the docstring. |

## Bugs (PR-worthy)
No bugs found.

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | src/notebooklm/_auth/refresh.py | `NOTEBOOKLM_REFRESH_CMD_USE_SHELL=1` opt-in emits no runtime warning, so operators who inadvertently set it in a broad env file may not notice the elevated risk | Emit a `warnings.warn()` or stderr notice when `shell=True` mode is activated at runtime, pointing operators to the SECURITY note in the docs |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | SKILL.md | "Processing times vary **significantly**." — vague quantifier immediately preceding the processing-time table; the table provides the specifics, but the intro sentence adds noise | -2 |

## Cross-Component
CLAUDE.md and SKILL.md serve complementary audiences (contributors vs. AI agents) without contradiction. All command syntax is consistent between files. CLAUDE.md cross-references `docs/architecture.md`, `docs/cli-reference.md`, `docs/python-api.md#concurrency-contract`, and `docs/development.md` — all are plausible paths in the repo tree and no 404 was detected. SKILL.md links to the GitHub installation guide and a Google support page; both URLs are syntactically valid external references. No orphaned components, stale counts, or terminology drift detected across the two artifacts.

## Recommendation
CLEAR — no true Critical or High security findings (the critical pre-scan match was a false positive in a help-text string); one MEDIUM finding (documented opt-in `shell=True`) suitable for a suggestion issue rather than a blocking PR. The single quality deduction is cosmetic. No NL bugs. The repo is well-structured and ready for standard contribution workflows.
