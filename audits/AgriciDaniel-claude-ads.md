# NLPM Audit: AgriciDaniel/claude-ads
**Date**: 2026-04-17  |  **Artifacts**: 32  |  **Strategy**: batched
**NL Score**: 99/100
**Security**: REVIEW
**Bugs**: 0  |  **Quality Issues**: 10  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| agents/audit-google.md | agent | 93 | "74-check" in workflow contradicts "80 Checks" category header; "applicable" vague |
| agents/audit-meta.md | agent | 93 | "46-check" in workflow contradicts "50 Checks" category header; "applicable" vague |
| agents/copy-writer.md | agent | 95 | Single example only (-5) |
| agents/format-adapter.md | agent | 95 | Single example only (-5) |
| CLAUDE.md | project doc | 95 | Architecture tree omits 4 creative agents (creative-strategist, visual-designer, copy-writer, format-adapter) |
| agents/audit-budget.md | agent | 98 | "applicable" vague quantifier in instruction text |
| agents/audit-compliance.md | agent | 98 | "applicable" vague quantifier in instruction text |
| agents/audit-creative.md | agent | 98 | "applicable" vague quantifier in instruction text |
| agents/audit-tracking.md | agent | 98 | "applicable" vague quantifier in instruction text |
| ads/SKILL.md | skill | 98 | "relevant" vague quantifier in orchestration instruction |
| agents/creative-strategist.md | agent | 100 | None |
| agents/visual-designer.md | agent | 100 | None |
| skills/ads-meta/SKILL.md | skill | 100 | None |
| skills/ads-microsoft/SKILL.md | skill | 100 | None |
| skills/ads-linkedin/SKILL.md | skill | 100 | None |
| skills/ads-tiktok/SKILL.md | skill | 100 | None |
| skills/ads-math/SKILL.md | skill | 100 | None |
| skills/ads-audit/SKILL.md | skill | 100 | None |
| skills/ads-generate/SKILL.md | skill | 100 | None |
| skills/ads-create/SKILL.md | skill | 100 | None |
| skills/ads-youtube/SKILL.md | skill | 100 | None |
| skills/ads-competitor/SKILL.md | skill | 100 | None |
| skills/ads-google/SKILL.md | skill | 100 | None |
| skills/ads-dna/SKILL.md | skill | 100 | None |
| skills/ads-test/SKILL.md | skill | 100 | None |
| skills/ads-apple/SKILL.md | skill | 100 | None |
| skills/ads-photoshoot/SKILL.md | skill | 100 | None |
| skills/ads-plan/SKILL.md | skill | 100 | None |
| skills/ads-creative/SKILL.md | skill | 100 | None |
| skills/ads-budget/SKILL.md | skill | 100 | None |
| skills/ads-landing/SKILL.md | skill | 100 | None |
| .claude-plugin/plugin.json | manifest | 100 | None |

**Weighted average**: (968 agents + 1998 skills + 95 CLAUDE.md + 100 plugin.json) / 32 = **99/100**

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
| Hooks | 0 files |
| Scripts | 6 files: `scripts/analyze_landing.py`, `scripts/capture_screenshot.py`, `scripts/fetch_page.py`, `scripts/generate_image.py`, `scripts/generate_report.py`, `scripts/url_utils.py` |
| MCP configs | 0 files |
| Package manifests | `requirements.txt` (Python; version-bounded) |
| Installer | `install.sh` (bash) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | MEDIUM | install.sh | 88 | curl-pipe-sh (documentation) | Echo statement instructs users to run `curl -fsSL .../banana-claude/main/install.sh \| bash` to install banana-claude. The pattern is not executed by the script itself — it is printed as a user instruction — but it promotes an insecure installation pattern (unauthenticated remote code execution). |
| 2 | MEDIUM | install.sh | 70–76 | Runtime package install | `pip install -r requirements.txt` runs during installation. Mitigated: requirements.txt uses bounded version ranges with documented CVE-fixing minimums (e.g., `urllib3>=2.6.3`, `requests>=2.32.4`). Low actual risk. |
| 3 | MEDIUM | scripts/generate_image.py | 289–303, 332–349 | Network calls to external APIs | `requests.post` to `api.stability.ai` and `requests.get` to Replicate URL. Replicate URL origin is validated for HTTPS scheme (line 347). Stability AI endpoint is hardcoded. Low practical risk; expected behavior for image generation. |
| 4 | LOW | scripts/generate_image.py | 123–154 | Environment variable access | API keys read from env vars (`GOOGLE_API_KEY`, `OPENAI_API_KEY`, `STABILITY_API_KEY`, `REPLICATE_API_TOKEN`). Legitimate and documented usage; error messages strip keys via `_SENSITIVE_PATTERN`. |
| 5 | LOW | scripts/generate_report.py | 362–380 | subprocess.run (mmdc CLI) | Mermaid diagram renderer invoked via `subprocess.run([mmdc, "-i", src, "-o", out, ...])` with no `shell=True`. Input is written to a temp file before passing; no direct injection path from user-controlled data. |

