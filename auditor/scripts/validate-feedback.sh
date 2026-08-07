#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# Check the rebuilt rule-health feedback log before anything acts on it.
#
#   bash auditor/scripts/validate-feedback.sh --data-dir DIR [--log PATH]
#
# The feedback log is the dataset that argues for weakening, rewriting or retiring rules. It is
# rebuilt from the event ledger by rule-health.py on every run, which means a bug there quietly
# becomes a rulebook change here. This is the gate between those two facts.
#
# A MISSING LOG IS A FAILURE, NOT A WARNING. The reference implementation prints a note and
# exits 0 when the log is absent, on the theory that a fresh install has no feedback yet. But
# rule-health.py runs BEFORE this and always writes the file, so after bootstrap an absent log
# does not mean "no feedback" — it means the rebuild did not happen or its output was lost. The
# lenient reading turns exactly that failure into a green check, and the consumer downstream
# then reads a stale log, or none, and reports that every rule is healthy. Pass --allow-missing
# only for the genuine pre-bootstrap case.
#
# The four content checks each encode an arithmetic that cannot be true of a real log:
#
#   * INVALID RULE IDS — a rule id outside the catalog's shape means the aggregation keyed on
#     something that is not a rule, so every count under it is attributed to nothing.
#   * NEGATIVE COUNTS — a count is a tally of records; below zero means subtraction happened
#     somewhere that should only ever have added.
#   * merged + rejected > submitted — more findings resolved than were ever sent. Guarantees
#     double-counting upstream, and it is the specific shape that duplicate events produce.
#   * MALFORMED JSON — a partial write. The file parses as a smaller, entirely plausible
#     dataset rather than failing, so nothing else would notice.
#
# Every check reports every violation it finds before exiting, rather than stopping at the
# first: a rebuild bug usually breaks many rows the same way, and seeing one row per run turns
# one fix into twenty runs.

set -uo pipefail

DATA_DIR="${AUDITOR_DATA_DIR:-}"
LOG=""
ALLOW_MISSING=0

while [ $# -gt 0 ]; do
  case "$1" in
    --data-dir) DATA_DIR="${2:-}"; shift 2 ;;
    --log) LOG="${2:-}"; shift 2 ;;
    --allow-missing) ALLOW_MISSING=1; shift ;;
    *) echo "REFUSE:validate-feedback:unknown-argument $1" >&2; exit 1 ;;
  esac
done

if [ -z "$DATA_DIR" ] && [ -z "$LOG" ]; then
  echo "REFUSE:validate-feedback:data-dir-required" >&2
  exit 1
fi
[ -n "$LOG" ] || LOG="$DATA_DIR/feedback/log.json"

if [ ! -f "$LOG" ]; then
  if [ "$ALLOW_MISSING" -eq 1 ]; then
    echo "validate-feedback: $LOG absent (pre-bootstrap; allowed)"
    exit 0
  fi
  echo "REFUSE:validate-feedback:log-missing $LOG" >&2
  exit 1
fi

if ! jq -e . "$LOG" > /dev/null 2>&1; then
  echo "REFUSE:validate-feedback:malformed-json $LOG" >&2
  exit 1
fi

if ! jq -e 'type == "object" and (.rules | type) == "array"' "$LOG" > /dev/null 2>&1; then
  echo "REFUSE:validate-feedback:schema-invalid expected an object with a rules array" >&2
  exit 1
fi

# One jq pass, every violation reported. `rule_id` must look like a catalog id; the counts are
# tallies so none may be negative; and resolutions may not exceed submissions.
VIOLATIONS="$(
  jq -r '
    .rules[]
    | . as $r
    | [
        (if ($r.rule_id // "" | test("^(R[0-9]{1,2}|[a-z]+:R[0-9]{1,2})$")) then empty
         else "invalid-rule-id: \($r.rule_id // "<null>")" end),
        (   [$r | to_entries[] | select((.value | type) == "number" and .value < 0)
             | "negative-count: \($r.rule_id // "<null>").\(.key)=\(.value)"] | .[]),
        (if ((($r.merged // 0) + ($r.rejected // 0)) > ($r.submitted // $r.hits // 0))
         then "resolved-exceeds-submitted: \($r.rule_id // "<null>") merged=\($r.merged // 0) rejected=\($r.rejected // 0) submitted=\($r.submitted // $r.hits // 0)"
         else empty end)
      ]
    | .[]
  ' "$LOG" 2>/dev/null
)" || {
  echo "REFUSE:validate-feedback:unreadable $LOG" >&2
  exit 1
}

if [ -n "$VIOLATIONS" ]; then
  printf '%s\n' "$VIOLATIONS" >&2
  COUNT="$(printf '%s\n' "$VIOLATIONS" | wc -l | tr -d ' ')"
  echo "REFUSE:validate-feedback:invalid $COUNT violation(s)" >&2
  exit 1
fi

RULES="$(jq -r '.rules | length' "$LOG")"
echo "validate-feedback: $LOG ok ($RULES rule(s))"
