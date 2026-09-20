#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Run one tier of the Python suite — the inner loop (vibe-226 / grill M30).

    python3 tests/tiers.py behaviour [-v] [-f]   # tests that run a process or call repository code
    python3 tests/tiers.py contract  [-v] [-f]   # tests that execute nothing: they read text and assert on it
    python3 tests/tiers.py all       [-v] [-f]   # both — what CI runs
    python3 tests/tiers.py list [--json] [--why] # every test class and its tier

**The module set is CI's.** Exactly the top-level `tests/test_*.py` files, sorted — the rule `ci.yml`'s
`find tests -maxdepth 1 -name 'test_*.py'` and `tests/run-parallel.sh` apply, which `tests/test_ci_shards.py` pins.
Each is loaded by name (`tests.<stem>`) from the repository root; `unittest.discover` is not used, so the tiers can
neither lose a module CI runs nor add one it does not.

**The tier is computed, and the rule is an allowlist.** A class is *contract* only when **everything it references
resolves to something known not to execute**: a listed builtin, a listed standard-library module (with `os`, `sys` and
`unittest` judged per attribute, so `os.path` is fine and `os.system` is not), a test helper imported from the module
that defines it, a method of its own class or a listed method of a value. Anything the rule cannot resolve — an
unlisted name, a wildcard import, reflection through `__globals__`, a computed `getattr`, a string-driven load, a
`mock.patch` of a string target, a module object used as a value — makes the class *behaviour*. Every top-level name is
judged on its own and the verdicts propagate over the reference graph to a fixed point, so the answer never depends on
the order classes are declared in. A class body may set `tier = "behaviour"` to force the safe side; there is no way to
force *contract*, because an allowlist a class can opt out of is not an allowlist.

Both ways the rule can be wrong are safe for CI, which runs every module: a contract test misread as behaviour just
runs in the inner loop, and a behaviour test misread as contract is skipped only by the inner loop. A class the rule
cannot find in source (a load failure, a generated class) is behaviour, so a module that fails to import is reported by
the inner loop rather than hidden.

