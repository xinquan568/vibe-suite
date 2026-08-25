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
| `PostToolUse` | `scripts/check-artifact.sh` | matcher `Write\|Edit\|MultiEdit`; timeout 5 s; advisory only — fail-open, never blocks, one stderr line on NL-artifact edits |

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

## Assumed harness contract

The Stop hook reads a JSON object on stdin (`cwd`, `stop_hook_active`), writes
`{"decision":"block","reason":"…"}` on stdout to block, writes nothing to allow, and **always exits
0**. Tests drive the script with harness-shaped stdin, so a contract change shows up as a failing
test rather than a gate that silently stops gating.
