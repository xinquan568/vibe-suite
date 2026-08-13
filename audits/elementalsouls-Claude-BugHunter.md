# Audit — elementalsouls/Claude-BugHunter

**Repo:** elementalsouls/Claude-BugHunter  
**Audited:** 2026-05-24  
**Auditor:** nlpm auditor pipeline  
**NL Score:** 79/100  
**Security:** CLEAR  
**Artifacts audited:** 65 (14 commands, 51 skills)

---

## NL Score Summary

| File | Score |
|---|---|
| commands/remember.md | 60/100 |
| commands/validate.md | 60/100 |
| commands/intel.md | 60/100 |
| commands/token-scan.md | 60/100 |
| commands/recon.md | 60/100 |
| commands/web3-audit.md | 60/100 |
| commands/triage.md | 60/100 |
| commands/autopilot.md | 60/100 |
| commands/hunt.md | 60/100 |
| commands/report.md | 60/100 |
| commands/chain.md | 60/100 |
| commands/surface.md | 65/100 |
| commands/memory-gc.md | 70/100 |
| commands/pickup.md | 70/100 |
| skills/hunt-cloud-misconfig/SKILL.md | 72/100 |
| skills/hunt-llm-ai/SKILL.md | 73/100 |
| skills/bb-local-toolkit/SKILL.md | 76/100 |
| skills/hunt-mfa-bypass/SKILL.md | 78/100 |
| skills/bug-bounty/SKILL.md | 80/100 |
| skills/hunt-http-smuggling/SKILL.md | 80/100 |
| skills/web2-recon/SKILL.md | 80/100 |
| skills/hunt-dispatch/SKILL.md | 80/100 |
| skills/hunt-saml/SKILL.md | 82/100 |
| skills/vmware-vcenter-attack/SKILL.md | 82/100 |
| skills/okta-attack/SKILL.md | 82/100 |
| skills/offensive-osint/SKILL.md | 82/100 |
| skills/cloud-iam-deep/SKILL.md | 83/100 |
| skills/security-arsenal/SKILL.md | 83/100 |
| skills/apk-redteam-pipeline/SKILL.md | 83/100 |
| skills/evidence-hygiene/SKILL.md | 83/100 |
| skills/meme-coin-audit/SKILL.md | 83/100 |
| skills/enterprise-vpn-attack/SKILL.md | 83/100 |
| skills/hunt-graphql/SKILL.md | 83/100 |
| skills/web3-audit/SKILL.md | 84/100 |
| skills/hunt-sqli/SKILL.md | 84/100 |
| skills/hunt-csrf/SKILL.md | 84/100 |
| skills/hunt-cache-poison/SKILL.md | 84/100 |
| skills/bb-methodology/SKILL.md | 84/100 |
| skills/hunt-api-misconfig/SKILL.md | 85/100 |
| skills/hunt-xxe/SKILL.md | 85/100 |
| skills/hunt-aspnet/SKILL.md | 85/100 |
| skills/hunt-file-upload/SKILL.md | 85/100 |
| skills/hunt-ato/SKILL.md | 85/100 |
| skills/hunt-ntlm-info/SKILL.md | 85/100 |
| skills/redteam-mindset/SKILL.md | 85/100 |
| skills/hunt-oauth/SKILL.md | 85/100 |
| skills/hunt-auth-bypass/SKILL.md | 86/100 |
| skills/hunt-xss/SKILL.md | 86/100 |
| skills/hunt-ssrf/SKILL.md | 86/100 |
| skills/hunt-misc/SKILL.md | 86/100 |
| skills/hunt-business-logic/SKILL.md | 87/100 |
| skills/hunt-race-condition/SKILL.md | 87/100 |
| skills/hunt-idor/SKILL.md | 87/100 |
| skills/supply-chain-attack-recon/SKILL.md | 87/100 |
| skills/hunt-ssti/SKILL.md | 87/100 |
| skills/hunt-subdomain/SKILL.md | 87/100 |
| skills/mid-engagement-ir-detection/SKILL.md | 87/100 |
| skills/bugcrowd-reporting/SKILL.md | 87/100 |
| skills/report-writing/SKILL.md | 87/100 |
| skills/redteam-report-template/SKILL.md | 88/100 |
| skills/hunt-rce/SKILL.md | 88/100 |
| skills/m365-entra-attack/SKILL.md | 88/100 |
| skills/osint-methodology/SKILL.md | 88/100 |
| skills/triage-validation/SKILL.md | 88/100 |
| skills/hunt-sharepoint/SKILL.md | 89/100 |

