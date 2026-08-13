# NLPM Audit: mbruhler/claude-orchestration
**Date**: 2026-04-06  |  **Artifacts**: 22  |  **Strategy**: batched
**NL Score**: 82/100
**Security**: CLEAR
**Bugs**: 5  |  **Quality Issues**: 24  |  **Security Findings**: 3

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| commands/pull.md | Command | 58 | Missing name (-25), no allowed-tools (-5), no empty-input handling (-10) |
| commands/template.md | Command | 61 | Missing name (-25), no allowed-tools (-5), partial empty-input handling (-5), vague (-4) |
| commands/menu.md | Command | 64 | Missing name (-25), no allowed-tools (-5), vague language (-6) |
| commands/explain.md | Command | 66 | Missing name (-25), no allowed-tools (-5), vague language (-4) |
| commands/examples.md | Command | 68 | Missing name (-25), no allowed-tools (-5), vague language (-2) |
| commands/run.md | Command | 68 | Missing name (-25), no allowed-tools (-5), vague (-2); deprecated |
| commands/init.md | Command | 70 | Missing name (-25), no allowed-tools (-5) |
| commands/orchestrate.md | Command | 70 | Missing name (-25), no allowed-tools (-5) |
| commands/help.md | Command | 70 | Missing name (-25), no allowed-tools (-5) |
| commands/create.md | Command | 70 | Missing name (-25), no allowed-tools (-5); deprecated |
| agents/workflow-socratic-designer.md | Agent | 73 | Write tool called but undeclared (-10), no model (-5), no output format section (-5), AskUserQuestion undeclared (-3) |
| commands/orchestrate.md | Command | 70 | Missing name (-25), no allowed-tools (-5) |
| agents/workflow-syntax-designer.md | Agent | 89 | No model declared (-5), vague language (-6) |
| commands/examples.md | Command | 68 | Missing name, no allowed-tools, deprecated |
| skills/executing-workflows/SKILL.md | Skill | 96 | Broken examples/ sub-links, vague (-4) |
| skills/managing-agents/SKILL.md | Skill | 96 | Vague "appropriate tools" and "comprehensive" (-4) |
| skills/designing-syntax/SKILL.md | Skill | 96 | Vague "intuitive" and "truly needed" (-4) |
| skills/managing-temp-scripts/SKILL.md | Skill | 96 | Vague "complex" and "restrictive" (-4) |
| skills/creating-workflows/SKILL.md | Skill | 96 | Vague "complex" and "proactively" (-4) |
| skills/using-orchestration/SKILL.md | Skill | 98 | Vague "relevant syntax" (-2) |
| skills/creating-workflows-from-description/SKILL.md | Skill | 98 | Vague "relevant example" (-2) |
| skills/debugging-workflows/SKILL.md | Skill | 100 | Clean |
| skills/using-templates/SKILL.md | Skill | 100 | Clean |
| .claude-plugin/plugin.json | Manifest | 100 | Clean |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | None |
| Scripts | None |
| MCP Configs | None |
| Package Manifests | None |
| Bash patterns in commands | commands/pull.md (curl), commands/run.md (rm cleanup) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | commands/pull.md | 38 | unsanitized-path | User-supplied workflow name used unsanitized in `curl -o "./examples/<workflow-name>.flow"` — path traversal possible if name contains `../` segments |
| 2 | Medium | skills/managing-temp-scripts/SKILL.md | 163 | runtime-package-install | Skill instructs `pip install` and `npm install` patterns driven by workflow variables; packages execute in user's environment with no version pinning requirement shown |
| 3 | Low | commands/run.md | 547 | rm-glob | `rm -rf ./temp-scripts/*` and `rm -f ./temp-agents/*.md` in cleanup phase; blast radius is limited to local temp dirs and gated by user confirmation, but unconditional glob delete is worth noting |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | agents/workflow-socratic-designer.md | `Write` tool called at line 294 (`Write({file_path: ...})`) but not declared in `tools: [Read, Grep, Task]` | Agent will fail at runtime when attempting to create temp-agent files |
| 2 | agents/workflow-socratic-designer.md | `AskUserQuestion` used as the primary interaction tool throughout but absent from `tools` list | Agent may lose access to its core interaction mechanism if tool list is enforced |
| 3 | agents/workflow-socratic-designer.md | Absolute hardcoded path `/Users/mbroler/.claude/plugins/repos/orchestration/docs/TEMP-SCRIPTS-DETECTION-GUIDE.md` at line 329 — includes author's username and file does not exist in the repo | Instruction is dead on every non-author machine; file is entirely absent from the repository |
| 4 | skills/creating-workflows/SKILL.md | References `docs/TEMP-SCRIPTS-DETECTION-GUIDE.md` (line 222) — this file does not exist anywhere in the repo | Guide link silently fails; temp-script detection guidance is unavailable |
| 5 | skills/executing-workflows/SKILL.md | References five files under `examples/` sub-directory (sequential.md, parallel.md, conditional.md, error-handling.md, checkpoints.md) that do not exist — the `examples/` directory inside `skills/executing-workflows/` is missing entirely | All five "See examples" cross-references are broken dead links |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | commands/pull.md | Workflow name from user arg used as-is in curl output path | Sanitize the filename: strip any leading `../`, reject names containing `/` after splitting, or use `basename` to extract only the final path component |
| 2 | skills/managing-temp-scripts/SKILL.md | Runtime `pip install` and `npm install` patterns with unspecified version constraints | Add a note in the security section to use pinned versions in `requirements.txt` / `package.json` and run installs inside a venv or isolated `node_modules` directory |
| 3 | commands/run.md | `rm -rf ./temp-scripts/*` glob delete in cleanup | Already gated by user confirmation; add a sanity check that the paths are within the current working directory before execution |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | commands/run.md | Missing `name` frontmatter field (all 10 commands share this pattern — likely intentional convention, but reduces AI discoverability) | -25 |
| 2 | commands/pull.md | Missing `name` frontmatter field | -25 |
| 3 | commands/init.md | Missing `name` frontmatter field | -25 |
| 4 | commands/template.md | Missing `name` frontmatter field | -25 |
| 5 | commands/examples.md | Missing `name` frontmatter field | -25 |
| 6 | commands/orchestrate.md | Missing `name` frontmatter field | -25 |
| 7 | commands/help.md | Missing `name` frontmatter field | -25 |
| 8 | commands/explain.md | Missing `name` frontmatter field | -25 |
| 9 | commands/menu.md | Missing `name` frontmatter field | -25 |
| 10 | commands/create.md | Missing `name` frontmatter field | -25 |
| 11 | All 10 commands | Missing `allowed-tools` frontmatter field (tools used: AskUserQuestion, Task, Bash, Glob, Read, Write) | -5 each |
| 12 | agents/workflow-socratic-designer.md | No `model` field declared | -5 |
| 13 | agents/workflow-syntax-designer.md | No `model` field declared | -5 |
| 14 | agents/workflow-socratic-designer.md | No dedicated `## Output` section; output format described inline across process steps | -5 |
| 15 | agents/workflow-socratic-designer.md | Vague "comprehensive prompt" (line 199) | -2 |
| 16 | agents/workflow-socratic-designer.md | Vague "Be thorough" (line 272) | -2 |
| 17 | agents/workflow-syntax-designer.md | Vague "intuitive" (line 201), "clearly" (line 54), "comprehensive documentation" (line 64) | -6 |
| 18 | skills/managing-agents/SKILL.md | Vague "Make prompts comprehensive and specific" (line 290), "Recommend appropriate tools" (line 292) | -4 |
| 19 | skills/executing-workflows/SKILL.md | Vague "gracefully" (line 36), "critical steps" (line 399) | -4 |
| 20 | skills/designing-syntax/SKILL.md | Vague "Intuitive" (line 27), "truly needed" (line 103) | -4 |
| 21 | skills/managing-temp-scripts/SKILL.md | Vague "complex" (line 14), "restrictive file permissions" (line 437) | -4 |
| 22 | skills/creating-workflows/SKILL.md | Vague "complex" (line 3), "proactively" (line 35) | -4 |
| 23 | skills/using-orchestration/SKILL.md | Vague "relevant syntax" (line 59) | -2 |
| 24 | skills/creating-workflows-from-description/SKILL.md | Vague "relevant example" (line 70) | -2 |

