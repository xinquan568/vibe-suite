#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# Publish an already-committed data change as a pull request.
#
# The workflow commits; this helper publishes. That split is deliberate and differs from the
# reference implementation, which expects staged changes and commits them itself. Our
# auditor-track workflow rewrites the registry, and those rewrites race the other stages, so
# track composes its own commit and never pushes straight at the data branch — the run's work
# goes up on a branch and lands through a PR. Ownership of the commit therefore belongs to the
# workflow, and this helper's job starts after it.
#
#   commit-via-pr.sh --checkout PATH --repo OWNER/NAME --base BRANCH --branch BRANCH
#
# WHAT `--base` MEANS. It is the freshly fetched remote ref `refs/remotes/origin/<base>`, never
# the local branch. After committing on a checked-out `auditor-data`, local HEAD *is* the tip of
# local `auditor-data`, so comparing against the local branch would refuse every normal call.
# The remote ref is the only definition that separates "already committed locally" from
# "nothing changed".
#
# Then: HEAD equal to the fetched base means there is nothing to publish; the fetched base being
# an ancestor of HEAD means publishable; anything else means the commit is stale, unrelated, or
# built on the wrong branch, and is refused rather than force-pushed over.
#
# TOKENS. PAT_TOKEN is preferred because PAT-created PRs trigger downstream workflows, which a
# GITHUB_TOKEN-created PR does not. GH_TOKEN is accepted with a warning. The token is used
# ephemerally and never written to .git/config, a remote URL, the output, or the PR body.
#
# Every refusal exits non-zero and prints one exact `REFUSE:commit-via-pr:<reason>` diagnostic,
# so a caller can branch on the reason rather than parse prose.

set -uo pipefail

die() { printf 'REFUSE:commit-via-pr:%s\n' "$1" >&2; exit 1; }

CHECKOUT=""; REPO=""; BASE=""; BRANCH=""
while [ $# -gt 0 ]; do
  case "$1" in
    --checkout) CHECKOUT="${2:-}"; shift 2 ;;
    --repo)     REPO="${2:-}";     shift 2 ;;
    --base)     BASE="${2:-}";     shift 2 ;;
    --branch)   BRANCH="${2:-}";   shift 2 ;;
    *) printf 'REFUSE:commit-via-pr:unknown-argument %s\n' "$1" >&2; exit 1 ;;
  esac
done

[ -n "$CHECKOUT" ] || die checkout-required
[ -n "$REPO" ]     || die repo-required
[ -n "$BASE" ]     || die base-required
[ -n "$BRANCH" ]   || die branch-required

[ -d "$CHECKOUT" ] || die checkout-missing
git -C "$CHECKOUT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die not-a-git-worktree

printf '%s' "$REPO" | grep -Eq '^[^/[:space:]]+/[^/[:space:]]+$' || die invalid-repo
git check-ref-format "refs/heads/$BASE"   >/dev/null 2>&1 || die invalid-base
git check-ref-format "refs/heads/$BRANCH" >/dev/null 2>&1 || die invalid-branch
[ "$BASE" != "$BRANCH" ] || die branch-equals-base

TOKEN="${PAT_TOKEN:-${GH_TOKEN:-}}"
[ -n "$TOKEN" ] || die token-missing
if [ -z "${PAT_TOKEN:-}" ]; then
  printf 'WARN:commit-via-pr:using-GH_TOKEN\n' >&2
fi

if [ -n "${GITHUB_REPOSITORY:-}" ]; then
  [ "$(printf '%s' "$GITHUB_REPOSITORY" | tr '[:upper:]' '[:lower:]')" = "$(printf '%s' "$REPO" | tr '[:upper:]' '[:lower:]')" ] \
    || die repository-mismatch
fi

ORIGIN="$(git -C "$CHECKOUT" remote get-url origin 2>/dev/null)" || die origin-missing
[ -n "$ORIGIN" ] || die origin-missing
# Normalise only the forms we can verify. An alias or an unrecognised URL is refused rather
# than assumed correct: pushing to the wrong repository is not a recoverable mistake.
NORMALISED="$(printf '%s' "$ORIGIN" | sed -E \
  -e 's#^ssh://git@github\.com/#https://github.com/#' \
  -e 's#^git@github\.com:#https://github.com/#' \
  -e 's#^https://github\.com/##' \
  -e 's#\.git$##')"
printf '%s' "$NORMALISED" | grep -Eq '^[^/[:space:]]+/[^/[:space:]]+$' || die origin-unverifiable
[ "$(printf '%s' "$NORMALISED" | tr '[:upper:]' '[:lower:]')" = "$(printf '%s' "$REPO" | tr '[:upper:]' '[:lower:]')" ] \
  || die repository-mismatch

