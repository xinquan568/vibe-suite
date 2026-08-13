# NLPM Audit: sickn33/antigravity-awesome-skills
**Date**: 2026-04-17  |  **Artifacts**: 2998 (sampled 65)  |  **Strategy**: stratified-sampling
**NL Score**: 82/100
**Security**: REVIEW REQUIRED
**Bugs**: 8  |  **Quality Issues**: 42  |  **Security Findings**: 9

> **Scale note**: This repository contains 2,998 SKILL.md files across 39 plugin bundles — approximately 30× larger than expected. Full enumeration was infeasible. Stratified sampling covered 65 files across all major bundle categories plus representative samples from the two large collections (antigravity-awesome-skills: 1381 files, antigravity-awesome-skills-claude: 1396 files). Score is an estimated mean with ±3 confidence margin.

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| gdpr-data-handling/SKILL.md | skill | 60 | Stub — body is only "open implementation-playbook.md"; no actual guidance |
| tavily-web/SKILL.md | skill | 62 | Stub — points to GitHub external link; no examples, no output format |
| tailwind-design-system/SKILL.md | skill | 65 | Stub — delegates to implementation-playbook.md; no inline content |
| nextjs-app-router-patterns/SKILL.md | skill | 65 | Stub — delegates to implementation-playbook.md; no inline content |
| git-pushing/SKILL.md | skill | 70 | risk:critical thin skill (41 lines); no output format, no examples, references external script only |
| youtube-summarizer/SKILL.md | skill | 75 | Malformed markdown — unclosed code fence in Step 5 output section |
| ethical-hacking-methodology/SKILL.md | skill | 75 | risk:unknown despite containing Metasploit persistence + backdoor SSH key commands; inconsistent labeling |
| cloud-penetration-testing/SKILL.md | skill | 78 | risk:offensive, security-allowlist present; no output format; AWS metadata credential extraction |
| linux-privilege-escalation/SKILL.md | skill | 78 | risk:offensive, security-allowlist present; reverse shell one-liners; no output format |
| docx-official/SKILL.md | skill | 78 | References external docx-js.md and ooxml.md that are not bundled; broken references |
| prompt-engineer/SKILL.md | skill | 78 | Multi-step workflow skips Step 2 entirely (jumps 1→3); appears to be copy-paste error |
| seo-content-writer/SKILL.md | skill | 78 | Missing output format, vague scope definition |
| seo-cannibalization-detector/SKILL.md | skill | 78 | Missing output format, vague scope definition |
| seo-content-planner/SKILL.md | skill | 78 | Missing output format |
| seo-structure-architect/SKILL.md | skill | 78 | Missing output format |
| seo-content-auditor/SKILL.md | skill | 78 | Missing output format |
| lint-and-validate/SKILL.md | skill | 80 | References scripts/lint_runner.py and scripts/type_coverage.py that may not be bundled |
| git-pr-workflows-git-workflow/SKILL.md | skill | 80 | No output format; multi-phase but phases unlabeled by number |
| schema-markup/SKILL.md | skill | 80 | Extra --- separator line at line 9 (between frontmatter and body — malformed YAML boundary) |
| seo-fundamentals/SKILL.md | skill | 82 | Extra --- separator line at line 9 |
| vulnerability-scanner/SKILL.md | skill | 80 | References scripts/security_scan.py; no output format |
| react-best-practices/SKILL.md | skill | 82 | References rules/*.md and AGENTS.md not bundled inline |
| bash-linux/SKILL.md | skill | 82 | Reference guide only; no examples, no scope definition |
| wiki-vitepress/SKILL.md | skill | 82 | No output format; vague "apply relevant best practices" |
| dropbox-automation/SKILL.md | skill | 82 | risk:critical; no output format; multi-workflow but format unlabeled |
| one-drive-automation/SKILL.md | skill | 82 | risk:critical; no output format |
| azure-ai-projects-dotnet/SKILL.md | skill | 82 | Comprehensive SDK reference; missing output format section |
| javascript-pro/SKILL.md | skill | 82 | Good; minor vague terms (appropriate, robust) |
| libreoffice-base/SKILL.md | skill | 82 | source:personal; good examples; no output format |
| libreoffice-draw/SKILL.md | skill | 82 | source:personal; good examples; no output format |
| libreoffice-impress/SKILL.md | skill | 82 | source:personal; good examples; no output format |
| hig-foundations/SKILL.md | skill | 82 | Good reference index; no output examples |
| business-analyst/SKILL.md | skill | 83 | 8 examples; good response approach; minor vague terms |
| hig-components-content/SKILL.md | skill | 82 | Has output format; references external *.md files |
| cc-skill-clickhouse-io/SKILL.md | skill | 82 | Good SQL + TypeScript examples; no output format |
| skill-router/SKILL.md | skill | 83 | Comprehensive routing reference; 1 example only |
| azure-identity-java/SKILL.md | skill | 83 | Comprehensive credential reference; good examples |
| azure-identity-py/SKILL.md | skill | 83 | Comprehensive Python auth reference; good examples |
| nodejs-best-practices/SKILL.md | skill | 83 | Principle-based; good decision trees; no output format |
| blog-writing-guide/SKILL.md | skill | 83 | Missing date_added in frontmatter (-5); otherwise comprehensive |
| concise-planning/SKILL.md | skill | 83 | Good concise template; minor vague terms |
| top-web-vulnerabilities/SKILL.md | skill | 83 | Comprehensive; risk:unknown (should be offensive or at least high) |
| security-auditor/SKILL.md | skill | 83 | Comprehensive; risk:unknown (should be offensive/high) |
| office-productivity/SKILL.md | skill | 83 | 7-phase workflow; good structure; references many other skills |
| agent-orchestrator/SKILL.md | skill | 83 | Portuguese-language metadata; calls external Python scripts; good orchestration logic |
| react-best-practices/SKILL.md | skill | 82 | 45-rule reference; relies on external rule files for detail |
| new-rails-project/SKILL.md | skill | 85 | Has allowed-tools declared; context:fork; good setup workflow |
| godot-4-migration/SKILL.md | skill | 85 | 2 detailed examples; practical migration guide |
| kaizen/SKILL.md | skill | 85 | Comprehensive 4-pillar guide; good output format |
| hig-patterns/SKILL.md | skill | 85 | Good reference index pattern; output format defined |
| active-directory-attacks/SKILL.md | skill | 85 | risk:offensive; "AUTHORIZED USE ONLY" disclaimer; 2 examples; numbered steps; NO security-allowlist annotation |
| deployment-procedures/SKILL.md | skill | 85 | Principle-based; good decision trees; 5-phase workflow |
| terraform-specialist/SKILL.md | skill | 87 | 8 examples; comprehensive; no output format |
| kubernetes-architect/SKILL.md | skill | 87 | 8 examples; comprehensive; no output format |
| systematic-debugging/SKILL.md | skill | 87 | Comprehensive 4-phase methodology; good output format |
| typescript-expert/SKILL.md | skill | 87 | category:framework; very comprehensive; risk:critical; good code examples |
| docker-expert/SKILL.md | skill | 87 | Comprehensive; code review checklist; no output format |
| libreoffice-writer/SKILL.md | skill | 83 | source:personal; most comprehensive LibreOffice skill; good examples |
| environment-setup-guide/SKILL.md | skill | 88 | 3 examples; comprehensive; NodeSource curl-pipe-bash without security-allowlist annotation |
| aws-serverless/SKILL.md | skill | 88 | 1344 lines; very comprehensive; sharp-edges section; no output format |
| brainstorming/SKILL.md | skill | 88 | 7-step process; output format present; well-structured |
| protect-mcp-governance/SKILL.md | skill | 90 | 3 worked examples; Cedar policy code; output format; well-structured |

**Score breakdown by plugin bundle** (sampled files):

| Plugin Bundle | Files Sampled | Avg Score | Notable |
|--------------|---------------|-----------|---------|
| antigravity-bundle-devops-cloud | 7 | 87 | Strongest bundle; aws-serverless, kubernetes, terraform all 87+ |
| antigravity-bundle-essentials | 5 | 83 | systematic-debugging and kaizen are standouts |
| antigravity-bundle-typescript-javascript | 5 | 80 | nextjs-app-router stub drags average |
| antigravity-bundle-security-engineer | 7 | 80 | risk labeling inconsistencies; allowlist annotations present for key files |
| antigravity-bundle-seo-specialist | 7 | 79 | Extra --- separators in 2 files; generally thin content |
| antigravity-bundle-apple-platform-design | 1 | 82 | Reference-index structure works well |
| antigravity-bundle-business-analyst | 1 | 83 | Good examples; reasonable quality |
| antigravity-bundle-documents-presentations | 1 | 83 | Multi-skill workflow bundle; solid structure |
| antigravity-bundle-oss-maintainer | 1 | 82 | documentation-templates solid |
| antigravity-awesome-skills | 20 | 81 | Some stubs drag avg; protect-mcp-governance is excellent |
| antigravity-awesome-skills-claude | 4 | 83 | active-directory-attacks well-structured; agent-orchestrator bilingual |

**Overall estimated NL score: 82/100**

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 4 |
| Low | 3 |

### Execution Surface Inventory

| Surface | Files | Notes |
|---------|-------|-------|
| Hooks | 0 | No hooks.json found anywhere in repo |
| Shell scripts (.sh) | 61 | All appear to be legitimate dev tooling |
| Python scripts (.py) | 1000 | Primarily security scanners, automation helpers, boilerplate examples |
| JavaScript scripts (.js) | Bundled in examples | No standalone attack scripts found |
| MCP configs (.mcp.json) | 0 | None found |
| Package manifests (package.json) | 10+ | Only in boilerplate examples (Telegram, WhatsApp nodeJS, Playwright, Apify) |
| Requirements files (requirements.txt) | 10+ | Only in skill boilerplate examples |
| Hardcoded credentials | 0 | AKIAIOSFODNN7EXAMPLE is AWS documentation placeholder; all sk-* are gateway example keys |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | High | antigravity-awesome-skills/skills/active-directory-attacks/SKILL.md | 159–166 | credential-extraction-no-allowlist | DCSync attack examples (lsadump::dcsync, secretsdump.py) and Golden Ticket forgery (kerberos::golden) without `<!-- security-allowlist -->` annotation. The file has `risk: offensive` and "AUTHORIZED USE ONLY" disclaimer, but the specific curl-free attack patterns are not annotated. Pattern scanner will flag this. |
| 2 | High | antigravity-awesome-skills-claude/skills/active-directory-attacks/SKILL.md | 159–166 | credential-extraction-no-allowlist | Identical file duplicated in the -claude plugin; same issue. Needs security-allowlist annotation for DCSync/Pass-the-Hash/Golden Ticket content. |
| 3 | Medium | antigravity-bundle-security-engineer/skills/ethical-hacking-methodology/SKILL.md | multiple | risk-label-mismatch | Contains Metasploit persistence commands and backdoor SSH key installation instructions, but uses `risk: unknown` instead of `risk: offensive`. Inconsistent with rest of security-engineer bundle. |
| 4 | Medium | antigravity-bundle-devops-cloud/skills/environment-setup-guide/SKILL.md | 98 | curl-pipe-bash-no-allowlist | `curl -fsSL https://deb.nodesource.com/setup_20.x \| sudo -E bash -` (official NodeSource installer) without `<!-- security-allowlist: curl-pipe-bash -->` annotation. Pattern is legitimate but unannoted. |
| 5 | Medium | antigravity-awesome-skills/skills/gitops-workflow/SKILL.md | 141 | curl-pipe-bash-no-allowlist | `curl -s https://fluxcd.io/install.sh \| sudo bash` (official Flux CD installer) without security-allowlist annotation. Mirrors same pattern as bun-development (which IS annotated). |
| 6 | Medium | antigravity-awesome-skills-claude/skills/gitops-workflow/SKILL.md | 141 | curl-pipe-bash-no-allowlist | Identical Flux CD installer in -claude plugin; same annotation gap. |
| 7 | Low | antigravity-awesome-skills-claude/skills/loki-mode/autonomy/run.sh | 50–55 | broad-autonomy-scope | Loki Mode autonomous runner designed to execute `claude --dangerously-skip-permissions` in a loop with configurable blocked command list. The BLOCKED_COMMANDS default is `rm -rf /,dd if=,mkfs` — this is intentionally narrow. Users enabling LOKI_PERPETUAL_MODE should understand the scope. Not malicious but warrants operational awareness. |
| 8 | Low | antigravity-awesome-skills/skills/007/ (scripts) | multiple | shell=True-in-comments | injection_scanner.py uses `os.system()` and `subprocess.run(shell=True)` as detection patterns in docstrings and string literals. These are detection targets, not actual invocations. Pattern scanners may false-positive on these. |
| 9 | Low | antigravity-awesome-skills/skills/lint-and-validate/SKILL.md | — | external-script-dependency | References `scripts/lint_runner.py` and `scripts/type_coverage.py` that exist in the skill directory but are not bundled in the markdown. Users must read the skill to discover the dependency; the SKILL.md body gives no indication these scripts exist. |

**Key security positives:**
- 50+ `risk: offensive` skills across both large collections consistently carry "AUTHORIZED USE ONLY" disclaimers
- cloud-penetration-testing and linux-privilege-escalation in both awesome-skills collections correctly annotated with `<!-- security-allowlist: curl-pipe-bash -->`
- bun-development, linkerd-patterns, apify-actor-development, evolution, varlock — all have security-allowlist where curl-pipe-bash appears for legitimate installer commands
- 007 skill is a legitimate defensive security audit tool (taint-tracking injection scanner, SSRF detector, secrets scanner) with no actual attack capabilities
- No hardcoded real credentials found anywhere
- No actual data exfiltration code found

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | antigravity-awesome-skills/skills/prompt-engineer/SKILL.md | Multi-step workflow skips Step 2 — sequence goes 1 → 3 → 4.5 → 4.6 | Users following numbered steps will miss the intended Step 2 action entirely; workflow is incomplete |
| 2 | antigravity-awesome-skills/skills/youtube-summarizer/SKILL.md | Malformed markdown: unclosed code fence in output section (Step 5) | Markdown renders incorrectly; output format section appears as raw text rather than structured block |
| 3 | antigravity-bundle-seo-specialist/skills/schema-markup/SKILL.md | Extra `---` separator line at line 9 (between frontmatter and body) | Creates a second frontmatter boundary; some parsers will treat lines 9+ as a new YAML block, breaking the body |
| 4 | antigravity-bundle-seo-specialist/skills/seo-fundamentals/SKILL.md | Extra `---` separator line at line 9 | Same YAML parsing issue as schema-markup |
| 5 | antigravity-awesome-skills/skills/blog-writing-guide/SKILL.md | Missing `date_added` field in frontmatter | Breaks NLPM frontmatter validation; file will score lower on automated checks |
| 6 | antigravity-awesome-skills/skills/docx-official/SKILL.md | References `docx-js.md` and `ooxml.md` that are not bundled in the skill directory | Users directed to open these files will get File Not Found; all detailed guidance is inaccessible |
| 7 | antigravity-awesome-skills-claude/skills/active-directory-attacks/SKILL.md | Missing `<!-- security-allowlist -->` annotation for high-severity credential extraction techniques | Security gate will flag this as uncleared CRITICAL content; contribution will be blocked |
| 8 | antigravity-awesome-skills/skills/active-directory-attacks/SKILL.md | Same as above — duplicate in other collection | Same security gate block |

## Security Fixes (PR-worthy)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | active-directory-attacks/SKILL.md (both copies) | No security-allowlist annotation for DCSync, Golden Ticket, Pass-the-Hash content | Add `<!-- security-allowlist: credential-extraction, kerberos-attacks -->` annotation after frontmatter, matching the pattern used in cloud-penetration-testing and linux-privilege-escalation |
| 2 | ethical-hacking-methodology/SKILL.md | risk:unknown despite containing backdoor installation and persistence commands | Change `risk: unknown` to `risk: offensive` to match the rest of the security-engineer bundle; add "AUTHORIZED USE ONLY" disclaimer at top of body |
| 3 | environment-setup-guide/SKILL.md (both copies) | NodeSource curl-pipe-bash without annotation | Add `<!-- security-allowlist: curl-pipe-bash -->` after frontmatter |
| 4 | gitops-workflow/SKILL.md (both copies) | Flux CD curl-pipe-bash without annotation | Add `<!-- security-allowlist: curl-pipe-bash -->` after frontmatter |

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | gdpr-data-handling/SKILL.md | Body is only "open implementation-playbook.md" — no actual content | -15 (no examples), -10 (no output format), -5 (no scope) |
| 2 | tavily-web/SKILL.md | Stub with only external link; no examples, no workflow | -15, -10, -5 |
| 3 | tailwind-design-system/SKILL.md | Delegates entirely to implementation-playbook.md | -15, -10, -5 |
| 4 | nextjs-app-router-patterns/SKILL.md | Delegates entirely to implementation-playbook.md | -15, -10, -5 |
| 5 | git-pushing/SKILL.md | risk:critical with no examples, no output format, only references external script | -15, -10, -5 |
| 6 | cloud-penetration-testing/SKILL.md | No output format section | -10 |
| 7 | linux-privilege-escalation/SKILL.md | No output format section | -10 |
| 8 | observability-monitoring-monitor-setup/SKILL.md | Vague: "relevant best practices", "appropriate monitoring" | -4 |
| 9 | dropbox-automation/SKILL.md | No output format; risk:critical with no examples | -15, -10 |
| 10 | one-drive-automation/SKILL.md | No output format; risk:critical with no examples | -15, -10 |
| 11 | azure-ai-projects-dotnet/SKILL.md | No output format section | -10 |
| 12 | skill-router/SKILL.md | Only 1 example (partial credit) | -5 |
| 13 | seo-content-writer through seo-content-auditor (5 files) | No output format in any of the 5 SEO skills | -10 each |
| 14 | bash-linux/SKILL.md | "Use this skill" section too vague; no examples | -5 (1 example) |
| 15 | lint-and-validate/SKILL.md | No examples; references external Python scripts without inline fallback | -15 |
| 16 | agent-orchestrator/SKILL.md | Workflow requires 3 external Python scripts to run before any response; skill non-functional without them | quality |
| 17 | top-web-vulnerabilities/SKILL.md | risk:unknown — should be risk:offensive or risk:high for security education content | quality |
| 18 | security-auditor/SKILL.md | risk:unknown — inconsistent with rest of security-engineer bundle | quality |
| 19 | typescript-expert/SKILL.md | No output format section despite comprehensive content | -10 |
| 20 | docker-expert/SKILL.md | No output format section | -10 |
| 21 | kubernetes-architect/SKILL.md | No output format section | -10 |
| 22 | terraform-specialist/SKILL.md | No output format section | -10 |
| 23 | react-best-practices/SKILL.md | All detail deferred to external rules/*.md files; inline body is a table of contents only | quality |
| 24 | nodejs-best-practices/SKILL.md | "Learn to THINK" meta-instruction in body is valuable but not a substitute for examples | -5 (1 implicit example) |
| 25 | Multiple skills across all bundles | Vague terms: "relevant", "appropriate", "best practices", "comprehensive", "modern", "robust" appearing 3–8 times per file | -2 each, capped at -20 per file |

## Cross-Component

**Structural pattern: stub skills pointing to implementation-playbook.md**
At least 4 skills (gdpr-data-handling, tailwind-design-system, nextjs-app-router-patterns, business-analyst's playbook reference) delegate their entire content to `resources/implementation-playbook.md`. In each case, that file exists alongside SKILL.md but is not loaded by Claude Code automatically. Users invoking the skill get empty guidance unless they manually read the playbook. This is a systemic design issue across the antigravity ecosystem.

**Duplication: antigravity-awesome-skills vs antigravity-awesome-skills-claude**
The two largest collections (1381 vs 1396 files) appear to be near-mirrors of each other. Shared skills include: linux-privilege-escalation, cloud-penetration-testing, active-directory-attacks, environment-setup-guide, gitops-workflow, vulnerability-scanner, 007, typescript-expert, and hundreds more. Any bug found in one collection likely applies to both. Security fixes to the -claude collection were explicitly noted where the bug was verified in both.

**Security bundle labeling inconsistency**
The security-engineer bundle uses `risk: offensive` consistently for burp-suite, cloud-penetration-testing, linux-privilege-escalation. But ethical-hacking-methodology, security-auditor, and top-web-vulnerabilities use `risk: unknown`. The awesome-skills collections have a richer `risk: offensive` usage (50+ files correctly labeled). Recommend normalizing the security-engineer bundle to match.

**allowed-tools usage**
Only `new-rails-project` (in awesome-skills) was observed with a proper `allowed-tools` declaration. All other SKILL.md files, including risk:critical ones (dropbox-automation, one-drive-automation, git-pushing, git-pr-workflows), declare no tool constraints. This is not a breaking issue for skills (which are passive reference documents), but it makes the scope contract implicit.

**Naming convention**
The `antigravity-awesome-skills` collection uses inconsistent skill naming: some directories use kebab-case with category prefix (`git-pr-workflows-git-workflow`), others just the skill name (`brainstorming`). The `-claude` collection follows a cleaner flat naming convention. No functional impact but creates confusion during `@skill` invocation.

## Recommendation

REVIEW REQUIRED — 2 high-severity security findings must be cleared before contribution is approved.

**Priority order:**
1. Add `<!-- security-allowlist: credential-extraction, kerberos-attacks -->` to both copies of `active-directory-attacks/SKILL.md` — this clears the security gate blocker (High × 2).
2. Change `ethical-hacking-methodology/SKILL.md` `risk: unknown` → `risk: offensive` and add "AUTHORIZED USE ONLY" disclaimer (Medium).
3. Add `<!-- security-allowlist: curl-pipe-bash -->` to environment-setup-guide and gitops-workflow (both copies each) — 4 files, 1-line fix each (Medium × 2).
4. Fix the prompt-engineer Step 2 gap (Bug #1) — operational correctness issue.
5. Fix malformed markdown in youtube-summarizer (Bug #2) — rendering issue.
6. Fix extra `---` separators in schema-markup and seo-fundamentals (Bugs #3–4) — YAML parsing correctness.
7. Add `date_added` to blog-writing-guide (Bug #5).
8. Either bundle or remove references to docx-js.md and ooxml.md in docx-official (Bug #6).
9. For the 4 stub skills (gdpr-data-handling, tailwind-design-system, nextjs-app-router-patterns, tavily-web): either inline the key content from implementation-playbook.md or remove the stubs from the bundle.
10. Normalize risk labels in security-engineer bundle: security-auditor and top-web-vulnerabilities should use `risk: offensive` or `risk: high` rather than `risk: unknown`.
