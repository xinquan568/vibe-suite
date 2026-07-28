#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
# `/vibe-suite:init` — interactive project setup (E2.1 / vibe-18, F1.1 + §7A rows 1-8/10).
#
# Two script families meet here and they take opposite rules. The **bridge** steps below are init's
# own mutations and each runs exactly once per install — F1.1's fix for cc-suite's double
# `bridge_skills.sh` run. The **§7A migration helpers** under `scripts/migrate/` carry the shared
# exit contract instead: exit 3 means a decision is required, and `common.sh` names init as the
# caller that asks and re-invokes.
#
# **Migration runs before any store this install writes.** `migrate-config.sh` skips once
# `.vibe-suite.md` exists and `migrate-history.sh` skips once the new history does, so a
# fresh-write-first order would suppress rows 1-3: the helper reports "new store wins", exits 0, and
# the legacy values are never read. Nothing fails; the settings simply never arrive.
#
# **Decisions are tri-state.** A flag absent means *not asked*; `--resolve-*` means *accepted with
# this value*; `--decline-*` means *asked and declined*. `false` is a legitimate value for
# `gate.stop_review_gate`, so a two-valued flag cannot carry the third state.
#
# **Init is re-entrant, not resumable.** Every invocation re-runs from the start and relies on each
# helper's own idempotence, so the accumulating decision flags are the whole resume state and nothing
# about a decision is persisted between runs.
#
# Usage: init.sh [--workspace DIR] --tier T --audit-depth D --strictness S [--skip PAT]
#                [--resolve-config JSON | --decline-config]
#                [--resolve-state true|false | --decline-state]
#                [--confirm-sentinels yes|no] [--non-interactive]
#                [--list-owned] [--list-checkpoints]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR source=migrate/common.sh disable=SC1091
. "$here/migrate/common.sh"

workspace="." tier="" depth="" strictness="" skip=""
resolve_config="" decline_config=0 resolve_state="" decline_state=0
confirm_sentinels="" non_interactive=0 list_owned=0 list_checkpoints=0

#: Every bridge step, in order. Each is a checkpoint boundary, so `VIBE_FAIL_AFTER` can interrupt
#: between any two and the re-run must converge.
CHECKPOINTS="survey provenance migrate-config migrate-history migrate-state migrate-sentinels \
config-fill memory codex mcp gitignore history-baseline"

while [ $# -gt 0 ]; do
    case "$1" in
        --workspace)         workspace="$2"; shift 2 ;;
        --tier)              tier="$2"; shift 2 ;;
        --audit-depth)       depth="$2"; shift 2 ;;
        --strictness)        strictness="$2"; shift 2 ;;
        --skip)              skip="$2"; shift 2 ;;
        --resolve-config)    resolve_config="$2"; shift 2 ;;
        --decline-config)    decline_config=1; shift ;;
        --resolve-state)     resolve_state="$2"; shift 2 ;;
        --decline-state)     decline_state=1; shift ;;
        --confirm-sentinels) confirm_sentinels="$2"; shift 2 ;;
        --non-interactive)   non_interactive=1; shift ;;
        --list-owned)        list_owned=1; shift ;;
        --list-checkpoints)  list_checkpoints=1; shift ;;
        --help)              sed -n '2,30p' "$0"; exit 0 ;;
        *)                   vibe_die "unknown argument: $1" ;;
    esac
done

if [ "$list_checkpoints" = 1 ]; then
    # shellcheck disable=SC2086  # deliberate split: one checkpoint per line
    printf '%s\n' $CHECKPOINTS
    exit 0
fi
if [ "$list_owned" = 1 ]; then python3 "$here/lib/bridge.py" list-owned "$workspace"; exit 0; fi

# Accept and decline are mutually exclusive per row. Treating one as precedence over the other would
# make a typo silently choose an answer the operator did not give.
[ -n "$resolve_config" ] && [ "$decline_config" = 1 ] && \
    vibe_die "--resolve-config and --decline-config are mutually exclusive"
[ -n "$resolve_state" ] && [ "$decline_state" = 1 ] && \
    vibe_die "--resolve-state and --decline-state are mutually exclusive"

[ -n "$tier" ] || vibe_die "--tier is required (a trust tier: haiku|sonnet|opus-class — never a versioned id, per P9/D6)"
[ -n "$depth" ] || vibe_die "--audit-depth is required (full|mini)"
[ -n "$strictness" ] || vibe_die "--strictness is required (relaxed|standard|strict)"

mkdir -p "$workspace"
workspace="$(cd "$workspace" && pwd)"
fail_after="${VIBE_FAIL_AFTER:-}"

checkpoint() {
    [ "$fail_after" = "$1" ] && { vibe_log "error: aborting after $1 (VIBE_FAIL_AFTER)"; exit 1; }
    return 0
}

# A helper that needs a decision exits 3. Init stops there and propagates it: with no answer there is
# nothing further it may safely do for that row, and §7A forbids guessing.
run_helper() {
    local name="$1"; shift
    local status=0
    "$here/migrate/$name" --workspace "$workspace" "$@" || status=$?
    if [ "$status" = 3 ]; then
        vibe_log "decision required by $name — see $workspace/.vibe-suite-state/"
        if [ "$non_interactive" = 1 ]; then
            vibe_log "non-interactive: re-run with the matching --resolve-* or --decline-* flag"
        fi
        exit 3
    fi
    [ "$status" = 0 ] || vibe_die "$name failed with status $status"
}

# ---- phase 1: survey (read-only) and provenance -------------------------------------------------
run_helper survey.sh
checkpoint survey

python3 "$here/lib/init_bridge.py" provenance-open "$workspace"
checkpoint provenance

# ---- phase 2: §7A migration, before any store this install writes -------------------------------
if [ "$decline_config" = 1 ]; then
    vibe_note "rows 1-2: declined — legacy config left in place"
elif [ -n "$resolve_config" ]; then
    # The helper takes a file, not inline JSON — a per-key mapping can exceed a comfortable argv.
    mkdir -p "$workspace/.vibe-suite-state"
    resolution_file="$workspace/.vibe-suite-state/config-resolution.json"
    printf '%s\n' "$resolve_config" > "$resolution_file"
    run_helper migrate-config.sh --resolution "$resolution_file"
else
    run_helper migrate-config.sh
fi
checkpoint migrate-config

run_helper migrate-history.sh
checkpoint migrate-history

if [ "$decline_state" = 1 ]; then
    vibe_note "row 5: declined — legacy stopReviewGate not imported"
elif [ -n "$resolve_state" ]; then
    # No flag exists on the helper: `migrate-state.sh:77` directs the caller to re-run with the value
    # already set in the new store, so the resolution is a write and then a re-invocation.
    python3 "$here/lib/init_bridge.py" set-gate "$workspace" "$resolve_state"
    run_helper migrate-state.sh
else
    run_helper migrate-state.sh
fi
checkpoint migrate-state

case "$confirm_sentinels" in
    yes) run_helper migrate-sentinels.sh --confirm ;;
    no)  vibe_note "row 6: declined — legacy sentinels left registered" ;;
    "")  run_helper migrate-sentinels.sh ;;
    *)   vibe_die "--confirm-sentinels expects yes|no, got '$confirm_sentinels'" ;;
esac
checkpoint migrate-sentinels

# ---- phase 3: bridge steps, each exactly once ---------------------------------------------------
python3 "$here/lib/init_bridge.py" install "$workspace" "$tier" "$depth" "$strictness" "$skip" \
    "${fail_after:-}"

vibe_log "vibe-suite initialised in $workspace"
