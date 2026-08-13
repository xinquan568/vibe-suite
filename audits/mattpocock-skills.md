# NLPM Audit: mattpocock/skills
**Date**: 2026-05-11  |  **Artifacts**: 30  |  **Strategy**: batched
**NL Score**: 98/100
**Security**: CLEAR
**Bugs**: 4  |  **Quality Issues**: 16  |  **Security Findings**: 0

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude-plugin/plugin.json | config | 82 | Missing version field; 4 misc skills absent |
| skills/in-progress/handoff/SKILL.md | skill | 90 | No handoff document format specified |
| skills/personal/edit-article/SKILL.md | skill | 90 | Process truncated at step 2a |
| skills/deprecated/qa/SKILL.md | skill | 94 | "relevant" ×3 |
| CLAUDE.md | config | 95 | Minimal content (appropriate for type) |
| skills/engineering/triage/SKILL.md | skill | 96 | "relevant" ×2 |
| skills/deprecated/ubiquitous-language/SKILL.md | skill | 96 | "relevant" ×2 |
| skills/misc/git-guardrails-claude-code/SKILL.md | skill | 98 | "appropriate" vague quantifier |
| skills/in-progress/review/SKILL.md | skill | 98 | "relevant" in sub-agent prompt |
| skills/productivity/write-a-skill/SKILL.md | skill | 98 | "relevant" vague quantifier |
| skills/engineering/to-prd/SKILL.md | skill | 98 | "relevant" vague quantifier |
| skills/engineering/zoom-out/SKILL.md | skill | 98 | "relevant" vague quantifier |
| skills/engineering/prototype/SKILL.md | skill | 98 | "relevant" vague quantifier |
| skills/engineering/diagnose/SKILL.md | skill | 98 | "relevant" vague quantifier |
| skills/misc/setup-pre-commit/SKILL.md | skill | 100 | — |
| skills/misc/migrate-to-shoehorn/SKILL.md | skill | 100 | — |
| skills/misc/scaffold-exercises/SKILL.md | skill | 100 | — |
| skills/in-progress/writing-beats/SKILL.md | skill | 100 | — |
| skills/in-progress/writing-fragments/SKILL.md | skill | 100 | — |
| skills/in-progress/writing-shape/SKILL.md | skill | 100 | — |
| skills/productivity/caveman/SKILL.md | skill | 100 | — |
| skills/productivity/grill-me/SKILL.md | skill | 100 | — |
| skills/personal/obsidian-vault/SKILL.md | skill | 100 | — |
| skills/engineering/grill-with-docs/SKILL.md | skill | 100 | — |
| skills/engineering/setup-matt-pocock-skills/SKILL.md | skill | 100 | — |
| skills/engineering/tdd/SKILL.md | skill | 100 | — |
| skills/engineering/improve-codebase-architecture/SKILL.md | skill | 100 | — |
| skills/engineering/to-issues/SKILL.md | skill | 100 | — |
| skills/deprecated/design-an-interface/SKILL.md | skill | 100 | — |
| skills/deprecated/request-refactor-plan/SKILL.md | skill | 100 | — |

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
| Scripts (repo-level) | scripts/list-skills.sh, scripts/link-skills.sh |
| Scripts (skill-bundled) | skills/misc/git-guardrails-claude-code/scripts/block-dangerous-git.sh, skills/engineering/diagnose/scripts/hitl-loop.template.sh |
| Hooks | none |
| MCP configs | none |
| Package manifests | none |

**scripts/list-skills.sh** — `find` + `sed` pipeline; no network, no eval. CLEAR.

**scripts/link-skills.sh** — creates symlinks under `~/.claude/skills`; includes a guard that aborts if `$DEST` is a symlink into the repo (preventing circular writes). `rm -rf "$target"` is scoped to `$DEST/$name` where `$name` is a basename extracted from the repo tree — not user-supplied. CLEAR.

**block-dangerous-git.sh** — reads JSON from stdin via `jq -r`; pattern-matches against a fixed list of dangerous git commands; exits with code 2 on match. No network, no eval, no credential handling. CLEAR.

**hitl-loop.template.sh** — interactive human-in-loop template; reads user responses into local variables with `read -r`; prints captured values with `printf '%s\n'`. No network, no eval, no shell injection path. Contains a hardcoded localhost URL (`http://localhost:3000`) as an illustrative placeholder, as documented in the file header ("Copy this file, edit the steps below"). CLEAR.

### Security Findings
No security findings.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude-plugin/plugin.json | `skills/misc/git-guardrails-claude-code` missing from skills array | Skill not registered when plugin is installed; users can't invoke `/git-guardrails-claude-code` |
| 2 | .claude-plugin/plugin.json | `skills/misc/setup-pre-commit` missing from skills array | Skill not registered when plugin is installed; users can't invoke `/setup-pre-commit` |
| 3 | .claude-plugin/plugin.json | `skills/misc/migrate-to-shoehorn` missing from skills array | Skill not registered when plugin is installed; users can't invoke `/migrate-to-shoehorn` |
| 4 | .claude-plugin/plugin.json | `skills/misc/scaffold-exercises` missing from skills array | Skill not registered when plugin is installed; users can't invoke `/scaffold-exercises` |

