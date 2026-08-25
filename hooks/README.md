# `hooks/` — Hook registrations

Plugin hook wiring and the scripts it invokes. Hooks are executed by the harness, so treat every
input as untrusted.

`hooks.json` registers four events (settings-shaped nested schema; commands resolve through
`${CLAUDE_PLUGIN_ROOT}`):

| Event | Script | Notes |
|---|---|---|
| `Stop` | `scripts/stop-review-gate-hook.mjs` | timeout 900 s; **ships disabled** |
| `SessionStart` | `scripts/session-lifecycle-hook.mjs --event start` | hygiene; exits 0 on runtime faults (unknown `--event` → 2) |
| `SessionEnd` | `scripts/session-lifecycle-hook.mjs --event end` | hygiene; exits 0 on runtime faults (unknown `--event` → 2) |
| `PostToolUse` | `scripts/check-artifact.sh` | matcher `Write\|Edit\|MultiEdit`; timeout 5 s; advisory — never blocks (exit 2 would); on an NL-artifact edit it prints one stderr line and exits 1 (a non-2 non-zero exit the harness shows to the operator) |

## The stop-review gate is opt-in (D3)

It reviews the session's **diff** — tracked changes plus the content of new untracked files — and
answers `ALLOW:`/`BLOCK:`. On a fresh install `gate.stop_review_gate` is **false**, so the hook
short-circuits before any dispatch. Infra failure (codex missing, timeout, no parseable verdict)
**fails open** with a warning; set `gate.fail_policy: closed` to invert that. `gate.model` selects
the review model; unset means the backend's own default (never a pinned id — P9).

**Enabling it:** `/vibe-suite:config` will own this toggle (E1.8, not yet built). Until then it is
a runtime-store write:

```bash
python3 -c "import sys; sys.path.insert(0, 'scripts/lib'); import store; \
  store.Store('.').set('gate.stop_review_gate', True)"
```

Read the resolved configuration with the store's read-only bridge — the same one the hook uses:

```bash
python3 scripts/lib/store.py effective-config .
```

## What the lifecycle hooks deliberately do NOT do (yet)

They reap orphan temp files and **report** abandoned or still-running background jobs. They never
rewrite a record they do not own — settling belongs to `/vibe-suite:jobs status --settle-abandoned`.
Three behaviours from the F2.6 source hook are deferred, with causes:

- **Session-scoped job cleanup** — job records carry no session id, so "this session's jobs" is not
  expressible today; adding one is a store-contract change, not a hook change.
- **Environment export** — nothing consumes it until the cross-tool bridge lands (F1.6 / E2.x).
- **Stale-registration migration** — owned by the §7A migration engine (E0.8), invoked by init
  (E2.1). A hook re-running it would be a second authority over the same sentinels.

## Harness output contract — where a report is actually SEEN (vibe-203 / M1)

A hook reporting on **stderr at exit 0 is transcript-only** — Claude Code does not surface it to
the operator interactively. Each event has a *visible* channel, and every report is routed to it:

| Event | Visible channel | This repo's use |
|---|---|---|
| `SessionStart` | **stdout** is added to the session context | `session-lifecycle-hook.mjs --event start` writes its reaped / unreadable / abandoned reports to **stdout** |
| `SessionEnd` | stdout is **not** shown (session ending) | `--event end` reports stay on stderr (transcript); "still running" is end-only |
| `Stop` | JSON on stdout: `{"decision":"block","reason":…}` blocks; **`{"systemMessage":…}`** shows a notice while still ALLOWING (no `decision` field = allow); empty stdout = silent allow | the fail-open path now emits `{"systemMessage":"stop-review gate: … — failing open"}` (and keeps the stderr line), so the operator SEES the H5 fail-open notice |
| `PostToolUse` | exit 2 blocks and feeds stderr to Claude; **a non-2 non-zero exit shows stderr to the operator, non-blocking**; exit 0 = transcript-only | `check-artifact.sh` prints the advisory to stderr and `exit 1` (non-blocking, shown) |

**Verification.** These channels are the documented Claude Code hook contract; the tests assert the
CHANNEL each report uses (`session-lifecycle.test.mjs` start→stdout / end→stderr;
`stop-gate.test.mjs` fail-open→`systemMessage`; `test_check_artifact_hook.py` advisory→exit 1). The
Stop **decision** JSON shape is unchanged — a block is still `{"decision":"block","reason":…}` — so
the harness's parse is preserved; only an *additional* `systemMessage` allow-notice was introduced.
