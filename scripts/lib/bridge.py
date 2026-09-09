#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Ownership marking, containment, atomic writes and provenance for the bridge (E2.1 / vibe-18).

**The filesystem-safety kernel lives in `scripts/lib/fsafe.py`** (split out of this file by M9 / vibe-223):
containment (`assert_root`/`assert_inside`/`classify`), the `O_NOFOLLOW` descent with its root pin, the mutation
primitives that ride the descent, `write_atomic`/`publish_new`, and the refusal classes `BridgeError`/`AbsentPath`.
This module imports it as `fsafe` and re-exports nothing; the anchored writes below build on it.

**This module owns the sentinel inventory**, and it is the only place that owns it. F1.4 requires the
teardown to iterate a single source — *"fixes cc-suite W4 (incomplete teardown) by making the sentinel
inventory the single source the script iterates"* — so `init`, `bridge`, `repair` and `unbridge` all
read from here. Two independently-maintained lists is the W4 defect itself.

`vibe-mcp` and `vibe-claude-mcp` are literal names. **`vibe-agent:` is a prefix**, not a name: the
concrete agents exist only at runtime, so the inventory exports a rule and an enumerator rather than
three strings.

**Five codecs, because the nine owned targets share no syntax.** JSON has no comments, so ownership
there is structural — a named key under `mcpServers`, or an entry inside an event array carrying its
own marker. A single comment-delimited block cannot express either.

**`OWNED_TARGETS` is the one inventory of what init owns in a workspace** (M12 / vibe-220): nine
paths, each with its codec and the block names or JSON keys that are ours (six marker blocks among
them). `TARGETS` and `OWNED_BLOCKS` are derived from it here; `init`, `doctor`, `bridge`, `repair`
and `unbridge` read those derivations, and `unbridge`'s JSON-key and exclusive-file views derive
from the same rows. Three hand-held views of "what is ours" is the W4 defect one level up.
"""

import base64
import hashlib
import json
import os
import re
import runpy
import sys
from pathlib import Path

# `bridge.py` is also run as a program by the migrate scripts (`python3 …/lib/bridge.py write|publish`), so it
# bootstraps before its one repository import, as every library program does (vibe-215).
runpy.run_path(str(Path(__file__).resolve().parents[1] / "_bootstrap.py"))
import fsafe  # noqa: E402  (M9 / vibe-223: the fs-safety kernel)

SCHEMA = 1
MARKER = "vibe-suite"


#: Literal sentinel names, plus the prefix whose members are discovered at runtime.
SENTINEL_LITERALS = ("vibe-mcp", "vibe-claude-mcp")
SENTINEL_PREFIX = "vibe-agent:"

#: The first line `migrate-state.sh` writes into `.vibe-suite-state/migration-conflicts.txt`, and
#: the exact prefix `unbridge` requires before it will remove that file. ONE definition, imported by
#: both sides — a second copy is precisely what vibe-265 was: the writer stamped the file so a re-run
#: would recognise its own output, and the teardown never looked, reading the prose as JSON instead.
#: A literal, deliberately NOT `f"# {MARKER}-owned: migration-conflicts\n"`: this is a PERSISTED
#: on-disk format. Deriving it from a renameable runtime constant would silently stop recognising
#: reports already written to a user's workspace.
MIGRATION_CONFLICTS_STAMP = "# vibe-suite-owned: migration-conflicts\n"


def stamp_matches(path, stamp):
    """Whether the file at `path` begins with EXACTLY `stamp`'s bytes.

    Byte-exact and fail-closed, and shared by both sides of a fixed-path ownership decision:
    `unbridge` deciding whether to **delete** a file, and `migrate-state` deciding whether to
    **overwrite** one. Both are destructive, so both need the same answer.

    `read_text` performs universal-newline translation, so a user's Windows-authored file whose
    first line is the marker followed by CRLF (or a bare CR) was normalised to the LF-only stamp and
    matched — deleted on the teardown side, truncated on the migration side (vibe-265). The decode
    below is a *readability* test only, kept because a file we cannot read end to end is one we
    cannot prove is ours; the shape test is on the raw bytes.

    Sharing the constant was not enough: both sides held the same string and compared it
    differently. The comparison is the thing that has to be shared.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return False        # a directory, an unreadable mode, a file that vanished mid-walk
    try:
        raw.decode("utf-8")
    except ValueError:
        return False        # undecodable: not provably ours, in either direction
    return raw.startswith(stamp.encode("utf-8"))

