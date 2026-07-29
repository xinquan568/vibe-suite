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
    """Delegates to the codec's validator so teardown cannot drift from what removal accepts.

    This lived here first, which is precisely why `.codex/config.toml` stayed exposed: a guard beside
    one caller is not a guard on the operation.
    """
    od, cd = ("<!--", " -->") if style == "md" else ("#", "")
    return bridge.markers_wellformed(text, name, od, cd)


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
        # An actual empty list, not anything falsey. `not inner` classified `{"Stop": false}` as
        # ours and unlinked the file — the same truthiness mistake this function was written to fix,
        # one level down.
        return nested == "Stop" and isinstance(inner, list) and len(inner) == 0
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
        if rel in EXCLUSIVE_FILES:
            # Checked here, before the shared-store branch. `json_is_only_ours` returns True
            # unconditionally for an exclusive file, so routing these through it made the
            # corroboration below unreachable — a guard that never ran.
            if not _is_recognisably_ours(rel, path):
                report.append(f"{rel}: kept — nothing identifies it as ours; remove it by hand")
                return
        elif rel.endswith(".json"):
            if not json_is_only_ours(rel, bridge.load_json(path)):
                report.append(f"{rel}: kept — it holds content that is not ours")
                return
        elif not _is_recognisably_ours(rel, path):
            # `kind: absent` says the installer created this file, and the record is not
            # authenticated — so on its own it cannot authorise deleting a whole file. A file the
            # installer created is one it can still recognise; anything else stays, as residue.
            report.append(f"{rel}: kept — nothing identifies it as ours; remove it by hand")
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


#: Files init creates **whole**, with no shared shape and no owned block to look for. Their content
#: cannot corroborate ownership because all of it is ours, so `kind` is the only signal available.
#:
#: That is a real limit, and it is bounded rather than closed: the provenance record lives inside
#: `.vibe-suite-state/`, so forging it needs write access to the workspace — the same access needed
#: to delete these files outright. Corroboration buys nothing against an attacker who already has it,
#: and for the accidental-corruption case the duplicate and allowed-path checks in `validate_record`
#: are what catch a record that has drifted.
EXCLUSIVE_FILES = (".vibe-suite.md", ".claude/vibe-history.json")


#: What the suite writes into `.vibe-suite-state/`. Anything else in there is the user's.
SUITE_STATE = ("install-provenance.json", "state.json", "config.json", "jobs.json", "history.json",
               "config-resolution.json", "row6-decision.json", "row6-provenance.json",
               "migration-conflicts.json", "migration-conflicts.txt")
#: `migrate-state.sh:32` writes `.txt`; the earlier entry said `.md` and matched nothing.
#:
#: These migration artefacts carry no `vibe_suite_owned` stamp, so they are *left behind* rather than
#: removed — recorded residue, and the safe direction: an artefact of ours surviving teardown costs
#: the user nothing, while deleting a file we cannot prove is ours costs them everything.


def _is_suite_state(relative, path=None):
    """Whether a path inside `.vibe-suite-state/` is one the suite wrote.

    **A matching name is not proof of ownership.** A user's own `state.json` sitting here before
    install has the same name as ours, and deleting it on the name alone is the very mistake the
    allowlist was added to fix, one level down. So the file's *content* has to carry our schema.
    Anything we cannot recognise is left behind — a suite artefact surviving teardown is a
    reduction; a user's file not surviving it is not.
    """
    parts = relative.parts
    if not parts:
        return False
    if len(parts) != 1 or path is None:
        # A directory prefix is not ownership either: `.vibe-suite-state/jobs/notes.txt` is the
        # user's file in a directory we happen to use.
        return False
    if Path(path).is_symlink():
        return False  # judged before any name shortcut: the link is what would be deleted
    if parts[0] == "install-provenance.json":
        return True   # we are reading it right now; nothing else writes it
    if parts[0] not in SUITE_STATE:
        return False
    # `load_json` follows a symlink, so the *destination's* stamp was being read as ownership of the
    # *link* — and a user's link pointing at any stamped file of ours was unlinked. The link is what
    # would be deleted, so the link is what must be judged.
    doc = bridge.load_json(path)
    # An explicit ownership stamp, not a generic `schema` key a user's own JSON may also carry.
    return isinstance(doc, dict) and doc.get("vibe_suite_owned") is True


def _is_recognisably_ours(rel, path):
    """Whether a file's *content* still identifies it as the installer's own.

    Independent corroboration for `kind: absent`, which is otherwise an unauthenticated record's
    unsupported word. A file init only *contributes a block to* is ours only while that block is
    present; once it is gone the file is the user's, whatever the record says.
    """
    if rel in EXCLUSIVE_FILES:
        # Corroborated on disk, not taken from the record. `kind: absent` is mutable, unauthenticated
        # metadata: an entry edited to say `absent` *and* stripped of its pre-image fields is
        # internally consistent, so validation cannot catch it and a file that predated the install
        # would be deleted.
        #
        # init writes an owned marker into these when it *creates* them, which is what makes the
        # proof possible — and F1.4's two clauses then both hold, instead of trading one for the
        # other. A user who deletes the marker keeps their file; that is the intended outcome.
        if rel.endswith(".json"):
            doc = bridge.load_json(path)
            return isinstance(doc, dict) and doc.get("vibe_suite_owned") is True
        # The exact well-formed block through the shared codec. `bridge.MARKER in text` was a
        # substring test for "vibe-suite", which a migrated `skip_patterns: [vibe-suite]` satisfies —
        # so an unmarked config would have been deleted wholesale on a coincidence.
        return bridge.md_block_has(bridge.read_text_verbatim(path), "config")
    text = bridge.read_text_verbatim(path)
    if not text.strip():
        return True  # created and since emptied; nothing of anyone's is in it
    for owned_rel, name, style in BLOCKS:
        if owned_rel == rel:
            return (bridge.md_block_has(text, name) if style == "md"
                    else bridge.text_block_has(text, name))
    return bridge.MARKER in text


