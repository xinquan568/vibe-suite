---
repo: nyldn/claude-octopus
audited_by: nlpm-auditor
audit_date: 2026-04-24
mode: re-audit
prior_audit_date: 2026-04-16
prior_score: 79
artifact_count: 127
recommendation: REVIEW
nlpm_score: 82
---

# NLPM Re-Audit: nyldn/claude-octopus
**Date**: 2026-04-24  |  **Artifacts**: 127  |  **Strategy**: progressive  |  **Mode**: re-audit vs 2026-04-16
**NL Score**: 82/100 (+3 vs prior 79)
**Recommendation**: REVIEW
**Bugs**: 4 (2 resolved, 2 new verified)  |  **Quality Issues**: 8 persistent  |  **Security**: 2 HIGH still open

---

## NL Score Summary (sorted ascending)

| Category | Files | Avg Score | Delta | Notes |
|----------|-------|-----------|-------|-------|
| `.github/agents/` (GH Actions subagents) | 10 | 65 | 0 | Non-standard tool names unresolved |
| `agents/personas/` (rich persona agents) | 32 | 82 | -3 | 16 still missing tools declaration |
| `.claude/commands/` (slash commands) | 48 | 80 | +6 | 5 now have allowed-tools (was 2) |
| `agents/droids/` (task-specific agents) | 10 | 85 | +7 | BUG-002 fixed: tools now declared |
| `agents/skills/` (skill-router agents) | 3 | 82 | +10 | Better scoped, cleaner descriptions |
| `.claude/agents/` (default subagents) | 10 | 85 | +1 | Stable, no regressions |
| `config/providers/CLAUDE.md` (provider docs) | 6 | 82 | +2 | Added OpenCode provider doc |
| `config/workflows/CLAUDE.md` | 1 | 85 | 0 | Unchanged |
| `agents/principles/` (critique rules) | 5 | 90 | +8 | Added write-intent.md (new, high quality) |
| `CLAUDE.md` (root) | 1 | 90 | +11 | Substantially expanded, comprehensive |
| `vendors/ui-ux-pro-max-skill/CLAUDE.md` | 1 | 95 | new | New vendor skill, high quality |
| **Overall** | **127** | **82** | **+3** | |

**Weighted NL Score: 82 / 100** (+3 vs prior 79/100)

---

## Finding Verification: Prior Audit vs HEAD

### Resolved Findings

| Original Finding | Status | Evidence |
|-----------------|--------|---------|
| BUG-002: `agents/droids/` missing tools declarations | RESOLVED | All 10 droids now declare `tools: ["All tools"]` |
| BUG-006: `openclaw-admin.md` wrong installation domain (`gogcli.sh`) | RESOLVED | Domain corrected to `openclaw.ai` in body text |

### Persistent Findings

| Original Finding | Status | Evidence |
|-----------------|--------|---------|
| BUG-001: `.github/agents/` use non-standard tool names | PERSISTENT | Still using `read`, `search`, `execute` instead of `Read`, `Glob/Grep`, `Bash` |
| FINDING-01: curl-pipe-sh in `agents/personas/openclaw-admin.md` | PARTIALLY FIXED | Domain corrected from `gogcli.sh` to `openclaw.ai`; curl-pipe-sh pattern remains |
| FINDING-02: curl-pipe-sh in `skills/skill-claw/SKILL.md` | PERSISTENT | Three instances still present (lines 184, 185, 210) |
| QUALITY-002: `.claude/commands/` missing `allowed-tools` | PARTIALLY FIXED | 5/48 now have allowed-tools (was 2/49); 43/48 still missing |
| QUALITY-013: Personas missing tools declarations | PERSISTENT | 16/32 personas still missing `tools:` field |

### New Findings (introduced at HEAD)

| Finding | Severity | Description |
|---------|----------|-------------|
| BUG-N1: `agents/personas/product-writer.md` — zero examples despite `model: sonnet` | MEDIUM | Body is 394 lines, no `examples:` block in frontmatter, no output format section |
| BUG-N2: `.claude/commands/` delegation commands with no output format (-10 each) | MEDIUM | ~42/48 commands lack explicit output format; systemic gap |

---

## Bugs

### BUG-001 — PERSISTENT — `.github/agents/` files use non-standard tool names

