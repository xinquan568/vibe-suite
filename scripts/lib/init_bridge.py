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

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bridge  # noqa: E402
import store as store_mod  # noqa: E402
import config as config_mod  # noqa: E402

STRICTNESS = {"relaxed": 60, "standard": 70, "strict": 80}

#: Every artefact init owns. The codec table names seven; `config-fill` and `history-baseline` add
#: two more, and those two merge into content migration may just have written.
TARGETS = (".gitignore", "AGENTS.md", "CLAUDE.md", "GEMINI.md", ".codex/config.toml",
           ".mcp.json", ".codex/hooks.json", ".vibe-suite.md", ".claude/vibe-history.json")

PROVENANCE = ".vibe-suite-state/install-provenance.json"


def _valid_target(entry):
    """A restore entry must carry what its kind needs, or it is not a restore source.

    An entry naming an expected path is not evidence it can restore that path: a `file` without its
    bytes or digest, or a `symlink` without a target, would silently restore nothing.
    """
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        return False
    kind = entry.get("kind")
    if kind == "absent":
        return True
    if kind == "symlink":
        return isinstance(entry.get("link_target"), str)
    if kind == "file":
        if not all(isinstance(entry.get(k), str) for k in ("mode", "sha256", "content_b64")):
            return False
        try:
            raw = base64.b64decode(entry["content_b64"], validate=True)
        except Exception:
            return False
        return hashlib.sha256(raw).hexdigest() == entry["sha256"]
    return False


def provenance_open(ws):
    """Record the pre-image of every target before the first mutation.

    `kind` comes from `lstat`, so a broken symlink classifies as a symlink and restores from its
    target. A directory where a file belongs is refused: `mode` cannot capture directory contents,
    so recording it would claim a recoverability the record does not have.
    """
    ws = Path(ws)
    out = ws / PROVENANCE
    bridge.assert_inside(ws, out)
    if bridge.classify(out) == "symlink":
        raise bridge.BridgeError(f"{out} is a symlink; refusing to treat it as a restore source")
    if out.is_file():
        # Write once. A second run's "pre-image" is the installed state, so rewriting would discard
        # the only record of what the workspace looked like before the suite touched it. An existing
        # record is still checked: a truncated or foreign file at this path would otherwise be
        # trusted as a restore source it cannot serve.
        existing = bridge.load_json(out)
        if (not isinstance(existing, dict) or existing.get("schema") != bridge.SCHEMA
                or not isinstance(existing.get("targets"), list)
                or not isinstance(existing.get("parents_created"), list)
                or not all(_valid_target(t) for t in existing["targets"])
                or len(existing["targets"]) != len(TARGETS)
                or {t["path"] for t in existing["targets"]} != {str(ws / rel) for rel in TARGETS}):
            raise bridge.BridgeError(
                f"{out} exists but is not a v{bridge.SCHEMA} provenance record; refusing to "
                "continue, because unbridge would treat it as one")
        return
    # The plugin version at install time, so a later doctor can tell an upgrade from a fresh
    # install. Recorded here because provenance is the only artefact written once, before anything.
    manifest = bridge.load_json(Path(__file__).resolve().parent.parent.parent
                                / ".claude-plugin" / "plugin.json")
    record = {"schema": bridge.SCHEMA, "targets": [], "parents_created": [],
              "plugin_version": manifest.get("version")}
    parents = []
    for rel in TARGETS + (PROVENANCE,):
        dest = ws / rel
        bridge.assert_inside(ws, dest)
        if rel != PROVENANCE:
            record["targets"].append(bridge.record_pre_image(dest))
        for parent in bridge.parents_created(ws, dest):
            if parent not in parents:
                parents.append(parent)
    record["parents_created"] = parents
    out.parent.mkdir(parents=True, exist_ok=True)
    bridge.write_atomic(ws, out, json.dumps(record, indent=2, sort_keys=True) + "\n")


def set_gate(ws, value):
    """Row 5's resolution. The helper takes no flag: `migrate-state.sh:77` directs the caller to
    re-run with the value already in the new store, and `overrides()` reads the nested leaf."""
    if value not in ("true", "false"):
        raise bridge.BridgeError(f"--resolve-state expects true|false, got '{value}'")
    wanted = value == "true"
    store = store_mod.Store(ws)
    # `Store.set` replaces the file unconditionally, so a resumed run carrying the same flag would
    # change state.json's mtime and break AC-2. `overrides()` reports what is genuinely stored —
    # `get()` masks absence behind the fresh default.
    if store.overrides().get("gate", {}).get("stop_review_gate") == wanted:
        return
    store.set("gate.stop_review_gate", wanted)


