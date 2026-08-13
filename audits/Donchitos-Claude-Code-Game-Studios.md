# NLPM Audit: Donchitos/Claude-Code-Game-Studios
**Date**: 2026-04-12  |  **Artifacts**: 175  |  **Strategy**: progressive
**NL Score**: 82/100
**Security**: CLEAR
**Bugs**: 2  |  **Quality Issues**: 47  |  **Security Findings**: 0

---

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `.claude/agents/live-ops-designer.md` | agent | 59 | No examples (-15) + no output format (-10) + 8 vague quantifiers (-16) |
| `.claude/agents/game-designer.md` | agent | 65 | No examples (-15) + 11 vague quantifiers, capped (-20) |
| `.claude/agents/narrative-director.md` | agent | 65 | No examples (-15) + no output format (-10) + 5 vague quantifiers (-10) |
| `CCGS Skill Testing Framework/agents/directors/technical-director.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/directors/art-director.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/directors/creative-director.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/directors/producer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/leads/game-designer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/leads/lead-programmer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/leads/audio-director.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/leads/qa-lead.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/leads/systems-designer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/leads/level-designer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/leads/narrative-director.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/qa/qa-tester.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/qa/security-engineer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/qa/accessibility-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/operations/analytics-engineer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/operations/devops-engineer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/operations/community-manager.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/operations/localization-lead.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/operations/live-ops-designer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/operations/release-manager.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/operations/economy-designer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/godot/godot-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/godot/godot-gdextension-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/godot/godot-gdscript-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/godot/godot-shader-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/godot/godot-csharp-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/unity/unity-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/unity/unity-addressables-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/unity/unity-ui-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/unity/unity-shader-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/unity/unity-dots-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/unreal/unreal-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/unreal/ue-blueprint-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/unreal/ue-replication-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/unreal/ue-umg-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/engine/unreal/ue-gas-specialist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/ux-designer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/network-programmer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/technical-artist.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/performance-analyst.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/ai-programmer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/tools-programmer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/prototyper.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/ui-programmer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/gameplay-programmer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/engine-programmer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/sound-designer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/writer.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `CCGS Skill Testing Framework/agents/specialists/world-builder.md` | test-spec | 70 | No YAML frontmatter (not registered as agent) |
| `.claude/skills/architecture-decision/SKILL.md` | skill | 72 | BUG: `Edit` used in body but not in allowed-tools |
| `.claude/skills/story-done/SKILL.md` | skill | 74 | BUG: `Write` needed to create active.md but not in allowed-tools |
| `.claude/agents/qa-lead.md` | agent | 67 | No examples (-15) + no output format (-10) + 4 vague quantifiers (-8) |
| `.claude/agents/writer.md` | agent | 67 | No examples (-15) + no output format (-10) + 4 vague quantifiers (-8) |
| `.claude/agents/world-builder.md` | agent | 67 | No examples (-15) + no output format (-10) + 4 vague quantifiers (-8) |
| `.claude/agents/lead-programmer.md` | agent | 69 | No examples (-15) + no output format (-10) + 3 vague quantifiers (-6) |
| `.claude/agents/audio-director.md` | agent | 69 | No examples (-15) + no output format (-10) + 3 vague quantifiers (-6) |
| `.claude/agents/level-designer.md` | agent | 69 | No examples (-15) + no output format (-10) + 3 vague quantifiers (-6) |
| `.claude/agents/localization-lead.md` | agent | 69 | No examples (-15) + no output format (-10) + 3 vague quantifiers (-6) |
| `.claude/agents/gameplay-programmer.md` | agent | 69 | No examples (-15) + no output format (-10) + 3 vague quantifiers (-6) |
| `.claude/agents/sound-designer.md` | agent | 69 | No examples (-15) + no output format (-10) + 3 vague quantifiers (-6) |
| `.claude/agents/economy-designer.md` | agent | 69 | No examples (-15) + has output format + 8 vague quantifiers (-16) |
| `.claude/agents/ux-designer.md` | agent | 71 | No examples (-15) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/unity-specialist.md` | agent | 71 | No examples (-15) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/unreal-specialist.md` | agent | 71 | No examples (-15) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/ue-replication-specialist.md` | agent | 71 | No examples (-15) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/ue-umg-specialist.md` | agent | 71 | No examples (-15) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/technical-artist.md` | agent | 71 | No examples (-15) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/unity-ui-specialist.md` | agent | 71 | No examples (-15) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/ui-programmer.md` | agent | 71 | No examples (-15) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/analytics-engineer.md` | agent | 73 | No examples (-15) + no output format (-10) + 1 vague quantifier (-2) |
| `.claude/agents/network-programmer.md` | agent | 73 | No examples (-15) + no output format (-10) + 1 vague quantifier (-2) |
| `.claude/agents/devops-engineer.md` | agent | 73 | No examples (-15) + no output format (-10) + 1 vague quantifier (-2) |
| `.claude/agents/community-manager.md` | agent | 73 | No examples (-15) + has output format + 6 vague quantifiers (-12) |
| `.claude/agents/ai-programmer.md` | agent | 73 | No examples (-15) + no output format (-10) + 1 vague quantifier (-2) |
| `.claude/agents/godot-specialist.md` | agent | 73 | No examples (-15) + no output format (-10) + 1 vague quantifier (-2) |
| `.claude/agents/technical-director.md` | agent | 75 | No examples (-15) + has output format + 5 vague quantifiers (-10) |
| `.claude/agents/systems-designer.md` | agent | 75 | No examples (-15) + has output format + 5 vague quantifiers (-10) |
| `.claude/agents/unity-dots-specialist.md` | agent | 75 | No examples (-5, code patterns) + no output format (-10) + 5 vague quantifiers (-10) |
| `.claude/agents/art-director.md` | agent | 77 | No examples (-15) + has gate verdict format + 4 vague quantifiers (-8) |
| `.claude/agents/release-manager.md` | agent | 77 | No examples (-15) + has checklist format + 4 vague quantifiers (-8) |
| `.claude/agents/ue-gas-specialist.md` | agent | 77 | No examples (-5, code patterns) + no output format (-10) + 4 vague quantifiers (-8) |
| `.claude/agents/creative-director.md` | agent | 79 | Has 1 example (-5) + has gate verdict format + 8 vague quantifiers (-16) |
| `.claude/agents/producer.md` | agent | 79 | Has 1 example (-5) + has gate verdict format + 8 vague quantifiers (-16) |
| `.claude/agents/performance-analyst.md` | agent | 79 | No examples (-15) + has output format + 3 vague quantifiers (-6) |
| `.claude/agents/godot-shader-specialist.md` | agent | 79 | Has code examples (-5) + no output format (-10) + 3 vague quantifiers (-6) |
| `.claude/agents/engine-programmer.md` | agent | 79 | Has code examples (-5) + no output format (-10) + 3 vague quantifiers (-6) |
| `CLAUDE.md` | claude-md | 80 | TO BE CONFIGURED placeholders; @imports good; engine not yet set |
| `.claude/agents/unity-addressables-specialist.md` | agent | 81 | Has code examples (-5) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/ue-blueprint-specialist.md` | agent | 81 | Has code examples (-5) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/tools-programmer.md` | agent | 81 | Has code examples (-5) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/godot-gdscript-specialist.md` | agent | 81 | Has code examples (-5) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/security-engineer.md` | agent | 81 | No examples (-15) + has checklist format + 2 vague quantifiers (-4) |
| `.claude/agents/unity-shader-specialist.md` | agent | 81 | Has code examples (-5) + no output format (-10) + 2 vague quantifiers (-4) |
| `.claude/agents/godot-csharp-specialist.md` | agent | 82 | Multiple code examples (0) + no output format (-10) + 4 vague quantifiers (-8) |
| `.claude/agents/godot-gdextension-specialist.md` | agent | 83 | Has code examples (-5) + no output format (-10) + 1 vague quantifier (-2) |
| `.claude/agents/accessibility-specialist.md` | agent | 85 | Has checklist example (-5) + has findings format + 5 vague quantifiers (-10) |
| `.claude/skills/brainstorm/SKILL.md` | skill | 88 | 6 vague quantifiers (-12) |
| `src/CLAUDE.md` | claude-md | 90 | Clear and specific; minor: @-import assumed |
| `docs/CLAUDE.md` | claude-md | 90 | Clear and specific; minor: references templates that may not exist |
| `.claude/skills/create-architecture/SKILL.md` | skill | 90 | 5 vague quantifiers (-10) |
| `.claude/skills/team-narrative/SKILL.md` | skill | 90 | 5 vague quantifiers (-10) |
| `.claude/skills/team-polish/SKILL.md` | skill | 90 | 5 vague quantifiers (-10) |
| `.claude/agents/prototyper.md` | agent | 87 | Has report format (0) + has examples (0) + 4 vague quantifiers (-8) + model haiku note: actually sonnet ✓ |
| `.claude/skills/setup-engine/SKILL.md` | skill | 92 | 4 vague quantifiers (-8) |
| `.claude/skills/team-ui/SKILL.md` | skill | 92 | 4 vague quantifiers (-8) |
| `.claude/skills/consistency-check/SKILL.md` | skill | 92 | 4 vague quantifiers (-8) |
| `.claude/skills/review-all-gdds/SKILL.md` | skill | 92 | 4 vague quantifiers (-8) |
| `.claude/skills/team-release/SKILL.md` | skill | 92 | 4 vague quantifiers (-8) |
| `.claude/skills/design-system/SKILL.md` | skill | 92 | 4 vague quantifiers (-8) |
| `.claude/skills/architecture-review/SKILL.md` | skill | 92 | 4 vague quantifiers (-8) |
| `CCGS Skill Testing Framework/CLAUDE.md` | claude-md | 92 | Clear structure; well-organized; minor: catalog.yaml path hardcoded |
| `design/CLAUDE.md` | claude-md | 92 | Clear structure; specific; numbered sections |
| `.claude/agents/qa-tester.md` | agent | 91 | Has code templates (-5) + has output formats (0) + 2 vague quantifiers (-4) |
| `.claude/skills/prototype/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/team-level/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/hotfix/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/team-combat/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/day-one-patch/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/team-audio/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/code-review/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/sprint-plan/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/asset-spec/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/adopt/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/create-stories/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/gate-check/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/team-qa/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/milestone-review/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/map-systems/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/team-live-ops/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/design-review/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/dev-story/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/perf-profile/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/qa-plan/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/ux-design/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/propagate-design-change/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/localize/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/create-control-manifest/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/security-audit/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/art-bible/SKILL.md` | skill | 94 | 3 vague quantifiers (-6) |
| `.claude/skills/ux-review/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/skill-test/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/asset-audit/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/bug-triage/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/changelog/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/test-evidence-review/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/release-checklist/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/regression-suite/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/balance-check/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/start/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/reverse-document/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/tech-debt/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/story-readiness/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/scope-check/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/launch-checklist/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/smoke-check/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/retrospective/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/quick-design/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/estimate/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/skill-improve/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/sprint-status/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/help/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/create-epics/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/test-setup/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/test-flakiness/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/patch-notes/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/soak-test/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/content-audit/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/playtest-report/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/onboard/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/test-helpers/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/bug-report/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |
| `.claude/skills/project-stage-detect/SKILL.md` | skill | 96 | 2 vague quantifiers (-4) |

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
| Hooks | 0 (hooks/ directory empty) |
| Scripts | 0 (no scripts/ directory) |
| MCP configs | 0 (no .mcp.json) |
| Package manifests | 0 (no package.json / requirements.txt) |