**The contract tier runs under a guard**, so a class misread as contract fails loudly instead of being skipped quietly.
While `contract` runs, an audit hook refuses every process start and records every load of repository code, and on
Python 3.12+ `sys.monitoring` records every call into repository code outside `tests/`. Instrumentation — a profiler, a
tracer, another monitoring tool, an audit hook — suspends that view, so installing one during the run is itself a
violation: the guard fails closed. Any violation prints a table and the command exits 1. On Python 3.11 there is no
`sys.monitoring`, so calls into already-loaded repository code are not detected; the command says so when it starts.
The `behaviour` and `all` tiers run unguarded, which is where a test that must profile or trace belongs.
"""

import argparse
import ast
import builtins
import importlib
import importlib.util
import json
import os
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TIERS = ("behaviour", "contract")

PURE_BUILTINS = frozenset({
    "len", "sorted", "set", "list", "dict", "tuple", "str", "int", "float", "bool", "bytes", "any", "all", "min", "max",
    "sum", "enumerate", "zip", "range", "isinstance", "issubclass", "next", "iter", "repr", "print", "frozenset",
    "reversed", "type", "super", "getattr", "hasattr", "map", "filter", "abs", "round", "ord", "chr", "hex", "open",
    "format", "hash", "id", "divmod", "object", "slice", "callable",
    "classmethod", "staticmethod", "property", "dir", "setattr", "delattr", "bytearray", "memoryview", "pow",
    "complex", "bin", "oct", "ascii", "NotImplemented", "Ellipsis", "BaseException", "ImportError",
    "ModuleNotFoundError", "PermissionError", "FileExistsError", "IsADirectoryError", "NotADirectoryError",
    "UnicodeError", "UnicodeEncodeError", "ZeroDivisionError", "AttributeError", "OverflowError", "TimeoutError",
    "UserWarning", "DeprecationWarning", "Warning", "RecursionError", "EOFError", "ExceptionGroup",
    "Exception", "AssertionError", "ValueError", "TypeError", "KeyError", "RuntimeError", "OSError", "FileNotFoundError",
    "NotImplementedError", "StopIteration", "IndexError", "LookupError", "SyntaxError", "UnicodeDecodeError"})
BUILTIN_NAMES = frozenset(dir(builtins))
MODULE_DUNDERS = frozenset({"__file__", "__name__", "__doc__"})
#: Standard-library modules none of whose functions start a process or load code by name.
PURE_MODULES = frozenset({"re", "json", "textwrap", "ast", "pathlib", "itertools", "collections", "functools", "string",
                          "fnmatch", "difflib", "hashlib", "base64", "math", "datetime", "tomllib", "unicodedata",
                          "copy", "dataclasses", "enum", "io", "struct", "hmac", "tempfile", "shutil", "stat", "time",
                          "codecs", "csv", "html", "keyword", "tokenize", "decimal", "fractions", "random",
                          "statistics", "glob", "posixpath", "types", "warnings", "zipfile", "tarfile", "gzip", "errno",
                          "shlex"})
#: os, sys and unittest are judged per attribute.
PURE_OS = frozenset({"path", "environ", "walk", "listdir", "scandir", "stat", "lstat", "getcwd", "sep", "fspath",
                     "makedirs", "mkdir", "chmod", "remove", "unlink", "rename", "replace", "rmdir", "getenv",
                     "readlink", "symlink", "link", "utime", "access", "umask", "getuid", "getpid", "linesep",
                     "curdir", "pardir", "devnull", "fsencode", "fsdecode", "open", "close", "read", "write", "fstat",
                     "mkfifo", "truncate", "isatty", "pathsep", "name", "O_RDONLY", "O_WRONLY", "O_CREAT",
                     "X_OK", "R_OK", "W_OK", "F_OK"})
PURE_SYS = frozenset({"path", "executable", "version_info", "platform", "stdout", "stderr", "stdin", "argv", "maxsize",
                      "byteorder", "getrecursionlimit", "stdlib_module_names", "version", "implementation",
                      "getdefaultencoding", "getfilesystemencoding", "prefix", "exc_info"})
UNITTEST_OK = frozenset({"TestCase", "skip", "skipIf", "skipUnless", "expectedFailure", "mock", "SkipTest",
                         "IsolatedAsyncioTestCase"})
MEDIATED = {"os": PURE_OS, "sys": PURE_SYS, "unittest": UNITTEST_OK}
#: Methods on values (str, bytes, Path, match objects, containers, hashes, tempdirs …).
PURE_METHODS = frozenset({
    "read_text", "read_bytes", "write_text", "write_bytes", "is_file", "is_dir", "is_symlink", "exists", "glob",
    "rglob", "iterdir", "relative_to", "resolve", "as_posix", "mkdir", "stat", "lstat", "joinpath", "with_name",
    "with_suffix", "with_stem", "unlink", "rmdir", "touch", "chmod", "rename", "replace", "symlink_to", "samefile",
    "open", "close", "read", "write", "readlines", "readline", "seek", "tell", "flush", "cleanup",
    "split", "rsplit", "strip", "lstrip", "rstrip", "splitlines", "startswith", "endswith", "lower", "upper",
    "casefold", "title", "capitalize", "join", "format", "encode", "decode", "count", "index", "find", "rfind",
    "rindex", "partition", "rpartition", "isdigit", "islower", "isupper", "isspace", "isalpha", "isalnum",
    "isidentifier", "zfill", "center", "ljust", "rjust", "expandtabs", "translate", "maketrans", "removeprefix",
    "removesuffix", "items", "keys", "values", "get", "pop", "popitem", "setdefault", "update", "append", "extend",
    "add", "insert", "remove", "discard", "clear", "sort", "reverse", "copy", "union", "intersection", "difference",
    "issubset", "issuperset", "fromkeys", "most_common", "elements", "group", "groups", "groupdict", "start", "end",
    "span", "search", "match", "fullmatch", "findall", "finditer", "sub", "subn", "hexdigest", "digest",
    "isoformat", "timestamp", "total_seconds", "strftime", "tobytes"})
EXECUTOR_METHODS = frozenset({"run", "call", "check_call", "check_output", "communicate", "spawn", "exec", "system",
                              "popen", "load_module", "exec_module", "loadTestsFromName", "loadTestsFromNames",
                              "loadTestsFromModule", "discover", "reload", "import_module", "run_path",
                              "run_module", "eval"})
#: Dunder attributes that read a name or apply an operator; any other (__globals__, __dict__, __code__,
#: __subclasses__, __builtins__ …) is reflection and makes a class behaviour.
PURE_DUNDERS = frozenset({"__name__", "__doc__", "__qualname__", "__module__", "__mro__", "__class__", "__str__",
                          "__repr__", "__init__", "__setitem__", "__getitem__", "__contains__", "__len__", "__iter__",
                          "__eq__", "__file__", "__enter__", "__exit__"})
TESTCASE_API = frozenset({"subTest", "skipTest", "fail", "addCleanup", "id", "shortDescription", "maxDiff",
                          "enterContext", "doCleanups"})
LIFECYCLE = frozenset({"setUp", "tearDown", "setUpClass", "tearDownClass", "__init__"})
#: Pure test helpers, trusted only when imported from the module that defines them (round 1's list, tied to its source
#: so a foreign callable aliased to a helper's name is judged by its own module).
HELPER_MODULES = frozenset({"tmpdirs", "git_env"})
HELPER_FROM = frozenset({("tmpdirs", "TempDirMixin"), ("tmpdirs", "scratch_dir"),
                         ("tests.test_auditor_state_machine", "extract"), ("tests.test_auditor_state_machine", "FIX"),
                         ("tests.test_skill_library", "parse_frontmatter")})
HELPER_METHODS = frozenset({"mkdtemp"})
PATCH_PARTS = frozenset({"patch", "dict", "multiple"})


def _bound_names(target):
    """Every plain name an assignment target binds, destructuring included."""
    return [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]


def judge_source(text):
    tree = ast.parse(text)
    # Every binding of every imported name, in any scope: a name bound to two modules is judged by the worst.
    bindings, from_names, module_objects, pairs = {}, {}, set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = (alias.asname or alias.name).split(".")[0]
                bindings.setdefault(name, set()).add(alias.name if alias.asname else alias.name.split(".")[0])
                pairs.setdefault(name, set()).add((alias.name if alias.asname else alias.name.split(".")[0], None))
                module_objects.add(name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                bindings.setdefault(name, set()).add(("." * node.level) + (node.module or ""))
                from_names.setdefault(name, set()).add(alias.name)
                pairs.setdefault(name, set()).add((("." * node.level) + (node.module or ""), alias.name))

    tops, classes = {}, {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            tops[node.name] = node
            if isinstance(node, ast.ClassDef):
                classes[node.name] = node
    # Module-level statements (assignments, mutations, loops …) attach to every top-level name they touch, so a
    # value installed later (`callbacks.append(subprocess.run)`) or bound by destructuring is judged with the name.
    def main_guard(node):
        """Exactly `if __name__ == "__main__":` — its body never runs on import (its else branch does)."""
        test = node.test if isinstance(node, ast.If) else None
        return isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq) \
            and isinstance(test.left, ast.Name) and test.left.id == "__name__" \
            and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value == "__main__"

    body = []
    for n in tree.body:
        if main_guard(n):
            body.extend(n.orelse)
        elif not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            body.append(n)
    bound = set(tops)
    for node in body:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                bound.add(sub.id)
    def receivers(node):
        """Names a module-level statement binds or mutates: x = …, x.m(…), x[k] = …, x.a = …, del x[k]."""
        names = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                names.add(sub.id)
            elif isinstance(sub, (ast.Subscript, ast.Attribute)) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                root = sub.value
                while isinstance(root, (ast.Subscript, ast.Attribute)):
                    root = root.value
                if isinstance(root, ast.Name):
                    names.add(root.id)
            elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                root = sub.func.value
                while isinstance(root, (ast.Subscript, ast.Attribute)):
                    root = root.value
                if isinstance(root, ast.Name):
                    names.add(root.id)
        return names

    statements = {}
    for node in body:
        for name in receivers(node) & bound:
            statements.setdefault(name, []).append(node)
    top_names = bound

    def module_verdict(module, name=None):
        """None when importing `name` from `module` (or the module itself) is known not to execute."""
        if module.startswith("."):
            return f"relative import {module}"
        top = module.split(".")[0]
        if (module, name) in HELPER_FROM or (module in HELPER_MODULES and name is None):
            return None
        if module in MEDIATED:
            if name is not None and name not in MEDIATED[module]:
                return f"from {module} import {name}"
            return None
        if top in MEDIATED:          # os.path, unittest.mock
            return None
        if top in PURE_MODULES:
            return None
        return f"references {module}"

    def foreign(name):
        if name in bindings:
            for module, original in sorted(pairs[name], key=str):
                why = module_verdict(module, original)
                if why:
                    return why
            return None
        if name in top_names:
            return None
        if name in BUILTIN_NAMES and name not in PURE_BUILTINS and name not in MODULE_DUNDERS:
            return f"builtin {name}"
        if name.startswith("__") and name.endswith("__") and name not in MODULE_DUNDERS:
            return f"dunder name {name}"
        return None

    def single_module(name):
        mods = bindings.get(name, set())
        return next(iter(mods)) if len(mods) == 1 else None

    def patcher(func):
        """True for mock.patch, patch.dict, patch.multiple and their aliases (not patch.object)."""
        chain = []
        while isinstance(func, ast.Attribute):
            chain.append(func.attr); func = func.value
        if not isinstance(func, ast.Name):
            return False
        root_mod = single_module(func.id)
        if root_mod is None or not root_mod.startswith("unittest"):
            return False
        chain.reverse()
        head = [o for o in from_names.get(func.id, {func.id})]
        parts = [p for p in head + chain if p not in ("mock", "unittest")]
        return bool(parts) and parts[0] == "patch" and all(p in PATCH_PARTS for p in parts)

    def patch_target(call):
        target = call.args[0] if call.args else next(
            (k.value for k in call.keywords if k.arg in ("target", "in_dict")), None)
        return target

    def pure_patch(call):
        target = patch_target(call)
        if isinstance(target, ast.Constant) and isinstance(target.value, str):
            return module_verdict(target.value.split(".")[0]) is None and target.value.split(".")[0] not in (
                "unittest",)
        # patch.dict on an object imports nothing: an attribute of an imported module (os.environ) or a dict literal.
        func = call.func
        is_dict = isinstance(func, ast.Attribute) and func.attr == "dict"
        return is_dict and (isinstance(target, ast.Dict) or (
            isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id in bindings))

    def module_attribute(node):
        """For `m.a` with m a module object: a verdict when the attribute is itself a module (shutil.os)."""
        mod = single_module(node.value.id)
        if mod is None or node.value.id not in module_objects:
            return None
        try:
            value = getattr(importlib.import_module(mod), node.attr, None) if mod.split(".")[0] in PURE_MODULES \
                or mod in MEDIATED else None
        except ImportError:
            return f"unresolvable {mod}"
        if isinstance(value, types.ModuleType):
            name = value.__name__
            if name.split(".")[0] == mod.split(".")[0] and mod not in MEDIATED:
                return None          # a submodule of the same pure package
            parent = parents.get(node)
            if name in MEDIATED:
                if isinstance(parent, ast.Attribute) and parent.value is node:
                    return None if parent.attr in MEDIATED[name] else f"{mod}.{node.attr}.{parent.attr}"
                return f"{mod}.{node.attr} used bare"
            return module_verdict(name)
        return None

    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def methods_of(cls_node, seen=()):
        found = set()
        for b in cls_node.bases:
            if isinstance(b, ast.Name) and b.id in classes and b.id not in seen:
                found |= methods_of(classes[b.id], seen + (b.id,))
        found |= {st.name for st in cls_node.body if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef))}
        return found

    class_methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods |= {st.name for st in node.body if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def direct(node, cls_methods):
        """(reason or None, top-level names referenced): judges node alone, without following names."""
        deps = set()
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Import, ast.ImportFrom)):
                for alias in sub.names:
                    if isinstance(sub, ast.Import):
                        why = module_verdict(alias.name)
                    else:
                        why = module_verdict(("." * sub.level) + (sub.module or ""), alias.name)
                    if why:
                        return why, deps
            elif isinstance(sub, ast.Name):
                why = foreign(sub.id)
                if why:
                    return why, deps
                if sub.id in module_objects and not (isinstance(parents.get(sub), ast.Attribute)
                                                     and parents[sub].value is sub):
                    return f"module {sub.id} used bare", deps
                if sub.id in top_names:
                    deps.add(sub.id)
            elif isinstance(sub, ast.Attribute):
                if sub.attr.startswith("__") and sub.attr.endswith("__") and sub.attr not in PURE_DUNDERS:
                    return f"reflection .{sub.attr}", deps
                if isinstance(sub.value, ast.Name) and sub.value.id in module_objects:
                    mod = single_module(sub.value.id)
                    if mod is None:
                        return f"conflicting bindings of {sub.value.id}", deps
                    if mod in MEDIATED and sub.attr not in MEDIATED[mod]:
                        return f"{mod}.{sub.attr}", deps
                    why = module_attribute(sub)
                    if why:
                        return why, deps
            if isinstance(sub, ast.Call):
                if patcher(sub.func):
                    if not pure_patch(sub):
                        return "patches a string or unknown target", deps
                    continue
                if isinstance(sub.func, ast.Name) and sub.func.id == "getattr" and sub.func.id not in bindings \
                        and not (len(sub.args) > 1 and isinstance(sub.args[1], ast.Constant)):
                    return "getattr with a computed name", deps
                if not isinstance(sub.func, ast.Attribute):
                    continue
                base, attr = sub.func.value, sub.func.attr
                if isinstance(base, ast.Name) and base.id in ("self", "cls"):
                    if attr in cls_methods or attr.startswith("assert") or attr in TESTCASE_API \
                            or attr in HELPER_METHODS or attr in LIFECYCLE:
                        continue
                    return f"calls self.{attr}()", deps
                if isinstance(base, ast.Call) and isinstance(base.func, ast.Name) and base.func.id == "super":
                    if attr in cls_methods or attr in LIFECYCLE or attr in HELPER_METHODS:
                        continue
                    return f"calls super().{attr}()", deps
                if attr in EXECUTOR_METHODS:
                    return f"calls .{attr}()", deps
                if isinstance(base, ast.Name) and base.id in bindings:
                    continue      # a function of an imported module or an imported callable, judged above
                if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id in bindings:
                    continue      # os.path.join: the chain's root was judged
                if (isinstance(base, ast.Name) and base.id in classes) or (
                        isinstance(base, ast.Call) and isinstance(base.func, ast.Name) and base.func.id in classes):
                    continue      # a same-module class, followed by name
                if attr in PURE_METHODS or attr in class_methods:
                    continue
                return f"calls .{attr}()", deps
        return None, deps

    # Judge every top-level name alone, then close over the reference graph: a name is behaviour when anything it
    # reaches is. Order-independent, and a cycle cannot cache a partial answer.
    alone, edges = {}, {}
    for name in top_names:
        nodes = ([tops[name]] if name in tops else []) + statements.get(name, [])
        why, deps = None, set()
        for node in nodes:
            m = methods_of(node) if isinstance(node, ast.ClassDef) else set()
            w, d = direct(node, m)
            why = why or w
            deps |= d
        alone[name], edges[name] = why, deps - {name}
    verdict = dict(alone)
    changed = True
    while changed:
        changed = False
        for name in top_names:
            if verdict[name] is None:
                for dep in edges[name]:
                    if verdict.get(dep):
                        verdict[name] = f"{dep} -> {verdict[dep]}"
                        changed = True
                        break

    def override(node):
        for st in node.body:
            if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name) \
                    and st.targets[0].id == "tier" and isinstance(st.value, ast.Constant) \
                    and st.value.value == "behaviour":
                return True
        return False

    # A module fixture runs for every class the module contributes, so each class depends on it.
    # `from X import *` binds names this rule cannot see. Trusted only when X itself is.
    def wildcard_verdict(module):
        # os, sys and unittest are trusted per attribute, so a wildcard from them is unresolved.
        return f"wildcard from {module}" if module in MEDIATED else module_verdict(module)

    wildcard = next((wildcard_verdict(m) for m, n in sorted(
        {(mod, nm) for nm, ps in pairs.items() if nm == "*" for mod, _ in ps}, key=str) if wildcard_verdict(m)), None)

    def fixture_verdict(name):
        """A module fixture defined here, or imported from another module (shared fixtures are ordinary reuse)."""
        if name in verdict:
            return verdict[name]
        return foreign(name) if name in bindings else None

    fixture = next((f"{n} -> {fixture_verdict(n)}" for n in ("setUpModule", "tearDownModule") if fixture_verdict(n)),
                   None)
    fixture = fixture or (f"wildcard import: {wildcard}" if wildcard else None)

    result = {}
    for name, node in classes.items():
        if fixture and not override(node):
            result[name] = ("behaviour", fixture)
            continue
        if override(node):
            result[name] = ("behaviour", "tier = \"behaviour\"")
        else:
            why = verdict[name]
            result[name] = ("behaviour", why) if why else ("contract", None)
    return result


def classify_source(text):
    """{class name: tier} for every class defined at the top level of a module's source."""
    return {name: tier for name, (tier, _) in judge_source(text).items()}


