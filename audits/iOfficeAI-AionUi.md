# NLPM Audit: iOfficeAI/AionUi
**Date**: 2026-04-06  |  **Artifacts**: 39  |  **Strategy**: batched
**NL Score**: 75/100
**Security**: BLOCKED
**Bugs**: 10  |  **Quality Issues**: 4  |  **Security Findings**: 4

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| examples/hello-world-extension/agents/hello-researcher-context.md | agent | 30 | No frontmatter at all — missing name (−25), description (−25), model (−5), examples (−15) |
| examples/hello-world-extension/agents/hello-coder-context.md | agent | 30 | No frontmatter at all — missing name (−25), description (−25), model (−5), examples (−15) |
| .claude/commands/package-assistant.md | command | 45 | No frontmatter (name −25, description −25); no allowed-tools declared (−5); hardcoded developer path `/Users/veryliu/…` |
| src/process/resources/skills/officecli-docx/SKILL.md | skill | 45 | YAML comment `# officecli: v1.0.23` at line 3 breaks AionUi's frontmatter parser (−50); version comment repeated as H1 headers in body (−5) |
| src/process/resources/skills/officecli-financial-model/SKILL.md | skill | 50 | YAML comment `# officecli: v1.0.24` at line 3 breaks AionUi's frontmatter parser (−50) |
| src/process/resources/skills/officecli-data-dashboard/SKILL.md | skill | 50 | YAML comment `# officecli: v1.0.24` at line 3 breaks AionUi's frontmatter parser (−50) |
| src/process/resources/skills/officecli-pitch-deck/SKILL.md | skill | 50 | YAML comment `# officecli: v1.0.24` at line 3 breaks AionUi's frontmatter parser (−50) |
| src/process/resources/skills/officecli-pptx/SKILL.md | skill | 50 | YAML comment `# officecli: v1.0.23` at line 3 breaks AionUi's frontmatter parser (−50) |
| src/process/resources/skills/officecli-academic-paper/SKILL.md | skill | 50 | YAML comment `# officecli: v1.0.24` at line 3 breaks AionUi's frontmatter parser (−50) |
| src/process/resources/skills/officecli-xlsx/SKILL.md | skill | 50 | YAML comment `# officecli: v1.0.23` at line 3 breaks AionUi's frontmatter parser (−50) |
| src/process/resources/skills/morph-ppt/SKILL.md | skill | 80 | Vague description ("Generate Morph-animated PPTs with officecli") lacks use-case specificity |
| src/process/resources/skills/moltbook/SKILL.md | skill | 80 | Non-standard frontmatter fields (version, homepage, metadata); API-key management lacks input-validation guidance |
| src/process/resources/skills/x-recruiter/SKILL.md | skill | 82 | External script dependencies (node, python3, playwright) assumed installed without pre-check |
| src/process/resources/skills/aionui-webui-setup/SKILL.md | skill | 82 | Minor structural gaps in headless setup steps |
| src/process/resources/skills/openclaw-setup/SKILL.md | skill | 82 | Good structure; minor reference-file proliferation without clear loading order |
| src/process/resources/skills/star-office-helper/SKILL.md | skill | 82 | Background process (nohup) launched without port-conflict or log-path guidance |
| src/process/resources/skills/morph-ppt-3d/SKILL.md | skill | 82 | Extends morph-ppt; inherits vague workflow phrasing |
| src/process/resources/skills/xiaohongshu-recruiter/SKILL.md | skill | 82 | External script dependencies assumed installed without pre-check |
| src/process/resources/skills/story-roleplay/SKILL.md | skill | 82 | Minor vague terms in persona description |
| src/process/resources/skills/pdf/SKILL.md | skill | 83 | Extra non-standard `license` field in frontmatter |
| src/process/resources/skills/_builtin/cron/SKILL.md | skill | 84 | Good content; minor gaps in error-handling guidance |
| src/process/resources/skills/mermaid/SKILL.md | skill | 85 | Minor vague terms; no output-format description |
| src/process/resources/skills/_builtin/office-cli/SKILL.md | skill | 85 | Contains curl-pipe-sh and irm\|iex install patterns (see Security Scan — BLOCKED) |
| src/process/resources/skills/_builtin/skill-creator/SKILL.md | skill | 85 | Non-standard `license` frontmatter field; otherwise comprehensive |
| src/process/resources/skills/_builtin/aionui-skills/SKILL.md | skill | 88 | Remote content fetch (skills.aionui.com) without integrity check (see Security: MEDIUM) |
| src/process/resources/skills/weixin-file-send/SKILL.md | skill | 88 | Excellent protocol specification; no issues |
| .claude/skills/pr-review/SKILL.md | skill | 88 | Comprehensive 9-step workflow; minor vague terms |
| .claude/skills/pr-fix/SKILL.md | skill | 88 | Solid fix workflow with triage layers |
| .claude/skills/bump-version/SKILL.md | skill | 88 | Clear versioning steps; well-structured |
| .claude/skills/pr-automation/SKILL.md | skill | 88 | Good label state machine; clear daemon integration |
| .claude/skills/oss-pr/SKILL.md | skill | 89 | Well-structured 6-step PR workflow with fork-aware push |
| .claude/skills/pr-ship/SKILL.md | skill | 87 | ScheduleWakeup integration appropriate; minor edge-case gaps |
| .claude/skills/fix-issues/SKILL.md | skill | 87 | Good bug-fix automation; comprehensive triage |
| .claude/skills/fix-sentry/SKILL.md | skill | 87 | Sentry integration well-documented |
| .claude/skills/pr-verify/SKILL.md | skill | 87 | Comprehensive 7-step verification with fork-aware merge handling |
| .claude/skills/testing/SKILL.md | skill | 90 | Excellent — clear workflow, behavior-first test guidance, edge-case checklist |
| .claude/skills/architecture/SKILL.md | skill | 90 | Concise and actionable decision tree |
| .claude/skills/i18n/SKILL.md | skill | 90 | Comprehensive i18n workflow with validation steps |
| CLAUDE.md | project | 90 | Single-line delegate (`@AGENTS.md`); AGENTS.md is well-organized and complete |

