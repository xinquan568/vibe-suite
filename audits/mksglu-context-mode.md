# NLPM Audit: mksglu/context-mode
**Date**: 2026-04-06  |  **Artifacts**: 11  |  **Strategy**: single
**NL Score**: 87/100
**Security**: BLOCKED
**Bugs**: 2  |  **Quality Issues**: 2  |  **Security Findings**: 11

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/context-mode-ops/SKILL.md | Skill | 73 | No example blocks (−15); 8 unverified companion-file cross-refs |
| hooks/hooks.json | Config | 85 | Broad PostToolUse matcher captures all tool calls and arguments |
| CLAUDE.md | Instruction | 88 | Substantially duplicates configs/claude-code/CLAUDE.md (drift risk) |
| skills/context-mode/SKILL.md | Skill | 88 | 4 unverified ./references/ cross-refs; "large" as sole routing criterion |
| skills/ctx-insight/SKILL.md | Skill | 88 | No example blocks |
| skills/ctx-upgrade/SKILL.md | Skill | 88 | Fallback uses literal `<PLUGIN_ROOT>` placeholder without resolution hint |
| .claude-plugin/plugin.json | Manifest | 90 | N/A |
| configs/claude-code/CLAUDE.md | Instruction | 90 | N/A |
| skills/ctx-doctor/SKILL.md | Skill | 90 | N/A |
| skills/ctx-purge/SKILL.md | Skill | 90 | N/A |
| skills/ctx-stats/SKILL.md | Skill | 90 | N/A |

**Weighted average**: (73+85+88+88+88+88+90+90+90+90+90) / 11 = **87/100**

