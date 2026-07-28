#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Fixtures for `/vibe-suite:unbridge` (E2.4 / vibe-21).

Acceptance is the strongest in this milestone: *after init→unbridge the fixture project is
byte-identical to pre-init, and nothing user-owned is touched.* Those two clauses conflict wherever a
user edited a target after install, and the order below is what lets both hold.

**Strip, then compare.** Provenance's `sha256` is the *pre-image* hash and init changed the target,
so comparing it against the current file detects "init ran", not "the user edited". Removing the
owned region first and comparing the remainder is the test that actually distinguishes them.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UNBRIDGE = REPO_ROOT / "scripts" / "unbridge.sh"
INIT = REPO_ROOT / "scripts" / "init.sh"


def tree(root):
    out = {}
    for p in sorted(Path(root).rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            out[rel] = ("l", None, os.readlink(p))
        elif p.is_dir():
            out[rel] = ("d", oct(p.stat().st_mode & 0o777), None)
        else:
            out[rel] = ("f", oct(p.lstat().st_mode & 0o777), p.read_bytes())
    return out


class UnbridgeCase(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-unbridge-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def install(self):
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def unbridge(self, *args):
        return subprocess.run(["bash", str(UNBRIDGE), "--workspace", str(self.ws), *args],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)


class TestAcceptance(UnbridgeCase):
    def test_init_then_unbridge_is_byte_identical_to_pre_init(self):
        (self.ws / "README.md").write_text("# Mine\n", encoding="utf-8")
        before = tree(self.ws)
        self.install()
        result = self.unbridge("--confirm")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tree(self.ws), before,
                         "the project is not byte-identical to its pre-init state")

    def test_a_second_unbridge_is_a_no_op(self):
        self.install()
        self.unbridge("--confirm")
        before = tree(self.ws)
        self.assertEqual(self.unbridge("--confirm").returncode, 0)
        self.assertEqual(tree(self.ws), before)


class TestUserContent(UnbridgeCase):
    def test_a_user_edit_after_init_survives_and_the_pre_image_is_not_restored(self):
        (self.ws / "CLAUDE.md").write_text("# Mine\n\noriginal\n", encoding="utf-8")
        self.install()
        text = (self.ws / "CLAUDE.md").read_text(encoding="utf-8")
        (self.ws / "CLAUDE.md").write_text(text.replace("original", "edited later"),
                                           encoding="utf-8")
        self.unbridge("--confirm")
        after = (self.ws / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("edited later", after, "the user's later edit was overwritten by the pre-image")
        self.assertNotIn("vibe-suite:", after, "the owned block survived")

    def test_lines_adjacent_to_an_owned_block_survive(self):
        (self.ws / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        self.install()
        text = (self.ws / ".gitignore").read_text(encoding="utf-8")
        (self.ws / ".gitignore").write_text(text + "\ndist/\n", encoding="utf-8")
        self.unbridge("--confirm")
        after = (self.ws / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("node_modules/", after)
        self.assertIn("dist/", after)
        self.assertNotIn("vibe-suite:", after)

    def test_a_created_file_the_user_filled_is_not_deleted(self):
        """`kind: absent` means delete — which is where user content is most at risk."""
        self.install()
        text = (self.ws / "GEMINI.md").read_text(encoding="utf-8")
        (self.ws / "GEMINI.md").write_text(text + "\nmine now\n", encoding="utf-8")
        self.unbridge("--confirm")
        self.assertTrue((self.ws / "GEMINI.md").is_file(),
                        "a file the user had written into was deleted")
        self.assertIn("mine now", (self.ws / "GEMINI.md").read_text(encoding="utf-8"))

    def test_user_servers_in_mcp_json_survive(self):
        self.install()
        doc = json.loads((self.ws / ".mcp.json").read_text())
        doc["mcpServers"]["mine"] = {"command": "x"}
        (self.ws / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        self.unbridge("--confirm")
        after = json.loads((self.ws / ".mcp.json").read_text())
        self.assertIn("mine", after["mcpServers"])
        self.assertNotIn("vibe-mcp", after["mcpServers"])

    def test_a_parent_holding_user_files_is_not_pruned(self):
        self.install()
        (self.ws / ".codex" / "mine.txt").write_text("keep\n", encoding="utf-8")
        self.unbridge("--confirm")
        self.assertTrue((self.ws / ".codex" / "mine.txt").is_file(),
                        "a directory holding user files was pruned")


class TestConfirmation(UnbridgeCase):
    def test_without_confirm_nothing_changes(self):
        self.install()
        before = tree(self.ws)
        result = self.unbridge()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(tree(self.ws), before, "an unconfirmed run mutated the workspace")

    def test_without_confirm_it_reports_what_would_go(self):
        self.install()
        self.assertIn("vibe-mcp", self.unbridge().stdout + self.unbridge().stderr)

    def test_legacy_sentinels_go_under_the_same_confirmation(self):
        self.install()
        doc = json.loads((self.ws / ".mcp.json").read_text())
        doc["mcpServers"]["cc-suite-mcp"] = {"command": "x"}
        (self.ws / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        self.unbridge("--confirm")
        # init created .mcp.json, and with both registrations gone nothing of the user's is left in
        # it — so the file itself goes. Either outcome satisfies "the legacy sentinel is removed";
        # what must not happen is it surviving.
        path = self.ws / ".mcp.json"
        remaining = json.loads(path.read_text()).get("mcpServers", {}) if path.is_file() else {}
        self.assertNotIn("cc-suite-mcp", remaining)


class TestUntrustedProvenance(UnbridgeCase):
    def test_a_target_outside_the_workspace_is_refused(self):
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (outside / "victim.md").write_text("not yours\n", encoding="utf-8")
        self.install()
        path = self.ws / ".vibe-suite-state" / "install-provenance.json"
        record = json.loads(path.read_text())
        record["targets"][0]["path"] = str(outside / "victim.md")
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        result = self.unbridge("--confirm")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((outside / "victim.md").is_file(), "unbridge deleted outside the workspace")

    def test_a_parents_created_entry_outside_the_workspace_is_refused(self):
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        self.install()
        path = self.ws / ".vibe-suite-state" / "install-provenance.json"
        record = json.loads(path.read_text())
        record["parents_created"] = [str(outside)]
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        self.unbridge("--confirm")
        self.assertTrue(outside.is_dir(), "unbridge pruned a directory outside the workspace")

    def test_missing_provenance_is_refused_not_guessed(self):
        self.install()
        (self.ws / ".vibe-suite-state" / "install-provenance.json").unlink()
        result = self.unbridge("--confirm")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.ws / "AGENTS.md").is_file(),
                        "unbridge removed artefacts it had no record for")


class TestCommandWiring(UnbridgeCase):
    def test_the_command_names_both_destructions(self):
        text = (REPO_ROOT / "commands" / "unbridge.md").read_text(encoding="utf-8")
        self.assertIn("scripts/unbridge.sh", text)
        self.assertIn("cc-suite", text, "the confirmation must name the legacy cleanup too")
        self.assertNotIn("/vibe:", text.replace("/vibe-suite:", ""))


if __name__ == "__main__":
    unittest.main()


class TestBlockerRegressions(UnbridgeCase):
    """Each reproduced against `0cde28c` before the fix."""

    def test_a_symlinked_target_does_not_delete_what_it_points_at(self):
        """`.resolve()` resolved away the final symlink, so containment passed and the delete landed
        on the target. Verified to destroy a user file."""
        self.install()
        (self.ws / "notes.md").write_text("MY IMPORTANT NOTES\n", encoding="utf-8")
        (self.ws / "AGENTS.md").unlink()
        (self.ws / "AGENTS.md").symlink_to(self.ws / "notes.md")
        self.unbridge("--confirm")
        self.assertTrue((self.ws / "notes.md").is_file(), "the user's file was deleted")
        self.assertEqual((self.ws / "notes.md").read_text(encoding="utf-8"),
                         "MY IMPORTANT NOTES\n")

    def test_a_symlinked_state_dir_does_not_delete_outside_the_workspace(self):
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (outside / "keep.txt").write_text("mine\n", encoding="utf-8")
        self.install()
        record = (self.ws / ".vibe-suite-state" / "install-provenance.json").read_bytes()
        shutil.rmtree(self.ws / ".vibe-suite-state")
        (self.ws / ".vibe-suite-state").symlink_to(outside, target_is_directory=True)
        (outside / "install-provenance.json").write_bytes(record)
        self.unbridge("--confirm")
        self.assertTrue((outside / "keep.txt").is_file(),
                        "unbridge recursively deleted outside the workspace")

    def test_a_server_added_after_init_is_not_lost_to_the_pre_image(self):
        """`restore` wrote the pre-image unconditionally for JSON targets."""
        (self.ws / ".mcp.json").write_text('{"mcpServers": {"pre": {"command": "a"}}}\n',
                                           encoding="utf-8")
        self.install()
        doc = json.loads((self.ws / ".mcp.json").read_text())
        doc["mcpServers"]["added-later"] = {"command": "b"}
        (self.ws / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        self.unbridge("--confirm")
        after = json.loads((self.ws / ".mcp.json").read_text())["mcpServers"]
        self.assertIn("added-later", after, "a server added after init was discarded")
        self.assertIn("pre", after)
        self.assertNotIn("vibe-mcp", after)

    def test_a_toml_registration_is_actually_removed(self):
        self.install()
        text = (self.ws / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("vibe-mcp", text)
        self.unbridge("--confirm")
        path = self.ws / ".codex" / "config.toml"
        remaining = path.read_text(encoding="utf-8") if path.is_file() else ""
        self.assertNotIn("mcp_servers.vibe-mcp", remaining,
                         "a TOML registration was enumerated but never removed")

    def test_the_owned_block_map_is_not_a_second_inventory(self):
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import bridge, unbridge as unbridge_mod
        self.assertIs(unbridge_mod.BLOCKS, bridge.OWNED_BLOCKS,
                      "unbridge keeps its own copy — the W4 defect F1.4 exists to fix")


class TestDescriptorRelativeDeletion(UnbridgeCase):
    """The path layer rewritten around directory descriptors.

    Deleting by path re-resolves every component at call time, so a symlink planted *anywhere* along
    it redirects the removal. Guarding the final component only — the earlier fix — left the parent
    open. Resolving the parent once and unlinking relative to that descriptor closes the class
    rather than the instance.
    """

    def test_a_symlinked_parent_cannot_redirect_a_deletion(self):
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (outside / "hooks.json").write_text("MINE\n", encoding="utf-8")
        self.install()
        shutil.rmtree(self.ws / ".codex")
        (self.ws / ".codex").symlink_to(outside, target_is_directory=True)
        self.unbridge("--confirm")
        self.assertTrue((outside / "hooks.json").is_file(),
                        "deletion followed a symlinked parent out of the workspace")
        self.assertEqual((outside / "hooks.json").read_text(encoding="utf-8"), "MINE\n")

    def test_a_symlink_inside_the_state_dir_is_not_followed(self):
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (outside / "keep.txt").write_text("mine\n", encoding="utf-8")
        self.install()
        (self.ws / ".vibe-suite-state" / "link").symlink_to(outside / "keep.txt")
        self.unbridge("--confirm")
        self.assertTrue((outside / "keep.txt").is_file(),
                        "a symlink inside the state dir took its target")

    def test_a_directory_is_removed_by_type_not_by_errno(self):
        """macOS raises PermissionError where Linux raises IsADirectoryError, so the removal has to
        decide on the node type."""
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import bridge
        (self.ws / "adir").mkdir()
        self.assertTrue(bridge.unlink_at(self.ws, "adir"))
        self.assertFalse((self.ws / "adir").exists())

    def test_unlink_at_reports_a_missing_entry_rather_than_raising(self):
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import bridge
        self.assertFalse(bridge.unlink_at(self.ws, "never-existed"))
