# Audit: data-goblin/power-bi-agentic-development

| | |
|---|---|
| **Repo** | data-goblin/power-bi-agentic-development |
| **Audit date** | 2026-06-20 |
| **Audited by** | nlpm auditor v0.8.23 |
| **NL score** | 95/100 |
| **Security** | CLEAR |
| **Artifacts scanned** | 54 |
| **Findings** | 2 bugs · 0 security · 12 quality |

---

## NL Score Summary

**Overall: 95/100** (5,136 points across 54 artifacts)

| Type | Count | Avg | Min | Max |
|------|-------|-----|-----|-----|
| agents | 8 | 97 | 90 | 100 |
| commands | 3 | 65 | 55 | 81 |
| skills | 30 | 96 | 90 | 97 |
| hooks | 3 | 100 | 100 | 100 |
| plugin manifests | 10 | 100 | 100 | 100 |

### Per-file scores

| File | Type | Score | Notes |
|------|------|-------|-------|
| plugins/fabric-cli/commands/migrating-fabric-trial-capacities.md | command | 55 | −25 missing `name`, −5 missing `model`, −5 no `allowed-tools`, −10 no empty-input handling |
| plugins/fabric-cli/commands/audit-context.md | command | 60 | −25 missing `name`, −5 no `allowed-tools`, −10 no empty-input handling |
| plugins/tabular-editor/commands/suggest-rule.md | command | 81 | −5 no `allowed-tools`, −10 no empty-input handling, −4 vague quantifiers |
| plugins/pbi-desktop/agents/query-listener.agent.md | agent | 90 | −10 no output format section |
| plugins/fabric-admin/skills/audit-tenant-settings/SKILL.md | skill | 90 | −4 vague quantifiers ("appropriate", "sufficient") |
| plugins/pbi-desktop/skills/connect-pbid/SKILL.md | skill | 93 | −7 vague quantifiers |
| plugins/tabular-editor/skills/bpa-rules/SKILL.md | skill | 94 | −6 vague quantifiers ("appropriate" ×2, "various") |
| plugins/fabric-cli/skills/fabric-cli/SKILL.md | skill | 94 | −6 vague quantifiers |
| plugins/reports/agents/r-reviewer.agent.md | agent | 95 | −5 only 1 example (≥2 required) |
| plugins/reports/agents/svg-reviewer.agent.md | agent | 95 | −5 only 1 example (≥2 required) |
| plugins/reports/agents/python-reviewer.agent.md | agent | 95 | −5 only 1 example (≥2 required) |
| plugins/tabular-editor/skills/c-sharp-scripting/SKILL.md | skill | 95 | minor vague |
| plugins/semantic-models/skills/refresh-semantic-model/SKILL.md | skill | 95 | minor vague |
| plugins/semantic-models/skills/standardize-naming-conventions/SKILL.md | skill | 95 | — |
| plugins/semantic-models/skills/dax/SKILL.md | skill | 95 | — |
| plugins/paginated-reports/skills/paginated-report/SKILL.md | skill | 95 | — |
| plugins/custom-visuals/skills/python-visuals/SKILL.md | skill | 95 | — |
| plugins/custom-visuals/skills/svg-visuals/SKILL.md | skill | 95 | — |
| plugins/custom-visuals/skills/r-visuals/SKILL.md | skill | 95 | — |
| plugins/pbip/skills/pbir-format/SKILL.md | skill | 95 | — |
| plugins/tabular-editor/skills/te-cli/SKILL.md | skill | 96 | — |
| plugins/semantic-models/skills/power-query/SKILL.md | skill | 96 | — |
| plugins/semantic-models/skills/semantic-model/SKILL.md | skill | 96 | — |
| plugins/semantic-models/skills/lineage-analysis/SKILL.md | skill | 96 | — |
| plugins/etl/skills/executing-spark/SKILL.md | skill | 96 | — |
| plugins/etl/skills/using-duckdb/SKILL.md | skill | 96 | — |
| plugins/custom-visuals/skills/deneb-visuals/SKILL.md | skill | 96 | — |
| plugins/custom-visuals/skills/powerbi-custom-visuals/SKILL.md | skill | 96 | — |
| plugins/pbip/skills/tmdl/SKILL.md | skill | 96 | — |
| plugins/reports/skills/review-report/SKILL.md | skill | 96 | −2 vague ("comprehensive", "loosely") |
| plugins/tabular-editor/skills/te2-cli/SKILL.md | skill | 97 | — |
| plugins/tabular-editor/skills/te-docs/SKILL.md | skill | 97 | — |
| plugins/pbip/skills/pbip/SKILL.md | skill | 97 | — |
| plugins/reports/skills/create-pbi-report/SKILL.md | skill | 97 | — |
| plugins/reports/skills/modifying-theme-json/SKILL.md | skill | 97 | — |
| plugins/reports/skills/pbi-report-design/SKILL.md | skill | 97 | −2 "loosely 12-15 max" |
| plugins/reports/skills/pbir-cli/SKILL.md | skill | 97 | — |
| plugins/tabular-editor/agents/bpa-expression-helper.agent.md | agent | 100 | — |
| plugins/semantic-models/agents/semantic-model-auditor.agent.md | agent | 100 | — |
| plugins/pbip/agents/pbip-validator.agent.md | agent | 100 | — |
| plugins/reports/agents/deneb-reviewer.agent.md | agent | 100 | — |
| plugins/paginated-reports/hooks/hooks.json | hook | 100 | — |
| plugins/pbi-desktop/hooks/hooks.json | hook | 100 | — |
| plugins/pbip/hooks/hooks.json | hook | 100 | — |
| plugins/tabular-editor/.claude-plugin/plugin.json | plugin | 100 | — |
| plugins/semantic-models/.claude-plugin/plugin.json | plugin | 100 | — |
| plugins/etl/.claude-plugin/plugin.json | plugin | 100 | — |
| plugins/fabric-admin/.claude-plugin/plugin.json | plugin | 100 | — |
| plugins/paginated-reports/.claude-plugin/plugin.json | plugin | 100 | — |
| plugins/fabric-cli/.claude-plugin/plugin.json | plugin | 100 | — |
| plugins/custom-visuals/.claude-plugin/plugin.json | plugin | 100 | — |
| plugins/pbi-desktop/.claude-plugin/plugin.json | plugin | 100 | — |
| plugins/pbip/.claude-plugin/plugin.json | plugin | 100 | — |
| plugins/reports/.claude-plugin/plugin.json | plugin | 100 | — |

