#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# Append one structured event to the ledger.
#
#   . auditor/scripts/log-event.sh
#   log_event discover search_complete '{"candidates":42,"new":15}'
#
# Every record is the envelope E8.2a wired all 18 emitters and ten ledger readers to:
#
#   {"timestamp":…, "workflow":…, "event":…, "run_id":…, "run_number":…, "data":{…}}
#
# TWO PARTS OF THAT SHAPE ARE LOAD-BEARING and each is mutation-tested:
#
#   * the payload lives NESTED under `data`, never spread across the top level. Spreading it
#     produces a record that still parses and still carries every field, so a shape check
#     passes — while a payload key named `event` or `timestamp` silently overwrites the
#     envelope and every reader keying on those fields mis-attributes the record.
#   * `run_number` is a NUMBER. Emitting it as a string yields valid JSON that sorts and
#     compares wrongly: "10" < "9" lexically, so run ordering inverts exactly where it matters.
#
# A payload that is not valid JSON is wrapped as `{"raw": "<text>"}` rather than dropped — an
# event that cannot be parsed is still evidence that something happened, and losing it silently
# is worse than recording it awkwardly.
#
# The ledger path follows M-1: <data-dir>/ledgers/events.jsonl, from AUDITOR_DATA_DIR or `.`.

log_event() {
  local workflow="$1" event="$2" data="${3:-}"
  local data_dir="${AUDITOR_DATA_DIR:-.}"
  local ledger="$data_dir/ledgers/events.jsonl"
  local timestamp run_id run_number
  timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  run_id="${GITHUB_RUN_ID:-local}"
  run_number="${GITHUB_RUN_NUMBER:-0}"

  [ -n "$data" ] || data='{}'

  if ! mkdir -p "$data_dir/ledgers" 2>/dev/null; then
    echo "log-event: could not create $data_dir/ledgers (event lost: $workflow/$event)" >&2
    return 1
  fi
  if ! command -v jq >/dev/null 2>&1; then
    echo "log-event: jq not on PATH (event lost: $workflow/$event)" >&2
    return 1
  fi

  # `tonumber? // 0` keeps run_number numeric even when the environment supplies junk.
  local envelope='{timestamp:$ts, workflow:$wf, event:$ev, run_id:$rid,
                   run_number:($rn|tonumber? // 0), data:.}'

  if printf '%s' "$data" | jq -c \
       --arg ts "$timestamp" --arg wf "$workflow" --arg ev "$event" \
       --arg rid "$run_id" --arg rn "$run_number" \
       "$envelope" >> "$ledger" 2>/dev/null; then
    echo "[$workflow] $event: $data"
    return 0
  fi

  # Payload was not JSON: keep the event, mark the payload raw.
  if jq -cn \
       --arg ts "$timestamp" --arg wf "$workflow" --arg ev "$event" \
       --arg rid "$run_id" --arg rn "$run_number" --arg d "$data" \
       '{timestamp:$ts, workflow:$wf, event:$ev, run_id:$rid,
         run_number:($rn|tonumber? // 0), data:{raw:$d}}' >> "$ledger"; then
    echo "[$workflow] $event: $data (payload raw-wrapped)"
    return 0
  fi

  echo "log-event: both writes failed (event lost: $workflow/$event)" >&2
  return 1
}

# Commit accumulated ledger entries. Takes the checkout explicitly rather than assuming the
# working directory (M-3): these helpers run from the data checkout while their siblings are
# resolved from the code checkout, so an implicit cwd is how the wrong repository gets committed.
commit_logs() {
  local checkout="${1:?commit_logs: checkout path required}" message="${2:-ledger update}"
  git -C "$checkout" config user.name "vibe-suite-auditor"
  git -C "$checkout" config user.email "auditor@users.noreply.github.com"
  git -C "$checkout" add ledgers/events.jsonl
  if git -C "$checkout" diff --cached --quiet; then
    return 0
  fi
  git -C "$checkout" commit -m "log: $message"
}
