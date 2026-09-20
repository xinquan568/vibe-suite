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

import importlib
import json
import os
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


def case(body, head="import unittest\n"):
    """One synthetic module: a head, then a class whose single test runs `body`."""
    lines = "".join("        " + line + "\n" for line in body.strip("\n").split("\n"))
    return head + "\n\nclass T(unittest.TestCase):\n    def test_a(self):\n" + lines


#: The rule's positive half (T16): forms that read text, patch objects and call pure code, and must stay contract.
PURE_FORMS = {
    "a prose read": case('t = Path(os.path.join("a", "b")).read_text()\nself.assertRegex(t, r"x")',
                         "import os\nimport unittest\nfrom pathlib import Path\n"),
    "patch.object": case('with mock.patch.object(Path, "read_text", return_value=""):\n    pass',
                         "import unittest\nfrom pathlib import Path\nfrom unittest import mock\n"),
    "patch.dict on os.environ": case('with mock.patch.dict(os.environ, {"A": "1"}):\n    pass',
                                     "import os\nimport unittest\nfrom unittest import mock\n"),
    "a stdlib literal patch": case('with mock.patch("os.getcwd", return_value="/"):\n    pass',
                                   "import unittest\nfrom unittest import mock\n"),
    "json and shlex": case('json.loads(shlex.split("1")[0])', "import json\nimport shlex\nimport unittest\n"),
    "a classmethod hook": ("import unittest\n\n\nclass T(unittest.TestCase):\n    @classmethod\n"
                           "    def setUpClass(cls):\n        cls.x = 1\n\n    def test_a(self):\n"
                           "        self.assertEqual(self.x, 1)\n"),
    "a call through a local variable": case("f = len\nf([1])"),
}

#: Every way to execute the rule must refuse (T17). 30 of the 37 classify contract under the denylist this replaces.
EXECUTION_FORMS = {
    "loadTestsFromName": case('unittest.defaultTestLoader.loadTestsFromName("tests.x")'),
    "loadTestsFromNames": case('unittest.defaultTestLoader.loadTestsFromNames(["tests.x"])'),
    "loadTestsFromModule": case("unittest.defaultTestLoader.loadTestsFromModule(mod)"),
    "a loader's discover": case('unittest.TestLoader().discover("tests")'),
    "importlib.reload": case("importlib.reload(mod)", "import importlib\nimport unittest\n"),
    "reload imported bare": case("reload(mod)", "import unittest\nfrom importlib import reload\n"),
    "reload aliased": case("r(mod)", "import unittest\nfrom importlib import reload as r\n"),
    "import_module imported bare": case('import_module("json")', "import unittest\nfrom importlib import import_module\n"),
    "import_module of a repository module": case('importlib.import_module("bridge")',
                                                 "import importlib\nimport unittest\n"),
    "import_module of a variable": case("importlib.import_module(name)", "import importlib\nimport unittest\n"),
    "__import__ of a repository module": case('__import__("bridge")'),
    "__import__ then run": case('__import__("subprocess").run(["true"])'),
    "__import__ of an f-string": case('__import__(f"x{y}")'),
    "a relative __import__": case('__import__("json", {"__package__": "p"}, level=1)'),
    "run_module imported bare": case('run_module("bridge")', "import unittest\nfrom runpy import run_module\n"),
    "run_path": case('runpy.run_path("scripts/x.py")', "import runpy\nimport unittest\n"),
    "eval": case('eval("1")'),
    "exec": case('exec("x = 1")'),
    "compile": case('compile("1", "f", "eval")'),
    "globals": case('globals()["x"]()'),
    "__builtins__": case('__builtins__["eval"]("1")'),
    "input": case("input()"),
    "breakpoint": case("breakpoint()"),
    "os.system": case('os.system("true")', "import os\nimport unittest\n"),
    "from os import system": case('system("true")', "import unittest\nfrom os import system\n"),
    "from os import system aliased": case('s("true")', "import unittest\nfrom os import system as s\n"),
    "import os.path then os.system": case('os.system("true")', "import os.path\nimport unittest\n"),
    "sys.modules": case('sys.modules["bridge"].get()', "import sys\nimport unittest\n"),
    "from sys import modules": case('modules["bridge"]', "import unittest\nfrom sys import modules\n"),
    "from unittest import defaultTestLoader": case('defaultTestLoader.loadTestsFromName("tests.x")',
                                                   "import unittest\nfrom unittest import defaultTestLoader\n"),
    "unittest.main": case("unittest.main()", "import unittest.mock\n"),
    "a bare module object": case("f(json)", "import json\nimport unittest\n"),
    "getattr with a computed name": case('getattr(os, "sys" + "tem")("true")', "import os\nimport unittest\n"),
    "vars of a module": case('vars(os)["system"]("true")', "import os\nimport unittest\n"),
    "run on a suite": case("suite.run(result)"),
    "an unknown value method": case('Path("x").frobnicate()', "import unittest\nfrom pathlib import Path\n"),
    "an unknown self method": case("self.run()"),
}