**Files:** All 10 files in `.github/agents/*.agent.md`
**Issue:** Every file declares tools using lowercase names not recognized by Claude Code: `read`, `search`, `execute`, `edit`. Valid tool names are `Read`, `Glob`, `Grep`, `Bash`, `Edit`, `Write`, etc. Claude Code's tool resolution is case-sensitive. These agents will be instantiated with no functional tools, making their workflows non-executable.
**Example (code-reviewer.agent.md):**
```yaml
tools:
  - read
  - search
  - execute
```
**Fix:** Replace with correct names: `Read` for file reading, `Glob`/`Grep` for search, `Bash` for execution, `Edit` for file editing.
**Severity:** BUG — agents cannot use any tools as configured. Unchanged since 2026-04-16.

---

### BUG-002 — RESOLVED — `agents/droids/` missing tools declarations

**Status:** Fixed. All 10 droid agents now declare `tools: ["All tools"]`. The original BUG-002 is closed.

---

### BUG-N1 — NEW — `agents/personas/product-writer.md` is 394 lines with no examples or output format

**File:** `agents/personas/product-writer.md`
**Issue:** At 394 lines this is the longest persona file. It has no `examples:` array in frontmatter (-15) and no "Output Format" section in the body (-10). The body is predominantly descriptive with no behavioral grounding. This is the outlier in the persona category — all other high-traffic personas (backend-architect, frontend-developer, security-auditor) have examples.
**Severity:** MEDIUM (functional, but low behavioral accuracy for a frequently-used persona).

---

### BUG-N2 — NEW — 16 personas still missing `tools:` declaration

**Files (16):** `docs-architect.md`, `business-analyst.md`, `product-writer.md`, `graphql-architect.md`, `exec-communicator.md`, `academic-writer.md`, `ai-engineer.md`, `mermaid-expert.md`, `incident-responder.md`, `deployment-engineer.md`, `cloud-architect.md`, `context-manager.md`, `devops-troubleshooter.md`, `ux-researcher.md`, `typescript-pro.md`, `test-automator.md`
**Issue:** Per original audit QUALITY-013, these 16 personas (50% of the category) have no `tools:` field. Without tool declarations, invocation as a Claude Code subagent silently restricts the agent to text generation only. This was flagged in the original audit and remains unaddressed. Promoting to BUG status since the droids fix (BUG-002) demonstrates this category accepts tool declarations.
**Severity:** BUG — agents silently non-functional as subagents for tool-dependent tasks.

---

## Security

### FINDING-01 — HIGH — curl-pipe-sh in `agents/personas/openclaw-admin.md` (partially improved)

**File:** `agents/personas/openclaw-admin.md`, line 112
**Pattern:** `curl -fsSL https://openclaw.ai/install.sh | bash`
**Change since prior audit:** Domain corrected from `gogcli.sh` to `openclaw.ai` (BUG-006 resolved). The curl-pipe-sh pattern itself remains. This is an improvement in correctness but not in security posture.
**Severity:** HIGH — arbitrary remote script execution from an external domain, no hash verification, no content inspection gate.

**Recommended fix:**
```bash
# Replace bare curl-pipe-sh with download-then-inspect pattern:
curl -fsSL https://openclaw.ai/install.sh -o /tmp/openclaw-install.sh
# Review script before executing
less /tmp/openclaw-install.sh
# Then run explicitly:
bash /tmp/openclaw-install.sh
```

---

### FINDING-02 — HIGH — curl-pipe-sh in `skills/skill-claw/SKILL.md` (unchanged)

**File:** `skills/skill-claw/SKILL.md`, lines 184, 185, 210
**Pattern:** `curl -fsSL https://openclaw.ai/install.sh | bash`
**Status:** Unchanged from prior audit. Three separate instances across macOS, Ubuntu/Debian install rows, and an explicit installation code block.
**Severity:** HIGH — same attack surface as FINDING-01, higher exposure due to multiple occurrences and explicit code-block presentation that Claude is more likely to execute directly.

---

## Quality Issues

### QUALITY-001 — PERSISTENT — `.github/agents/` minimal stubs score ~65/100

No behavioral guidance, no examples (-15 per file), no model declaration (-5 per file), no output format (-10 per file). Combined with BUG-001 tool names, these agents cannot function as intended in GitHub Actions CI/CD workflows. Category score unmoved at 65 since prior audit.

**Affected files (10):** All files in `.github/agents/`

