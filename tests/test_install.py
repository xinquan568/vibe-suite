#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""E7.5 (vibe-57): the artifacts a clean-machine install ships.

Two defects reached `main` because nothing here checked them, and both were invisible to every
existing gate:

  * `skills/rules` and `skills/runs-stats` carried an unquoted `: ` inside their `description`
    scalar. The frontmatter did not parse, so at runtime those skills loaded with EMPTY
    metadata — two of the registered skills could never trigger, on any install.
  * `plugin.json` declared `hooks: ./hooks/hooks.json`, which Claude Code also loads
    automatically. On a clean install the whole plugin reported **failed to load** with a
    duplicate-hooks error.

So the assertions below are about installability, not style, and each one names the failure it
prevents. Frontmatter is checked with a YAML subset checker rather than a parser (the suite is
stdlib-only) whose one job is to catch exactly the plain-scalar syntax that broke here — the
negative fixtures in `FrontmatterSyntax` pin that it does.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKET = REPO_ROOT / ".claude-plugin" / "marketplace.json"
README = REPO_ROOT / "README.md"


def manifest():
    return json.loads(PLUGIN.read_text(encoding="utf-8"))


def marketplace():
    return json.loads(MARKET.read_text(encoding="utf-8"))


def frontmatter_of(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    return parts[1] if len(parts) > 2 else None


def scalar_problem(line):
    """The plain-scalar defect this module exists to prevent, or None.

    YAML rejects a bare `: ` (colon-space) inside an unquoted value: it reads as a nested
    mapping and the document fails to parse. A quoted or block scalar is fine.
    """
    if ":" not in line:
        return None
    key, _, value = line.partition(":")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key.strip()):
        return None
    value = value.strip()
    if not value or value[0] in "\"'|>[{&*":
        return None
    if ": " in value:
        return f"unquoted plain scalar contains ': ' — {key.strip()}"
    return None


def parse_frontmatter(text):
    """Top-level key → value for the simple mapping shape these artifacts use.

    Returns (mapping, problems). A non-empty `problems` means Claude Code's own parser would
    reject the block, which is the condition that drops all metadata at runtime.
    """
    mapping, problems, pending = {}, [], None
    for raw in text.strip().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t", "-")):
            continue                                   # nested/continuation line
        problem = scalar_problem(raw)
        if problem:
            problems.append(problem)
        key, sep, value = raw.partition(":")
        if not sep:
            continue
        pending = key.strip()
        mapping[pending] = value.strip().strip("\"'")
    return mapping, problems


def registered(kind):
    return [REPO_ROOT / entry[2:] if entry.startswith("./") else REPO_ROOT / entry
            for entry in manifest().get(kind, [])]


class FrontmatterSyntax(unittest.TestCase):
    """The checker must actually catch the defect — asserted on fixtures, not on the corpus."""

    def test_the_defect_shape_is_caught(self):
        self.assertIsNotNone(scalar_problem(
            "description: Generate reports over the runs/ tree: all-time plus weekly"))
        self.assertIsNotNone(scalar_problem(
            "description: The 51 rules — the guide: quality is judged against it"))

    def test_valid_shapes_are_not_flagged(self):
        for line in ('description: "Generate reports over runs/ tree: all-time"',
                     "description: 'a: b'",
                     "description: a plain description with no colon space",
                     "name: runs-stats",
                     "model: sonnet"):
            with self.subTest(line=line):
                self.assertIsNone(scalar_problem(line))