#: Every route the nine review rounds raised (T18). 15 classify contract under the denylist, named in the test.
REVIEWER_ROUTES = {
    "a same-module helper that runs": ("import subprocess\nimport unittest\n\n\ndef go():\n"
                                       "    subprocess.run(['true'])\n\n\nclass T(unittest.TestCase):\n"
                                       "    def test_a(self):\n        go()\n"),
    "a cycle judged second": ("import subprocess\nimport unittest\n\n\ndef a():\n    if False:\n        b()\n"
                              "    subprocess.run(['true'])\n\n\ndef b():\n    a()\n\n\n"
                              "class First(unittest.TestCase):\n    def test_a(self):\n        a()\n\n\n"
                              "class T(unittest.TestCase):\n    def test_a(self):\n        b()\n"),
    "a module reached through a pure one": case('shutil.os.system("true")', "import shutil\nimport unittest\n"),
    "reflection through __globals__": case('os.walk.__globals__["system"]("true")', "import os\nimport unittest\n"),
    "an import inside a method": case("from tests import tiers"),
    "patch by alias": case('with p("bridge.X", 1):\n    pass', "import unittest\nfrom unittest.mock import patch as p\n"),
    "patch by keyword": case('with patch(target="bridge.X", new=1):\n    pass',
                             "import unittest\nfrom unittest.mock import patch\n"),
    "patch.dict of a variable": case('target = "bridge.CONF"\nwith mock.patch.dict(target, {}):\n    pass',
                                     "import unittest\nfrom unittest import mock\n"),
    "patch of an f-string": case('with mock.patch(f"{m}.X", 1):\n    pass', "import unittest\nfrom unittest import mock\n"),
    "a value installed by mutation": ("import subprocess\nimport unittest\n\ncallbacks = []\n"
                                      "callbacks.append(subprocess.run)\n\n\nclass T(unittest.TestCase):\n"
                                      "    def test_a(self):\n        callbacks[0]([\"true\"])\n"),
    "a value bound by destructuring": ("import unittest\nfrom subprocess import run\n\ngo, = (run,)\n\n\n"
                                       "class T(unittest.TestCase):\n    def test_a(self):\n        go([\"true\"])\n"),
    "a mutation in an import-time branch": ("import subprocess\nimport unittest\n\ncallbacks = []\n"
                                            "if __name__ == \"__main__\":\n    pass\nelse:\n"
                                            "    callbacks.append(subprocess.run)\n\n\n"
                                            "class T(unittest.TestCase):\n    def test_a(self):\n"
                                            "        callbacks[0]([\"true\"])\n"),
    "a binding shadowed in another scope": ("import subprocess as runner\nimport unittest\n\n\n"
                                            "class T(unittest.TestCase):\n    def test_a(self):\n"
                                            "        runner.run([\"true\"])\n\n\ndef unrelated():\n"
                                            "    import json as runner  # noqa: F401\n"),
    "a native handle": case('native(b"true")', "import unittest\nfrom ctypes import CDLL as extract\n\n"
                                               "native = extract(None).system\n"),
    "a thread started at import": ("import unittest\nfrom threading import Thread\n\nfrom bridge import upsert\n\n"
                                   "worker = Thread(target=upsert)\nworker.start()\n\n\n"
                                   "class T(unittest.TestCase):\n    def test_a(self):\n        worker.join()\n"),
    "exec of repository source": case('run_source((Path("scripts") / "config.py").read_text(), {})',
                                      "import unittest\nfrom builtins import exec as run_source\n"
                                      "from pathlib import Path\n"),
    "a relative run_path": case('loaded = run_path("scripts/bridge.py")', "import unittest\nfrom runpy import run_path\n"),
    "os.fork with no audit arguments": case("fork()", "import unittest\nfrom os import fork\n"),
    "a generator from repository code": case("next(values)", "import runpy\nimport unittest\n\n"
                                                             "values = runpy.run_path('tools/x.py')['gen']()\n"),
    "a directory change around a call": case('os.chdir("/tmp")\nupsert()', "import os\nimport unittest\n"
                                                                          "from bridge import upsert\n"),
    "a fresh namespace for repository code": case("run_source(code, {})",
                                                  "import unittest\nfrom builtins import exec as run_source\n\n"
                                                  "code = compile('', 'scripts/config.py', 'exec')\n"),
    "a profile callback": case("sys.setprofile(hook)", "import sys\nimport unittest\n"),
    "a trace callback": case("sys.settrace(hook)", "import sys\nimport unittest\n"),
    "an audit hook": case('sys.addaudithook(hook)\nsys.audit("x")', "import sys\nimport unittest\n"),
    "a second monitoring tool": case('sys.monitoring.use_tool_id(4, "observer")', "import sys\nimport unittest\n"),
    "profiling repository code": case("cProfile.Profile().runcall(upsert)",
                                      "import cProfile\nimport unittest\nfrom bridge import upsert\n"),
    "a wildcard import of a repository module": ("import unittest\nfrom shared_fixture import *  # noqa: F401,F403\n\n\n"
                                                 "class T(unittest.TestCase):\n    def test_a(self):\n"
                                                 "        self.assertTrue(True)\n"),
    "a wildcard import of os": ("import unittest\nfrom os import *  # noqa: F401,F403\n\n\n"
                                "class T(unittest.TestCase):\n    def test_a(self):\n"
                                "        self.assertEqual(system(\"true\"), 0)  # noqa: F405\n"),
    "a module fixture that runs": ("import subprocess\nimport unittest\n\n\ndef setUpModule():\n"
                                   "    subprocess.run([\"true\"])\n\n\nclass T(unittest.TestCase):\n"
                                   "    def test_a(self):\n        self.assertTrue(True)\n"),
    "an imported module fixture": ("import unittest\nfrom shared_fixture import setUpModule  # noqa: F401\n\n\n"
                                   "class T(unittest.TestCase):\n    def test_a(self):\n"
                                   "        self.assertTrue(True)\n"),
    "an imported teardown fixture": ("import unittest\nfrom shared_fixture import tearDownModule  # noqa: F401\n\n\n"
                                     "class T(unittest.TestCase):\n    def test_a(self):\n"
                                     "        self.assertTrue(True)\n"),
    "a process in setUpClass": ("import subprocess\nimport unittest\n\n\nclass T(unittest.TestCase):\n"
                                "    @classmethod\n    def setUpClass(cls):\n        subprocess.run([\"true\"])\n\n"
                                "    def test_a(self):\n        self.assertTrue(True)\n"),
    "a process in tearDownClass": ("import subprocess\nimport unittest\n\n\nclass T(unittest.TestCase):\n"
                                   "    @classmethod\n    def tearDownClass(cls):\n        subprocess.run([\"true\"])\n\n"
                                   "    def test_a(self):\n        self.assertTrue(True)\n"),
    "a swallowed refusal": case('try:\n    subprocess.run(["true"])\nexcept Exception:\n    pass',
                                "import subprocess\nimport unittest\n"),
    "an override forcing behaviour": ("import unittest\n\n\nclass T(unittest.TestCase):\n    tier = \"behaviour\"\n\n"
                                      "    def test_a(self):\n        self.assertTrue(True)\n"),
    "an override trying to force contract": ("import subprocess\nimport unittest\n\n\nclass T(unittest.TestCase):\n"
                                             "    tier = \"contract\"\n\n    def test_a(self):\n"
                                             "        subprocess.run([\"true\"])\n"),
}


