# NLPM Audit: aaronmaturen/claude-plugin
**Date**: 2026-04-29  |  **Artifacts**: 30  |  **Strategy**: complete
**NL Score**: 36/100
**Security**: REVIEW
**Bugs**: 2  |  **Quality Issues**: 6  |  **Security Findings**: 3 (2 false positives)

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| commands/spike-investigation.md | command | 15 | Missing frontmatter (name, description); no empty-input guard (-10); vague quantifiers ≥10 (cap -20) |
| commands/feature-investigation.md | command | 19 | Missing frontmatter; no empty-input guard (-10); 8 vague quantifiers (-16) |
| commands/a11y-audit.md | command | 25 | Missing frontmatter; vague quantifiers ≥10 (cap -20) |
| commands/ai-agent-audit.md | command | 25 | Missing frontmatter; vague quantifiers ≥10 (cap -20) |
| commands/a11y-expert.md | command | 25 | Missing frontmatter; no numbered steps (-10); 5 vague quantifiers (-10) |
| commands/angular-architecture-audit.md | command | 25 | Missing frontmatter; vague quantifiers ≥10 (cap -20) |
| commands/angular-expert.md | command | 25 | Missing frontmatter; no numbered steps (-10); 5 vague quantifiers (-10) |
| commands/angular-performance-audit.md | command | 25 | Missing frontmatter; vague quantifiers ≥10 (cap -20) |
| commands/angular-style-audit.md | command | 25 | Missing frontmatter; vague quantifiers ≥10 (cap -20) |
| commands/django-api-audit.md | command | 25 | Missing frontmatter; vague quantifiers ≥10 (cap -20) |
| commands/django-model-audit.md | command | 25 | Missing frontmatter; vague quantifiers ≥10 (cap -20) |
| commands/git-revise-history.md | command | 25 | Missing frontmatter; vague quantifiers ≥10 (cap -20) |
| commands/implement-pr-feedback.md | command | 25 | Missing frontmatter; no empty-input guard (-10); 5 vague quantifiers (-10) |
| commands/pr-review.md | command | 25 | Missing frontmatter; no empty-input guard (-10); 5 vague quantifiers (-10) |
| commands/problem-solver.md | command | 25 | Missing frontmatter; no empty-input guard (-10); 5 vague quantifiers (-10) |
| commands/release-architect.md | command | 25 | Missing frontmatter; no empty-input guard (-10); 5 vague quantifiers (-10) |
| commands/bug-investigation.md | command | 29 | Missing frontmatter; 8 vague quantifiers (-16) |
| commands/django-expert.md | command | 29 | Missing frontmatter; no numbered steps (-10); 3 vague quantifiers (-6) |
| commands/simplify.md | command | 29 | Missing frontmatter; 8 vague quantifiers (-16) |
| commands/self-review.md | command | 31 | Missing frontmatter; 7 vague quantifiers (-14) |
| commands/summarize-branch.md | command | 31 | Missing frontmatter; 7 vague quantifiers (-14) |
| commands/django-security-audit.md | command | 35 | Missing frontmatter; 5 vague quantifiers (-10) |
| commands/generate-slidedeck.md | command | 35 | Missing frontmatter; 5 vague quantifiers (-10) |
| commands/scaffold.md | command | 35 | Missing frontmatter; 5 vague quantifiers (-10) |
| commands/ticket-explainer.md | command | 35 | Missing frontmatter; 5 vague quantifiers (-10) |
| commands/commit-msg.md | command | 41 | Missing frontmatter; 2 vague quantifiers (-4); pbcopy macOS-only |
| .claude/skills/ai/SKILL.md | skill | 84 | 8 vague quantifiers: effective, specific, appropriate, focused, relevant, clear, good, proper (-16) |
| .claude/skills/bash/SKILL.md | skill | 88 | 6 vague quantifiers: Always×3, graceful, informative, standard (-12) |
| CLAUDE.md | config | 95 | Redirect-only file; no direct documentation |
| .claude-plugin/plugin.json | manifest | 96 | 2 vague words in description (Professional, comprehensive) |

