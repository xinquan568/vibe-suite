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
import json, os, sys, hashlib, datetime, tempfile

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

# mkstemp, not a predictable "<target>.vibe-tmp": that name is guessable, and `open(path, "wb")`
# follows a symlink, so anyone able to plant one could have this migration overwrite a file of
# their choosing. mkstemp creates with O_CREAT|O_EXCL, which fails on an existing path of any kind.
directory = os.path.dirname(target_path) or "."
handle, tmp_path = tempfile.mkstemp(dir=directory, prefix=".vibe-history-", suffix=".tmp")
try:
    with os.fdopen(handle, "wb") as out:
        out.write(body)
        out.flush()
        # fchmod on the descriptor, never chmod on the path: a path-based operation after the
        # descriptor closes can be redirected by swapping the name for a symlink, which would both
        # chmod someone else's file and publish the substituted one.
        os.fchmod(out.fileno(), 0o644)
        os.fsync(out.fileno())
    try:
        # link, not replace: it fails if the target exists, so a new store that appeared while
        # this ran still wins. Publication is a single atomic step over a fully written inode.
        os.link(tmp_path, target_path)
    except FileExistsError:
        sys.stderr.write("note: row 3: .claude/vibe-history.json appeared concurrently — left as "
                         "it is (new store wins)\n")
        raise SystemExit(0)
finally:
    try:
        os.unlink(tmp_path)
    except FileNotFoundError:
        pass

fd = os.open(directory, os.O_RDONLY)
try:
    os.fsync(fd)
finally:
    os.close(fd)
PY

vibe_note "row 3: copied .claude/nlpm-history.json → .claude/vibe-history.json with one marker"
vibe_note "        (the original is untouched)"
exit "$VIBE_EXIT_OK"
