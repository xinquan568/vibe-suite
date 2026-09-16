# SPDX-License-Identifier: ISC
"""vibe-318: no git the test suite spawns runs auto-maintenance, and every git-spawning module says so.

Test A is behavioural: a commit under the suite's environment spawns no `git maintenance` child
(observed through git's own trace2 stream), and the same commit WITHOUT the settings does — so the
observable is live on the running git, not a vacuous zero. Tests B and C are structural pins over
the source: every module that spawns git imports `git_env`, and every spawn either inherits
`os.environ` or carries the keys. D covers the helper's merge rules.
"""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import git_env  # noqa: E402  (installs the settings into os.environ)
from git_env import GIT_NO_AUTO_MAINTENANCE, SETTINGS, quiet_git_env  # noqa: E402

TESTS = Path(__file__).resolve().parent
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
SPAWN = re.compile(r"(^|\.)(subprocess|_sp|sp)\.(run|Popen|check_output|check_call|call)$")


def _maintenance_children(env):
    """argv of every child git spawned while committing one file in a fresh repository under `env`."""
    with tempfile.TemporaryDirectory(prefix="git-env-") as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        (repo / "a.txt").write_text("x\n", encoding="utf-8")
        trace = Path(tmp) / "trace.json"
        e = {**env, **IDENTITY, "GIT_TRACE2_EVENT": str(trace)}
        for argv in (["git", "init", "-q", "-b", "main", "."], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "seed"]):
            subprocess.run(argv, cwd=repo, env=e, check=True, capture_output=True)
        children = []
        for line in trace.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event") == "child_start":
                children.append(" ".join(event.get("argv", [])))
        return [c for c in children if "maintenance" in c or " gc " in f" {c} "]


def _without_settings(env):
    """`env` with our GIT_CONFIG_* entries removed (other entries kept, renumbered)."""
    out = {k: v for k, v in env.items() if not k.startswith("GIT_CONFIG_")}
    keep = []
    count = int(env.get("GIT_CONFIG_COUNT", "0") or 0)
    ours = {k for k, _ in SETTINGS}
    for i in range(count):
        k, v = env.get(f"GIT_CONFIG_KEY_{i}"), env.get(f"GIT_CONFIG_VALUE_{i}")
        if k is not None and k not in ours:
            keep.append((k, v))
    for i, (k, v) in enumerate(keep):
        out[f"GIT_CONFIG_KEY_{i}"], out[f"GIT_CONFIG_VALUE_{i}"] = k, v
    if keep:
        out["GIT_CONFIG_COUNT"] = str(len(keep))
    return out


class A_NoMaintenanceChild(unittest.TestCase):
    def test_a_commit_under_the_suite_environment_spawns_no_maintenance(self):
        control = _maintenance_children(_without_settings(os.environ))
        if not control:
            version = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
            self.skipTest(f"{version} spawns no maintenance child on commit, so this observable cannot fire here")
        self.assertEqual([], _maintenance_children(os.environ),
                         f"git still spawned auto-maintenance under the suite environment (control saw {control})")


def _git_spawning_modules():
    """Modules with an executable `git init`/`git commit` call, by the scope-aware walk the analysis used."""
    found = set()
    for p in sorted(TESTS.glob("test_*.py")):
        if p.name == Path(__file__).name:
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        if _spawns_git_init_or_commit(tree):
            found.add(p.name)
    return found


def _lit(e):
    if isinstance(e, ast.Constant):
        return e.value
    return "<*>" if isinstance(e, ast.Starred) else "<expr>"


def _sub_of(argv):
    rest, i = argv[1:], 0
    while i < len(rest):
        t = rest[i]
        if t in ("-C", "-c", "--git-dir"):
            i += 2
            continue
        if t in ("<expr>", "<*>") or (isinstance(t, str) and t.startswith(("--git-dir=", "-q"))):
            i += 1
            continue
        break
    return rest[i] if i < len(rest) else None


