# NLPM Audit: addyosmani/agent-skills
**Date**: 2026-04-06  |  **Artifacts**: 35  |  **Strategy**: batched
**NL Score**: 94/100
**Security**: BLOCKED
**Bugs**: 0  |  **Quality Issues**: 25  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude/commands/build.md | command | 85 | No allowed-tools declared; no empty-input handling |
| .claude/commands/code-simplify.md | command | 85 | No allowed-tools declared; no empty-input handling |
| .claude/commands/plan.md | command | 85 | No allowed-tools declared; no empty-input handling |
| .claude/commands/review.md | command | 85 | No allowed-tools declared; no empty-input handling |
| .claude/commands/ship.md | command | 85 | No allowed-tools declared; no empty-input handling |
| .claude/commands/spec.md | command | 85 | No allowed-tools declared; no empty-input handling |
| .claude/commands/test.md | command | 85 | No allowed-tools declared; no empty-input handling |
| agents/README.md | documentation | 90 | No frontmatter (README convention; no formal penalty) |
| agents/code-reviewer.md | agent | 90 | No model declared (R10); only one example block (R09) |
| agents/security-auditor.md | agent | 90 | No model declared (R10); only one example block (R09) |
| agents/test-engineer.md | agent | 90 | No model declared (R10); only one example block (R09) |
| skills/idea-refine/SKILL.md | skill | 93 | Env-specific absolute path in optional bash command; minor vague language |
| skills/context-engineering/SKILL.md | skill | 94 | "relevant" used without measurable criteria (×3, R01) |
| skills/documentation-and-adrs/SKILL.md | skill | 94 | "significant" vague quantifier (×3, R01) |
| skills/performance-optimization/SKILL.md | skill | 94 | "unnecessary", "significantly" vague quantifiers (R01) |
| skills/source-driven-development/SKILL.md | skill | 94 | "relevant" vague quantifier (×3, R01) |
| hooks/hooks.json | config | 95 | Valid; registers one hook type only |
| skills/frontend-ui-engineering/SKILL.md | skill | 96 | Minor vague language (R01) |
| skills/spec-driven-development/SKILL.md | skill | 96 | Minor vague language (R01) |
| skills/using-agent-skills/SKILL.md | skill | 96 | "relevant" vague (×2, R01) |
| CLAUDE.md | rules | 98 | "significant architectural choices" in boundaries (R01) |
| .claude-plugin/plugin.json | manifest | 98 | Well-formed; all required fields present |
| skills/api-and-interface-design/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/browser-testing-with-devtools/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/ci-cd-and-automation/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/code-review-and-quality/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/code-simplification/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/debugging-and-error-recovery/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/deprecation-and-migration/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/git-workflow-and-versioning/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/incremental-implementation/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/planning-and-task-breakdown/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/security-and-hardening/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/shipping-and-launch/SKILL.md | skill | 98 | Minor vague language (R01) |
| skills/test-driven-development/SKILL.md | skill | 99 | Near-perfect |

**Weighted average**: 3278 / 35 = 93.7 → **94/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 0 |
| Medium | 2 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks (registered in hooks.json) | hooks/session-start.sh |
| Hooks (opt-in extras, not auto-registered) | hooks/sdd-cache-pre.sh, hooks/sdd-cache-post.sh, hooks/simplify-ignore.sh |
| Scripts (test utility, not registered) | hooks/simplify-ignore-test.sh |
| MCP configs | None |
| Package manifests | None |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Critical | hooks/simplify-ignore-test.sh | 34 | eval-cmd-subst | `eval "$(sed -n '/^filter_file()/,/^}/p' hooks/simplify-ignore.sh)"` — executes code extracted from a file at runtime; if simplify-ignore.sh is compromised, this eval would execute the malicious payload in the test runner. |
| 2 | Medium | hooks/sdd-cache-pre.sh | 71 | network-call | `curl -sI … "$URL"` makes an outbound HEAD request to a user-agent-supplied URL without domain allowlisting; could be used for SSRF or internal network probing. |
| 3 | Medium | hooks/sdd-cache-post.sh | 82 | network-call | `curl -sI -L … "$URL"` follows HTTP redirects to a user-agent-supplied URL without redirect-target validation; redirect chain could reach internal services. |
| 4 | Low | hooks/session-start.sh | 13 | json-injection | `$CONTENT` (contents of SKILL.md) inserted into a bare heredoc JSON string without escaping; double-quotes or backslashes in the skill file produce malformed JSON output. |
| 5 | Low | hooks/sdd-cache-post.sh | 118 | file-write-external-content | Arbitrary web content written to `.claude/sdd-cache/*.json` without content-type or size validation; a large or crafted response could fill disk or embed instruction-like text. |

