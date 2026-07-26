#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
# §7A row 6 — cc-suite sentinels → vibe sentinels (E0.8 / vibe-10).
#
# §7A offers this row as one compound transition — "offer re-registration under vibe sentinels +
# removal of old blocks (explicit confirm; provenance-backed)" — and the parenthetical governs the
# whole offer, not the removal alone. So confirmation is sought once, for both halves, and the
# order is forced:
#
#     confirm → write provenance durably → install vibe-* → verify present → remove cc-suite-*
#
# Interrupted anywhere, the workspace holds the old registration or both, never neither. Provenance
# goes first because a record written afterwards cannot make a removal reversible — the crash that
# loses it is the crash that makes it necessary. Provenance also records completed steps, which is
# what makes a re-run finish an interrupted transition instead of restarting it.
#
# An existing vibe-* sentinel is preserved verbatim even if it differs from what this would write:
# new store wins applies to live configuration too.
#
# Usage: migrate-sentinels.sh [--workspace DIR] [--confirm]
#   without --confirm this reports and changes nothing.

set -euo pipefail
# shellcheck source=scripts/migrate/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

workspace="."
confirm=0
while [ $# -gt 0 ]; do
    case "$1" in
        --workspace) workspace="${2:?--workspace needs a directory}"; shift 2 ;;
        --confirm)   confirm=1; shift ;;
        -h|--help)   sed -n '3,22p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) vibe_die "unknown argument: $1" ;;
    esac
done

set +e
VIBE_FAIL_AFTER="${VIBE_FAIL_AFTER:-}" python3 - "$workspace" "$confirm" <<'PY'
import json, os, re, sys
from pathlib import Path

ws, confirm = Path(sys.argv[1]), sys.argv[2] == "1"
provenance = ws / ".vibe-suite-state" / "row6-provenance.json"

# A test hook, and only that: named steps abort immediately after completing, so the ordering can
# be proved rather than asserted. Unset in every real run.
FAIL_AFTER = os.environ.get("VIBE_FAIL_AFTER") or None

LEGACY = re.compile(r"^cc-suite-(mcp|claude-mcp|agent:.+)$")
def vibe_name(legacy):
    return "vibe-" + legacy[len("cc-suite-"):]

mcp_path, toml_path = ws / ".mcp.json", ws / ".codex" / "config.toml"