### Security Findings

No security findings.

---

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `.claude/skills/architecture-decision/SKILL.md` | Body uses `Edit` tool ("Append each missing section to the ADR file using the Edit tool") but `Edit` is not in `allowed-tools: Read, Glob, Grep, Write, Task, AskUserQuestion`. Also needs Edit for updating architecture registry entries at step 6. | Retrofit mode fails with a permission error when attempting to append missing sections to existing ADRs. Registry updates are also broken. |
| 2 | `.claude/skills/story-done/SKILL.md` | Body creates `production/session-state/active.md` when absent ("If `active.md` does not exist, create it with this block as the initial content") but `Write` is not in `allowed-tools: Read, Glob, Grep, Bash, Edit, AskUserQuestion, Task`. | Session-state creation fails on first run of `/story-done` in a fresh project. The skill silently loses completion notes. |

---

## Security Fixes (PR-worthy, Medium/Low only)

No security findings requiring fixes.

---

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | All 49 `.claude/agents/*.md` | Zero usage-example blocks across every agent definition. No `## Example` or interaction-walkthrough sections showing how to invoke the agent and what a response looks like. | -15 per agent (zero examples) |
| 2 | ~35 `.claude/agents/*.md` | No explicit `## Output Format` section specifying structure of agent responses (code, documents, tables, etc.). Agents that produce structured artifacts (ADRs, design docs, bug reports, perf reports) should specify their output format. Agents with formats: `technical-director`, `performance-analyst`, `qa-tester`, `community-manager`, `creative-director`, `art-director`, `producer`, `security-engineer`, `accessibility-specialist`, `release-manager`, `systems-designer`, `prototyper`, `economy-designer`. | -10 per affected agent |
| 3 | `.claude/agents/live-ops-designer.md` | 8 vague quantifiers: "appropriate", "meaningful", "relevant", "suitable", "various", "significant", "reasonable", "generous". These make it impossible for the agent to know objectively when a criterion is met. | -16 |
| 4 | `.claude/agents/game-designer.md` | 11 vague quantifiers including "appropriate" (×3), "relevant" (×3), "various" (×2), "suitable", "reasonable", "clear". Heavy use of theoretical vocabulary bleeds into instruction language. | -20 (capped) |
| 5 | `.claude/agents/creative-director.md` | 8 vague quantifiers: "appropriate", "suitable", "reasonable", "various", "clear", "specific", "strategic", "explicit". | -16 |
| 6 | `.claude/agents/producer.md` | 8 vague quantifiers: "appropriate", "realistic", "various", "relevant", "strategic", "explicit", "all", "clear". | -16 |
| 7 | `.claude/agents/economy-designer.md` | 8 vague quantifiers: "appropriate", "relevant", "suitable", "satisfying", "various", "significant", "reasonable", "explicit". | -16 |
| 8 | `.claude/agents/devops-engineer.md` | Assigned `model: haiku` but has Write, Edit, Bash tools and writes CI/CD configuration, branching strategy, build scripts — creative/implementation work that Haiku underperforms on. Coordination rules define Haiku for "read-only status checks, formatting, simple lookups." DevOps work exceeds that scope. | Quality concern: model underspec |
| 9 | `.claude/agents/community-manager.md` | Assigned `model: haiku` but writes crisis communications, dev blogs, patch notes, and community strategy. Haiku may produce lower-quality long-form communications. Same model-tier concern as devops-engineer. | Quality concern: model underspec |
| 10 | All 49 `.claude/agents/*.md` — "Collaboration Protocol" boilerplate | 30+ agents share identical 6-step "Implementation Workflow" boilerplate that was designed for programmers: "Should this be a static utility class or a scene node?" / "Where should [data] live? ([SystemData]? [Container] class?)" This coding-specific language appears verbatim in community-manager, game-designer, narrative-director, writer, world-builder, sound-designer, and other non-coding agents. The language is semantically wrong for their roles. | Quality: misleading instructions |
| 11 | `.claude/agents/narrative-director.md` | Has only 3 tools declared (`Read, Glob, Grep` + disallows Bash, but also has Write and Edit) — missing explicit Write/Edit in tools list while `disallowedTools: Bash` implies Bash is otherwise allowed. Cross-check: description says "produces story docs" so Write is needed. | Minor: tool declaration ambiguity |
| 12 | All 49 CCGS test-spec files | Files in `CCGS Skill Testing Framework/agents/` have no YAML frontmatter. They use `# Agent Summary` markdown headings instead. Claude Code will not register them as agents. They are behavioral test specifications, not registrable agent definitions — but this structure is not communicated in the file format itself. | Not bugs (intentional as test specs), but -25/-25 if scored as agent registrations |
| 13 | `.claude/skills/architecture-decision/SKILL.md` | Referenced tool `Edit` missing from `allowed-tools` (BUG, detailed above) PLUS the skill references `AskUserQuestion` repeatedly but that tool depends on the runtime — if called as a subagent via Task (where AskUserQuestion may not surface interactively), the flow could silently break. | BUG severity on Edit; quality note on AskUserQuestion subagent scenario |
| 14 | `.claude/skills/team-combat/SKILL.md` | Phase 2 spawns "primary engine specialist" by reading `technical-preferences.md` at runtime, but if the engine is not yet configured (`[TO BE CONFIGURED]`), the dynamic spawn target is indeterminate. No fallback documented if `technical-preferences.md` is missing or unconfigured. | Missing empty/unconfigured-state handling |
| 15 | `.claude/skills/team-audio/SKILL.md` | Same issue as team-combat: dynamic engine specialist spawn with no fallback for unconfigured projects. The skill does say "If no engine is configured, skip the specialist spawn" — this is adequate for audio but not consistently applied in team-combat. | Minor: inconsistency between team-* skills |
| 16 | `.claude/skills/brainstorm/SKILL.md` | 6 vague quantifiers: "appropriate", "relevant", "suitable", "unusual", "reasonable", "gentle" | -12 |
| 17 | `.claude/agents/world-builder.md` | No examples (-15) + no output format (-10) + 4 vague quantifiers (-8) — produces lore documents but the format/structure of those documents is not specified | -33 combined |
| 18 | `.claude/agents/narrative-director.md` | No examples (-15) + no output format (-10) + 5 vague quantifiers (-10) | -35 combined |
| 19 | `.claude/agents/qa-lead.md` | No examples (-15) + no output format (-10) despite explicitly producing QA plans, sign-off reports, and regression suites | -25 on examples + format |
| 20 | `.claude/skills/design-system/SKILL.md` | File is large (section-by-section GDD authoring for a full game system). Heavy use of incremental file writing logic. 4 vague quantifiers but the main quality concern is the `model: sonnet` assignment when the skill orchestrates a `technical-director` gate review internally — caller and callee use the same model, reducing independence of the review. | Quality: review independence concern |