## Security Fixes (PR-worthy, Medium/Low only)
No security fixes needed.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/in-progress/handoff/SKILL.md | Missing output format — no handoff document template or section structure specified | −10 |
| 2 | skills/personal/edit-article/SKILL.md | Process truncated at step 2a with no loop-close, commit, or completion signal | −10 |
| 3 | skills/misc/git-guardrails-claude-code/SKILL.md:39 | "appropriate settings file" — `appropriate` is a vague quantifier; the target file is fully determined by the scope choice made in step 1 | −2 |
| 4 | skills/in-progress/review/SKILL.md:55 | "per file/hunk where relevant" — `relevant` is a vague quantifier in the sub-agent prompt | −2 |
| 5 | skills/productivity/write-a-skill/SKILL.md:62 | "picks the relevant skill" — `relevant` is a vague quantifier | −2 |
| 6 | skills/engineering/to-prd/SKILL.md:58 | "within the relevant decision" — `relevant` is a vague quantifier | −2 |
| 7 | skills/engineering/zoom-out/SKILL.md:7 | "all the relevant modules and callers" — `relevant` is a vague quantifier | −2 |
| 8 | skills/engineering/prototype/SKILL.md:25 | "the full relevant state" — `relevant` is a vague quantifier | −2 |
| 9 | skills/engineering/triage/SKILL.md:65 | "codebase summary relevant to the issue" — `relevant` is a vague quantifier | −2 |
| 10 | skills/engineering/triage/SKILL.md:67 | "trace the relevant code" — `relevant` is a vague quantifier | −2 |
| 11 | skills/engineering/diagnose/SKILL.md:10 | "the relevant modules" — `relevant` is a vague quantifier | −2 |
| 12 | skills/deprecated/qa/SKILL.md:24 | "the relevant area" — `relevant` is a vague quantifier | −2 |
| 13 | skills/deprecated/qa/SKILL.md:70 | "relevant inputs, flags, or configuration" — `relevant` is a vague quantifier | −2 |
| 14 | skills/deprecated/qa/SKILL.md:108 | "relevant to this slice" — `relevant` is a vague quantifier | −2 |
| 15 | skills/deprecated/ubiquitous-language/SKILL.md:13 | "domain-relevant nouns" — `relevant` is a vague quantifier | −2 |
| 16 | skills/deprecated/ubiquitous-language/SKILL.md:64 | "terms relevant for domain experts" — `relevant` is a vague quantifier | −2 |

## Cross-Component

**CLAUDE.md ↔ plugin.json — misc skills absent from manifest**

CLAUDE.md mandates: "Every skill in `engineering/`, `productivity/`, or `misc/` must have…an entry in `.claude-plugin/plugin.json`." All 4 `misc/` skills appear correctly in the top-level `README.md` (lines 172–175) and in `skills/misc/README.md`, confirming they are active, promoted skills. None appear in `plugin.json`. A user who installs the plugin via `claude plugin install` will receive only the 13 engineering/productivity skills; the 4 misc skills are silently omitted.

**All referenced bundled files exist**

- `grill-with-docs` references `CONTEXT-FORMAT.md` and `ADR-FORMAT.md` — both present in the skill directory.
- `prototype` references `LOGIC.md` and `UI.md` — both present.
- `tdd` references `tests.md`, `mocking.md`, `deep-modules.md`, `interface-design.md`, `refactoring.md` — all present.
- `diagnose` references `scripts/hitl-loop.template.sh` — present.
- `triage` references `AGENT-BRIEF.md` and `OUT-OF-SCOPE.md` — both present.
- `improve-codebase-architecture` references `LANGUAGE.md`, `INTERFACE-DESIGN.md`, `../grill-with-docs/CONTEXT-FORMAT.md`, `../grill-with-docs/ADR-FORMAT.md` — all present.
- `setup-matt-pocock-skills` references `domain.md`, `triage-labels.md`, `issue-tracker-github.md`, `issue-tracker-gitlab.md`, `issue-tracker-local.md` — all present.
- `git-guardrails-claude-code` references `scripts/block-dangerous-git.sh` — present.

**personal/in-progress/deprecated skills correctly absent from plugin.json** — no spurious registrations found.

## Recommendation
CLEAR — submit PRs for all 4 bugs (add missing misc skills to plugin.json). No security findings. Quality issues are informational; the `relevant`/`appropriate` instances are low-friction fixes but the deprecated skills are read-only context and not worth a PR on their own.