#: Advisor ownership is structural, not nominal (E6.1 / vibe-47): an advisor registers under its
#: bare name — the skill's `mcp__<name>__<tool_name>` callable identity requires the server key to
#: BE the name — so the claim of ownership travels inside the entry, exactly as owned hook entries
#: carry theirs. Only this exact marker value is a claim; anything else is a user's key.
ADVISOR_MARKER_KEY = f"_{MARKER}_owned"
ADVISOR_MARKER = {"kind": "advisor", "schema": SCHEMA}

#: The one inventory (M12 / vibe-220). Rows in the order init creates the targets — the provenance
#: record's `targets` list follows it, so this order is a persisted shape. `(rel, kind, blocks)`:
#:   md-block / text-block — a file the suite contributes marker blocks to; `blocks` names them, in
#:                           the order they are recognised (first match wins per path);
#:   json-keys             — a shared JSON store; `blocks` are the top-level keys that are ours;
#:   exclusive-md          — a whole file that is ours while its one block is present;
#:   exclusive-json        — a whole file that is ours by its JSON stamp (`vibe_suite_owned`).
#: `.codex/config.toml`'s `server:vibe-mcp` block has had no writer since vibe-191; it stays so the
#: teardown of an older install still recognises it.
OWNED_TARGETS = (
    (".gitignore", "text-block", ("ignore", "advisor-ignore")),
    ("AGENTS.md", "md-block", ("memory",)),
    ("CLAUDE.md", "md-block", ("import",)),
    ("GEMINI.md", "md-block", ("import",)),
    (".codex/config.toml", "text-block", ("server:vibe-mcp",)),
    (".mcp.json", "json-keys", ("mcpServers",)),
    (".codex/hooks.json", "json-keys", ("hooks",)),
    (".vibe-suite.md", "exclusive-md", ("config",)),
    (".claude/vibe-history.json", "exclusive-json", ()),
)
OWNED_KINDS = ("md-block", "text-block", "json-keys", "exclusive-md", "exclusive-json")

#: Every artefact init owns — the nine paths, in creation order. Derived; never listed twice.
TARGETS = tuple(rel for rel, _kind, _blocks in OWNED_TARGETS)

#: The marker blocks the suite contributes to shared text files, as `(rel, name, style)`. Derived
#: from OWNED_TARGETS — md-block rows first, then text-block rows, each in table order — which is
#: the order `unbridge._owned_artefacts_present` reads paths in and returns at the first owned
#: block, so it is behaviour, not style: AGENTS.md, CLAUDE.md, GEMINI.md, then .gitignore's two
#: blocks (`ignore` before `advisor-ignore`), then .codex/config.toml.
OWNED_BLOCKS = tuple(
    (rel, name, style)
    for kind, style in (("md-block", "md"), ("text-block", "text"))
    for rel, k, blocks in OWNED_TARGETS if k == kind
    for name in blocks)


class JsonUnreadable(fsafe.BridgeError):
    """`load_json(strict=True)`'s one failure: the path is not a regular file, cannot be read or decoded,
    is empty or whitespace-only (a `JSONDecodeError`), or is not valid JSON. `.cause` is the underlying exception so a caller can keep its own
    vocabulary (`StoreFormatError`, `Refusal`, a `parse-error` warning) without re-reading the file."""

    def __init__(self, path, cause):
        super().__init__(f"{path}: {cause.__class__.__name__}: {cause}")
        self.path = path
        self.cause = cause


# --------------------------------------------------------------------------------------------
# Anchored writes — a containment root for an arbitrary output path (vibe-216, vibe-217)
# --------------------------------------------------------------------------------------------