---

### QUALITY-002 — PARTIALLY FIXED — `.claude/commands/` `allowed-tools` coverage at 10% (5/48)

Commands with `allowed-tools` declared: `setup.md`, `retro.md`, `costs.md`, `history.md`, `doctor.md`. The remaining 43/48 commands omit this field. This is an improvement from 2/49 in the prior audit (3 new additions), but 90% of commands remain without tool declarations.

Per R15 (least-privilege tools), commands should declare which tools they use. Without `allowed-tools`, the command surface is unrestricted.

**Top priority for allowed-tools addition:** `embrace.md`, `factory.md`, `parallel.md`, `multi.md`, `develop.md`, `discover.md`, `deliver.md`, `define.md`.

---

### QUALITY-003 — PERSISTENT — No output format in ~42/48 commands (-10 each)

Of 48 command files, only ~6 define an explicit output format section: `costs.md`, `discover.md`, `embrace.md`, `meta-prompt.md`, `extract.md`, `prd-score.md`. The remaining 42 commands — including long, complex files like `plan.md` (563 lines), `brainstorm.md` (249 lines), and `multi.md` (231 lines) — do not define what their output looks like. This creates unpredictable response formats when commands are used programmatically.

---

### QUALITY-004 — PERSISTENT — Vague quantifiers in persona bodies (-2 to -8 per file)

24 of 32 personas contain at least one vague quantifier. Most common: "appropriate", "relevant", "various", "several", "reasonable". Under R01, each occurrence costs -2 (capped at -20). Most files absorb -2 to -6 per vague word cluster. The 8 personas free of vague language are: `backend-architect.md`, `tdd-orchestrator.md`, `code-reviewer.md`, `debugger.md`, `security-auditor.md`, `frontend-developer.md`, `database-architect.md`, `python-pro.md`.

---

### QUALITY-005 — PERSISTENT — CLAUDE.md root too long (290+ lines, -5)

The root `CLAUDE.md` is 290+ lines, exceeding the 200-line threshold from R33 (-5). Despite this, its content is high-quality and substantially actionable (visual indicators, file creation policy, workflow reference, cost awareness, provider detection). The score penalty is mechanical; the quality is sound. Recommend splitting provider detection and cost awareness into a dedicated `config/REFERENCE.md` to bring CLAUDE.md under 200 lines.

---

### QUALITY-006 — PERSISTENT — `agents/principles/` reference files use non-standard format

The 5 principle files in `agents/principles/` are not formatted as agent definitions (no `name:`/`model:`/`tools:` frontmatter) nor as NLPM skill files (no `name:`/`description:` frontmatter matching the skill schema). They function as inline reference content embedded in agent descriptions. This is valid but means they are not individually addressable or versioned as skill artifacts. Score reflects reference-document rubric, not agent rubric. Average 90 due to clean, specific, testable content.

---

### QUALITY-007 — PERSISTENT — droids use `tools: ["All tools"]` (overly broad)

All 10 droid agents declare `tools: ["All tools"]` — a broad declaration that violates the spirit of R11 (least-privilege tools). While this is not a schema error and is technically valid, it means these agents can invoke any tool including Write, Edit, and Bash on any file. The original intent (per their "Output Contract" sections) suggests some droids should be read-only. Recommend replacing with explicit tool lists matching each droid's stated behavior.

---

### QUALITY-008 — NEW — `vendors/ui-ux-pro-max-skill/CLAUDE.md` missing test command (-5)

**File:** `vendors/ui-ux-pro-max-skill/CLAUDE.md`
**Issue:** This new vendor CLAUDE.md is otherwise excellent (99 lines, has build command `python3 src/ui-ux-pro-max/scripts/search.py`, architecture section, prerequisites). It does not specify a test command. The "Git Workflow" section mentions PR creation but not unit test execution. Score: 95/100.
**Fix:** Add a test command, e.g.: `python3 src/ui-ux-pro-max/scripts/search.py "glassmorphism" --domain style` as a smoke test.

---

## Cross-Component Analysis

### Positive: BUG-002 Fix Shows Coordinated Improvement Pattern

The droids category jumped from 78→85 with the tools fix. All 10 files received consistent updates in the same commit, indicating a coordinated batch fix workflow is available and working. This same pattern should be applied to the `.github/agents/` tool name bug (BUG-001) and the 16 missing-tools personas.