HEAD_SHA="$(git -C "$CHECKOUT" rev-parse --verify 'HEAD^{commit}' 2>/dev/null)" || die head-missing

# The tree must be settled. Staged or unstaged leftovers mean the caller's commit did not
# capture everything it meant to, and publishing a partial change is worse than refusing.
git -C "$CHECKOUT" diff --cached --quiet 2>/dev/null || die staged-changes
git -C "$CHECKOUT" diff --quiet 2>/dev/null         || die unstaged-changes
[ -z "$(git -C "$CHECKOUT" ls-files --others --exclude-standard 2>/dev/null)" ] || die untracked-files

git -C "$CHECKOUT" ls-remote --heads origin >/dev/null 2>&1 || die remote-unreachable
[ -n "$(git -C "$CHECKOUT" ls-remote --heads origin "$BASE" 2>/dev/null)" ] || die base-not-found

git -C "$CHECKOUT" fetch --no-tags origin "+refs/heads/$BASE:refs/remotes/origin/$BASE" \
  >/dev/null 2>&1 || die base-fetch-failed
BASE_SHA="$(git -C "$CHECKOUT" rev-parse --verify "refs/remotes/origin/$BASE^{commit}" 2>/dev/null)" \
  || die base-ref-missing

[ "$HEAD_SHA" != "$BASE_SHA" ] || die nothing-to-publish
git -C "$CHECKOUT" merge-base --is-ancestor "$BASE_SHA" "$HEAD_SHA" 2>/dev/null \
  || die head-not-descendant-of-base

remote_branch_sha() {
  git -C "$CHECKOUT" ls-remote --heads origin "$BRANCH" 2>/dev/null | awk '{print $1}' | head -1
}
EXISTING="$(remote_branch_sha)" || die branch-query-failed

if [ -z "$EXISTING" ]; then
  # No force, ever. If the push loses a race the remote is re-queried and the outcome decided
  # from what is actually there.
  if ! git -C "$CHECKOUT" push origin "$HEAD_SHA:refs/heads/$BRANCH" >/dev/null 2>&1; then
    AFTER="$(remote_branch_sha)"
    if [ -z "$AFTER" ]; then die push-failed
    elif [ "$AFTER" != "$HEAD_SHA" ]; then die branch-collision
    fi
  fi
elif [ "$EXISTING" != "$HEAD_SHA" ]; then
  die branch-collision
fi

export GH_TOKEN="$TOKEN"
OPEN="$(gh pr list --repo "$REPO" --base "$BASE" --head "$BRANCH" --state open \
        --json url --jq '.[].url' 2>/dev/null)" || die pr-query-failed
COUNT="$(printf '%s' "$OPEN" | grep -c . || true)"

if [ "$COUNT" -gt 1 ]; then
  die pr-collision
elif [ "$COUNT" -eq 1 ]; then
  PR_URL="$OPEN"
else
  # A closed or merged PR already consumed this branch and none is open. Reusing that history
  # would republish under a PR somebody already adjudicated; refuse instead of reopening.
  CONSUMED="$(gh pr list --repo "$REPO" --base "$BASE" --head "$BRANCH" --state all \
              --json url --jq '.[].url' 2>/dev/null | grep -c . || true)"
  [ "$CONSUMED" -eq 0 ] || die branch-already-consumed
  gh pr create --repo "$REPO" --base "$BASE" --head "$BRANCH" \
    --title "auditor: $BRANCH" \
    --body "Automated data-branch update published by the auditor pipeline." \
    --label auditor-bot >/dev/null 2>&1 || die pr-create-failed
  PR_URL="$(gh pr list --repo "$REPO" --base "$BASE" --head "$BRANCH" --state open \
            --json url --jq '.[].url' 2>/dev/null)" || die pr-query-failed
fi
[ -n "$PR_URL" ] || die pr-url-missing

# PUBLICATION IS THE POINT. Opening a PR and stopping leaves the data on a branch nobody
# merges: the run reports success, the registry update never reaches auditor-data, and the next
# stage reads stale state. Auto-merge first because it survives required checks that have not
# finished; one synchronous attempt as a fallback where auto-merge is disabled on the repo.
if ! gh pr merge "$PR_URL" --auto --merge >/dev/null 2>&1; then
  if ! gh pr merge "$PR_URL" --merge >/dev/null 2>&1; then
    # The PR and branch are deliberately left intact: the work is published and recoverable by
    # hand. Only the merge failed, and saying so beats deleting the evidence.
    die merge-failed
  fi
fi

printf 'PR_URL=%s\n' "$PR_URL"
