#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
# Shared layer for the §7A migration helpers (E0.8 / vibe-10).
#
# One rule governs every helper that sources this file: the suite never deletes or rewrites a legacy
# store. It copies or derives, leaves the original untouched, and where both stores exist the new
# one wins. Rollback is deleting the new store, because the original was never touched.
#
# Exit contract, shared by every helper:
#   0  done, or nothing to do — always safe to re-run
#   3  a decision is required; a report was written and nothing else changed
#   1  error
#
# Exit 3 exists because §7A asks the user to be consulted (row 2's conflicts, row 6's confirmation)
# and a non-interactive script cannot do that without either blocking on stdin or deciding silently.
# The helper reports; the caller — init, in E2.1 — asks and re-invokes with the answer.

set -euo pipefail

# Exported, not merely readonly: these are the interface this library offers the helpers that
# source it, and exporting says so where a bare `readonly` would look like dead weight.
declare -rx VIBE_EXIT_OK=0
declare -rx VIBE_EXIT_ERROR=1
declare -rx VIBE_EXIT_DECISION=3

# ---------------------------------------------------------------------------- reporting

vibe_log()  { printf '%s\n' "$*" >&2; }
vibe_note() { printf 'note: %s\n' "$*" >&2; }
vibe_warn() { printf 'warning: %s\n' "$*" >&2; }
vibe_die()  { printf 'error: %s\n' "$*" >&2; exit "$VIBE_EXIT_ERROR"; }

# vibe_redact <text> — strip credentials from anything that may carry a remote URL.
# Applied to every string this layer prints, because a token embedded in a clone URL would
# otherwise reach stdout, a log file, and CI output.
vibe_redact() {
    printf '%s' "$1" | sed -E 's#(://)[^/@[:space:]]+@#\1***@#g'
}

vibe_report_url() { printf '%s\n' "$(vibe_redact "$1")"; }

# ---------------------------------------------------------------------------- new-store precedence

# vibe_safe_write <path> <<< content — writes only when the destination does not exist.
# "New store wins" in its most common form: if the new store is already there, the migration has
# nothing to say about it. Returns 0 whether it wrote or skipped; callers that need to know check
# vibe_exists first.
vibe_safe_write() {
    local dest="$1" tmp
    if [ -e "$dest" ]; then
        vibe_note "$dest already exists — left as it is (new store wins)"
        cat > /dev/null
        return 0
    fi
    # `publish` is create-only by construction — an `O_EXCL` scratch at the destination's mode,
    # fsynced, then linked into place. The old `mktemp` + `mv -f` followed a symlink at `$dest` and
    # `mv -f` would clobber whatever was there.
    mkdir -p "$(dirname "$dest")"
    cat | python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/bridge.py" publish "$(dirname "$dest")" "$dest"
}

vibe_exists() { [ -e "$1" ]; }

# ---------------------------------------------------------------------------- provenance

# vibe_provenance_write <path> <tool> <detail...> — a durable record written BEFORE any mutation.
# Row 6 depends on this ordering: provenance written afterwards cannot make a removal reversible,
# because the crash that loses it is the one that makes it necessary.
vibe_provenance_write() {
    local path="$1" tool="$2"; shift 2
    mkdir -p "$(dirname "$path")"
    {
        printf '{\n'
        printf '  "tool": "%s",\n' "$tool"
        printf '  "schema": 1,\n'
        printf '  "steps": [%s]\n' "$(vibe_json_list "$@")"
        printf '}\n'
    } | python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/bridge.py" write "$(dirname "$path")" "$path" 600
    vibe_fsync_dir "$(dirname "$path")"
}

# vibe_fsync_dir <dir> — flush the directory entry, so a record written before a mutation is really
# on disk when the crash that makes it necessary happens. Without this, the provenance ordering is
# an ordering in the page cache only.
vibe_fsync_dir() {
    python3 -c 'import os,sys
fd = os.open(sys.argv[1], os.O_RDONLY)
try:
    os.fsync(fd)
finally:
    os.close(fd)' "$1"
}

vibe_json_list() {
    local out="" item
    for item in "$@"; do
        [ -n "$out" ] && out="$out, "
        out="$out\"$item\""
    done
    printf '%s' "$out"
}

# vibe_provenance_step <path> <step> — append a completed step, making helpers resumable.
vibe_provenance_step() {
    local path="$1" step="$2"
    [ -f "$path" ] || vibe_die "no provenance at $path"
    python3 - "$path" "$step" "${BASH_SOURCE[0]%/*}/../lib" <<'PY'
import json, sys
from pathlib import Path

path, step, lib = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, lib)
import bridge  # noqa: E402

with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
if step not in data.setdefault("steps", []):
    data["steps"].append(step)

# Through the primitive. The hand-rolled version wrote a **fixed** `.tmp` sibling with `open(...,
# "w")` — no symlink check, and created at the default mode. The provenance record holds complete
# pre-images, so that scratch file was a world-readable copy of a `0600` `.mcp.json`: the very leak
# `c2112ac` closed on the record itself, reopened one path over.
target = Path(path)
bridge.write_atomic(target.parent.parent, target,
                    json.dumps(data, indent=2, sort_keys=True) + "\n",
                    mode=(target.lstat().st_mode & 0o7777) if target.is_file() else 0o600)
PY
}

vibe_provenance_has() {
    local path="$1" step="$2"
    [ -f "$path" ] || return 1
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if sys.argv[2] in d.get("steps",[]) else 1)' \
        "$path" "$step" 2>/dev/null
}

# ---------------------------------------------------------------------------- snapshots

# vibe_snapshot_tree <root> — path, mode, type and content hash for every file beneath <root>.
# Used by the tests to assert that a legacy store came through byte-identical, and by row 8 to
# assert that nothing anywhere changed. Sorted, so two snapshots compare as text.
vibe_snapshot_tree() {
    local root="$1"
    [ -d "$root" ] || { printf '(absent)\n'; return 0; }
    find "$root" -mindepth 1 \( -type f -o -type d -o -type l \) -print0 \
        | LC_ALL=C sort -z \
        | while IFS= read -r -d '' entry; do
            if [ -L "$entry" ]; then
                printf 'l %s -> %s\n' "${entry#"$root"/}" "$(readlink "$entry")"
            elif [ -d "$entry" ]; then
                printf 'd %s\n' "${entry#"$root"/}"
            else
                printf 'f %s %s %s\n' "${entry#"$root"/}" \
                    "$(vibe_mode_of "$entry")" "$(vibe_sha256 "$entry")"
            fi
        done
}

vibe_mode_of() {
    if stat -f '%Lp' "$1" >/dev/null 2>&1; then stat -f '%Lp' "$1"; else stat -c '%a' "$1"; fi
}

vibe_sha256() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
    else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

# ---------------------------------------------------------------------------- decisions

# vibe_decision_report <path> <line...> — write the report that accompanies exit 3.
vibe_decision_report() {
    local path="$1"; shift
    mkdir -p "$(dirname "$path")"
    printf '%s\n' "$@" | python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/bridge.py" write "$(dirname "$path")" "$path"
    vibe_log "decision required — see $path"
}