def existing_anchor(path):
    """`(unresolved, realpath)` of the nearest existing directory at or above `path`.

    `write_atomic` and `publish_new` need a root that exists (the descent opens it directly and
    creates only descendants) and is not a symlink (`assert_root`), hence the realpath. A caller
    writing under a user-chosen output directory anchors at that directory's *parent*, so the output
    directory itself is always below the anchor: created through the `O_NOFOLLOW` descent when
    absent, refused when it is a symlink or a regular file. Symlinks at or above the anchor are
    therefore followed — they are the user's existing directories (`/tmp` → `private/tmp` on macOS)
    — while every component below it is refused if it is a symlink. One rule, one place: the
    programs under `bin/` and `scripts/` share this instead of each carrying a copy.
    """
    p = Path(path).absolute()
    while not p.is_dir():          # a regular file on the way up is not an anchor either
        p = p.parent
    return p, Path(os.path.realpath(p))


def _rebase(anchor, dest):
    """Rebase `dest` lexically onto the anchor's realpath so `relative_to` sees one spelling."""
    unresolved, real = anchor
    return real, real / Path(dest).absolute().relative_to(unresolved)


def write_below(anchor, dest, content, mode=None):
    """`write_atomic` with `dest` rebased onto `anchor` (see `existing_anchor`)."""
    root, target = _rebase(anchor, dest)
    fsafe.write_atomic(root, target, content, mode=mode)


def publish_below(anchor, dest, content, mode=0o644):
    """`publish_new` with `dest` rebased onto `anchor`: True when created, False when a regular
    file already occupies the destination (the caller's retry signal); a symlink there raises."""
    root, target = _rebase(anchor, dest)
    return fsafe.publish_new(root, target, content, mode=mode)


# --------------------------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------------------------

def record_pre_image(path):
    """Enough to restore, or an explicit refusal.

    `content_b64` because a JSON string cannot carry arbitrary non-UTF-8 bytes, and the installer
    does not get to assume a user's file is text.
    """
    p = Path(path)
    kind = fsafe.classify(p)
    entry = {"path": str(p), "kind": kind}
    if kind == "symlink":
        entry["link_target"] = os.readlink(p)
    elif kind == "file":
        raw = p.read_bytes()
        entry["mode"] = oct(p.lstat().st_mode & 0o7777)
        entry["sha256"] = hashlib.sha256(raw).hexdigest()
        entry["content_b64"] = base64.b64encode(raw).decode("ascii")
    elif kind in ("dir", "other"):
        raise fsafe.BridgeError(f"{p} is a {kind} where a file belongs; the install refuses")
    return entry


def parents_created(root, dest):
    """Directories this install would bring into existence, so #21 can remove them."""
    made, probe = [], Path(dest).parent
    root = Path(root).resolve()
    while probe != root and root in probe.resolve().parents or probe == root:
        if probe == root or probe.exists():
            break
        made.append(str(probe))
        probe = probe.parent
    return list(reversed(made))


# --------------------------------------------------------------------------------------------
# Codecs — has / upsert / remove over one inventory
# --------------------------------------------------------------------------------------------

def _block(name, body, open_delim, close_delim):
    return (f"{open_delim} >>> {MARKER}:{name} v{SCHEMA} >>>{close_delim}\n"
            f"{body.rstrip()}\n"
            f"{open_delim} <<< {MARKER}:{name} <<<{close_delim}\n")


def _marker_open(name, open_delim, close_delim):
    """The opening marker, anchored to a whole line."""
    return (rf"^{re.escape(open_delim)} >>> {re.escape(MARKER)}:{re.escape(name)} v\d+ >>>"
            rf"{re.escape(close_delim)}$")


def _marker_close(name, open_delim, close_delim):
    """The closing marker, anchored to a whole line."""
    return (rf"^{re.escape(open_delim)} <<< {re.escape(MARKER)}:{re.escape(name)} <<<"
            rf"{re.escape(close_delim)}$")


def _block_re(name, open_delim, close_delim):
    """Detection and removal, built from the **same** anchored markers the validator uses.

    This was two regexes: an unanchored one here and an anchored one in `markers_wellformed`. A line
    like `prefix # >>> vibe-suite:x v1 >>>` therefore counted as zero markers to the validator — so
    the document passed as well-formed — while still matching here, and removal deleted through the
    user's content between it and the next close. Two parsers for one grammar is the defect; the
    parity is now structural rather than a thing to keep in step by hand.
    """
    return re.compile(
        _marker_open(name, open_delim, close_delim) + r"\n.*?"
        + _marker_close(name, open_delim, close_delim) + r"\n",
        re.S | re.M)


