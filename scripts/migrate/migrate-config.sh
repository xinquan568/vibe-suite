#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
# §7A rows 1 and 2 — `.cc-suite.md` + `.claude/nlpm.local.md` → `.vibe-suite.md` (E0.8 / vibe-10).
#
# §7A merges the two in one run, so they are one script. Where they disagree the user is asked
# once — once meaning one interruption, not one answer covering every key. A user shown three
# conflicts may keep cc-suite's value for one and nlpm's for the others, so the resolution is a
# per-key mapping and a resolution that does not cover every reported key is an error.
#
# The new file is written by `scripts/lib/config.py`, which owns the schema and its grammar. No
# other artifact — this script included — knows how `.vibe-suite.md` is spelled.
#
# Usage: migrate-config.sh [--workspace DIR] [--resolution FILE]
#   exit 0  written, or nothing to do
#   exit 3  conflicts — see .vibe-suite-state/migration-conflicts.json; nothing was written
#   exit 1  error

set -euo pipefail
# shellcheck source=scripts/migrate/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

workspace="."
resolution=""
while [ $# -gt 0 ]; do
    case "$1" in
        --workspace)  workspace="${2:?--workspace needs a directory}"; shift 2 ;;
        --resolution) resolution="${2:?--resolution needs a file}"; shift 2 ;;
        -h|--help) sed -n '3,17p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) vibe_die "unknown argument: $1" ;;
    esac
done

lib="$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)"
set +e
python3 - "$workspace" "$lib" "$resolution" <<'PY'
import importlib.util, json, re, sys
sys.path.insert(0, sys.argv[2])
import bridge  # noqa: E402
from pathlib import Path

workspace, lib, resolution = sys.argv[1], sys.argv[2], sys.argv[3]