class TestTheAllowlist(unittest.TestCase):
    """T16-T21 - the rule, over synthetic sources."""

    @classmethod
    def setUpClass(cls):
        cls.tiers = load_tiers()

    def tier(self, source):
        return self.tiers.classify_source(textwrap.dedent(source))["T"]

    def test_the_pure_forms_stay_contract(self):
        """T16 - the rule's positive half: these are green at the denylist too, and M15 keeps them live."""
        for name, source in PURE_FORMS.items():
            with self.subTest(form=name):
                self.assertEqual(self.tiers.classify_source(source)["T"], "contract")

    def test_every_execution_form_is_behaviour(self):
        """T17 - every way to execute. 30 of the 37 are contract under the classifier this replaces."""
        for name, source in EXECUTION_FORMS.items():
            with self.subTest(form=name):
                self.assertEqual(self.tiers.classify_source(source)["T"], "behaviour")

    def test_the_reviewers_counter_examples_are_behaviour(self):
        """T18 - every route the nine review rounds raised, each judged on the class named T."""
        for name, source in REVIEWER_ROUTES.items():
            with self.subTest(route=name):
                self.assertEqual(self.tiers.classify_source(source)["T"], "behaviour")

    def test_a_helper_is_trusted_only_from_its_own_module(self):
        """T19 - provenance: a foreign callable under a helper's name is judged by its own module."""
        self.assertEqual(self.tier("""
            import unittest
            from tmpdirs import TempDirMixin
            class T(TempDirMixin, unittest.TestCase):
                def test_a(self):
                    self.assertTrue(self.mkdtemp())
        """), "contract")
        self.assertEqual(self.tier("""
            import unittest
            from tests.test_auditor_state_machine import extract
            class T(unittest.TestCase):
                def test_a(self):
                    self.assertTrue(extract("p", "m", "n"))
        """), "contract")
        self.assertEqual(self.tier("""
            import unittest
            from ctypes import CDLL as extract
            class T(unittest.TestCase):
                def test_a(self):
                    extract(None)
        """), "behaviour")
        self.assertEqual(self.tier("""
            import unittest
            from shared_fixture import scratch_dir
            class T(unittest.TestCase):
                def test_a(self):
                    scratch_dir()
        """), "behaviour", "a helper's name is trusted only from the module that defines it")

    def test_the_override_only_forces_behaviour(self):
        """T20 - replaces round 1's two-way override test: an allowlist cannot be opted out of toward contract."""
        self.assertEqual(self.tier("""
            import unittest
            class T(unittest.TestCase):
                tier = "behaviour"
                def test_a(self):
                    self.assertTrue(True)
        """), "behaviour")
        self.assertEqual(self.tier("""
            import subprocess, unittest
            class T(unittest.TestCase):
                tier = "contract"
                def test_a(self):
                    subprocess.run(["true"])
        """), "behaviour")

    def test_a_cycle_is_judged_the_same_either_way(self):
        """T21 - the verdicts propagate to a fixed point, so declaration order cannot decide them."""
        module = textwrap.dedent("""
            import subprocess, unittest
            def a():
                if False:
                    b()
                subprocess.run(["true"])
            def b():
                a()
        """)
        first = textwrap.dedent("""
            class First(unittest.TestCase):
                def test_a(self):
                    a()
        """)
        second = textwrap.dedent("""
            class Cycle(unittest.TestCase):
                def test_a(self):
                    b()
        """)
        for order, source in (("first then cycle", module + first + second), ("cycle then first", module + second + first)):
            with self.subTest(order=order):
                verdicts = self.tiers.classify_source(source)
                self.assertEqual(verdicts["First"], "behaviour")
                self.assertEqual(verdicts["Cycle"], "behaviour")

    def test_the_classes_that_execute_are_behaviour(self):
        """T22 - the four real classes the rule moves, each for a reason the listing can show."""
        moved = {
            "tests.test_migration_fixtures.Row09AuditorData": "loads another test module by name",
            "tests.test_tmpdirs.TempDirMixinCleansUp": "runs a nested test case",
            "tests.test_unbridge.StampHasOneDefinitionOnTheReaderSide": "its module fixture imports a repository module",
            "tests.test_update.Manifest": "its module fixture imports a repository module",
        }
        tiers = {entry["id"]: entry["tier"] for entry in self.tiers.listing(REPO_ROOT)}
        for name, why in moved.items():
            with self.subTest(cls=name, why=why):
                self.assertEqual(tiers.get(name), "behaviour")


