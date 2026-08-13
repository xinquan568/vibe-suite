---
slug: alexgreensh-token-optimizer
repo: alexgreensh/token-optimizer
audited: 2026-05-13
commit_sha: e80f11f2070eaa55e51945288404fb2a23f06f14
score: 98
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
  - R30
---

# Exemplar: alexgreensh/token-optimizer

**Score**: 98/100  |  **Date**: 2026-05-13  |  **Commit**: `e80f11f2070eaa55e51945288404fb2a23f06f14`

A five-skill Claude Code plugin for token usage auditing, fleet analysis, and behavioral coaching; notable for systematically precise description triggers, scoped companion skills, runnable bash with inline error handling, decision tables in place of branching prose, and consistent `${CLAUDE_PLUGIN_ROOT}` use across all hooks.

## Per-rule evidence

### R04 — Description as trigger

All four 100-score skills pack use-when specificity and quantified claims directly into their `description` frontmatter. `fleet-auditor` names the supported platforms and three distinct waste categories. `token-coach` lists four discrete user situations. Neither relies on the skill name to carry the trigger load.

> Real quote from `skills/fleet-auditor/SKILL.md:3`:
>
> ```
> description: Audit token waste across agent systems (Claude Code, OpenClaw, Hermes, OpenCode). Detect idle burns, model misrouting, and config bloat with dollar savings.
> ```

> Real quote from `skills/token-coach/SKILL.md:3`:
>
> ```
> description: Context window coach. Proactive guidance for token-efficient Claude Code projects, multi-agent systems, and skill architecture.
> ```

`fleet-auditor`'s description names four systems and three waste categories in 186 characters — enough for Claude to distinguish it from the single-system token-optimizer skill without reading the body.

---

### R05 — Under 500 lines

The plugin separates a large orchestration skill (token-optimizer, 559 lines) from four narrowly scoped companions that each stay under 200 lines: `token-dashboard` at 33 lines, `openclaw/skills/token-optimizer` at 51 lines, `token-coach` at 112 lines, `fleet-auditor` at 140 lines. Each companion covers exactly one workflow and cross-references the main skill where users need deeper capability. This is the split-into-scoped-sub-skills architecture R05 recommends.

> Real quote from `skills/token-dashboard/SKILL.md:1-6` (the entire skill in three numbered steps):
>
> ```markdown
> ---
> name: token-dashboard
> description: Open the Token Optimizer dashboard. Collects latest session data, regenerates the dashboard, and opens it in your browser.
> ---
>
> # Token Optimizer Dashboard
> ```

`token-dashboard` completes its work in 3 numbered steps and 33 lines by delegating all measurement to `measure.py` — single-responsibility scope leaves no room for creep.

---

### R06 — Code examples must be runnable

Every bash block in `token-optimizer` uses real syntax with inline error handling. The `measure.py` path resolver in Phase 0 iterates two install paths, guards with `[ -f "$f" ]`, and exits with a named error message if nothing is found — no pseudocode or placeholder paths.

> Real quote from `skills/token-optimizer/SKILL.md:20-27`:
>
> ```bash
> MEASURE_PY=""
> for f in "$HOME/.claude/skills/token-optimizer/scripts/measure.py" \
>          "$HOME/.claude/plugins/cache"/*/token-optimizer/*/skills/token-optimizer/scripts/measure.py; do
>   [ -f "$f" ] && MEASURE_PY="$f" && break
> done
> [ -z "$MEASURE_PY" ] && { echo "[Error] measure.py not found. Is Token Optimizer installed?"; exit 1; }
> echo "Using: $MEASURE_PY"
> ```

The `[ -f "$f" ]` guard and the `[ -z "$MEASURE_PY" ]` exit clause distinguish a working example from a working example that also tells users what went wrong. Pseudocode would show neither.

---

### R07 — Scope note when related skills exist

`fleet-auditor` declares its activation scope upfront in the skill body and explicitly routes users to `/token-optimizer` in Phase 5 for deeper Claude Code analysis. Without the Phase 5 handoff, a user asking "why are my tokens high?" from inside a fleet audit would never discover the single-system deeper audit.

> Real quote from `skills/fleet-auditor/SKILL.md:11-12`:
>
> ```
> **Use when**: Running multiple agent systems, spending $2-5/day on agents, suspecting idle
> heartbeats are burning tokens, or want a cross-system cost audit.
> ```

> Real quote from `skills/fleet-auditor/SKILL.md:105-107`:
>
> ```
> ## Phase 5: Deep Dive (optional)
>
> For Claude Code specifically, offer `/token-optimizer` for full audit (CLAUDE.md, skills, MCP, hooks, etc.).
> ```

The scope note in the body and the Phase 5 handoff together close the routing gap at the exact point where the user is most likely to need the deeper skill.

---

### R08 — Patterns over theory

`token-optimizer` encodes multi-state decisions as lookup tables rather than conditional prose. The daemon/consent state machine in Phase 0 Step 6 is a 3×3 table — Claude reads the two state values, finds the cell, and executes the prescribed action without parsing nested if/else branches.

> Real quote from `skills/token-optimizer/SKILL.md:122-126`:
>
> ```
> | Daemon \ Consent | unrecorded (`{}`) | `consent: true` | `consent: false` |
> |---|---|---|---|
> | `DAEMON_RUNNING` | skip; lead with URL next time output mentions the dashboard | skip; URL works | the user declined but the daemon is still running — offer `setup-daemon --uninstall` once |
> | `DAEMON_FOREIGN` | prompt, but warn port 24842 is already bound by a foreign service (`netstat -ano \| findstr :24842` on Windows, `lsof -i :24842` on Mac) | note conflict, suggest uninstalling our daemon's prior instance or freeing the port | skip silently |
> | `DAEMON_NOT_RUNNING` | first-time install prompt (below) | offer to reinstall (`measure.py setup-daemon`) — launchd / Task Scheduler lost it | skip silently |
> ```

The table encodes 9 distinct behaviors in a form Claude can index in one pass. An equivalent if/else chain in prose would be ~40 tokens longer and would require Claude to simulate branching rather than direct lookup.

---

### R30 — Use `${CLAUDE_PLUGIN_ROOT}` for paths

Every command entry in `hooks/hooks.json` references both the launcher script and the Python runner via `${CLAUDE_PLUGIN_ROOT}` — no hardcoded absolute paths anywhere in the file across 17 hook registrations.

> Real quote from `hooks/hooks.json:9`:
>
> ```json
> "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/python-launcher.sh\" \"${CLAUDE_PLUGIN_ROOT}/hooks/run.py\" skills/token-optimizer/scripts/read_cache.py --quiet"
> ```

The pattern applies `${CLAUDE_PLUGIN_ROOT}` to the launcher and runner, then uses a relative path for the Python target — so the hook works whether the plugin is installed under `~/.claude/skills/`, `~/.claude/plugins/cache/`, or any other prefix without modification.

---

## Worth adopting

**Pattern: Truth-table for N×M state machines.** Evidence: `skills/token-optimizer/SKILL.md:120-126`. Why it would be a useful rule: when a skill has two independent state variables with 3+ values each, a markdown table encodes all branches unambiguously and more compactly than prose conditionals — Claude can index to the cell rather than simulate a branch tree. Candidate rule: "Use a markdown table when a decision has two axes with three or more values each. Tables prevent branch-conflation errors and reduce token length for equivalent logic."
