#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The bridge/fsafe split as a STRUCTURE, not a snapshot (M9 / vibe-223).

`scripts/lib/fsafe.py` is the filesystem-safety kernel of the Python half; `scripts/lib/bridge.py` keeps the codecs,
sentinels, provenance, anchored writes and the shell CLI, and imports the kernel. The moved code is covered by every
existing suite; what no existing test states is the split's shape — a leaf kernel, one home for every kernel name,
one refusal class, one root pin, and a lint that now sees `bridge.py`. These tests state it.
"""

import ast
import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB = REPO_ROOT / "scripts" / "lib"
sys.path.insert(0, str(LIB))
import fsafe  # noqa: E402
import bridge  # noqa: E402
import advisors  # noqa: E402

KERNEL = ("assert_root", "assert_inside", "classify", "pin_root", "_open_dir_chain", "open_dir_chain", "unlink_at", "remove_tree_at",
          "ensure_dir_at", "_remove_tree_fd", "rename_at", "symlink_at", "publish_new", "_scratch", "_fsync_dir", "secure_dir", "lstat_at",
          "write_atomic", "O_NOFOLLOW_FLAG", "_ROOT_PIN", "BridgeError", "AbsentPath")
MOVED_CALLABLES = tuple(n for n in KERNEL if n not in ("O_NOFOLLOW_FLAG", "_ROOT_PIN"))


def _non_stdlib_imports(source):
    """Every import in `source` that is NOT the standard library — a repository module or package (`bridge`, `tests`,
    `runs_stats`), a third-party distribution, or a relative import. `sys.stdlib_module_names` (3.10+) is the authority,
    so the check does not depend on what happens to sit beside the kernel. A leaf passes with `[]`."""
    tree = ast.parse(source); found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.split(".")[0] not in sys.stdlib_module_names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                found.append("." * node.level + (node.module or ""))
            elif node.module.split(".")[0] not in sys.stdlib_module_names:
                found.append(node.module)
    return sorted(found)


class TestTheKernelIsALeaf(unittest.TestCase):
    def test_fsafe_imports_only_the_standard_library_and_never_bootstraps(self):        # (a)
        source = (LIB / "fsafe.py").read_text(encoding="utf-8")
        self.assertEqual(_non_stdlib_imports(source), [], "fsafe.py must import nothing outside the standard library")
        self.assertNotIn("runpy", [n.names[0].name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Import)],
                         "a leaf library never bootstraps")
        self.assertNotIn("_bootstrap", source)

    def test_the_leaf_check_rejects_repository_third_party_and_relative_imports(self):   # (a) — both directions
        self.assertEqual(_non_stdlib_imports("import binascii\nimport os\nfrom pathlib import Path\nimport os.path\n"), [])
        self.assertEqual(_non_stdlib_imports("import bridge\n"), ["bridge"])
        self.assertEqual(_non_stdlib_imports("import tests.helpers\n"), ["tests.helpers"])
        self.assertEqual(_non_stdlib_imports("from runs_stats import discover\n"), ["runs_stats"])
        self.assertEqual(_non_stdlib_imports("import yaml\n"), ["yaml"])
        self.assertEqual(_non_stdlib_imports("from . import sibling\nfrom ..lib import x\n"), [".", "..lib"])

    def test_every_kernel_name_is_defined_in_fsafe(self):                              # (c)
        for name in KERNEL:
            with self.subTest(name=name):
                self.assertTrue(hasattr(fsafe, name), name)
        self.assertIsInstance(fsafe._ROOT_PIN, dict)


class TestBridgeHoldsNoKernelName(unittest.TestCase):
    def test_bridge_defines_and_re_exports_none_of_the_moved_names(self):             # (b)
        tree = ast.parse((LIB / "bridge.py").read_text(encoding="utf-8"))
        defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        assigned = {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        self.assertEqual(sorted((defined | assigned) & set(KERNEL)), [], "a second home for a kernel name")
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "fsafe":
                self.fail("bridge.py re-exports kernel names (`from fsafe import …`); callers must spell the kernel by its one name")
        for name in MOVED_CALLABLES:
            with self.subTest(name=name):
                self.assertFalse(name in vars(bridge), f"bridge.{name} still resolves")

    def test_bridge_bootstraps_before_importing_the_kernel(self):                    # (g)
        tree = ast.parse((LIB / "bridge.py").read_text(encoding="utf-8"))
        boot = imp = None
        for i, node in enumerate(tree.body):
            src = ast.unparse(node)
            if boot is None and src.startswith("runpy.run_path(") and "_bootstrap.py" in src:
                boot = i
            if isinstance(node, ast.Import) and any(a.name == "fsafe" for a in node.names):
                imp = i
        self.assertIsNotNone(boot, "no bootstrap statement"); self.assertIsNotNone(imp, "no `import fsafe`")
        self.assertLess(boot, imp)


class TestOneRefusalClassAndOnePin(unittest.TestCase):
    def test_exception_identity_holds_across_the_cut(self):                          # (d)
        self.assertIn(fsafe.BridgeError, bridge.JsonUnreadable.__mro__)
        self.assertIn(fsafe.BridgeError, advisors.AdvisorError.__mro__)
        self.assertTrue(issubclass(fsafe.AbsentPath, fsafe.BridgeError))

    def test_the_root_pin_is_one_dict_shared_by_pin_root_and_the_descent(self):        # (c)
        import tempfile, shutil, os
        base = Path(tempfile.mkdtemp(prefix="fsafe-pin-")); self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        root = base / "ws"; root.mkdir(); (root / "sub").mkdir()
        fsafe._ROOT_PIN.pop(str(root), None); self.addCleanup(fsafe._ROOT_PIN.pop, str(root), None)
        pinned = fsafe.pin_root(root)                                         # pin_root writes the pin ...
        self.assertEqual(fsafe._ROOT_PIN.get(str(root)), pinned)
        # ... and NO descent has run yet. Now swap the directory under the pinned path. The original stays
        # alive under another name so the replacement cannot inherit its inode (Linux hands freed inodes
        # straight back — an rmtree+recreate swap is invisible to a (dev, ino) pin there).
        os.rename(root, base / "ws.orig"); root.mkdir(); (root / "sub").mkdir()
        st = os.stat(root); self.assertNotEqual((st.st_dev, st.st_ino), pinned, "the swap must change the identity")
        # The FIRST descent through the swapped root must refuse: it reads pin_root's dict. A descent with a
        # pin of its own would pin the swapped directory lazily here and accept it.
        with self.assertRaises(fsafe.BridgeError):
            fsafe._open_dir_chain(root, ("sub",))
        self.assertEqual(fsafe._ROOT_PIN.get(str(root)), pinned, "a refusal must not re-pin")


def _heredoc_bodies(text):
    """The Python heredoc bodies of a shell file (`python3 - … <<'PY'` … `PY`), as tests/test_bootstrap.py extracts them."""
    return re.findall(r"python3 -[^\n]*<<'PY'\n(.*?)\nPY\n", text, re.S)


def _stale_kernel_references(source):
    """Executable reads of a moved name off the `bridge` module: `Attribute(value=Name('bridge'), attr=<moved>)`.
    Text — comments, docstrings, diagnostic strings — is not a reference; an unparseable source is reported."""
    tree = ast.parse(source)
    return sorted({f"bridge.{n.attr}" for n in ast.walk(tree)
                   if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "bridge" and n.attr in MOVED_CALLABLES})


class TestOneSpellingEverywhere(unittest.TestCase):
    def test_no_executable_reference_spells_a_moved_name_through_bridge(self):       # (e)
        offenders = []
        for base in ("scripts", "bin", "tests"):
            for p in sorted((REPO_ROOT / base).rglob("*")):
                if not p.is_file() or p.name == "test_fsafe_split.py":
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                sources = []
                if p.suffix == ".py" or (p.suffix == "" and text.startswith("#!") and "python" in text.splitlines()[0]):
                    sources = [text]
                elif p.suffix == ".sh":
                    sources = _heredoc_bodies(text)
                for src in sources:
                    try:
                        refs = _stale_kernel_references(src)
                    except SyntaxError:
                        continue          # a deliberately invalid fixture is not a caller
                    offenders += [f"{p.relative_to(REPO_ROOT)}: {r}" for r in refs]
        self.assertEqual(offenders, [], "the kernel has one name:\n  " + "\n  ".join(offenders))

    def test_the_reference_check_sees_a_real_stale_caller_and_ignores_prose(self):   # (e), both directions
        self.assertEqual(_stale_kernel_references("import bridge\nbridge.write_atomic(root, dest, 'x')\n"), ["bridge.write_atomic"])
        self.assertEqual(_stale_kernel_references("import bridge\nbridge.load_json(p)  # still bridge's\n"), [])
        prose = "\n".join(['"' * 3 + "every write goes through bridge.write_atomic" + '"' * 3, 'X = "bridge.write_atomic"', "# bridge.publish_new", ""])
        self.assertEqual(_stale_kernel_references(prose), [])
        self.assertEqual(_stale_kernel_references("import fsafe\nfsafe.write_atomic(root, dest, 'x')\n"), [])


class TestTheLintNowSeesBridge(unittest.TestCase):
    def test_both_exemption_sets_name_only_the_kernel(self):                         # (f)
        spec = importlib.util.spec_from_file_location("twd", REPO_ROOT / "tests" / "test_write_discipline.py")
        twd = importlib.util.module_from_spec(spec); spec.loader.exec_module(twd)
        self.assertEqual(twd.PRIMITIVE, {"scripts/lib/fsafe.py"})
        self.assertEqual(set(twd.EXEMPT), {"scripts/lib/fsafe.py"})


if __name__ == "__main__":
    unittest.main()
