# NLPM Audit: Yeachan-Heo/oh-my-claudecode
**Date**: 2026-04-19  |  **Artifacts**: 58  |  **Strategy**: multi-agent parallel scan
**NL Score**: 80/100
**Security**: REVIEW
**Bugs**: 3  |  **Quality Issues**: 10  |  **Security Findings**: 8

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| src/agents/templates/exploration-template.md | agent-template | 45 | No YAML frontmatter — `name` and `description` absent; file cannot be registered as an agent |
| src/agents/templates/implementation-template.md | agent-template | 45 | No YAML frontmatter — `name` and `description` absent; file cannot be registered as an agent |
| skills/debug/SKILL.md | skill | 65 | Missing `triggers`, `level`, and `## Output Format` section; no examples (-15 -10 -10) |
| skills/skillify/SKILL.md | skill | 65 | Missing `triggers`, `level`, and `## Output Format` section; no examples (-15 -10 -10) |
| skills/verify/SKILL.md | skill | 65 | Missing `triggers`, `level`, and `## Output Format` section; no examples (-15 -10 -10) |
| skills/omc-reference/SKILL.md | skill | 70 | No `level` field; `user-invocable: false` is non-standard frontmatter; no examples, no output format |
| skills/remember/SKILL.md | skill | 70 | Missing `triggers` and `level`; no output format section; sparse body |
| skills/ask/SKILL.md | skill | 72 | Missing `triggers` and `level`; one example present but no output format section |
| skills/project-session-manager/SKILL.md | skill | 72 | HIGH security findings (dangerously-skip-permissions, unsanitized tmux send-keys); no `triggers` field |
| skills/ai-slop-cleaner/SKILL.md | skill | 75 | Missing `triggers` in frontmatter; no explicit `## Output Format` section |
| skills/cancel/SKILL.md | skill | 75 | Missing `triggers`; bash fallback embeds `rm -f` and `python3` one-liner without input validation |
| skills/learner/SKILL.md | skill | 75 | Missing `triggers`; Level 7 self-improving designation lacks output format for the stable workflow section |
| skills/mcp-setup/SKILL.md | skill | 75 | Missing `triggers`; `npx -y` auto-executes unpinned packages (LOW security) |
| skills/self-improve/SKILL.md | skill | 75 | Missing `triggers`; no `## Output Format` section; autonomous improvement engine with no trigger guardrails |
| skills/setup/SKILL.md | skill | 75 | Missing `triggers`; thin routing-only logic with no examples |
| agents/code-simplifier.md | agent | 78 | Missing `<Examples>` section entirely (-15); all other fields present |
| skills/hud/SKILL.md | skill | 78 | Non-standard frontmatter fields (`role`, `scope`) that are NLPM-invisible; missing `triggers` |
| skills/skill/SKILL.md | skill | 78 | Missing `triggers`; subcommands documented but no concrete end-to-end example |
| skills/wiki/SKILL.md | skill | 78 | Missing `level` field; has `triggers` (only file with triggers in this score band) |
| skills/ccg/SKILL.md | skill | 80 | Missing `triggers`; brief content for a Level 5 skill; no output format |
| skills/configure-notifications/SKILL.md | skill | 80 | MEDIUM security findings (plaintext token storage, curl with user tokens); no `triggers` |
| skills/deepinit/SKILL.md | skill | 80 | Missing `triggers`; no examples; creates AGENTS.md files but output format not enumerated |
| skills/omc-doctor/SKILL.md | skill | 80 | MEDIUM security finding (WebFetch to raw.githubusercontent.com); missing `triggers` |
| skills/omc-setup/SKILL.md | skill | 80 | MEDIUM security finding (bash from $CLAUDE_PLUGIN_ROOT path); missing `triggers` |
| skills/release/SKILL.md | skill | 80 | Missing `triggers`; conditional branching flow lacks numbered steps in one path |
| skills/trace/SKILL.md | skill | 80 | Missing `triggers` in frontmatter despite having `agent` field; no output format section |
| skills/visual-verdict/SKILL.md | skill | 80 | Missing `triggers`; XML-format content but no YAML trigger registration |
| skills/writer-memory/SKILL.md | skill | 80 | Missing `triggers`; Level 7 with dense subcommand surface but no output format table |
| skills/omc-teams/SKILL.md | skill | 82 | Labeled as "legacy compatibility" in body but no `deprecated` frontmatter flag; missing `triggers` |
| skills/sciomc/SKILL.md | skill | 82 | Missing `triggers`; decomposition/synthesis steps present but no output format |
| skills/team/SKILL.md | skill | 82 | Missing `triggers` despite being the primary team orchestration skill; per-role routing well documented |
| skills/ultraqa/SKILL.md | skill | 82 | Missing `triggers`; QA cycle output not formally specified in output format section |
| skills/ultrawork/SKILL.md | skill | 82 | Missing `triggers`; XML-format content; no `## Output Format` but Completion_Criteria implicitly covers it |
| agents/document-specialist.md | agent | 83 | Inconsistent formatting — some sections use XML tags, others bare markdown; output format partially present |
| skills/external-context/SKILL.md | skill | 83 | Missing `triggers`; examples present; no output format section |
| agents/analyst.md | agent | 88 | Near-complete; `Open_Questions` section is good practice; no empty-input handling clause |
| agents/debugger.md | agent | 88 | XML-format prompt well-structured; Good/Bad examples present; no empty-input handling clause |
| agents/explore.md | agent | 88 | `disallowedTools: [Write, Edit]` declared; context budget section; no empty-input handling |
| agents/test-engineer.md | agent | 88 | TDD enforcement table present; no empty-input handling clause |
| agents/verifier.md | agent | 88 | Strict output format defined; no empty-input handling |
| skills/deep-interview/SKILL.md | skill | 88 | Pipeline/next-skill/handoff in frontmatter; mathematical ambiguity scoring; minor vague quantifiers |
| agents/planner.md | agent | 85 | Uses Write tool for plan output; RALPLAN-DR protocol; no `triggers` field in frontmatter |
| agents/security-reviewer.md | agent | 85 | `ast_grep_search` referenced in Tool_Usage but absent from formal `disallowedTools` allow-list; good examples |
| skills/autopilot/SKILL.md | skill | 85 | XML-format content; `Use_When` section substitutes for missing YAML `triggers`; good examples |
| skills/plan/SKILL.md | skill | 85 | Pipeline/next-skill/handoff in frontmatter; consensus mode well-documented; missing `triggers` |
| skills/ralph/SKILL.md | skill | 85 | Detailed PRD-driven loop; good examples; missing `triggers` |
| skills/ralplan/SKILL.md | skill | 85 | Has `argument-hint`; detailed flags section; missing `triggers` in YAML (has `Use_When` in body) |
| agents/designer.md | agent | 87 | Solid structure; no empty-input handling |
| agents/executor.md | agent | 87 | Solid structure; no empty-input handling |
| agents/git-master.md | agent | 87 | Solid structure; no empty-input handling |
| agents/qa-tester.md | agent | 87 | tmux integration well-specified; no empty-input handling |
| agents/writer.md | agent | 87 | Haiku model appropriate; good scope constraints |
| agents/architect.md | agent | 90 | `disallowedTools: [Write, Edit]` declared; consensus addendum; exemplary structure |
| agents/code-reviewer.md | agent | 90 | Extensive review modes; `disallowedTools: [Write, Edit]`; good examples |
| agents/critic.md | agent | 90 | 5-phase investigation protocol; self-audit + realist-check sections; excellent examples |
| agents/scientist.md | agent | 90 | Structured output markers ([OBJECTIVE], [FINDING]); `disallowedTools: [Write, Edit]`; good examples |
| agents/tracer.md | agent | 90 | Evidence strength hierarchy; good examples; exemplary scope discipline |
| skills/deep-dive/SKILL.md | skill | 90 | Pipeline/next-skill/handoff/level all present; final checklist; best-in-class skill structure |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 5 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | hooks/hooks.json (11 hook types, Node.js scripts via run.cjs) |
| Scripts | scripts/run.cjs, scripts/keyword-detector.mjs, scripts/skill-injector.mjs, scripts/session-start.mjs, scripts/project-memory-session.mjs, scripts/wiki-session-start.mjs, scripts/setup-init.mjs, scripts/setup-maintenance.mjs, scripts/pre-tool-enforcer.mjs, scripts/permission-handler.mjs, scripts/post-tool-verifier.mjs, scripts/setup-claude-md.sh, scripts/setup-progress.sh |
| MCP configs | .mcp.json (referenced in plugin.json) |
| Package manifests | .claude-plugin/plugin.json (oh-my-claudecode v4.12.1) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | High | skills/project-session-manager/SKILL.md | 255, 307, 337 | `--dangerously-skip-permissions` flag | All three session types (PR review, issue fix, feature) spawn Claude with `--dangerously-skip-permissions`, bypassing the Claude Code permission system entirely. The spawned Claude instance can read, write, and execute files without user approval prompts. The comment on line 253 acknowledges this is to suppress the trust prompt — the workaround is to `cd` to the project directory first and start the session there, or to pre-accept permissions for the project directory. |
| 2 | High | skills/project-session-manager/SKILL.md | 260, 309, 338 | Unsanitized tmux `send-keys` with API-sourced data | PR titles (line 260), issue titles (line 309), and feature names (line 338) retrieved from the GitHub API are passed directly to `tmux send-keys -l` without sanitization. Tmux's `-l` flag (literal mode) does prevent terminal escape sequence injection, but newline characters, control sequences, and null bytes in PR/issue titles — which GitHub permits — can still break the intended command structure. A crafted PR title could inject unexpected commands into the tmux session. |
| 3 | Medium | skills/configure-notifications/SKILL.md | 51, 154 | Plaintext API credential storage | Bot tokens (Telegram, Discord) and webhook URLs (Slack) are written to `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.omc-config.json` in plaintext. The `.claude/` directory is not encrypted and may be included in backups, synced via dotfile managers, or readable by other processes running as the same user. Tokens with long TTLs stored here represent a persistent credential exposure risk. |
| 4 | Medium | skills/configure-notifications/SKILL.md | 122, 208 | `curl` with user-provided tokens to external APIs | Bot tokens collected interactively are interpolated into `curl` calls to `api.telegram.org` (line 122) and Discord/Slack endpoints (line 208). If token collection is triggered by a compromised context or if the token string contains shell metacharacters, the interpolation could produce unexpected behavior. The skill does not validate token format before use. |
| 5 | Medium | hooks/hooks.json | 10, 15, 27, 32, 37, 47, 57, 69, 81, 93 | `$CLAUDE_PLUGIN_ROOT` in all hook command strings | All 10 hook command strings construct their executable path by interpolating `$CLAUDE_PLUGIN_ROOT` directly: `node "$CLAUDE_PLUGIN_ROOT"/scripts/run.cjs "$CLAUDE_PLUGIN_ROOT"/scripts/*.mjs`. If `$CLAUDE_PLUGIN_ROOT` is unset, empty, or set to a malicious path (e.g., via environment manipulation), an attacker could redirect hook execution to arbitrary scripts. The hook runner does not validate or canonicalize the path before execution. |
| 6 | Medium | skills/omc-setup/SKILL.md | 120, 121, 140 | `bash` with `$CLAUDE_PLUGIN_ROOT` path interpolation | Setup phases run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup-claude-md.sh"` and `bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup-progress.sh"` without validating the env var. This is the same path-injection vector as finding #5, but expressed through skill instructions rather than the hook runner. An attacker who can influence `$CLAUDE_PLUGIN_ROOT` could redirect these bash invocations to arbitrary executables. |
| 7 | Medium | skills/omc-doctor/SKILL.md | 185 | `WebFetch` to `raw.githubusercontent.com` for live CLAUDE.md update | The doctor skill fetches `https://raw.githubusercontent.com/Yeachan-Heo/oh-my-claudecode/main/docs/CLAUDE.md` and uses the result to update the local installation. If the upstream repository is compromised (supply-chain attack), or if DNS/TLS is manipulated, the fetched content could contain malicious instructions that get injected into the user's CLAUDE.md. The fetch is unauthenticated and the content is not integrity-checked before use. |
| 8 | Low | skills/mcp-setup/SKILL.md | 101, 106, 111 | `npx -y` auto-executes unpinned MCP packages | MCP server setup uses `npx -y @upstash/context7-mcp`, `npx -y exa-mcp-server`, and `npx -y @modelcontextprotocol/server-filesystem` without pinning versions. `npx -y` downloads and immediately executes the latest published version of these packages without prompting. A compromised or typosquatted package at the latest tag would execute in the user's environment automatically. |

