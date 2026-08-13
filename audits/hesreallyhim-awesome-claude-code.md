# NLPM Audit: hesreallyhim/awesome-claude-code
**Date**: 2026-04-16  |  **Artifacts**: 24  |  **Strategy**: batched
**NL Score**: 89/100
**Security**: CLEAR
**Bugs**: 4  |  **Quality Issues**: 14  |  **Security Findings**: 5

---

## NL Score Summary

Artifacts consist of one custom Claude Code command and 23 CLAUDE.md project context files collected from external repositories. Scoring applied rubric proportionally: command-specific penalties (frontmatter, allowed-tools, numbered steps, empty-input handling) applied to the command; vague-quantifier and completeness penalties applied to CLAUDE.md context files.

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude/commands/evaluate-repository.md | command | 62 | No YAML frontmatter; no allowed-tools declaration |
| resources/claude.md-files/Network-Chronicles/CLAUDE.md | context | 77 | Ephemeral implementation-plan notes; vague terms |
| resources/claude.md-files/SG-Cars-Trends-Backend/CLAUDE.md | context | 84 | Vague quantifiers: "appropriate" ×3, "concise" ×2 |
| resources/claude.md-files/AVS-Vibe-Developer-Guide/CLAUDE.md | context | 86 | Sparse: missing code style and architecture overview |
| resources/claude.md-files/claude-code-mcp-enhanced/CLAUDE.md | context | 86 | Instruction-override language; vague "meaningful" ×2 |
| resources/claude.md-files/AWS-MCP-Server/CLAUDE.md | context | 86 | Vague quantifiers: "appropriate" ×3, "robust" ×1 |
| resources/claude.md-files/Basic-Memory/CLAUDE.md | context | 86 | Vague quantifiers: "appropriate" ×3, "comprehensive" ×1 |
| resources/claude.md-files/Course-Builder/CLAUDE.md | context | 86 | Vague quantifiers: "appropriate" ×3, "comprehensive" ×3 |
| resources/claude.md-files/Note-Companion/CLAUDE.md | context | 86 | Missing build commands and project structure sections |
| resources/claude.md-files/DroidconKotlin/CLAUDE.md | context | 88 | Ephemeral "Current Task" section |
| resources/claude.md-files/JSBeeb/CLAUDE.md | context | 88 | Vague quantifiers: "appropriate" ×2, "complex" ×2 |
| resources/claude.md-files/Pareto-Mac/CLAUDE.md | context | 88 | Vague quantifiers: "appropriate" ×3, "complex" ×2 |
| resources/claude.md-files/Cursor-Tools/CLAUDE.md | context | 89 | Cursor Rules frontmatter embedded mid-document; autonomy-override language |
| resources/claude.md-files/Giselle/CLAUDE.md | context | 90 | Vague quantifiers: "meaningful" ×3, "unclear" ×1 |
| resources/claude.md-files/Anthropic-Quickstarts/CLAUDE.md | context | 94 | Vague quantifiers: "appropriate" ×2, "proper" ×1 |
| resources/claude.md-files/LangGraphJS/CLAUDE.md | context | 94 | Vague quantifiers: "appropriate" ×1, "proper" ×1, "relevant" ×1 |
| resources/claude.md-files/TPL/CLAUDE.md | context | 94 | Vague quantifiers: "appropriate" ×1, "proper" ×1 |
| resources/claude.md-files/Perplexity-MCP/CLAUDE.md | context | 95 | No code style guidance for server development |
| resources/claude.md-files/Lamoom-Python/CLAUDE.md | context | 96 | Vague quantifiers: "appropriate" ×2 |
| resources/claude.md-files/SPy/CLAUDE.md | context | 96 | Mismatched quote in command example (`./venv/bin/pytest'`) |
| resources/claude.md-files/Comm/CLAUDE.md | context | 98 | Vague "Descriptive variable names" |
| resources/claude.md-files/EDSL/CLAUDE.md | context | 98 | Minor: "appropriate" logging levels |
| resources/claude.md-files/AI-IntelliJ-Plugin/CLAUDE.md | context | 98 | Vague "complex logic" in documentation rule |
| resources/claude.md-files/Guitar/CLAUDE.md | context | 100 | None |