## Bugs (PR-worthy)
No structural bugs found. All required frontmatter fields are present on their respective artifact types, all cross-references resolve to existing files, and no tool is invoked without being available.

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | hooks/sdd-cache-pre.sh | curl HEAD request to unvalidated URL (Medium) | Validate URL scheme is `https` and optionally allowlist domains before invoking curl; add `--max-redirs 0` to prevent redirect following in a HEAD check. |
| 2 | hooks/sdd-cache-post.sh | curl follows redirects to unvalidated URL (Medium) | Add URL validation before curl; use `--max-redirs 3` or `0`; log the final resolved URL. |
| 3 | hooks/session-start.sh | SKILL.md content injected into JSON without escaping (Low) | Replace heredoc JSON construction with `jq -n --arg msg "$CONTENT" '{"priority":"IMPORTANT","message":$msg}'` for safe, properly escaped JSON output. |
| 4 | hooks/sdd-cache-post.sh | External web content stored without size/type guard (Low) | Add a max-content-size check (e.g., `${#CONTENT} -gt 524288`) and skip caching if the limit is exceeded. |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | agents/security-auditor.md | No `model` field in frontmatter (R10) | -5 |
| 2 | agents/security-auditor.md | Only one example block — the output template (R09) | -5 |
| 3 | agents/test-engineer.md | No `model` field in frontmatter (R10) | -5 |
| 4 | agents/test-engineer.md | Only one example block — the output template (R09) | -5 |
| 5 | agents/code-reviewer.md | No `model` field in frontmatter (R10) | -5 |
| 6 | agents/code-reviewer.md | Only one example block — the output template (R09) | -5 |
| 7 | .claude/commands/plan.md | No `allowed-tools` in frontmatter (R11) | -5 |
| 8 | .claude/commands/plan.md | No empty-input handling (R15) | -10 |
| 9 | .claude/commands/ship.md | No `allowed-tools` in frontmatter (R11) | -5 |
| 10 | .claude/commands/ship.md | No empty-input handling (R15) | -10 |
| 11 | .claude/commands/spec.md | No `allowed-tools` in frontmatter (R11) | -5 |
| 12 | .claude/commands/spec.md | No empty-input handling (R15) | -10 |
| 13 | .claude/commands/review.md | No `allowed-tools` in frontmatter (R11) | -5 |
| 14 | .claude/commands/review.md | No empty-input handling (R15) | -10 |
| 15 | .claude/commands/build.md | No `allowed-tools` in frontmatter (R11) | -5 |
| 16 | .claude/commands/build.md | No empty-input handling (R15) | -10 |
| 17 | .claude/commands/test.md | No `allowed-tools` in frontmatter (R11) | -5 |
| 18 | .claude/commands/test.md | No empty-input handling (R15) | -10 |
| 19 | .claude/commands/code-simplify.md | No `allowed-tools` in frontmatter (R11) | -5 |
| 20 | .claude/commands/code-simplify.md | No empty-input handling (R15) | -10 |
| 21 | skills/documentation-and-adrs/SKILL.md | "significant" vague quantifier ×3 without measurable criteria (R01) | -6 |
| 22 | skills/performance-optimization/SKILL.md | "unnecessary" and "significantly" vague quantifiers (R01) | -6 |
| 23 | skills/source-driven-development/SKILL.md | "relevant" used ×3 without measurable criteria (R01) | -6 |
| 24 | skills/context-engineering/SKILL.md | "relevant" used ×3 without measurable criteria (R01) | -6 |
| 25 | skills/idea-refine/SKILL.md | Optional bash command uses `/mnt/skills/user/…` absolute path; only valid in specific plugin-mount contexts, not when running from repo root | -5 |

## Cross-Component
- **hooks.json vs. hook scripts**: hooks.json registers only `SessionStart → session-start.sh`. The sdd-cache and simplify-ignore hooks are documented as opt-in extras in `hooks/SDD-CACHE.md` and `hooks/SIMPLIFY-IGNORE.md`. This is intentional — no orphan scripts.
- **commands → agents**: `/ship` fans out to `code-reviewer`, `security-auditor`, and `test-engineer` using the exact `name` fields defined in those agent files. No drift.
- **skills → references**: All `references/*.md` files cited in skills (`references/orchestration-patterns.md`, `references/performance-checklist.md`, `references/security-checklist.md`, `references/accessibility-checklist.md`, `references/testing-patterns.md`) exist. No broken links.
- **idea-refine → support files**: `skills/idea-refine/frameworks.md`, `refinement-criteria.md`, and `examples.md` all exist. No broken links.
- **CLAUDE.md**: Accurately describes the repo structure, skills-by-phase matrix, and conventions. No stale references detected.

## Recommendation
**BLOCKED — do not submit PRs. File private security report.**

A Critical security finding exists in `hooks/simplify-ignore-test.sh` (line 34): `eval` with `$(sed …)` command substitution dynamically executes code extracted from `hooks/simplify-ignore.sh`. While this is in a developer test utility that is not automatically triggered, the pattern creates a supply-chain vector — a compromised `simplify-ignore.sh` would be eval'd silently during test runs. This finding must be addressed (or disclosed privately and accepted with documented rationale) before any public PRs are submitted.

The NL quality score (94/100) is strong. Once the security gate is cleared, the quality issues in this report are all straightforward improvements suitable for open PRs: add `model` to agent frontmatter, add `allowed-tools` and empty-input guards to commands, and replace the few vague quantifiers with measurable language.