class FakeMonitor:
    """The sys.monitoring surface the guard uses, without touching the interpreter (D15)."""

    PROFILER_ID = 2
    DISABLE = object()

    class events:
        PY_START = 1
        PY_RESUME = 2
        PY_THROW = 4

    def __init__(self):
        self.tools = {}
        self.callbacks = {}
        self.events_set = {}

    def get_tool(self, tool):
        return self.tools.get(tool)

    def use_tool_id(self, tool, name):
        self.tools[tool] = name

    def free_tool_id(self, tool):
        self.tools.pop(tool, None)

    def register_callback(self, tool, event, callback):
        self.callbacks[(tool, event)] = callback

    def set_events(self, tool, mask):
        self.events_set[tool] = mask

    def get_events(self, tool):
        return self.events_set.get(tool, 0)


class TestGuardUnit(TempDirMixin, unittest.TestCase):
    """T23, T26, T27 at unit level - nothing process-global is installed (D15)."""

    def setUp(self):
        super().setUp()
        self.tiers = load_tiers()
        self.root = Path(self.mkdtemp())
        (self.root / "tests").mkdir()
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "mod.py").write_text("def work():\n    return 1\n", encoding="utf-8")

    def guard(self, monitor=None):
        guard = self.tiers.Guard(self.root, monitor=monitor or FakeMonitor())
        self.addCleanup(guard.stop)          # the hook stays installed for this process; stopping makes it inert
        guard.start("t")
        return guard

    def test_a_process_start_is_recorded_and_refused(self):
        """T23 - recorded before it is refused, so a test that swallows the refusal still fails the command."""
        guard = self.guard()
        with self.assertRaises(PermissionError):
            guard.observe("subprocess.Popen", (["true"],))
        self.assertEqual([v[1] for v in guard.violations], ["subprocess.Popen"])

    def test_a_process_event_without_arguments_is_recorded(self):
        """T23 - os.fork and os.forkpty raise their audit event with an empty argument tuple."""
        guard = self.guard()
        with self.assertRaises(PermissionError):
            guard.observe("os.fork", ())
        self.assertEqual([v[1] for v in guard.violations], ["os.fork"])

    def test_instrumentation_during_the_run_is_a_violation(self):
        """T26 - a profiler, a tracer, an audit hook or another monitoring tool suspends the guard's view."""
        for event in ("sys.setprofile", "sys.settrace", "sys.addaudithook", "sys.monitoring.register_callback"):
            with self.subTest(event=event):
                guard = self.guard()
                guard.observe(event, ())
                self.assertEqual([v[1] for v in guard.violations], ["instrumentation"])

    def test_instrumentation_installed_before_the_run_is_reported_when_it_starts(self):
        """T26 - held while inactive, reported at the boundary, so the guard never runs with a suspended view."""
        guard = self.tiers.Guard(self.root, monitor=FakeMonitor())
        self.addCleanup(guard.stop)
        guard.observe("sys.settrace", ())
        self.assertEqual(guard.violations, [])
        guard.start("t")
        self.assertEqual([v[1] for v in guard.violations], ["instrumentation"])

    def test_another_monitoring_tool_is_a_violation(self):
        """T26 - a tool registered while the guard was inactive is found by the boundary scan."""
        monitor = FakeMonitor()
        guard = self.tiers.Guard(self.root, monitor=monitor)
        self.addCleanup(guard.stop)
        monitor.use_tool_id(4, "observer")
        guard.start("t")
        self.assertIn("instrumentation", [v[1] for v in guard.violations])

    def test_a_displaced_tool_is_a_violation(self):
        """T26 - the guard owns its tool id for the whole run."""
        monitor = FakeMonitor()
        guard = self.tiers.Guard(self.root, monitor=monitor)
        self.addCleanup(guard.stop)
        monitor.tools[monitor.PROFILER_ID] = "someone-else"
        guard.start("t")
        self.assertIn("guard displaced", [v[1] for v in guard.violations])

    def test_call_monitoring_is_a_capability(self):
        """T27 - without sys.monitoring the guard still refuses processes and records loads, and says so."""
        guard = self.tiers.Guard(self.root, monitor=None)
        self.addCleanup(guard.stop)
        self.assertFalse(guard.available)
        guard.start("t")
        with self.assertRaises(PermissionError):
            guard.observe("os.system", (b"true",))
        self.assertEqual([v[1] for v in guard.violations], ["os.system"])