**Averages:** commands 62/100 · skills 84/100 · overall 79/100

---

## Security Scan

| Surface | Files | Critical | High | Medium | Low |
|---|---|---|---|---|---|
| scripts/*.py | 2 | 0 | 0 | 1 | 0 |
| scripts/*.sh | 3 | 0 | 0 | 1 | 0 |
| hooks/ | 0 | — | — | — | — |
| .mcp.json | 0 | — | — | — | — |
| package.json | 0 | — | — | — | — |
| requirements.txt | 0 | — | — | — | — |
| commands/*.md (Bash injection) | 14 | 0 | 0 | 0 | 0 |

**Security verdict: CLEAR**

One medium finding: `scripts/install-community-skills.sh` clones an external GitHub repo and pipes its installer to bash without pinning to a commit hash (supply chain trust issue, not exploitable remotely). The target repo is explicitly named and the script is labeled optional; no CI/CD invocation detected. No critical or high findings. Contribution not blocked.

---

## Bugs

### BUG-missing-frontmatter-name — all 14 commands

Every command file has only a `description:` field in its frontmatter. The required `name:` field is absent from all 14.

```
commands/remember.md   line 2: description: ...   (no name:)
commands/validate.md   line 2: description: ...   (no name:)
commands/intel.md      line 2: description: ...   (no name:)
commands/token-scan.md line 2: description: ...   (no name:)
commands/surface.md    line 2: description: ...   (no name:)
commands/recon.md      line 2: description: ...   (no name:)
commands/web3-audit.md line 2: description: ...   (no name:)
commands/memory-gc.md  line 2: description: ...   (no name:)
commands/triage.md     line 2: description: ...   (no name:)
commands/autopilot.md  line 2: description: ...   (no name:)
commands/pickup.md     line 2: description: ...   (no name:)
commands/hunt.md       line 2: description: ...   (no name:)
commands/report.md     line 2: description: ...   (no name:)
commands/chain.md      line 2: description: ...   (no name:)
```

**Fix:** Add `name: <command-slug>` as the first frontmatter field in each file.

```markdown
---
name: hunt
description: ...
---
```

**Penalty:** -25 per file. Score impact: commands average drops from 87 to 62.

---

### BUG-missing-frontmatter-allowed-tools — all 14 commands

No command declares `allowed-tools:`. This is a required field per NLPM conventions for command artifacts. Without it, tool permission prompts are undeclared and may surprise users.

**Fix:** Add `allowed-tools: [WebFetch, Bash, Read]` (or the actual tool set used) to each command's frontmatter.

**Penalty:** -5 per file.

---

### BUG-dispatch-duplicate-entries — skills/hunt-dispatch/SKILL.md

The WAPT skill list in the taxonomy print section contains three duplicate entries:

```
hunt-race-condition hunt-race-condition    (lines 102-103)
hunt-cache-poison hunt-cache-poison        (lines 103-104)
hunt-subdomain hunt-subdomain              (lines 103-104)
```

When `hunt-dispatch` prints the taxonomy for operator selection, each of these skills appears twice. This is a copy-paste error in the skill list construction.

**Fix:** Deduplicate each line in the WAPT array. The correct list has each skill name exactly once.

---

## Security Fixes

None required. Security verdict is CLEAR.

---

## Quality Issues

### Q1 — Thin methodology: hunt-cloud-misconfig, hunt-llm-ai

Both skills score below 75 and have notably shorter methodology sections than peer skills:

- `hunt-cloud-misconfig` (72/100): Missing Gate 0 pre-conditions, no bypass techniques section, no real-world examples. The S3/IAM/SSRF content is present but lacks the step-by-step structure of peer skills (hunt-ssrf, cloud-iam-deep).
- `hunt-llm-ai` (73/100): Sparse — no Gate 0, no tooling section, no severity scoring guidance. Prompt injection and model training data exfiltration are covered briefly but not with the attack-path depth of peer skills.

**Recommendation:** Expand both skills to match the 8–10 step structure used by hunt-idor, hunt-ssrf, and hunt-xss. Add Gate 0 checks, bypass table, and at least one real-world example per vulnerability class.

### Q2 — Content overlap: bb-local-toolkit vs bug-bounty

`skills/bb-local-toolkit/SKILL.md` (~1550 lines) and `skills/bug-bounty/SKILL.md` (~1600 lines) both contain the 7-Question Gate, IDOR methodology, SSRF bypass table, and CI/CD deep-dive. This duplication creates divergence risk: a fix to one is not automatically reflected in the other.

**Recommendation:** Designate one as canonical (e.g., `bug-bounty` as the master) and have the other reference it via a Related Skills pointer rather than duplicating the content.

### Q3 — Missing optional frontmatter: 9 skills

Nine skills are missing `sources:` and `report_count:` fields (`hunt-api-misconfig`, `hunt-ssti`, `hunt-file-upload`, `hunt-ato`, `evidence-hygiene`, `meme-coin-audit`, `hunt-dispatch`, `web2-recon`, `bb-local-toolkit`). These fields are advisory but support the auditor pipeline's coverage tracking.

**Recommendation:** Add `sources: operator-notes` and `report_count: 0` stubs to each.

### Q4 — Empty input handling missing: 11 commands

11 of 14 commands have no documented behavior when invoked with no arguments. Only `memory-gc`, `pickup`, and `surface` handle the empty-input case.

Commands that take a target argument (`/hunt`, `/recon`, `/intel`, `/token-scan`, `/web3-audit`) should begin with:

```
If no target is specified: print usage and list recent targets from memory.
```

Commands that operate on a session state (`/triage`, `/validate`, `/chain`, `/autopilot`) should begin with:

```
If no finding or context: prompt the user for what to triage.
```

---

## Cross-Component

### CC-dispatch-skill-gap

`skills/hunt-dispatch/SKILL.md` routes to `hunt-llm-ai` in its taxonomy. `hunt-llm-ai` scores 73/100 (the second-lowest skill score). When the dispatcher routes there, the user receives thin methodology. The dispatcher's quality is bounded by its weakest routed skill.

### CC-offensive-osint-external-delegation

`skills/offensive-osint/SKILL.md` references `docs/references/*.md` files for bulk content (GitHub dork library, passive DNS sources, etc.). These external files are not NLPM-audited artifacts. If the references move or are deleted, the skill silently loses content without any frontmatter version bump.

**Recommendation:** Inline at least one concrete example per section into the SKILL.md itself; treat `references/*.md` as supplemental rather than load-bearing.

---

## Recommendation

**Merge-eligible bugs:** BUG-missing-frontmatter-name (14 files), BUG-dispatch-duplicate-entries (1 file). These are mechanical fixes with no ambiguity.

**BUG-missing-frontmatter-name** is the highest-priority fix: it drops every command to 60/100 and makes command registration unreliable. The fix is trivial — one line per file — and is unambiguously correct.

**BUG-dispatch-duplicate-entries** is a one-line deduplication with clear correct answer.

The skill corpus is strong (average 84/100). The command corpus is structurally well-designed but uniformly missing the required `name:` field — this appears to be a systematic omission from when the commands were authored, not a deliberate choice.

Overall the repo represents a high-quality, well-organized bug-hunting toolkit. Once the frontmatter gaps are resolved, the command corpus should score in the 80–85 range.