**Mean**: 36/100  |  **Median**: 29/100  |  **Range**: 15–96

## Security Scan

All 30 artifacts scanned for executable surfaces. Surfaces found: MCP server config in `.claude-plugin/plugin.json`; Python subprocess execution in `commands/git-revise-history.md`; shell path arguments in 6 audit commands.

| Finding | File | Severity | Pattern | Confirmed |
|---------|------|----------|---------|-----------|
| Python script written to `/tmp/claude-filter.py` and executed via subprocess in `git filter-repo` callback | commands/git-revise-history.md | HIGH | tmp-script-exec | **False positive** — Claude's exec context already has user-level filesystem access; no privilege escalation vector |
| `APP_PATH="$arg"` from `$ARGUMENTS` passed to `grep` without path sanitization (also in angular-architecture-audit, angular-performance-audit, angular-style-audit, django-api-audit, django-model-audit) | commands/a11y-audit.md | HIGH | unvalidated-path-arg | **False positive** — grep runs inside the user's own checked-out repository; no cross-user or privilege boundary exists |
| `"args": ["-y", "@upstash/context7-mcp"]` installs an unpinned npm package at each MCP server start | .claude-plugin/plugin.json | MEDIUM | npx-dash-y | **Confirmed** — supply-chain risk; any future semver-incompatible or malicious publish of `@upstash/context7-mcp` will silently affect all users of this plugin |

## Bugs