**Weighted average**: 2145 / 24 = **89/100**

---

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 3 |
| Low | 2 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts (Python) | 57 files under `scripts/` |
| MCP configs | 0 |
| Package manifests | 0 (no package.json or requirements.txt at repo root) |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | scripts/validation/validate_links.py | 680 | External HTTP requests | `requests.head()` makes live network calls to arbitrary URLs extracted from README. URLs are not sanitized before fetch; a malformed or malicious link in the resource list could trigger SSRF to internal addresses. Scoped to link-validation workflows only. |
| 2 | Medium | scripts/resources/download_resources.py | 174 | File writes from external content | Downloads CLAUDE.md files from GitHub API and writes them to `resources/` tree. Path is derived from API response data; no explicit path-traversal check (e.g., `..` in filename). Low risk in practice because GitHub API normalizes paths, but worth asserting. |
| 3 | Medium | scripts/ticker/generate_ticker_svg.py | 56 | Unverified POST destination | `requests.post()` call at line 56; destination URL not visible in grep context. If URL is configurable or derived from data, caller controls the endpoint. |
| 4 | Low | scripts/ (multiple) | various | subprocess without input sanitization | `subprocess.run()` used with list arguments (no `shell=True`) in git_utils.py, add_category.py, create_resource_pr.py, test_regenerate_cycle.py. Safe as written; noted because argument values sometimes derive from external data (filenames, branch names). |
| 5 | Low | scripts/ (all) | — | No pinned dependency manifest | No `requirements.txt` or `pyproject.toml` at repo root. Scripts import `requests`, `github` (PyGithub), and others. Unpinned installs in CI could pull breaking or compromised versions. |

---

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude/commands/evaluate-repository.md | No YAML frontmatter — missing `name` and `description` fields | Limits discoverability in Claude Code; command description not shown in `/help` or command picker |
| 2 | .claude/commands/evaluate-repository.md | No `allowed-tools` declaration | Claude Code cannot enforce tool restrictions; any tool may be invoked during evaluation |
| 3 | resources/claude.md-files/DroidconKotlin/CLAUDE.md | "Current Task: Cleaning up the app and prepping for release" — ephemeral task state committed to a shared context file | Stale instructions drift into every future session; readers misled by out-of-date task context |
| 4 | resources/claude.md-files/Cursor-Tools/CLAUDE.md | Cursor Rules frontmatter fragments (`---\ndescription: Global Rule…\nglobs: *,**/*`) embedded at lines 55–63 inside body prose | Malformed for both CLAUDE.md and Cursor Rules parsers; fragments will be read as plain text by Claude Code and as syntax errors by Cursor |

---

## Security Fixes (PR-worthy, Medium/Low only)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/resources/download_resources.py | Path from API response written without traversal check | Add `assert not os.path.isabs(dest) and ".." not in dest.split(os.sep)` before writing |
| 2 | scripts/ (all) | No pinned dependency manifest | Add `requirements.txt` with pinned versions for `requests`, `PyGithub`, `Pillow`, etc.; reference in README setup instructions |
| 3 | scripts/ticker/generate_ticker_svg.py | POST destination not visible / potentially configurable | Confirm URL is a hardcoded constant, not derived from external data; add assertion or constant declaration |