Scoring notes:
- `context-mode-ops/SKILL.md`: −15 (zero examples for an orchestrator skill), −2 ("warm" vague quantifier) = 83 rounded to 73 after −10 cross-reference penalty
- `hooks/hooks.json`: −15 (PostToolUse matcher breadth not documented, privacy implication undisclosed)
- Simple utility skills (ctx-doctor, ctx-purge, ctx-stats, ctx-upgrade, ctx-insight): −10 for absent or minimal examples; remaining deductions for placeholder text

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 5 |
| Low | 4 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks config (NL artifact) | hooks/hooks.json |
| Primary hook scripts | hooks/pretooluse.mjs, hooks/posttooluse.mjs, hooks/sessionstart.mjs, hooks/precompact.mjs, hooks/userpromptsubmit.mjs |
| Shared hook module (auto-imported) | hooks/ensure-deps.mjs |
| Adapter hook scripts | hooks/cursor/*, hooks/codex/*, hooks/gemini-cli/*, hooks/vscode-copilot/*, hooks/jetbrains-copilot/*, hooks/kiro/*, hooks/session-*.bundle.mjs |
| Shell scripts | scripts/ctx-debug.sh, scripts/install-openclaw-plugin.sh |
| Node postinstall | scripts/postinstall.mjs |
| MCP config | .mcp.json |
| Package manifest | package.json |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | High | hooks/ensure-deps.mjs | 57 | subprocess shell=True | `execSync(\`npm install ${pkg}\`, { shell: true })` — `pkg` is hardcoded "better-sqlite3" so no injection today, but `shell: true` with string interpolation is a dangerous pattern that breaks the moment `pkg` becomes dynamic |
| 2 | High | package.json | 95 | postinstall script | `"postinstall": "node scripts/postinstall.mjs"` auto-executes on every `npm install` without user confirmation; grants install-time code execution on end-user machines and is a common supply-chain attack vector |
| 3 | Medium | hooks/ensure-deps.mjs | 57 | runtime package install | `npm install better-sqlite3` is triggered automatically at hook import time when the native binary is absent; runs over network inside the agent event loop with no user visibility or opt-out mechanism |
| 4 | Medium | hooks/pretooluse.mjs | 88 | file writes outside repo | Self-heal block silently writes to `~/.claude/plugins/installed_plugins.json` (line 88) and `~/.claude/settings.json` (line 146) — modifies Claude Code system configuration without notifying the user |
| 5 | Medium | hooks/hooks.json | 6 | excessive hook coverage | PostToolUse matcher `"Bash\|Read\|Write\|Edit\|NotebookEdit\|Glob\|Grep\|TodoWrite\|...\|mcp__"` captures essentially all tool calls; all tool arguments — including file content, code, and user prompts — flow into the local session SQLite DB with no documented retention policy |
| 6 | Medium | scripts/ctx-debug.sh | 155 | shell variable in node -e | `fs.readFileSync('$path','utf8')` interpolates a shell variable directly into a `node -e` string literal; a `$path` value containing a single-quote terminates the JS string and could execute injected code |
| 7 | Medium | scripts/ctx-debug.sh | 980 | outbound network call | Makes HTTPS request to `registry.npmjs.org` during diagnostics; executes automatically without user opt-in, leaking tool version and IP to npm's registry on every diagnostic run |
| 8 | Low | scripts/ctx-debug.sh | 176 | PATH modification | `export NODE_PATH=` permanently modifies `NODE_PATH` in the calling shell session; persists beyond the script and can shadow system modules for subsequent commands |
| 9 | Low | scripts/ctx-debug.sh | 969 | eval with variable | `eval echo "\${$pvar:-}"` uses `eval` for indirect expansion; `$pvar` is from a hardcoded list (safe in practice), but the pattern is fragile if the list ever becomes dynamic |
| 10 | Low | hooks/ensure-deps.mjs | 183 | shell interpolation in execSync | `execSync(\`codesign --sign - --force "${binaryPath}"\`)` — `binaryPath` derives from the plugin directory (controlled), but double-quote quoting in a shell-interpreted string is insufficient protection if the path contains spaces or special characters |
| 11 | Low | package.json | — | unpinned semver | All production dependencies use `^` ranges: `better-sqlite3 ^12.6.2` (native module), `@modelcontextprotocol/sdk ^1.26.0`, `zod ^3.25.0`; native module especially risky — minor updates can introduce ABI breaks or supply-chain compromise |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/context-mode-ops/SKILL.md | 8 relative links to sibling files (`tdd.md`, `validation.md`, `agent-teams.md`, `communication.md`, `marketing.md`, `review-pr.md`, `triage-issue.md`, `release.md`) — none appear in the published plugin artifact list; if absent, every referenced workflow is inaccessible to users | Skill partially non-functional; all workflow-specific instructions become dead links |
| 2 | skills/context-mode/SKILL.md | "Reference Files" section links to `./references/patterns-javascript.md`, `./references/patterns-python.md`, `./references/patterns-shell.md`, `./references/anti-patterns.md` — `./references/` directory not in audit scope; if absent, pattern guidance is entirely inaccessible | Reference section dead for users if companion directory not bundled |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | hooks/ensure-deps.mjs | `execSync` with `shell: true` and string interpolation (lines 57, 133, 156) | Replace with `execFileSync(npmBin, ['install', pkg, '--no-package-lock', '--no-save', '--silent'], {cwd, stdio, timeout})` to eliminate shell parsing |
| 2 | hooks/ensure-deps.mjs | Runtime `npm install` triggered at hook import with no user visibility | Emit a `console.error` diagnostic before install; add `CONTEXT_MODE_NO_AUTO_INSTALL=1` env var to disable the auto-install path |
| 3 | hooks/pretooluse.mjs | Self-heal block silently modifies `~/.claude/settings.json` and `installed_plugins.json` | Emit a `console.error` log line when config files are rewritten; add `CONTEXT_MODE_NO_SELF_HEAL=1` opt-out |
| 4 | scripts/ctx-debug.sh | Shell variable `$path` interpolated into `node -e` JS string (line 155) | Pass path via `process.argv`: `node -e "const p=process.argv[1]; const c=fs.readFileSync(p,'utf8')..." -- "$path"` |
| 5 | scripts/ctx-debug.sh | Outbound network call to npm registry without user consent (line 980) | Gate behind a `--check-updates` flag; document the network call at script start |
| 6 | scripts/ctx-debug.sh | `export NODE_PATH` leaks into caller shell (line 176) | Scope to subshell: `( export NODE_PATH=...; node ... )` |
| 7 | scripts/ctx-debug.sh | `eval` for indirect variable expansion (line 969) | Use Bash indirect expansion `${!pvar:-}` instead |
| 8 | hooks/ensure-deps.mjs | `codesign` path interpolated in shell string (line 183) | Use `execFileSync('codesign', ['--sign', '-', '--force', binaryPath], {stdio, timeout})` |
| 9 | package.json | Unpinned `^` semver for all production deps | Pin `better-sqlite3` to exact version; run `pnpm audit` in CI |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/context-mode-ops/SKILL.md | Zero example blocks for an orchestrator skill that spawns 10–20 agents per task; no sample agent invocation, no sample routing decision, no sample `gh` command output shown | −15 |
| 2 | skills/context-mode-ops/SKILL.md | Vague quantifier "warm" in communication guidance ("be warm, technical, and always put responsibility on contributors") — "warm" is subjective and not actionable for an agent following instructions | −2 |

## Cross-Component
**Content duplication** (`CLAUDE.md` vs `configs/claude-code/CLAUDE.md`): Both files contain the "Think in Code — MANDATORY" block, the "Tool Selection" numbered list, and the "Output" block. `configs/claude-code/CLAUDE.md` is the more complete version (adds Memory, Session Continuity, ctx commands table). When one is updated the other can silently fall behind. Recommend making `configs/claude-code/CLAUDE.md` canonical and having `CLAUDE.md` delegate to it, or merging into a single file.

**Unverified companion files** (`skills/context-mode-ops/SKILL.md`): The skill references 8 sibling markdown files that are not in the audit scope. If these ship with the plugin package, the references are valid. If not, every workflow branch is partially broken. A manifest check in CI (`test -f skills/context-mode-ops/tdd.md` etc.) would catch this before release.

**Unverified reference files** (`skills/context-mode/SKILL.md`): The `./references/` subdirectory with 4 pattern files is not in the audit scope. Same risk as above. Recommend a CI step that validates all relative markdown links resolve.

**hooks.json PostToolUse breadth undocumented**: The extremely broad PostToolUse matcher (all major tool types) captures sensitive data (file contents written via Write, user prompts via UserPromptSubmit) and stores it in a local SQLite DB. No privacy disclosure or retention policy is described anywhere in the audited NL artifacts. Users should be informed what is captured and why.

## Recommendation
BLOCKED — do not submit PRs. File private security report.

Two HIGH findings require private disclosure before any PR activity:

1. **ensure-deps.mjs `shell: true` with interpolation** (Finding #1): Pattern match for subprocess shell injection. `pkg` is currently hardcoded so no immediate exploit exists, but the pattern is a latent vulnerability that should be remediated before external contributors extend the code.

2. **package.json postinstall** (Finding #2): Auto-executes `scripts/postinstall.mjs` on every `npm install`. The script is benign (Windows symlink fix), but the surface grants install-time code execution and is a known supply-chain attack vector. A security reviewer must explicitly clear this before the pipeline contributes to the repo.

After security clearance, the recommended PR sequence:
1. Submit Bug #1 and #2 (broken companion-file references) as separate focused PRs — these are safe and clear
2. Submit Security Fixes #1–#9 (Medium/Low mitigations) as a single hardening PR
3. Hold the HIGH findings for the private disclosure thread
