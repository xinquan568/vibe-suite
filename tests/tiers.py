#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Run one tier of the Python suite — the inner loop (vibe-226 / grill M30).

    python3 tests/tiers.py behaviour [-v] [-f]   # tests that run a process or call repository code
    python3 tests/tiers.py contract  [-v] [-f]   # tests that execute nothing: they read text and assert on it
    python3 tests/tiers.py all       [-v] [-f]   # both — what CI runs
    python3 tests/tiers.py list [--json]         # every test class and its tier

**The module set is CI's.** Exactly the top-level `tests/test_*.py` files, sorted — the rule `ci.yml`'s
`find tests -maxdepth 1 -name 'test_*.py'` and `tests/run-parallel.sh` apply, which `tests/test_ci_shards.py` pins.
Each is loaded by name (`tests.<stem>`) from the repository root; `unittest.discover` is not used, so the tiers can
neither lose a module CI runs nor add one it does not.

**The tier is computed, not tagged.** A test class is *contract* when neither it, its bases in the same module, nor any
module-level function, class or variable it reaches (followed by name, transitively) uses an executor — a subprocess,
`runpy`, `multiprocessing`, `py_compile`, `exec`, a module load, `os.system` / `os.popen` — or an imported module that is
not in the standard library, other than the named test helpers below. Everything else is *behaviour*. A class body may
set `tier = "behaviour"` or `tier = "contract"` to override the rule. Both ways the rule can be wrong are safe: a contract
test misread as behaviour just runs in the inner loop; a behaviour test misread as contract is skipped only by the inner
loop, never by CI, which runs every module. A class the rule cannot find in source (a load failure, a generated class) is
behaviour, so a module that fails to import is reported by the inner loop rather than hidden.
"""

import argparse
import ast
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Names whose use means the code executes something.
EXECUTORS = frozenset({"subprocess", "runpy", "multiprocessing", "py_compile", "exec", "exec_module", "load_module",
                       "system", "popen", "run_path", "check_output", "spawn"})
#: Test infrastructure that executes nothing of the repository: the temp-dir mixin module, and pure helpers other
#: test modules export (a text parser, a fixture path, an environment builder).
HELPER_MODULES = frozenset({"tmpdirs"})
HELPER_NAMES = frozenset({"TempDirMixin", "parse_frontmatter", "extract", "FIX", "git_env", "scratch_dir"})
STDLIB = frozenset(sys.stdlib_module_names)
TIERS = ("behaviour", "contract")


def modules(root=REPO_ROOT):
    """CI's module set: the stems of the top-level tests/test_*.py files, sorted."""
    return sorted(p.stem for p in (Path(root) / "tests").glob("test_*.py"))


def classify_source(text):
    """{class name: tier} for every class defined at the top level of a module's source."""
    tree = ast.parse(text)
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported[(alias.asname or alias.name).split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imported[alias.asname or alias.name] = node.module
    tops = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            tops[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                if isinstance(target, ast.Name):
                    tops[target.id] = node

    def repo_import(name):
        module = imported.get(name)
        if module is None or name in HELPER_NAMES:
            return False
        top = module.split(".")[0]
        if top in HELPER_MODULES:
            return False
        return top == "tests" or top not in STDLIB

    def direct(node):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Attribute) and sub.attr in EXECUTORS:
                return True
            if isinstance(sub, ast.Name) and (sub.id in EXECUTORS or repo_import(sub.id)):
                return True
        return False

    # A module-level statement that executes (`spec.loader.exec_module(loaded)`) taints every top-level name it
    # touches: a class that later uses `loaded` reaches an executed module even though no assignment says so.
    tainted = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)) \
                and direct(node):
            tainted.update(sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name) and sub.id in tops)

    memo = {}

    def executes(node, seen):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Attribute):
                if sub.attr in EXECUTORS:
                    return True
                continue
            if not isinstance(sub, ast.Name):
                continue
            name = sub.id
            if name in EXECUTORS or name in tainted or repo_import(name):
                return True
            target = tops.get(name)
            if target is not None and target is not node and name not in seen:
                seen.add(name)
                if name not in memo:
                    memo[name] = executes(target, seen)
                if memo[name]:
                    return True
        return False

    def override(node):
        for statement in node.body:
            if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == "tier"
                    and isinstance(statement.value, ast.Constant) and statement.value.value in TIERS):
                return statement.value.value
        return None

    result = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            result[node.name] = override(node) or ("behaviour" if executes(node, {node.name}) else "contract")
    return result


_CLASSIFIED = {}


def tier_of(cls, root=REPO_ROOT):
    """The tier of a loaded TestCase class, from its module's source."""
    module = getattr(cls, "__module__", "")
    parts = module.split(".")
    if len(parts) != 2 or parts[0] != "tests":
        return "behaviour"
    path = Path(root) / "tests" / f"{parts[1]}.py"
    if path not in _CLASSIFIED:
        try:
            _CLASSIFIED[path] = classify_source(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            _CLASSIFIED[path] = {}
    return _CLASSIFIED[path].get(cls.__qualname__, "behaviour")


def _flatten(suite):
    stack = [suite]
    while stack:
        item = stack.pop()
        if isinstance(item, unittest.TestSuite):
            stack.extend(reversed(list(item)))
        else:
            yield item


_LOADED = {}


def load(root=REPO_ROOT):
    """Every test case the CI module set yields, loaded by name from the repository root."""
    root = Path(root).resolve()
    if root not in _LOADED:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        loader = unittest.TestLoader()
        cases = []
        for stem in modules(root):
            cases.extend(_flatten(loader.loadTestsFromName(f"tests.{stem}")))
        _LOADED[root] = cases
    return _LOADED[root]


def select(root, tier):
    return [case for case in load(root) if tier == "all" or tier_of(type(case), root) == tier]


def test_ids(root, tier):
    return {case.id() for case in select(root, tier)}


def listing(root=REPO_ROOT):
    seen = {}
    for case in load(root):
        cls = type(case)
        key = f"{cls.__module__}.{cls.__qualname__}"
        seen.setdefault(key, tier_of(cls, root))
    return [{"id": key, "tier": tier} for key, tier in seen.items()]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tests/tiers.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("tier", choices=("behaviour", "contract", "all", "list"))
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root (default: this checkout)")
    parser.add_argument("--json", action="store_true", help="with `list`: machine-readable output")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-f", "--failfast", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if args.tier == "list":
        rows = listing(root)
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for row in rows:
                print(f"{row['tier']:<10} {row['id']}")
        return 0
    suite = unittest.TestSuite(select(root, args.tier))
    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1, failfast=args.failfast)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
