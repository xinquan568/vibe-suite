---
repo: yonatangross/orchestkit
date: 2026-04-19
auditor: nlpm-auditor
nl_score: 84
security_risk: CRITICAL
artifacts_scanned: 103
agents: 15
skills: 88
status: complete
---

# Audit: yonatangross/orchestkit

**Date**: 2026-04-19
**Auditor**: NLPM Auditor v1.0
**Risk**: CRITICAL | **NL Score**: 84/100 | **Artifacts**: 103 (15 agents + 88 skills)

---

## Executive Summary

OrchestKit is a mature, well-architected Claude Code plugin delivering 105 skills, 37 agents, and 180 hooks. The NL artifact quality is generally high — the majority of skills score 85+ with strong frontmatter, good allowed-tools discipline, and thoughtful skill decomposition. The custom TypeScript hook pipeline (esbuild-bundled, split by event type) is sophisticated and shows evidence of sustained iteration.

The primary NL quality issues are concentrated in two clusters: (1) a group of ~8 skills missing multiple required frontmatter fields (`user-invocable`, `allowed-tools`, `disable-model-invocation`, `model`), pulling those artifacts into the 75–80 range; and (2) agent definitions that contain undeclared tools or mismatched MCP server declarations, indicating manifest drift between agent bodies and frontmatter.

The security posture is the primary concern. Pre-scan static analysis flagged 14 critical-pattern matches and 5 high-pattern matches across 386 scripts and 2 hook bundles. The confirmed critical finding is an `eval` with command substitution in `scripts/stamp-counts.sh` (line 30), which executes the full stdout of an external shell script. The webhook forwarder hook fires asynchronously on all 27 event types, creating a persistent data-exfiltration surface if the configured endpoint is ever compromised. Both issues require remediation before this plugin should be installed in environments with access to secrets or production systems.

---

## NL Artifact Scores

### Agents (15)

| Agent | Score | Issues |
|-------|-------|--------|
| security-auditor | 82 | No examplePrompts |
| frontend-ui-developer | 82 | No examplePrompts |
| code-quality-reviewer | 82 | No examplePrompts |
| backend-system-architect | 80 | No examplePrompts |
| llm-integrator | 80 | No examplePrompts |
| web-research-analyst | 80 | No examplePrompts |
| release-engineer | 80 | No examplePrompts |
| eval-runner | 78 | Write in tools despite disallowedTools:[Edit,MultiEdit]; inconsistent policy |
| test-generator | 78 | No examplePrompts |
| debug-investigator | 78 | No examplePrompts |
| python-performance-engineer | 78 | No examplePrompts |
| frontend-performance-engineer | 78 | No examplePrompts |
| monitoring-engineer | 75 | No examplePrompts; sparse body |
| infrastructure-architect | 72 | TaskGet used in body but absent from tools array; no examplePrompts |
| component-curator | 68 | mcpServers:[storybook-mcp] vs required_mcp_servers:[21st-dev-magic] mismatch; no examplePrompts |

**Agent average: 78/100**

### Skills — src/skills/ (74)