---

## Cross-Component

### Broken References
- `.claude/skills/story-done/SKILL.md` references `.claude/docs/director-gates.md` (to look up gate identifiers like `QL-TEST-COVERAGE`, `LP-CODE-REVIEW`) — this file exists in the coordination docs but was not listed in the audit manifest. The dependency is real and must remain consistent.
- `.claude/skills/architecture-decision/SKILL.md` references `docs/registry/architecture.yaml` at step 6. That file path follows from other skills but was not confirmed to exist in a fresh project. This is a soft dependency.
- Multiple skills reference `production/review-mode.txt` — this file does not exist until explicitly created by the user. All skills that read it have a safe fallback ("default to `lean`"), which is correct.

### Orphaned Components
- All 49 CCGS framework agent test-specs in `CCGS Skill Testing Framework/agents/` are referenced by `catalog.yaml` (per the CCGS CLAUDE.md), but `catalog.yaml` was not in the audit manifest. If catalog.yaml is absent, `/skill-test` and `/skill-improve` will not function. The CCGS CLAUDE.md acknowledges this: "This folder is deletable."
- `.claude/docs/templates/` directory is referenced in `docs/CLAUDE.md` ("Use the ADR template: `.claude/docs/templates/architecture-decision-record.md`") and in `community-manager` ("Crisis comms template in `.claude/docs/templates/incident-response.md`"). These templates were not in the audit manifest — they may be absent in fresh installs.