def read_json(path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: row 6: {path} is not readable JSON: {exc}\n")
        raise SystemExit(1)

def toml_blocks(text):
    """Split TOML into (header, block-text) pairs, preserving everything verbatim."""
    blocks, header, buf = [], None, []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            blocks.append((header, "".join(buf)))
            header, buf = stripped[1:-1].strip(), [line]
        else:
            buf.append(line)
    blocks.append((header, "".join(buf)))
    return blocks

data = read_json(mcp_path) or {}
servers = data.get("mcpServers") if isinstance(data, dict) else None
servers = servers if isinstance(servers, dict) else {}
json_legacy = sorted(name for name in servers if LEGACY.match(name))

toml_text = toml_path.read_text(encoding="utf-8") if toml_path.is_file() else ""
blocks = toml_blocks(toml_text) if toml_text else []
toml_legacy = sorted({
    header.split(".", 1)[1] for header, _ in blocks
    if header and header.startswith("mcp_servers.") and LEGACY.match(header.split(".", 1)[1])
})

if not json_legacy and not toml_legacy:
    sys.stderr.write("note: row 6: no cc-suite sentinels found — nothing to migrate\n")
    raise SystemExit(0)

for name in json_legacy:
    sys.stderr.write(f"note: row 6: .mcp.json carries legacy sentinel {name!r}\n")
for name in toml_legacy:
    sys.stderr.write(f"note: row 6: .codex/config.toml carries legacy sentinel {name!r}\n")

if not confirm:
    sys.stderr.write("row 6: re-registration under vibe-* sentinels and removal of the legacy "
                     "blocks require explicit confirmation.\n")
    sys.stderr.write("Re-run with --confirm to perform the transition. Nothing has been changed.\n")
    raise SystemExit(3)

def checkpoint(step):
    """Record a completed step, then honour the failure hook if it names this step."""
    record = json.loads(provenance.read_text(encoding="utf-8"))
    if step not in record["steps"]:
        record["steps"].append(step)
    tmp = provenance.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(provenance)
    if FAIL_AFTER == step:
        sys.stderr.write(f"error: row 6: aborting after {step} (VIBE_FAIL_AFTER)\n")
        raise SystemExit(1)

# --- step 1: provenance, before any mutation ---------------------------------------------------
if not provenance.is_file():
    if FAIL_AFTER == "start":
        sys.stderr.write("error: row 6: aborting before provenance (VIBE_FAIL_AFTER)\n")
        raise SystemExit(1)
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(json.dumps({
        "row": 6, "schema": 1, "steps": [],
        "legacy": {"mcp.json": json_legacy, "codex/config.toml": toml_legacy},
        "restore": {"mcp.json": {name: servers[name] for name in json_legacy}},
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checkpoint("provenance")
record = json.loads(provenance.read_text(encoding="utf-8"))
done = set(record.get("steps", []))

# --- step 2: register vibe-* in .mcp.json ------------------------------------------------------
if "register-json" not in done and json_legacy:
    added = []
    for name in json_legacy:
        new = vibe_name(name)
        if new in servers:
            sys.stderr.write(f"note: row 6: {new!r} already registered — preserved as it is\n")
            continue
        servers[new] = servers[name]
        added.append(new)
    data["mcpServers"] = servers
    tmp = mcp_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(mcp_path)
    sys.stderr.write(f"note: row 6: registered {len(added)} vibe sentinel(s) in .mcp.json\n")
    checkpoint("register-json")

# --- step 3: register vibe-* in .codex/config.toml ---------------------------------------------
if "register-toml" not in done and toml_legacy:
    present = {header.split(".", 1)[1] for header, _ in blocks
               if header and header.startswith("mcp_servers.")}
    appended = []
    for name in toml_legacy:
        new = vibe_name(name)
        if new in present:
            sys.stderr.write(f"note: row 6: {new!r} already registered — preserved as it is\n")
            continue
        source = next(text for header, text in blocks if header == f"mcp_servers.{name}")
        appended.append(source.replace(f"[mcp_servers.{name}]", f"[mcp_servers.{new}]", 1))
    if appended:
        body = toml_text if toml_text.endswith("\n") or not toml_text else toml_text + "\n"
        toml_path.write_text(body + "".join(appended), encoding="utf-8")
        toml_text = toml_path.read_text(encoding="utf-8")
        blocks = toml_blocks(toml_text)
    sys.stderr.write(f"note: row 6: registered {len(appended)} vibe sentinel(s) in "
                     ".codex/config.toml\n")
    checkpoint("register-toml")

# --- step 4: verify both registrations before removing anything --------------------------------
verified = True
if json_legacy:
    current = read_json(mcp_path).get("mcpServers", {})
    missing = [vibe_name(n) for n in json_legacy if vibe_name(n) not in current]
    if missing:
        sys.stderr.write(f"error: row 6: .mcp.json is missing {missing} — refusing to remove "
                         "anything\n")
        verified = False
if toml_legacy:
    headers = {h for h, _ in toml_blocks(toml_path.read_text(encoding="utf-8")) if h}
    missing = [vibe_name(n) for n in toml_legacy if f"mcp_servers.{vibe_name(n)}" not in headers]
    if missing:
        sys.stderr.write(f"error: row 6: .codex/config.toml is missing {missing} — refusing to "
                         "remove anything\n")
        verified = False
if not verified:
    raise SystemExit(1)
checkpoint("verified")

# --- step 5: only now, remove the superseded blocks ---------------------------------------------
if json_legacy:
    current = read_json(mcp_path)
    for name in json_legacy:
        current.get("mcpServers", {}).pop(name, None)
    tmp = mcp_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(mcp_path)
if toml_legacy:
    kept = [text for header, text in toml_blocks(toml_path.read_text(encoding="utf-8"))
            if not (header and header.startswith("mcp_servers.")
                    and header.split(".", 1)[1] in toml_legacy)]
    toml_path.write_text("".join(kept), encoding="utf-8")
checkpoint("pruned")
sys.stderr.write("note: row 6: transition complete — vibe sentinels registered, legacy blocks "
                 "removed, provenance retained\n")
PY
status=$?
set -e
exit "$status"