def _split_front(text):
    """(newline, frontmatter lines, trailing body), line-ending agnostic.

    An LF-only reader treats a CRLF config's frontmatter as body and writes a *second* block above
    it — which does not fail, and silently hides every setting the file already carried. Line endings
    are a property of the user's file, not an assumption this module gets to make.
    """
    newline = "\r\n" if "\r\n" in text.split("\n", 1)[0] + "\n" else "\n"
    bom = "\ufeff" if text.startswith("\ufeff") else ""
    stripped = text[len(bom):]
    first = stripped.split("\n", 1)[0].strip()
    if first == "---":
        head_len = stripped.index("\n") + 1
        rest = stripped[head_len:]
        # Mixed endings are real: a file edited on two platforms can open CRLF and close LF. Both
        # closers are searched and the *earliest* wins, so a later match cannot swallow the body.
        best = None
        for candidate in ("\r\n---\r\n", "\n---\n"):
            end = rest.find(candidate)
            if end != -1 and (best is None or end < best[0]):
                best = (end, candidate)
        if best:
            end, candidate = best
            return bom + newline if bom else newline, rest[:end].splitlines(), \
                rest[end + len(candidate):]
    return (bom + newline) if bom else newline, [], text


def _verify_config(ws, text):  # noqa: D401
    """Validate with the canonical *validating* load, not a bare parse.

    `parse_frontmatter` only checks the grammar: it accepts `effort: sonnet` happily, while
    `config.py`'s value checks reject it because the enum is `low|medium|high`. Parsing alone would
    have shipped exactly the invalid config this check exists to prevent, so the candidate is written
    to a scratch workspace and loaded the way every downstream consumer loads it.
    """
    # Validated against the **real** workspace: `config.py` resolves path-valued keys against the
    # root and refuses ones that escape it, so a scratch directory would clear a config the actual
    # project rejects. The candidate is staged beside the target and removed either way.
    ws = Path(ws)
    staged = ws / f".{config_mod.CONFIG_FILENAME}.vibe-candidate"
    real = ws / config_mod.CONFIG_FILENAME
    if real.is_symlink():
        # `os.replace` below is a direct rename: it does not go through `write_atomic`, so the
        # symlink refusal there never sees this path. Replacing the link would convert the user's
        # link into a regular copy of its target — the exact conversion teardown cannot undo, since
        # it records `kind: symlink` and never restores one.
        raise bridge.BridgeError(
            f"{real} is a symlink; replacing it would convert the user's link into a regular copy "
            f"and could not be undone by /vibe-suite:unbridge. Remove or re-point it and re-run")
    keep = real.read_bytes() if real.is_file() else None
    try:
        bridge.write_atomic(ws, staged, text)
        os.replace(staged, real)
        config_mod.load(str(ws))
    except Exception as exc:
        raise bridge.BridgeError(
            f"refusing to write a config the canonical loader rejects: {exc}") from exc
    finally:
        if keep is None:
            real.unlink(missing_ok=True)
        else:
            real.write_bytes(keep)
        staged.unlink(missing_ok=True)


def _upsert_text(ws, rel, name, body, markdown=False):
    dest = Path(ws) / rel
    existing = bridge.read_text_verbatim(dest)
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


def repair_step(ws, step, values):
    """One bridge step, by name, from stored settings.

    `install()` runs the whole sequence and stops at the first raise. Repair needs them one at a
    time — F1.3 requires collecting failures and continuing — so the bodies live here and both
    callers use them rather than each keeping its own copy.
    """
    ws = Path(ws)
    effort, sandbox = values["effort"], values["sandbox"]
    depth, threshold = values["depth"], values["threshold"]
    if step == "memory":
        memory = ("Project memory for vibe-suite. Commands ship under the `/vibe-suite:` namespace.\n"
                  f"Codex effort: {effort}. Sandbox: {sandbox}. Audit depth: {depth}.")
        _upsert_text(ws, "AGENTS.md", "memory", memory, markdown=True)
        for name in ("CLAUDE.md", "GEMINI.md"):
            _upsert_text(ws, name, "import", "@AGENTS.md", markdown=True)
    elif step == "codex":
        _upsert_text(ws, ".codex/config.toml", "server:vibe-mcp",
                     '[mcp_servers.vibe-mcp]\ncommand = "vibe-suite"')
    elif step == "mcp":
        _upsert_json(ws, ".mcp.json", lambda d: bridge.json_server_upsert(
            d, "vibe-mcp", {"command": "vibe-suite", "args": []}))
        _upsert_json(ws, ".codex/hooks.json", lambda d: bridge.json_hook_entry_upsert(
            d, "Stop", {"type": "command", "command": "vibe-suite stop-gate"}))
    elif step == "gitignore":
        _upsert_text(ws, ".gitignore", "ignore", ".vibe-suite-state/\n.claude/vibe-reports/")
    elif step == "history":
        _history_baseline(ws, threshold if threshold is not None else 70)
    else:
        raise bridge.BridgeError(f"unknown repair step: {step}")