def modules(root=REPO_ROOT):
    """CI's module set: the stems of the top-level tests/test_*.py files, sorted."""
    return sorted(p.stem for p in (Path(root) / "tests").glob("test_*.py"))


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


MONITOR = getattr(sys, "monitoring", None)   # 3.12+ only: the guard needs a tool id it cannot lose
TOOL_NAME = "tiers-guard"
#: Installing a profiler, a tracer or another monitoring tool suspends the guard's view: while such a callback runs,
#: sys.monitoring raises no events, so repository calls made inside it are invisible. The guard fails closed on these.
INSTRUMENTATION_EVENTS = frozenset({"sys.setprofile", "sys.settrace", "sys.monitoring.register_callback",
                                    "sys.addaudithook"})
PROCESS_EVENTS = frozenset({"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork",
                            "os.forkpty", "os.startfile", "ctypes.dlopen"})


class Guard:
    """While active, records (test id, event, detail) for every process start, every load of code from a file in the
    repository, and every call into repository code outside tests/."""

    def __init__(self, root, monitor=MONITOR):
        self.root = str(Path(root).resolve()) + "/"
        self.tests = self.root + "tests/"
        self.current = None
        self.violations = []
        self.pending = []            # instrumentation seen while inactive: reported when enforcement starts
        self._installing = True      # the guard's own hook and callbacks are not foreign instrumentation
        self._where = {}
        self._loaded = {}             # id(code) -> (code, origin fixed when the code was loaded)
        self._cwd0 = os.getcwd()
        # Installed before the tier's modules load, recording nothing until start(): a thread or generator a module
        # creates at import is already instrumented when a test later drives it.
        # The audit hook (process starts, repository loads) works everywhere. Detecting a CALL into repository code
        # that is already loaded needs sys.monitoring, which owns its tool id and cannot be displaced (3.12+).
        self.monitor = monitor
        self.available = monitor is not None
        sys.addaudithook(self.observe)
        if self.available:
            tool = self.monitor.PROFILER_ID
            if self.monitor.get_tool(tool) is None:
                self.monitor.use_tool_id(tool, TOOL_NAME)
            E = self.monitor.events
            self.monitor.register_callback(tool, E.PY_START, self._py_start)
            self.monitor.register_callback(tool, E.PY_RESUME, self._py_start)
            self.monitor.register_callback(tool, E.PY_THROW, self._py_throw)
            self.monitor.set_events(tool, E.PY_START | E.PY_RESUME | E.PY_THROW)
        self._installing = False

    def _origin_of(self, code):
        """A code object's origin, fixed at load time when the load was seen (so a later chdir cannot move it)."""
        seen = self._loaded.get(id(code))
        if seen is not None and seen[0] is code:
            return seen[1]
        where = self._origin(code.co_filename)
        if not os.path.isabs(code.co_filename or "<"):
            # A relative name not seen at load: repository if it resolves there from where the guard started.
            cwd = os.getcwd()
            try:
                os.chdir(self._cwd0)
                first = self._origin(code.co_filename)
            finally:
                os.chdir(cwd)
            where = "repo" if "repo" in (where, first) else "tests" if "tests" in (where, first) else where
        return where

    def _remember(self, code):
        """Fix the origin of a code object and its nested code objects the FIRST time it is loaded: re-executing
        already-loaded code from another directory must not move it."""
        seen = self._loaded.get(id(code))
        if seen is not None and seen[0] is code:
            return seen[1]
        where = self._origin(code.co_filename)
        stack = [code]
        while stack:
            c = stack.pop()
            known = self._loaded.get(id(c))
            if known is not None and known[0] is c:
                continue
            self._loaded[id(c)] = (c, where)
            stack.extend(k for k in c.co_consts if isinstance(k, types.CodeType))
        return where

    def _origin(self, filename):
        """'repo' (a repository file outside tests/), 'tests', 'outside', or None when undecidable (a synthetic name).
        Relative names are resolved against the current directory, so they are not cached."""
        if not filename or filename.startswith("<"):
            return None
        relative = not os.path.isabs(filename)
        key = (os.getcwd(), filename) if relative else filename
        if key not in self._where:
            path = os.path.realpath(os.path.join(os.getcwd(), filename)) + ("/" if os.path.isdir(filename) else "")
            self._where[key] = "tests" if path.startswith(self.tests) else "repo" if path.startswith(self.root) \
                else "outside"
        return self._where[key]
    def _repo(self, filename):
        return self._origin(filename) in ("repo", "tests")

    def _record(self, event, detail):
        self.violations.append((self.current, event, detail))

    def observe(self, event, args):
        """The audit hook, and the seam a unit test drives directly."""
        if event == "exec" and args and isinstance(args[0], types.CodeType):
            where = self._remember(args[0])   # active or not: the origin is fixed the first time the code is loaded
            if self.current is not None and where in ("repo", "tests"):
                self._record("load", args[0].co_filename)
            return
        if event in INSTRUMENTATION_EVENTS:
            # Judged whether or not a test is running: instrumentation installed before enforcement starts suspends
            # the guard's view just as much, so it is held and reported at the first boundary.
            if self._installing:
                return
            if self.current is None:
                self.pending.append(event)
            else:
                self._record("instrumentation", event)
            return
        if self.current is None:
            return
        if event in PROCESS_EVENTS:
            self._record(event, repr(args[0])[:80] if args else "")      # os.fork / os.forkpty carry no arguments
            raise PermissionError(f"contract test started a process ({event}); it is behaviour")

    def _py_start(self, code, offset):
        where = self._origin_of(code)
        if where in ("outside", "tests") and os.path.isabs(code.co_filename):
            return self.monitor.DISABLE          # an absolute path never becomes repository code outside tests/
        if where == "repo" and self.current is not None:
            self._record("call", f"{code.co_filename}:{code.co_name}")
        return None

    def _py_throw(self, code, offset, exc):
        # PY_THROW cannot be disabled (3.14 raises and drops the callback), so this only records.
        if self._origin_of(code) == "repo" and self.current is not None:
            self._record("call", f"{code.co_filename}:{code.co_name}")
        return None

    def start(self, label):
        self.current = label
        self.check_ownership()
        self.check_instrumentation()

    def check_instrumentation(self):
        """Anything that can suspend the guard's view — another profiler, tracer, audit hook or monitoring tool —
        is refused rather than tolerated, whether it was installed during the run or before it."""
        for event in self.pending:
            self._record("instrumentation", f"{event} (before enforcement)")
        self.pending.clear()
        if sys.getprofile() is not None or sys.gettrace() is not None:
            self._record("instrumentation", "a profile or trace hook is installed")
        if self.available:
            for tool in range(6):
                if tool != self.monitor.PROFILER_ID and self.monitor.get_tool(tool) is not None:
                    self._record("instrumentation", f"monitoring tool {tool}: {self.monitor.get_tool(tool)}")

    def check_ownership(self):
        """The monitoring tool id is ours for the whole run. A second profiling tool cannot take it silently: the
        interpreter refuses the competing tool. If it is ever not ours, enforcement is gone and that is a violation."""
        if self.available and self.monitor.get_tool(self.monitor.PROFILER_ID) != TOOL_NAME:
            self._record("guard displaced", str(self.monitor.get_tool(self.monitor.PROFILER_ID)))

    def stop(self):
        self.check_ownership()
        self.check_instrumentation()
        self.current = None


