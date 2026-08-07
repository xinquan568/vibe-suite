#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# Resolve a push-race conflict with the right strategy per file.
#
#   bash auditor/scripts/resolve-merge-conflicts.sh --checkout DIR
#
# Called from the push-retry loop after a pull has produced conflicts. Uses git's three merge
# stages: :1 base, :2/:3 ours/theirs — WHICH IS WHICH DEPENDS ON MERGE vs REBASE; see below.
#
# THE STRATEGY DIFFERS PER FILE BECAUSE THE FAILURE MODES DIFFER, and each choice here comes
# from a way the naive default actually lost data:
#
#   registry/repos.json    three-way merge. A two-way ours-wins merge reverts remote updates to
#                          entries this workflow never touched, because ours still holds the
#                          checkout-time value. Entries oscillate between states run after run.
#
#   append-only ledgers    line union. `--ours` DROPS the remote's appended lines outright. When
#                          two audits append concurrently the loser's resolution discarded the
#                          winner's findings, and per-rule metrics undercounted by several times
#                          — every precision figure derived from them was wrong, and nothing
#                          looked broken.
#
#   exemplars/README.md    regenerate from disk. The gallery is a pure function of the corpus,
#                          so after the rebase has staged both sides' exemplars, regenerating
#                          gives the union. Picking a side keeps that side's snapshot and
#                          silently reverts the other's entries.
#
#   everything else        --ours. Preferring theirs silently discards the current workflow's
#                          own work whenever a concurrent push wins the race.
#
# Siblings are resolved relative to THIS script, not the working directory (M-3): the resolver
# runs inside the data checkout while its siblings live in the code checkout, so a cwd-relative
# path finds nothing.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKOUT="${AUDITOR_DATA_DIR:-.}"
while [ $# -gt 0 ]; do
  case "$1" in
    --checkout|--data-dir) CHECKOUT="${2:-}"; shift 2 ;;
    *) echo "REFUSE:resolve-merge-conflicts:unknown-argument $1" >&2; exit 1 ;;
  esac
done
[ -d "$CHECKOUT" ] || { echo "REFUSE:resolve-merge-conflicts:checkout-missing" >&2; exit 1; }

TMP="$(mktemp -d -t vibe-resolve.XXXXXX)"   # per-run: concurrent resolvers must not collide

# WHICH SIDE IS "OURS" DEPENDS ON HOW THE CONFLICT AROSE, and getting it backwards silently
# discards this run's work while the rebase and the push both still succeed.
#
# In a MERGE, stage :2 is our commit and :3 is the incoming one. In a REBASE, git replays our
# commit ONTO upstream, so the roles invert: :2 is UPSTREAM and :3 is the commit being
# replayed — ours. Verified, not assumed: rebase a local change onto a conflicting upstream one
# and `git checkout --ours` yields the UPSTREAM content.
#
# git-push-with-retry.sh calls this after `git pull --rebase`, so the rebase orientation is the
# production path — the one where treating :2 as ours drops the update the retry exists to
# publish.
GIT_DIR_PATH="$(git -C "$CHECKOUT" rev-parse --absolute-git-dir 2>/dev/null || echo)"
if [ -n "$GIT_DIR_PATH" ] && { [ -d "$GIT_DIR_PATH/rebase-merge" ] || [ -d "$GIT_DIR_PATH/rebase-apply" ]; }; then
  OURS_STAGE=3; THEIRS_STAGE=2; OURS_FLAG="--theirs"
  echo "resolve-merge-conflicts: rebase in progress; ours=:3 theirs=:2"
else
  OURS_STAGE=2; THEIRS_STAGE=3; OURS_FLAG="--ours"
fi

trap 'rm -rf "$TMP"' EXIT

conflicted() { git -C "$CHECKOUT" diff --name-only --diff-filter=U 2>/dev/null || true; }

# --- registry: three-way merge -------------------------------------------------------------
if conflicted | grep -qx "registry/repos.json"; then
  echo "resolve: registry/repos.json via three-way merge"
  git -C "$CHECKOUT" show :1:registry/repos.json > "$TMP/base.json" 2>/dev/null || echo '{}' > "$TMP/base.json"
  git -C "$CHECKOUT" show ":$OURS_STAGE:registry/repos.json" > "$TMP/ours.json"
  git -C "$CHECKOUT" show ":$THEIRS_STAGE:registry/repos.json" > "$TMP/theirs.json"
  if ! python3 "$HERE/three-way-merge-registry.py" \
        "$TMP/base.json" "$TMP/ours.json" "$TMP/theirs.json" > "$TMP/merged.json"; then
    echo "REFUSE:resolve-merge-conflicts:registry-merge-failed" >&2
    exit 1
  fi
  # The atomic writer validates before landing; a malformed merge must never reach disk.
  REG_TMP="$TMP/merged.json" bash "$HERE/atomic-registry-write.sh" --data-dir "$CHECKOUT"
  git -C "$CHECKOUT" add registry/repos.json
fi

# --- append-only ledgers: union, deduped --------------------------------------------------
# All FOUR append-only ledgers SCHEMAS.md declares. vocab-advisories.jsonl was missing, so
# it fell through to the ours-wins default and every advisory the other side appended was
# discarded — silently, because the merge succeeded and the file stayed valid JSONL.
for ledger in ledgers/events.jsonl ledgers/findings.jsonl \
              ledgers/disagreements.jsonl ledgers/vocab-advisories.jsonl; do
  if conflicted | grep -qx "$ledger"; then
    echo "resolve: $ledger via line union"
    git -C "$CHECKOUT" show ":$OURS_STAGE:$ledger" > "$TMP/ours.jsonl"
    git -C "$CHECKOUT" show ":$THEIRS_STAGE:$ledger" > "$TMP/theirs.jsonl"
    # theirs first so the remote's earlier lines keep their position; awk drops exact repeats
    # without sorting, so append order is preserved and nothing is duplicated.
    cat "$TMP/theirs.jsonl" "$TMP/ours.jsonl" | awk '!seen[$0]++' > "$CHECKOUT/$ledger"
    git -C "$CHECKOUT" add "$ledger"
  fi
done

# --- exemplar gallery: regenerate ----------------------------------------------------------
if conflicted | grep -qx "exemplars/README.md"; then
  echo "resolve: exemplars/README.md via regenerate-from-disk"
  git -C "$CHECKOUT" checkout "$OURS_FLAG" exemplars/README.md      # clear the conflict marker
  python3 "$HERE/build-exemplar-gallery.py" --data-dir "$CHECKOUT" >/dev/null
  git -C "$CHECKOUT" add exemplars/README.md
fi

# --- everything else: keep this workflow's work --------------------------------------------
conflicted | while read -r path; do
  [ -n "$path" ] || continue
  echo "resolve: $path via --ours"
  git -C "$CHECKOUT" checkout "$OURS_FLAG" "$path"
  git -C "$CHECKOUT" add "$path"
done
