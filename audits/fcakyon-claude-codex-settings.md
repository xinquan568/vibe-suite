# NLPM Audit: fcakyon/claude-codex-settings
**Date**: 2026-04-06  |  **Artifacts**: 103  |  **Strategy**: progressive
**NL Score**: 79/100
**Security**: REVIEW
**Bugs**: 23  |  **Quality Issues**: 12  |  **Security Findings**: 8

## NL Score Summary

Scores sorted ascending. Reference-doc skills under `supabase-cli/references/commands/` are scored as SKILL.md artifacts — they have no frontmatter block and pull the average down significantly. The 4 github-dev agents are the strongest artifacts in the repo.

| Score | Artifact | Type | Penalties |
|-------|----------|------|-----------|
| 50 | plugins/supabase-skills/skills/supabase-cli/references/commands/functions.md | skill | no frontmatter block (-50) |
| 50 | plugins/supabase-skills/skills/supabase-cli/references/commands/gen.md | skill | no frontmatter block (-50) |
| 50 | plugins/supabase-skills/skills/supabase-cli/references/commands/init.md | skill | no frontmatter block (-50) |
| 50 | plugins/supabase-skills/skills/supabase-cli/references/commands/link.md | skill | no frontmatter block (-50) |
| 50 | plugins/supabase-skills/skills/supabase-cli/references/commands/login.md | skill | no frontmatter block (-50) |
| 50 | plugins/supabase-skills/skills/supabase-cli/references/commands/projects.md | skill | no frontmatter block (-50) |
| 50 | plugins/supabase-skills/skills/supabase-cli/references/commands/secrets.md | skill | no frontmatter block (-50) |
| 50 | plugins/supabase-skills/skills/supabase-cli/references/commands/start.md | skill | no frontmatter block (-50) |
| 50 | plugins/supabase-skills/skills/supabase-cli/references/commands/status.md | skill | no frontmatter block (-50) |
| 50 | plugins/supabase-skills/skills/supabase-cli/references/commands/stop.md | skill | no frontmatter block (-50) |
| 70 | plugins/azure-tools/commands/setup.md | command | missing name (-25), missing allowed-tools (-5) |
| 70 | plugins/claude-tools/commands/sync-allowlist.md | command | missing name (-25), broken repo reference in step 1 (-5) |
| 70 | plugins/gcloud-tools/commands/setup.md | command | missing name (-25), missing allowed-tools (-5) |
| 70 | plugins/paper-search-tools/commands/setup.md | command | missing name (-25), missing allowed-tools (-5) |
| 70 | plugins/tavily-tools/commands/setup.md | command | missing name (-25), missing allowed-tools (-5) |
| 75 | plugins/claude-tools/commands/load-claude-md.md | command | missing name (-25) |
| 75 | plugins/claude-tools/commands/sync-claude-md.md | command | missing name (-25) |
| 75 | plugins/claude-tools/commands/update-readme.md | command | missing name (-25) |
| 82 | plugins/react-skills/skills/composition-patterns/SKILL.md | skill | non-trigger description (-10), vendor-prefix in name (-8) |
| 83 | plugins/stripe-skills/skills/upgrade-stripe/SKILL.md | skill | description not in trigger format (-10), no quoted trigger phrases (-7) |
| 85 | plugins/stripe-skills/skills/stripe-projects/SKILL.md | skill | description not in trigger format (-10), no quoted trigger phrases (-5) |
| 88 | plugins/github-dev/agents/commit-creator.md | agent | potentially unused tools: WebSearch, WebFetch, mcp__tavily__* (-6), inline example format (-6) |
| 88 | plugins/github-dev/agents/pr-creator.md | agent | potentially unused tools: WebSearch, WebFetch, mcp__tavily__* (-6), inline example format (-6) |
| 88 | plugins/mongodb-skills/skills/mongodb-natural-language-querying/SKILL.md | skill | non-standard `allowed-tools` field in SKILL.md schema (-12) |
| 90 | plugins/agent-browser/skills/agent-browser/SKILL.md | skill | non-standard `allowed-tools` frontmatter field (-10) |
| 90 | plugins/cloudflare-skills/skills/cloudflare-deploy/SKILL.md | skill | large index skill with no output format hint (-10) |
| 90 | plugins/hetzner-skills/skills/hetzner-deploy/SKILL.md | skill | non-standard `references` frontmatter field (-10) |
| 90 | plugins/livekit-skills/skills/livekit-skills/SKILL.md | skill | extra metadata fields: author, version (-10) |
| 92 | plugins/github-dev/agents/pr-comment-resolver.md | agent | description specificity could be stronger (-8) |
| 92 | plugins/python-skills/skills/python-guidelines/SKILL.md | skill | trigger phrases could be more varied (-8) |
| 92 | plugins/web-performance-skills/skills/web-performance-optimization/SKILL.md | skill | non-standard `license` field in frontmatter (-8) |
| 95 | plugins/github-dev/agents/pr-reviewer.md | agent | minor description verbosity (-5) |