## Bugs (PR-worthy)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | src/agents/templates/exploration-template.md | Missing YAML frontmatter entirely — the file has no `name`, `description`, or `model` fields. NLPM's scanner will attempt to score it as an agent definition and fail to register it; the `-25 -25 -5 = -55` penalty chain drops it to a 45. The file is intended as a human-readable template, but its placement in `src/agents/templates/` means it appears in agent discovery. | Either add YAML frontmatter (`name: exploration-template`, `description: ...`, `model: sonnet`) if it should be a registerable agent, or move it outside the discoverable agents path (e.g., `docs/templates/`) if it is documentation only. |
| 2 | src/agents/templates/implementation-template.md | Same issue as Bug #1 — missing YAML frontmatter causes registration failure and a 45/100 NL score. | Same fix path: add frontmatter or relocate to a non-scanned documentation directory. |
| 3 | .github/CLAUDE.md | Version string `4.8.2` is stale — `docs/CLAUDE.md` and `plugin.json` both declare version `4.12.1`. Any contributor reading `.github/CLAUDE.md` will have incorrect version context. The divergence spans at least 4 minor versions, suggesting the file was not updated during any of those releases. | Update the version string in `.github/CLAUDE.md` to `4.12.1` and add a note to the release checklist to keep it in sync with `plugin.json`. |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | skills/configure-notifications/SKILL.md | Lines 51, 154: API credentials written to plaintext `~/.claude/.omc-config.json`. | Add a note in the setup flow that users should set credentials as environment variables (`TELEGRAM_BOT_TOKEN`, `DISCORD_WEBHOOK_URL`, `SLACK_WEBHOOK_URL`) instead of persisting them to disk. Treat the JSON config as a fallback, not the primary path. Mention that the file should be added to `.gitignore` if the `.claude/` directory is ever tracked. |
| 2 | skills/configure-notifications/SKILL.md | Lines 122, 208: `curl` calls interpolate `$BOT_TOKEN` with no format validation. | Add a token format validation step before the curl call (Telegram tokens match `^\d+:[A-Za-z0-9_-]{35}$`). Prefer passing the token via environment variable rather than shell interpolation: `curl -s "https://api.telegram.org/bot$(printenv BOT_TOKEN)/getUpdates"`. |
| 3 | hooks/hooks.json + skills/omc-setup/SKILL.md | `$CLAUDE_PLUGIN_ROOT` interpolated unvalidated into command strings (hooks.json lines 10–93; omc-setup lines 120–140). | The hook runner (`scripts/run.cjs`) should validate that `$CLAUDE_PLUGIN_ROOT` is an absolute path that resolves to the expected plugin directory before passing it to child processes. Add a guard: `if (!process.env.CLAUDE_PLUGIN_ROOT?.startsWith('/')) throw new Error('CLAUDE_PLUGIN_ROOT unset or relative')`. |
| 4 | skills/omc-doctor/SKILL.md | Line 185: unauthenticated `WebFetch` to upstream GitHub used to update local CLAUDE.md. | Pin the fetch to a specific commit SHA instead of `main` branch: `https://raw.githubusercontent.com/Yeachan-Heo/oh-my-claudecode/<SHA>/docs/CLAUDE.md`. Display a diff and ask for user confirmation before writing the fetched content. |
| 5 | skills/mcp-setup/SKILL.md | Lines 101, 106, 111: `npx -y` auto-executes unpinned packages. | Pin to a verified version: `npx -y @upstash/context7-mcp@<version>`. At minimum, show the user what will be installed and ask for confirmation before running `npx -y`. Consider using `claude mcp add` with `--version` flag where available. |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | agents/code-simplifier.md | Missing `<Examples>` section entirely. All other agents in the catalog include Good/Bad examples; this agent defines what it does but gives no concrete input/output illustration. A refactoring agent without examples is particularly risky — authors cannot calibrate what "appropriate simplification" looks like. | -15 |
| 2 | skills/debug/SKILL.md, skills/verify/SKILL.md, skills/skillify/SKILL.md | All three are utility skills with only `name` and `description` in frontmatter. Missing: `level`, `triggers`, `argument-hint`, and `## Output Format`. These skills are invocable by name but are invisible to NLPM's trigger-dispatch system. Users must know the exact skill name. | -35 each |
| 3 | skills/ (33 of 37 files) | `triggers` field absent from frontmatter across the majority of skills. Only `skills/wiki/SKILL.md` and `skills/configure-notifications/SKILL.md` declare YAML `triggers`. Some skills compensate with XML `<Use_When>` or `Use_When` sections in the body (autopilot, ralplan), but these are invisible to NLPM's trigger auto-detection. Without YAML `triggers`, keyword-based invocation requires users to know skill names in advance. | informational |
| 4 | agents/document-specialist.md | Inconsistent formatting throughout — some behavioral sections use `<XML_Tags>` while others use bare markdown headers. Contrast with agents like `architect.md` and `scientist.md` which are uniformly XML-structured. The inconsistency signals partial maintenance; a reader cannot rely on structural cues. | -7 |
| 5 | agents/security-reviewer.md | Body references `ast_grep_search` as an available tool in the `<Tool_Usage>` section, but this tool does not appear in the agent's formal `disallowedTools` or allowed-tools list. If `ast_grep_search` is not available in the execution environment, the agent will silently degrade without surfacing an error. | informational |
| 6 | agents/planner.md | Uses the `Write` tool to persist plans to disk, which is appropriate for a planner, but this is not declared in frontmatter. Agents that write files should either list `Write` explicitly in their tool configuration or justify its presence in the prompt body. Without explicit declaration, downstream model routing decisions cannot account for the write surface. | informational |
| 7 | .github/CLAUDE.md | Contains version `4.8.2` while the live codebase is at `4.12.1`. The `.github/CLAUDE.md` context is loaded for CI/PR agents; stale version numbers in CI context cause agents to make incorrect assumptions about available features. | informational |
| 8 | skills/omc-reference/SKILL.md | Uses `user-invocable: false` as a frontmatter field, but this is not a standard NLPM frontmatter key. If NLPM's scanner reads this file, it will score it as a normal skill (without understanding the non-invocable intent) and apply penalties accordingly. Consider moving this to a standard documentation mechanism or using a NLPM-recognized field. | informational |
| 9 | skills/hud/SKILL.md | Uses non-standard frontmatter fields `role: config-writer` and `scope: ~/.claude/**` with inline `# DOCUMENTATION ONLY` comments. These are documentation conventions layered on top of YAML rather than standard NLPM fields, making them invisible to any tool that parses frontmatter by schema. | informational |
| 10 | skills/learner/SKILL.md | Level 7 designation is undocumented in the level taxonomy (levels 1-5 are referenced in other agents). Without a published level scale that includes 7, downstream routing cannot interpret this correctly. `writer-memory/SKILL.md` also uses level 7. | informational |

