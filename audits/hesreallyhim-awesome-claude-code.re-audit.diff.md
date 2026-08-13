# Re-Audit: hesreallyhim/awesome-claude-code

**Date**: 2026-04-24  |  **Before**: `unknown` (89/100)  |  **After**: `672a061` (97/100)

## Summary

| Outcome | Count |
|---------|------:|
| fixed — upstream, not via our PR | 21 |
| newly introduced (regressions) | 15 |

## Original findings — verification

| # | File | Line | Rule | Pattern | Outcome | PR |
|---|------|------|------|---------|---------|----|
| 1 | `.claude/commands/evaluate-repository.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — upstream, not via our PR |  |
| 2 | `.claude/commands/evaluate-repository.md` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 3 | `resources/claude.md-files/DroidconKotlin/CLAUDE.md` | — | BUG-ephemeral-context | `ephemeral-claude-md` | fixed — upstream, not via our PR |  |
| 4 | `resources/claude.md-files/Cursor-Tools/CLAUDE.md` | 55 | BUG-invalid-frontmatter | `malformed-frontmatter` | fixed — upstream, not via our PR |  |
| 5 | `scripts/resources/download_resources.py` | — | SEC-unknown | `path-from-api-response-written-without-t` | fixed — upstream, not via our PR |  |
| 6 | `scripts/ (all)` | — | SEC-unknown | `no-pinned-dependency-manifest` | fixed — upstream, not via our PR |  |
| 7 | `scripts/ticker/generate_ticker_svg.py` | — | SEC-unknown | `post-destination-not-visible-potentially` | fixed — upstream, not via our PR |  |
| 8 | `.claude/commands/evaluate-repository.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 9 | `resources/claude.md-files/Network-Chronicles/CLAUDE.md` | — | UNCLASSIFIED | `extensive-implementation-plan-notes-mixe` | fixed — upstream, not via our PR |  |
| 10 | `resources/claude.md-files/Network-Chronicles/CLAUDE.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 11 | `resources/claude.md-files/Note-Companion/CLAUDE.md` | — | UNCLASSIFIED | `file-covers-styling-and-audio-only-missi` | fixed — upstream, not via our PR |  |
| 12 | `resources/claude.md-files/AVS-Vibe-Developer-Guide/CLAUDE.md` | — | R09 | `no-examples` | fixed — upstream, not via our PR |  |
| 13 | `resources/claude.md-files/claude-code-mcp-enhanced/CLAUDE.md` | — | BUG-instruction-override | `instruction-override` | fixed — upstream, not via our PR |  |
| 14 | `resources/claude.md-files/Cursor-Tools/CLAUDE.md` | — | UNCLASSIFIED | `don-t-ask-me-for-permission-to-do-stuff` | fixed — upstream, not via our PR |  |
| 15 | `resources/claude.md-files/SG-Cars-Trends-Backend/CLAUDE.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 16 | `resources/claude.md-files/Giselle/CLAUDE.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 17 | `resources/claude.md-files/JSBeeb/CLAUDE.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 18 | `resources/claude.md-files/Pareto-Mac/CLAUDE.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 19 | `resources/claude.md-files/AWS-MCP-Server/CLAUDE.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 20 | `resources/claude.md-files/Basic-Memory/CLAUDE.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 21 | `resources/claude.md-files/Course-Builder/CLAUDE.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |

## Findings introduced since audit

These findings appear in the re-audit but were not in the original audit. They may be true regressions (new commits introduced them) or artifacts of scoring drift.

| # | File | Line | Rule | Pattern | Description |
|---|------|------|------|---------|-------------|
| 1 | `.claude/commands/evaluate-repository.md` | — | BUG-missing-frontmatter | `missing-frontmatter-name` | Command file has no YAML frontmatter block; `name:` field is absent, preventing discoverability in /help and command picker |
| 2 | `.claude/commands/evaluate-repository.md` | — | BUG-missing-frontmatter | `missing-frontmatter-description` | Command file has no YAML frontmatter block; `description:` field is absent, hiding command purpose from users and IDE integrations |
| 3 | `.claude/commands/evaluate-repository.md` | — | BUG-missing-frontmatter | `missing-allowed-tools` | Command file declares no `allowed-tools:` field; Claude Code cannot enforce tool restrictions during repository evaluation |
| 4 | `resources/claude.md-files/Cursor-Tools/CLAUDE.md` | 64 | BUG-malformed-syntax | `embedded-cursor-rules-frontmatter` | Cursor Rules YAML frontmatter fragments (--- description: Global Rule... globs: *,**/*) embedded at lines 64-73 inside body prose, malformed for both CLAUDE.md and Cursor Rules parsers |
| 5 | `resources/claude.md-files/Lamoom-Python/CLAUDE.md` | 24 | R01 | `vague-quantifier-appropriate` | Vague quantifier `appropriate` in: 'Use the logging module with appropriate levels' |
| 6 | `resources/claude.md-files/AVS-Vibe-Developer-Guide/CLAUDE.md` | 22 | R01 | `vague-quantifier-appropriate` | Vague quantifier `appropriately` in: 'Benchmark examples should be placed in appropriately named subdirectories' |
| 7 | `resources/claude.md-files/Cursor-Tools/CLAUDE.md` | 79 | R01 | `vague-quantifier-relevant` | Vague quantifier `relevant` in: 'Identify relevant files in your codebase (using Gemini by default)' |
| 8 | `resources/claude.md-files/Cursor-Tools/CLAUDE.md` | 121 | R01 | `vague-quantifier-sufficient` | Vague quantifier `sufficient` in: 'The query must include sufficient information for vibe-tools to determine which server to use' |
| 9 | `resources/claude.md-files/SG-Cars-Trends-Backend/CLAUDE.md` | — | R01 | `vague-quantifier-appropriate` | Vague quantifier `appropriate` in: 'Use mock data where appropriate, avoid hitting real APIs in tests' |
| 10 | `resources/claude.md-files/Network-Chronicles/CLAUDE.md` | 33 | R01 | `vague-quantifier-appropriate` | Vague quantifier `appropriate` in: 'Generates appropriate XP rewards and notifications for discoveries' |
| 11 | `resources/claude.md-files/AWS-MCP-Server/CLAUDE.md` | 73 | R01 | `vague-quantifier-appropriate` | Vague quantifier `appropriate` in: 'Implement appropriate logging levels (debug, info, error)' |
| 12 | `resources/claude.md-files/Pareto-Mac/CLAUDE.md` | 49 | R01 | `vague-quantifier-appropriate` | Vague quantifier `appropriate` in: 'Use os_log for logging, with appropriate log levels' |
| 13 | `resources/claude.md-files/Basic-Memory/CLAUDE.md` | — | R01 | `vague-quantifier-relevant` | Vague quantifier `relevant` in: 'Continue previous conversations with relevant historical context' |
| 14 | `resources/claude.md-files/SG-Cars-Trends-Backend/CLAUDE.md` | — | CC-broken-relative-path | `unverifiable-sub-file-reference` | File references apps/api/CLAUDE.md, apps/web/CLAUDE.md, packages/database/CLAUDE.md, and infra/CLAUDE.md as sub-guides; these were not included in the audit set so their existence in the target repo cannot be confirmed |
| 15 | `resources/claude.md-files/Cursor-Tools/CLAUDE.md` | — | CC-broken-relative-path | `runtime-artifact-reference` | File cites node_modules/vibe-tools/README.md and vibe-tools.config.json as authoritative documentation; these are runtime artifacts absent from the repository root |

