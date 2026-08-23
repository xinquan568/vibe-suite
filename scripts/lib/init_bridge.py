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

#: grill S4 (vibe-191): no `vibe-suite` executable ships with the plugin, so nothing registers one.
#: A host that honoured a bare `vibe-suite` command would resolve it on the operator's PATH to
#: whatever happens to be there. Until the binary ships, init and repair register NOTHING under this
#: name and REMOVE a registration an earlier revision left (it is dangling); when it ships, the
#: registration is an absolute `${CLAUDE_PLUGIN_ROOT}`-based path, never a bare name.
BARE_COMMAND = "vibe-suite"
DANGLING_SERVER = "vibe-mcp"
DANGLING_FILES = (".codex/config.toml", ".mcp.json", ".codex/hooks.json")


def dangling_registrations(ws):
    """The owned registrations that name the bare `vibe-suite` command, by file — what doctor reports
    and what init/repair remove. A `vibe-mcp` entry whose command is something else (an absolute
    path, say) is NOT dangling: that is the shape a shipped binary registers under."""
    ws = Path(ws)
    found = []
    def loaded(rel):
        # an unreadable store is not a dangling registration — doctor reports it as its own finding
        try:
            return bridge.load_json(ws / rel)
        except Exception:
            return {}
    toml = bridge.read_text_verbatim(ws / ".codex" / "config.toml")
    block = bridge._block_re(f"server:{DANGLING_SERVER}", "#", "").search(toml)
    if block and f'command = "{BARE_COMMAND}"' in block.group(0):
        found.append(".codex/config.toml")
    entry = (loaded(".mcp.json").get("mcpServers") or {}).get(DANGLING_SERVER)
    if isinstance(entry, dict) and entry.get("command") == BARE_COMMAND:
        found.append(".mcp.json")
    for hook in (loaded(".codex/hooks.json").get("hooks") or {}).get("Stop") or []:
        if (isinstance(hook, dict) and hook.get(f"_{bridge.MARKER}_owned") is not None
                and str(hook.get("command") or "").split()[:1] == [BARE_COMMAND]):
            found.append(".codex/hooks.json")
            break
    return found


