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
        # This object is what a local install resolves. A malformed source would pass a mere
        # presence check while making the plugin uninstallable.
        source = self.manifest["plugins"][0].get("source")
        self.assertIsInstance(source, dict, "source must be an object")
        self.assertEqual(source.get("source"), "github")
        self.assertEqual(source.get("repo"), REPO_SLUG)


class TestComponentDirectoryMarkers(unittest.TestCase):
    """`commands/` and `agents/` are scanned for flat component files, so any `.md` placed
    directly in them is parsed as a command or agent and must carry frontmatter. Inert markers
    are used there instead; their explanation lives in the root README's layout table.
    Regression guard for `claude plugin validate .claude-plugin/plugin.json --strict`.
    """

    SCANNED_DIRS = ("commands", "agents")

    def test_no_bare_markdown_in_scanned_component_dirs(self):
        for name in self.SCANNED_DIRS:
            directory = REPO_ROOT / name
            if not directory.is_dir():
                continue
            stray = sorted(p.name for p in directory.glob("*.md"))
            with self.subTest(directory=name):
                self.assertEqual(
                    stray, [],
                    f"{name}/ is component-scanned: a bare .md there is parsed as a component "
                    f"and fails --strict validation without frontmatter. Found: {stray}",
                )


if __name__ == "__main__":
    unittest.main()