## Security Scan

> **Status: BLOCKED** — one CRITICAL pattern found. The `auditor-contribute` workflow will refuse to open PRs until this issue is manually reviewed and the `security-blocked` label is cleared.

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 active (14 `.git/hooks/*.sample` files only) |
| Scripts | 18 (`.sh`×6, `.js`×10, `.py`×0) |
| MCP configs | 0 |
| Package manifests | 1 (`package.json`) |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | **CRITICAL** | `src/process/resources/skills/_builtin/office-cli/SKILL.md` | 18 | `curl-pipe-sh` | Code block instructs Claude to run `curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh \| bash` — downloads and executes arbitrary code from a GitHub raw URL with no integrity check. Claude Code agents following this skill will run this command verbatim. |
| 2 | HIGH | `src/process/resources/skills/_builtin/office-cli/SKILL.md` | 27 | `irm-iex` | PowerShell equivalent: `irm https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.ps1 \| iex` — same download-and-execute pattern on Windows. |
| 3 | HIGH | `scripts/install-ubuntu.sh` | 17 | `curl-pipe-sh` | Usage documentation in the script header shows `curl -fsSL .../install-ubuntu.sh \| bash` as the canonical install method. The script itself is the target of that curl-pipe-sh invocation; while the script body is well-guarded, the distribution model is inherently high-risk. |
| 4 | MEDIUM | `src/process/resources/skills/_builtin/aionui-skills/SKILL.md` | 19 | `remote-content-fetch` | `curl -s https://skills.aionui.com/SKILL.md > ~/.config/aionui-skills/SKILL.md` — fetches remote content to a local config path with no integrity verification. A compromised CDN could deliver malicious skill instructions. |

