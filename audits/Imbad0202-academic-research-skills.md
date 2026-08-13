# NL Audit: Imbad0202/academic-research-skills

<!-- nlpm-audit-metadata: {"repo":"Imbad0202/academic-research-skills","audited_at":"2026-05-21","auditor_version":"0.8","scope":"55 NL artifacts","security_level":"CLEAR"} -->

## NL Score Summary

| Metric | Value |
|--------|-------|
| **NL Score** | **77/100** |
| Files scored | 55 |
| Agents | 39 |
| Commands | 10 |
| Skills / Config | 6 |
| Security | CLEAR |
| Threshold | 70 (default) |
| Status | PASS |

### Score Breakdown by Suite

| Suite | Files | Avg | Key Penalties |
|-------|-------|-----|---------------|
| deep-research agents (14) | 14 | 77 | model missing (11/14), zero examples (14/14) |
| academic-paper-reviewer agents (7) | 7 | 79 | model missing (7/7), zero examples (5/7) |
| academic-pipeline agents (5) | 5 | 75 | model missing (5/5), orchestrator vague-cap −20 |
| academic-paper agents (12) | 12 | 88 | model missing (12/12), but 10/12 have 2+ examples |
| shared agents (1) | 1 | 86 | model missing |
| commands (10) | 10 | 60 | no `name:`, no `allowed-tools:`, no empty-input handling |
| SKILL.md files (4) | 4 | 88 | version mismatches (bugs) |
| config / hooks (2) | 2 | 85 | — |

### Universal Issues

1. **Missing `model:` frontmatter (36 / 39 agents, −5 each)** — Only `synthesis_agent`, `research_architect_agent`, and `report_compiler_agent` declare `model: inherit`. Every other agent omits the field, leaving model routing to caller defaults.

2. **Missing example blocks (23 / 39 agents, −15 each)** — The deep-research and academic-paper-reviewer suites have no dedicated example sections. The academic-paper suite is notably better: 10 of 12 agents include 2+ inline examples (scored at 0-penalty).

3. **Commands missing `name:` frontmatter (10 / 10, −25 each)** — All 10 commands declare only `description:` and `model:`. The `name:` field is absent from every command file.

4. **Commands missing `allowed-tools:` (10 / 10, −5 each)** — No command specifies which tools it allows.

5. **Commands missing empty-input handling (10 / 10, −10 each)** — No command addresses invocation without arguments.

---

## Security Scan

**Risk Level: CLEAR**

Pre-scan: 0 critical pattern matches, 0 high pattern matches (1 hook file, 130+ scripts, 0 MCP configs).

Manual review of executable artifacts confirms pre-scan.

### MEDIUM Findings

| # | File | Line | Issue |
|---|------|------|-------|
| M-1 | `scripts/run_codex_audit.sh` | 802 | `codex exec -m gpt-5.5` — makes external network call to OpenAI API. Expected workflow behavior for a Codex-based audit harness; input paths are validated (no traversal, no injection). |
| M-2 | `scripts/bootstrap_timeline_yaml.py` | 38 | `requests.get("https://api.crossref.org/works/{doi}")` — network call to Crossref. Gracefully degrades when `requests` is absent; no credential handling. |

### LOW Findings

| # | File | Line | Issue |
|---|------|------|-------|
| L-1 | `hooks/hooks.json` | 8 | `SessionStart` hook executes `announce-ars-loaded.sh`. Script is stdout-only and has no write side-effects, but represents a shell execution surface on every session start. |

### Patterns with No Findings

- `curl | sh` or curl-pipe-to-interpreter: **none**
- `eval` with variable input: **none**
- `os.system()`: **none**
- `subprocess(..., shell=True)`: **none** — all `subprocess.run` calls use list form
- Reverse shell patterns: **none**
- Credential exfiltration: **none**
- Path traversal: **none** — `run_codex_audit.sh` validates all path inputs via `_validate_repo_relative()` (no leading `/`, no `..`, no whitespace)

---

## Bugs (PR-worthy)

### BUG-001 · Stale agent count in `deep-research/SKILL.md`

**File**: `deep-research/SKILL.md` · **Lines**: 3 (frontmatter description), ~100 (body heading)  
**Severity**: medium · **Category**: BUG-stale-count

