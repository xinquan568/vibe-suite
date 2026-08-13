# NLPM Audit: AgriciDaniel/claude-obsidian
**Date**: 2026-04-20  |  **Artifacts**: 19  |  **Strategy**: single
**NL Score**: 91/100
**Security**: BLOCKED
**Bugs**: 5  |  **Quality Issues**: 11  |  **Security Findings**: 8

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| commands/autoresearch.md | command | 60 | Missing `name` frontmatter (-25), no allowed-tools (-5), unnumbered multi-step body (-10) |
| commands/save.md | command | 60 | Missing `name` frontmatter (-25), no allowed-tools (-5), unnumbered multi-step body (-10) |
| commands/canvas.md | command | 70 | Missing `name` frontmatter (-25), no allowed-tools (-5) |
| commands/wiki.md | command | 70 | Missing `name` frontmatter (-25), no allowed-tools (-5) |
| skills/wiki-query/SKILL.md | skill | 85 | Write tool used but not declared in allowed-tools (files answers back to wiki) |
| agents/wiki-lint.md | agent | 97 | Bash declared in tools but no bash commands appear in agent body (unused tool) |
| skills/autoresearch/SKILL.md | skill | 98 | Vague quantifier: "major contradictions" (-2) |
| skills/save/SKILL.md | skill | 98 | Vague quantifier: "most valuable content" (-2) |
| skills/wiki-lint/SKILL.md | skill | 98 | Vague quantifier: "significant cross-references" (-2) |
| skills/wiki/SKILL.md | skill | 98 | Vague quantifier: "significant query exchange" (-2) |
| skills/wiki-ingest/SKILL.md | skill | 96 | Vague quantifiers: "significant ideas", "relevant domain" (-4) |
| hooks/hooks.json | config | 90 | Auto-commits .raw/ contents; Stop hook injects instructions via echo |
| agents/wiki-ingest.md | agent | 100 | — |
| .claude-plugin/plugin.json | config | 100 | — |
| CLAUDE.md | docs | 100 | — |
| skills/canvas/SKILL.md | skill | 100 | — |
| skills/defuddle/SKILL.md | skill | 100 | — |
| skills/obsidian-bases/SKILL.md | skill | 100 | — |
| skills/obsidian-markdown/SKILL.md | skill | 100 | — |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 1 |
| Medium | 4 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks (hooks.json) | hooks/hooks.json |
| Scripts | None found |
| MCP configs | None found |
| Package manifests | None found |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | CRITICAL | hooks/hooks.json | 46 | Prompt injection via echo | Stop hook outputs a multi-sentence LLM instruction string via `echo` to command stdout. Claude Code injects command hook output back into the model context. This is a deliberate prompt injection vector: arbitrary instructions written by the plugin author are injected into every session-end context, directing Claude to overwrite wiki/hot.md. An attacker who modifies this hook string can execute arbitrary Claude instructions silently. |
| 2 | CRITICAL | hooks/hooks.json | 9 | File content injection | SessionStart hook runs `cat wiki/hot.md` and injects its raw contents into Claude's context. hot.md is written by Claude and accumulates across sessions. If any ingest source or adversarial web page causes Claude to write malicious instructions into hot.md (indirect prompt injection), those instructions will be re-injected at every session start without user visibility. |
| 3 | HIGH | skills/canvas/SKILL.md | 79 | Command injection via python3 -c | Instructs Claude to build a `python3 -c "...Image.open('[path]')..."` shell string where `[path]` is a user-supplied or URL-derived value. A path containing `'); import os; os.system('...'); #` would execute arbitrary code. No quoting or sanitization is specified. |
| 4 | MEDIUM | skills/canvas/SKILL.md | 71 | SSRF via curl | `curl -sL [url] -o _attachments/images/canvas/[filename]` fetches a user-provided URL to disk. No URL scheme validation specified. An attacker can pass `http://169.254.169.254/` (cloud metadata) or other internal endpoints. Filename is derived from the URL path without sanitization, creating a secondary path traversal risk. |
| 5 | MEDIUM | hooks/hooks.json | 35 | Sensitive file auto-commit | PostToolUse hook runs `git add wiki/ .raw/ && git commit` after every Write/Edit. The `.raw/` folder stores raw source documents which may contain uploaded API keys, credentials, personal documents, or other sensitive material. These are silently staged and committed to version history without per-file review. |
| 6 | MEDIUM | skills/defuddle/SKILL.md | 35 | Path traversal in slug derivation | Shell examples use `$SLUG` derived from URL path without sanitization: `> .raw/articles/$SLUG.md`. A URL with path segments like `../../etc/passwd` or `../../../.env` would write to arbitrary vault locations. No slug sanitization pattern is shown. |
| 7 | MEDIUM | skills/wiki-ingest/SKILL.md | 39 | Unquoted path in shell | Delta tracking instructs `md5sum [file] | cut -d' ' -f1` where `[file]` is a user-provided path. Paths with spaces, semicolons, or backticks are not quoted, enabling command injection or unintended word-splitting in the generated Bash command. |
| 8 | LOW | skills/canvas/SKILL.md | 181 | Predictable /tmp path | Uses a fixed path `/tmp/ten-min-ago` as a reference timestamp file. On a multi-user system this file could be pre-created by another user to manipulate `find -newer` results and cause stale or unexpected image lists. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | commands/autoresearch.md | Missing `name` field in frontmatter | Command cannot register correctly; `/nlpm:ls` will not surface it as a named artifact |
| 2 | commands/canvas.md | Missing `name` field in frontmatter | Command cannot register correctly |
| 3 | commands/save.md | Missing `name` field in frontmatter | Command cannot register correctly |
| 4 | commands/wiki.md | Missing `name` field in frontmatter | Command cannot register correctly |
| 5 | skills/wiki-query/SKILL.md | `Write` not declared in `allowed-tools` but skill writes wiki pages (lines 44, 56, 153) | Claude will lack permission to write files; the "offer to file" feature silently fails |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | hooks/hooks.json | PostToolUse auto-commits `.raw/` — may expose sensitive uploaded documents | Change `git add wiki/ .raw/` to `git add wiki/` only; `.raw/` should not be auto-committed |
| 2 | skills/defuddle/SKILL.md | URL-derived slug used unsanitized in file path | Add slug sanitization: `SLUG=$(echo "$URL_PATH" | sed 's|[^a-zA-Z0-9._-]|-|g' | sed 's|--*|-|g')` |
| 3 | skills/wiki-ingest/SKILL.md | Unquoted path in md5sum | Quote the file argument: `md5sum "[file]" | cut -d' ' -f1` |
| 4 | skills/canvas/SKILL.md | Predictable /tmp path | Use `mktemp` instead of a fixed path: `TMP=$(mktemp); python3 -c "import time,os; os.utime('$TMP',...)"; find ... -newer "$TMP"` |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | agents/wiki-lint.md | `Bash` declared in `tools` but no bash commands appear in the agent body; Grep and Glob cover all lookup needs | -3 (unused tool) |
| 2 | commands/autoresearch.md | Multi-step workflow (read program.md → run loop → update indexes → report) has no numbered steps | -10 |
| 3 | commands/save.md | Multi-step workflow (read skill → run save workflow → update index/log/hot) has no numbered steps | -10 |
| 4 | skills/autoresearch/SKILL.md | "major contradictions" — "major" is an unanchored vague quantifier | -2 |
| 5 | skills/save/SKILL.md | "most valuable content" — undefined selection criterion | -2 |
| 6 | skills/wiki-ingest/SKILL.md | "significant ideas and frameworks" and "relevant domain page" — both unanchored vague quantifiers | -4 |
| 7 | skills/wiki-lint/SKILL.md | "significant cross-references" in canvas map section — vague; also references Dataview (third-party Obsidian plugin) as a dependency without noting installation requirement | -2 |
| 8 | skills/wiki-query/SKILL.md | "If wiki coverage is thin" — "thin" is undefined; no threshold or heuristic given | -0 (minor) |
| 9 | skills/wiki/SKILL.md | Promotional community footer ("Join the AI Marketing Hub") embedded as a mandatory skill output after major operations. Appears as Claude-generated content but promotes the author's paid community. Not a security issue but reduces user trust. | -2 |
| 10 | hooks/hooks.json | `SessionStart` matcher `"startup\|resume"` uses a pipe inside a quoted string — this is a regex OR, which may or may not be supported depending on the hooks matcher implementation. Should be verified. | informational |
| 11 | skills/wiki-lint/SKILL.md | Dataview dashboard queries (lines 103-133) require the Obsidian Dataview community plugin. The skill does not mention this dependency, so lint runs silently produce non-rendering dashboards on vaults without Dataview installed. | informational |