def text_block_upsert(existing, name, body, open_delim="#", close_delim=""):
    """Replace between markers, or append. Idempotent: identical input yields identical output.

    A second marker pair for the same name is refused rather than silently half-replaced: two owned
    regions means an earlier run or a hand edit left the file in a state this function cannot
    reconcile, and picking the first would strand the other forever.
    """
    block = _block(name, body, open_delim, close_delim)
    pattern = _block_re(name, open_delim, close_delim)
    found = pattern.findall(existing)
    opens = existing.count(f"{open_delim} >>> {MARKER}:{name} ")
    closes = existing.count(f"{open_delim} <<< {MARKER}:{name} ")
    if len(found) > 1 or opens != closes or opens > len(found):
        raise fsafe.BridgeError(
            f"{name}: found {opens} opening and {closes} closing markers for "
            f"{len(found)} well-formed block(s); refusing to guess which region is owned")
    if found:
        return pattern.sub(lambda _: block, existing, count=1)
    prefix = existing if existing.endswith("\n") or not existing else existing + "\n"
    return (prefix + "\n" if prefix else "") + block


def md_block_upsert(existing, name, body):
    return text_block_upsert(existing, name, body, "<!--", " -->")


def json_server_upsert(doc, name, entry):
    doc.setdefault("mcpServers", {})[name] = entry
    return doc


def json_hook_entry_upsert(doc, event, entry):
    """Ownership inside an event array. The entry carries its own marker, because a list member has
    no key to be owned by, and a user's entries share the array."""
    entry = dict(entry, **{f"_{MARKER}_owned": SCHEMA})
    events = doc.setdefault("hooks", {}).setdefault(event, [])
    for index, existing in enumerate(events):
        if isinstance(existing, dict) and existing.get(f"_{MARKER}_owned") is not None:
            events[index] = entry
            return doc
    events.append(entry)
    return doc


def text_block_has(existing, name, open_delim="#", close_delim=""):
    return bool(_block_re(name, open_delim, close_delim).search(existing))


def markers_wellformed(existing, name, open_delim="#", close_delim=""):
    """Whether this document's markers for `name` are clean, non-overlapping, full-line pairs.

    `_block_re` matches non-greedily from an opening marker to the *next* close, so a stray or
    duplicated opening marker makes the match start early and swallow everything up to the real
    block's close — user content included. Validation therefore has to live **here**, beside the
    removal it guards: a check in one caller left every other caller (`toml_server_remove` among
    them) removing unvalidated.

    The grammar is not merely *like* `_block_re`'s — it is built from the same two functions, so the
    two cannot drift. A validator that recognised a marker the remover did not (or the reverse) would
    pass a document whose removal still spans user data.
    """
    opens = [m.start() for m in re.finditer(
        _marker_open(name, open_delim, close_delim), existing, re.M)]
    closes = [m.start() for m in re.finditer(
        _marker_close(name, open_delim, close_delim), existing, re.M)]
    if len(opens) != len(closes):
        return False
    expect = "o"
    for _, kind in sorted([(p, "o") for p in opens] + [(p, "c") for p in closes]):
        if kind != expect:
            return False
        expect = "c" if expect == "o" else "o"
    return True


def text_block_remove(existing, name, open_delim="#", close_delim=""):
    """The exact inverse of `text_block_upsert`, so a clean install→remove round trip is
    byte-identical.

    Upsert appends `"\n" + block` to a non-empty file. Removal takes that one separator back and
    nothing else. An earlier revision normalised `\n\n\n` to `\n\n` anywhere in the file, which
    silently rewrote blank lines a user had put between their *own* paragraphs.

    Refuses a document whose markers are malformed rather than removing across them.
    """
    if not markers_wellformed(existing, name, open_delim, close_delim):
        raise fsafe.BridgeError(
            f"owned markers for {name!r} are malformed; refusing to remove across them")
    pattern = _block_re(name, open_delim, close_delim)
    match = pattern.search(existing)
    if not match:
        return existing
    start, end = match.span()
    # Reclaim the single separator newline upsert inserted before the block, if it is there.
    if start >= 1 and existing[start - 1] == "\n" and (start == 1 or existing[start - 2] == "\n"):
        start -= 1
    return existing[:start] + existing[end:]


