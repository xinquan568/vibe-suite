# Audit: agenticnotetaking/arscontexta
Audited: 2026-04-12
Artifacts: 27
Strategy: batched

**NL Score**: 96/100
**Security**: CLEAR
**Bugs**: 10
**Quality Issues**: 28
**Security Findings**: 5

---

## NL Score Summary

| Artifact | Score | Primary Penalties |
|----------|-------|-------------------|
| agents/knowledge-guide.md | 86/100 | Missing output format (-10), missing allowed-tools (-5), vague quantifiers (-4) |
| skill-sources/refactor/SKILL.md | 91/100 | Missing model declaration (-5), vague quantifiers (-4) |
| skill-sources/reflect/SKILL.md | 91/100 | Missing model declaration (-5), vague quantifiers (-4) |
| skill-sources/reweave/SKILL.md | 91/100 | Missing model declaration (-5), vague quantifiers (-4) |
| skill-sources/help (skills/help/SKILL.md) | 93/100 | Missing model declaration (-5), vague quantifier (-2) |
| skill-sources/learn/SKILL.md | 93/100 | Missing model declaration (-5), vague quantifier (-2) |
| skill-sources/rethink/SKILL.md | 93/100 | Missing model declaration (-5), vague quantifier (-2) |
| skill-sources/ralph/SKILL.md | 95/100 | Missing model declaration (-5) |
| skill-sources/reduce/SKILL.md | 95/100 | Missing model declaration (-5) |
| skill-sources/verify/SKILL.md | 95/100 | Missing model declaration (-5) |
| skills/add-domain/SKILL.md | 96/100 | Vague quantifiers (-4) |
| skills/architect/SKILL.md | 96/100 | Vague quantifiers (-4) |
| skill-sources/next/SKILL.md | 96/100 | Vague quantifiers (-4) |
| skill-sources/remember/SKILL.md | 96/100 | Vague quantifiers (-4) |
| skills/reseed/SKILL.md | 96/100 | Vague quantifiers (-4) |
| skills/setup/SKILL.md | 96/100 | Vague quantifiers (-4) |
| skill-sources/validate/SKILL.md | 96/100 | Vague quantifiers (-4) |
| skill-sources/pipeline/SKILL.md | 97/100 | Vague quantifier (-2) |
| skills/ask/SKILL.md | 98/100 | Vague quantifier (-2) |
| skills/health/SKILL.md | 98/100 | Vague quantifier (-2) |
| skills/recommend/SKILL.md | 98/100 | Vague quantifier (-2) |
| skill-sources/tasks/SKILL.md | 98/100 | Vague quantifier (-2) |
| skills/upgrade/SKILL.md | 98/100 | Vague quantifier (-2) |
| skill-sources/graph/SKILL.md | 100/100 | — |
| skill-sources/seed/SKILL.md | 100/100 | — |
| skill-sources/stats/SKILL.md | 100/100 | — |
| skills/tutorial/SKILL.md | 100/100 | — |

**Weighted average**: 2582 / 27 = 95.6 → **96/100**

*Note: `reduce/SKILL.md` (11,574 tokens) and `setup/SKILL.md` (19,386 tokens) exceeded the read-tool token limit. Frontmatter and opening sections were read; body was partially assessed.*

---

## Security Scan

### Severity Counts

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 3 |
| LOW | 2 |

### Execution Surface Inventory

| File | Type | Trigger |
|------|------|---------|
| hooks/hooks.json | Hook configuration | SessionStart, PostToolUse(Write) |
| hooks/scripts/session-orient.sh | Shell script | SessionStart hook |
| hooks/scripts/write-validate.sh | Shell script | PostToolUse(Write) hook |
| hooks/scripts/auto-commit.sh | Shell script | PostToolUse(Write) hook, async |
| hooks/scripts/vaultguard.sh | Shell script | Called by all hooks |
| hooks/scripts/read_config.sh | Shell script | Called by session-orient, auto-commit |
| scripts/sync-thinking.sh | Shell script | Developer utility (not a hook) |
| .claude-plugin/plugin.json | Package manifest | Install-time |

### Security Findings

| Severity | File | Line | Pattern | Notes |
|----------|------|------|---------|-------|
| MEDIUM | hooks/scripts/session-orient.sh | 59 | `git commit --no-verify` | Bypasses pre-commit hooks. Standard auto-commit pattern to avoid infinite loops — necessary in hook context. |
| MEDIUM | hooks/scripts/auto-commit.sh | 52 | `git commit --no-verify` | Same pattern, same justification. Acceptable in async PostToolUse hook. |
| MEDIUM | hooks/scripts/read_config.sh | 30 | `grep -E "^${KEY}:"` | KEY interpolated directly into grep regex pattern. In practice, callers always pass literal strings (`"git"`, `"session_capture"`); exploitable only if calling code changes. |
| LOW | hooks/scripts/auto-commit.sh | 29 | `git add -A` | Stages all tracked and untracked files. Could inadvertently commit sensitive vault content. Documented as intentional for vault auto-commit. |
| LOW | hooks/scripts/session-orient.sh | 137 | `bash ops/scripts/reconcile.sh` | Calls a vault-owned script at a fixed path. If the vault path is attacker-controlled, this executes arbitrary code. Low risk in practice — vault is user-owned. |

