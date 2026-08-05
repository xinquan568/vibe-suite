#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""E7.3 (vibe-55): the doc set's counts-vs-disk acceptance.

Every count a document states is a claim this file holds true THREE ways — the README's prose
number, the manifest's registration list, and the files actually on disk must agree (A-4:
manifest-only comparison would be transitively right but the acceptance says disk). The
migration table's `new` side must resolve to a registered command or a user-invocable skill;
the old side is history no test can check, so it rests on review.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
CLAUDE = REPO_ROOT / "CLAUDE.md"
PRIVACY = REPO_ROOT / "PRIVACY.md"


def manifest():
    return json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())


class DocsExist(unittest.TestCase):
    def test_all_three_exist_and_are_substantial(self):
        for doc in (README, CLAUDE, PRIVACY):
            with self.subTest(doc=doc.name):
                self.assertTrue(doc.is_file(), f"{doc.name} missing")
                self.assertGreater(len(doc.read_text(encoding="utf-8")), 500)


class ReadmeCounts(unittest.TestCase):
    def counts_from_disk(self):
        m = manifest()
        commands_disk = [p for p in (REPO_ROOT / "commands").rglob("*.md")
                         if f"./{p.relative_to(REPO_ROOT).as_posix()}" in m["commands"]]
        agents_disk = [p for p in (REPO_ROOT / "agents").glob("*.md")
                       if f"./{p.relative_to(REPO_ROOT).as_posix()}" in m["agents"]]
        skills_disk = [d for d in (REPO_ROOT / "skills").iterdir()
                       if d.is_dir() and (d / "SKILL.md").is_file()
                       and f"./{d.relative_to(REPO_ROOT).as_posix()}" in m["skills"]]
        return len(commands_disk), len(agents_disk), len(skills_disk)

    def test_readme_counts_equal_manifest_and_disk(self):
        text = README.read_text(encoding="utf-8")
        m = manifest()
        stated = re.search(r"\*\*(\d+) commands, (\d+) agents, (\d+) skills\*\*", text)
        self.assertIsNotNone(stated, "README lacks the counts sentence")
        c, a, s = (int(stated.group(i)) for i in (1, 2, 3))
        self.assertEqual((c, a, s),
                         (len(m["commands"]), len(m["agents"]), len(m["skills"])),
                         "README counts != manifest")
        self.assertEqual((c, a, s), self.counts_from_disk(), "README counts != disk")

    def test_python_floor_is_stated(self):
        self.assertIn("Python 3.11+", README.read_text(encoding="utf-8"))

    def test_migration_table_targets_resolve(self):
        text = README.read_text(encoding="utf-8")
        m = manifest()
        commands = {Path(c).stem for c in m["commands"]}
        skills = {Path(s).name for s in m["skills"]}
        rows = re.findall(r"^\| `/(?:cc-suite|nlpm|grill):[a-z-]+`[^|]*\| ([^|]+) \|",
                          text, re.M)
        self.assertGreaterEqual(len(rows), 25, "migration table too small")
        for new in rows:
            new = new.strip()
            if "no successor" in new:
                continue
            m2 = re.search(r"/vibe-suite:([a-z-]+)|the `([a-z-]+)` skill", new)
            self.assertIsNotNone(m2, f"unparseable replacement cell: {new!r}")
            target = m2.group(1) or m2.group(2)
            self.assertIn(target, commands | skills,
                          f"migration target {target!r} is neither a registered command "
                          "nor a registered skill")


class ClaudeMdAnchors(unittest.TestCase):
    def test_battery_commands_resolve(self):
        text = CLAUDE.read_text(encoding="utf-8")
        for rel in ("tools/model-pin-lint.py", "bin/vibe-check",
                    "tools/legacy-string-sweep.sh"):
            self.assertIn(rel, text, f"CLAUDE.md does not name {rel}")
            self.assertTrue((REPO_ROOT / rel).exists(), f"{rel} named but absent")
        self.assertIn("codex-src", text)


class PrivacyAnchors(unittest.TestCase):
    def test_named_surfaces_exist(self):
        text = PRIVACY.read_text(encoding="utf-8")
        self.assertIn("claude-octopus", text)
        self.assertTrue((REPO_ROOT / "scripts" / "lib" /
                         "claude-octopus-pin.txt").is_file())
        for secret in ("CLAUDE_CODE_OAUTH_TOKEN", "PAT_TOKEN", "OPENAI_API_KEY"):
            self.assertIn(secret, text)
        self.assertNotIn("local-only", text.lower())
        self.assertIn("future", text.lower())


if __name__ == "__main__":
    unittest.main()