def validate_record(ws, record):
    """Every mutation this command performs is directed by the provenance record, so the record is
    authority — and authority that is only shape-checked is authority a tampered file inherits.

    Checking `targets` was a list let an entry rewritten to
    `{"path": "<ws>/notes.txt", "kind": "absent"}` make `restore()` unlink an arbitrary user file,
    and a forged `parents_created` remove an empty user directory. The paths init can legitimately
    have touched are a **closed, known set**, so the record is checked against that set rather than
    trusted to describe itself.

    Returns a list of complaints; empty means usable.
    """
    problems = []
    if not isinstance(record, dict):
        return ["the provenance record is not an object"]
    targets = record.get("targets")
    if not isinstance(targets, list):
        return ["the provenance record has no targets list"]

    # Both sides go through `realpath`. The record holds the path as the *caller* gave it, while
    # `main` resolves the workspace, so on macOS an honest record reads `/var/...` against an
    # expected `/private/var/...`. Comparing raw strings rejects every real install.
    allowed = {os.path.realpath(ws / rel) for rel in init_bridge.TARGETS}
    seen = []
    for entry in targets:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            problems.append("a target entry is not an object with a path")
            continue
        kind = entry.get("kind")
        if kind not in ("absent", "file", "symlink", "dir"):
            problems.append(f"{entry['path']}: unknown kind {kind!r}")
        else:
            # `kind` and the pre-image fields are written together, so they must agree. Flipping a
            # `file` entry to `absent` to make teardown delete the user's file leaves those fields
            # behind — which is what makes an accidentally or deliberately edited record detectable
            # without authenticating it.
            pre_image = {"mode", "sha256", "content_b64", "link_target"} & set(entry)
            if kind == "absent" and pre_image:
                problems.append(
                    f"{entry['path']}: recorded absent but carries {', '.join(sorted(pre_image))}; "
                    f"the kind and the pre-image disagree")
            if kind == "file" and not {"sha256", "content_b64"} <= set(entry):
                problems.append(f"{entry['path']}: recorded as a file without its pre-image")
            if kind == "symlink" and "link_target" not in entry:
                problems.append(f"{entry['path']}: recorded as a symlink without its target")
        resolved = os.path.realpath(entry["path"])
        if resolved not in allowed:
            problems.append(f"{entry['path']}: not a path this installer writes")
        seen.append(resolved)
    # Exactly one entry per target. A duplicate `absent` entry appended beside an honest `file` one
    # named the same path twice with two different meanings, and the destructive reading won.
    for path in sorted(set(seen)):
        if seen.count(path) > 1:
            problems.append(f"{path}: named by {seen.count(path)} entries; expected exactly one")
    missing = allowed - set(seen)
    if missing:
        problems.append(f"the record is missing {len(missing)} of the installer's own targets")

    parents = record.get("parents_created") or []
    if not isinstance(parents, list):
        problems.append("parents_created is not a list")
    else:
        # A created parent can only be an ancestor directory of a target, never a target itself and
        # never anything else in the tree.
        ancestors = {os.path.realpath(ws / ".vibe-suite-state")}
        for rel in init_bridge.TARGETS:
            for parent in (ws / rel).parents:
                if parent == ws or ws in parent.parents:
                    ancestors.add(os.path.realpath(parent))
        for raw in parents:
            if not isinstance(raw, str) or os.path.realpath(raw) not in ancestors:
                problems.append(f"{raw}: not a directory this installer creates")
    return problems


def main(argv):
    ws = Path(argv[1]).resolve()
    confirm = argv[2] == "1"
    # Before the record is read, before anything is validated, before any path-based read: fix what
    # "this workspace" means. Everything after is checked against this directory.
    try:
        bridge.pin_root(ws)
    except OSError as exc:
        print(f"error: {ws} could not be opened safely ({exc})", file=sys.stderr)
        return 1
    provenance = ws / init_bridge.PROVENANCE
    if not provenance.is_file() and not bridge.inventory_enumerate(ws):
        print("nothing to remove: no vibe-suite artefacts are registered here")
        return 0
    record = bridge.load_json(provenance)
    problems = validate_record(ws, record)
    if problems:
        print("error: the provenance record is not usable; unbridge is directed entirely by it and "
              "will not act on one it cannot vouch for:", file=sys.stderr)
        for problem in problems[:10]:
            print(f"  - {problem}", file=sys.stderr)
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
        # Only what the suite puts there. `rglob("*")` deleted every child, so anything a user had
        # placed in this directory before install — it is a plain directory, nothing stops them —
        # was destroyed by a command that is supposed to remove only what it owns.
        for child in sorted(state.rglob("*"), key=lambda c: len(str(c)), reverse=True):
            rel = str(child.relative_to(ws))
            if _is_suite_state(child.relative_to(state), child):
                bridge.unlink_at(ws, rel)
            else:
                report.append(f"{rel}: not a suite state file — left alone")
        # Depth-first above, so the directory is empty here exactly when everything in it was ours.
        if not any(state.iterdir()):
            bridge.unlink_at(ws, ".vibe-suite-state")
            report.append(".vibe-suite-state/: removed")
        else:
            report.append(".vibe-suite-state/: kept — it still holds files that are not ours")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except bridge.BridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
