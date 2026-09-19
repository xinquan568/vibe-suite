#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The two test tiers and the inner-loop command (vibe-226 / grill M30).

`tests/tiers.py` splits the suite into a **contract** tier — test classes that execute nothing (they read markdown,
JSON or source text and assert on it) — and a **behaviour** tier — everything that runs a process or calls repository
code. The tier is computed from the test source, not hand-tagged, so it cannot drift from what a class does.

What these tests hold:
- the module set is CI's (every top-level `tests/test_*.py`, the set `test_ci_shards` pins against `ci.yml`), so the inner
  loop can never run something CI does not, nor lose something CI runs;
- the two tiers partition every test those modules yield;
- the classifier marks a class behaviour for every way it can execute — directly, through module helpers, through a base,
  through a repository import — and contract only when it reaches none; an explicit `tier` attribute overrides it;
- the command runs exactly the tier asked for and reports failure faithfully.
"""

import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tmpdirs import TempDirMixin  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TIERS = REPO_ROOT / "tests" / "tiers.py"


def load_tiers():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vibe_tiers", TIERS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPartition(unittest.TestCase):
    """T1, T1b — over the real suite."""

    @classmethod
    def setUpClass(cls):
        cls.tiers = load_tiers()

    def test_the_module_set_is_cis(self):
        """CI runs every top-level tests/test_*.py (`find tests -maxdepth 1`); the tiers load exactly that set."""
        expected = sorted(p.stem for p in (REPO_ROOT / "tests").glob("test_*.py"))
        self.assertEqual(self.tiers.modules(REPO_ROOT), expected)

    def test_the_tiers_partition_discovery_exactly(self):
        listing = self.tiers.listing(REPO_ROOT)
        ids = [entry["id"] for entry in listing]
        self.assertEqual(len(ids), len(set(ids)), "a class appears twice")
        self.assertTrue(all(entry["tier"] in ("contract", "behaviour") for entry in listing))
        contract = self.tiers.test_ids(REPO_ROOT, "contract")
        behaviour = self.tiers.test_ids(REPO_ROOT, "behaviour")
        everything = self.tiers.test_ids(REPO_ROOT, "all")
        self.assertFalse(contract & behaviour, "a test is in both tiers")
        self.assertEqual(contract | behaviour, everything, "a test is in neither tier")
        self.assertTrue(contract and behaviour, "both tiers are non-empty")


class TestClassifier(unittest.TestCase):
    """T2, T3, T4 — synthetic modules, one per way a class can execute."""

    @classmethod
    def setUpClass(cls):
        cls.tiers = load_tiers()

    def tier(self, source, cls="T"):
        return self.tiers.classify_source(textwrap.dedent(source))[cls]

    def test_executors_make_a_class_behaviour(self):
        cases = {
            "direct subprocess": """
                import subprocess, unittest
                class T(unittest.TestCase):
                    def test_a(self):
                        subprocess.run(["true"])
            """,
            "attribute form": """
                import os, unittest
                class T(unittest.TestCase):
                    def test_a(self):
                        os.system("true")
            """,
            "through a helper two calls deep": """
                import subprocess, unittest
                def inner():
                    return subprocess.run(["true"])
                def outer():
                    return inner()
                class T(unittest.TestCase):
                    def test_a(self):
                        outer()
            """,
            "through a same-module base": """
                import runpy, unittest
                class Base(unittest.TestCase):
                    def helper(self):
                        runpy.run_path("x.py")
                class T(Base):
                    def test_a(self):
                        self.helper()
            """,
            "through a module-level variable": """
                import importlib.util, unittest
                spec = importlib.util.spec_from_file_location("m", "m.py")
                loaded = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(loaded)
                class T(unittest.TestCase):
                    def test_a(self):
                        loaded.go()
            """,
            "a repository import": """
                import unittest
                import bridge
                class T(unittest.TestCase):
                    def test_a(self):
                        bridge.json_server_has({}, "x")
            """,
            "an executing helper from another test module": """
                import unittest
                from tests.test_auditor_state_machine import Sandbox
                class T(unittest.TestCase):
                    def test_a(self):
                        Sandbox()
            """,
        }
        for label, source in cases.items():
            with self.subTest(case=label):
                self.assertEqual(self.tier(source), "behaviour")

    def test_a_prose_class_is_contract(self):
        source = """
            import json, re, unittest
            from pathlib import Path
            from tmpdirs import TempDirMixin
            from tests.test_skill_library import parse_frontmatter
            DOC = Path("README.md")
            def read(p):
                return p.read_text(encoding="utf-8")
            class T(TempDirMixin, unittest.TestCase):
                def test_a(self):
                    self.assertRegex(read(DOC), r"x")
                    json.loads("{}")
                    parse_frontmatter("---\\n---\\n")
        """
        self.assertEqual(self.tier(source), "contract")

    def test_an_override_wins_both_ways(self):
        executing = """
            import subprocess, unittest
            class T(unittest.TestCase):
                tier = "contract"
                def test_a(self):
                    subprocess.run(["true"])
        """
        prose = """
            import unittest
            class T(unittest.TestCase):
                tier = "behaviour"
                def test_a(self):
                    self.assertTrue(True)
        """
        self.assertEqual(self.tier(executing), "contract")
        self.assertEqual(self.tier(prose), "behaviour")


class TestCommand(TempDirMixin, unittest.TestCase):
    """T5, T6 — the command, run as a program against a throwaway root."""

    MODULE = textwrap.dedent('''
        import subprocess, sys, unittest
        class Prose(unittest.TestCase):
            def test_reads(self):
                self.assertTrue(True)
        class Runs(unittest.TestCase):
            def test_spawns(self):
                self.assertEqual(subprocess.run([sys.executable, "-c", "pass"]).returncode, 0)
    ''')

    def root(self, extra=""):
        root = Path(self.mkdtemp())
        (root / "tests").mkdir()
        (root / "tests" / "test_fixture.py").write_text(self.MODULE + extra, encoding="utf-8")
        return root

    def run_tiers(self, root, *args):
        return subprocess.run([sys.executable, str(TIERS), "--root", str(root), *args],
                              capture_output=True, text=True, timeout=120)

    def test_behaviour_runs_only_behaviour(self):
        result = self.run_tiers(self.root(), "behaviour", "-v")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("test_spawns", result.stderr)
        self.assertNotIn("test_reads", result.stderr)
        self.assertRegex(result.stderr, r"Ran 1 test\b")
        contract = self.run_tiers(self.root(), "contract", "-v")
        self.assertEqual(contract.returncode, 0, contract.stderr)
        self.assertIn("test_reads", contract.stderr)
        self.assertNotIn("test_spawns", contract.stderr)

    def test_a_failing_test_in_the_tier_fails_the_command(self):
        failing = textwrap.dedent('''
            class Broken(unittest.TestCase):
                def test_fails(self):
                    subprocess.run([sys.executable, "-c", "pass"])
                    self.fail("deliberate")
        ''')
        result = self.run_tiers(self.root(failing), "behaviour")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.run_tiers(self.root(failing), "contract").returncode, 0)

    def test_list_json_is_the_partition(self):
        result = self.run_tiers(self.root(), "list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        listing = json.loads(result.stdout)
        self.assertEqual({(e["id"], e["tier"]) for e in listing},
                         {("tests.test_fixture.Prose", "contract"), ("tests.test_fixture.Runs", "behaviour")})


if __name__ == "__main__":
    unittest.main()