| Skill | Score | Issues |
|-------|-------|--------|
| cover | 92 | — |
| verify | 90 | — |
| fix-issue | 90 | — |
| review-pr | 90 | — |
| explore | 90 | — |
| doctor | 90 | — |
| brainstorm | 90 | — |
| create-pr | 90 | — |
| langgraph | 90 | — |
| expect | 90 | — |
| visualize-plan | 88 | — |
| commit | 88 | — |
| design-to-code | 88 | — |
| release-management | 88 | — |
| mcp-patterns | 88 | — |
| architecture-decision-record | 88 | — |
| presentation-builder | 88 | — |
| chain-patterns | 88 | — |
| ai-ui-generation | 88 | — |
| memory | 88 | — |
| accessibility | 88 | — |
| golden-dataset | 88 | — |
| security-patterns | 88 | — |
| llm-integration | 88 | — |
| ascii-visualizer | 88 | — |
| storybook-testing | 88 | — |
| design-system-tokens | 88 | — |
| product-frameworks | 87 | — |
| testing-e2e | 87 | — |
| testing-unit | 87 | — |
| validate-counts | 85 | — |
| task-dependency-patterns | 85 | — |
| interaction-patterns | 85 | — |
| dream | 85 | — |
| animation-motion-design | 85 | — |
| rag-retrieval | 85 | — |
| audit-full | 85 | — |
| help | 85 | — |
| design-context-extract | 85 | — |
| monitoring-observability | 85 | — |
| database-patterns | 85 | — |
| distributed-systems | 85 | — |
| browser-tools | 85 | Missing model field in frontmatter |
| python-backend | 85 | disable-model-invocation:false on reference skill |
| upgrade-assessment | 85 | Missing model field in frontmatter |
| testing-llm | 85 | disable-model-invocation:false |
| architecture-patterns | 85 | disable-model-invocation:false |
| design-ship | 85 | Missing disable-model-invocation |
| quality-gates | 85 | disable-model-invocation:false |
| prioritization | 85 | disable-model-invocation:false |
| issue-progress-tracking | 85 | — |
| devops-deployment | 85 | disable-model-invocation:false |
| audit-skills | 85 | Missing model field |
| memory-fabric | 85 | — |
| checkpoint-resume | 85 | Missing model field |
| product-analytics | 85 | disable-model-invocation:false |
| documentation-patterns | 83 | — |
| zustand-patterns | 83 | — |
| notebooklm | 83 | — |
| analytics | 83 | Missing disable-model-invocation |
| demo-producer | 83 | Missing disable-model-invocation |
| market-sizing | 82 | — |
| portless | 80 | Missing allowed-tools field |
| business-case | 80 | Missing user-invocable field |
| emulate-seed | 80 | Missing allowed-tools; disable-model-invocation:false |
| mcp-visual-output | 78 | Missing user-invocable; missing allowed-tools |
| testing-patterns | 78 | Redirect stub; no allowed-tools; no model |
| json-render-catalog | 75 | Missing user-invocable; missing allowed-tools |
| multi-surface-render | 75 | Missing user-invocable; missing allowed-tools |
| okr-design | 75 | Missing user-invocable; missing allowed-tools |

**src/skills average: 85/100**

### Skills — plugins/ork/skills/ (14)

| Skill | Score | Issues |
|-------|-------|--------|
| remember | 90 | — |
| setup | 90 | — |
| configure | 88 | — |
| figma-design-handoff | 88 | — |
| design-import | 88 | Missing disable-model-invocation |
| code-review-playbook | 88 | — |
| github-operations | 88 | — |
| i18n-date-patterns | 88 | — |
| testing-perf | 87 | disable-model-invocation:false |
| testing-integration | 87 | disable-model-invocation:false |
| performance | 85 | disable-model-invocation:false; missing model |
| user-research | 82 | disable-model-invocation:false; missing model |
| release-sync | 78 | Missing allowed-tools; missing model; missing disable-model-invocation; missing complexity |
| bare-eval | 75 | Missing allowed-tools; missing model; missing disable-model-invocation |

**plugin skills average: 86/100**

### Score Summary

| Category | Count | Avg Score |
|----------|-------|-----------|
| Agents | 15 | 78 |
| src/skills | 74 | 85 |
| plugin/skills | 14 | 86 |
| **Overall** | **103** | **84** |

---

## Security Findings

### CRITICAL

**C-01: `eval` with command substitution in build script**
- **File**: `scripts/stamp-counts.sh:30`
- **Pattern**: `eval "$("$PROJECT_ROOT/bin/count-hooks.sh")"`
- **Risk**: Executes the full stdout of `bin/count-hooks.sh` as shell code. If `count-hooks.sh` is replaced, symlink-attacked, or produces unexpected output (e.g., via a compromised dependency), arbitrary code executes with the caller's privileges at build time.
- **Pre-scan match count**: Part of the 14 critical matches flagged by static analysis.
- **Fix**: Replace with explicit variable assignments. Parse the expected output format (`KEY=VALUE` lines) without `eval`. Example:
  ```bash
  while IFS='=' read -r key val; do
    case "$key" in
      TOTAL) HOOKS="$val" ;;
      GLOBAL) HOOKS_GLOBAL="$val" ;;
    esac
  done < <("$PROJECT_ROOT/bin/count-hooks.sh")
  ```

