# NLPM Audit: Jeffallan/claude-skills
**Date**: 2026-04-12  |  **Artifacts**: 81  |  **Strategy**: progressive
**NL Score**: 92/100
**Security**: CLEAR
**Bugs**: 13  |  **Quality Issues**: 28  |  **Security Findings**: 0

---

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| CLAUDE.md | project-config | 40 | Missing name + description frontmatter, no output-format |
| commands/common-ground/references/assumption-classification.md | reference | 44 | No frontmatter (name + description missing) |
| commands/common-ground/references/reasoning-graph.md | reference | 48 | No frontmatter (name + description missing) |
| commands/common-ground/references/file-management.md | reference | 50 | No frontmatter (name + description missing) |
| commands/project/retrospectives/complete-sprint.md | command | 50 | Missing name; 10+ vague quantifiers (cap reached) |
| commands/project/planning/create-epic-plan.md | command | 62 | Missing name; 4 vague quantifiers |
| commands/project/execution/complete-epic.md | command | 64 | Missing name; 3 vague quantifiers |
| commands/project/execution/execute-ticket.md | command | 64 | Missing name; 3 vague quantifiers; typo |
| commands/project/discovery/approve-synthesis.md | command | 66 | Missing name; 2 vague quantifiers |
| commands/common-ground/COMMAND.md | command | 66 | Missing name; 2 vague quantifiers |
| commands/project/discovery/synthesize-discovery.md | command | 68 | Missing name; 1 vague quantifier |
| commands/project/planning/create-implementation-plan.md | command | 68 | Missing name; 1 vague quantifier |
| commands/project/execution/complete-ticket.md | command | 70 | Missing name |
| commands/project/discovery/create-epic-discovery.md | command | 70 | Missing name |
| skills/api-designer/SKILL.md | skill | 82 | 9 vague quantifier matches (comprehensive×2, proper×2, others) |
| skills/python-pro/SKILL.md | skill | 90 | 5 vague quantifier matches |
| skills/angular-architect/SKILL.md | skill | 92 | 4 vague quantifier matches |
| skills/pandas-pro/SKILL.md | skill | 92 | 4 vague quantifier matches |
| skills/spring-boot-engineer/SKILL.md | skill | 94 | 3 vague quantifier matches |
| skills/monitoring-expert/SKILL.md | skill | 96 | 2 vague quantifier matches |
| skills/test-master/SKILL.md | skill | 96 | 2 vague quantifier matches |
| skills/spark-engineer/SKILL.md | skill | 96 | 2 vague quantifier matches |
| skills/mcp-developer/SKILL.md | skill | 96 | 2 vague quantifier matches |
| skills/cloud-architect/SKILL.md | skill | 98 | 1 vague quantifier match |
| skills/nextjs-developer/SKILL.md | skill | 98 | 1 vague quantifier match |
| skills/cli-developer/SKILL.md | skill | 98 | 1 vague quantifier match |
| skills/sql-pro/SKILL.md | skill | 98 | 1 vague quantifier match |
| skills/secure-code-guardian/SKILL.md | skill | 98 | 1 vague quantifier match |
| skills/kotlin-specialist/SKILL.md | skill | 98 | 1 vague quantifier match |
| .claude-plugin/plugin.json | manifest | 100 | None |
| skills/prompt-engineer/SKILL.md | skill | 100 | None |
| skills/rust-engineer/SKILL.md | skill | 100 | None |
| skills/graphql-architect/SKILL.md | skill | 100 | None |
| skills/devops-engineer/SKILL.md | skill | 100 | None |
| skills/dotnet-core-expert/SKILL.md | skill | 100 | None |
| skills/terraform-engineer/SKILL.md | skill | 100 | None |
| skills/postgres-pro/SKILL.md | skill | 100 | None |
| skills/golang-pro/SKILL.md | skill | 100 | None |
| skills/wordpress-pro/SKILL.md | skill | 100 | None |
| skills/django-expert/SKILL.md | skill | 100 | None |
| skills/fastapi-expert/SKILL.md | skill | 100 | None |
| skills/swift-expert/SKILL.md | skill | 100 | None |
| skills/java-architect/SKILL.md | skill | 100 | None |
| skills/legacy-modernizer/SKILL.md | skill | 100 | None |
| skills/microservices-architect/SKILL.md | skill | 100 | None |
| skills/feature-forge/SKILL.md | skill | 100 | None |
| skills/spec-miner/SKILL.md | skill | 100 | None |
| skills/vue-expert-js/SKILL.md | skill | 100 | None |
| skills/shopify-expert/SKILL.md | skill | 100 | None |
| skills/game-developer/SKILL.md | skill | 100 | None |
| skills/code-reviewer/SKILL.md | skill | 100 | None |
| skills/fullstack-guardian/SKILL.md | skill | 100 | None |
| skills/fine-tuning-expert/SKILL.md | skill | 100 | None |
| skills/debugging-wizard/SKILL.md | skill | 100 | None |
| skills/php-pro/SKILL.md | skill | 100 | None |
| skills/playwright-expert/SKILL.md | skill | 100 | None |
| skills/the-fool/SKILL.md | skill | 100 | None |
| skills/sre-engineer/SKILL.md | skill | 100 | None |
| skills/nestjs-expert/SKILL.md | skill | 100 | None |
| skills/vue-expert/SKILL.md | skill | 100 | None |
| skills/architecture-designer/SKILL.md | skill | 100 | None |
| skills/flutter-expert/SKILL.md | skill | 100 | None |
| skills/embedded-systems/SKILL.md | skill | 100 | None |
| skills/react-expert/SKILL.md | skill | 100 | None |
| skills/database-optimizer/SKILL.md | skill | 100 | None |
| skills/security-reviewer/SKILL.md | skill | 100 | None |
| skills/csharp-developer/SKILL.md | skill | 100 | None |
| skills/code-documenter/SKILL.md | skill | 100 | None |
| skills/kubernetes-specialist/SKILL.md | skill | 100 | None |
| skills/salesforce-developer/SKILL.md | skill | 100 | None |
| skills/rails-expert/SKILL.md | skill | 100 | None |
| skills/rag-architect/SKILL.md | skill | 100 | None |
| skills/javascript-pro/SKILL.md | skill | 100 | None |
| skills/websocket-engineer/SKILL.md | skill | 100 | None |
| skills/laravel-specialist/SKILL.md | skill | 100 | None |
| skills/typescript-pro/SKILL.md | skill | 100 | None |
| skills/react-native-expert/SKILL.md | skill | 100 | None |
| skills/cpp-pro/SKILL.md | skill | 100 | None |
| skills/atlassian-mcp/SKILL.md | skill | 100 | None |
| skills/ml-pipeline/SKILL.md | skill | 100 | None |
| skills/chaos-engineer/SKILL.md | skill | 100 | None |

