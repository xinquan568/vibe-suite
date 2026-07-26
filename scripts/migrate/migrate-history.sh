#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
# §7A row 3 — `.claude/nlpm-history.json` → `.claude/vibe-history.json` (E0.8 / vibe-10).
#
# Copy verbatim (the schema is unchanged) and append exactly one `migrated_from` marker snapshot.
# "Exactly one" is the whole difficulty: appending is not naturally idempotent, so a second run
# must recognise its own marker rather than add another.
#
# Usage: migrate-history.sh [--workspace DIR]

set -euo pipefail
# shellcheck source=scripts/migrate/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

workspace="."
while [ $# -gt 0 ]; do
    case "$1" in
        --workspace) workspace="${2:?--workspace needs a directory}"; shift 2 ;;
        -h|--help) sed -n '3,9p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) vibe_die "unknown argument: $1" ;;
    esac
done

legacy="$workspace/.claude/nlpm-history.json"
target="$workspace/.claude/vibe-history.json"

[ -f "$legacy" ] || { vibe_note "row 3: no .claude/nlpm-history.json — nothing to migrate"; exit "$VIBE_EXIT_OK"; }

if [ -e "$target" ]; then
    # New store wins. This is also what makes the second run a no-op.
    vibe_note "row 3: .claude/vibe-history.json already exists — left as it is (new store wins)"
    exit "$VIBE_EXIT_OK"
fi

mkdir -p "$(dirname "$target")"
python3 - "$legacy" "$target" <<'PY'
import json, os, sys, hashlib, datetime

legacy_path, target_path = sys.argv[1], sys.argv[2]
raw = open(legacy_path, "rb").read()
try:
    data = json.loads(raw.decode("utf-8"))
except (UnicodeDecodeError, json.JSONDecodeError) as exc:
    sys.stderr.write(f"error: {legacy_path} is not readable JSON: {exc}\n")
    raise SystemExit(1)

marker = {
    "migrated_from": {
        "path": ".claude/nlpm-history.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
}

# The schema is unchanged, so the copy is verbatim and the marker is added alongside it. A list
# history gets the marker appended as one entry; a mapping gets it as one member. Either way there
# is exactly one, and a run that finds one already present adds nothing.
if isinstance(data, list):
    if any(isinstance(item, dict) and "migrated_from" in item for item in data):
        sys.stderr.write("note: row 3: a migrated_from marker is already present — not adding another\n")
    else:
        data.append(marker)
elif isinstance(data, dict):
    if "migrated_from" in data:
        sys.stderr.write("note: row 3: a migrated_from marker is already present — not adding another\n")
    else:
        data["migrated_from"] = marker["migrated_from"]
else:
    sys.stderr.write(f"error: {legacy_path}: expected a JSON list or object at the top level\n")
    raise SystemExit(1)

tmp = target_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, sort_keys=True)
    handle.write("\n")
os.replace(tmp, target_path)
PY

vibe_note "row 3: copied .claude/nlpm-history.json → .claude/vibe-history.json with one marker"
vibe_note "        (the original is untouched)"
exit "$VIBE_EXIT_OK"