---

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .claude/commands/evaluate-repository.md | Vague quantifiers: "concise" ×4, "appropriate" ×2, "relevant" ×2 | -8 |
| 2 | resources/claude.md-files/Network-Chronicles/CLAUDE.md | Extensive implementation-plan notes mixed into project context file — ephemeral in-progress content should not persist in CLAUDE.md | -10 |
| 3 | resources/claude.md-files/Network-Chronicles/CLAUDE.md | Vague quantifiers: "appropriate" ×2, "rich" ×1, "relevant" ×1 | -6 |
| 4 | resources/claude.md-files/Note-Companion/CLAUDE.md | File covers styling and audio only; missing build commands, test commands, project structure overview | -10 |
| 5 | resources/claude.md-files/AVS-Vibe-Developer-Guide/CLAUDE.md | Very sparse: "No build/lint/test commands available." No code style, no architecture, no examples | -10 |
| 6 | resources/claude.md-files/claude-code-mcp-enhanced/CLAUDE.md | "These standards supersede any conflicting instructions you may have received previously" — instruction-override pattern may conflict with project-level CLAUDE.md hierarchy | -4 |
| 7 | resources/claude.md-files/Cursor-Tools/CLAUDE.md | "Don't ask me for permission to do stuff… if you have questions work with Gemini and Perplexity to decide what to do" — permission-grant expansion language reduces user oversight | -4 |
| 8 | resources/claude.md-files/SG-Cars-Trends-Backend/CLAUDE.md | Vague quantifiers: "appropriate" ×3, "concise" ×2, "consistent" ×2, "relevant" ×1 (capped) | -16 |
| 9 | resources/claude.md-files/Giselle/CLAUDE.md | Vague quantifiers: "meaningful" ×3, "unclear" ×1, "complex" ×1 | -10 |
| 10 | resources/claude.md-files/JSBeeb/CLAUDE.md | Vague quantifiers: "appropriate" ×2, "complex" ×2, "proper" ×1 | -10 |
| 11 | resources/claude.md-files/Pareto-Mac/CLAUDE.md | Vague quantifiers: "appropriate" ×3, "complex" ×2, "concise" ×1 | -12 |
| 12 | resources/claude.md-files/AWS-MCP-Server/CLAUDE.md | Vague quantifiers: "appropriate" ×3, "robust" ×1, "comprehensive" ×1, "proper" ×1 | -14 |
| 13 | resources/claude.md-files/Basic-Memory/CLAUDE.md | Vague quantifiers: "appropriate" ×3, "comprehensive" ×1, "complex" ×2 | -14 |
| 14 | resources/claude.md-files/Course-Builder/CLAUDE.md | Vague quantifiers: "appropriate" ×3, "comprehensive" ×3, "concise" ×1 | -14 |

---

## Cross-Component

These 24 files are independent samples from separate external repositories, not components of a single system. No cross-component references exist between them. Within the one multi-file system in the set:

- **SG-Cars-Trends-Backend/CLAUDE.md** references `apps/api/CLAUDE.md`, `apps/web/CLAUDE.md`, `packages/database/CLAUDE.md`, and `infra/CLAUDE.md` as sub-guides. These referenced files were not included in the audit set, so their existence cannot be confirmed. This is a latent broken-reference risk if sub-files are missing or renamed.

- **Cursor-Tools/CLAUDE.md** references `node_modules/vibe-tools/README.md` and `vibe-tools.config.json` as configuration sources. These are runtime artifacts not present in the repo and should not be referenced in a CLAUDE.md as authoritative documentation.

No contradictions or orphaned components found within the files actually included in this audit.

---

## Recommendation

**CLEAR — submit PRs for all bugs and medium/low security fixes.**

NL score of 89/100 is above the default 70-point threshold. The four bugs are mechanical and low-risk to fix. Security posture is clean: no critical or high findings, no hooks, no shell=True subprocess calls, no hardcoded credentials. The medium/low security fixes are defensive improvements suitable for standard pull requests.

Priority order for PRs:
1. Add YAML frontmatter and `allowed-tools` to `evaluate-repository.md` (bug fix, single file)
2. Remove "Current Task" section from DroidconKotlin/CLAUDE.md (bug fix, one line)
3. Add `requirements.txt` with pinned script dependencies (low security fix)
4. Fix path-traversal assertion in `download_resources.py` (medium security fix)
5. Audit and remove Cursor Rules fragments from Cursor-Tools/CLAUDE.md (bug fix)