`deep-research/SKILL.md` declares `"13-agent pipeline"` in both the frontmatter `description:` field and the `## Agent Team (13 Agents)` body heading. The directory `deep-research/agents/` contains 14 files. `timeline_extraction_agent.md` was introduced in v3.9.4 (documented in `.claude/CLAUDE.md` changelog) but the SKILL.md count and agent table were not updated.

**Suggested fix**: Change `"13-agent"` → `"14-agent"` in frontmatter description. Add `timeline_extraction_agent` row to the Agent Team table in the body.

---

### BUG-002 · Stale version in `scripts/announce-ars-loaded.sh`

**File**: `scripts/announce-ars-loaded.sh` · **Lines**: 57, 60  
**Severity**: medium · **Category**: BUG-stale-version

The script hardcodes `"ARS v3.7.0"` in both the compact/resume banner (line 57) and the full startup banner (line 60). The current plugin version is `3.9.4.2` per `.claude-plugin/plugin.json`. Users see a misleading version string on every Claude Code session start. Four version cycles of features (v3.7.3 three-layer citation, v3.8 claim-faithfulness gate, v3.9.x phase-boundary fencing) are not reflected in the banner.

**Suggested fix**: Replace `"ARS v3.7.0"` with the current version. Consider reading version dynamically from `plugin.json` via `jq -r .version .claude-plugin/plugin.json` to prevent future drift.

---

### BUG-003 · Stale version in `academic-pipeline/SKILL.md` title

**File**: `academic-pipeline/SKILL.md` · **Line**: 19  
**Severity**: low · **Category**: BUG-stale-version

The SKILL.md body title reads `# Academic Pipeline v3.8.2` but the frontmatter `metadata.version` field is `"3.9.4.2"` and `.claude-plugin/plugin.json` confirms 3.9.4.2. The title was not updated when the version was incremented.

**Suggested fix**: Update line 19: `# Academic Pipeline v3.8.2` → `# Academic Pipeline v3.9.4.2`.

---

### BUG-004 · Missing `model:` on 36 agents

**Affected files**: All agents except `synthesis_agent.md`, `research_architect_agent.md`, `report_compiler_agent.md`  
**Line**: 1–4 (frontmatter block)  
**Severity**: low · **Category**: BUG-missing-frontmatter

36 of 39 agent files omit the `model:` frontmatter field. The Claude Code Agent SDK uses this field for model-tier routing. Without it, model selection falls back to the caller's default, which may produce inconsistent behavior when agents are invoked across different orchestration contexts. The three agents with `model: inherit` correctly signal that they should inherit the caller's model.

Affected suites: all 14 deep-research agents minus the 2 with `model: inherit` (11 agents), all 7 academic-paper-reviewer agents, all 5 academic-pipeline agents, all 12 academic-paper agents, `compliance_agent`.

**Suggested fix**: Add `model: sonnet` to agents performing research/drafting tasks; `model: opus` for high-stakes review and orchestration agents (`pipeline_orchestrator_agent`, `peer_reviewer_agent`, `devils_advocate_agent`, `integrity_verification_agent`).

---

## Security Fixes

No security fixes required. All findings are MEDIUM or LOW and represent expected behavior for an academic research automation pipeline (external API calls to Crossref and OpenAI Codex are legitimate workflow dependencies, not vulnerabilities).

---

## Quality Issues

### Q-001 · 23 agents with zero example blocks (−15 each)

All 14 deep-research agents, 5 of 7 academic-paper-reviewer agents, and `argument_builder_agent` contain no dedicated example blocks. These agents document their output formats thoroughly but show no concrete input/output pairs, making it difficult for integrators to verify correct invocation.

**Agents with zero examples** (illustrative, not exhaustive): `research_question_agent.md`, `bibliography_agent.md`, `source_verification_agent.md`, `meta_analysis_agent.md`, `risk_of_bias_agent.md`, `devils_advocate_agent.md`, `monitoring_agent.md`, `editor_in_chief_agent.md`, `ethics_review_agent.md`, `timeline_extraction_agent.md`, `socratic_mentor_agent.md` (deep-research), `domain_reviewer_agent.md`, `eic_agent.md`, `editorial_synthesizer_agent.md`, `methodology_reviewer_agent.md`, `perspective_reviewer_agent.md`, `pipeline_orchestrator_agent.md`, `integrity_verification_agent.md`, `collaboration_depth_agent.md`, `argument_builder_agent.md`.

**Suggested fix**: Add a `## Examples` section with one realistic input/output pair to each agent. Even a minimal example (e.g., one `Source Verification Report` excerpt) raises the score from 76 to 86.