## Cross-Component

**Broken reference — machine-specific path**: `agents/workflow-socratic-designer.md` at line 329 embeds `/Users/mbroler/.claude/plugins/repos/orchestration/...` — an absolute path containing the author's macOS username. This path doesn't resolve on any other machine and the referenced file (`TEMP-SCRIPTS-DETECTION-GUIDE.md`) doesn't exist in the repo at all. The same guide is referenced more portably in `skills/creating-workflows/SKILL.md` at line 222 using a relative `docs/` path, but that file is also missing. Both references need the file created or the references removed.

**Missing examples sub-directory**: `skills/executing-workflows/SKILL.md` links to `examples/sequential.md`, `examples/parallel.md`, `examples/conditional.md`, `examples/error-handling.md`, and `examples/checkpoints.md`. The `skills/executing-workflows/examples/` directory does not exist. The five linked files are all absent.

**Deprecated commands in active help**: `commands/help.md` lists `/orchestration:run`, `/orchestration:template`, `/orchestration:examples`, and `/orchestration:explain` in its quick-reference panel without marking them as deprecated. Users following the help output will invoke deprecated commands. The help should either remove deprecated entries or annotate them `(deprecated)`.

**Namespace inconsistency in skill names**: `skills/executing-workflows/SKILL.md` and `skills/creating-workflows/SKILL.md` declare `name: orchestration:executing-workflows` and `name: orchestration:creating-workflows` (with namespace prefix). All other skills omit the namespace in their `name` field. This is an inconsistency — either all skill names should include the namespace or none should.

**Command routing gap in orchestrate.md**: `commands/orchestrate.md` routes to `/orchestration:examples`, `/orchestration:template`, `/orchestration:run`, and `/orchestration:explain` — four of which are deprecated. The router's fallback logic still works but actively directs users into deprecated code paths.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

Priority order:
1. **Bug #1** (`workflow-socratic-designer.md` undeclared Write tool) — runtime failure risk
2. **Bug #3 + #4** (missing `TEMP-SCRIPTS-DETECTION-GUIDE.md`) — create the file or remove dead references
3. **Bug #5** (missing `examples/` in executing-workflows) — create stub files or remove broken links
4. **Security #1** (unsanitized filename in pull.md curl command) — sanitize before shipping
5. **Quality** (missing `name` and `allowed-tools` in all commands) — low friction, high discoverability gain