def _wrapper_of(fn):
    params = {a.arg for a in fn.args.args} | ({fn.args.vararg.arg} if fn.args.vararg else set())
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and SPAWN.search(ast.unparse(c.func)) and c.args:
            a0 = c.args[0]
            if isinstance(a0, (ast.List, ast.Tuple)):
                argv = [_lit(e) for e in a0.elts]
                star = [i for i, e in enumerate(a0.elts)
                        if isinstance(e, ast.Starred) and isinstance(e.value, ast.Name) and e.value.id in params]
                if argv and argv[0] == "git" and star:
                    return ("prefix", argv[:star[0]])
            elif isinstance(a0, ast.Name) and a0.id in params:
                return ("passthrough", None)
    return None


def _spawns_git_init_or_commit(tree):
    module_w = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and (w := _wrapper_of(n)):
            module_w[n.name] = w
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        local = dict(module_w)
        for st in fn.body:
            if (isinstance(st, ast.Assign) and isinstance(st.value, ast.Lambda) and len(st.targets) == 1
                    and isinstance(st.targets[0], ast.Name) and (w := _wrapper_of(st.value))):
                local[st.targets[0].id] = w
        for st in fn.body:
            if isinstance(st, ast.FunctionDef):
                continue
            for c in ast.walk(st):
                if not isinstance(c, ast.Call):
                    continue
                name = ast.unparse(c.func)
                argv = None
                if SPAWN.search(name) and c.args and isinstance(c.args[0], (ast.List, ast.Tuple)):
                    a = [_lit(e) for e in c.args[0].elts]
                    if a and a[0] == "git":
                        argv = a
                elif name.split(".")[-1] in local:
                    kind, pre = local[name.split(".")[-1]]
                    tail = [_lit(a) for a in c.args]
                    argv = pre + tail if kind == "prefix" else (tail if tail and tail[0] == "git" else None)
                if argv is not None and _sub_of(argv) in ("init", "commit"):
                    return True
    return False


def _imports_git_env(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name == "git_env" for a in n.names):
            return True
        if isinstance(n, ast.ImportFrom) and n.module == "git_env":
            return True
    return False


class B_EveryGitSpawningModuleImportsTheHelper(unittest.TestCase):
    def test_modules(self):
        mods = _git_spawning_modules()
        self.assertGreaterEqual(len(mods), 12, f"the census shrank: {sorted(mods)}")
        missing = sorted(m for m in mods if not _imports_git_env(TESTS / m))
        self.assertEqual([], missing, f"git-spawning modules that do not import git_env: {missing}")


class C_EverySpawnCarriesTheSettings(unittest.TestCase):
    """A structural rule over the source, deliberately narrow: an `env=` is accepted when it is absent
    (the child inherits the process environment, into which `git_env` installed the keys), when its
    expression INHERITS `os.environ` as a mapping (`{**os.environ, …}`, `dict(os.environ, …)`,
    `os.environ.copy()`, a comprehension over `os.environ.items()`), or when it names
    `GIT_NO_AUTO_MAINTENANCE` or is built by `quiet_git_env(...)`. A bare name or a call is followed to its definition — the nearest
    assignment earlier in the SAME function's own scope (nested functions excluded) first, then a
    module-level assignment or `def` (never a class method) — two levels deep. Borrowing a single entry (`{"PATH": os.environ["PATH"]}`) is NOT inheritance and is
    refused — that is the shape that carried the race. The one exemption is this module's own
    `_maintenance_children`, which test A calls with the keys deliberately stripped."""

    INHERITS = re.compile(r"\*\*os\.environ|dict\(os\.environ|os\.environ\.copy\(\)|os\.environ\.items\(\)|GIT_NO_AUTO_MAINTENANCE|quiet_git_env\(")
    EXEMPT_FUNCTIONS = {"_maintenance_children"}

    def test_spawns(self):
        offenders = []
        for p in sorted(TESTS.glob("test_*.py")):
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for fn, call in _spawn_calls(tree):
                if fn is not None and fn.name in self.EXEMPT_FUNCTIONS and p.name == Path(__file__).name:
                    continue
                for kw in call.keywords:
                    if kw.arg == "env" and not _env_inherits(tree, fn, kw.value, call.lineno, self.INHERITS):
                        offenders.append(f"{p.name}:{call.lineno} env={ast.unparse(kw.value)[:50]}")
        self.assertEqual([], offenders, "git/bash spawns whose env neither inherits os.environ nor carries the keys:\n  " + "\n  ".join(offenders))


