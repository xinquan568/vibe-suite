#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Validate the vibe-suite plugin manifest pair (E0.1 / vibe-3).

These assertions are the scaffold's contract. `.claude-plugin/plugin.json` is the component
manifest — its `name` also fixes the command namespace (`/vibe-suite:*`), so it is asserted
exactly. `.claude-plugin/marketplace.json` is the installation pointer; its `source` object is
what a local install resolves, so its shape is asserted rather than merely its presence.
"""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_MANIFEST = REPO_ROOT / ".claude-plugin" / "marketplace.json"

PLUGIN_NAME = "vibe-suite"
REPO_SLUG = "xinquan568/vibe-suite"
COMPONENT_KEYS = ("commands", "agents", "skills")


def _load(path):
    if not path.exists():
        raise AssertionError(f"manifest not found: {path.relative_to(REPO_ROOT)}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


class TestPluginManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = _load(PLUGIN_MANIFEST)

    def test_name_fixes_the_command_namespace(self):
        # Claude Code derives a command's prefix from this field; `vibe-suite` yields
        # `/vibe-suite:*` (D1-revised). Changing it renames every command in the plugin.
        self.assertEqual(self.manifest.get("name"), PLUGIN_NAME)

    def test_required_metadata_present(self):
        for key in ("version", "description"):
            with self.subTest(key=key):
                self.assertTrue(str(self.manifest.get(key, "")).strip(), f"{key} must be non-empty")

    def test_component_arrays_declared_as_lists(self):
        # The manifest declares each component key explicitly and each later issue registers its
        # own artifact. The durable contract is that the arrays are ACCURATE, not that they are
        # empty — emptiness held only for the scaffold commit, before anything was registered.
        for key in COMPONENT_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, self.manifest, f"{key} must be declared explicitly")
                self.assertIsInstance(self.manifest[key], list, f"{key} must be a list")

    def test_registered_components_exist_on_disk(self):
        # An entry naming a path that is not there is worse than no entry: the manifest asserts a
        # component the loader cannot find.
        for key in COMPONENT_KEYS:
            for entry in self.manifest.get(key, []):
                with self.subTest(key=key, entry=entry):
                    self.assertTrue(
                        (REPO_ROOT / entry).exists(),
                        f"{key} registers {entry}, which does not exist",
                    )

    def test_registered_skills_match_disk_exactly(self):
        # D-f: `skills` contains exactly the skills that exist. assertIn would miss both failure
        # directions — a stale entry for a deleted skill, and a skill on disk nobody registered.
        # Deriving the expected set from disk catches each.
        on_disk = {
            f"./skills/{d.name}"
            for d in (REPO_ROOT / "skills").iterdir()
            if d.is_dir() and (d / "SKILL.md").is_file()
        }
        self.assertEqual(
            set(self.manifest.get("skills", [])), on_disk,
            "plugin.json:skills must match the skills present on disk exactly",
        )

    def test_license_is_isc(self):
        self.assertEqual(self.manifest.get("license"), "ISC")


class TestMarketplaceManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = _load(MARKETPLACE_MANIFEST)

    def test_declares_exactly_one_plugin(self):
        plugins = self.manifest.get("plugins")
        self.assertIsInstance(plugins, list, "plugins must be a list")
        self.assertEqual(len(plugins), 1, "single-plugin marketplace: expected exactly one entry")

    def test_entry_name_matches_plugin_manifest(self):
        self.assertEqual(self.manifest["plugins"][0].get("name"), PLUGIN_NAME)

    def test_source_pointer_shape(self):
        # What an install resolves. The intent of this check has not changed — a malformed
        # source passes a presence check while breaking installation — but E7.5 (vibe-57)
        # narrowed the correct shape on evidence: a separate `github` object resolves
        # INDEPENDENTLY of the marketplace fetch, so the listing and the installed bytes can
        # come from different commits. A smoke run this way silently installed origin/main
        # instead of the branch under test. `"./"` means "this same repository, this same
        # commit", which is true here because the marketplace ships inside the plugin repo.
        source = self.manifest["plugins"][0].get("source")
        self.assertEqual(source, "./",
                         "the plugin ships in the marketplace's own repository; a separate "
                         "source lets the two resolve to different commits")
        # the repository identity still has to be stated, and still has to be this repo
        self.assertEqual(self.manifest["owner"]["url"].rsplit("/", 1)[-1],
                         REPO_SLUG.split("/")[0])


class TestComponentRegistration(unittest.TestCase):
    """`commands/` and `agents/` are scanned for flat component files. Through E1.1 the scaffold
    asserted these directories held NO bare `.md` at all; E1.2 (vibe-12) ships the first real
    command, so the guard becomes a consistency contract: every flat `.md` carries frontmatter
    (`--strict` validation fails without it) and manifest and disk agree in both directions.
    Subdirectories (`commands/shared/`) are not component-scanned and stay exempt.
    """

    SCANNED_DIRS = ("commands", "agents")

    def setUp(self):
        self.manifest = _load(PLUGIN_MANIFEST)

    @staticmethod
    def _frontmatter(path):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            return None
        end = text.find("\n---", 4)
        return text[4:end] if end != -1 else None

    def test_flat_component_markdown_carries_frontmatter(self):
        for name in self.SCANNED_DIRS:
            directory = REPO_ROOT / name
            if not directory.is_dir():
                continue
            for md in sorted(directory.glob("*.md")):
                with self.subTest(component=f"{name}/{md.name}"):
                    frontmatter = self._frontmatter(md)
                    self.assertIsNotNone(
                        frontmatter,
                        f"{name}/{md.name} is component-scanned and fails --strict validation "
                        f"without a frontmatter block")
                    self.assertIn("description:", frontmatter,
                                  f"{name}/{md.name}: frontmatter must carry a description")

    def test_manifest_entries_exist_on_disk(self):
        for key in ("commands", "agents"):
            for entry in self.manifest.get(key, []):
                with self.subTest(entry=entry):
                    self.assertTrue(entry.startswith("./"), f"{key} entry must be repo-relative: {entry}")
                    self.assertTrue((REPO_ROOT / entry).is_file(), f"{key} entry missing on disk: {entry}")

    def test_flat_component_files_are_registered(self):
        for name, key in (("commands", "commands"), ("agents", "agents")):
            directory = REPO_ROOT / name
            on_disk = {f"./{name}/{p.name}" for p in directory.glob("*.md")} if directory.is_dir() else set()
            registered = set(self.manifest.get(key, []))
            with self.subTest(directory=name):
                self.assertEqual(
                    on_disk, registered,
                    f"{name}/ and plugin.json:{key} disagree — an unregistered command does not "
                    f"exist to Claude Code, and a registered ghost fails validation")

    def test_at_least_one_command_ships(self):
        # E1.2 onward this is a repo invariant: the plugin is not command-less. Written before the
        # implementation landed (TDD RED) and kept as a regression floor.
        self.assertTrue(self.manifest.get("commands"),
                        "plugin.json:commands is empty — /vibe-suite:jobs (vibe-12) must be registered")


if __name__ == "__main__":
    unittest.main()