### Positive: Root CLAUDE.md is Now Comprehensive Reference

The root `CLAUDE.md` (previously ~130 lines, score 70) has been expanded to 290+ lines covering: visual indicators, file creation policy, workflow quick reference, provider detection, cost awareness, Opus 4.7 effort levels, fast Opus mode, auto memory integration, and enforcement best practices. Despite the length penalty (-5), this is genuinely useful documentation. Score improved to 90.

### Positive: New vendor skill (`vendors/ui-ux-pro-max-skill/`) is high quality

The ui-ux-pro-max-skill vendor integration is well-structured: CLAUDE.md with architecture, build/run commands, prerequisites, and sync rules. At 95/100 it sets a positive precedent for vendor skill onboarding. The SKILL.md exists but was not in scope for this re-audit.

### Concern: `.github/agents/` BUG-001 completely unaddressed

The non-standard tool names (`read`, `search`, `execute`) in all 10 GitHub Actions agents are the clearest correctness bug in the repository and were not touched between audits. These agents are used in CI/CD workflows where silent failure has real consequences. Treating this as zero-priority creates technical debt that compounds as more GitHub Actions workflows are added.

### Concern: Commands `allowed-tools` gap widened in terms of impact

The commands category grew from 49 → 48 files (one removed) but gained only 3 new `allowed-tools` declarations. With 43/48 still uncovered, and some of the most complex commands (`embrace`, `factory`, `parallel`) still lacking restrictions, this is the highest-impact quality gap in the repository.

### Concern: Security findings FINDING-01 and FINDING-02 still open

Two HIGH-severity curl-pipe-sh patterns remain in the repository. FINDING-01 improved (domain corrected) but the execution risk is unchanged. FINDING-02 is completely unmodified. Neither was addressed despite being flagged as "Required Fixes (blocks contribution)" in the prior audit. These prevent the repository from receiving CONTRIBUTE status.

---

## Recommendation

**REVIEW** — Same recommendation as prior audit. The score improved from 79→82 through meaningful structural fixes (droids tools, domain correction) but the two blocking security findings remain open, the systemic BUG-001 is unaddressed, and the largest category gap (commands `allowed-tools`) saw only marginal improvement.

### Required Fixes (blocks contribution clearance)

1. **FINDING-02 (HIGH):** Replace all three curl-pipe-sh instances in `skills/skill-claw/SKILL.md` (lines 184, 185, 210) with a download-then-review pattern. This is the clearest required fix.

2. **FINDING-01 (HIGH — degraded):** The curl-pipe-sh in `agents/personas/openclaw-admin.md` line 112 now uses the correct domain. The curl-pipe-sh execution pattern itself must still be replaced with an inspect-first approach.

3. **BUG-001 (CRITICAL):** Fix tool names in all 10 `.github/agents/*.agent.md` files. Replace `read`→`Read`, `search`→`Glob` or `Grep`, `execute`→`Bash`, `edit`→`Edit`. This is a mechanical batch find-and-replace.

### Recommended Improvements (unblocks score ≥90)

4. Add `tools:` declarations to the 16 personas still missing them. Use explicit tool lists matching each persona's operational scope (e.g., `incident-responder` needs Bash, Read, Grep; `academic-writer` needs only Read and WebSearch).

5. Add `allowed-tools:` to high-traffic commands: `embrace.md`, `factory.md`, `parallel.md`, `multi.md`, `develop.md`, `discover.md`, `deliver.md`, `define.md`.

6. Add output format sections to `product-writer.md` and the command files lacking them. A minimal "## Output" section with a template prevents format drift.

7. Add `<example>` blocks to `.github/agents/*.agent.md` files. Even one example per agent removes the -15 penalty and provides behavioral grounding for CI/CD usage.

---

## Appendix: Individual File Scores