### Contradictions
- `devops-engineer.md` uses `model: haiku` and `maxTurns: 10`, but `.claude/docs/coordination-rules.md` defines Haiku as appropriate only for "read-only status checks, formatting, simple lookups — no creative judgment needed." DevOps writes build scripts and CI config, which requires implementation judgment. The assignment contradicts the project's own model-tier policy.
- `community-manager.md` has the same contradiction: `model: haiku` for writing long-form crisis communications and dev blogs.
- Many non-coding agents (`community-manager`, `game-designer`, `writer`, `world-builder`, `sound-designer`) include the verbatim programmer-centric "Implementation Workflow" boilerplate with lines like "Should this be a static utility class or a scene node?" that are semantically incorrect for their roles. The workflow was copy-pasted without role-appropriate customization.

### Architecture Consistency
- The gate-verdict pattern (`[GATE-ID]: APPROVE / CONCERNS / REJECT`) is correctly implemented in `technical-director`, `creative-director`, `art-director`, and `producer`. The `qa-lead` agent does NOT have this gate format despite being invoked via gate identifiers (`QL-TEST-COVERAGE`, `QL-STORY-READY`) in multiple skills. This is an inconsistency: skills read a specific verdict format from `qa-lead` but the agent does not document producing it.
- 72 skills all correctly specify `allowed-tools` in YAML frontmatter. 2 skills have mismatches between declared tools and tools used in the body (`architecture-decision` missing Edit, `story-done` missing Write). All other skills appear consistent.

