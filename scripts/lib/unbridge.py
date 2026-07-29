#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Teardown for `/vibe-suite:unbridge` (E2.4 / vibe-21, F1.4).

**Strip, then compare.** Provenance's `sha256` is the *pre-image* hash, and init changed the target —
so comparing it against the current file detects "init ran", not "the user edited". Removing the
owned region first and comparing the remainder is the test that distinguishes them, and it is what
lets both halves of the acceptance criterion hold at once: byte-identical to pre-init where the user
changed nothing, and untouched user content where they did.

**The record is data, not authority.** `targets` and `parents_created` hold absolute paths and are
only shape-validated by the writer. Every one is re-contained, `lstat`-classified and refused if it
is not what the record claims, before anything is deleted.
"""

import json
import re
import os
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bridge  # noqa: E402
import init_bridge  # noqa: E402

#: Read from `bridge`, never redeclared here — one inventory is what F1.4 requires.
BLOCKS = bridge.OWNED_BLOCKS


def recorded_path(ws, raw):
    """A path from the record, re-anchored to the resolved workspace, or None if it escapes.

    Provenance stores the path `init` was given; this command resolves its workspace. On macOS
    `/var` and `/private/var` name one directory, so a literal comparison rejects legitimate entries
    and — worse — the re-anchoring is also what proves an entry is genuinely inside.
    """
    path = Path(raw)
    try:
        # The *parent* is resolved, never the final component. Resolving the whole path follows a
        # symlink planted at the target, so containment passes and the deletion lands on whatever it
        # points at — verified to destroy a user file.
        anchored = ws / path.parent.resolve().relative_to(ws) / path.name
    except (ValueError, OSError):
        return None
    return anchored


#: **Shared** JSON stores: the tool contributes named keys to a document the user also uses, so only
#: those keys are ours and any foreign key means the file has become theirs.
OWNED_JSON_KEYS = {".mcp.json": ("mcpServers",), ".codex/hooks.json": ("hooks",)}

#: **Exclusive** JSON files: created by the suite, for the suite, with no shared shape. The whole
#: document is ours, so an init-created one is removable whatever it now contains.
EXCLUSIVE_JSON = (".claude/vibe-history.json",)


def markers_sane(text, name, style):
    """Whether this file's owned markers are a clean sequence of non-overlapping pairs.

    `_block_re` matches non-greedily from an opening marker to the *next* closing one. A stray or
    duplicated opening marker therefore makes the match start early and swallow everything up to the
    real block's close — user content included — and the result is then written back. Counting the
    markers first is what turns that from silent data loss into a refusal.
    """
    od, cd = ("<!--", " -->") if style == "md" else ("#", "")
    marker = re.escape(bridge.MARKER)
    opens = [m.start() for m in re.finditer(
        rf"{re.escape(od)} >>> {marker}:{re.escape(name)} v\d+ >>>{re.escape(cd)}", text)]
    closes = [m.start() for m in re.finditer(
        rf"{re.escape(od)} <<< {marker}:{re.escape(name)} <<<{re.escape(cd)}", text)]
    if len(opens) != len(closes):
        return False
    expect = "o"
    for _, kind in sorted([(p, "o") for p in opens] + [(p, "c") for p in closes]):
        if kind != expect:
            return False
        expect = "c" if expect == "o" else "o"
    return True


def json_is_only_ours(rel, doc):
    """Whether a JSON file init created still holds nothing but our own (now empty) structures.

    Checking one known key was not enough: a file whose `mcpServers` we had just emptied could carry
    an unrelated top-level key the user added, and deleting the file took that with it. Any foreign
    key means a *shared* file has become theirs.

    The distinction that matters is shared versus exclusive. `.mcp.json` is a document the user also
    writes; `.claude/vibe-history.json` is ours end to end. Applying the shared rule to an exclusive
    file would strand our own state forever.
    """
    if rel in EXCLUSIVE_JSON:
        return True
    if not isinstance(doc, dict):
        return False
    owned = OWNED_JSON_KEYS.get(rel)
    if owned is None or any(key not in owned for key in doc):
        return False
    for key in owned:
        value = doc.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            return False
        # Presence, not truthiness, and *whose* key rather than whether it is empty.
        # `any(value.values())` read `{"mcpServers": {"mine": {}}}` as empty because an empty dict
        # is falsey, so a user server with blank config did not keep its own file alive. But the
        # inverse — any key at all keeps the file — would strand the empty `{"Stop": []}` we leave
        # behind ourselves. So each nested key is attributed.
        for nested, inner in value.items():
            if not _nested_is_ours(key, nested, inner):
                return False
    return True


def _nested_is_ours(container, nested, inner):
    """Whether an entry inside a shared container is still only ours.

    `.mcp.json` holds server names, which the sentinel vocabulary already decides — a surviving
    foreign name is the user's.

    `.codex/hooks.json` is subtler: `Stop` is an event we *share* with the user, not one we own.
    Our entries are removed by marker, so a `Stop` list that is still populated holds **their**
    hooks. The key is ours only once it is empty.
    """
    if container == "mcpServers":
        return nested in bridge.SENTINEL_LITERALS or nested.startswith(bridge.SENTINEL_PREFIX)
    if container == "hooks":
        return nested == "Stop" and not inner
    return False


def restore(ws, entry, report):
    """Remove what we own. Never write a pre-image back.

    **Init only ever *adds* owned regions** — a block between markers, a named key, a file it
    created. It never rewrites content outside them. So removing those regions *is* the restore, and
    for a project nobody edited the result is byte-identical to pre-init by construction.

    Writing the recorded pre-image back was the source of every user-content-loss defect in this
    file: it cannot tell an untouched file from an edited one without a comparison that keeps getting
    the corner cases wrong, and when it guesses wrong it overwrites work. A teardown that only
    *removes* cannot lose content that way — the guarantee is weaker on paper and one I can actually
    hold.

    The record is still consulted, for one thing only: whether a file existed before init, which is
    what decides remove-the-block versus remove-the-file.
    """
    path = recorded_path(ws, entry["path"])
    if path is None:
        raise bridge.BridgeError(
            f"provenance names a path outside the workspace: {entry['path']}")
    rel = str(path.relative_to(ws))

    st = bridge.lstat_at(ws, rel)
    if st is None:
        report.append(f"{rel}: already gone")
        return
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        report.append(f"{rel}: not a regular file — left alone")
        return

    owned = next(((r, n, c) for r, n, c in BLOCKS if r == rel), None)
    if owned:
        text = bridge.read_text_verbatim(path)
        if not markers_sane(text, owned[1], owned[2]):
            report.append(f"{rel}: owned markers are malformed — left alone, remove the block by hand")
            return
        stripped = (bridge.md_block_remove(text, owned[1]) if owned[2] == "md"
                    else bridge.text_block_remove(text, owned[1]))
        if entry["kind"] == "absent" and not stripped.strip():
            # init created it and nothing of the user's is in it. Empty either because this call
            # stripped the block or because an earlier phase already did — the file's state is what
            # decides, not whether this particular call changed it.
            bridge.unlink_at(ws, rel)
            report.append(f"{rel}: removed")
        elif stripped != text:
            bridge.write_atomic(ws, path, stripped)
            report.append(f"{rel}: owned block removed")
        else:
            report.append(f"{rel}: nothing of ours remains — left alone")
        return

    # Not a block target: JSON handled by json_targets(), everything else is ours only if init
    # created it and nothing has been added since.
    if entry["kind"] == "absent":
        if rel.endswith(".json"):
            if not json_is_only_ours(rel, bridge.load_json(path)):
                report.append(f"{rel}: kept — it holds content that is not ours")
                return
        bridge.unlink_at(ws, rel)
        report.append(f"{rel}: removed")
        return

    report.append(f"{rel}: existed before install — left as it is")


def json_targets(ws, report, dry):
    """`.mcp.json` and `.codex/hooks.json`: structural ownership, so user entries survive."""
    for name in sorted(bridge.inventory_enumerate(ws)) + ["cc-suite-mcp", "cc-suite-claude-mcp"]:
        doc = bridge.load_json(ws / ".mcp.json")
        if bridge.json_server_has(doc, name):
            report.append(f".mcp.json: {name}")
            if not dry:
                bridge.write_atomic(ws, ws / ".mcp.json",
                                    json.dumps(bridge.json_server_remove(doc, name),
                                               indent=2, sort_keys=True) + "\n")
    toml_path = ws / ".codex" / "config.toml"
    if toml_path.is_file():
        text = bridge.read_text_verbatim(toml_path)
        for name in bridge.toml_owned_names(text):
            if bridge.toml_server_has(text, name):
                report.append(f".codex/config.toml: {name}")
                if not dry:
                    text = bridge.toml_server_remove(text, name)
        if not dry:
            bridge.write_atomic(ws, toml_path, text)
    hooks = bridge.load_json(ws / ".codex" / "hooks.json")
    if bridge.json_hook_entry_has(hooks, "Stop"):
        report.append(".codex/hooks.json: owned Stop entry")
        if not dry:
            bridge.write_atomic(ws, ws / ".codex" / "hooks.json",
                                json.dumps(bridge.json_hook_entry_remove(hooks, "Stop"),
                                           indent=2, sort_keys=True) + "\n")


def prune(ws, record, report):
    """Directories init created — removed only when empty, since a user may have filled one."""
    for raw in sorted(record.get("parents_created") or [], key=len, reverse=True):
        path = recorded_path(ws, raw)
        if path is None:
            report.append(f"{raw}: outside the workspace, left alone")
            continue
        st = bridge.lstat_at(ws, str(path.relative_to(ws)))
        if st and stat.S_ISDIR(st.st_mode) and not any(path.iterdir()):
            bridge.unlink_at(ws, str(path.relative_to(ws)))
            report.append(f"{path.relative_to(ws)}/: removed")


def main(argv):
    ws = Path(argv[1]).resolve()
    confirm = argv[2] == "1"
    provenance = ws / init_bridge.PROVENANCE
    if not provenance.is_file() and not bridge.inventory_enumerate(ws):
        print("nothing to remove: no vibe-suite artefacts are registered here")
        return 0
    record = bridge.load_json(provenance)
    if not isinstance(record, dict) or not isinstance(record.get("targets"), list):
        print("error: no usable provenance record; unbridge restores from it and will not guess "
              "what to remove", file=sys.stderr)
        return 1

    report = []
    if not confirm:
        for entry in record["targets"]:
            candidate = recorded_path(ws, entry["path"])
            if candidate and bridge.classify(candidate) != "absent":
                report.append(f"{candidate.name}: would be restored or removed")
        json_targets(ws, report, dry=True)
        print("\n".join(report))
        print("\nThis removes every vibe-suite artefact above **and** any legacy cc-suite "
              "registrations. Re-run with --confirm.", file=sys.stderr)
        return 3

    json_targets(ws, report, dry=False)
    for entry in record["targets"]:
        restore(ws, entry, report)
    prune(ws, record, report)
    state = ws / ".vibe-suite-state"
    if state.is_symlink():
        report.append(".vibe-suite-state/: a symlink, not a directory — left alone")
    elif state.is_dir():
        # Depth-first over entries that are themselves not symlinks: a link inside would otherwise
        # be followed and take its target with it.
        for child in sorted(state.rglob("*"), key=lambda c: len(str(c)), reverse=True):
            bridge.unlink_at(ws, str(child.relative_to(ws)))
        bridge.unlink_at(ws, ".vibe-suite-state")
        report.append(".vibe-suite-state/: removed")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except bridge.BridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