spec = importlib.util.spec_from_file_location("vibe_config", Path(lib) / "config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

ws = Path(workspace)
target = ws / config.CONFIG_FILENAME
if target.exists():
    sys.stderr.write(f"note: rows 1-2: {config.CONFIG_FILENAME} already exists — left as it is "
                     "(new store wins)\n")
    raise SystemExit(0)

# --- row 1: `.cc-suite.md` is bold-label bullets, not frontmatter -------------------------------
# Mapped by label. `Default model` becomes `model_overrides.codex` because cc-suite's commands run
# on Codex, so a per-engine override is where that value means the same thing in the new schema.
CC_LABELS = {
    "default effort": ("effort", None),
    "default audit type": ("audit_depth", None),
    "default sandbox": ("sandbox", None),
    "default model": ("model_overrides", "codex"),
}
_BULLET = re.compile(r"^\s*[-*]\s+\*\*(?P<label>[^*]+)\*\*\s*:\s*(?P<value>.+?)\s*$")

cc_values, cc_path = {}, ws / ".cc-suite.md"
if cc_path.is_file():
    for line in cc_path.read_text(encoding="utf-8").splitlines():
        match = _BULLET.match(line)
        if not match:
            continue
        label = match.group("label").strip().lower()
        if label not in CC_LABELS:
            continue
        key, sub = CC_LABELS[label]
        value = match.group("value").strip().strip("`")
        cc_values[key if sub is None else f"{key}.{sub}"] = value

# --- row 2: `.claude/nlpm.local.md` is frontmatter the shared reader can parse -------------------
nlpm_values, nlpm_path = {}, ws / ".claude" / "nlpm.local.md"
if nlpm_path.is_file():
    try:
        parsed = config.parse_frontmatter(nlpm_path.read_text(encoding="utf-8"), str(nlpm_path))
    except config.ConfigSyntaxError as exc:
        sys.stderr.write(f"error: row 2: {exc}\n")
        raise SystemExit(1)
    for key, value in parsed.items():
        if key in config.SCHEMA:
            # Flatten one level so a map supplied whole (`model_overrides: {codex: x}`) compares
            # against the same map supplied per leaf (`model_overrides.codex`). Comparing at the top
            # level lets two sources disagree about one leaf without registering a conflict, and the
            # later merge then picks one silently.
            if isinstance(value, dict) and config.SCHEMA[key].type == "map":
                for sub, sub_value in value.items():
                    nlpm_values[key + "." + sub] = sub_value
            else:
                nlpm_values[key] = value
        else:
            sys.stderr.write(f"note: row 2: {key!r} has no equivalent in the new schema — not "
                             "migrated\n")

if not cc_values and not nlpm_values:
    sys.stderr.write("note: rows 1-2: no legacy configuration found — nothing to migrate\n")
    raise SystemExit(0)

# --- merge, asking once about anything the two disagree on --------------------------------------
SOURCES = {"cc-suite": cc_values, "nlpm": nlpm_values}
conflicts = {
    key: {"cc-suite": cc_values[key], "nlpm": nlpm_values[key]}
    for key in set(cc_values) & set(nlpm_values)
    if cc_values[key] != nlpm_values[key]
}

chosen = {}
if conflicts:
    report = ws / ".vibe-suite-state" / "migration-conflicts.json"
    if not resolution:
        report.parent.mkdir(parents=True, exist_ok=True)
        # A fixed path is a path the user may own, and the stamp lets a re-run recognise its own
        # report instead of truncating whatever is there.
        if report.is_symlink():
            sys.stderr.write(f"error: rows 1-2: {report} is a symlink; refusing\n")
            raise SystemExit(1)
        if report.is_file():
            prior = bridge.load_json(report)
            if not (isinstance(prior, dict) and prior.get("vibe_suite_owned") is True):
                sys.stderr.write(f"error: rows 1-2: {report} exists and is not ours; refusing\n")
                raise SystemExit(1)
        bridge.write_atomic(ws, report,
                            json.dumps({"rows": [1, 2], "conflicts": conflicts,
                                        "vibe_suite_owned": True},
                                       indent=2, sort_keys=True) + "\n")
        sys.stderr.write(f"decision required — {len(conflicts)} conflicting key(s); see {report}\n")
        sys.stderr.write("Re-run with --resolution FILE mapping each key to 'cc-suite' or 'nlpm'.\n")
        raise SystemExit(3)
    try:
        answers = json.loads(Path(resolution).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: --resolution {resolution}: {exc}\n")
        raise SystemExit(1)
    missing = sorted(set(conflicts) - set(answers))
    if missing:
        sys.stderr.write("error: resolution does not cover every reported key: "
                         + ", ".join(missing) + "\n")
        raise SystemExit(1)
    for key in conflicts:
        source = answers[key]
        if source not in SOURCES:
            sys.stderr.write(f"error: resolution for {key!r}: expected 'cc-suite' or 'nlpm'\n")
            raise SystemExit(1)
        chosen[key] = SOURCES[source][key]

merged = {}
for key, value in list(nlpm_values.items()) + list(cc_values.items()):
    merged.setdefault(key, value)
merged.update(chosen)

# Dotted keys land in their nested map.
mapping = {}
for key, value in merged.items():
    if "." in key:
        head, _, sub = key.partition(".")
        mapping.setdefault(head, {})[sub] = value
    else:
        mapping[key] = value

try:
    rendered = config.render(mapping)
except config.ConfigValueError as exc:
    sys.stderr.write(f"error: rows 1-2: legacy value is not valid in the new schema: {exc}\n")
    raise SystemExit(1)

# Through the primitive: it refuses a symlinked target (a dangling one reports False from
# `exists()`), picks a scratch name that cannot collide with a user's file, and carries the
# destination's prior mode.
bridge.write_atomic(ws, target, rendered,
                    mode=(target.lstat().st_mode & 0o7777) if target.is_file() else None)
sys.stderr.write(f"note: rows 1-2: wrote {config.CONFIG_FILENAME} from "
                 f"{len(merged)} legacy value(s); originals untouched\n")
PY
status=$?
set -e
exit "$status"
