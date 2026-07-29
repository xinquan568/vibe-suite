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
lib="$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)"
python3 - "$legacy" "$target" "$lib" <<'PY'
import json, os, sys, hashlib, datetime
from pathlib import Path
sys.path.insert(0, sys.argv[3])
import bridge  # noqa: E402

legacy_path, target_path = sys.argv[1], sys.argv[2]
raw = open(legacy_path, "rb").read()
try:
    text = raw.decode("utf-8")
    data = json.loads(text)
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

# §7A says "copy verbatim", so the original bytes are spliced rather than reserialised. A round
# trip through json.dumps preserves the values and loses the file: key order and whitespace both
# change, and the result is a re-rendering of the history rather than a copy of it.
def markers_in(value):
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict) and "migrated_from" in item]
    return [value] if isinstance(value, dict) and "migrated_from" in value else []

present = markers_in(data)
if len(present) > 1:
    sys.stderr.write(f"error: {legacy_path} already carries {len(present)} migrated_from markers; "
                     "refusing to guess which one is authoritative\n")
    raise SystemExit(1)

stripped = text.rstrip()
if present:
    sys.stderr.write("note: row 3: a migrated_from marker is already present — copied as is\n")
    body = raw
elif isinstance(data, list) and stripped.endswith("]"):
    inner = stripped[:-1].rstrip()
    separator = "" if inner.endswith("[") else ","
    body = (inner + separator + "\n" + json.dumps(marker, indent=2) + "\n]\n").encode("utf-8")
elif isinstance(data, dict) and stripped.endswith("}"):
    inner = stripped[:-1].rstrip()
    separator = "" if inner.endswith("{") else ","
    body = (inner + separator + "\n  \"migrated_from\": "
            + json.dumps(marker["migrated_from"], indent=2) + "\n}\n").encode("utf-8")
else:
    sys.stderr.write(f"error: {legacy_path}: expected a JSON list or object at the top level\n")
    raise SystemExit(1)

# O_EXCL rather than check-then-write: the existence check earlier in this script is advisory, and
# a new store that appears between that check and this write still wins.
# The splice is textual, so the result is validated in memory — before any file exists. Validating
# a file on disk and then publishing it invites a race in between; there is nothing to race with
# here.
check = json.loads(body.decode("utf-8"))
if len(markers_in(check)) != 1:
    sys.stderr.write("error: row 3: the copy does not carry exactly one migrated_from marker\n")
    raise SystemExit(1)

# Through the primitive. `publish_new` is create-only by construction: it writes a scratch file
# with an unpredictable `O_EXCL` name at the destination's mode from the start, fsyncs it, and links
# it into place — so a store that appeared while this ran still wins, which is row 3's rule.
# The source's mode travels with its bytes: a 0600 legacy history holds whatever the user put
# there, and publishing it 0644 exposes exactly that. The workspace is the root, not the
# destination's own parent.
source_mode = os.stat(legacy_path).st_mode & 0o7777
if not bridge.publish_new(Path(target_path).parent.parent, Path(target_path), body,
                          mode=source_mode):
    sys.stderr.write("note: row 3: .claude/vibe-history.json appeared concurrently — left as "
                     "it is (new store wins)\n")
    raise SystemExit(0)

# The directory fsync is `publish_new`'s job now — it fsyncs both the file and its parent before
# returning, so a second one here would be duplicating the primitive's guarantee.
PY

vibe_note "row 3: copied .claude/nlpm-history.json → .claude/vibe-history.json with one marker"
vibe_note "        (the original is untouched)"
exit "$VIBE_EXIT_OK"