## Cross-Component
- **Agent-to-skill references: MOSTLY CONSISTENT** — Skills correctly reference agents by canonical name (`tracer` agent in `trace/SKILL.md`; `document-specialist` in `external-context/SKILL.md`; `scientist` in `sciomc/SKILL.md`). No broken agent references found.
- **Version: INCONSISTENT** — `.github/CLAUDE.md` declares version `4.8.2`; `docs/CLAUDE.md` and `.claude-plugin/plugin.json` declare `4.12.1`. Root `CLAUDE.md` (the OMC runtime context) does not declare a version number, relying on the OMC:VERSION comment instead.
- **OMC:VERSION markers: CONSISTENT** — All three `CLAUDE.md` files have `OMC:START`/`OMC:END` markers. The root `CLAUDE.md` (used as runtime context) references `4.9.1` in its OMC:VERSION comment while `docs/CLAUDE.md` is the canonical `4.12.1`. This three-way divergence means different surfaces report different versions.
- **Template placement: BUG** — `src/agents/templates/` contains `.md` files that will be discovered by NLPM's agent scanner. Templates intended for human authors, not runtime registration, should not be in agent-discoverable paths.
- **Triggers: GAP** — 33 of 37 skills have no YAML `triggers`. The OMC `CLAUDE.md` runtime context documents keyword triggers for skills (e.g., "autopilot"→autopilot, "ralph"→ralph), but these trigger mappings live in the CLAUDE.md prose rather than in skill frontmatter. This means trigger routing is maintained in two places and can drift.
- **Security perimeter: CONCENTRATED** — All HIGH and MEDIUM security findings are concentrated in three skills: `project-session-manager`, `configure-notifications`, and `omc-setup`/`omc-doctor`. The core agents (19 files) are clean. Isolating or sandboxing these skills would reduce the attack surface significantly.

## Recommendation

**REVIEW** — Submit NL fix PRs for the three bugs; flag security findings in an issue for maintainer triage.

The core agent catalog (19 agents) is high quality at 87 average, with `architect`, `critic`, `code-reviewer`, `scientist`, and `tracer` serving as reference implementations. The `deep-dive` and `deep-interview` skills demonstrate what a well-specified skill looks like. These are the templates the weaker skills should be brought up to.

The two immediate priorities are:

1. **Security (Issue):** The `--dangerously-skip-permissions` pattern in `project-session-manager` is the most impactful finding — it creates fully unrestricted Claude sessions without user consent at each use. This deserves a dedicated issue with severity HIGH before any further automation is added to PSM. The `$CLAUDE_PLUGIN_ROOT` path-injection vector in hooks affects the entire hook system and should be addressed in `scripts/run.cjs` at the validation layer.

2. **Triggers gap (PR):** Adding YAML `triggers` to the 33 skills that lack them would lift the average NL score by ~4 points and make the skill catalog navigable without memorizing names. The existing `CLAUDE.md` keyword-trigger documentation provides the source of truth for what each trigger string should be.
