---
description: "Non-interactive repair of a vibe-suite bridge: re-runs every bridge step from the settings already in .vibe-suite.md, with no prompts, collecting failures and continuing so one broken step cannot hide the rest. Reports a per-step outcome. The escalation path from doctor. No arguments."
argument-hint: ""
---

# /vibe-suite:repair — non-interactive bridge repair

The escalation path from `/vibe-suite:doctor`. Doctor says what is wrong; repair fixes what it can
**without asking anything**, because repair is what runs when nobody is there to answer.

## What to do

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/repair.py" --workspace .
```

Add `--json` for the structured form; the command itself takes no arguments.

## What it repairs, and what it deliberately does not

`/vibe-suite:doctor` marks findings `auto-fixable`, and that flag means exactly one thing: **a
no-prompt repair clears it**. Three checks qualify — `sentinels` (a dangling registration of the
bare `vibe-suite` command, which no shipped binary backs — repair removes it from the file that
carries it and says so in the step's outcome), `memory`, `gitignore`.

Five look repairable and are not:

| Finding | Why repair cannot clear it | What does |
|---|---|---|
| `legacy-config`, `legacy-state` | §7A **preserves** the legacy source, so the finding survives its own fix | `/vibe-suite:init` |
| `legacy-sentinels` | §7A row 6 requires **explicit confirmation** | `/vibe-suite:init` |
| `pins` | provenance is **write-once**; re-installing does not re-stamp the version | a fresh install |
| `not-initialised` | the fix is `init`, which asks questions | `/vibe-suite:init` |
| `hooks` | no owned `Stop` hook is written until the `vibe-suite` binary ships, so there is nothing to restore; an owned entry whose absolute command does not resolve is yours to fix | you |

None of these is flagged auto-fixable. A flag promising what no command delivers is worse than no
flag.

## Collect and continue

Each step runs in isolation and one failure never stops the others — that is F1.3's requirement and
the reason repair does not simply re-run the installer, which stops at its first error. Report the
per-step table as returned, then say plainly whether anything failed.

Exit `0` all steps fine · `1` at least one failed · `2` nothing is installed here.

## What it will not do

- **Prompt.** Not for a §7A decision, not for anything. A row needing a *fresh* decision is reported
  and skipped, because §7A forbids deciding silently and repair has no answer to give.
- **Install.** Repair restores a bridge; it does not create one. On an uninitialised project it
  declines and points at `/vibe-suite:init` rather than half-installing without the answers init
  would have asked for.
- **Ask for strictness.** The band's only job was computing `score_threshold`, which the config
  already stores, so repair reads the stored value instead of reconstructing the question.
