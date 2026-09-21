#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The bridge's codec and kernel primitives, named one by one (vibe-225 / grill M28).

Eleven of `bridge.py`'s public functions were never named by a test — exercised only transitively, through the
commands that call them — and `fsafe.open_dir_chain` appeared only as a string in a list. Each gets one positive
and one negative case here, taken from its own contract. `pin_root`, `remove_tree_at`, `ensure_dir_at` and
`lstat_at` are already covered (`test_fsafe_split.py`, `test_unbridge.py`, `test_update.py`) and are not repeated.

The replace-step crash is covered twice by design: the HARD crash (`os._exit` at `os.replace`, which leaves exactly
one scratch behind — nothing can clean up after `_exit`) is `test_bridge_cli.py`'s
`test_a_write_interrupted_after_scratch_creation_does_not_poison_the_destination`; the SOFT one — an error raised at
the replace, which `write_atomic`'s own cleanup must turn into "destination unchanged, no scratch left" — is here.
"""

import base64
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import bridge  # noqa: E402
import fsafe  # noqa: E402

OWNED = f"_{bridge.MARKER}_owned"


class TempDir(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory(prefix="vibe-bridge-prim-")
        self.addCleanup(self._dir.cleanup)
        self.root = Path(self._dir.name).resolve()


class TestJsonServer(unittest.TestCase):
    def test_upsert_creates_the_map_and_adds_the_entry(self):
        self.assertEqual(bridge.json_server_upsert({}, "vibe-mcp", {"command": "x"}),
                         {"mcpServers": {"vibe-mcp": {"command": "x"}}})

    def test_upsert_replaces_one_entry_and_keeps_its_siblings(self):
        doc = {"mcpServers": {"vibe-mcp": {"command": "old"}, "user": {"command": "mine"}}}
        self.assertEqual(bridge.json_server_upsert(doc, "vibe-mcp", {"command": "new"}),
                         {"mcpServers": {"vibe-mcp": {"command": "new"}, "user": {"command": "mine"}}})

    def test_has_is_true_for_a_present_name(self):
        self.assertTrue(bridge.json_server_has({"mcpServers": {"vibe-mcp": {}}}, "vibe-mcp"))

    def test_has_is_false_for_an_absent_name_or_an_absent_map(self):
        self.assertFalse(bridge.json_server_has({"mcpServers": {"user": {}}}, "vibe-mcp"))
        self.assertFalse(bridge.json_server_has({}, "vibe-mcp"))
        self.assertFalse(bridge.json_server_has({"mcpServers": None}, "vibe-mcp"))

    def test_remove_drops_the_name_and_keeps_its_siblings(self):
        doc = {"mcpServers": {"vibe-mcp": {}, "user": {"command": "mine"}}}
        self.assertEqual(bridge.json_server_remove(doc, "vibe-mcp"), {"mcpServers": {"user": {"command": "mine"}}})

    def test_remove_of_an_absent_name_or_map_is_a_no_op(self):
        self.assertEqual(bridge.json_server_remove({"mcpServers": {"user": {}}}, "vibe-mcp"),
                         {"mcpServers": {"user": {}}})
        self.assertEqual(bridge.json_server_remove({}, "vibe-mcp"), {})


class TestJsonHookEntry(unittest.TestCase):
    USER = {"type": "command", "command": "user-hook"}

    def test_upsert_appends_the_entry_with_the_ownership_marker(self):
        doc = bridge.json_hook_entry_upsert({}, "Stop", {"type": "command", "command": "ours"})
        self.assertEqual(doc, {"hooks": {"Stop": [{"type": "command", "command": "ours", OWNED: bridge.SCHEMA}]}})

    def test_upsert_replaces_the_owned_entry_in_place_and_keeps_the_user_entry(self):
        doc = {"hooks": {"Stop": [dict(self.USER), {"command": "old", OWNED: 1}]}}
        doc = bridge.json_hook_entry_upsert(doc, "Stop", {"command": "new"})
        self.assertEqual(doc["hooks"]["Stop"], [self.USER, {"command": "new", OWNED: bridge.SCHEMA}])

    def test_has_is_true_when_an_owned_entry_is_present(self):
        self.assertTrue(bridge.json_hook_entry_has({"hooks": {"Stop": [dict(self.USER), {OWNED: 1}]}}, "Stop"))

    def test_has_is_false_for_user_entries_only_or_an_absent_event(self):
        self.assertFalse(bridge.json_hook_entry_has({"hooks": {"Stop": [dict(self.USER)]}}, "Stop"))
        self.assertFalse(bridge.json_hook_entry_has({"hooks": {}}, "Stop"))
        self.assertFalse(bridge.json_hook_entry_has({}, "Stop"))

    def test_remove_drops_only_owned_entries(self):
        doc = {"hooks": {"Stop": [dict(self.USER), {"command": "ours", OWNED: 1}]}}
        self.assertEqual(bridge.json_hook_entry_remove(doc, "Stop"), {"hooks": {"Stop": [self.USER]}})

    def test_remove_keeps_user_entries_and_an_absent_event_is_a_no_op(self):
        doc = {"hooks": {"Stop": [dict(self.USER)]}}
        self.assertEqual(bridge.json_hook_entry_remove(doc, "Stop"), {"hooks": {"Stop": [self.USER]}})
        self.assertEqual(bridge.json_hook_entry_remove({"hooks": {}}, "Stop"), {"hooks": {}})


class TestMarkdownBlock(unittest.TestCase):
    def setUp(self):
        self.text = "# Title\n\nuser text\n"
        self.with_block = bridge.md_block_upsert(self.text, "rules", "managed body\n")

    def test_has_is_true_for_a_well_formed_block_of_that_name(self):
        self.assertTrue(bridge.md_block_has(self.with_block, "rules"))

    def test_has_is_false_for_another_name(self):
        self.assertFalse(bridge.md_block_has(self.with_block, "other"))
        self.assertFalse(bridge.md_block_has(self.text, "rules"))

    def test_remove_drops_the_block_and_keeps_the_surrounding_text(self):
        removed = bridge.md_block_remove(self.with_block, "rules")
        self.assertFalse(bridge.md_block_has(removed, "rules"))
        self.assertIn("user text", removed)
        self.assertNotIn("managed body", removed)

    def test_remove_of_text_without_the_block_returns_it_unchanged(self):
        self.assertEqual(bridge.md_block_remove(self.text, "rules"), self.text)


class TestTomlTableNames(unittest.TestCase):
    def test_bare_and_quoted_headers_with_spaces_around_the_dot(self):
        text = ('[mcp_servers.bare]\n[ mcp_servers . "double" ]\n[mcp_servers.\'single\']\n'
                '[mcp_servers."dotted.name"]\n')
        self.assertEqual(bridge.toml_table_names(text), ["bare", "double", "single", "dotted.name"])

    def test_a_subtable_or_an_unterminated_quote_is_not_a_name(self):
        text = '[mcp_servers.x.env]\n[mcp_servers."y".env]\n[mcp_servers."open]\n[other.z]\n'
        self.assertEqual(bridge.toml_table_names(text), [])


class TestRecordPreImage(TempDir):
    def test_a_file_round_trips_non_utf8_bytes(self):
        path = self.root / "f.bin"
        raw = b"\xff\xfe line\r\n\x00"
        path.write_bytes(raw)
        os.chmod(path, 0o640)
        entry = bridge.record_pre_image(path)
        self.assertEqual(entry["kind"], "file")
        self.assertEqual(entry["mode"], oct(0o640))
        self.assertEqual(entry["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(base64.b64decode(entry["content_b64"]), raw)

    def test_a_symlink_records_its_target_and_absence_is_recorded_as_absent(self):
        link = self.root / "l"
        os.symlink("elsewhere", link)
        self.assertEqual(bridge.record_pre_image(link),
                         {"path": str(link), "kind": "symlink", "link_target": "elsewhere"})
        self.assertEqual(bridge.record_pre_image(self.root / "none"),
                         {"path": str(self.root / "none"), "kind": "absent"})

    def test_a_directory_where_a_file_belongs_is_refused(self):
        (self.root / "d").mkdir()
        with self.assertRaises(fsafe.BridgeError):
            bridge.record_pre_image(self.root / "d")


class TestAdvisorOwnedEntry(unittest.TestCase):
    def test_the_exact_marker_is_owned(self):
        self.assertTrue(bridge.advisor_owned_entry({bridge.ADVISOR_MARKER_KEY: dict(bridge.ADVISOR_MARKER)}))

    def test_coerced_malformed_or_absent_markers_are_not_owned(self):
        key, kind = bridge.ADVISOR_MARKER_KEY, bridge.ADVISOR_MARKER["kind"]
        for entry in ({key: {"kind": kind, "schema": True}},          # == 1 in Python, not our claim
                      {key: {"kind": kind, "schema": 1.0}},
                      {key: {"kind": kind}},
                      {key: {"kind": kind, "schema": 1, "extra": 1}},
                      {key: "advisor"},
                      {},
                      "not a dict"):
            with self.subTest(entry=entry):
                self.assertFalse(bridge.advisor_owned_entry(entry))


class TestReadTextVerbatim(TempDir):
    def test_crlf_is_preserved_and_undecodable_bytes_survive(self):
        path = self.root / "t.txt"
        path.write_bytes(b"a\r\nb\xff\n")
        text = bridge.read_text_verbatim(path)
        self.assertEqual(text.encode("utf-8", errors="surrogateescape"), b"a\r\nb\xff\n")

    def test_a_missing_path_reads_as_empty(self):
        self.assertEqual(bridge.read_text_verbatim(self.root / "missing"), "")


class TestOpenDirChain(TempDir):
    def test_a_real_nested_directory_opens(self):
        (self.root / "a" / "b").mkdir(parents=True)
        fd = fsafe.open_dir_chain(self.root, ("a", "b"))
        try:
            self.assertEqual(os.fstat(fd).st_ino, (self.root / "a" / "b").stat().st_ino)
        finally:
            os.close(fd)

    def test_a_symlinked_component_is_refused(self):
        (self.root / "real").mkdir()
        os.symlink(self.root / "real", self.root / "link")
        with self.assertRaises(fsafe.BridgeError):
            os.close(fsafe.open_dir_chain(self.root, ("link",)))


class TestWriteAtomicSoftFailure(TempDir):
    """An error AT the replace: the destination is unchanged, no scratch is left, and the error surfaces."""

    def test_an_error_at_the_replace_leaves_the_destination_and_no_scratch(self):
        dest = self.root / "state.json"
        dest.write_bytes(b"before\n")
        with mock.patch.object(fsafe.os, "replace", side_effect=OSError("replace refused")):
            with self.assertRaises(OSError):
                fsafe.write_atomic(self.root, dest, "after\n")
        self.assertEqual(dest.read_bytes(), b"before\n")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["state.json"],
                         "no .vibe-tmp scratch may survive a failure the writer itself caught")


BRIDGE_PY = REPO_ROOT / "scripts" / "lib" / "bridge.py"


class TestBridgeProgramExits(TempDir):
    """vibe-231: `bridge.py`'s shell entry point. A refusal is one `bridge: …` line and exit 1, never a
    traceback; a mode that is not octal is a usage error (2); `publish` over an existing destination
    exits 3, so a caller can tell "already there" from "created" (both used to exit 0)."""

    def run_bridge(self, *args, content="new\n"):
        return subprocess.run([sys.executable, str(BRIDGE_PY), *map(str, args)], input=content,
                              capture_output=True, text=True)

    def assert_one_bridge_line(self, result, code):
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertTrue(lines[0].startswith("bridge: "), lines[0])
        return lines[0]

    def test_a_write_outside_the_root_is_one_line_and_exit_1(self):
        with tempfile.TemporaryDirectory() as other:
            dest = Path(other).resolve() / "f"
            self.assert_one_bridge_line(self.run_bridge("write", self.root, dest), 1)
            self.assertFalse(dest.exists())

    def test_a_write_through_a_symlinked_parent_is_one_line_and_exit_1(self):
        with tempfile.TemporaryDirectory() as other:
            (self.root / "link").symlink_to(other)
            self.assert_one_bridge_line(self.run_bridge("write", self.root, self.root / "link" / "f"), 1)
            self.assertFalse((Path(other) / "f").exists())

    def test_a_mode_that_is_not_octal_is_a_usage_error(self):
        dest = self.root / "f"
        line = self.assert_one_bridge_line(self.run_bridge("write", self.root, dest, "9z"), 2)
        self.assertEqual(line, "bridge: invalid mode '9z' (octal expected)")
        self.assertFalse(dest.exists())

    @unittest.skipIf(os.geteuid() == 0, "permission bits do not bind root")
    def test_a_raw_os_error_is_one_line_and_exit_1(self):
        """`list-owned` reads `.codex/config.toml` through `read_text_verbatim`, whose PermissionError is a plain
        OSError, not a BridgeError: the handler's OSError arm is the only thing between it and a traceback."""
        (self.root / ".codex").mkdir()
        toml = self.root / ".codex" / "config.toml"
        toml.write_text("".join(line + chr(10) for line in ("[mcp_servers.x]", 'command = "y"')), encoding="utf-8")
        toml.chmod(0)
        self.addCleanup(toml.chmod, 0o644)
        line = self.assert_one_bridge_line(self.run_bridge("list-owned", self.root), 1)
        self.assertIn("Permission denied", line)
        self.assertIn("config.toml", line)

    def test_publish_exits_0_when_it_creates_and_3_when_the_destination_existed(self):
        dest = self.root / "f"
        created = self.run_bridge("publish", self.root, dest, content="first\n")
        self.assertEqual((created.returncode, created.stderr), (0, ""))
        self.assertEqual(dest.read_text(encoding="utf-8"), "first\n")
        existed = self.run_bridge("publish", self.root, dest, content="second\n")
        self.assertEqual((existed.returncode, existed.stderr), (3, ""))
        self.assertEqual(dest.read_text(encoding="utf-8"), "first\n", "create-only: the first store wins")


if __name__ == "__main__":
    unittest.main()