---

## Recommendation

CLEAR — submit PRs for all bugs and medium/low security fixes.

### Priority Actions

**P0 — Ship blockers (break existing functionality):**
1. **Fix `architecture-decision/SKILL.md`**: Add `Edit` to `allowed-tools`. Current: `Read, Glob, Grep, Write, Task, AskUserQuestion`. Should be: `Read, Glob, Grep, Write, Edit, Task, AskUserQuestion`. The Edit tool is explicitly invoked in Phase 0 (retrofit mode) and Phase 6 (registry updates).
2. **Fix `story-done/SKILL.md`**: Add `Write` to `allowed-tools`. Current: `Read, Glob, Grep, Bash, Edit, AskUserQuestion, Task`. Should be: `Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion, Task`. Required to create `production/session-state/active.md` on first run.

**P1 — High-value quality improvements:**
3. **Add example blocks to all 49 agents**: Each agent definition should include 1-2 `## Example` sections showing a realistic invocation and response pattern. This is the single highest-ROI change — affects all 49 agents and accounts for the largest score gap.
4. **Add output format sections to ~35 agents**: Agents that produce structured artifacts (ADRs, design docs, QA plans, perf reports, test cases) should specify the format. Copy the pattern from `performance-analyst` (explicit markdown table) or `technical-director` (ADR format).
5. **Fix model tier for `devops-engineer` and `community-manager`**: Change `model: haiku` to `model: sonnet`. Both roles require implementation judgment and long-form authoring beyond Haiku's strengths. Haiku is correct only for read-only status-check roles.