def md_block_has(existing, name):
    return text_block_has(existing, name, "<!--", " -->")


def md_block_remove(existing, name):
    return text_block_remove(existing, name, "<!--", " -->")


def toml_server_upsert(existing, name, body):
    """`[mcp_servers.<name>]` plus its subtables. A subtable alone is not a registration —
    `migrate-sentinels.sh:151-160` already encodes that distinction, and a codec that ignored it
    would treat `[mcp_servers.x.env]` as evidence that `x` is registered."""
    return text_block_upsert(existing, f"server:{name}", body)


def toml_server_remove(existing, name):
    return text_block_remove(existing, f"server:{name}")


def toml_server_has(existing, name):
    return bool(_block_re(f"server:{name}", "#", "").search(existing))


def toml_table_names(text):
    """Every top-level `[mcp_servers.<name>]` table name in a TOML document.

    One parser for every consumer — enumeration and collision detection alike — because two
    parsers for one grammar is how `[mcp_servers.'probe']` collided invisibly: the collision
    check recognized bare and double-quoted keys while this function's grammar also knew single
    quotes. TOML permits whitespace around the dots and either quote kind; a subtable is not a
    registration.
    """
    names = []
    for header in re.findall(r"^\s*\[\s*mcp_servers\s*\.\s*(.+?)\s*\]\s*$", text, re.M):
        rest = header.strip()
        if rest.startswith(('"', "'")):
            quote = rest[0]
            end = rest.find(quote, 1)
            if end == -1:
                continue
            name, trailer = rest[1:end], rest[end + 1:]
        else:
            name, _, trailer = rest.partition(".")
            trailer = "." + trailer if trailer else ""
        if trailer.strip():
            continue          # a subtable is not a registration
        names.append(name)
    return names


def toml_owned_names(text):
    """Concrete owned servers declared in a TOML document, including `vibe-agent:` members.

    Enumeration has to span every codec: an agent registered only in `.codex/config.toml` is invisible
    to a JSON-only sweep, and #21's teardown iterates whatever this returns.
    """
    found = set()
    for name in toml_table_names(text):
        if name in SENTINEL_LITERALS or name.startswith(SENTINEL_PREFIX):
            found.add(name)
    # A bare-name advisor block is owned by its fence, not its name: the `server:<name>` markers
    # `toml_server_upsert` writes are the TOML-side twin of the JSON entry's advisor marker.
    for fenced in re.findall(
            rf"^# >>> {re.escape(MARKER)}:server:(.+?) v\d+ >>>$", text, re.M):
        if re.search(r"^\s*\[mcp_servers\.(?:%s|\"%s\")(?:\.[^]]+)?\]\s*$"
                     % (re.escape(fenced), re.escape(fenced)), text, re.M):
            found.add(fenced)
    return sorted(found)


def json_server_has(doc, name):
    return name in (doc.get("mcpServers") or {})


def json_server_remove(doc, name):
    (doc.get("mcpServers") or {}).pop(name, None)
    return doc


def json_hook_entry_remove(doc, event):
    events = (doc.get("hooks") or {}).get(event) or []
    (doc.get("hooks") or {})[event] = [
        e for e in events
        if not (isinstance(e, dict) and e.get(f"_{MARKER}_owned") is not None)]
    return doc


def json_hook_entry_has(doc, event):
    return any(isinstance(e, dict) and e.get(f"_{MARKER}_owned") is not None
               for e in (doc.get("hooks") or {}).get(event) or [])


def inventory_enumerate(root):
    """Every suite-owned sentinel in a workspace, across every store that can hold one.

    This is the single source F1.4 requires teardown to iterate. Two independently-maintained lists
    is the cc-suite W4 defect itself.
    """
    root = Path(root)
    names = set(owned_names(load_json(root / ".mcp.json", strict=False)))
    toml = root / ".codex" / "config.toml"
    if toml.is_file():
        names |= set(toml_owned_names(toml.read_text(encoding="utf-8", errors="replace")))
    return sorted(names)