**Score distribution:** 51 skills at 100 · 6 skills 96–98 · 4 skills 90–94 · 1 skill 82 · 4 commands 64–70 · 4 commands/refs below 70 · CLAUDE.md 40

---

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks | 0 files |
| Scripts | 5 files (migrate-frontmatter.py, test-makefile.sh, update-docs.py, validate-markdown.py, validate-skills.py) |
| MCP configs (.mcp.json) | Not present |
| Package manifests (package.json, requirements.txt) | Not present |

### Security Findings

No security findings.

All five scripts were reviewed:

- **migrate-frontmatter.py** — YAML frontmatter migration utility. Reads/writes files within the `skills/` directory. No network calls, no eval/exec, no shell=True. Uses `json.load()` with a safe YAML fallback parser. Clean.
- **test-makefile.sh** — Tests Makefile targets using a temporary directory (`mktemp -d`) with `trap cleanup EXIT` ensuring cleanup. Reads `version.json` via `python -c "import json; print(json.load(open('version.json'))['version'])"` — a static one-liner with no injection vector. Clean.
- **update-docs.py** — Updates documentation markers (version, skill counts) across local files. No network calls; reads from filesystem and writes back within repo. Dry-run mode available. Clean.
- **validate-markdown.py** — Validates markdown table structure and code fence pairing. Read-only (no writes). No network calls. Clean.
- **validate-skills.py** — Comprehensive YAML and structural validation for skill files. Read-only on skill files; writes to stdout only. Uses `json.load()` / `yaml.safe_load()` (when PyYAML present). Clean.