## Security Scan

**Severity counts**: Critical: 0 | High: 1 | Medium: 5 | Low: 2

**Execution surface inventory**:
- Hook JSON files: 4 (`ultralytics-dev`, `tavily-tools`, `github-dev`, `claude-tools`)
- Hook Python scripts: 11 files across 4 plugins
- MCP config files: 5 (`.mcp.json` in `tavily-tools`, `azure-tools`, `gcloud-tools`, `paper-search-tools`, `web-performance-skills`)
- GitHub maintenance scripts: 14 bash scripts under `.github/scripts/`

| Severity | File | Pattern | Notes |
|----------|------|---------|-------|
| HIGH | plugins/ultralytics-dev/hooks/hooks.json:10 | Inline bash reads `file_path` from jq stdin then uses it in `case` matching and `sed -i` | AI tool input flows into shell operations without sanitization; path from Claude tool response determines which `sed` runs |
| MEDIUM | plugins/github-dev/hooks/scripts/git_commit_confirm.py | `subprocess.run(["git", "diff", "--cached", ...])` | Safe list form; no injection; reads AI-controlled staged content |
| MEDIUM | plugins/github-dev/hooks/scripts/gh_pr_create_confirm.py | `subprocess.run(["gh", "api", "user", ...])` | Safe list form; makes outbound GitHub API calls |
| MEDIUM | plugins/ultralytics-dev/hooks/scripts/python_code_quality.py | `subprocess.run(['ruff', 'check', '--fix', ...], str(py_file))` | File path from JSON input; validated via pathlib before use; safe in practice |
| MEDIUM | plugins/claude-tools/hooks/scripts/sync_marketplace_to_plugins.py | Writes files to plugin dirs from `source` field in marketplace.json | Path traversal risk if marketplace.json is tampered; no traversal guard present |
| MEDIUM | .github/scripts/_helpers.sh | `python3 -c "..."` with `$skill_md`/`$license` shell variable interpolation | Developer-only maintenance script; limited runtime exposure |
| LOW | plugins/*/. mcp.json (5 files) | Broad MCP server permissions with no explicit scope restrictions | Standard MCP pattern; no active exploit; worth scoping on install |
| LOW | .github/scripts/release.sh | `for sync_script in "$SCRIPTS_DIR"/sync-*-skills.sh; do bash "$sync_script"` | Glob expansion of developer-controlled scripts; developer-only context |

## Bugs

Mechanical NL schema violations. All are PR-ready fixes with no design decisions required.

| File | Field / Location | Expected | Found |
|------|-----------------|----------|-------|
| plugins/tavily-tools/commands/setup.md | `name` frontmatter | kebab-case string | missing |
| plugins/tavily-tools/commands/setup.md | `allowed-tools` frontmatter | tool list | missing |
| plugins/claude-tools/commands/update-readme.md | `name` frontmatter | kebab-case string | missing |
| plugins/claude-tools/commands/sync-claude-md.md | `name` frontmatter | kebab-case string | missing |
| plugins/claude-tools/commands/load-claude-md.md | `name` frontmatter | kebab-case string | missing |
| plugins/claude-tools/commands/sync-allowlist.md | `name` frontmatter | kebab-case string | missing |
| plugins/claude-tools/commands/sync-allowlist.md | step 1 repo URL | `fcakyon/claude-codex-settings` | `fcakyon/claude-settings` |
| plugins/azure-tools/commands/setup.md | `name` frontmatter | kebab-case string | missing |
| plugins/azure-tools/commands/setup.md | `allowed-tools` frontmatter | tool list | missing |
| plugins/gcloud-tools/commands/setup.md | `name` frontmatter | kebab-case string | missing |
| plugins/gcloud-tools/commands/setup.md | `allowed-tools` frontmatter | tool list | missing |
| plugins/paper-search-tools/commands/setup.md | `name` frontmatter | kebab-case string | missing |
| plugins/paper-search-tools/commands/setup.md | `allowed-tools` frontmatter | tool list | missing |
| plugins/supabase-skills/skills/supabase-cli/references/commands/functions.md | frontmatter block | `---\nname: ...\ndescription: ...\n---` | no frontmatter |
| plugins/supabase-skills/skills/supabase-cli/references/commands/gen.md | frontmatter block | `---\nname: ...\ndescription: ...\n---` | no frontmatter |
| plugins/supabase-skills/skills/supabase-cli/references/commands/init.md | frontmatter block | `---\nname: ...\ndescription: ...\n---` | no frontmatter |
| plugins/supabase-skills/skills/supabase-cli/references/commands/link.md | frontmatter block | `---\nname: ...\ndescription: ...\n---` | no frontmatter |
| plugins/supabase-skills/skills/supabase-cli/references/commands/login.md | frontmatter block | `---\nname: ...\ndescription: ...\n---` | no frontmatter |
| plugins/supabase-skills/skills/supabase-cli/references/commands/projects.md | frontmatter block | `---\nname: ...\ndescription: ...\n---` | no frontmatter |
| plugins/supabase-skills/skills/supabase-cli/references/commands/secrets.md | frontmatter block | `---\nname: ...\ndescription: ...\n---` | no frontmatter |
| plugins/supabase-skills/skills/supabase-cli/references/commands/start.md | frontmatter block | `---\nname: ...\ndescription: ...\n---` | no frontmatter |
| plugins/supabase-skills/skills/supabase-cli/references/commands/status.md | frontmatter block | `---\nname: ...\ndescription: ...\n---` | no frontmatter |
| plugins/supabase-skills/skills/supabase-cli/references/commands/stop.md | frontmatter block | `---\nname: ...\ndescription: ...\n---` | no frontmatter |

## Security Fixes

Medium and Low findings with targeted remediations.

| Severity | File | Fix |
|----------|------|-----|
| MEDIUM | plugins/claude-tools/hooks/scripts/sync_marketplace_to_plugins.py | Add path traversal guard: resolve the `source` field path with `Path(...).resolve()` and assert it starts with the expected plugin root before writing |
| MEDIUM | .github/scripts/_helpers.sh | Replace `python3 -c "..."` with a separate `.py` script file; pass variables as arguments rather than interpolating into the `-c` string |
| LOW | plugins/*/. mcp.json (5 files) | Document recommended permission scoping per server in README; note that users should review permissions on install |

