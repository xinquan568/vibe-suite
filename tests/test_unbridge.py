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
