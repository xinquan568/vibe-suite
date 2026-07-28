#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The bridge-installing half of `/vibe-suite:init` (E2.1 / vibe-18).

Nine targets, five codecs, one provenance record. The shell orchestrator owns phase order and the
§7A decision protocol; this module owns the writes, because JSON and TOML manipulation in bash is
how the sources acquired the defects this merge is fixing.

Every target goes through `bridge.write_atomic` — full-file replacement, fsync, rename, directory
fsync. Two writers stay outside that guarantee and the exclusion is a fact about them, not a choice:
`Store.set` does its own temp-write/replace without fsync (`store.py:109`), and each migration helper
owns its writes.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bridge  # noqa: E402
import store as store_mod  # noqa: E402

STRICTNESS = {"relaxed": 60, "standard": 70, "strict": 80}

#: Every artefact init owns. The codec table names seven; `config-fill` and `history-baseline` add
#: two more, and those two merge into content migration may just have written.
TARGETS = (".gitignore", "AGENTS.md", "CLAUDE.md", "GEMINI.md", ".codex/config.toml",
           ".mcp.json", ".codex/hooks.json", ".vibe-suite.md", ".claude/vibe-history.json")

PROVENANCE = ".vibe-suite-state/install-provenance.json"


def provenance_open(ws):
    """Record the pre-image of every target before the first mutation.

    `kind` comes from `lstat`, so a broken symlink classifies as a symlink and restores from its
    target. A directory where a file belongs is refused: `mode` cannot capture directory contents,
    so recording it would claim a recoverability the record does not have.
    """
    ws = Path(ws)
    out = ws / PROVENANCE
    if out.is_file():
        # Write once. A second run's "pre-image" is the installed state, so rewriting would discard
        # the only record of what the workspace looked like before the suite touched it.
        return
    record = {"schema": bridge.SCHEMA, "targets": [], "parents_created": []}
    for rel in TARGETS:
        dest = ws / rel
        bridge.assert_inside(ws, dest)
        record["targets"].append(bridge.record_pre_image(dest))
        record["parents_created"].extend(bridge.parents_created(ws, dest))
    out.parent.mkdir(parents=True, exist_ok=True)
    bridge.write_atomic(ws, out, json.dumps(record, indent=2, sort_keys=True) + "\n")


def set_gate(ws, value):
    """Row 5's resolution. The helper takes no flag: `migrate-state.sh:77` directs the caller to
    re-run with the value already in the new store, and `overrides()` reads the nested leaf."""
    if value not in ("true", "false"):
        raise bridge.BridgeError(f"--resolve-state expects true|false, got '{value}'")
    store_mod.Store(ws).set("gate.stop_review_gate", value == "true")


def _upsert_text(ws, rel, name, body, markdown=False):
    dest = Path(ws) / rel
    existing = dest.read_text(encoding="utf-8") if dest.is_file() else ""
    updated = (bridge.md_block_upsert(existing, name, body) if markdown
               else bridge.text_block_upsert(existing, name, body))
    if updated != existing:
        bridge.write_atomic(ws, dest, updated)


def _upsert_json(ws, rel, mutate):
    dest = Path(ws) / rel
    doc = bridge.load_json(dest)
    before = json.dumps(doc, indent=2, sort_keys=True)
    doc = mutate(doc)
    after = json.dumps(doc, indent=2, sort_keys=True)
    if after != before or not dest.is_file():
        bridge.write_atomic(ws, dest, after + "\n")


def install(ws, tier, depth, strictness, skip, fail_after=""):
    ws = Path(ws)

    def checkpoint(step):
        if fail_after == step:
            raise SystemExit(f"error: aborting after {step} (VIBE_FAIL_AFTER)")

    if strictness not in STRICTNESS:
        raise bridge.BridgeError(f"--strictness expects {'|'.join(STRICTNESS)}, got '{strictness}'")

    # config-fill — merge into whatever migration produced; never a fresh overwrite.
    dest = ws / ".vibe-suite.md"
    existing = dest.read_text(encoding="utf-8") if dest.is_file() else ""
    lines = [f"model_tier: {tier}", f"audit_depth: {depth}",
             f"score_threshold: {STRICTNESS[strictness]}"]
    if skip:
        lines.append(f"skip_patterns: {skip}")
    if existing.strip():
        body = existing.rstrip("\n") + "\n"
        for line in lines:
            key = line.split(":")[0]
            if f"\n{key}:" not in body:
                body = body.replace("\n---\n", f"\n{line}\n---\n", 1) if body.count("---") >= 2 \
                    else body + line + "\n"
        if body != existing:
            bridge.write_atomic(ws, dest, body)
    else:
        bridge.write_atomic(ws, dest, "---\n" + "\n".join(lines) + "\n---\n")
    checkpoint("config-fill")

    memory = ("Project memory for vibe-suite. Commands ship under the `/vibe-suite:` namespace.\n"
              f"Model tier: {tier}. Audit depth: {depth}.")
    _upsert_text(ws, "AGENTS.md", "memory", memory, markdown=True)
    for name in ("CLAUDE.md", "GEMINI.md"):
        _upsert_text(ws, name, "import", "@AGENTS.md", markdown=True)
    checkpoint("memory")

    _upsert_text(ws, ".codex/config.toml", "codex",
                 "[mcp_servers.vibe-mcp]\ncommand = \"vibe-suite\"")
    checkpoint("codex")

    _upsert_json(ws, ".mcp.json", lambda d: bridge.json_server_upsert(
        d, "vibe-mcp", {"command": "vibe-suite", "args": []}))
    _upsert_json(ws, ".codex/hooks.json", lambda d: bridge.json_hook_entry_upsert(
        d, "Stop", {"type": "command", "command": "vibe-suite stop-gate"}))
    checkpoint("mcp")

    _upsert_text(ws, ".gitignore", "ignore", ".vibe-suite-state/\n.claude/vibe-reports/")
    checkpoint("gitignore")

    # history-baseline — the append recognises its own marker rather than counting, which is how
    # `migrate-history.sh:60` makes a non-idempotent append safe to repeat.
    dest = ws / ".claude" / "vibe-history.json"
    history = bridge.load_json(dest) or {"snapshots": []}
    snapshots = history.setdefault("snapshots", [])
    if not any(isinstance(s, dict) and s.get("baseline") for s in snapshots):
        snapshots.append({"baseline": True, "threshold": STRICTNESS[strictness]})
        bridge.write_atomic(ws, dest, json.dumps(history, indent=2, sort_keys=True) + "\n")
    checkpoint("history-baseline")


def main(argv):
    try:
        if argv[1] == "provenance-open":
            provenance_open(argv[2])
        elif argv[1] == "set-gate":
            set_gate(argv[2], argv[3])
        elif argv[1] == "install":
            install(argv[2], argv[3], argv[4], argv[5], argv[6], argv[7] if len(argv) > 7 else "")
        else:
            print(f"unknown subcommand: {argv[1]}", file=sys.stderr)
            return 2
    except bridge.BridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
