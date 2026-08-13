# NLPM Audit: Lum1104/Understand-Anything
**Date**: 2026-04-06  |  **Artifacts**: 20  |  **Strategy**: single
**NL Score**: 86/100
**Security**: CLEAR
**Bugs**: 1  |  **Quality Issues**: 21  |  **Security Findings**: 4

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| agents/knowledge-graph-guide.md | Agent | 75 | No invocation examples (-15), no output format (-10) |
| agents/tour-builder.md | Agent | 77 | No invocation examples (-15), four vague quantifiers (-8) |
| agents/graph-reviewer.md | Agent | 79 | No invocation examples (-15), three vague quantifiers (-6) |
| agents/file-analyzer.md | Agent | 81 | No invocation examples (-15), "significant"/"notable" vague (-4) |
| agents/article-analyzer.md | Agent | 83 | No invocation examples (-15), "relevant" vague (-2) |
| agents/assemble-reviewer.md | Agent | 83 | No invocation examples (-15), "sensible defaults" vague (-2) |
| agents/domain-analyzer.md | Agent | 83 | No invocation examples (-15), "relevant" vague (-2) |
| CLAUDE.md | Doc | 85 | Developer docs; NL structure not required |
| agents/architecture-analyzer.md | Agent | 85 | No invocation examples (-15) |
| agents/project-scanner.md | Agent | 85 | No invocation examples (-15) |
| hooks/hooks.json | Config | 85 | `${PLUGIN_DIR}` in single-quoted echo (functional bug) |
| skills/understand-onboard/SKILL.md | Skill | 89 | No examples (-5), three vague quantifiers (-6) |
| .claude-plugin/plugin.json | Manifest | 90 | Complete manifest; no NL-specific gaps |
| skills/understand-diff/SKILL.md | Skill | 91 | No examples (-5), two vague quantifiers (-4) |
| skills/understand-explain/SKILL.md | Skill | 91 | No examples (-5), two vague quantifiers (-4) |
| skills/understand/SKILL.md | Skill | 91 | No examples (-5), two vague quantifiers (-4) |
| skills/understand-chat/SKILL.md | Skill | 93 | No examples (-5), "concise but thorough" (-2) |
| skills/understand-dashboard/SKILL.md | Skill | 93 | No examples (-5), "if needed" vague (-2) |
| skills/understand-knowledge/SKILL.md | Skill | 93 | No examples (-5), "solid" vague (-2) |
| skills/understand-domain/SKILL.md | Skill | 95 | No examples (-5) |