The HIGH finding in `ultralytics-dev/hooks/hooks.json` requires architectural change (see Recommendations).

## Quality Issues

Non-schema issues that reduce clarity or trigger reliability but do not break the artifact.

| File | Issue | Suggestion |
|------|-------|-----------|
| plugins/stripe-skills/skills/upgrade-stripe/SKILL.md | Description uses imperative ("Guide for upgrading...") not trigger format | Rewrite: "This skill should be used when upgrading Stripe API versions..." |
| plugins/stripe-skills/skills/stripe-projects/SKILL.md | Description uses present tense ("Use when setting up...") not trigger format | Rewrite: "This skill should be used when setting up Stripe..." |
| plugins/react-skills/skills/composition-patterns/SKILL.md | name is `vercel-composition-patterns` — vendor prefix couples skill to one provider | Rename to `react-composition-patterns` |
| plugins/react-skills/skills/composition-patterns/SKILL.md | Description not in trigger format | Rewrite with "This skill should be used when..." preamble |
| plugins/github-dev/agents/commit-creator.md | Tools include WebSearch, WebFetch, mcp__tavily__* but no step in the agent body explicitly uses web retrieval | Remove or justify with a "Source Verification" step like pr-creator does |
| plugins/github-dev/agents/pr-creator.md | Same unused-tool pattern as commit-creator | Verify WebSearch/WebFetch usage is exercised; remove if not |
| plugins/mongodb-skills/skills/mongodb-natural-language-querying/SKILL.md | `allowed-tools: mcp__mongodb__*` is not part of the SKILL.md schema | Move tool constraint to the agent that loads this skill, or document as intentional extension |
| plugins/livekit-skills/skills/livekit-skills/SKILL.md | Extra frontmatter fields: `author`, `version` | Remove; these fields are ignored by Claude Code and add noise |
| plugins/hetzner-skills/skills/hetzner-deploy/SKILL.md | Non-standard `references` frontmatter field | Remove or move inline as a section header |
| plugins/web-performance-skills/skills/web-performance-optimization/SKILL.md | Non-standard `license` frontmatter field | Remove; license belongs in plugin.json, not SKILL.md |
| plugins/claude-tools/commands/sync-claude-md.md | Body is single-sentence prose, no numbered steps | Break into numbered steps for consistency with other commands in this plugin |
| plugins/agent-browser/skills/agent-browser/SKILL.md | `allowed-tools` in frontmatter is non-standard for SKILL.md | Move to a companion agent definition or document as non-standard |