def advisor_owned_entry(entry):
    """Whether a server entry carries the exact advisor ownership marker.

    Exact-match on purpose — including *types*: Python's `==` treats `True`, `1` and `1.0` as
    equal, so a plain dict comparison would claim `{"schema": true}` and make teardown delete an
    entry the suite never wrote. A malformed or coerced marker is a user's key, not our claim.
    """
    if not isinstance(entry, dict):
        return False
    marker = entry.get(ADVISOR_MARKER_KEY)
    if not isinstance(marker, dict) or set(marker) != set(ADVISOR_MARKER):
        return False
    kind, schema = marker.get("kind"), marker.get("schema")
    return (type(kind) is str and kind == ADVISOR_MARKER["kind"]
            and type(schema) is int and not isinstance(schema, bool)
            and schema == ADVISOR_MARKER["schema"])


def owned_names(doc):
    """Every suite-owned server name in a parsed `.mcp.json`: the literals, every concrete member
    of the `vibe-agent:` family, and every bare-name entry carrying the advisor marker."""
    servers = doc.get("mcpServers", {}) if isinstance(doc, dict) else {}
    found = [n for n in servers if n in SENTINEL_LITERALS or n.startswith(SENTINEL_PREFIX)
             or advisor_owned_entry(servers[n])]
    return sorted(found)


def read_text_verbatim(path):
    """Text with its line endings intact. `Path.read_text()` normalises CRLF to LF, so a
    read-modify-write silently rewrites every line of a CRLF file."""
    p = Path(path)
    if not p.is_file():
        return ""
    return p.read_bytes().decode("utf-8", errors="surrogateescape")


def load_json(path, *, strict=True):
    """The one JSON reader (M6 / vibe-218).

    `strict=True` (default): the path must be a regular file holding valid, non-empty JSON; every other
    outcome — missing, a directory, unreadable, undecodable, empty or whitespace-only, invalid — raises
    `JsonUnreadable` carrying the cause. `strict=False` is the lenient contract the installer paths were
    written against: not a regular file or zero bytes → `{}`, invalid JSON → `fsafe.BridgeError` ("the install
    refuses rather than overwrite a file it cannot read"). Callers that want the lenient reading say so.
    """
    p = Path(path)
    if strict:
        try:
            if not p.is_file():
                raise FileNotFoundError(f"{p} is not a regular file")
            return json.loads(p.read_text(encoding="utf-8"))   # empty or whitespace-only raises JSONDecodeError itself
        except (OSError, ValueError, RecursionError) as exc:   # JSONDecodeError and UnicodeDecodeError are ValueErrors;
            # json.loads raises RecursionError on a deeply nested document — a parser failure like any other (Step 9 R1)
            raise JsonUnreadable(p, exc) from exc
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise fsafe.BridgeError(f"{p} is not valid JSON ({exc}); the install refuses rather than "
                          "overwrite a file it cannot read") from exc


def main(argv):
    if len(argv) >= 4 and argv[1] == "write":
        # For shell callers. A native redirection (`printf ... > path`) **follows a symlink**, so a
        # link planted at a fixed path redirects the write onto whatever it points at — and
        # redirections are invisible to the AST lint, which is how one survived the sweep that
        # routed every Python write. Content arrives on stdin so no argv limit applies.
        root, dest = Path(argv[2]), Path(argv[3])
        mode = int(argv[4], 8) if len(argv) >= 5 else None
        fsafe.write_atomic(root, dest, sys.stdin.read(), mode=mode)
        return 0
    if len(argv) >= 4 and argv[1] == "publish":
        # Create-only, for shell callers. `mv -f` clobbers; this refuses, which is what "a store
        # that appeared while we ran still wins" requires.
        root, dest = Path(argv[2]), Path(argv[3])
        return 0 if fsafe.publish_new(root, dest, sys.stdin.read()) else 0
    if len(argv) >= 3 and argv[1] == "list-owned":
        for name in inventory_enumerate(argv[2]):
            print(name)
        return 0
    print("usage: bridge.py list-owned <workspace>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