**Weighted average**: (75+77+79+81+83+83+83+85+85+85+85+89+90+91+91+91+93+93+93+95) / 20 = **86/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | `understand-anything-plugin/hooks/hooks.json` (2 hooks: PostToolUse/Bash, SessionStart) |
| Scripts (Python) | `skills/understand/merge-batch-graphs.py`, `skills/understand/merge-subdomain-graphs.py`, `skills/understand-domain/extract-domain-context.py`, `skills/understand-knowledge/parse-knowledge-base.py`, `skills/understand-knowledge/merge-knowledge-graph.py` |
| Scripts (JS/MJS) | `scripts/generate-large-graph.mjs` |
| MCP configs | None |
| Package manifests | `package.json` (no `postinstall` script; only `prepare`, `build`, `test`, `dev:dashboard`, `lint`) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | `hooks/hooks.json` | 9 | Tool input piped to shell | `echo "$TOOL_INPUT" \| grep -qE '...'` pipes raw hook event JSON into a grep invocation. The data is used only for pattern matching (not execution) and the regex is fixed, so there is no code injection vector. Flagged as medium for defense-in-depth; input validation is not present. |
| 2 | Medium | `skills/understand-dashboard/SKILL.md` | 49, 57 | Runtime package install / dev server | Skill instructs Claude to run `pnpm install` (network package download) and `npx vite --host 127.0.0.1 --open` (local dev server, auto-opens browser). Expected functionality for a dashboard tool, but represents a supply-chain dependency surface. |
| 3 | Low | `hooks/hooks.json` | 19 | Inline Node.js eval | `node -p "JSON.parse(require('fs').readFileSync(...))"` evaluates an inline Node.js expression. The file path is hardcoded (`.understand-anything/meta.json`); no user-controlled input reaches `eval`. Risk is limited but non-zero if the meta.json path is symlinked externally. |
| 4 | Low | `skills/understand-domain/extract-domain-context.py` | 128–137 | User-controlled regex construction | `parse_gitignore()` reads `.gitignore` and converts patterns to compiled regexes. A malformed regex triggers a `re.error` that is caught and silently skipped. No execution risk; patterns used only for path matching. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `hooks/hooks.json` lines 9, 19 | `${PLUGIN_DIR}` appears inside single-quoted bash strings in both the PostToolUse and SessionStart hooks. Single quotes suppress variable expansion in bash, so Claude receives the literal text `${PLUGIN_DIR}/hooks/auto-update-prompt.md` instead of the resolved path. If the Claude Code hook runner does not pre-expand `${PLUGIN_DIR}` before handing the command to bash, the auto-update advisory message will point to a non-existent path and Claude cannot execute the auto-update instructions. | Auto-update feature silently broken when Claude cannot locate the prompt file. Fix: change single quotes to double quotes around the echo argument, or verify Claude Code expands plugin variables before bash sees the command. |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `hooks/hooks.json:9` | `echo "$TOOL_INPUT"` introduces unvalidated tool event data into a shell pipeline | Wrap in a shell function that explicitly sanitizes or length-limits the input before grep, or use `printf '%s' "$TOOL_INPUT"` to avoid potential echo interpretation of special characters. Risk is low but easy to harden. |
| 2 | `skills/understand-domain/extract-domain-context.py:128–137` | Silent swallowing of `re.error` in gitignore parser | Log skipped invalid patterns to stderr (e.g., `print(f"Warning: skipping invalid gitignore pattern '{line}': {e}", file=sys.stderr)`) so users can diagnose unexpected exclusion behavior. |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | agents/architecture-analyzer.md | No invocation examples (zero `## Example` blocks showing agent called with sample input/output) | -15 |
| 2 | agents/article-analyzer.md | No invocation examples | -15 |
| 3 | agents/assemble-reviewer.md | No invocation examples | -15 |
| 4 | agents/domain-analyzer.md | No invocation examples | -15 |
| 5 | agents/file-analyzer.md | No invocation examples | -15 |
| 6 | agents/graph-reviewer.md | No invocation examples | -15 |
| 7 | agents/knowledge-graph-guide.md | No invocation examples | -15 |
| 8 | agents/project-scanner.md | No invocation examples | -15 |
| 9 | agents/tour-builder.md | No invocation examples | -15 |
| 10 | agents/knowledge-graph-guide.md | No output format defined (conversational guide agent with no schema or structure specified for responses) | -10 |
| 11 | agents/graph-reviewer.md | Vague quantifiers: "sane" (step 1), "reasonable" (step 1), "sensible" (step 2) | -6 |
| 12 | agents/tour-builder.md | Vague quantifiers: "most important and illustrative", "genuinely educational", "notable", "meaningful" | -8 |
| 13 | agents/file-analyzer.md | Vague quantifiers: "significant" (step 2 filter), "notable" (languageNotes guidance) | -4 |
| 14 | agents/article-analyzer.md | Vague quantifier: "relevant" in "plus any relevant category" | -2 |
| 15 | agents/assemble-reviewer.md | Vague quantifier: "sensible defaults" in node recovery step | -2 |
| 16 | agents/domain-analyzer.md | Vague quantifier: "relevant" in tags field guidance | -2 |
| 17 | skills/understand-onboard/SKILL.md | Vague quantifiers: "comprehensive" (description), "key files" (used three times), "carefully" | -6 |
| 18 | skills/understand-diff/SKILL.md | Vague quantifiers: "potential issues", "carefully" | -4 |
| 19 | skills/understand-explain/SKILL.md | Vague quantifiers: "thorough" (description), "clearly" in step 7 | -4 |
| 20 | skills/understand/SKILL.md | Vague quantifiers: "appropriate" (layer assignment context), "relevant" | -4 |
| 21 | skills/understand-chat/SKILL.md | No empty-argument handling: step 3 passes `"$ARGUMENTS"` directly to grep; empty invocation matches every node and floods context | -2 |

## Cross-Component
**References verified ✅:**
- `understand/SKILL.md` dispatches `project-scanner`, `file-analyzer`, `architecture-analyzer`, `assemble-reviewer`, `tour-builder`, `graph-reviewer` — all agents exist
- `understand-domain/SKILL.md` dispatches `domain-analyzer` — exists
- `understand-knowledge/SKILL.md` dispatches `article-analyzer` — exists
- `understand-domain/SKILL.md` uses `extract-domain-context.py` — exists at `skills/understand-domain/`
- `understand/SKILL.md` uses `merge-batch-graphs.py`, `merge-subdomain-graphs.py` — both exist at `skills/understand/`
- `understand-knowledge/SKILL.md` uses `parse-knowledge-base.py`, `merge-knowledge-graph.py` — both exist at `skills/understand-knowledge/`
- Both hooks reference `${PLUGIN_DIR}/hooks/auto-update-prompt.md` — file exists at `hooks/auto-update-prompt.md`

**Unverified references (not in audit scope):**
- `understand/SKILL.md` Phase 4 reads `./languages/<language-id>.md` and `./frameworks/<framework-id-lowercase>.md` — these subdirectories were not included in the audit file list; their existence is unconfirmed

**Potential consistency gap:**
- `understand-chat/SKILL.md` lists node types as `file, function, class, module, concept` (5 types), but the full schema in `understand/SKILL.md` defines 13 structural node types plus 3 domain types. The chat skill's Graph Structure Reference section is an abbreviated subset that may mislead users querying for `config`, `document`, `service`, etc. nodes. Same gap exists in `understand-diff`, `understand-explain`, and `understand-onboard` which all copy the same abbreviated node type list.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

**Priority order:**
1. **Bug fix (high value):** Fix `${PLUGIN_DIR}` single-quote expansion in `hooks/hooks.json` — one-line change that unblocks the auto-update feature
2. **Quality (systematic):** Add `## Example` blocks to all 9 agents — the biggest score gap (15 points each); even one worked example per agent would recover 10 points
3. **Quality (quick wins):** Add empty-argument guard to `understand-chat` (check `$ARGUMENTS` is non-empty before grep); update abbreviated node-type lists in `understand-chat`, `understand-diff`, `understand-explain`, `understand-onboard` to match the full 13-type schema
4. **Security (low effort):** Add a stderr log line in `extract-domain-context.py` for skipped gitignore patterns