---

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | commands/project/retrospectives/complete-sprint.md | Missing `name` field in frontmatter | Command cannot be registered by name in Claude Code; referenced as anonymous |
| 2 | commands/project/retrospectives/complete-epic.md | Missing `name` field in frontmatter | Same — anonymous registration |
| 3 | commands/project/discovery/approve-synthesis.md | Missing `name` field in frontmatter | Same |
| 4 | commands/project/discovery/synthesize-discovery.md | Missing `name` field in frontmatter | Same |
| 5 | commands/project/discovery/create-epic-discovery.md | Missing `name` field in frontmatter | Same |
| 6 | commands/project/planning/create-epic-plan.md | Missing `name` field in frontmatter | Same |
| 7 | commands/project/planning/create-implementation-plan.md | Missing `name` field in frontmatter | Same |
| 8 | commands/project/execution/execute-ticket.md | Missing `name` field in frontmatter | Same |
| 9 | commands/project/execution/complete-ticket.md | Missing `name` field in frontmatter | Same |
| 10 | commands/common-ground/COMMAND.md | Missing `name` field in frontmatter | Same |
| 11 | commands/common-ground/references/assumption-classification.md | No frontmatter block at all (missing `name` and `description`) | Not registerable; scoring treats as broken artifact |
| 12 | commands/common-ground/references/file-management.md | No frontmatter block at all | Same |
| 13 | commands/common-ground/references/reasoning-graph.md | No frontmatter block at all | Same |

**Note on reference files (bugs 11–13):** These are contextually loaded reference documents — COMMAND.md routes to them via its Reference Guide table. Their lack of frontmatter is likely intentional (they are not user-invocable). The NLPM scanner treats them as standalone artifacts and penalizes accordingly. The real fix may be documentation (noting they are sub-references) rather than adding frontmatter. Recommend confirming with the project author before filing a PR for these three.

---

## Security Fixes (PR-worthy, Medium/Low only)

No security findings. No security fix PRs warranted.

---

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | commands/project/retrospectives/complete-sprint.md | 10+ vague quantifiers: "comprehensive", "appropriate", "relevant", "various", "effective", etc. | −20 (cap) |
| 2 | commands/project/planning/create-epic-plan.md | 4 vague quantifiers: "comprehensive", "appropriate", "relevant" | −8 |
| 3 | commands/project/retrospectives/complete-epic.md | 3 vague quantifiers: "comprehensive", "appropriate" | −6 |
| 4 | commands/project/execution/execute-ticket.md | 3 vague quantifiers + typo "unforseen sideffects" (line 50) | −6 + quality |
| 5 | commands/common-ground/COMMAND.md | 2 vague quantifiers: "appropriate", "relevant" | −4 |
| 6 | commands/project/discovery/approve-synthesis.md | 2 vague quantifiers | −4 |
| 7 | commands/project/discovery/synthesize-discovery.md | 1 vague quantifier | −2 |
| 8 | commands/project/planning/create-implementation-plan.md | 1 vague quantifier | −2 |
| 9 | All 10 command files | Missing `allowed-tools` declaration | −5 each |
| 10 | skills/api-designer/SKILL.md | 9 pattern matches including "comprehensive" ×2, "proper" ×2; note: some matches are substrings in JSON schema ("properties:") | −18 |
| 11 | skills/python-pro/SKILL.md | 5 vague quantifier matches | −10 |
| 12 | skills/angular-architect/SKILL.md | 4 vague quantifier matches | −8 |
| 13 | skills/pandas-pro/SKILL.md | 4 vague quantifier matches | −8 |
| 14 | skills/spring-boot-engineer/SKILL.md | 3 vague quantifier matches | −6 |
| 15 | skills/monitoring-expert/SKILL.md | 2 vague quantifier matches | −4 |
| 16 | skills/test-master/SKILL.md | 2 vague quantifier matches | −4 |
| 17 | skills/spark-engineer/SKILL.md | 2 vague quantifier matches | −4 |
| 18 | skills/mcp-developer/SKILL.md | 2 vague quantifier matches | −4 |
| 19 | skills/cloud-architect/SKILL.md | 1 vague quantifier match | −2 |
| 20 | skills/nextjs-developer/SKILL.md | 1 vague quantifier match | −2 |
| 21 | skills/cli-developer/SKILL.md | 1 vague quantifier match | −2 |
| 22 | skills/sql-pro/SKILL.md | 1 vague quantifier match | −2 |
| 23 | skills/secure-code-guardian/SKILL.md | 1 vague quantifier match | −2 |
| 24 | skills/kotlin-specialist/SKILL.md | 1 vague quantifier match | −2 |
| 25 | CLAUDE.md | Missing `name`, `description`, `output-format` frontmatter (project config, not a plugin artifact) | −60 (scoring artifact; not a real bug) |
| 26 | skills/api-designer/SKILL.md | Vague scanner false positives: "proper" matches substrings in YAML schema examples ("properties:"). Consider scoping vague word detection to prose sections only. | informational |
| 27 | commands/project/execution/execute-ticket.md | Typo on line 50: "unforseen sideffects" → "unforeseen side effects" | informational |
| 28 | All commands | No `argument-hint` validation for empty `$ARGUMENTS` on complete-ticket.md (ticket key is optional, handled gracefully) — well-handled | informational (no penalty) |