---

## Security Scan

**Result: CLEAR**

| Surface | Files | Critical | High | Medium | Low |
|---------|-------|----------|------|--------|-----|
| hooks | 3 | 0 | 0 | 0 | 0 |
| scripts | 55 | 0 | 0 | 0 | 0 |
| MCP configs | 2 | 0 | 0 | 0 | 0 |

Hook scripts (`validate-rdl.sh`, `pbi-hooks.sh`, `validate-pbir.sh`, `validate-tmdl.sh`, `validate-report-binding.sh`) are pure validation wrappers with no credential exfiltration, eval+variable patterns, or subprocess shell=True usage. All hooks use `${CLAUDE_PLUGIN_ROOT}` path resolution with explicit timeout caps. No Critical or High risk patterns found.

---

## Bugs

These findings are mechanically verifiable and PR-eligible.

| File | Line | Rule | Description | Suggested Fix |
|------|------|------|-------------|---------------|
| plugins/fabric-cli/commands/audit-context.md | 1 | BUG-missing-frontmatter | Frontmatter has no `name:` field. Without a `name`, this slash command cannot be registered in the Claude Code plugin index. The `description`, `argument-hint`, and `model` fields are present but the command is effectively invisible to the plugin loader. | Add `name: audit-context` to the frontmatter block. |
| plugins/fabric-cli/commands/migrating-fabric-trial-capacities.md | 1 | BUG-missing-frontmatter | Frontmatter has no `name:` field. Same effect: the command cannot be discovered or invoked. The `description` and `argument-hint` are present but registration fails silently. | Add `name: migrating-fabric-trial-capacities` to the frontmatter block. |

---

## Security Fixes

None. No security findings.

---

## Quality Issues

These findings are below the PR threshold but reduce artifact quality.