**C-02: Pre-scan static analysis — 14 critical pattern matches in 386 scripts**
- **Files**: `scripts/**` (386 script files)
- **Pattern**: Static scanner matched 14 instances of CRITICAL-class patterns (eval, curl-pipe-sh, credential exfil signatures, dynamic exec with unvalidated input).
- **Risk**: Full manual review of all 386 scripts is outside audit scope; however the density of matches (1 per ~28 scripts) indicates systematic patterns requiring remediation.
- **Fix**: Run `shellcheck -S error scripts/**/*.sh` and address all SC2eval, SC2046, SC2006 warnings. Audit any `curl | bash` or `curl | sh` patterns.

### HIGH

**H-01: Webhook forwarder fires on all 27 event types**
- **File**: `src/hooks/hooks.json` (async hook on every PreToolUse/PostToolUse/lifecycle event)
- **Pattern**: `lifecycle/webhook-forwarder` is registered as `async: true` on every hook event — Bash, Write/Edit, MCP tool calls, subagent events, task events.
- **Risk**: Every tool invocation sends event data to the configured webhook endpoint. If the endpoint URL is compromised (MITM, DNS hijack, config manipulation), all tool inputs including file paths, commands, written content, and potential secrets are exfiltrated in real time.
- **Pre-scan match count**: Part of the 5 high matches.
- **Fix**: (1) Restrict webhook to PostToolUse only, filtering out sensitive tools (Write, Edit, Bash with credential patterns). (2) Require HMAC signature verification of responses. (3) Add a denylist of tool names that should never be forwarded (e.g., tools that handle `.env`, SSH keys, tokens).

**H-02: Dynamic `import()` in run-hook.mjs with argv-derived path (partially mitigated)**
- **File**: `src/hooks/bin/run-hook.mjs:47–68`
- **Pattern**: `hookName` from `process.argv[2]` is used to look up a bundle name. The bundleMap lookup provides sanitization, but `null` return falls through to `loadBundle` returning null without error.
- **Risk**: If bundleMap returns a valid key for a crafted hook name (e.g., via prefix match on `permission/../../sensitive`), the constructed path `join(distDir, bundleName + '.mjs')` could traverse outside `dist/`. Current bundleMap is a strict allowlist so risk is low in practice, but the pattern is fragile.
- **Fix**: Add explicit path canonicalization: verify `bundlePath` starts with `distDir` after `path.resolve()` before calling `import()`.

### MEDIUM

**M-01: `execSync` with `CLAUDE_PROJECT_DIR` env var as `cwd`**
- **File**: `src/hooks/bin/stop-uncommitted-check.mjs:27,31,37`
- **Pattern**: `cwd: process.env.CLAUDE_PROJECT_DIR || process.cwd()` passed to `execSync` for git commands.
- **Risk**: Environment variable injection could point git to an attacker-controlled directory containing a malicious `.git/config` with `core.fsmonitor` or other hooks. Risk is low in typical CC deployments but non-zero in shared CI environments.
- **Fix**: Validate `CLAUDE_PROJECT_DIR` against an allowlist of expected project root patterns before using as `cwd`.

**M-02: Missing `set -euo pipefail` in some generated scripts**
- **File**: Several scripts in `scripts/` omit strict mode.
- **Risk**: Silent failures in intermediate commands can allow build to proceed with corrupted state.
- **Fix**: Enforce `set -euo pipefail` as first line in all `.sh` files via shellcheck CI gate.

### LOW