class ShippedArtifactsLoad(unittest.TestCase):
    """Every registered artifact must load with its metadata intact."""

    def test_skills_and_agents_declare_name_and_description(self):
        for path in registered("skills") + registered("agents"):
            target = path / "SKILL.md" if path.is_dir() else path
            with self.subTest(artifact=target.relative_to(REPO_ROOT).as_posix()):
                text = frontmatter_of(target)
                self.assertIsNotNone(text, "no YAML frontmatter")
                fields, problems = parse_frontmatter(text)
                self.assertEqual(problems, [], "frontmatter would fail to parse — the skill "
                                               "loads with EMPTY metadata and never triggers")
                self.assertTrue(fields.get("name"), "empty name")
                self.assertTrue(fields.get("description"), "empty description")

    def test_commands_declare_a_description(self):
        """Commands take their name from the filename; only `description` is required."""
        for path in registered("commands"):
            with self.subTest(artifact=path.relative_to(REPO_ROOT).as_posix()):
                text = frontmatter_of(path)
                self.assertIsNotNone(text, "no YAML frontmatter")
                fields, problems = parse_frontmatter(text)
                self.assertEqual(problems, [], "frontmatter would fail to parse")
                self.assertTrue(fields.get("description"), "empty description")

    def test_every_registered_path_exists(self):
        """An install must not ship a manifest pointing at absent files."""
        for kind in ("commands", "agents", "skills"):
            for path in registered(kind):
                target = path / "SKILL.md" if kind == "skills" else path
                with self.subTest(entry=target.relative_to(REPO_ROOT).as_posix()):
                    self.assertTrue(target.exists(), "registered but missing on disk")

    def test_the_manifest_does_not_redeclare_the_standard_hooks_file(self):
        """`hooks/hooks.json` is auto-loaded; declaring it too fails the whole plugin load."""
        declared = manifest().get("hooks")
        if declared is None:
            return
        entries = [declared] if isinstance(declared, str) else list(declared)
        for entry in entries:
            self.assertNotIn("hooks/hooks.json", entry,
                             "the standard hooks file is loaded automatically — declaring it "
                             "produces 'Duplicate hooks file detected' and the plugin fails "
                             "to load on a clean install")


class ManifestIdentity(unittest.TestCase):
    """Each field the two manifests duplicate is pinned to its counterpart, one by one."""

    def setUp(self):
        self.plugin = manifest()
        self.entry = marketplace()["plugins"][0]
        self.market = marketplace()

    def test_entry_name_matches(self):
        self.assertEqual(self.entry["name"], self.plugin["name"])

    def test_entry_description_matches(self):
        self.assertEqual(self.entry["description"], self.plugin["description"])

    def test_entry_author_matches(self):
        self.assertEqual(self.entry["author"], self.plugin["author"])

    def test_entry_homepage_matches(self):
        self.assertEqual(self.entry["homepage"], self.plugin["homepage"])

    def test_entry_license_matches(self):
        self.assertEqual(self.entry["license"], self.plugin["license"])

    def test_entry_keywords_match(self):
        self.assertEqual(self.entry["keywords"], self.plugin["keywords"])

    def test_owner_url_is_the_repository_account(self):
        """owner.url names the ACCOUNT; the repository identity is homepage/repository."""
        account = self.plugin["homepage"].rsplit("/", 1)[0]
        self.assertEqual(self.market["owner"]["url"], account)

    def test_the_plugin_source_is_this_same_repository(self):
        """A separate github source resolves independently of the marketplace fetch, so an
        install can land different bytes than the marketplace it came from. `./` keeps both
        sides on one commit."""
        self.assertEqual(self.entry["source"], "./")

    def test_the_entry_declares_no_version(self):
        """plugin.json's version governs resolution; a second one would stale doctor's
        version-coherence row."""
        self.assertNotIn("version", self.entry)


class InstallDocs(unittest.TestCase):
    """Asserted on the Install SECTION alone — the migration table names these commands too."""

    def setUp(self):
        text = README.read_text(encoding="utf-8")
        match = re.search(r"^## Install\b(.*?)(?=^## )", text, re.S | re.M)
        self.assertIsNotNone(match, "README has no ## Install section")
        self.section = match.group(1)
        self.full = text

    def test_the_marketplace_commands_are_exact(self):
        self.assertIn("/plugin marketplace add xinquan568/vibe-suite", self.section)
        self.assertIn("/plugin install vibe-suite@vibe-suite", self.section)

    def test_the_from_clone_path_is_documented(self):
        self.assertIn("git clone", self.section)

    def test_the_isolated_profile_variable_is_documented(self):
        self.assertIn("CLAUDE_CONFIG_DIR", self.section)

    def test_install_then_init_then_doctor_in_that_order(self):
        """Installation populates the plugin cache; doctor reports not-initialised until
        init runs. The documented order has to reflect that."""
        install = self.section.find("/plugin install")
        init = self.section.find("/vibe-suite:init")
        doctor = self.section.find("/vibe-suite:doctor")
        for name, pos in (("install", install), ("init", init), ("doctor", doctor)):
            self.assertGreater(pos, -1, f"the Install section never mentions {name}")
        self.assertLess(install, init, "init must come after install")
        self.assertLess(init, doctor, "doctor is the verify step, after init")

    def test_the_readme_no_longer_claims_scaffold_status(self):
        self.assertNotIn("**Status:** scaffold", self.full)


if __name__ == "__main__":
    unittest.main()