**Confidence notes:**
- Finding 1 & 2: **high** — the code blocks appear verbatim in an instruction section; Claude Code would execute them.
- Finding 3: **medium** — in a comment/documentation line, not an active code path.
- Finding 4: **medium** — the fetched content is not executed, but it does influence AI behaviour.

**Remediation before clearing security gate:**
1. Replace the bare `curl | bash` pattern in `office-cli/SKILL.md` with a version-pinned, checksum-verified download (e.g. download to `/tmp`, verify SHA256, then install).
2. Apply the same treatment to the PowerShell `irm | iex` block.
3. Consider publishing `officecli` to a package registry (Homebrew, npm, winget) to eliminate the bootstrap-from-raw-GitHub pattern entirely.

## Bugs (PR-worthy)

> **Note:** Contribution is currently BLOCKED by the security gate. These bugs are documented for when the gate clears.

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `src/process/resources/skills/officecli-financial-model/SKILL.md` | **YAML comment breaks parser** — `# officecli: v1.0.24` on line 3 inside the `---` block causes AionUi's frontmatter parser (`/^---\s*\n([\s\S]*?)\n---/` followed by non-standard comment stripping) to fail silently. Confirmed in `package-assistant.md`'s own documentation: "Skills with `# officecli: vX.X.X` comments inside the YAML frontmatter block break AionUi's parser, causing skills to not appear in Skills Center." | Skill invisible in Skills Center; name, description, and trigger conditions are never registered. |
| 2 | `src/process/resources/skills/officecli-data-dashboard/SKILL.md` | Same as #1 (`# officecli: v1.0.24`). | Same impact. |
| 3 | `src/process/resources/skills/officecli-pitch-deck/SKILL.md` | Same as #1 (`# officecli: v1.0.24`). | Same impact. |
| 4 | `src/process/resources/skills/officecli-docx/SKILL.md` | Same as #1 (`# officecli: v1.0.23`), compounded by `# officecli: v1.0.23` appearing 5 additional times in the document body as spurious H1 headers, corrupting the section structure. | Skill invisible in Skills Center; body structure is also broken, causing section-heading misparse. |
| 5 | `src/process/resources/skills/officecli-pptx/SKILL.md` | Same as #1 (`# officecli: v1.0.23`). | Same impact. |
| 6 | `src/process/resources/skills/officecli-academic-paper/SKILL.md` | Same as #1 (`# officecli: v1.0.24`). | Same impact. |
| 7 | `src/process/resources/skills/officecli-xlsx/SKILL.md` | Same as #1 (`# officecli: v1.0.23`). | Same impact. |
| 8 | `examples/hello-world-extension/agents/hello-researcher-context.md` | **No YAML frontmatter** — file opens directly with prose (`You are an AI assistant…`); no `---` block present. The agent's `name`, `description`, and `model` fields are all absent. | Agent cannot be registered or invoked by name in Claude Code; all required frontmatter fields missing. |
| 9 | `examples/hello-world-extension/agents/hello-coder-context.md` | Same as #8 — no YAML frontmatter at all. | Same impact. |
| 10 | `.claude/commands/package-assistant.md` | **Hardcoded developer path** — command references `/Users/veryliu/Documents/GitHub/officecli/` and `/Users/veryliu/Documents/GitHub/officecli/iterations/` (absolute macOS home-directory path). Will fail for every other user. | Command non-functional for any contributor whose machine is not the original author's. |

**Suggested fix for bugs #1–7 (YAML comment):** Remove the `# officecli: vX.X.X` line from inside the `---` frontmatter block. If version tracking is needed, place it after the closing `---` as an HTML comment (`<!-- officecli: v1.0.24 -->`) or in a `version:` frontmatter field if the parser supports it.

**Suggested fix for bugs #8–9:** Add a minimal frontmatter block at line 1 of each agent file, e.g.:
```
---
name: hello-researcher
description: Example research agent for the hello-world extension.
model: claude-sonnet-4-5
---
```

