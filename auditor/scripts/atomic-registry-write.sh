#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# Validate a staged registry write, then land it atomically.
#
# Callers build the next registry state with jq into a staging file and invoke this to
# validate-and-rename. If the staged file is not valid JSON the move is REFUSED and the caller's
# step fails loudly, leaving the registry on disk exactly as it was.
#
# The ordering is the entire point: VALIDATE FIRST, THEN WRITE. A helper that copies to the
# destination and validates afterwards has already destroyed the good registry by the time it
# discovers the problem, and the registry is the join key for every finding, PR outcome and
# disagreement the pipeline has ever recorded. Silent write-corruption becomes immediate step
# failure instead.
#
# The rename is staged INSIDE the destination directory on purpose. `mv` across filesystems is a
# copy-then-unlink, not a rename(2), and CI runners routinely have /tmp on tmpfs with the
# checkout on another filesystem — so a crash mid-move could leave the registry a truncated
# partial copy. A same-directory tempfile makes the final step a true atomic rename.
#
# Usage:
#   jq <filter> "$DATA_DIR/registry/repos.json" > "$REG_TMP" \
#     && bash auditor/scripts/atomic-registry-write.sh --data-dir "$DATA_DIR"
#
# Options / env:
#   --data-dir DIR   root of the data checkout (default $AUDITOR_DATA_DIR, then .)
#   REG_TMP          staging path (default /tmp/reg.json)
#   REG_DEST         destination (default <data-dir>/registry/repos.json)

set -euo pipefail

DATA_DIR="${AUDITOR_DATA_DIR:-.}"
while [ $# -gt 0 ]; do
  case "$1" in
    --data-dir) DATA_DIR="${2:-}"; shift 2 ;;
    *) echo "REFUSE:atomic-registry-write:unknown-argument $1" >&2; exit 1 ;;
  esac
done

REG_TMP="${REG_TMP:-/tmp/reg.json}"
REG_DEST="${REG_DEST:-$DATA_DIR/registry/repos.json}"

if [ ! -f "$REG_TMP" ]; then
  echo "REFUSE:atomic-registry-write:nothing-staged ($REG_TMP)" >&2
  exit 1
fi

# Validate BEFORE the destination is touched in any way.
if ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$REG_TMP" >/dev/null 2>&1; then
  echo "REFUSE:atomic-registry-write:staged-not-json ($REG_TMP)" >&2
  echo "       the registry on disk is unchanged" >&2
  exit 1
fi

DEST_DIR="$(dirname "$REG_DEST")"
mkdir -p "$DEST_DIR"
STAGED="$(mktemp "$DEST_DIR/.repos.json.XXXXXX")"
trap 'rm -f "$STAGED"' EXIT
cp "$REG_TMP" "$STAGED"
mv "$STAGED" "$REG_DEST"          # same-filesystem rename(2): atomic
trap - EXIT
rm -f "$REG_TMP"                  # consume the staging file so a stale one cannot be re-landed