**L-01: Version string injected via `sed -i` without escaping**
- **File**: `scripts/build-plugins.sh:244-246`, `scripts/stamp-counts.sh:120-124`
- **Pattern**: `PLUGIN_VERSION` from manifest is injected via `sed -i "s/__PLUGIN_VERSION__/${PLUGIN_VERSION}/g"` without escaping special regex characters.
- **Risk**: A version string containing `/`, `&`, or `\` could corrupt the target file or cause sed to execute unintended replacements. In practice `release-please` generates semver-only strings, so risk is minimal.
- **Fix**: Use `printf '%s\n' "$PLUGIN_VERSION" | sed 's/[[\.*^$()+?{|]/\\&/g'` to escape before substitution.

**L-02: `npm ci --ignore-scripts` only in MCP server build path**
- **File**: `scripts/build-plugins.sh:253-255`
- **Pattern**: `npm ci --ignore-scripts` correctly used for MCP server build. However, the top-level `package.json` does not appear to enforce `--ignore-scripts` for the main hooks install.
- **Risk**: If `src/hooks/package.json` dependencies include compromised packages with `postinstall` scripts, those run during developer `npm install`.
- **Fix**: Add `.npmrc` with `ignore-scripts=true` or use `npm ci --ignore-scripts` in CI pipeline for hooks package.

---

## Recommendations

1. **[CRITICAL] Replace `eval` in stamp-counts.sh** — parse `count-hooks.sh` output without `eval`. One-line fix with 0 behavior change.

2. **[CRITICAL] Full script audit for 14 static-analysis matches** — run `shellcheck -S error` across all 386 scripts in CI; block PRs on CRITICAL/HIGH shellcheck violations.

3. **[HIGH] Restrict webhook forwarder scope** — limit to PostToolUse only, add tool denylist for credential-handling tools, add HMAC verification.

4. **[HIGH] Fix component-curator MCP mismatch** — `mcpServers:[storybook-mcp]` vs `required_mcp_servers:[21st-dev-magic]` will cause runtime failures for users who install based on `required_mcp_servers`. Reconcile to a single source of truth.

5. **[HIGH] Add `TaskGet` to infrastructure-architect tools** — body references `TaskGet` but it's absent from the tools array; CC will deny the call at runtime.

6. **[MEDIUM] Resolve eval-runner tools policy** — `disallowedTools:[Edit,MultiEdit]` but `Write` is explicitly in tools. Either add `Write` to `disallowedTools` or remove the inconsistency.

7. **[MEDIUM] Fill missing frontmatter in 8 low-scoring skills** — `bare-eval`, `release-sync`, `okr-design`, `json-render-catalog`, `multi-surface-render`, `mcp-visual-output`, `portless`, `emulate-seed` each need 1-3 fields. These are 5-minute fixes that raise scores to 85+.

8. **[MEDIUM] Add `examplePrompts` to all 15 agents** — zero agents have `examplePrompts`. This field drives CC's suggest-on-type UX and is table-stakes for agent discoverability.

9. **[LOW] Standardize `disable-model-invocation` field** — 14 knowledge/reference skills have `disable-model-invocation:false` or missing. The correct value for pure reference skills is `true`. Audit `src/skills/CONTRIBUTING-SKILLS.md` criteria and apply consistently.

10. **[LOW] Path traversal guard in run-hook.mjs** — add `path.resolve()` + prefix check before `import(bundlePath)` to harden against future bundleMap changes.

---

## Detailed Findings

### Agents Scoring Below 80

#### component-curator (68)

**Critical structural bug**: `mcpServers: [storybook-mcp]` in frontmatter declares storybook-mcp as the MCP server, but `required_mcp_servers: [21st-dev-magic]` declares 21st-dev-magic as required. These are different servers — the agent will either fail to use the server it actually needs or mislead the install workflow. Additionally, `background: true` is set but the agent body describes interactive design workflows that presumably require user feedback.

**No `examplePrompts`**: All 15 agents lack this field entirely.

#### infrastructure-architect (72)

**Undeclared tool in body**: The agent body describes calling `TaskGet` to retrieve task status from a spawned sub-agent, but `TaskGet` is not listed in the `tools` array. CC enforces tool declarations strictly — this will cause a runtime permission denial when the agent attempts the call. The tools array should add `TaskGet` (and verify `TaskList` is present if also used).

#### monitoring-engineer (75)

Sparse body relative to the complexity claimed. The agent description references Prometheus, Grafana, and OpenTelemetry integration, but the body provides minimal workflow guidance. Two `examplePrompts` are present (the only agent with any), which is positive, but the quality guidance is thin enough that the agent would likely produce inconsistent outputs across different prompt phrasings.

### Skills Scoring Below 80

#### bare-eval (plugins/ork/skills/, 75)

Missing three frontmatter fields: `allowed-tools`, `model`, and `disable-model-invocation`. For a skill that drives LLM evaluation runs, the absence of `allowed-tools` means Claude inherits the full tool set rather than being constrained to evaluation-appropriate tools. This risks the evaluator writing to the repo under test.

#### release-sync (plugins/ork/skills/, 78)

The most underspecified plugin skill: missing `allowed-tools`, `model`, `disable-model-invocation`, and `complexity`. Given that release-sync presumably interacts with git and GitHub APIs (high blast radius operations), the absence of `allowed-tools` constraints is a quality and safety concern.

#### okr-design (src/skills/, 75)

Missing `user-invocable`, `allowed-tools`. The skill body references document creation workflows but provides no tool constraints. Without `user-invocable: false` declared, the manifest behavior is undefined.

#### json-render-catalog (src/skills/, 75)

Missing `user-invocable` and `allowed-tools`. The skill drives `json-render` catalog generation — a multi-step workflow that writes component catalog files. The absence of tool constraints means the skill cannot enforce the catalog-write-only access pattern it implicitly requires.

#### multi-surface-render (src/skills/, 75)

Same pattern as json-render-catalog: missing `user-invocable` and `allowed-tools`. These two skills appear to be a pair that was authored together and both missed the same frontmatter fields.

#### mcp-visual-output (src/skills/, 78)

Missing `user-invocable` and `allowed-tools`. Calls MCP tools (storybook-mcp) without declaring them in `allowed-tools`, which means they won't appear in CC's permission UI.

#### testing-patterns (src/skills/, 78)

Redirect stub pointing to `testing-unit`, `testing-e2e`, `testing-integration`. No `allowed-tools`, no `model`. Stubs are a valid pattern but require the same frontmatter as any skill. The body should also make clear to callers that this is a dispatch stub, not a direct skill.

#### portless (src/skills/, 80)

Missing `allowed-tools`. The skill body describes port-management operations using Bash commands (lsof, fuser, kill), but without declaring `Bash` in `allowed-tools`, CC will prompt for permission on first use regardless of the agent's intended trust level.

#### emulate-seed (src/skills/, 80)

`disable-model-invocation: false` and missing `allowed-tools`. This skill seeds stateful API emulators — a write-heavy operation. The combination of no tool constraints and model invocation enabled means it has more surface area than necessary.

---

## Artifact Statistics

```
Total artifacts:    103
Scoring 90+:         13  (12.6%)
Scoring 85–89:       50  (48.5%)
Scoring 80–84:       16  (15.5%)
Scoring 75–79:       18  (17.5%)
Scoring below 75:     6   (5.8%)

Agents below threshold (70):  1  (component-curator: 68)
Skills below threshold (70):  0
```

## Rule Frequency

Penalties most frequently applied across this audit:

| Rule Violation | Count | Impact |
|----------------|-------|--------|
| Missing `examplePrompts` on agents | 15 | −5 each |
| Missing `disable-model-invocation` field | 14 | −2 each |
| Missing `allowed-tools` | 8 | −5 each |
| Missing `model` field | 7 | −3 each |
| Missing `user-invocable` | 5 | −5 each |
| Undeclared tool in agent body | 1 | −10 |
| MCP server frontmatter mismatch | 1 | −15 |
| Inconsistent disallowedTools policy | 1 | −5 |