## Cross-Component

- **Broken reference**: `plugins/claude-tools/commands/sync-allowlist.md` step 1 hardcodes `fcakyon/claude-settings` as the source repo. The actual repo is `fcakyon/claude-codex-settings`. This causes the sync command to silently fetch allowlists from a different (possibly nonexistent) repository.
- **Missing commands in python-skills**: The `python-skills` plugin has a `python-guidelines` SKILL.md and its CLAUDE.md mentions installing and enabling via `python-skills` plugin, but there are no commands under `plugins/python-skills/commands/`. Users who follow the CLAUDE.md instruction (`install and enable the python-skills plugin`) get only the skill, not the referenced `python-guidelines` skill command trigger implied by the text.
- **Hook script paths are consistent**: All `ultralytics-dev` hooks reference `${CLAUDE_PLUGIN_ROOT}/hooks/scripts/...` and the scripts exist at those paths. No dangling references.

## Recommendations

1. **Fix the HIGH security finding first.** Extract the inline bash from `ultralytics-dev/hooks/hooks.json` line 10 into a Python script (matching the pattern used by `python_code_quality.py`). Validate and resolve the file path with `pathlib.Path.resolve()` before any shell operation. The inline JSON bash approach cannot be safely sanitized.

2. **Add `name` to all 8 commands.** This is a one-line fix per file and recovers 25 points per artifact from the score. The pattern is already established by agents in the same repo.

3. **Add frontmatter to the 10 supabase-cli reference docs.** These files score 50/100 and drag the repo average down by ~5 points. Even a minimal `name` + `description` block restores them to 100.

4. **Fix the sync-allowlist.md repo URL** before a user runs it and silently syncs from the wrong repo.

5. **Standardize SKILL.md descriptions.** The stripe and react skills use freeform descriptions. The SKILL.md spec requires "This skill should be used when..." with quoted trigger phrases. A one-pass edit across those files aligns them with the schema and improves agent routing accuracy.
