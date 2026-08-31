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
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UNBRIDGE = REPO_ROOT / "scripts" / "unbridge.sh"
import sys
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import bridge      # noqa: E402
import unbridge    # noqa: E402
import init_bridge # noqa: E402
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


def plant_dangling_registrations(ws):
    """The three registrations an earlier revision of init wrote — a bare `vibe-suite` command in
    each host-read file — beside a user's own entries, which must survive their removal."""
    ws = Path(ws)
    (ws / ".codex").mkdir(exist_ok=True)
    toml = ws / ".codex" / "config.toml"
    existing = toml.read_text(encoding="utf-8") if toml.is_file() else ""
    toml.write_text(bridge.toml_server_upsert(existing, "vibe-mcp",
                                              '[mcp_servers.vibe-mcp]\ncommand = "vibe-suite"'),
                    encoding="utf-8")
    mcp = ws / ".mcp.json"
    doc = json.loads(mcp.read_text(encoding="utf-8")) if mcp.is_file() else {}
    doc.setdefault("mcpServers", {})["mine"] = {"command": "x"}
    doc["mcpServers"]["vibe-mcp"] = {"command": "vibe-suite", "args": []}
    mcp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hooks = ws / ".codex" / "hooks.json"
    hdoc = json.loads(hooks.read_text(encoding="utf-8")) if hooks.is_file() else {}
    hdoc.setdefault("hooks", {}).setdefault("Stop", []).append({"type": "command", "command": "my-hook"})
    hdoc = bridge.json_hook_entry_upsert(hdoc, "Stop", {"type": "command", "command": "vibe-suite stop-gate"})
    hooks.write_text(json.dumps(hdoc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bare_registrations(ws):
    """Which of the three files still reference `vibe-suite` as a command."""
    ws = Path(ws)
    out = []
    toml = ws / ".codex" / "config.toml"
    if toml.is_file() and 'command = "vibe-suite"' in toml.read_text(encoding="utf-8"):
        out.append(".codex/config.toml")   # the bare SHAPE, not the server name: a non-bare vibe-mcp is legitimate
    mcp = ws / ".mcp.json"
    if mcp.is_file():
        servers = json.loads(mcp.read_text(encoding="utf-8")).get("mcpServers") or {}
        if any(isinstance(s, dict) and s.get("command") == "vibe-suite" for s in servers.values()):
            out.append(".mcp.json")
    hooks = ws / ".codex" / "hooks.json"
    if hooks.is_file():
        for event in (json.loads(hooks.read_text(encoding="utf-8")).get("hooks") or {}).values():
            if any(isinstance(e, dict) and str(e.get("command") or "").startswith("vibe-suite") for e in event):
                out.append(".codex/hooks.json")
                break
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
        plant_dangling_registrations(self.ws)   # grill S4: init no longer writes vibe-mcp; an old one is planted
        self.unbridge("--confirm")
        after = json.loads((self.ws / ".mcp.json").read_text())
        self.assertIn("mine", after["mcpServers"])
        self.assertNotIn("vibe-mcp", after["mcpServers"])
        # retained behaviour (init no longer writes the owned Stop hook, so this branch must be
        # asserted explicitly): the owned entry goes, the user's sibling hook survives
        stop = json.loads((self.ws / ".codex" / "hooks.json").read_text())["hooks"]["Stop"]
        self.assertEqual([e.get("command") for e in stop], ["my-hook"],
                         "unbridge removes the owned Stop hook and keeps the user's")

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
        plant_dangling_registrations(self.ws)   # grill S4: an old registration is what would go
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
        plant_dangling_registrations(self.ws)   # grill S4: init no longer writes it; an old one is planted
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


class ReadAndDeleteDoNotCreateDirectories(UnbridgeCase):
    """vibe-179 / grill M10. `_open_dir_chain` created every missing path component as a side effect
    of OPENING it, for every caller — so a read (`lstat_at`) or a deletion (`unlink_at`) minted
    directories the user never had, and a teardown could leave behind a `.codex/` the user had
    removed. Creation is opt-in now; read and delete primitives report absence and touch nothing."""

    def test_lstat_at_on_a_missing_intermediate_directory_does_not_create_it(self):
        self.assertFalse((self.ws / ".codex").exists())
        self.assertIsNone(bridge.lstat_at(self.ws, ".codex/config.toml"))
        self.assertFalse((self.ws / ".codex").exists(), "a read created .codex/")

    def test_unlink_at_on_a_missing_intermediate_directory_does_not_create_it(self):
        self.assertFalse(bridge.unlink_at(self.ws, ".vibe-suite-state/advisor-preimages.json"))
        self.assertFalse((self.ws / ".vibe-suite-state").exists(), "a deletion created .vibe-suite-state/")

    def test_remove_tree_at_on_a_missing_intermediate_directory_does_not_create_it(self):
        self.assertFalse(bridge.remove_tree_at(self.ws, ".vibe-suite/agents/gone"))
        self.assertFalse((self.ws / ".vibe-suite").exists(), "a tree removal created .vibe-suite/")

    def test_secure_dir_on_a_missing_directory_refuses_and_creates_nothing(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.secure_dir(self.ws, ".vibe-suite-state")
        self.assertFalse((self.ws / ".vibe-suite-state").exists(), "a mode change created the directory")

    def test_a_symlink_component_is_still_refused_not_reported_absent(self):
        """ENOENT alone means "nothing is there". A link where a directory should be stays a refusal
        — it must not be mistaken for absence and silently skipped."""
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (self.ws / "link").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(bridge.BridgeError) as caught:
            bridge.lstat_at(self.ws, "link/config.toml")
        self.assertNotIsInstance(caught.exception, bridge.AbsentPath)

    def test_the_creating_primitives_still_bring_parents_into_existence(self):
        self.assertTrue(bridge.symlink_at(self.ws, "a/b/link", "target"))
        self.assertTrue((self.ws / "a" / "b" / "link").is_symlink())
        bridge.write_atomic(self.ws, self.ws / "c" / "d" / "file.txt", "x")
        self.assertEqual((self.ws / "c" / "d" / "file.txt").read_text(), "x")
        self.assertTrue(bridge.publish_new(self.ws, self.ws / "e" / "f" / "new.txt", "y"))
        bridge.ensure_dir_at(self.ws, "g/h")
        self.assertTrue((self.ws / "g" / "h").is_dir())

    def test_unbridge_on_a_workspace_whose_codex_dir_is_gone_leaves_no_codex_dir(self):
        """`.codex/` existed before install (so `prune` never records it), and the user removed it
        afterwards. Teardown's read of `.codex/config.toml` used to recreate the directory and
        nothing removed it again."""
        (self.ws / ".codex").mkdir()
        self.install()
        shutil.rmtree(self.ws / ".codex")
        result = self.unbridge("--confirm")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.ws / ".codex").exists(), "teardown recreated a .codex/ the user had removed")

    def test_a_missing_workspace_root_is_a_plain_refusal_not_an_absent_entry(self):
        """The root is the trust anchor, not a path component: a workspace that does not exist is a
        refusal (`BridgeError`), never `AbsentPath` — a read must not answer "nothing there" for a
        root that was simply mistyped. The anchor open used to leak a raw `FileNotFoundError`."""
        missing = self.ws / "never-made"
        with self.assertRaises(bridge.BridgeError) as caught:
            bridge.lstat_at(missing, "config.toml")
        self.assertNotIsInstance(caught.exception, bridge.AbsentPath)
        self.assertFalse(missing.exists(), "the refusal created the root")


class TestRemoveOnly(UnbridgeCase):
    """Teardown removes what it owns and never writes a pre-image back.

    Init only ever *adds* owned regions, so removing them is the restore. Writing the recorded
    pre-image was the source of every user-content-loss defect here: it cannot tell an untouched
    file from an edited one without a comparison that kept getting corner cases wrong, and a wrong
    guess overwrites work. Removing cannot lose content that way.
    """

    def test_a_file_rewritten_entirely_after_init_keeps_the_users_version(self):
        (self.ws / "CLAUDE.md").write_text("# original\n", encoding="utf-8")
        self.install()
        (self.ws / "CLAUDE.md").write_text("# completely different now\n", encoding="utf-8")
        self.unbridge("--confirm")
        after = (self.ws / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(after, "# completely different now\n",
                         "the pre-image was written back over the user's rewrite")

    def test_the_suites_own_files_are_removed_not_reverted(self):
        """`.vibe-suite.md` and the history are the *suite's* artefacts, so a teardown removes them —
        that is what byte-identity to pre-init means. The distinction that matters is between the
        suite's files and the user's: an edit to the suite's own config does not make it the user's.
        What must never happen is a **pre-image being written back**, which is what would silently
        revert an edit in a file the user does own."""
        self.install()
        path = self.ws / ".vibe-suite.md"
        path.write_text(path.read_text(encoding="utf-8").replace("effort: medium", "effort: high"),
                        encoding="utf-8")
        self.unbridge("--confirm")
        self.assertFalse(path.exists(), "the suite's own config survived teardown")
        self.assertFalse((self.ws / ".claude" / "vibe-history.json").exists())

    def test_a_pre_image_is_never_written_back(self):
        """The property that replaces restore. No file ends a teardown holding bytes it did not hold
        when the teardown began, unless those bytes are a strict subset (our region removed)."""
        (self.ws / "CLAUDE.md").write_text("# original\n", encoding="utf-8")
        self.install()
        (self.ws / "CLAUDE.md").write_text("# rewritten\n", encoding="utf-8")
        before = (self.ws / "CLAUDE.md").read_text(encoding="utf-8")
        self.unbridge("--confirm")
        self.assertEqual((self.ws / "CLAUDE.md").read_text(encoding="utf-8"), before,
                         "content reappeared that was not there when teardown started")

    def test_a_file_that_existed_before_init_is_never_deleted(self):
        (self.ws / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        self.install()
        self.unbridge("--confirm")
        self.assertTrue((self.ws / ".gitignore").is_file())
        self.assertEqual((self.ws / ".gitignore").read_text(encoding="utf-8"), "node_modules/\n")


class ContentLossPaths(unittest.TestCase):
    """The two paths on which teardown could destroy user data.

    Both are *reproductions first*. Each seeds the exact shape the reviewer named, runs the real
    teardown, and asserts the user's bytes survive — so each fails against the implementation that
    preceded this class rather than merely exercising the new guard.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)

    # -- a stray opening marker makes the non-greedy match start early ---------------------------
    def test_a_duplicated_opening_marker_does_not_consume_user_content(self):
        text = ("# >>> vibe-suite:ignore v1 >>>\n"
                "USER DATA THEY CARE ABOUT\n"
                "# >>> vibe-suite:ignore v1 >>>\n"
                "ours\n"
                "# <<< vibe-suite:ignore <<<\n")
        self.assertFalse(unbridge.markers_sane(text, "ignore", "text"))
        # Proof the guard is not theatre: the underlying pattern really does span the user's line,
        # so an unguarded removal would delete it.
        self.assertNotIn("USER DATA", bridge._block_re("ignore", "#", "").sub("", text))
        # And the codec now refuses rather than performing that removal.
        with self.assertRaises(bridge.BridgeError):
            bridge.text_block_remove(text, "ignore")

    def test_the_toml_codec_is_guarded_too(self):
        """`toml_server_remove` used the raw pattern directly, so `.codex/config.toml` was removed
        unvalidated no matter what teardown checked beforehand."""
        text = ("# >>> vibe-suite:server:x v1 >>>\n"
                "USER DATA\n"
                "# >>> vibe-suite:server:x v1 >>>\n"
                "ours\n"
                "# <<< vibe-suite:server:x <<<\n")
        with self.assertRaises(bridge.BridgeError):
            bridge.toml_server_remove(text, "x")

    def test_a_closer_with_trailing_text_is_rejected(self):
        """The validator's grammar must match the remover's: accepting a marker the remover rejects
        would pass a document whose removal still spans user data."""
        self.assertFalse(bridge.markers_wellformed(
            "# >>> vibe-suite:ignore v1 >>>\na\n# <<< vibe-suite:ignore <<< junk\n", "ignore"))

    def test_a_lone_closing_marker_is_malformed(self):
        self.assertFalse(unbridge.markers_sane(
            "# <<< vibe-suite:ignore <<<\nmine\n", "ignore", "text"))

    def test_a_clean_pair_is_still_removed(self):
        text = "# >>> vibe-suite:ignore v1 >>>\nours\n# <<< vibe-suite:ignore <<<\n"
        self.assertTrue(unbridge.markers_sane(text, "ignore", "text"))

    def test_markers_sane_handles_the_markdown_delimiters(self):
        text = ("<!-- >>> vibe-suite:memory v1 -->\nours\n<!-- <<< vibe-suite:memory -->\n")
        self.assertTrue(unbridge.markers_sane(text, "memory", "md"))

    # -- an init-created JSON that has since become the user's ------------------------------------
    def test_an_unrelated_top_level_key_keeps_the_file(self):
        """`mcpServers` being empty was taken as "nothing of theirs is left", which was only ever
        true of that one key."""
        self.assertFalse(unbridge.json_is_only_ours(
            ".mcp.json", {"mcpServers": {}, "theirIntegration": {"token_env": "X"}}))

    def test_an_empty_owned_document_is_still_deletable(self):
        self.assertTrue(unbridge.json_is_only_ours(".mcp.json", {"mcpServers": {}}))
        self.assertTrue(unbridge.json_is_only_ours(".codex/hooks.json", {"hooks": {"Stop": []}}))

    def test_remaining_owned_entries_keep_the_file(self):
        self.assertFalse(unbridge.json_is_only_ours(
            ".codex/hooks.json", {"hooks": {"Stop": [{"command": "x"}]}}))

    def test_a_json_path_we_never_created_is_never_deleted(self):
        self.assertFalse(unbridge.json_is_only_ours(".their-config.json", {}))

    def test_a_non_object_document_is_never_deleted(self):
        self.assertFalse(unbridge.json_is_only_ours(".mcp.json", ["a list"]))

    def test_a_users_entry_keeps_the_file_even_when_its_value_is_empty(self):
        """Truthiness was the wrong test: an empty dict is falsey, so a user's server whose config
        happened to be blank did not keep its own file alive."""
        self.assertFalse(unbridge.json_is_only_ours(".mcp.json", {"mcpServers": {"mine": {}}}))
        self.assertFalse(unbridge.json_is_only_ours(
            ".codex/hooks.json", {"hooks": {"PreToolUse": []}}))

    def test_a_file_the_suite_owns_end_to_end_is_removable(self):
        """The shared rule must not reach exclusive files, or teardown strands its own state."""
        self.assertTrue(unbridge.json_is_only_ours(
            ".claude/vibe-history.json", {"entries": [{"anything": 1}]}))


class ProvenanceIsNotTrusted(unittest.TestCase):
    """The record directs every mutation, so a tampered one directed them at the user's files.

    These drive the **real command**, not the validator, because the previous round's tests passed
    against a bypassed guard by only ever calling helpers.
    """

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-prov-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.record_path = self.ws / init_bridge.PROVENANCE

    def rewrite(self, mutate):
        record = json.loads(self.record_path.read_text())
        mutate(record)
        self.record_path.write_text(json.dumps(record, indent=2))

    def unbridge(self):
        return subprocess.run(["bash", str(UNBRIDGE), "--workspace", str(self.ws), "--confirm"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def test_a_forged_target_does_not_delete_a_user_file(self):
        victim = self.ws / "notes.txt"
        victim.write_text("a year of notes")
        self.rewrite(lambda r: r["targets"].append(
            {"path": str(victim), "kind": "absent"}))
        self.assertEqual(self.unbridge().returncode, 1)
        self.assertTrue(victim.is_file())
        self.assertEqual(victim.read_text(), "a year of notes")

    def test_a_forged_created_parent_does_not_remove_a_user_directory(self):
        theirs = self.ws / "empty-but-theirs"
        theirs.mkdir()
        self.rewrite(lambda r: r.setdefault("parents_created", []).append(str(theirs)))
        self.assertEqual(self.unbridge().returncode, 1)
        self.assertTrue(theirs.is_dir())

    def test_an_honest_record_still_runs(self):
        """The guard has to reject forgeries without rejecting every real install."""
        self.assertEqual(self.unbridge().returncode, 0)


class SymlinkTargetsAreRefused(unittest.TestCase):
    """The conversion, not the teardown, was the destructive step.

    Init replacing a pre-existing symlink produced a regular 0644 copy of its target. Unbridge
    removes only what it owns, so the copy survived and the original link target went with the
    provenance — losing user-owned metadata and leaving content that had been reachable only through
    a link the user controlled sitting in an independent file. Refusing the conversion removes the
    whole class; there is nothing to restore because nothing is destroyed.
    """

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-symlink-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_writing_over_a_symlink_is_refused(self):
        secret = self.ws / "private.md"
        secret.write_text("theirs")
        link = self.ws / "CLAUDE.md"
        link.symlink_to(secret)
        with self.assertRaises(bridge.BridgeError):
            bridge.write_atomic(self.ws, link, "ours\n")
        # The link is intact, still a link, still pointing where the user put it.
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), str(secret))
        self.assertEqual(secret.read_text(), "theirs")

    def test_a_regular_file_is_still_written(self):
        target = self.ws / "CLAUDE.md"
        target.write_text("before")
        bridge.write_atomic(self.ws, target, "after\n")
        self.assertEqual(target.read_text(), "after\n")
        self.assertFalse(target.is_symlink())


class OneGrammarNotTwo(unittest.TestCase):
    """The recurring defect: a guard beside one caller, or a validator that does not share the
    grammar of the thing it guards."""

    def test_a_prefixed_marker_is_not_a_marker_to_either_parser(self):
        """The exact input the previous round's fix made *worse*: anchoring the validator while
        leaving the remover unanchored made this validate as well-formed and then be removed
        through. Both now agree it is not our marker at all, so the user's line survives."""
        text = ("prefix # >>> vibe-suite:ignore v1 >>>\n"
                "USER DATA\n"
                "prefix # <<< vibe-suite:ignore <<<\n")
        self.assertTrue(bridge.markers_wellformed(text, "ignore"))
        self.assertIn("USER DATA", bridge.text_block_remove(text, "ignore"))
        self.assertFalse(bridge.text_block_has(text, "ignore"))

    def test_a_clean_block_still_round_trips(self):
        body = "ours\n"
        built = bridge.text_block_upsert("", "ignore", body)
        self.assertTrue(bridge.text_block_has(built, "ignore"))
        self.assertEqual(bridge.text_block_remove(built, "ignore"), "")


class ProvenanceKindIsNotAuthority(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-kind-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.record_path = self.ws / init_bridge.PROVENANCE

    def rewrite(self, mutate):
        record = json.loads(self.record_path.read_text())
        mutate(record)
        self.record_path.write_text(json.dumps(record, indent=2))

    def unbridge(self):
        return subprocess.run(["bash", str(UNBRIDGE), "--workspace", str(self.ws), "--confirm"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def test_a_duplicate_entry_for_one_target_is_refused(self):
        """Two entries naming one path with different kinds meant two meanings, and the destructive
        one won."""
        def dup(record):
            first = dict(record["targets"][0])
            first["kind"] = "absent"
            record["targets"].append(first)
        self.rewrite(dup)
        self.assertEqual(self.unbridge().returncode, 1)

    def test_flipping_a_shared_file_to_absent_does_not_delete_it(self):
        """`.gitignore` carries an owned block, so its content can corroborate the record. With the
        block already gone, `kind: absent` alone must not authorise deleting the user's file."""
        gitignore = self.ws / ".gitignore"
        gitignore.write_text("node_modules/\nmine.log\n")
        self.rewrite(lambda r: [e.__setitem__("kind", "absent")
                                for e in r["targets"] if e["path"].endswith(".gitignore")])
        self.unbridge()
        self.assertTrue(gitignore.is_file(), "the user's .gitignore was deleted on the record's word")
        self.assertIn("mine.log", gitignore.read_text())


class StateDirectoryIsNotOursToEmpty(unittest.TestCase):
    """`.vibe-suite-state/` is a plain directory. Nothing stops a user putting something in it, and
    `rglob("*")` deleted every child — so a command that removes only what it owns destroyed files
    it did not."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-state-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_a_users_file_in_the_state_directory_survives(self):
        (self.ws / ".vibe-suite-state").mkdir()
        theirs = self.ws / ".vibe-suite-state" / "personal.txt"
        theirs.write_text("notes I keep here")
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        subprocess.run(["bash", str(UNBRIDGE), "--workspace", str(self.ws), "--confirm"],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertTrue(theirs.is_file(), "a user's file in the state directory was deleted")
        self.assertEqual(theirs.read_text(), "notes I keep here")

    def test_a_state_directory_holding_only_ours_is_removed(self):
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        subprocess.run(["bash", str(UNBRIDGE), "--workspace", str(self.ws), "--confirm"],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertFalse((self.ws / ".vibe-suite-state").exists(),
                         "the suite's own state directory survived teardown")


class KindAndPreImageMustAgree(unittest.TestCase):
    """Flipping `file` to `absent` left the pre-image fields behind. That disagreement is what makes
    an edited record detectable without authenticating it — and it covers accidental corruption,
    which the same-write-access argument does not."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-shape-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        (self.ws / ".vibe-suite.md").write_text("---\neffort: high\n---\nmine, from before\n")
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_an_exclusive_file_flipped_to_absent_is_refused(self):
        record_path = self.ws / init_bridge.PROVENANCE
        record = json.loads(record_path.read_text())
        for entry in record["targets"]:
            if entry["path"].endswith(".vibe-suite.md"):
                entry["kind"] = "absent"          # keep the pre-image fields, as a tamper would
        record_path.write_text(json.dumps(record, indent=2))
        proc = subprocess.run(["bash", str(UNBRIDGE), "--workspace", str(self.ws), "--confirm"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue((self.ws / ".vibe-suite.md").is_file(),
                        "a pre-existing config was deleted on a self-contradicting record")


class StateOwnershipIsCorroborated(unittest.TestCase):
    """A matching *name* is not proof of ownership — that was the allowlist's own mistake, one level
    down. A user's `state.json` sitting in this directory before install has the same name as ours."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-stateown-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_a_users_state_json_is_not_deleted_for_having_our_name(self):
        (self.ws / ".vibe-suite-state").mkdir()
        theirs = self.ws / ".vibe-suite-state" / "state.json"
        # Carries a `schema` key too: a generic field a user's own JSON may well have, which is why
        # ownership needs an explicit stamp rather than a plausible-looking one.
        theirs.write_text(json.dumps({"schema": 1, "notes": "mine"}))
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        subprocess.run(["bash", str(UNBRIDGE), "--workspace", str(self.ws), "--confirm"],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
        # Unconditional: `if theirs.exists()` made this test incapable of failing.
        self.assertTrue(theirs.is_file(), "a user's state.json was deleted for having our name")
        self.assertEqual(json.loads(theirs.read_text()), {"schema": 1, "notes": "mine"})


class ExclusiveFilesAreCorroborated(unittest.TestCase):
    """The last open hole: `.vibe-suite.md` carried no ownership evidence, so teardown deleted it on
    the record's unauthenticated word. init now marks the file when it *creates* it, which lets
    teardown prove ownership — so byte-identity and never-delete-what-we-cannot-prove both hold."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-excl-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def init(self):
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def unbridge(self):
        return subprocess.run(["bash", str(UNBRIDGE), "--workspace", str(self.ws), "--confirm"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def test_a_consistent_absent_forgery_no_longer_deletes_a_pre_existing_config(self):
        """The reviewer's input: flip `file` to `absent` AND strip the pre-image, so the record is
        internally consistent and validation cannot object. Ownership must come from the disk."""
        (self.ws / ".vibe-suite.md").write_text("---\neffort: high\n---\nmine, from before init\n")
        self.init()
        record_path = self.ws / init_bridge.PROVENANCE
        record = json.loads(record_path.read_text())
        for entry in record["targets"]:
            if entry["path"].endswith(".vibe-suite.md"):
                entry["kind"] = "absent"
                for field in ("mode", "sha256", "content_b64", "link_target"):
                    entry.pop(field, None)
        record_path.write_text(json.dumps(record, indent=2))
        self.unbridge()
        self.assertTrue((self.ws / ".vibe-suite.md").is_file(),
                        "a pre-existing config was deleted on a self-consistent forged record")
        self.assertIn("mine, from before init", (self.ws / ".vibe-suite.md").read_text())

    def test_a_config_init_created_is_still_removed(self):
        """And the other clause still holds: what init made, teardown takes away."""
        self.init()
        self.assertIn(bridge.MARKER, (self.ws / ".vibe-suite.md").read_text())
        self.unbridge()
        self.assertFalse((self.ws / ".vibe-suite.md").exists(),
                         "the suite's own config survived teardown")


class OwnershipNeedsAnExplicitStamp(unittest.TestCase):
    """Three ways a coincidence was mistaken for ownership, each now closed."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-stamp-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def init(self):
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def unbridge(self):
        return subprocess.run(["bash", str(UNBRIDGE), "--workspace", str(self.ws), "--confirm"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def test_the_word_vibe_suite_in_a_config_is_not_ownership(self):
        """`bridge.MARKER in text` was a substring test, which a migrated
        `skip_patterns: [vibe-suite]` satisfies — deleting an unmarked config on a coincidence."""
        self.assertFalse(unbridge._is_recognisably_ours(
            ".vibe-suite.md", self._write(".vibe-suite.md",
                                          "---\nskip_patterns:\n  - vibe-suite\n---\nmine\n")))

    def test_a_generic_schema_key_is_not_ownership(self):
        self.assertFalse(unbridge._is_suite_state(
            Path("state.json"), self._write("state.json", json.dumps({"schema": 1, "n": "mine"}))))

    def test_a_users_file_under_a_directory_we_use_is_not_ours(self):
        """A path prefix is not ownership: `jobs/` is a directory we happen to write into."""
        self.assertFalse(unbridge._is_suite_state(Path("jobs/notes.txt"), None))

    def test_a_pre_existing_history_is_not_deleted(self):
        """The exclusive-JSON check used to be unreachable — `json_is_only_ours` returned True for
        this path unconditionally, so the corroboration below it never ran."""
        (self.ws / ".claude").mkdir(parents=True, exist_ok=True)
        theirs = self.ws / ".claude" / "vibe-history.json"
        theirs.write_text(json.dumps({"snapshots": [{"score": 91}], "mine": True}))
        self.init()
        record_path = self.ws / init_bridge.PROVENANCE
        record = json.loads(record_path.read_text())
        for entry in record["targets"]:
            if entry["path"].endswith("vibe-history.json"):
                entry["kind"] = "absent"
                for field in ("mode", "sha256", "content_b64", "link_target"):
                    entry.pop(field, None)
        record_path.write_text(json.dumps(record, indent=2))
        self.unbridge()
        self.assertTrue(theirs.is_file(), "a pre-existing history was deleted on a forged record")
        self.assertTrue(json.loads(theirs.read_text()).get("mine"))

    def _write(self, name, text):
        path = self.ws / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path


class OwnershipOfThingsInitTouches(unittest.TestCase):
    """Two paths that claimed ownership by filename alone."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-touch-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_a_symlinked_config_is_refused_not_replaced(self):
        """`_verify_config` used `os.replace`, a direct rename that never reaches `write_atomic` —
        so the symlink refusal there did not see this path. Replacing the link would convert it to a
        regular copy, and teardown records `kind: symlink` but never restores one."""
        real = self.ws / "elsewhere.md"
        real.write_text("---\neffort: high\n---\ntheirs\n")
        (self.ws / ".vibe-suite.md").symlink_to(real)
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, "init replaced a symlinked config instead of refusing")
        self.assertTrue((self.ws / ".vibe-suite.md").is_symlink(), "the user's link was replaced")
        self.assertEqual(real.read_text(), "---\neffort: high\n---\ntheirs\n")

    def test_a_foreign_hook_side_file_is_not_overwritten_or_deleted(self):
        (self.ws / ".codex").mkdir(parents=True)
        side = self.ws / ".codex" / "hooks.vibe-suite.json"
        side.write_text(json.dumps({"hooks": {"Stop": [{"command": "theirs"}]}}))
        subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                        "--audit-depth", "mini", "--strictness", "standard"],
                       capture_output=True, text=True)
        self.assertTrue(side.is_file(), "a foreign hook side file was deleted")
        self.assertEqual(json.loads(side.read_text())["hooks"]["Stop"][0]["command"], "theirs")


class LstatNotExists(unittest.TestCase):
    """One root cause, three sites. `exists()` follows the link, so a **dangling** symlink reports
    False and every existence guard waves it through — which is how the user's link was replaced by
    three different writers in turn, each fixed one pass after the last."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-lstat-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def init(self):
        return subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                               "--audit-depth", "mini", "--strictness", "standard"],
                              capture_output=True, text=True)

    def test_a_dangling_config_symlink_survives_migration(self):
        """The earliest writer is `migrate-config.sh`, not `_verify_config` — guarding the later one
        left the path open. A dangling link is the case `exists()` cannot see."""
        (self.ws / ".cc-suite.md").write_text("---\neffort: high\n---\n")
        (self.ws / ".vibe-suite.md").symlink_to(self.ws / "missing.md")
        self.init()
        self.assertTrue((self.ws / ".vibe-suite.md").is_symlink(),
                        "a dangling user symlink was replaced by a regular file")

    def test_an_occupied_scratch_path_is_not_consumed(self):
        theirs = self.ws / ".{}.vibe-candidate".format(".vibe-suite.md".lstrip("."))
        theirs.write_text("something of mine")
        self.init()
        if theirs.exists():
            self.assertEqual(theirs.read_text(), "something of mine")

    def test_a_symlink_in_the_state_dir_is_judged_as_a_link(self):
        """`load_json` follows the link, so the destination's ownership stamp was read as ownership
        of the link itself."""
        (self.ws / ".vibe-suite-state").mkdir(parents=True, exist_ok=True)
        stamped = self.ws / "stamped.json"
        stamped.write_text(json.dumps({"vibe_suite_owned": True}))
        link = self.ws / ".vibe-suite-state" / "config.json"
        link.symlink_to(stamped)
        self.assertFalse(unbridge._is_suite_state(Path("config.json"), link))


class TheRootIsTheWorkspaceNotTheParent(unittest.TestCase):
    """Passing the destination's own parent as the primitive's root makes a **symlinked parent the
    trusted anchor** — `assert_inside` then compares the escape against itself and passes it."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-root-"))
        self.outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.outside, ignore_errors=True)

    def test_a_symlinked_state_dir_cannot_redirect_a_write_outside(self):
        theirs = self.outside / "state.json"
        theirs.write_text(json.dumps({"config": {"gate": {"fail_policy": "open"}}}))
        (self.ws / ".vibe-suite-state").symlink_to(self.outside)
        subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "config_cli.py"),
                        "--workspace", str(self.ws), "--set", "gate.fail_policy=closed"],
                       capture_output=True, text=True)
        self.assertEqual(json.loads(theirs.read_text())["config"]["gate"]["fail_policy"], "open",
                         "a write escaped the workspace through a symlinked state directory")


class RowSixProvenanceDoesNotPublishSecrets(unittest.TestCase):
    """Row 6's record holds complete `.mcp.json` pre-images — and `.mcp.json` is where credentials
    live. Writing it at the default mode is the `c2112ac` leak in the row that migrates the very
    file the secrets are in."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-row6-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_the_record_is_not_group_or_world_readable(self):
        mcp = self.ws / ".mcp.json"
        mcp.write_text(json.dumps(
            {"mcpServers": {"cc-suite-mcp": {"command": "x", "env": {"TOKEN": "s3cret"}}}}))
        os.chmod(mcp, 0o600)
        subprocess.run(["bash", str(REPO_ROOT / "scripts/migrate/migrate-sentinels.sh"),
                        "--workspace", str(self.ws), "--confirm"], capture_output=True, text=True)
        record = self.ws / ".vibe-suite-state" / "row6-provenance.json"
        self.assertTrue(record.is_file(), "row 6 wrote no provenance — the fixture proves nothing")
        self.assertIn("s3cret", record.read_text(),
                      "the fixture does not exercise the leak: no secret reached the record")
        mode = stat.S_IMODE(record.lstat().st_mode)
        dir_mode = stat.S_IMODE(record.parent.lstat().st_mode)
        self.assertEqual(mode & 0o077, 0, f"the record is readable at {oct(mode)}")
        self.assertEqual(dir_mode & 0o077, 0, f"its directory is traversable at {oct(dir_mode)}")


class TestAdvisorTeardown(UnbridgeCase):
    """E6.1: bare-name advisor registrations are inventory-visible, so teardown removes them.
    vibe-185: the advisor ledger (acceptances + registration stamps) and a pending journal are the
    suite's records — they go with the registrations they authorise."""

    def test_the_advisor_ledger_and_journal_do_not_outlive_teardown(self):
        self.install()
        agents = self.ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "probe_advisor.md").write_text(
            "---\ndescription: |\n  Judges probe things.\nmodel: sonnet\n---\n\nValue truth.\n", encoding="utf-8")
        import subprocess as sp
        r = sp.run(["python3", str(REPO_ROOT / "scripts" / "advisor_cli.py"), "--workspace", str(self.ws),
                    "add", "probe_advisor"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        state = self.ws / ".vibe-suite-state"
        self.assertTrue((state / "advisor-preimages.json").is_file(), "precondition: the stamp is on disk")
        crashed = sp.run(["python3", str(REPO_ROOT / "scripts" / "advisor_cli.py"), "--workspace", str(self.ws),
                          "remove", "probe_advisor", "--delete-timeline"], capture_output=True, text=True,
                         env=dict(os.environ, VIBE_ADVISOR_FAIL_AFTER="json"))
        self.assertEqual(crashed.returncode, 9, crashed.stderr)
        self.assertTrue((state / "advisor-txn.json").is_file(), "precondition: a pending journal is on disk")
        self.assertEqual(self.unbridge("--confirm").returncode, 0)
        self.assertFalse((state / "advisor-preimages.json").exists(), "the ledger went with the registrations")
        self.assertFalse((state / "advisor-txn.json").exists(), "so did the journal")
        self.assertNotIn("probe_advisor", (json.loads((self.ws / ".mcp.json").read_text()) if (self.ws / ".mcp.json").is_file() else {}).get("mcpServers", {}))

    def test_lookalike_advisor_records_and_symlinks_survive_teardown(self):
        # The recogniser demands the COMPLETE schema the suite writes; a same-named file that merely
        # resembles it — a user's own, or a truncated copy — is not ours to delete.
        self.install()
        state = self.ws / ".vibe-suite-state"
        state.mkdir(exist_ok=True)
        lookalikes = {
            "advisor-preimages.json": json.dumps({"registered": "nope"}) + "\n",
            "advisor-txn.json": json.dumps({"schema": 1, "intent": "apply"}) + "\n",
        }
        for name, text in lookalikes.items():
            (state / name).write_text(text, encoding="utf-8")
        elsewhere = self.ws / "my-ledger.json"
        elsewhere.write_text(json.dumps({".mcp.json": None}) + "\n", encoding="utf-8")
        link = state / "advisor-preimages.json"
        link.unlink(); link.symlink_to(elsewhere)                                 # a symlink named like the ledger
        r = self.unbridge("--confirm")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(link.is_symlink(), "a symlink named like the ledger is left alone")
        self.assertTrue(elsewhere.is_file(), "and its target is untouched")
        self.assertTrue((state / "advisor-txn.json").is_file(), "a journal lookalike is left alone")
        self.assertIn("left alone", r.stdout + r.stderr)

    def test_full_key_near_miss_records_are_not_recognised_as_ours(self):
        # The recogniser demands the EXACT writer shape: a journal or ledger that carries every key but
        # a value the writer never produces is not ours. Templates come from a real crashed transaction;
        # the end-to-end removal of real records is `test_the_advisor_ledger_and_journal_do_not_outlive_teardown`.
        import subprocess as sp, copy, sys as _sys
        _sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import unbridge as unbridge_mod
        self.install()
        agents = self.ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "probe_advisor.md").write_text(
            "---\ndescription: |\n  Judges probe things.\nmodel: sonnet\n---\n\nValue truth.\n", encoding="utf-8")
        cli = ["python3", str(REPO_ROOT / "scripts" / "advisor_cli.py"), "--workspace", str(self.ws)]
        self.assertEqual(sp.run([*cli, "add", "probe_advisor"], capture_output=True, text=True).returncode, 0)
        state = self.ws / ".vibe-suite-state"
        ledger_path = state / "advisor-preimages.json"
        crashed = sp.run([*cli, "remove", "probe_advisor", "--delete-timeline"], capture_output=True, text=True,
                         env=dict(os.environ, VIBE_ADVISOR_FAIL_AFTER="json"))
        self.assertEqual(crashed.returncode, 9, crashed.stderr)
        txn_path = state / "advisor-txn.json"
        real_journal = json.loads(txn_path.read_text()); real_ledger = json.loads(ledger_path.read_text())
        self.assertEqual(real_journal["intent"], "remove")
        ours = lambda name, path: unbridge_mod._advisor_record_is_ours(name, path)
        self.assertTrue(ours("advisor-txn.json", txn_path), "control: the real journal is ours")
        self.assertTrue(ours("advisor-preimages.json", ledger_path), "control: the real ledger is ours")
        probe = state / "advisor-txn.json"
        def near_misses():
            j = copy.deepcopy(real_journal); j["intent"] = "apply"; j["delete_timeline"] = False
            yield "apply-with-remove-fields", j                       # an apply journal carrying a remove_name and a definition pre-image
            j = copy.deepcopy(real_journal); j["pre_images"][".mcp.json"]["extra"] = 1
            yield "image-extra-field", j                              # an image with a field the writer never adds
            j = copy.deepcopy(real_journal); j["pre_images"][".mcp.json"]["path"] = "/etc/passwd"
            yield "image-foreign-path", j                             # an image for some other file
            j = copy.deepcopy(real_journal); j.pop("registered")
            yield "missing-registered-member", j                      # still recoverable (pre-vibe-185 shape) — but not the writer's shape now
            j = copy.deepcopy(real_journal); j["remove_name"] = "some_other"
            yield "definition-image-for-another-name", j              # the definition pre-image names probe_advisor, the journal another advisor
        for label, j in near_misses():
            with self.subTest(journal=label):
                probe.write_text(json.dumps(j) + "\n", encoding="utf-8")
                self.assertFalse(ours("advisor-txn.json", probe), f"{label}: a full-key near-miss journal is not ours")
        probe.write_text(json.dumps(real_journal) + "\n", encoding="utf-8")
        self.assertTrue(ours("advisor-txn.json", probe))
        lookalike = copy.deepcopy(real_ledger); lookalike[".mcp.json"]["path"] = str(self.ws / "elsewhere.json")
        ledger_path.write_text(json.dumps(lookalike) + "\n", encoding="utf-8")
        self.assertFalse(ours("advisor-preimages.json", ledger_path), "a ledger whose image names another file is not ours")
        lookalike = copy.deepcopy(real_ledger); lookalike[".mcp.json"]["mode"] = "0644"; lookalike[".mcp.json"]["sha256"] = "0" * 64
        ledger_path.write_text(json.dumps(lookalike) + "\n", encoding="utf-8")
        self.assertFalse(ours("advisor-preimages.json", ledger_path), "an image whose sha does not match its content is not ours")
        ledger_path.write_text(json.dumps(real_ledger) + "\n", encoding="utf-8")
        self.assertTrue(ours("advisor-preimages.json", ledger_path))

    def test_marker_and_fence_registrations_are_torn_down(self):
        self.install()
        mcp = self.ws / ".mcp.json"
        doc = json.loads(mcp.read_text())
        doc.setdefault("mcpServers", {})["probe_advisor"] = {
            "command": "npx", "args": ["-y", "claude-octopus@9.9.9"], "env": {},
            "_vibe-suite_owned": {"kind": "advisor", "schema": 1}}
        mcp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        toml = self.ws / ".codex" / "config.toml"
        block = ("# >>> vibe-suite:server:probe_advisor v1 >>>\n"
                 '[mcp_servers.probe_advisor]\ncommand = "npx"\n'
                 "# <<< vibe-suite:server:probe_advisor <<<\n")
        toml.parent.mkdir(exist_ok=True)
        existing = toml.read_text() if toml.is_file() else ""
        toml.write_text(existing + ("\n" if existing and not existing.endswith("\n") else "") + block)
        self.assertEqual(self.unbridge("--confirm").returncode, 0)
        after = json.loads(mcp.read_text()) if mcp.is_file() else {}
        self.assertNotIn("probe_advisor", (after.get("mcpServers") or {}))
        if toml.is_file():
            self.assertNotIn("probe_advisor", toml.read_text())


class ListedNonJsonStateFile(UnbridgeCase):
    """vibe-265: `migration-conflicts.txt` is listed in SUITE_STATE and is prose, not JSON.

    Before the fix `_is_suite_state` sent it to `load_json`, which raised; the walk aborted after
    it had already unlinked every deeper child, and `print` — then sitting after the loop — was
    never reached. The file carries an ownership stamp *specifically* so a re-run recognises it.
    """

    STAMP = bridge.MIGRATION_CONFLICTS_STAMP

    def ours(self, name, path):
        return unbridge._is_suite_state(Path(name), path)

    def state(self):
        d = self.ws / ".vibe-suite-state"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def written_by_the_migration(self):
        """A real stamped report, produced by RUNNING the writer — never a hand-typed literal.

        A hand-typed stamp would keep passing if the reader and `migrate-state.sh` ever diverged,
        which is this very defect one level up.
        """
        for name, value in ((".cc-suite-state", True), (".codex-toolkit-state", False)):
            d = self.ws / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "state.json").write_text(json.dumps({"config": {"stopReviewGate": value}}))
        self.state()
        r = subprocess.run(["bash", str(REPO_ROOT / "scripts/migrate/migrate-state.sh"),
                            "--workspace", str(self.ws)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 3, r.stderr)
        report = self.ws / ".vibe-suite-state" / "migration-conflicts.txt"
        self.assertTrue(report.is_file(), "precondition: the migration wrote its conflicts report")
        self.assertTrue(report.read_text(encoding="utf-8").startswith(self.STAMP),
                        "precondition: the writer stamped its own output")
        return report

    # T1
    def test_a_stamped_report_written_by_the_migration_is_ours(self):
        report = self.written_by_the_migration()
        self.assertTrue(self.ours("migration-conflicts.txt", report))

    # T2
    def test_a_users_unstamped_file_at_that_path_is_left_alone(self):
        path = self.state() / "migration-conflicts.txt"
        path.write_text("my own notes about a migration\n", encoding="utf-8")
        self.assertFalse(self.ours("migration-conflicts.txt", path))

    # T3
    def test_a_member_that_is_not_utf8_is_left_alone_and_does_not_raise(self):
        path = self.state() / "migration-conflicts.txt"
        path.write_bytes(b"\xff\xfe not text at all\n")
        self.assertFalse(self.ours("migration-conflicts.txt", path),
                         "undecodable bytes must be unowned, not an uncaught UnicodeDecodeError")

    # T4 — regression: this already passed before vibe-265.
    def test_a_directory_at_that_path_is_left_alone(self):
        path = self.state() / "migration-conflicts.txt"
        path.mkdir()
        self.assertFalse(self.ours("migration-conflicts.txt", path))

    # T5
    def test_a_near_miss_stamp_is_not_the_writers_shape(self):
        report = self.written_by_the_migration()
        real = report.read_text(encoding="utf-8")
        body = real[len(self.STAMP):]
        self.assertTrue(self.ours("migration-conflicts.txt", report), "control: the real report is ours")

        def near_misses():
            yield "wrong-marker-text", "# vibe-suite-owned: migration-conflict\n" + body
            yield "marker-cased", self.STAMP.upper() + body
            yield "stamp-not-on-the-first-line", "row 5: a note\n" + self.STAMP + body
            yield "leading-whitespace", " " + self.STAMP + body
            yield "leading-blank-line", "\n" + self.STAMP + body
            yield "stamp-without-its-newline", self.STAMP.rstrip("\n") + " extra\n" + body
            yield "empty", ""

        # Byte-level near-misses. `read_text` translates CRLF and bare CR to LF, so these two were
        # normalised into the writer's stamp and DELETED — a user's Windows-authored file at a path
        # the suite happens to know. The shape test is on bytes precisely so they cannot match.
        for label, head in (("crlf-after-the-marker", self.STAMP.rstrip("\n").encode() + b"\r\n"),
                            ("bare-cr-after-the-marker", self.STAMP.rstrip("\n").encode() + b"\r")):
            with self.subTest(shape=label):
                report.write_bytes(head + body.encode("utf-8"))
                self.assertFalse(self.ours("migration-conflicts.txt", report),
                                 f"{label}: only the writer's exact byte sequence is ours")

        for label, text in near_misses():
            with self.subTest(shape=label):
                report.write_text(text, encoding="utf-8")
                self.assertFalse(self.ours("migration-conflicts.txt", report),
                                 f"{label}: a near-miss stamp is not the writer's exact shape")

        # The stamp is ASCII, so `errors="replace"` would preserve it and call this ours. The read
        # is strict precisely so a file we cannot decode end to end is never deleted.
        report.write_bytes(self.STAMP.encode("utf-8") + b"\xff\xfe binary tail\n")
        self.assertFalse(self.ours("migration-conflicts.txt", report),
                         "an exact stamp above undecodable bytes must still be left alone")

        report.write_text(real, encoding="utf-8")
        self.assertTrue(self.ours("migration-conflicts.txt", report), "control: still ours afterwards")

    # T6 — bullet 5: JSON members are unchanged. Guards against widening the catch too far.
    def test_an_unparseable_json_member_still_raises(self):
        path = self.state() / "state.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(bridge.BridgeError):
            self.ours("state.json", path)

    # T10 — regression: placement of the new branch must not disturb these.
    def test_symlinks_and_deeper_paths_are_still_judged_first(self):
        state = self.state()
        outside = self.ws / "keep.txt"
        outside.write_text(self.STAMP, encoding="utf-8")
        link = state / "migration-conflicts.txt"
        link.symlink_to(outside)
        self.assertFalse(self.ours("migration-conflicts.txt", link),
                         "a symlink is judged before any name shortcut")
        nested = state / "jobs"
        nested.mkdir()
        deep = nested / "migration-conflicts.txt"
        deep.write_text(self.STAMP, encoding="utf-8")
        self.assertFalse(unbridge._is_suite_state(Path("jobs/migration-conflicts.txt"), deep),
                         "a path deeper than one component is still rejected")


class StampHasOneDefinitionOnTheReaderSide(unittest.TestCase):
    """T18 — the mirror of `test_migrate`'s T12, and it was missing.

    A value test cannot see this: replacing the shared reference with an identical private literal
    leaves every behavioural test green while restoring the two-definitions state that vibe-265 was.
    The writer side was pinned structurally from the start; the reader side was not, so the design's
    central claim — one definition, nothing to drift — held only by convention on this half.
    """

    SOURCE = REPO_ROOT / "scripts" / "lib" / "unbridge.py"
    LITERAL = "# vibe-suite-owned: migration-conflicts"

    def test_unbridge_sources_the_stamp_and_keeps_no_literal_of_its_own(self):
        text = self.SOURCE.read_text(encoding="utf-8")
        self.assertIn("bridge.MIGRATION_CONFLICTS_STAMP", text,
                      "the recogniser must take the stamp from the shared definition")
        self.assertNotIn(self.LITERAL, text,
                         "a second copy of the stamp is what vibe-265 was; there must be exactly one")


class SharedOwnershipCheckIsUsed(UnbridgeCase):
    """vibe-271: pin that the ownership DECISION routes through `bridge.stamp_matches`.

    #265 made the delete-side and overwrite-side share one check so they could not disagree about
    who owns a file. Nothing tested that either side still *calls* it: a byte-identical private copy
    left the whole suite green, restoring the two-implementation state #265 exists to prevent.

    Three weaker properties were tried and each is defeated by a real mutant, which is why the
    assertions below look heavier than they might:

    * *the call appears in the source* — satisfied by the docstring and comment above `:306`;
    * *the call executes* — satisfied by `(stamp_matches(...) or True) and private(...)`;
    * *the forced answer is followed* — satisfied by a private VETO on a naturally-matching fixture.

    What survives all three is **one shared call per decision, and the decision equals its return**,
    across fixture classes and repeated visits.
    """

    STAMP = bridge.MIGRATION_CONFLICTS_STAMP

    def state(self):
        d = self.ws / ".vibe-suite-state"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def fixtures(self):
        """The content classes the acceptance criteria enumerate, with their natural answers."""
        return (
            ("stamped", self.STAMP.encode() + b"row 5\n"),
            ("unstamped", b"my own notes\n"),
            ("crlf", self.STAMP.rstrip("\n").encode() + b"\r\nnotes\r\n"),
            ("invalid-utf8", self.STAMP.encode() + b"\xff\xfe"),
            ("empty", b""),
        )

    def test_every_decision_makes_exactly_one_shared_call_and_follows_it(self):
        import unittest.mock as mock
        for label, raw in self.fixtures():
            for forced in (True, False):
                with self.subTest(fixture=label, forced=forced):
                    path = self.state() / "migration-conflicts.txt"
                    path.write_bytes(raw)
                    with mock.patch.object(bridge, "stamp_matches",
                                           return_value=forced) as spy:
                        # TWO decisions on the same path: a first-call cache would make one call.
                        first = unbridge._is_suite_state(Path("migration-conflicts.txt"), path)
                        second = unbridge._is_suite_state(Path("migration-conflicts.txt"), path)
                    self.assertEqual(spy.call_count, 2,
                                     f"{label}: {spy.call_count} shared call(s) for 2 decisions")
                    self.assertIs(first, forced, f"{label}: decision ignored the shared answer")
                    self.assertIs(second, forced, f"{label}: repeat decision diverged")

    def test_the_shared_check_receives_the_path_and_that_members_stamp(self):
        import unittest.mock as mock
        path = self.state() / "migration-conflicts.txt"
        path.write_bytes(self.STAMP.encode())
        with mock.patch.object(bridge, "stamp_matches", return_value=True) as spy:
            unbridge._is_suite_state(Path("migration-conflicts.txt"), path)
        spy.assert_called_once_with(path, unbridge.SUITE_STATE_STAMPS["migration-conflicts.txt"])


class TeardownReportSurvives(UnbridgeCase):
    """vibe-265: `print` used to sit after the walk, so any raise inside it lost the whole report."""

    # T8 — end to end, the issue's first acceptance criterion.
    def test_a_workspace_with_a_stamped_conflicts_report_tears_down_completely(self):
        self.install()
        report = self.ws / ".vibe-suite-state" / "migration-conflicts.txt"
        report.write_text(bridge.MIGRATION_CONFLICTS_STAMP + "row 5: legacy dirs disagree\n",
                          encoding="utf-8")
        r = self.unbridge("--confirm")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(report.exists(), "the stamped report is ours and must be removed")
        self.assertFalse((self.ws / ".vibe-suite-state").exists(),
                         "with everything in it ours, the state directory goes too")
        self.assertTrue(r.stdout.strip(), "the run must print its report")

    # T7 — the report survives a raise inside the walk.
    def test_a_raise_inside_the_walk_still_prints_the_report(self):
        self.install()
        state = self.ws / ".vibe-suite-state"
        # A listed JSON member that cannot be parsed. `load_json` raises by design (bullet 5).
        (state / "history.json").write_text("{not json", encoding="utf-8")
        r = self.unbridge("--confirm")
        self.assertNotEqual(r.returncode, 0, "an unreadable JSON member still fails the run")
        self.assertTrue(r.stdout.strip(),
                        "the report must reach stdout even though the walk raised")
        self.assertIn("error:", r.stderr)

    # T11 — an unlink failure is reported, not thrown as a traceback.
    @unittest.skipIf(os.geteuid() == 0, "permission bits do not bind root")
    def test_an_unlink_failure_is_a_message_not_a_traceback(self):
        self.install()
        state = self.ws / ".vibe-suite-state"
        self.assertTrue((state / "install-provenance.json").is_file(), "precondition: a member to unlink")
        os.chmod(state, 0o500)                      # r-x: entries cannot be removed from it
        self.addCleanup(os.chmod, state, 0o700)
        r = self.unbridge("--confirm")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stdout.strip(), "the report must reach stdout")
        self.assertIn("error:", r.stderr)
        self.assertIn("teardown could not complete", r.stderr)
        self.assertNotIn("Traceback", r.stderr, "a permission failure must not surface as a traceback")

    # T13 — the newline case end to end: a user's CRLF file must SURVIVE a completed teardown.
    def test_a_users_crlf_file_at_that_path_survives_teardown(self):
        self.install()
        report = self.ws / ".vibe-suite-state" / "migration-conflicts.txt"
        raw = bridge.MIGRATION_CONFLICTS_STAMP.rstrip("\n").encode() + b"\r\nmy own notes\r\n"
        report.write_bytes(raw)
        r = self.unbridge("--confirm")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(report.is_file(), "a user's CRLF file was deleted by teardown")
        self.assertEqual(report.read_bytes(), raw, "the user's bytes were altered")
        self.assertIn("not a suite state file", r.stdout)

    # T14 — an OSError raised BEFORE the state-directory walk must not be blamed on that directory.
    @unittest.skipIf(os.geteuid() == 0, "permission bits do not bind root")
    def test_a_failure_before_the_walk_is_not_attributed_to_the_state_directory(self):
        self.install()
        target = self.ws / ".claude"
        self.assertTrue(target.is_dir(), "precondition: a restore/prune target outside the state dir")
        os.chmod(target, 0o500)
        self.addCleanup(os.chmod, target, 0o700)
        r = self.unbridge("--confirm")
        if r.returncode == 0:
            self.skipTest("this workspace shape did not force an error before the walk")
        self.assertNotIn(".vibe-suite-state/: teardown could not complete", r.stderr,
                         "a failure elsewhere was misattributed to the state directory")
        # Positively assert the normalised message, so an unrelated non-zero exit cannot false-pass.
        self.assertIn("teardown could not complete", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
