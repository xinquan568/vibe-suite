#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
# `/vibe-suite:unbridge` — complete teardown (E2.4 / vibe-21, F1.4).
#
# The inventory in `scripts/lib/bridge.py` is the single source this iterates. F1.4 names that as the
# fix for cc-suite W4: a teardown driven by its own hand-written list misses whatever the installer
# learned to write since.
#
# Usage: unbridge.sh [--workspace DIR] [--confirm]
#   Without --confirm it reports what would be removed, changes nothing, and exits 3.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="." confirm=0
while [ $# -gt 0 ]; do
    case "$1" in
        --workspace) workspace="$2"; shift 2 ;;
        --confirm)   confirm=1; shift ;;
        --help)      sed -n '2,12p' "$0"; exit 0 ;;
        *)           printf 'error: unknown argument: %s\n' "$1" >&2; exit 1 ;;
    esac
done
exec python3 "$here/lib/unbridge.py" "$workspace" "$confirm"