---

## Cross-Component

**Workflow chain consistency:** All project commands participate in a well-documented linear workflow chain (`create-epic-discovery` → `synthesize-discovery` → `approve-synthesis` → `create-epic-plan` → `create-implementation-plan` → `execute-ticket` → `complete-ticket` → `complete-epic` → `complete-sprint`). The chain is clearly visualized in each command's "Workflow Chain" section. Cross-references are accurate.

**Command ↔ Skill coupling:** Commands depend on the `atlassian-mcp` skill for Jira/Confluence access, but this dependency is not declared anywhere in command frontmatter. The lack of `allowed-tools` means there is no machine-readable record of which tools commands invoke. This is the most actionable structural gap.

**Reference file routing:** `COMMAND.md` (common-ground) has a Reference Guide table correctly routing to `references/assumption-classification.md`, `references/file-management.md`, and `references/reasoning-graph.md`. All three reference files exist and are reachable. The routing is valid.

**Skill cross-references (`related-skills`):** Spot-checked a sample of `related-skills` entries. All referenced skill directory names resolve to existing directories (e.g., `fullstack-guardian`, `test-master`, `devops-engineer`). No broken cross-references detected.

**plugin.json vs filesystem:** `plugin.json` declares `"skills": "./skills/"` and `"commands": "./commands/"` — both paths exist and contain the expected content. Version is `0.4.11`.

**CLAUDE.md:** Comprehensive project configuration document covering skill authorship standards, release checklist, and progressive disclosure architecture. Well-structured. The only NL-scoring issue is the absence of YAML frontmatter, which is expected for project configuration and not a real artifact defect.

**No orphaned components detected.** No contradictions between components found.

---

## Recommendation

CLEAR — submit PRs for all bugs and NL quality fixes.

**Priority 1 (bugs, will fix registration):** Add `name` field to all 10 command frontmatter blocks. The fix is mechanical: each command's name should match its filename without the `.md` extension (e.g., `complete-sprint`, `execute-ticket`, `COMMAND.md` → `common-ground`). Open one PR per command directory or a single omnibus PR.

**Priority 2 (quality, commands):** Add `allowed-tools` to all command frontmatter, declaring the MCP tools and built-in tools each command calls. This makes tool dependencies explicit and enables static validation.

**Priority 3 (quality, skills):** Reduce vague quantifiers in `api-designer`, `python-pro`, `angular-architect`, `pandas-pro`, and `spring-boot-engineer` SKILL.md files. Replace "comprehensive", "appropriate", "proper" with specific, testable language where used as qualifiers (not in technical names like "comprehensive OpenAPI spec").

**Priority 4 (reference files):** Confirm with project author whether `commands/common-ground/references/*.md` files should have frontmatter. If they are purely contextual reference documents (not user-invocable), add a comment at the top clarifying their role. If they should be addressable independently, add minimal frontmatter.

**Security:** No action required. All scripts are clean utility tools with no dangerous patterns.