**Suggested fix for bug #10:** Replace hardcoded paths with a relative path or an environment variable (e.g., `$OFFICECLI_REPO` or `./path/relative/to/project`).

## Quality Issues (informational)

| # | File(s) | Issue | Penalty |
|---|---------|-------|---------|
| 1 | `examples/hello-world-extension/agents/hello-researcher-context.md`, `hello-coder-context.md` | **Missing model and examples** — beyond the frontmatter bug (#8/#9 above), neither agent declares a model pin (`model:`) or includes any worked example. Without examples, the agent's expected invocation and output are undefined. | −5 (model), −15 (zero examples) per file — these penalties are subsumed by the more severe −50 frontmatter penalty in the score. |
| 2 | `.claude/commands/package-assistant.md` | **Missing `allowed-tools` declaration** — a 5-step command that reads files and runs shell commands has no `allowed-tools` field, so Claude Code cannot enforce tool-level sandboxing. | −5 |
| 3 | `src/process/resources/skills/officecli-docx/SKILL.md` | **Repeated version comment as H1 headers in body** — `# officecli: v1.0.23` appears 5+ times as section headings inside the skill body, producing spurious top-level headings that disrupt the document outline. | −5 (structure) |
| 4 | `src/process/resources/skills/morph-ppt/SKILL.md` | **Vague description** — "Generate Morph-animated PPTs with officecli" tells the system what the skill does but not *when* to trigger it or what distinguishes it from the base `officecli-pptx` skill. | −2 (weak description specificity) |

## Cross-Component

The `.claude/skills/` directory forms a well-integrated automation suite: `pr-automation` orchestrates `pr-review`, `pr-fix`, `pr-ship`, and `pr-verify` via a label state machine, and all five reference each other's comment markers consistently (`<!-- pr-automation-bot -->`, `<!-- pr-review-bot -->`, etc.). Worktree path conventions are enforced (`/tmp/aionui-pr-*` for automation, `/tmp/aionui-verify-*` for pr-verify) and explicitly documented in the Mandatory Rules sections.

The `officecli-*` skill family has a systemic cross-component defect: 7 of the 8 specialised Office skills share the same YAML-comment-breaks-parser bug. The root cause appears to be a version-tracking convention (`# officecli: vX.X.X`) that was added to the frontmatter block without recognising that AionUi's parser rejects YAML comments in that position. One skill (`office-cli/SKILL.md`, the base skill) is unaffected because it does not carry the version comment. The fix is the same for all seven and can be applied in a single PR.

`package-assistant.md` references the `office-cli` skill family (it packages and distributes officecli skills) and explicitly documents the YAML-comment bug — confirming it is a known issue. No other cross-component reference inconsistencies were found.

## Recommendation

**BLOCKED — security gate must be cleared before any PRs can be opened.**

The CRITICAL `curl-pipe-sh` finding in `office-cli/SKILL.md` must be resolved first. Once resolved:

1. **Highest-value PR**: Fix the `yaml-comment-breaks-parser` bug across all 7 affected officecli skills in a single commit (remove `# officecli: vX.X.X` from inside `---` blocks). These skills are currently invisible in Skills Center, making the entire `officecli-*` family non-functional despite containing high-quality content.

2. **Second PR**: Fix `examples/hello-world-extension/agents/` — both example agents need minimal frontmatter so they function as working examples for contributors.

3. **Third PR**: Fix the hardcoded developer path in `package-assistant.md` and add `allowed-tools`.

The `.claude/skills/` automation suite is of high quality (87–90/100) and requires no changes. The `office-cli/SKILL.md` base skill is also well-written and would score ~92/100 if the security findings were addressed.

**NL score of 75/100 would rise to approximately 84/100** after fixing the YAML comment bug (the 7 broken skills would each recover ~40 points), **and to ~86/100** after fixing the two example agents.
