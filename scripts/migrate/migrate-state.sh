#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
# §7A row 5 — import `config.stopReviewGate` from a legacy state dir (E0.8 / vibe-10).
#
# One key, and only when the new store has not already set it. `Store.get()` cannot be used to
# decide that: it returns the fresh default for an absent key, so a stored `false` and an unset key
# are indistinguishable through it. `Store.overrides()` reports what is genuinely present, and that
# is what "new store wins" has to be measured against.
#
# Jobs are ephemeral and are not migrated.
#
# Usage: migrate-state.sh [--workspace DIR] [--legacy-state DIR]...

set -euo pipefail
# shellcheck source=scripts/migrate/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

workspace="."
legacy_dirs=()
while [ $# -gt 0 ]; do
    case "$1" in
        --workspace)    workspace="${2:?--workspace needs a directory}"; shift 2 ;;
        --legacy-state) legacy_dirs+=("${2:?--legacy-state needs a directory}"); shift 2 ;;
        -h|--help) sed -n '3,12p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) vibe_die "unknown argument: $1" ;;
    esac
done
if [ "${#legacy_dirs[@]}" -eq 0 ]; then
    legacy_dirs=("$workspace/.cc-suite-state" "$workspace/.codex-toolkit-state")
fi

report="$workspace/.vibe-suite-state/migration-conflicts.txt"
lib="$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)"

set +e
python3 - "$workspace" "$lib" "$report" "${legacy_dirs[@]}" <<'PY'
import importlib.util, json, os, sys
sys.path.insert(0, sys.argv[2])
import bridge  # noqa: E402
from pathlib import Path

workspace, lib, report = sys.argv[1], sys.argv[2], sys.argv[3]
legacy_dirs = sys.argv[4:]

spec = importlib.util.spec_from_file_location("vibe_store", Path(lib) / "store.py")
store_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store_mod)

KEY = "gate.stop_review_gate"
LEGACY_KEY = "stopReviewGate"

store = store_mod.Store(workspace)
# overrides(), not get(): get() masks absence behind the fresh default. overrides() returns the
# stored sections nested — {"gate": {"stop_review_gate": ...}} — so presence is a two-step lookup,
# not a membership test on a dotted string.
section, _, leaf = KEY.partition(".")
if leaf in store.overrides().get(section, {}):
    sys.stderr.write("note: row 5: gate.stop_review_gate is already set — legacy value not imported\n")
    raise SystemExit(0)

found = {}
for directory in legacy_dirs:
    path = Path(directory) / "state.json"
    if not path.is_file():
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        sys.stderr.write(f"warning: row 5: {path} is not readable JSON — skipped\n")
        continue
    config = data.get("config") if isinstance(data, dict) else None
    if isinstance(config, dict) and LEGACY_KEY in config:
        found[str(path)] = config[LEGACY_KEY]

if not found:
    sys.stderr.write("note: row 5: no legacy config.stopReviewGate found — nothing to import\n")
    raise SystemExit(0)

distinct = set(found.values())
if len(distinct) > 1:
    lines = ["row 5: legacy state directories disagree on config.stopReviewGate.", ""]
    lines += [f"  {path}: {value}" for path, value in sorted(found.items())]
    lines += ["", "Choose one and re-run with the value set in the new store."]
    Path(report).parent.mkdir(parents=True, exist_ok=True)
    # A fixed path is a path the user may own. `lstat`, not `exists` — a dangling symlink reports
    # False and would be followed. The report carries an ownership line so a re-run recognises its
    # own output instead of truncating whatever is there.
    stamp = bridge.MIGRATION_CONFLICTS_STAMP   # vibe-265: one definition, shared with unbridge
    existing = Path(report)
    if existing.is_symlink():
        sys.stderr.write(f"error: row 5: {report} is a symlink; refusing to write through it\n")
        raise SystemExit(1)
    # vibe-265: byte-exact and fail-closed, the same check the teardown uses. `read_text` here
    # translated CRLF/bare CR to LF, so a user's Windows-authored file matched and was overwritten.
    if existing.is_file() and not bridge.stamp_matches(report, stamp):
        sys.stderr.write(f"error: row 5: {report} exists and is not ours; refusing to overwrite\n")
        raise SystemExit(1)
    bridge.write_atomic(Path(sys.argv[1]), Path(report), stamp + "\n".join(lines) + "\n")
    sys.stderr.write(f"decision required — see {report}\n")
    raise SystemExit(3)

value = next(iter(distinct))
if not isinstance(value, bool):
    sys.stderr.write(f"error: row 5: config.stopReviewGate must be true or false\n")
    raise SystemExit(1)

store.set(KEY, value)      # validates and writes atomically
sys.stderr.write(f"note: row 5: imported config.stopReviewGate → {KEY}\n")
PY
status=$?
set -e
exit "$status"