| ID | File(s) | Description | Severity |
|----|---------|-------------|----------|
| BUG-missing-frontmatter | commands/*.md (all 26 command files) | Every command file lacks a YAML frontmatter block. The `name` and `description` fields required for NLPM registration are absent; the NLPM scanner cannot register any of these commands. Each file incurs -25 (name) + -25 (description) + -5 (allowed-tools) = -55 base penalty before any other deductions, producing a score ceiling of 45 for every command. | high |
| CC-terminology-drift | .claude-plugin/plugin.json, commands/*.md (example invocations) | Plugin name is `"atm"` but example invocations throughout command bodies use the form `/atm-scaffold`, `/atm-simplify`, etc. (hyphen-joined). Claude Code slash commands under a plugin namespace use a colon separator (`atm:scaffold`) or the bare command name depending on install scope. The example invocations in the body of commands like `simplify.md` would not match the actual registered command paths. | low |

## Security Fixes

| ID | File | Finding | Suggested Fix |
|----|------|---------|---------------|
| SEC-unpinned-npm-install | .claude-plugin/plugin.json | `npx -y @upstash/context7-mcp` installs the package without a version pin at every MCP server start; a malicious or breaking publish silently affects all plugin users | Pin to a specific release: `"args": ["-y", "@upstash/context7-mcp@X.Y.Z"]`; update the pin when the package releases a new tested version |

## Quality Issues

| Category | File(s) Affected | Issue | Suggested Fix |
|----------|-----------------|-------|---------------|
| Missing allowed-tools declaration | All 26 command files | No `allowed-tools` field in any command frontmatter (frontmatter is also missing, but even if added, allowed-tools would still need to be declared); Claude receives no permission budget guidance | Add `allowed-tools` to each command's frontmatter listing only the tools that command actually invokes |
| Expert persona commands lack process steps | commands/a11y-expert.md, commands/angular-expert.md, commands/django-expert.md | These files establish an expert persona ("You are now operating as a senior X engineer") but define no numbered steps or structured workflow; there is no deterministic process for the model to follow | Add a numbered task list or structured workflow section even for persona-mode commands, so the model has a repeatable execution path |
| No empty-input guard | commands/spike-investigation.md, commands/pr-review.md, commands/feature-investigation.md, commands/implement-pr-feedback.md, commands/problem-solver.md, commands/release-architect.md | `$ARGUMENTS` is consumed (directly or via variable assignment) without an explicit check for empty input; the model receives no guidance when invoked without arguments | Add: `if [[ -z "$ARGUMENTS" ]]; then echo "Usage: /atm:<command> <argument>"; exit 1; fi` before first use of `$ARGUMENTS` |
| Platform-specific clipboard command | commands/commit-msg.md | Uses `pbcopy` (macOS only) to copy the generated commit message; fails silently on Linux and Windows | Check `$OSTYPE` and branch: `pbcopy` on Darwin, `xclip -selection clipboard` or `xsel --clipboard` on Linux; or use the `bash` skill's clipboard abstraction |
| Vague quantifiers in skill files | .claude/skills/bash/SKILL.md, .claude/skills/ai/SKILL.md | bash skill: "Always" used 3 times as an unconditional directive without specifying the condition that triggers it; "graceful", "informative", "standard" lack measurable thresholds. ai skill: "effective", "specific", "appropriate", "focused", "relevant", "clear", "good", "proper" appear without success criteria | Replace vague qualifiers with measurable criteria (e.g., "Always check for command availability" → "Before running a command, test with `command -v <tool> >/dev/null 2>&1`") |
| High vague-word density in multi-step commands | commands/simplify.md, commands/bug-investigation.md, commands/self-review.md, commands/summarize-branch.md | These commands use 7–8 vague quantifiers each (comprehensive, thorough, relevant, complete, appropriate, etc.) in step descriptions, reducing the model's ability to know when a step is "done enough" | Audit each step instruction and replace subjective adjectives with observable completion criteria |

## Cross-Component

**Skill coverage**: The two skills (`.claude/skills/bash/SKILL.md`, `.claude/skills/ai/SKILL.md`) are well-structured and have frontmatter. However, no command file declares which skills it uses; the connection between commands and skills is implicit rather than declared in frontmatter `skills:` fields.

**$REPORT_BASE convention**: `commands/simplify.md` and `commands/spike-investigation.md` both write reports to `$REPORT_BASE` and the `bash` skill documents this variable — a coherent convention. Other commands that produce output (bug-investigation writes 3 files to unspecified paths) do not follow this pattern consistently.

**JIRA CLI usage**: Three commands (`bug-investigation.md`, `feature-investigation.md`, `ticket-explainer.md`) use `jira issue view` with consistent patterns. The `ticket-explainer` is the only one with an explicit authentication guidance message; the others silently fail if `jira` is not configured.

**Context7 MCP dependency**: At least four commands (`scaffold.md`, `spike-investigation.md`, `release-architect.md`, and implicitly `simplify.md`) rely on the `Context7` MCP server declared in `plugin.json`. The unpinned-npm-install security finding therefore affects all of these commands simultaneously; a single fix to `plugin.json` resolves the risk for all four.

**CLAUDE.md → AGENTS.md redirect**: The two-line CLAUDE.md that delegates to AGENTS.md is an intentional and documented pattern (described in `.claude/skills/ai/SKILL.md` §Claude Code Configuration). AGENTS.md is present in the repository root. This is not a bug.

**Expert persona consistency**: Three expert commands (`a11y-expert`, `angular-expert`, `django-expert`) follow the same persona pattern but have inconsistent depth: `django-expert.md` covers 5 topic domains with bullet-point guidance while `a11y-expert.md` and `angular-expert.md` are shorter and less structured. Standardising the expert template across the three would reduce scoring variance.

## Recommendation

**REVIEW** — security gate clears (no confirmed HIGH/CRITICAL findings; one confirmed MEDIUM). Submit NL fix PRs for the two bugs and the medium security fix. The systemic frontmatter bug (BUG-missing-frontmatter) is the highest-leverage single change: adding frontmatter to all 26 command files would lift the mean NL score from 36 to approximately 75 before any other changes, because the -55 base penalty is the dominant cost across every command. Address the MCP pin (SEC-unpinned-npm-install) and the six empty-input-guard commands in the same pass.