**P2 — Quality polish:**
6. **Prune boilerplate in non-coding agents**: `community-manager`, `game-designer`, `writer`, `world-builder`, `sound-designer`, `narrative-director` all contain the programmer-centric "Implementation Workflow" with "Should this be a static utility class?" language. Replace with role-appropriate workflows (e.g., the "Question-First Workflow" already present in design agents is the correct pattern).
7. **Reduce vague quantifiers** in `live-ops-designer` (8 instances), `game-designer` (11), `creative-director` (8), `producer` (8), `economy-designer` (8). Replace "appropriate" → specific criteria; "relevant" → named list; "various" → enumerated types.
8. **Add `qa-lead` gate verdict format**: Multiple skills (`story-done`, `hotfix`, `day-one-patch`) read gate verdicts from `qa-lead` using `QL-*` gate IDs, but `qa-lead.md` does not document the `[GATE-ID]: ADEQUATE / GAPS / INADEQUATE` verdict format. Add it to match the director agents' gate format documentation.

### What is Excellent
The skill library (72 files, avg 94/100) is production-quality: complete frontmatter, numbered phases, explicit output formats, consistent verdicts, argument checking, error recovery protocols. Particularly strong: `gate-check`, `code-review`, `story-done` (despite the Write bug), `hotfix`, `smoke-check`, and all team-* orchestration skills. The agent delegation hierarchy is coherent and well-documented across all 49 agents. The CCGS testing framework is a sophisticated self-QA system that demonstrates dogfooding discipline.