**Note on pre-scan critical match**: The 1 critical pattern match flagged in the pre-scan matches the text of the `echo` statement on `install.sh:88`. The curl command is printed as documentation for users, not executed by the installer. This is a **false positive** from mechanical pattern scanning. There are no actual curl-pipe-sh executions, eval-with-variables, reverse shells, base64-decode-exec, or credential exfiltration patterns in any script.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| — | — | No registration-breaking bugs found | — |

No missing frontmatter fields, no broken cross-references, no tools called outside declared tool lists, no structural issues preventing agent or skill registration.

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | install.sh:88 | Echo promotes curl-pipe-sh installation pattern for banana-claude | Replace echo suggestion with: `echo "    Install via plugin: claude plugin install banana-claude@AgriciDaniel --scope user"` or add SHA256 checksum verification step alongside the curl suggestion |
| 2 | install.sh:70–76 | pip install uses `--break-system-packages` as silent fallback | Remove `--break-system-packages` silent fallback; surface the failure clearly and direct user to use a virtual environment instead |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | agents/audit-google.md | Workflow step 1 says "74-check audit checklist" but categories table header reads "80 Checks" (12+8+12+8+18+18+4=80). Creates ambiguity about actual check count. | -5 |
| 2 | agents/audit-meta.md | Workflow step 1 says "46-check audit checklist" but categories table header reads "50 Checks" (11+13+19+7=50). Same inconsistency pattern. | -5 |
| 3 | agents/copy-writer.md | Only one `<example>` block; two examples recommended for agents. | -5 |
| 4 | agents/format-adapter.md | Only one `<example>` block; two examples recommended for agents. | -5 |
| 5 | CLAUDE.md | Architecture tree lists only 6 audit agents; the 4 creative agents (creative-strategist, visual-designer, copy-writer, format-adapter) are omitted from the directory listing despite the comment saying "10 agents (6 audit + 4 creative)". | -5 |
| 6 | agents/audit-budget.md | "Evaluate each applicable check" in step 5 — "applicable" is a vague quantifier in instruction text. | -2 |
| 7 | agents/audit-compliance.md | "Evaluate each applicable check" in step 4 — "applicable" is a vague quantifier. | -2 |
| 8 | agents/audit-creative.md | "Evaluate each applicable check" in step 4 — "applicable" is a vague quantifier. | -2 |
| 9 | agents/audit-tracking.md | "Evaluate each applicable check" in step 3 — "applicable" is a vague quantifier. | -2 |
| 10 | ads/SKILL.md | "load the relevant sub-skill directly" in orchestration logic — "relevant" is a vague quantifier. | -2 |

## Cross-Component
**References**: All agent cross-references to `ads/references/*.md` files resolve correctly via the path resolution note in `ads/SKILL.md` ("resolve to `~/.claude/skills/ads/references/*.md`"). No broken reference paths detected.

**Check count inconsistencies**: Two agents (`audit-google`, `audit-meta`) define a different check count in their workflow step vs. their categories table. These differ because the agent bodies define additional checks (G-AI, G-DG, G-CTV, G-PM series; M-AN, M-AT, M-IA, M-TH series) beyond the reference file's baseline. The reference files are separate from the agent bodies. While functional, this creates confusion for maintainers. A comment clarifying "reference file contains N base checks; agent adds M additional checks for a total of X" would resolve the ambiguity.

**Audit agent Bash tool**: Six audit agents (audit-budget, audit-compliance, audit-google, audit-meta, audit-creative, audit-tracking) declare Bash in their tool lists but do not demonstrate Bash usage in their examples or numbered workflow steps. Bash is plausible for running ad-hoc analysis scripts but is never shown. Format-adapter and visual-designer correctly demonstrate their Bash usage with concrete commands.

**Promotional footer in ads/SKILL.md**: The `Community Footer` block (lines 117–126) includes external Skool community links appended after all major deliverables. This is branding, not a compliance issue, but auditors should be aware it is embedded output.

**install.ps1 / uninstall.sh / uninstall.ps1**: CLAUDE.md references `install.sh / install.ps1` and `uninstall.sh / uninstall.ps1` as cross-platform installers, but only `install.sh` was present in the repository. If the PowerShell and uninstall scripts are missing, CLAUDE.md's architecture description is inaccurate.

## Recommendation
**REVIEW** — Submit NL fix PRs for quality issues (check count documentation, second example for copy-writer and format-adapter, architecture tree in CLAUDE.md). Flag medium security findings (curl-pipe-sh echo pattern in install.sh, --break-system-packages fallback) in a GitHub issue for maintainer awareness. No Critical or High security findings block contribution.

**Suggested PR scope:**
1. `agents/audit-google.md` — reconcile "74-check" vs "80 Checks" (add clarifying note)
2. `agents/audit-meta.md` — reconcile "46-check" vs "50 Checks" (add clarifying note)
3. `agents/copy-writer.md` — add second example block
4. `agents/format-adapter.md` — add second example block
5. `CLAUDE.md` — add creative agents (creative-strategist, visual-designer, copy-writer, format-adapter) to architecture tree
6. `install.sh` — replace `--break-system-packages` silent fallback with explicit failure message; document the curl-pipe-sh banana install step with a checksum
