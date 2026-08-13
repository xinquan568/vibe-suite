# NLPM Audit: eyaltoledano/claude-task-master
**Date**: 2026-04-06  |  **Artifacts**: 57  |  **Strategy**: batched
**NL Score**: 67/100
**Security**: BLOCKED
**Bugs**: 6  |  **Quality Issues**: 58  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| tests/unit/scripts/modules/commands/README.md | doc | 50 | Not an executable NL artifact; no frontmatter |
| .claude/commands/go/pr-comments.md | command | 60 | No name frontmatter; no empty-input handling |
| packages/claude-code-plugin/commands/smart-workflow.md | command | 60 | No name frontmatter; no output format |
| packages/claude-code-plugin/commands/command-pipeline.md | command | 60 | No name frontmatter; no output format |
| .claude/commands/dedupe.md | command | 65 | Missing name in frontmatter |
| packages/claude-code-plugin/commands/learn.md | command | 65 | No name frontmatter; vague quantifiers |
| .cursor/commands/goham.md | command | 65 | No name or description frontmatter |
| .claude/commands/go/ham.md | command | 65 | No name or description frontmatter |
| packages/claude-code-plugin/commands/show-task.md | command | 65 | No name frontmatter; vague quantifiers |
| packages/claude-code-plugin/commands/update-task.md | command | 65 | No name frontmatter; no empty-input handling |
| packages/claude-code-plugin/commands/next-task.md | command | 66 | No name frontmatter; vague decision tree |
| packages/claude-code-plugin/commands/project-status.md | command | 66 | No name frontmatter; no output format |
| packages/claude-code-plugin/commands/analyze-project.md | command | 66 | No name frontmatter; vague quantifiers |
| packages/claude-code-plugin/commands/auto-implement-tasks.md | command | 66 | No name frontmatter; vague quantifiers |
| packages/claude-code-plugin/commands/list-tasks.md | command | 68 | No name frontmatter; vague "intelligently" |
| packages/claude-code-plugin/commands/add-task.md | command | 68 | No name frontmatter; vague quantifiers |
| packages/claude-code-plugin/commands/to-deferred.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/remove-subtasks.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/remove-dependency.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/remove-subtask.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/complexity-report.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/sync-readme.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/view-models.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/tm-main.md | command | 70 | No name frontmatter; reference doc as command |
| packages/claude-code-plugin/commands/init-project-quick.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/to-cancelled.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/install-taskmaster.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/to-done.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/add-subtask.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/analyze-complexity.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/init-project.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/expand-task.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/fix-dependencies.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/parse-prd-with-research.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/setup-models.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/expand-all-tasks.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/to-pending.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/remove-all-subtasks.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/convert-task-to-subtask.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/remove-task.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/update-single-task.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/to-in-progress.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/parse-prd.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/update-tasks-from-id.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/to-review.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/list-tasks-with-subtasks.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/help.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/quick-install-taskmaster.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/add-dependency.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/validate-dependencies.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/commands/list-tasks-by-status.md | command | 70 | No name frontmatter |
| packages/claude-code-plugin/.claude-plugin/plugin.json | manifest | 75 | Missing version field |
| CLAUDE.md | doc | 78 | Project instructions; not executable artifact |
| .taskmaster/CLAUDE.md | doc | 78 | Project instructions; not executable artifact |
| packages/claude-code-plugin/agents/task-orchestrator.md | agent | 89 | Partial output format; vague quantifiers |
| packages/claude-code-plugin/agents/task-executor.md | agent | 92 | Output format only loosely defined |
| packages/claude-code-plugin/agents/task-checker.md | agent | 96 | Minor vague quantifier ("acceptable") |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 1 |
| Medium | 1 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts (sh/py/js) | 55 (scripts/*.sh, scripts/*.js, scripts/modules/**/*.js) |
| MCP configs | 1 (.mcp.json) |
| Package manifests | 1 (package.json) |
| Requirements.txt | 0 |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Critical | scripts/modules/prompt-manager.js | 280 | eval-new-function | `new Function(...Object.keys(context), \`return ${condition}\`)` executes dynamic code from template config conditions; functionally equivalent to eval() |
| 2 | Critical | packages/claude-code-plugin/commands/install-taskmaster.md | 95 | curl-pipe-sh | `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh \| bash` in a Claude command file Claude will execute as part of the `/taskmaster:install-taskmaster` workflow |
| 3 | High | packages/claude-code-plugin/commands/install-taskmaster.md | 79 | sudo-usage | `sudo npm install -g task-master-ai` in a Claude command file, instructs Claude to run privileged package installation |
| 4 | Medium | .mcp.json | 5 | unpinned-npx | `npx -y task-master-ai` with no version pin; `-y` auto-confirms, allowing any published version of task-master-ai to run without user review |
| 5 | Low | package.json | 63–125 | unpinned-semver | Majority of production dependencies use `^` semver range; includes security-sensitive packages (jsonwebtoken ^9.0.2, undici ^7.16.0, express ^4.21.2) |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | packages/claude-code-plugin/.claude-plugin/plugin.json | Missing `version` field; standard plugin manifests require semantic version | Plugin may fail version-gated install or update checks |
| 2 | .claude/commands/dedupe.md | Has `allowed-tools` and `description` frontmatter but no `name` field | Command name undefined at registration; falls back to filename |
| 3 | .claude/commands/go/pr-comments.md | No frontmatter at all; `$ARGUMENTS` (PR number) is required but no empty-input guard | Silent failure if invoked without PR number |
| 4 | .claude/commands/go/ham.md | No frontmatter; no `allowed-tools` declared | Command runs with default broad permissions |
| 5 | .cursor/commands/goham.md | No frontmatter; no `allowed-tools` declared | Command runs with default broad permissions |
| 6 | packages/claude-code-plugin/commands/* (47 files) | Systemic: no YAML frontmatter `name` field on any plugin command | Plugin registration relies entirely on filename-derived names; formal `name:` field absent in all 47 |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | .mcp.json | `npx -y task-master-ai` with no version pin | Pin to a specific version: `"args": ["-y", "task-master-ai@0.43.1"]` and update with each release |
| 2 | package.json | `jsonwebtoken ^9.0.2` and `undici ^7.16.0` use semver range | Pin exact versions for security-critical packages; use `npm audit` in CI to surface advisories promptly |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | packages/claude-code-plugin/commands/* (47 files) | No `allowed-tools` frontmatter on any plugin command | -5 each |
| 2 | packages/claude-code-plugin/commands/smart-workflow.md | No output format specified; "I'll chain appropriate commands" is vague | -10 (output format), -2 (vague) |
| 3 | packages/claude-code-plugin/commands/command-pipeline.md | No output format specified for pipeline execution result | -10 |
| 4 | packages/claude-code-plugin/commands/project-status.md | No output format; UI mockup shown but not specified as contract | -10 |
| 5 | packages/claude-code-plugin/commands/next-task.md | Output format absent; vague decision tree logic without deterministic steps | -10 |
| 6 | packages/claude-code-plugin/commands/update-task.md | No empty-input handling when $ARGUMENTS is blank | -10 |
| 7 | packages/claude-code-plugin/commands/pr-comments.md | No empty-input handling for required PR number | -10 |
| 8 | packages/claude-code-plugin/commands/show-task.md | Vague quantifiers: "relevant" (-2), "appropriate" (-2) | -4 |
| 9 | packages/claude-code-plugin/commands/analyze-project.md | Vague quantifiers: "relevant" (-2), "appropriate" (-2) | -4 |
| 10 | packages/claude-code-plugin/commands/auto-implement-tasks.md | Vague quantifiers: "comprehensive" (-2), "appropriate" (-2) | -4 |
| 11 | packages/claude-code-plugin/commands/list-tasks.md | Vague quantifier: "intelligently" (-2) | -2 |
| 12 | packages/claude-code-plugin/commands/add-task.md | Vague quantifiers: "intelligently" (-2), "appropriate" (-2) | -4 |
| 13 | packages/claude-code-plugin/commands/smart-workflow.md | Vague quantifier: "appropriate" (-2) | -2 |
| 14 | packages/claude-code-plugin/commands/learn.md | Vague quantifiers: "intelligently" (-2), "appropriate" (-2) | -4 |
| 15 | packages/claude-code-plugin/agents/task-orchestrator.md | Vague quantifiers: "sufficient" (-2), "clear" (-2), "well-defined" (-2) | -6 |
| 16 | packages/claude-code-plugin/agents/task-orchestrator.md | Output format only partially defined (template shown, not prescribed) | -5 |
| 17 | packages/claude-code-plugin/agents/task-executor.md | Output format only loosely described ("briefly summarize") | -5 |
| 18 | packages/claude-code-plugin/agents/task-checker.md | Vague quantifier: "acceptable" in decision criteria | -2 |
| 19 | packages/claude-code-plugin/commands/tm-main.md | File is a reference document masquerading as a command; no executable instructions | informational |
| 20 | tests/unit/scripts/modules/commands/README.md | Pure documentation file with no NL artifact structure | informational |

## Cross-Component
- **`help.md` registry vs. actual commands**: `help.md` lists `/taskmaster:remove-subtasks` (clear-subtasks) and `/taskmaster:remove-all-subtasks` (clear-all-subtasks) but the actual command files are `remove-subtasks.md` and `remove-all-subtasks.md` — name alignment is correct. No broken references detected.
- **`tm-main.md` references `generate-tasks`** as `/taskmaster:generate` → no corresponding `generate-tasks.md` or `generate.md` command file found in the plugin. Broken reference.
- **`goham.md` references `.cursor/rules/hamster.mdc` and `.cursor/rules/git_workflow.mdc`** — these Cursor rule files are external references that may not exist in all deployments; no validation possible without reading those files.
- **`task-orchestrator.md` deploys `task-executor` agents** — the task-executor agent exists and the reference is valid.
- **`task-checker.md` references `mcp__task-master-ai__get_task`** — this MCP tool depends on `.mcp.json` being active; consistent with the `.mcp.json` config found.
- **`install-taskmaster.md` references `/project:utils:check-health`** — no corresponding command file found; broken reference.
- **`learn.md` references `/project:task-master:*` namespace** — these reference a different plugin namespace (`project:task-master`) than the installed namespace (`taskmaster`); all 6 cross-references in `learn.md` use the wrong command prefix.

## Recommendation
BLOCKED — do not submit PRs. Two critical security findings require private disclosure before any public contribution:

1. **`scripts/modules/prompt-manager.js:280`** — `new Function()` with dynamic condition string is eval-equivalent. If `condition` values can be influenced by task data loaded from external sources (e.g., a malicious tasks.json), this is a code injection vector. File a private security report with the maintainer.

2. **`packages/claude-code-plugin/commands/install-taskmaster.md:95`** — `curl | bash` in a Claude command file. When a user invokes `/taskmaster:install-taskmaster`, Claude will offer or execute this command, potentially fetching and running arbitrary shell code from the network. File a private security report.

Once critical findings are resolved, the NL bugs (missing frontmatter across all 47 plugin commands, broken `generate-tasks` reference, wrong namespace in `learn.md`) are straightforward PR targets.