def _spawn_calls(tree):
    """(enclosing function or None, call) for every subprocess call that spawns git or bash."""
    out = []
    def visit(node, fn):
        for child in ast.iter_child_nodes(node):
            inner = child if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
            if isinstance(child, ast.Call) and SPAWN.search(ast.unparse(child.func)) and child.args:
                head = ast.unparse(child.args[0])
                if head.startswith(('["git"', "['git'", '["bash"', "['bash'")) or head in ("a", "args"):
                    out.append((fn, child))
            visit(child, inner)
    visit(tree, None)
    return out


def _own_statements(fn):
    """Every node of `fn`'s body that is not inside a NESTED function or class — lexical scope, not the subtree."""
    out = []
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        out.append(n)
        stack.extend(ast.iter_child_nodes(n))
    return out


def _env_inherits(tree, fn, expr, before_line, pattern, depth=0):
    if pattern.search(ast.unparse(expr)):
        return True
    if depth >= 2:
        return False
    if isinstance(expr, ast.Name):
        name = expr.id
    elif isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name):
        name = expr.func.id
    else:
        return False
    # 1. the nearest earlier assignment to `name` in the SAME function's own scope (nested defs excluded)
    best = None
    if fn is not None:
        for n in _own_statements(fn):
            if isinstance(n, ast.Assign) and n.lineno < before_line and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
                if best is None or n.lineno > best.lineno:
                    best = n
    # 2. else a MODULE-LEVEL assignment or def — never a class method, never a nested binding
    if best is None:
        for n in tree.body:
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
                best = n
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
                best = n
    if best is None:
        return False
    if isinstance(best, ast.Assign):
        return _env_inherits(tree, fn, best.value, best.lineno, pattern, depth + 1)
    return any(isinstance(r, ast.Return) and r.value is not None and _env_inherits(tree, best, r.value, r.lineno, pattern, depth + 1)
               for r in _own_statements(best))


class D_MergeRules(unittest.TestCase):
    def test_empty_base_gets_exactly_the_settings(self):
        self.assertEqual(GIT_NO_AUTO_MAINTENANCE, {k: v for k, v in quiet_git_env({}).items()})

    def test_existing_entries_keep_their_numbers_and_ours_follow(self):
        base = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "user.name", "GIT_CONFIG_VALUE_0": "x"}
        env = quiet_git_env(base)
        self.assertEqual(("user.name", "x"), (env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"]))
        self.assertEqual("maintenance.auto", env["GIT_CONFIG_KEY_1"])
        self.assertEqual("gc.autoDetach", env["GIT_CONFIG_KEY_2"])
        self.assertEqual("3", env["GIT_CONFIG_COUNT"])

    def test_install_is_idempotent(self):
        once = quiet_git_env({})
        self.assertEqual(once, quiet_git_env(once))

    def test_a_malformed_count_is_left_alone(self):
        base = {"GIT_CONFIG_COUNT": "many"}
        self.assertEqual(base, quiet_git_env(base))

    def test_git_reads_the_settings(self):
        with tempfile.TemporaryDirectory(prefix="git-env-") as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True, capture_output=True)
            out = subprocess.run(["git", "-C", tmp, "config", "--get", "maintenance.auto"], env=quiet_git_env(os.environ),
                                 capture_output=True, text=True)
            self.assertEqual("false", out.stdout.strip())


if __name__ == "__main__":
    unittest.main()
