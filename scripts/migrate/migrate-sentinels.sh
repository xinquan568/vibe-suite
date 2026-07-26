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
state = ws / ".vibe-suite-state"
provenance = state / "row6-provenance.json"
report_path = state / "row6-decision.json"

# A test hook, and only that: named steps abort immediately after completing, so the ordering can
# be proved rather than asserted. Unset in every real run.
FAIL_AFTER = os.environ.get("VIBE_FAIL_AFTER") or None

LEGACY = re.compile(r"^cc-suite-(mcp|claude-mcp|agent:.+)$")
def vibe_name(legacy):
    return "vibe-" + legacy[len("cc-suite-"):]

mcp_path, toml_path = ws / ".mcp.json", ws / ".codex" / "config.toml"

def write_atomically(path, text):
    """Write through a temporary file in the same directory, then fsync file and directory.

    Row 6 mutates live configuration. A truncating write that is interrupted leaves the user with a
    half-written `.mcp.json` or `config.toml` — which is worse than either outcome this row is
    allowed to produce, because it is not a registration state at all.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".vibe-tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def read_json(path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: row 6: {path} is not readable JSON: {exc}\n")
        raise SystemExit(1)

# --- TOML: split into header-delimited blocks, understanding quoted keys ------------------------
# `[mcp_servers."cc-suite-agent:auditor"]` is the normal spelling for a sentinel whose name carries
# a colon, and `[mcp_servers.cc-suite-mcp.env]` is a subtable of one. A splitter that treats "." as
# a separator unconditionally misses both: the first because the quotes become part of the name,
# the second because the name gains a suffix.
def split_key(text):
    """Split a TOML key path on unquoted dots. Both quote styles are valid TOML."""
    parts, current, quote, index = [], "", None, 0
    while index < len(text):
        char = text[index]
        if quote is None and char in "\"'":
            quote = char
        elif quote is not None and char == quote:
            quote = None
        elif char == "." and quote is None:
            parts.append(current); current = ""; index += 1; continue
        else:
            current += char
        index += 1
    parts.append(current)
    return [part.strip() for part in parts]

def quote_key(name):
    return f'"{name}"' if re.search(r"[^A-Za-z0-9_-]", name) else name

def strip_inline_comment(line):
    """Drop a trailing `# comment`, respecting quotes. `[mcp_servers.x] # note` is a valid header
    and an earlier version did not recognise it as one."""
    quote, index = None, 0
    while index < len(line):
        char = line[index]
        if quote is None and char in "\"'":
            quote = char
        elif quote is not None and char == quote:
            quote = None
        elif char == "#" and quote is None:
            return line[:index].strip()
        index += 1
    return line


def toml_blocks(text):
    blocks, header, buf = [], None, []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        stripped = strip_inline_comment(stripped)
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
            blocks.append((header, "".join(buf)))
            header, buf = stripped[1:-1].strip(), [line]
        else:
            buf.append(line)
    blocks.append((header, "".join(buf)))
    return blocks

def server_of(header):
    """The sentinel a header belongs to, or None. Covers the table and all its subtables."""
    if not header:
        return None
    parts = split_key(header)
    if len(parts) < 2 or parts[0] != "mcp_servers":
        return None
    return parts[1]


def registered(header):
    """The sentinel this header *registers*, or None — the root table only.

    A subtable is not a registration. `[mcp_servers.vibe-mcp.env]` without
    `[mcp_servers.vibe-mcp]` describes the environment of a server that is not declared; treating
    it as "already registered" would skip installing the real table, let verification pass, and
    then prune the only functional legacy block. That is the forbidden neither state reached by a
    route that looks like success.
    """
    parts = split_key(header) if header else []
    if len(parts) != 2 or parts[0] != "mcp_servers":
        return None
    return parts[1]

data = read_json(mcp_path) or {}
servers = data.get("mcpServers") if isinstance(data, dict) else None
servers = servers if isinstance(servers, dict) else {}
json_legacy = sorted(name for name in servers if LEGACY.match(name))

toml_text = toml_path.read_text(encoding="utf-8") if toml_path.is_file() else ""
blocks = toml_blocks(toml_text) if toml_text else []
toml_legacy = sorted({name for name, _ in ((server_of(h), b) for h, b in blocks)
                      if name and LEGACY.match(name)})

if not json_legacy and not toml_legacy:
    sys.stderr.write("note: row 6: no cc-suite sentinels found — nothing to migrate\n")
    raise SystemExit(0)

for name in json_legacy:
    sys.stderr.write(f"note: row 6: .mcp.json carries legacy sentinel {name!r}\n")
for name in toml_legacy:
    sys.stderr.write(f"note: row 6: .codex/config.toml carries legacy sentinel {name!r}\n")

if not confirm:
    # Exit 3 writes a machine-readable report, as the shared exit contract requires: the caller
    # needs to know what it is being asked to confirm, and it cannot parse prose on stderr.
    state.mkdir(parents=True, exist_ok=True)
    write_atomically(report_path, json.dumps({
        "row": 6,
        "decision": "confirm re-registration under vibe-* sentinels and removal of the legacy blocks",
        "register": {".mcp.json": [vibe_name(n) for n in json_legacy],
                     ".codex/config.toml": [vibe_name(n) for n in toml_legacy]},
        "remove": {".mcp.json": json_legacy, ".codex/config.toml": toml_legacy},
        "rerun_with": "--confirm",
    }, indent=2, sort_keys=True) + "\n")
    sys.stderr.write("row 6: re-registration under vibe-* sentinels and removal of the legacy "
                     "blocks require explicit confirmation.\n")
    sys.stderr.write(f"decision required — see {report_path}\n")
    raise SystemExit(3)

def checkpoint(step):
    record = json.loads(provenance.read_text(encoding="utf-8"))
    if step not in record["steps"]:
        record["steps"].append(step)
    write_atomically(provenance, json.dumps(record, indent=2, sort_keys=True) + "\n")
    if FAIL_AFTER == step:
        sys.stderr.write(f"error: row 6: aborting after {step} (VIBE_FAIL_AFTER)\n")
        raise SystemExit(1)

# --- step 1: provenance, before any mutation, recording enough to restore ----------------------
if not provenance.is_file():
    if FAIL_AFTER == "start":
        sys.stderr.write("error: row 6: aborting before provenance (VIBE_FAIL_AFTER)\n")
        raise SystemExit(1)
    state.mkdir(parents=True, exist_ok=True)
    write_atomically(provenance, json.dumps({
        "row": 6, "schema": 1, "steps": [],
        "legacy": {"mcp.json": json_legacy, "codex/config.toml": toml_legacy},
        # Both stores are recorded in restorable form. Recording only the JSON side would make the
        # removal reversible in one file and irreversible in the other.
        "restore": {
            ".mcp.json": {name: servers[name] for name in json_legacy},
            ".codex/config.toml": {
                name: "".join(text for header, text in blocks if server_of(header) == name)
                for name in toml_legacy
            },
        },
    }, indent=2, sort_keys=True) + "\n")
    checkpoint("provenance")
record = json.loads(provenance.read_text(encoding="utf-8"))
done = set(record.get("steps", []))

# --- step 2: register vibe-* in .mcp.json ------------------------------------------------------
if "register-json" not in done and json_legacy:
    for name in json_legacy:
        new = vibe_name(name)
        if new in servers:
            sys.stderr.write(f"note: row 6: {new!r} already registered in .mcp.json — preserved\n")
            continue
        servers[new] = servers[name]
    data["mcpServers"] = servers
    write_atomically(mcp_path, json.dumps(data, indent=2, sort_keys=True) + "\n")
    sys.stderr.write("note: row 6: registered vibe sentinel(s) in .mcp.json\n")
    checkpoint("register-json")

# --- step 3: register vibe-* in .codex/config.toml ---------------------------------------------
if "register-toml" not in done and toml_legacy:
    present = {registered(header) for header, _ in blocks if registered(header)}
    appended = []
    for name in toml_legacy:
        new = vibe_name(name)
        if new in present:
            sys.stderr.write(f"note: row 6: {new!r} already registered in config.toml — preserved\n")
            continue
        # Every block belonging to the sentinel, including its subtables, with only the sentinel
        # segment of each header rewritten.
        for header, text in blocks:
            if server_of(header) != name:
                continue
            parts = split_key(header)
            parts[1] = quote_key(new)
            appended.append(text.replace(f"[{header}]", "[" + ".".join(parts) + "]", 1))
    if appended:
        body = toml_text if (not toml_text or toml_text.endswith("\n")) else toml_text + "\n"
        write_atomically(toml_path, body + "".join(appended))
        toml_text = toml_path.read_text(encoding="utf-8")
        blocks = toml_blocks(toml_text)
    sys.stderr.write("note: row 6: registered vibe sentinel(s) in .codex/config.toml\n")
    checkpoint("register-toml")

# --- step 4: verify BOTH registrations before removing anything --------------------------------
verified = True
if json_legacy:
    current = read_json(mcp_path).get("mcpServers", {})
    missing = [vibe_name(n) for n in json_legacy if vibe_name(n) not in current]
    if missing:
        sys.stderr.write(f"error: row 6: .mcp.json is missing {missing} — refusing to remove "
                         "anything\n")
        verified = False
if toml_legacy:
    have = {registered(h) for h, _ in toml_blocks(toml_path.read_text(encoding="utf-8"))
            if registered(h)}
    missing = [vibe_name(n) for n in toml_legacy if vibe_name(n) not in have]
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
    write_atomically(mcp_path, json.dumps(current, indent=2, sort_keys=True) + "\n")
if toml_legacy:
    kept = [text for header, text in toml_blocks(toml_path.read_text(encoding="utf-8"))
            if server_of(header) not in toml_legacy]
    write_atomically(toml_path, "".join(kept))
checkpoint("pruned")
sys.stderr.write("note: row 6: transition complete — vibe sentinels registered, legacy blocks "
                 "removed, provenance retained\n")
PY
status=$?
set -e
exit "$status"