def install(ws, effort, sandbox, depth, strictness, skip, fail_after=""):
    ws = Path(ws)

    def checkpoint(step):
        if fail_after == step:
            raise SystemExit(f"error: aborting after {step} (VIBE_FAIL_AFTER)")

    if strictness not in STRICTNESS:
        raise bridge.BridgeError(f"--strictness expects {'|'.join(STRICTNESS)}, got '{strictness}'")

    # config-fill — merge into whatever migration produced; never a fresh overwrite. The keys are
    # `config.py`'s, not this module's: F1.1 asks for Codex **effort** and **sandbox**, and both are
    # schema enums. An earlier revision invented `model_tier` and wrote `effort: sonnet`, which the
    # canonical validator rejects — so every advertised answer produced an unreadable config.
    dest = ws / ".vibe-suite.md"
    existing = bridge.read_text_verbatim(dest)
    values = {"effort": effort, "sandbox": sandbox, "audit_depth": depth,
              "score_threshold": str(STRICTNESS[strictness])}
    patterns = [s.strip() for s in skip.split(",") if s.strip()] if skip else []

    newline, front, rest = _split_front(existing)
    for key, value in values.items():
        if not any(line.strip().startswith(f"{key}:") for line in front):
            front.append(f"{key}: {value}")
    if patterns and not any(line.strip().startswith("skip_patterns:") for line in front):
        front.append("skip_patterns:")
        front.extend(f"  - {pattern}" for pattern in patterns)
    bom, sep = (newline[:1], newline[1:]) if newline.startswith("\ufeff") else ("", newline)
    rendered = bom + sep.join(["---", *front, "---", ""]) + rest
    if not dest.exists():
        # Creating it, not merging into one the user already had — so this marker only ever lands in
        # a file we made. It is what lets `/vibe-suite:unbridge` *prove* the file is ours before
        # deleting it: without it, teardown had to take the provenance record's unauthenticated word,
        # and a record edited to say `absent` would delete a config that predated the install.
        #
        # If the user later removes this line, the file stops being recognisably ours and teardown
        # leaves it alone. That is the correct outcome, not a failure.
        # Keyed on the path not existing, not on empty content: a pre-existing zero-byte file is
        # still the user's, and marking it would claim something we did not create.
        rendered = bridge.md_block_upsert(
            rendered, "config",
            "Created by /vibe-suite:init. Remove this block to keep the file on teardown.")
    if rendered != existing:
        _verify_config(ws, rendered)
        bridge.write_atomic(ws, dest, rendered)
    checkpoint("config-fill")

    memory = ("Project memory for vibe-suite. Commands ship under the `/vibe-suite:` namespace.\n"
              f"Codex effort: {effort}. Sandbox: {sandbox}. Audit depth: {depth}.")
    _upsert_text(ws, "AGENTS.md", "memory", memory, markdown=True)
    for name in ("CLAUDE.md", "GEMINI.md"):
        _upsert_text(ws, name, "import", "@AGENTS.md", markdown=True)
    checkpoint("memory")

    # Marked `server:vibe-mcp`, the same name `toml_server_has`/`_remove` use. An earlier revision
    # wrote it under a generic `codex` marker, so the codec that is supposed to manage it could not
    # find it — the inventory would have been complete and the teardown still incomplete.
    _upsert_text(ws, ".codex/config.toml", "server:vibe-mcp",
                 '[mcp_servers.vibe-mcp]\ncommand = "vibe-suite"')
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
    _history_baseline(ws, STRICTNESS[strictness])
    checkpoint("history-baseline")


def _history_baseline(ws, threshold):
    ws = Path(ws)
    dest = ws / ".claude" / "vibe-history.json"
    # Row 3 copies the legacy history verbatim, and nlpm's canonical shape is a **top-level list**
    # (`tests/test_migrate.py:214`) — not the mapping an earlier revision assumed. Both shapes are
    # live, so the baseline is appended into whichever one is there. `is None` rather than `or`,
    # because an existing empty list is a history, and `[] or {...}` would discard it.
    history = bridge.load_json(dest) if dest.is_file() else None
    if isinstance(history, list):
        snapshots, container = history, history
    elif isinstance(history, dict):
        snapshots = history.setdefault("snapshots", [])
        if not isinstance(snapshots, list):
            raise bridge.BridgeError(
                f"{dest}: 'snapshots' is {type(snapshots).__name__}, not a list; refusing to append")
        container = history
    elif history is None and not dest.is_file():
        # Created by us, so stamped as ours. Teardown needs on-disk proof before deleting a whole
        # file; without it, an edited provenance record was the only evidence, and that is not
        # evidence. A pre-existing history is never stamped, so it is never deleted.
        snapshots = []
        container = {"vibe_suite_owned": True, "snapshots": snapshots}
    else:
        # Valid JSON of an unexpected shape. Replacing it would discard a file the user may care
        # about, and this command has no mandate to decide that.
        raise bridge.BridgeError(
            f"{dest} holds a JSON {type(history).__name__}, not a history; refusing to replace it")
    if not any(isinstance(s, dict) and s.get("baseline") for s in snapshots):
        snapshots.append({"baseline": True, "threshold": threshold})
        bridge.write_atomic(ws, dest, json.dumps(container, indent=2, sort_keys=True) + "\n")


def main(argv):
    try:
        if argv[1] == "provenance-open":
            provenance_open(argv[2])
        elif argv[1] == "set-gate":
            set_gate(argv[2], argv[3])
        elif argv[1] == "install":
            install(argv[2], argv[3], argv[4], argv[5], argv[6], argv[7],
                    argv[8] if len(argv) > 8 else "")
        else:
            print(f"unknown subcommand: {argv[1]}", file=sys.stderr)
            return 2
    except bridge.BridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