class GuardedResult(unittest.TextTestResult):
    """Names the running test; between tests (class and module fixtures) the guard stays active, labelled by the
    test that ran last."""
    guard = None

    def startTest(self, test):
        super().startTest(test)
        self.guard.start(test.id())

    def stopTest(self, test):
        self.guard.check_ownership()
        self.guard.check_instrumentation()
        self.guard.current = f"fixture after {test.id()}"
        super().stopTest(test)


def guarded_run(cases, root, guard=None, verbosity=1, failfast=False):
    """Run `cases` under `guard`, active for the whole run so every fixture span is enforced."""
    guard = guard or Guard(root)
    GuardedResult.guard = guard
    runner = unittest.TextTestRunner(resultclass=GuardedResult, verbosity=verbosity, failfast=failfast)
    guard.start("fixture before the first test")      # active for the whole run: setUpClass runs before startTest
    try:
        result = runner.run(unittest.TestSuite(cases))
    finally:
        guard.stop()
    return result, guard.violations


def main(argv=None, monitor=MONITOR, guard_factory=None):
    parser = argparse.ArgumentParser(prog="tests/tiers.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("tier", choices=("behaviour", "contract", "all", "list"))
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root (default: this checkout)")
    parser.add_argument("--json", action="store_true", help="with `list`: machine-readable output")
    parser.add_argument("--why", action="store_true", help="with `list`: also print why a class is behaviour")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-f", "--failfast", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if args.tier == "list":
        rows = listing(root)
        if args.why:
            reasons = {}
            for stem in modules(root):
                for name, (_, why) in judge_source((Path(root) / "tests" / f"{stem}.py").read_text(
                        encoding="utf-8")).items():
                    reasons[f"tests.{stem}.{name}"] = why
            for row in rows:
                row["why"] = reasons.get(row["id"])
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for row in rows:
                print(f"{row['tier']:<10} {row['id']}" + (f"  # {row['why']}" if row.get("why") else ""))
        return 0

    guard = None
    if args.tier == "contract":
        # Before load(): a module's import-time threads and generators are then already covered, and every code
        # object's origin is fixed while it is loaded.
        guard = (guard_factory or Guard)(root, monitor=monitor)
        if not guard.available:
            print(f"call monitoring unavailable on {sys.version.split()[0]} (needs sys.monitoring, 3.12+): process "
                  f"starts and repository loads are still enforced by the audit hook")
    cases = select(root, args.tier)
    if guard is None:
        runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1, failfast=args.failfast)
        return 0 if runner.run(unittest.TestSuite(cases)).wasSuccessful() else 1

    result, violations = guarded_run(cases, root, guard, verbosity=2 if args.verbose else 1, failfast=args.failfast)
    if violations:
        print(f"\n{len(violations)} guard violation(s) — these tests execute and are not contract:")
        for test_id, event, detail in violations:
            print(f"  {test_id} · {event} · {detail}")
    return 0 if result.wasSuccessful() and not violations else 1


if __name__ == "__main__":
    sys.exit(main())