## Cross-Component
**Broken references (unverified):**
- `commands/wiki.md` → `skills/wiki/references/plugins.md`, `references/modes.md`, `references/css-snippets.md`, `references/git-setup.md` — referenced in the wiki skill body but not in the audited file list; existence not confirmed
- `commands/autoresearch.md` → `skills/autoresearch/references/program.md` — referenced as required pre-reading but not in audited scope
- `skills/canvas/SKILL.md` → `references/canvas-spec.md` — required for all canvas edits ("Read canvas-spec.md before editing any canvas JSON") but not in audited scope
- `skills/wiki-ingest/SKILL.md` → `references/frontmatter.md` — required for source frontmatter schema but not in audited scope

**Inconsistency:**
- `agents/wiki-lint.md` declares `tools: Bash` but the corresponding `skills/wiki-lint/SKILL.md` does not include `Bash` in `allowed-tools`. The agent can run bash; the skill reference assumes it cannot.
- `agents/wiki-ingest.md` is described as a "parallel batch ingestion agent" for multiple sources, but `skills/wiki-ingest/SKILL.md` has separate Single Source and Batch Ingest sections. The agent definition does not indicate which mode it runs — this ambiguity could cause the agent to skip batch cross-referencing.

**Orphaned component:**
- `skills/defuddle/SKILL.md` is listed in plugin.json's description context and CLAUDE.md's skill table but is not wired to any command with `allowed-tools` that would permit `Bash`. `defuddle` CLI calls require Bash, which wiki-ingest declares but canvas does not.

## Recommendation

**BLOCKED — do not submit PRs. File private security report.**

Two critical findings require private disclosure before any public PR activity:

1. **hooks/hooks.json lines 9 and 46** — the SessionStart `cat` injection and the Stop `echo` injection are architectural-level prompt injection surfaces. The Stop hook is particularly dangerous because the injected instruction string is a long, specific directive that persists across sessions and is invisible to the user. Recommend: convert both to `prompt`-type hooks (which are visible in the hooks UI and don't execute shell commands) or restrict the cat to a verified-safe path with content sanitization.

2. **skills/canvas/SKILL.md line 79** — the python3 -c command injection pattern requires the skill to be rewritten to use quoted paths and a separate script rather than an inline -c string.

After critical/high findings are resolved via private disclosure and patched releases, the 4 missing `name` frontmatter fields and the `wiki-query` missing `Write` declaration are clean, low-risk PRs suitable for public submission.