| File | Score | Delta | Key Penalties |
|------|-------|-------|---------------|
| `vendors/ui-ux-pro-max-skill/CLAUDE.md` | 95 | new | no test command (-5) |
| `CLAUDE.md` (root) | 90 | +20 | over 200 lines (-5), no test command (-5) |
| `agents/principles/write-intent.md` | 95 | new | — |
| `agents/principles/security.md` | 90 | +6 | — |
| `agents/principles/performance.md` | 90 | +8 | — |
| `agents/principles/general.md` | 88 | +6 | vague "appropriately" (-2) |
| `agents/principles/maintainability.md` | 88 | +6 | vague "appropriately" (-2) |
| `agents/personas/security-auditor.md` | 92 | 0 | — |
| `agents/personas/backend-architect.md` | 90 | 0 | examples ✓, tools ✓, no output format (-10) |
| `agents/personas/frontend-developer.md` | 90 | 0 | — |
| `agents/personas/database-architect.md` | 90 | 0 | — |
| `agents/personas/tdd-orchestrator.md` | 90 | 0 | — |
| `agents/personas/code-reviewer.md` | 90 | 0 | — |
| `agents/personas/debugger.md` | 90 | 0 | — |
| `agents/droids/octo-code-reviewer.md` | 85 | +7 | tools ✓ (fixed), no examples (-15) |
| `agents/droids/octo-backend-architect.md` | 85 | +7 | tools ✓ (fixed), no examples (-15) |
| `agents/droids/octo-security-auditor.md` | 85 | +7 | tools ✓ (fixed), no examples (-15) |
| `agents/droids/octo-tdd-orchestrator.md` | 85 | +7 | tools ✓ (fixed), no examples (-15) |
| `agents/droids/octo-frontend-developer.md` | 85 | +7 | tools ✓ (fixed), no examples (-15) |
| `.claude/agents/backend-architect.md` | 85 | +1 | no examples (-15), output format ✓ |
| `.claude/agents/security-auditor.md` | 85 | +1 | no examples (-15), output format ✓ |
| `.claude/agents/code-reviewer.md` | 85 | +1 | no examples (-15), output format ✓ |
| `config/providers/claude/CLAUDE.md` | 85 | +5 | no test command (-5), no arch overview (-5) → 90 |
| `config/providers/opencode/CLAUDE.md` | 85 | new | no test command (-5), detailed multi-backend doc |
| `config/workflows/CLAUDE.md` | 85 | 0 | no test command (-5) |
| `agents/skills/architecture.md` | 82 | +10 | short reference, no version |
| `agents/personas/ui-ux-designer.md` | 88 | 0 | vague "appropriate" (-2) |
| `agents/personas/business-analyst.md` | 80 | -5 | no tools (-5), no output format (-10), examples ✓ |
| `agents/personas/devops-troubleshooter.md` | 75 | -3 | no tools (-5), no output format (-10) |
| `agents/personas/incident-responder.md` | 75 | -3 | no tools (-5), no output format (-10) |
| `agents/personas/cloud-architect.md` | 75 | -3 | no tools (-5), no output format (-10) |
| `agents/personas/context-manager.md` | 70 | -6 | no examples (-15), no tools (-5), no output format (-10) |
| `agents/personas/product-writer.md` | 65 | -21 | no examples (-15), no output format (-10), 394 lines |
| `.claude/commands/setup.md` | 90 | +5 | allowed-tools ✓, numbered steps ✓, output format ✓ |
| `.claude/commands/costs.md` | 88 | new | allowed-tools ✓, output format ✓ |
| `.claude/commands/retro.md` | 87 | new | allowed-tools ✓, output format ✓ |
| `.claude/commands/embrace.md` | 82 | +2 | no allowed-tools (-5), has numbered steps ✓, output ✓ |
| `.claude/commands/auto.md` | 80 | +2 | no allowed-tools (-5), numbered steps ✓, output format ✓ |
| `.claude/commands/plan.md` | 75 | -3 | no allowed-tools (-5), 563 lines, vague quantifiers |
| `.claude/commands/spec.md` | 80 | new | no allowed-tools (-5), delegation command, no output format (-10), clean otherwise |
| `.claude/commands/extract.md` | 75 | new | no allowed-tools (-5), 1532 lines — longest command |
| `.github/agents/tdd-orchestrator.agent.md` | 65 | 0 | non-standard tools, no examples (-15), no model (-5), no output format (-10) |
| `.github/agents/code-reviewer.agent.md` | 65 | 0 | non-standard tools, no examples (-15), no model (-5), no output format (-10) |
| `agents/personas/openclaw-admin.md` | 72 | +17 | FINDING-01 downgraded (domain fixed), curl-pipe-sh still present; examples ✓ |
| `skills/skill-claw/SKILL.md` | 60 | 0 | FINDING-02 unresolved, curl-pipe-sh ×3 |