---

### Q-002 · Grammar issues in 3 agent descriptions

| File | Issue |
|------|-------|
| `academic-paper-reviewer/agents/field_analyst_agent.md` | Description reads `"papers field"` and `"teams identities"` — missing possessive apostrophes |
| `academic-paper-reviewer/agents/devils_advocate_reviewer_agent.md` | Description reads `"devils advocate"` — missing apostrophe |
| `academic-paper/agents/argument_builder_agent.md` | Description reads `"papers core argument"` — missing apostrophe |

---

### Q-003 · All 10 commands missing `name:` frontmatter (−25 each)

`ars-full.md`, `ars-plan.md`, `ars-revision.md`, `ars-revision-coach.md`, `ars-abstract.md`, `ars-lit-review.md`, `ars-format-convert.md`, `ars-citation-check.md`, `ars-disclosure.md`, `ars-outline.md` all omit the `name:` field. Commands have `description:` and `model:` but no `name:`.

**Suggested fix**: Add `name: ars-full` (etc.) to each command's frontmatter, matching the filename without extension.

---

### Q-004 · All 10 commands missing `allowed-tools:` and empty-input handling (−15 combined)

These are minimal dispatch commands; the absence of `allowed-tools:` means callers cannot know which tool permissions are needed. Empty-input handling is absent: if a user invokes `/ars-full` with no text, nothing guides the agent to prompt for the paper topic.

**Suggested fix**: Add `allowed-tools: []` (these commands dispatch to skill prompts and need no direct tool access themselves) and append a one-line fallback: "If no paper topic or context is provided, ask the user what they want to research or write."

---

### Q-005 · `pipeline_orchestrator_agent.md` vague-quantifier cap (−20)

`academic-pipeline/agents/pipeline_orchestrator_agent.md` (800+ lines) contains ≥10 vague quantifiers including "appropriate mode", "relevant agents", "sufficient context", "reasonable approach", "suitable method" throughout the Adaptive Checkpoint System and routing logic sections. This hits the −20 vague-cap.

**Suggested fix**: Replace each vague term with a specific observable criterion. E.g., "appropriate mode" → "the mode matching the user's stage_hint field per MODE_REGISTRY.md"; "sufficient context" → "at least one of: RQ Brief, Annotated Bibliography, or existing draft section provided".

---

## Cross-Component

### CC-001 · `deep-research/SKILL.md` agent count out of sync with `deep-research/agents/`

SKILL.md declares 13 agents; directory contains 14. `timeline_extraction_agent` added in v3.9.4 is missing from the Agent Team table. — See BUG-001.

### CC-002 · `announce-ars-loaded.sh` version out of sync with `plugin.json`

Hook broadcasts "ARS v3.7.0" at session start; plugin declares 3.9.4.2. Users and external tools (e.g., auditors inspecting the session banner) see stale version. — See BUG-002.

### CC-003 · `academic-pipeline/SKILL.md` title version out of sync with frontmatter and `plugin.json`

SKILL.md title "v3.8.2" conflicts with both `metadata.version: "3.9.4.2"` in frontmatter and the plugin.json version. — See BUG-003.

---

## Recommendation

**CONTRIBUTE** — 3 clean mechanical bugs with narrow diffs; systemic quality issues are well-understood and non-blocking.

The ARS plugin demonstrates strong engineering depth: 38 agents with detailed output formats, multi-phase pipeline enforcement (v3.9.2), three-layer citation provenance (v3.7.3), claim-faithfulness audit gate (v3.8), and cross-index triangulation (v3.9.0). The academic-paper suite scores 88/100 on average because 10 of 12 agents include 2+ concrete examples.

The score drag comes primarily from the deep-research and academic-paper-reviewer suites (average ~78) where example blocks are uniformly absent, and from 10 minimal command files that all score 60 due to missing `name:`, `allowed-tools:`, and empty-input handling.

**Suggested first PRs (priority order)**:
1. **BUG-001**: Fix agent count + add `timeline_extraction_agent` row to `deep-research/SKILL.md` Agent Team table
2. **BUG-002**: Update version string in `announce-ars-loaded.sh` from v3.7.0 → 3.9.4.2
3. **BUG-003**: Update title line in `academic-pipeline/SKILL.md` from v3.8.2 → v3.9.4.2
4. **Q-003**: Add `name:` frontmatter to all 10 command files (mechanical, 10-line diff)
