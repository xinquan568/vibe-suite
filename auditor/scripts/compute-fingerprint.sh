#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# The finding fingerprint: the join key linking findings.jsonl, finding-outcome events and
# disagreements.jsonl (auditor/SCHEMAS.md §3).
#
#   sha256( "<repo>|<file>|<rule_id>|<pattern>|<line>" )
#
# Absent `file`, `rule_id` and `pattern` contribute the empty string; an absent OR null `line`
# contributes the literal text "null", so a file-level finding and a line-0 finding cannot
# collide.
#
# Two properties are contractual rather than incidental, and each has a test that fails when
# it is broken:
#
#   * the digest covers jq's TRAILING NEWLINE. Stripping it produces a different, equally
#     stable-looking fingerprint, which would silently re-key every historical finding.
#   * a jq parse failure must propagate. Without pipefail the pipeline's status is shasum's,
#     so malformed input would hash the empty string to a valid-looking fingerprint and
#     corrupt the join key with a value that never fails a schema check.
#
# Sourced, not executed:
#   . auditor/scripts/compute-fingerprint.sh
#   fp="$(printf '%s' "$finding_json" | compute_fingerprint "owner/name")"

compute_fingerprint() {
  local repo="$1"
  (
    set -o pipefail
    jq -r --arg repo "$repo" \
      '"\($repo)|\(.file // "")|\(.rule_id // "")|\(.pattern // "")|\(.line // "null")"' \
      | shasum -a 256 \
      | awk '{ print "sha256:" $1 }'
  )
}