def remove_dangling(ws, only=None):
    """Remove the dangling registrations — all, or those among `only` — through the audited
    writers; returns the files changed. Nothing is created: a file that does not carry one is not
    touched."""
    ws = Path(ws)
    removed = []
    for rel in dangling_registrations(ws):
        if only is not None and rel not in only:
            continue
        if rel == ".codex/config.toml":
            text = bridge.read_text_verbatim(ws / rel)
            bridge.write_atomic(ws, ws / rel, bridge.toml_server_remove(text, DANGLING_SERVER))
        elif rel == ".mcp.json":
            _upsert_json(ws, rel, lambda d: bridge.json_server_remove(d, DANGLING_SERVER))
        elif rel == ".codex/hooks.json":
            _upsert_json(ws, rel, lambda d: bridge.json_hook_entry_remove(d, "Stop"))
        removed.append(rel)
    return removed

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
    # The record holds complete pre-images — every byte of every file it replaced, `.mcp.json`
    # among them. A `0600` file's contents therefore end up inside this one, so writing it at the
    # usual `0644` publishes whatever the user had protected. It is written at the **tightest** mode
    # of anything it records, never looser than `0600`.
    strictest = 0o600
    for entry in record["targets"]:
        mode = entry.get("mode")
        if isinstance(mode, str):
            try:
                strictest &= int(mode, 8)
            except ValueError:
                strictest = 0o600
                break
    bridge.write_atomic(ws, out, json.dumps(record, indent=2, sort_keys=True) + "\n",
                        mode=strictest or 0o600)
    # The directory holding it is traversable by default, so a pre-existing looser mode would
    # undo the file's own protection.
    bridge.secure_dir(ws, Path(PROVENANCE).parent)


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
    have shipped exactly the invalid config this check exists to prevent.

    **Nothing is written.** This used to stage the candidate over the live config, load, and put the
    original back — so the user's file was replaced for the duration of a validation, and the restore
    had to carry bytes *and* mode back. Every defect this function accumulated (a `0600` config
    world-readable through the window, a mode lost on restore, a fixed scratch path) came from that
    swap, and none of it was ever necessary: only containment needs the workspace root, and it takes
    the root as an argument.
    """
    try:
        config_mod.resolve_text(text, str(ws))
    except Exception as exc:
        raise bridge.BridgeError(
            f"refusing to write a config the canonical loader rejects: {exc}") from exc


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


def _ensure_document(ws, rel, empty):
    """Create a target file with its empty document only when nothing is there; never rewrite,
    replace or write through what exists (a user's file stays byte- and mtime-identical; a symlink
    or a directory is left alone). `publish_new` is the tree's create-only primitive: O_EXCL, so a
    file that appears between the probe and the publication wins and is not clobbered; `classify`
    (lstat-based) keeps a symlink — which publish_new would refuse — and a directory out of its way."""
    dest = Path(ws) / rel
    if bridge.classify(dest) == "absent":
        bridge.publish_new(ws, dest, empty)


def _dangling_note(removed):
    if not removed:
        return None
    return (f"removed dangling `{BARE_COMMAND}` registration from " + ", ".join(removed)
            + " (no such binary ships; nothing is registered until it does)")


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
        # grill S4: nothing is registered until the binary ships; a dangling registration an
        # earlier revision left is removed and REPORTED (the outcome carries the note).
        removed = remove_dangling(ws, only=(".codex/config.toml",))
        return _dangling_note(removed)
    elif step == "mcp":
        removed = remove_dangling(ws, only=(".mcp.json", ".codex/hooks.json"))
        return _dangling_note(removed)
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
        # An ownership marker, written only when init *creates* the file — never when merging into
        # one the user already had. It is what lets `/vibe-suite:unbridge` prove the file is ours
        # before deleting it: otherwise teardown takes the provenance record's unauthenticated word,
        # and a record edited to say `absent` deletes a config that predated the install.
        #
        # Remove the block and the file stops being recognisably ours, so teardown leaves it alone.
        # That is the intended outcome — the marker is the claim, so deleting it withdraws the claim.
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

    # grill S4 (vibe-191): no `vibe-suite` binary ships, so NOTHING is registered under that name —
    # a bare command would be resolved on the host's PATH. A registration an earlier revision wrote
    # (`[mcp_servers.vibe-mcp] command = "vibe-suite"`, the `.mcp.json` server, the `Stop` hook
    # `vibe-suite stop-gate`) is dangling and is removed here; the two checkpoints keep their names
    # for VIBE_FAIL_AFTER. When the binary ships it registers an absolute path, never a bare name.
    # The three files stay among the nine targets init creates (empty documents when absent — the
    # provenance record and teardown are built on that set; a file init created is pruned by
    # unbridge exactly as before); only the registration content is gone.
    _ensure_document(ws, ".codex/config.toml", "")
    remove_dangling(ws, only=(".codex/config.toml",))
    checkpoint("codex")

    _ensure_document(ws, ".mcp.json", '{"mcpServers": {}}\n')
    _ensure_document(ws, ".codex/hooks.json", '{"hooks": {}}\n')
    remove_dangling(ws, only=(".mcp.json", ".codex/hooks.json"))
    checkpoint("mcp")

    _upsert_text(ws, ".gitignore", "ignore", ".vibe-suite-state/\n.claude/vibe-reports/")
    checkpoint("gitignore")

    # history-baseline — the append recognises its own marker rather than counting, which is how
    # `migrate-history.sh:60` makes a non-idempotent append safe to repeat.
    _history_baseline(ws, STRICTNESS[strictness])
    checkpoint("history-baseline")

    # advisors — vibe-185 / grill H1b: a definition under .vibe-suite/agents/ is repository content,
    # so init DISCLOSES every declared definition (name, tools, permission mode, cwd, additional
    # dirs, prompt size, whether it is registered) and registers nothing the operator has not named:
    # registration is `/vibe-suite:advisor add <name>` (or `add --all`). The flag-less reconcile
    # still runs — it converges definitions the operator registered before and removes orphaned
    # registrations; a refusal is surfaced, not fatal, and doctor reports the advisor state.
    import advisors
    try:
        rows = advisors.listing(ws)
        for row in rows:
            danger = f"; DANGEROUS: {', '.join(row['dangerous'])}" if row["dangerous"] else ""
            print(f"note: advisor {row['name']}: tools={','.join(row['allowed_tools'])} "
                  f"permission_mode={row['permission_mode']} cwd={row['cwd']} "
                  f"additional_dirs={','.join(row['additional_dirs']) or '-'} "
                  f"prompt={row['prompt_bytes']}B registration={row['registration']}{danger}",
                  file=sys.stderr)
        unregistered = [r["name"] for r in rows if r["registration"] != "registered"]
        if unregistered:
            print("note: init registers no advisor — register one with /vibe-suite:advisor add <name> "
                  "(or add --all after reading the listing): " + ", ".join(unregistered), file=sys.stderr)
        advisors.reconcile(ws)
    except bridge.BridgeError as exc:
        print(f"note: advisor reconcile deferred — {exc}", file=sys.stderr)
    checkpoint("advisors")


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
        # file; an edited provenance record is not proof. A pre-existing history is never stamped,
        # so it is never deleted.
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