class TestGuardInAProcess(TempDirMixin, unittest.TestCase):
    """T23-T27, T29 - real instrumentation and real execution, each in a fresh process (D15)."""

    #: `tmpdirs.scratch_dir` is a helper the rule trusts by provenance, so a class calling it classifies contract
    #: however the helper is written. The tree puts its own `tmpdirs.py` at the root and the command runs with the
    #: tree as the interpreter's directory, so this checkout's `tests/tmpdirs.py` is not on the child's path.
    BOOTSTRAP = "import runpy, sys; sys.argv = ['tiers.py'] + sys.argv[1:]; runpy.run_path({tiers!r}, run_name='__main__')"

    def tree(self, body, test_body, extra=""):
        root = Path(self.mkdtemp())
        (root / "tests").mkdir()
        (root / "scripts").mkdir()
        (root / "scripts" / "mod.py").write_text(
            "def work():\n    return 'done'\n\n\ndef gen():\n    yield 1\n    yield 2\n", encoding="utf-8")
        (root / "tmpdirs.py").write_text(textwrap.dedent(body), encoding="utf-8")
        (root / "tests" / "test_fixture.py").write_text(textwrap.dedent(test_body) + extra, encoding="utf-8")
        return root

    def run_in_tree(self, root, *args, python=None):
        env = dict(os.environ)
        for name in ("COVERAGE_PROCESS_START", "PYTHONSTARTUP", "PYTHONPROFILEIMPORTTIME", "PYTHONPATH"):
            env.pop(name, None)
        return subprocess.run([python or sys.executable, "-B", "-c", self.BOOTSTRAP.format(tiers=str(TIERS)),
                               *args, "--root", str(root)],
                              cwd=str(root), capture_output=True, text=True, timeout=180, env=env)

    def run_guarded(self, root, *args, python=None):
        return self.run_in_tree(root, "contract", *args, python=python)

    def test_a_misclassified_contract_test_fails_the_command(self):
        """T29 - the guard's whole point: the class is contract by the rule, and executes. Kills M27."""
        root = self.tree(
            "import subprocess\n\n\ndef scratch_dir():\n    subprocess.run(['true'])\n    return 'x'\n",
            """
            import unittest
            from tmpdirs import scratch_dir
            class Looks(unittest.TestCase):
                def test_a(self):
                    try:
                        scratch_dir()
                    except Exception:
                        pass
                    self.assertTrue(True)
            """)
        listing = self.run_in_tree(root, "list")
        self.assertIn("contract   tests.test_fixture.Looks", listing.stdout, listing.stdout + listing.stderr)
        result = self.run_guarded(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("subprocess.Popen", result.stdout)
        self.assertIn("test_a", result.stdout)

    def test_a_repository_load_is_recorded(self):
        """T24(a) - importing a repository module during a contract test. Runs on every version."""
        root = self.tree(
            "import importlib, sys\n\n\ndef scratch_dir():\n    sys.path.insert(0, str(__import__('pathlib')"
            ".Path(__file__).resolve().parent / 'scripts'))\n    return importlib.import_module('mod')\n",
            """
            import unittest
            from tmpdirs import scratch_dir
            class Looks(unittest.TestCase):
                def test_a(self):
                    scratch_dir()
            """)
        result = self.run_guarded(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("load", result.stdout)

    def test_a_process_start_is_refused_in_every_fixture_span(self):
        """T25 - setUpClass, tearDownClass, addCleanup, setUpModule, tearDownModule and the outer spans."""
        prologue = ("import unittest\nfrom tmpdirs import scratch_dir\n\n\ndef _run():\n    scratch_dir()\n\n\n")
        plain = "class Looks(unittest.TestCase):\n    def test_a(self):\n        self.assertTrue(True)\n"
        for span, module in (
            ("setUpModule", prologue + "def setUpModule():\n    _run()\n\n\n" + plain),
            ("tearDownModule", prologue + "def tearDownModule():\n    _run()\n\n\n" + plain),
            ("setUpClass", prologue + "class Looks(unittest.TestCase):\n    @classmethod\n"
                           "    def setUpClass(cls):\n        _run()\n\n    def test_a(self):\n"
                           "        self.assertTrue(True)\n"),
            ("tearDownClass", prologue + "class Looks(unittest.TestCase):\n    @classmethod\n"
                              "    def tearDownClass(cls):\n        _run()\n\n    def test_a(self):\n"
                              "        self.assertTrue(True)\n"),
            ("addCleanup", prologue + "class Looks(unittest.TestCase):\n    def test_a(self):\n"
                           "        self.addCleanup(_run)\n        self.assertTrue(True)\n"),
        ):
            with self.subTest(span=span):
                root = self.tree(
                    "import subprocess\n\n\ndef scratch_dir():\n    return subprocess.run(['true'])\n", module)
                result = self.run_guarded(root)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("subprocess.Popen", result.stdout)

    def test_real_instrumentation_fails_closed(self):
        """T26 - installed for real, in a fresh process, so no hook leaks into this one."""
        for name, body in (
            ("profile", "import sys\n\n\ndef scratch_dir():\n    sys.setprofile(lambda *a: None)\n"
                        "    sys.setprofile(None)\n    return 1\n"),
            ("trace", "import sys\n\n\ndef scratch_dir():\n    sys.settrace(lambda *a: None)\n"
                      "    sys.settrace(None)\n    return 1\n"),
            ("audit hook", "import sys\n\n\ndef scratch_dir():\n    sys.addaudithook(lambda e, a: None)\n    return 1\n"),
        ):
            with self.subTest(instrumentation=name):
                root = self.tree(body, """
                    import unittest
                    from tmpdirs import scratch_dir
                    class Looks(unittest.TestCase):
                        def test_a(self):
                            scratch_dir()
                """)
                result = self.run_guarded(root)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("instrumentation", result.stdout)

    @unittest.skipUnless(getattr(sys, "monitoring", None), "call monitoring needs sys.monitoring (3.12+)")
    def test_a_call_into_repository_code_is_recorded(self):
        """T24(b) - the call the audit hook cannot see: the module is already loaded."""
        root = self.tree(
            "import importlib, sys\nfrom pathlib import Path\n\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parent / 'scripts'))\n"
            "mod = importlib.import_module('mod')\n\n\ndef scratch_dir():\n    return mod.work()\n",
            """
            import unittest
            from tmpdirs import scratch_dir
            class Looks(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(scratch_dir(), 'done')
            """)
        result = self.run_guarded(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("call", result.stdout)

    @unittest.skipUnless(getattr(sys, "monitoring", None), "call monitoring needs sys.monitoring (3.12+)")
    def test_a_call_after_a_directory_change_is_recorded(self):
        """T24(b) - the origin is fixed when the code is loaded, so chdir cannot move it."""
        root = self.tree(
            "import importlib, os, sys\nfrom pathlib import Path\n\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parent / 'scripts'))\n"
            "mod = importlib.import_module('mod')\n\n\ndef scratch_dir():\n    os.chdir('/tmp')\n"
            "    return mod.work()\n",
            """
            import unittest
            from tmpdirs import scratch_dir
            class Looks(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(scratch_dir(), 'done')
            """)
        result = self.run_guarded(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("call", result.stdout)

    def test_re_executing_relative_code_after_a_directory_change_is_recorded(self):
        """T24(b) - the origin is fixed at a code object's FIRST load; a later chdir must not move it."""
        root = self.tree(
            "import os\n\n"
            "SOURCE = open(os.path.join('scripts', 'mod.py')).read()\n"
            "CODE = compile(SOURCE, os.path.join('scripts', 'mod.py'), 'exec')   # a relative filename\n"
            "exec(CODE, {})                                                      # first load, from the tree\n\n\n"
            "def scratch_dir():\n    os.chdir('/tmp')\n    namespace = {}\n    exec(CODE, namespace)\n"
            "    return namespace['work']()\n",
            """
            import unittest
            from tmpdirs import scratch_dir
            class Looks(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(scratch_dir(), 'done')
            """)
        result = self.run_guarded(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("load", result.stdout)

    @unittest.skipUnless(getattr(sys, "monitoring", None), "call monitoring needs sys.monitoring (3.12+)")
    def test_a_throw_into_foreign_code_keeps_the_guard_watching(self):
        """T24(d) - PY_THROW cannot be disabled: 3.14 drops the callback if a callback returns DISABLE, and every
        later call into repository code would go unrecorded."""
        root = self.tree(
            "import importlib, sys\nfrom pathlib import Path\n\n"
            "HERE = Path(__file__).resolve().parent\n"
            "sys.path.insert(0, str(HERE / 'scripts'))\nsys.path.insert(0, str(HERE / 'tests'))\n"
            "mod = importlib.import_module('mod')\nforeign = importlib.import_module('foreign_gen')\n\n\n"
            "def scratch_dir():\n    watched = mod.gen()                # repository code, never resumed\n"
            "    values = foreign.gen()\n    next(values)\n"
            "    try:\n        values.throw(ValueError('x'))   # a throw into code the guard does not watch\n"
            "    except Exception:\n        pass\n"
            "    try:\n        watched.throw(ValueError('x'))  # ... must not stop this one being recorded\n"
            "    except Exception:\n        pass\n    return 'done'\n",
            """
            import unittest
            from tmpdirs import scratch_dir
            class Looks(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(scratch_dir(), 'done')
            """)
        (root / "tests" / "foreign_gen.py").write_text("def gen():\n    yield 1\n    yield 2\n", encoding="utf-8")
        result = self.run_guarded(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        # The repository generator is only ever entered by the throw, so its frame appears exactly when the throw
        # callback survived. A callback that answered DISABLE would have been removed by the first throw.
        self.assertIn("mod.py:gen", result.stdout, result.stdout)

    @unittest.skipUnless(getattr(sys, "monitoring", None), "call monitoring needs sys.monitoring (3.12+)")
    def test_a_resumed_or_thrown_generator_is_recorded(self):
        """T24(d) - PY_RESUME and PY_THROW, the events a started generator arrives through."""
        for name, drive in (("resumed", "return next(values)"),
                            ("thrown", "return values.throw(ValueError('x'))")):
            with self.subTest(generator=name):
                root = self.tree(
                    "import importlib, sys\nfrom pathlib import Path\n\n"
                    "sys.path.insert(0, str(Path(__file__).resolve().parent / 'scripts'))\n"
                    "values = importlib.import_module('mod').gen()\nnext(values)\n\n\n"
                    "def scratch_dir():\n    " + drive + "\n",
                    """
                    import unittest
                    from tmpdirs import scratch_dir
                    class Looks(unittest.TestCase):
                        def test_a(self):
                            try:
                                scratch_dir()
                            except Exception:
                                pass
                    """)
                result = self.run_guarded(root)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("call", result.stdout)

    def test_the_guard_is_built_before_the_modules_load(self):
        """T24(e) - M25's killer: the ordering itself, asserted through the guard_factory seam."""
        tiers = load_tiers()
        path_before = list(sys.path)
        modules_before = set(sys.modules)

        def restore():
            sys.path[:] = path_before
            for name in set(sys.modules) - modules_before:
                sys.modules.pop(name, None)
            importlib.invalidate_caches()

        self.addCleanup(restore)
        root = Path(self.mkdtemp())
        (root / "tests").mkdir()
        (root / "tests" / "test_guard_ordering_fixture.py").write_text(textwrap.dedent("""
            import unittest
            class Prose(unittest.TestCase):
                def test_a(self):
                    self.assertIn("a", "abc")
        """), encoding="utf-8")
        seen = {}

        def factory(root_arg, monitor=None):
            seen["modules"] = [name for name in sys.modules if "test_guard_ordering_fixture" in name]
            return tiers.Guard(root_arg, monitor=monitor)

        exit_code = tiers.main(["contract", "--root", str(root)], guard_factory=factory)
        self.assertEqual(seen["modules"], [], "the guard was built after the tier's modules were loaded")
        self.assertIn("test_guard_ordering_fixture", ",".join(sys.modules), "the fixture module never loaded")
        self.assertEqual(exit_code, 0)


class TestTheGuardedCommand(unittest.TestCase):
    """T28 - the carrier: CI runs this module, so CI runs the guarded contract tier."""

    def test_the_guarded_contract_command_passes(self):
        env = dict(os.environ)
        for name in ("COVERAGE_PROCESS_START", "PYTHONSTARTUP"):
            env.pop(name, None)
        result = subprocess.run([sys.executable, "-B", str(TIERS), "contract"],
                                cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=900, env=env)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])
        self.assertNotIn("guard violation", result.stdout)
