#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
# §7A rows 4, 7, 8 and 10 — detect and report (E0.8 / vibe-10).
#
# These four rows share one property: none of them produces an artifact. Row 4's reports are
# point-in-time and are not copied, row 7 forbids a forced rename, row 8's paths are already
# identical, and row 10 is a recommendation about other plugins. So they share one script, and that
# script's contract is that it changes nothing at all — a property row 8's test asserts over the
# whole workspace, not just over the two directories row 8 names.
#
# Usage: survey.sh [--workspace DIR]
# Writes a JSON report to stdout. Human-readable notes go to stderr. Always exits 0.

set -euo pipefail
# shellcheck source=scripts/migrate/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

workspace="."
while [ $# -gt 0 ]; do
    case "$1" in
        --workspace) workspace="${2:?--workspace needs a directory}"; shift 2 ;;
        -h|--help) sed -n '3,12p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) vibe_die "unknown argument: $1" ;;
    esac
done
[ -d "$workspace" ] || vibe_die "not a directory: $workspace"

findings=()
add() { findings+=("$1"); }

# --- row 4: legacy reports directory is noted, never copied ---------------------------------
if [ -d "$workspace/.claude/nlpm-reports" ]; then
    count="$({ find "$workspace/.claude/nlpm-reports" -type f 2>/dev/null || true; } | wc -l | tr -d ' ')"
    vibe_note "row 4: .claude/nlpm-reports/ present ($count files) — not copied; reports are"
    vibe_note "        point-in-time artifacts. New reports go to .claude/vibe-reports/."
    add "{\"row\": 4, \"kind\": \"legacy-reports-present\", \"path\": \".claude/nlpm-reports\", \"files\": $count, \"action\": \"none\"}"
fi

# --- row 7: both spec paths stay readable; nothing is renamed -------------------------------
# `find` on a missing directory exits non-zero, and under `pipefail` that would take the whole
# script down silently. The absence of the directory is an ordinary case, not a failure.
legacy_specs="$({ find "$workspace/.nlpm-test" -name '*.spec.md' 2>/dev/null || true; } | wc -l | tr -d ' ')"
if [ "$legacy_specs" -gt 0 ]; then
    vibe_note "row 7: $legacy_specs spec(s) under .nlpm-test/ — left where they are. Both paths stay"
    vibe_note "        readable; new specs are written to .vibe-test/."
    add "{\"row\": 7, \"kind\": \"legacy-specs-present\", \"path\": \".nlpm-test\", \"files\": $legacy_specs, \"action\": \"none\"}"
fi

# --- row 8: paths and schemas are identical, so there is nothing to do ----------------------
# Deliberately no filesystem access beyond existence: row 8's contract is that this script does
# nothing, and reading is the most it may ever do.
for path in runs docs/discussion; do
    if [ -d "$workspace/$path" ]; then
        add "{\"row\": 8, \"kind\": \"identical-schema\", \"path\": \"$path\", \"action\": \"none\"}"
    fi
done

# --- row 10: source plugins installed alongside ---------------------------------------------
# VIBE_PLUGIN_ROOT exists so this is testable without touching a real installation.
plugin_root="${VIBE_PLUGIN_ROOT:-$HOME/.claude/plugins}"
if [ -d "$plugin_root" ]; then
    for name in cc-suite nlpm grill-for-claude; do
        if [ -d "$plugin_root/$name" ]; then
            vibe_warn "row 10: the '$name' plugin is installed alongside vibe-suite."
            vibe_warn "        Recommend: uninstall $name — its commands share a namespace with"
            vibe_warn "        vibe-suite's and the collision table in README.md lists the overlaps."
            add "{\"row\": 10, \"kind\": \"source-plugin-installed\", \"plugin\": \"$name\", \"action\": \"recommend-uninstall\", \"recommendation\": \"uninstall $name\"}"
        fi
    done
fi

printf '{\n  "helper": "survey",\n  "findings": [\n'
for index in "${!findings[@]}"; do
    printf '    %s' "${findings[$index]}"
    [ "$index" -lt $(( ${#findings[@]} - 1 )) ] && printf ','
    printf '\n'
done
printf '  ]\n}\n'
exit "$VIBE_EXIT_OK"