| File | Line | Rule | Severity | Description |
|------|------|------|----------|-------------|
| plugins/pbi-desktop/agents/query-listener.agent.md | — | R09-output-format | MEDIUM | No explicit `## Output Format` section. The numbered process steps describe the agent's output implicitly, but the convention requires a dedicated section so consumers can rely on a stable output contract. |
| plugins/reports/agents/r-reviewer.agent.md | — | R07-examples | MEDIUM | Only 1 example block. Convention requires ≥2 examples to illustrate distinct inputs and outputs. The single example covers the happy path but leaves edge cases undocumented. |
| plugins/reports/agents/svg-reviewer.agent.md | — | R07-examples | MEDIUM | Only 1 example block. Same gap as r-reviewer — a single example is insufficient for a reviewer agent with multiple review dimensions. |
| plugins/reports/agents/python-reviewer.agent.md | — | R07-examples | MEDIUM | Only 1 example block. Convention requires ≥2 examples to illustrate distinct review contexts or visual complexity levels. |
| plugins/tabular-editor/commands/suggest-rule.md | 1 | R31-allowed-tools | MEDIUM | No `allowed-tools:` frontmatter field. Commands should declare which tools they may invoke so the runtime can enforce least-privilege constraints. |
| plugins/tabular-editor/commands/suggest-rule.md | — | R30-empty-input | MEDIUM | No empty-input handling. The command uses `$ARGUMENTS` but has no guard for the case when the user invokes it with no argument. It should detect an empty `$ARGUMENTS` and prompt the user for a rule description. |
| plugins/tabular-editor/commands/suggest-rule.md | — | R04-vague-quantifier | LOW | "appropriate Severity" appears twice. The command should instead specify a concrete mapping (e.g., "Severity 3 for violations that break the model, Severity 2 for quality issues, Severity 1 for documentation gaps"). |
| plugins/fabric-cli/commands/audit-context.md | 1 | R31-allowed-tools | MEDIUM | No `allowed-tools:` frontmatter field (in addition to the missing `name` bug). |
| plugins/fabric-cli/commands/audit-context.md | — | R30-empty-input | MEDIUM | No empty-input handling for `$ARGUMENTS`. The command should explain what to audit when invoked without a specific scope argument. |
| plugins/fabric-cli/commands/migrating-fabric-trial-capacities.md | 1 | R03-model | MEDIUM | No `model:` frontmatter field. The command invokes a multi-step migration workflow; without a model directive the runtime may assign a weaker model than the task requires. |
| plugins/fabric-cli/commands/migrating-fabric-trial-capacities.md | 1 | R31-allowed-tools | MEDIUM | No `allowed-tools:` frontmatter field (in addition to the missing `name` bug). |
| plugins/fabric-cli/commands/migrating-fabric-trial-capacities.md | — | R30-empty-input | MEDIUM | No empty-input handling for `$ARGUMENTS`. A migration command should validate that the required capacity name or workspace argument is present before executing destructive steps. |

---

## Cross-Component

**Consistency: GOOD.** All 10 plugin manifests share the same `author`, `repository`, `homepage`, and `license` fields consistently. Version `26.25` is uniform across all 54 artifacts. No broken cross-references between skills and the agents/commands that load them.

**Gap — broken command registration in fabric-cli plugin:** Both `audit-context.md` and `migrating-fabric-trial-capacities.md` reside in `plugins/fabric-cli/commands/` but neither can be registered as a slash command due to missing `name:`. The `fabric-cli` plugin advertises rich Fabric service tooling but its two commands are effectively dead on install. Users would see the skills and agent but find no usable slash commands under this plugin.

**Gap — thin example coverage on `custom-visuals` reviewer agents:** `r-reviewer`, `svg-reviewer`, and `python-reviewer` each have only 1 example, while `deneb-reviewer` (same plugin, same reviewer pattern) has 2. The pattern is inconsistent across agents within the same plugin. Users exploring the plugin's agents would find uneven documentation quality.

**Hook coverage is well-designed:** Three hooks cover three distinct plugin boundaries (`paginated-reports`, `pbi-desktop`, `pbip`). Each hook is scoped precisely with `if` conditions so it only fires on relevant file paths. No hook fires on all writes unconditionally.

**Skills are well-referenced:** Every agent's `description` field lists the exact trigger conditions that load it, and cross-skill references (`tmdl`, `pbir-format`, `pbi-report-design`, `pbir-cli`, `create-pbi-report`) use the canonical `name:` values from the target skills' frontmatter. No broken `[[name]]` references detected.

---

## Recommendation

**CONTRIBUTE.** The repository scores **95/100** with a CLEAR security result. The skill library is one of the highest-quality Power BI/Fabric plugin corpora encountered in this audit cycle — comprehensive, well-structured, consistently versioned, and free of security risks. The two bugs are trivially fixable (add `name:` to two frontmatter blocks) and functionally impactful (those commands are currently unregisterable). The quality issues on reviewer agents are low-effort improvements (add a second example). Recommend opening a PR targeting the two bug fixes in `plugins/fabric-cli/commands/`.