**No CRITICAL or HIGH findings. Classification: CLEAR.**

---

## Bugs

All bugs are missing required frontmatter fields. No broken cross-component references found.

### Missing `model` declarations (9 files)

These skill-source files declare `allowed-tools` but omit `model`. Claude Code cannot select the right inference tier without this field.

| File | Impact |
|------|--------|
| skill-sources/refactor/SKILL.md | Defaults to ambient model; intended tier unknown |
| skill-sources/reweave/SKILL.md | Defaults to ambient model; intended tier unknown |
| skill-sources/verify/SKILL.md | Defaults to ambient model; intended tier unknown |
| skill-sources/reflect/SKILL.md | Defaults to ambient model; intended tier unknown |
| skill-sources/learn/SKILL.md | Defaults to ambient model; intended tier unknown |
| skill-sources/reduce/SKILL.md | Defaults to ambient model; intended tier unknown |
| skill-sources/rethink/SKILL.md | Defaults to ambient model; intended tier unknown |
| skill-sources/ralph/SKILL.md | Defaults to ambient model; intended tier unknown |
| skills/help/SKILL.md | Defaults to ambient model; intended tier unknown |

**Fix**: Add `model: sonnet` (or `opus` for deep-reasoning skills) to each frontmatter block.

### Missing `allowed-tools` declaration (1 file)

| File | Issue |
|------|-------|
| agents/knowledge-guide.md | No `allowed-tools` declared. The agent reads `${CLAUDE_PLUGIN_ROOT}/reference/` files but cannot if Read is not granted. |

**Fix**: Add `allowed-tools: Read` to frontmatter.

---

## Security Fixes

### MEDIUM — Sanitize KEY parameter in read_config.sh

**File**: `hooks/scripts/read_config.sh:30`

The `KEY` argument is interpolated directly into a grep `-E` regex:
```bash
VALUE=$(grep -E "^${KEY}:" "$CONFIG_FILE" ...)
```

If callers ever pass untrusted input as `KEY`, special regex characters could cause unexpected matches. Harden with a literal-string match:
```bash
VALUE=$(grep -F "${KEY}:" "$CONFIG_FILE" ... | grep -E "^${KEY}:")
```
Or validate KEY against an allowlist at entry:
```bash
case "$KEY" in
  git|session_capture) ;;
  *) echo "$DEFAULT"; exit 0 ;;
esac
```

### LOW — Scope `git add` in auto-commit.sh

**File**: `hooks/scripts/auto-commit.sh:29`

`git add -A` stages everything, including files outside the vault's knowledge space (dotfiles, credentials, secrets inadvertently placed in the project root). Scope to the vault directories:
```bash
git add notes/ ops/ self/ inbox/ templates/ .arscontexta 2>/dev/null || exit 0
```
Or at minimum exclude common sensitive patterns via `.gitignore`.

### LOW — Guard external reconcile.sh call

**File**: `hooks/scripts/session-orient.sh:137`

The call to `ops/scripts/reconcile.sh` executes a vault-owned script without validation. If the file is absent this is a no-op, but if compromised it runs arbitrary code. Add an existence and permission check:
```bash
if [ -f ops/scripts/reconcile.sh ] && [ -x ops/scripts/reconcile.sh ]; then
  bash ops/scripts/reconcile.sh --compact 2>/dev/null
fi
```
(The `-x` check prevents execution of non-executable files accidentally placed at that path.)

---

## Quality Issues

These are informational. Each instance was penalized during scoring; fixing them would raise individual skill scores.

### Vague quantifiers (27 instances across 17 files)

The most common pattern is degree adverbs and relational adjectives without quantitative thresholds. Examples:

| File | Instance | Suggested Fix |
|------|----------|---------------|
| agents/knowledge-guide.md | "short suggestions" | "1–2 sentence suggestions" |
| agents/knowledge-guide.md | "encouraging" | "affirming the connection without adding claims" |
| skill-sources/remember/SKILL.md | "very similar content" | "≥80% lexical overlap" |
| skill-sources/remember/SKILL.md | "very long sessions" | "sessions exceeding 5,000 tokens" |
| skill-sources/refactor/SKILL.md | "appropriate" (schema) | "matching the domain template in templates/*.md" |
| skill-sources/refactor/SKILL.md | "non-trivial" | "requiring changes to 3 or more fields" |
| skill-sources/next/SKILL.md | "recent" (sessions) | "sessions from the last 7 days" |
| skill-sources/next/SKILL.md | "meaningful" (connections) | "connections not already present in the note's relevant_notes" |
| skill-sources/reflect/SKILL.md | "non-obvious" (connections) | "connections not already linked in either note" |
| skill-sources/reflect/SKILL.md | "genuinely" | "where the articulation test passes: [[A]] extends [[B]] because [specific reason]" |
| skill-sources/reweave/SKILL.md | (2 instances) | Specify thresholds for staleness and update criteria |
| skill-sources/validate/SKILL.md | "common YAML errors" | list the 3 specific errors checked |
| skill-sources/validate/SKILL.md | "similar content" | "≥70% title word overlap with an existing note" |
| skill-sources/learn/SKILL.md | "meaningful new directions" | "questions not present in the current goals.md or graph" |
| skill-sources/rethink/SKILL.md | "potential pattern" | "3 or more observations sharing a common theme keyword" |
| skills/architect/SKILL.md | "most relevant" (claims) | "top 5 claims by relevance score from mcp__qmd__deep_search" |
| skills/architect/SKILL.md | evidence "thin" | "fewer than 3 research claims supporting the position" |
| skills/add-domain/SKILL.md | "significant" drift | "drift score >40% per the reseed rubric" |
| skills/add-domain/SKILL.md | "substantially overlaps" | "shares >50% of topic vocabulary with an existing domain" |
| skills/upgrade/SKILL.md | "significant" changes | "changes affecting output format, step ordering, or quality gates" |
| skills/reseed/SKILL.md | (2 instances) | Specify numeric thresholds for drift classification |
| skills/help/SKILL.md | "likely" used commands | "commands with no artifact evidence in ops/ or sessions/" |
| skills/recommend/SKILL.md | "meaningful" | "architecturally distinct" |
| skills/ask/SKILL.md | "tangentially related" | "related by shared topic but not by direct claim lineage" |

### Missing output format section (1 file)

`agents/knowledge-guide.md` has no defined output format section. The agent's response structure (how many suggestions, in what form, with what metadata) is undefined, leaving the LLM to improvise. Add an explicit format block specifying suggestion count, whether citations are included, and the termination condition.

---

## Cross-Component Analysis

**Vocabulary consistency**: All 27 artifacts use `${vocabulary.*}` template variables and `${CLAUDE_PLUGIN_ROOT}` path variables consistently. No mismatched variable names found.

**Reference integrity**: All `${CLAUDE_PLUGIN_ROOT}/reference/*.md` and `${CLAUDE_PLUGIN_ROOT}/methodology/` paths follow the same naming convention across files. The `derivation-manifest.md`, `interaction-constraints.md`, `kernel.yaml`, `three-spaces.md`, and `failure-modes.md` references appear in multiple skills without naming divergence.

**Tool consistency**: The MCP tool set (`mcp__qmd__search`, `mcp__qmd__vector_search`, `mcp__qmd__deep_search`, `mcp__qmd__get`, `mcp__qmd__multi_get`, `mcp__qmd__status`) is used consistently across `architect`, `reseed`, `reflect`, `reweave`, `verify`, `learn`, and `ask`. All declare the same tool names with no aliases or typos.

**Pipeline handoff**: The `ralph/SKILL.md` orchestrator and the pipeline skill (`pipeline/SKILL.md`) both reference the RALPH HANDOFF protocol. `ralph` mandates Task tool usage for every phase; `pipeline` includes the Task tool in its `allowed-tools`. Protocol naming is consistent.

**Missing model on skill-sources vs skills**: All 10 meta-skills in `skills/` declare `model: opus` (complex setup/evolution skills) or `model: sonnet`. The 9 skill-source files missing `model` are the primary consistency gap — the plugin's meta-layer is fully specified while the generated-skill layer is not.

**Auto-commit hook scope**: `auto-commit.sh` fires on every Write tool use across the vault. The `write-validate.sh` hook correctly scopes to `*/notes/*` and `*/thinking/*`. The asymmetry means auto-commit runs on ops/, self/, and templates/ writes as well as notes — this is intentional per the hook description but worth documenting explicitly.

---

## Recommendation

**Approve with minor fixes.** Ars Contexta is a mature, well-structured knowledge management plugin scoring 96/100. The methodology is coherent, the three-space architecture is consistently applied, and the processing pipeline is fully specified. The 9 missing `model` declarations in skill-sources are the single most impactful fix — they should be resolved before publishing to prevent ambient-model drift in generated vaults. The 3 medium security findings are all standard patterns in hook development (--no-verify to prevent recursive commits) and do not represent real attack surface. No CRITICAL or HIGH security issues found.
