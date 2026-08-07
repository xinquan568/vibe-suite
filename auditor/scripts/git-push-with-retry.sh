#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# Push an already-committed change, reconciling against concurrent writers.
#
#   bash auditor/scripts/git-push-with-retry.sh --checkout DIR [--attempts N]
#
# The auditor pipeline is cron-driven with many concurrent committers, so losing a push race is
# routine rather than exceptional. On each failure this rebases onto the remote and, when the
# rebase conflicts, hands the conflict to resolve-merge-conflicts.sh — which knows the per-file
# strategy that keeps both sides' work.
#
# The caller must have committed already; this owns only the push and the reconciliation.
#
# TWO DETAILS THAT ONLY BITE IN CI:
#
#   * `git rebase --continue` opens $GIT_EDITOR for the commit message. A headless runner has no
#     terminal and usually no EDITOR, so it fails with "Terminal is dumb, but EDITOR unset" —
#     after the conflicts were already resolved correctly. GIT_EDITOR=true accepts the existing
#     message non-interactively.
#   * the rebase-state directories live under the CHECKOUT's .git, not the process's working
#     directory. Probing relative `.git/rebase-merge` silently finds nothing when the helper is
#     invoked from anywhere else, so the rebase is never continued and the loop spins to
#     exhaustion with the work stranded mid-rebase.
#
# Exhaustion is a hard failure. A push that never landed must not look like success, or the run
# reports work it did not publish.

set -uo pipefail

CHECKOUT="${AUDITOR_DATA_DIR:-.}"
ATTEMPTS=3
while [ $# -gt 0 ]; do
  case "$1" in
    --checkout|--data-dir) CHECKOUT="${2:-}"; shift 2 ;;
    --attempts) ATTEMPTS="${2:-3}"; shift 2 ;;
    *) echo "REFUSE:git-push-with-retry:unknown-argument $1" >&2; exit 1 ;;
  esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -d "$CHECKOUT" ] || { echo "REFUSE:git-push-with-retry:checkout-missing" >&2; exit 1; }
git -C "$CHECKOUT" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || { echo "REFUSE:git-push-with-retry:not-a-git-worktree" >&2; exit 1; }

GIT_DIR_PATH="$(git -C "$CHECKOUT" rev-parse --absolute-git-dir 2>/dev/null)" \
  || { echo "REFUSE:git-push-with-retry:no-git-dir" >&2; exit 1; }

unresolved() {
  git -C "$CHECKOUT" status --porcelain=v1 2>/dev/null \
    | grep -qE '^(UU|AA|DD|AU|UA|DU|UD)'
}

for attempt in $(seq 1 "$ATTEMPTS"); do
  if git -C "$CHECKOUT" push; then
    exit 0
  fi
  echo "git-push-with-retry: attempt $attempt/$ATTEMPTS failed; reconciling"

  if git -C "$CHECKOUT" pull --rebase; then
    continue
  fi

  echo "git-push-with-retry: rebase conflicted; invoking the resolver"
  if ! bash "$HERE/resolve-merge-conflicts.sh" --checkout "$CHECKOUT"; then
    echo "REFUSE:git-push-with-retry:resolver-failed" >&2
    exit 1
  fi

  if unresolved; then
    echo "REFUSE:git-push-with-retry:unresolved-conflicts" >&2
    exit 1
  fi

  if [ -d "$GIT_DIR_PATH/rebase-merge" ] || [ -d "$GIT_DIR_PATH/rebase-apply" ]; then
    if ! GIT_EDITOR=true git -C "$CHECKOUT" rebase --continue; then
      echo "REFUSE:git-push-with-retry:rebase-continue-failed" >&2
      exit 1
    fi
  fi
done

echo "REFUSE:git-push-with-retry:exhausted after $ATTEMPTS attempt(s)" >&2
exit 1
