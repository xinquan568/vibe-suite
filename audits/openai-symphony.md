# NLPM Audit: openai/symphony
**Date**: 2026-05-05  |  **Artifacts**: 6  |  **Strategy**: single
**NL Score**: 89/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 13  |  **Security Findings**: 0

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .codex/skills/land/SKILL.md | skill | 84 | Missing output section; vague: "judgment", "brief" (×2) |
| .codex/skills/pull/SKILL.md | skill | 86 | Missing output section; vague: "minimal", "complex" |
| .codex/skills/push/SKILL.md | skill | 86 | Missing output section; vague: "proper", "clearly" |
| .codex/skills/debug/SKILL.md | skill | 88 | Missing output section; vague: "relevant" |
| .codex/skills/linear/SKILL.md | skill | 90 | Missing output section |
| .codex/skills/commit/SKILL.md | skill | 100 | None |

**Weighted average**: (84 + 86 + 86 + 88 + 90 + 100) / 6 = **89/100**

### Scoring notes

`commit` is the reference implementation: it has explicit `## Goals`, `## Inputs`, `## Steps` (numbered), `## Output`, and `## Template` sections. All five remaining skills are missing a dedicated `## Output` section (-10 each). `land` accumulates the most vague-quantifier penalties: "Use judgment" (line 122) and two uses of "brief" (lines 211, 213).

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | none |
| Scripts | `.codex/worktree_init.sh`, `.codex/skills/land/land_watch.py`, `elixir/test/support/live_e2e_docker/live_worker_entrypoint.sh` |
| MCP configs | none |
| Package manifests | none |

### Security Findings

No security findings.

**Script analysis summary:**

- **`.codex/worktree_init.sh`** — 17-line Bash setup script. Calls `mise trust` and `make setup` inside the Elixir project directory. No credential handling, no network calls, no `eval`, no `sudo`. Clean.
- **`.codex/skills/land/land_watch.py`** — 622-line async Python PR watcher. Uses `asyncio.create_subprocess_exec("gh", *args, ...)` — `shell=False` throughout, so no shell-injection risk. All GitHub API calls go through the authenticated `gh` CLI. Includes a `sanitize_terminal_output` function that strips control characters before printing comment bodies. No credential exfiltration, no arbitrary exec. Clean.
- **`elixir/test/support/live_e2e_docker/live_worker_entrypoint.sh`** — 14-line Docker entrypoint for the live E2E test container. Installs an SSH authorized key from a mounted volume and starts `sshd`. Intentional test infrastructure; bounded and reviewed. Clean.

## Bugs (PR-worthy)

No bugs found. All six skills carry valid `name` and `description` frontmatter. All cross-skill references resolve (see Cross-Component). No declared tools or broken includes.

## Security Fixes (PR-worthy, Medium/Low only)

No security fixes required.

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .codex/skills/debug/SKILL.md | Missing `## Output` section — the skill drives an investigation but does not specify what evidence/summary the agent should produce | -10 |
| 2 | .codex/skills/debug/SKILL.md | Vague quantifier "relevant" (line 23: "when the relevant run is older") | -2 |
| 3 | .codex/skills/linear/SKILL.md | Missing `## Output` section — reference guide but callers cannot infer what structured result to expect from each operation | -10 |
| 4 | .codex/skills/pull/SKILL.md | Missing `## Output` section — step 9 describes a merge summary inline but no dedicated output declaration | -10 |
| 5 | .codex/skills/pull/SKILL.md | Vague quantifier "minimal" (line 61: "Prefer minimal, intention-preserving edits") | -2 |
| 6 | .codex/skills/pull/SKILL.md | Vague quantifier "complex" (line 63: "For complex conflicts, search for related files") | -2 |
| 7 | .codex/skills/push/SKILL.md | Missing `## Output` section — step 8 mentions "Reply with the PR URL" inline but no dedicated output declaration | -10 |
| 8 | .codex/skills/push/SKILL.md | Vague quantifier "proper" (line 44: "Write a proper PR title that clearly describes the change outcome") | -2 |
| 9 | .codex/skills/push/SKILL.md | Vague quantifier "clearly" (line 44: same sentence) | -2 |
| 10 | .codex/skills/land/SKILL.md | Missing `## Output` section — goal is an implicit "PR merged" state but no declared output format | -10 |
| 11 | .codex/skills/land/SKILL.md | Vague quantifier "judgment" (line 122: "Use judgment to identify flaky failures") | -2 |
| 12 | .codex/skills/land/SKILL.md | Vague quantifier "brief" (line 211: "with a brief reason") | -2 |
| 13 | .codex/skills/land/SKILL.md | Vague quantifier "brief" (line 213: "offer a brief alternative or follow-up trigger") | -2 |

## Cross-Component

**Ambiguous path reference — pull/SKILL.md line 33:**
`"Verify with project checks (follow repo policy in AGENTS.md)."` — no path prefix given. The repository has no root-level `AGENTS.md`; the file exists only at `elixir/AGENTS.md`. The reference is functionally correct but could mislead an agent searching from the workspace root. Recommend changing to `elixir/AGENTS.md`.

**All other cross-references are valid:**
- `land` → `commit`, `pull`, `push` skills — all present at `.codex/skills/{commit,pull,push}/SKILL.md`
- `land` → `land_watch.py` — present at `.codex/skills/land/land_watch.py`
- `push` → `.github/pull_request_template.md` — present
- `debug` → `elixir/docs/logging.md` — present

## Recommendation

CLEAR — security scan is clean with zero findings across three scripts. No NL bugs require private disclosure. Submit quality-improvement PRs for the five skills missing `## Output` sections, and patch the ambiguous `AGENTS.md` path reference in `pull/SKILL.md`. Vague-quantifier fixes are low-priority but straightforward. The overall corpus is high quality; `commit/SKILL.md` is an exemplary reference.
