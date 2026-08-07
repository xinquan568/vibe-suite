#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# The vocab-advisory fingerprint. A vocab advisory clusters TERMS rather than locating a single
# file:line, so its join key differs from compute-fingerprint.sh:
#
#   sha256( "<repo>|VOCAB|<sorted,csv,terms>|<disposition>" )
#
# An absent disposition contributes the empty string. Terms are comma-joined with no spaces, and
# as with the finding fingerprint the digest covers jq's trailing newline.
#
# The sort is the whole point. The scanner discovers a cluster's terms in whatever order it
# happens to walk the corpus, so hashing them in SOURCE order would give the same advisory a
# different fingerprint on every run — the join key would never match itself and every
# advisory would look new. Sorting makes the fingerprint a property of the SET.
#
# Changing a cluster's membership does change the fingerprint, and that is intended: a
# different term set is a different advisory, not the same one drifting.
#
# Sourced, not executed:
#   . auditor/scripts/compute-vocab-fingerprint.sh
#   fp="$(printf '%s' "$advisory_json" | compute_vocab_fingerprint "owner/name")"

compute_vocab_fingerprint() {
  local repo="$1"
  (
    set -o pipefail
    jq -r --arg repo "$repo" \
      '"\($repo)|VOCAB|\([.terms[]] | sort | join(","))|\(.disposition // "")"' \
      | shasum -a 256 \
      | awk '{ print "sha256:" $1 }'
  )
}
