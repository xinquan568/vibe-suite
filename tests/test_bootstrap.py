#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""P4 / vibe-215: one bootstrap for the library path; `store` imports `config` once.

Acceptance, as tests: zero `sys.path` mutations under scripts/, bin/, tools/ except the bootstrap (a);
every program bootstraps and no library does (b); `effective_config` uses the shared `config` module
(c, d); the bootstrap is idempotent in a fresh process (e); programs load from a foreign cwd (f); the
lint's inventory is exactly the pinned set and `bin/` is scanned (g).
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
LIB = SCRIPTS / "lib"
BIN = REPO_ROOT / "bin"
TOOLS = REPO_ROOT / "tools"
BOOTSTRAP = SCRIPTS / "_bootstrap.py"

MUTATION = re.compile(r"sys\.path\s*(\.\s*(insert|append|extend)\s*\(|\+=)")

#: The pinned inventory (plan decision 2). A program that imports only the standard library is not in
#: it; (g) asserts the computed selector reproduces exactly this set.
TOP = sorted([
    "advisor_cli.py", "bridge_cli.py", "check_engine.py", "config_cli.py", "doctor.py",
    "issue2pr_mode_driver.py", "mechanical_fix.py", "mirror-sync.py", "profile_manifest.py",
    "render_final.py", "repair.py", "score_engine.py", "trend_engine.py", "update.py", "write_profile.py",
])
BIN_PROGRAMS = sorted([
    "vibe-badge", "vibe-build-case-studies-index", "vibe-build-docs", "vibe-build-reference-md",
    "vibe-build-site-report-pages", "vibe-build-vocab-data", "vibe-check", "vibe-report",
])
HEREDOCS = sorted(["common.sh", "migrate-config.sh", "migrate-history.sh", "migrate-sentinels.sh", "migrate-state.sh"])
LIB_PROGRAMS = sorted(["store.py", "init_bridge.py", "unbridge.py"])
STDLIB_ONLY_PROGRAMS = sorted(["scripts/lib/bridge.py", "scripts/lib/config.py", "scripts/lib/scope_tag.py"])


def local_names(root=REPO_ROOT):
    """Every bare module name a repository import can resolve: scripts/lib/*.py and scripts/*.py."""
    names = {p.stem for p in (root / "scripts" / "lib").glob("*.py")} | {p.stem for p in (root / "scripts").glob("*.py")}
    names.discard("_bootstrap")
    names.discard("__init__")
    return names


def module_level_local_imports(tree, names):
    """Positions of module-level statements importing a repository module by bare name."""
    out = []
    for i, node in enumerate(tree.body):
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[0] in names for a in node.names):
                out.append(i)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] in names:
                out.append(i)
    return out


def calls_run_path(tree):
    """True when any call anywhere in the module is `runpy.run_path(...)`, whatever its formatting or argument."""
    return any(isinstance(n, ast.Call) and ast.unparse(n.func) == "runpy.run_path" for n in ast.walk(tree))


def bootstrap_positions(tree):
    """Indices of module-level executable `runpy.run_path(<…_bootstrap.py>)` calls."""
    out = []
    for i, node in enumerate(tree.body):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            src = ast.unparse(node.value)
            if src.startswith("runpy.run_path(") and "_bootstrap.py" in src:
                out.append(i)
    return out


def heredoc_bodies(text):
    """The Python heredoc bodies of a shell file (`python3 - … <<'PY'` … `PY`)."""
    return re.findall(r"python3 -[^\n]*<<'PY'\n(.*?)\nPY\n", text, re.S)


def is_python_program(path):
    try:
        first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return False
    return first.startswith("#!") and "python" in first


def computed_inventory(root=REPO_ROOT):
    """The selector of plan decision 2: programs that import a repository module at module level."""
    names = local_names(root)
    top, bins, libs, heredocs = [], [], [], []
    for p in sorted((root / "scripts").glob("*.py")):
        if p.name == "_bootstrap.py":
            continue
        if module_level_local_imports(ast.parse(p.read_text(encoding="utf-8")), names):
            top.append(p.name)
    for p in sorted((root / "bin").iterdir()):
        if p.is_file() and os.access(p, os.X_OK) and is_python_program(p):
            if module_level_local_imports(ast.parse(p.read_text(encoding="utf-8")), names):
                bins.append(p.name)
    for p in sorted((root / "scripts" / "lib").glob("*.py")):
        text = p.read_text(encoding="utf-8")
        if '__name__ == "__main__"' in text and module_level_local_imports(ast.parse(text), names):
            libs.append(p.name)
    for p in sorted((root / "scripts" / "migrate").glob("*.sh")):
        for body in heredoc_bodies(p.read_text(encoding="utf-8")):
            if module_level_local_imports(ast.parse(body), names):
                heredocs.append(p.name)
                break
    return {"TOP": top, "BIN": bins, "LIB_PROGRAMS": libs, "HEREDOCS": heredocs}


def scan_mutations(root=REPO_ROOT):
    files = list((root / "scripts").rglob("*.py")) + list((root / "scripts").rglob("*.sh")) \
        + [p for p in (root / "bin").iterdir() if p.is_file()] + list((root / "tools").rglob("*.py"))
    hits = []
    for p in sorted(files):
        if p.resolve() == (root / "scripts" / "_bootstrap.py").resolve():
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if MUTATION.search(line):
                hits.append(f"{p.relative_to(root)}:{n}")
    return hits


def program_violations(root=REPO_ROOT):
    """(b): programs lacking a bootstrap call before their first local import; libraries carrying one."""
    names = local_names(root)
    missing, extra = [], []
    inv = computed_inventory(root)
    for rel in [f"scripts/{n}" for n in inv["TOP"]] + [f"bin/{n}" for n in inv["BIN"]] + [f"scripts/lib/{n}" for n in inv["LIB_PROGRAMS"]]:
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        first = module_level_local_imports(tree, names)[0]
        boots = bootstrap_positions(tree)
        if not boots or boots[0] > first:
            missing.append(rel)
    for n in inv["HEREDOCS"]:
        text = (root / "scripts" / "migrate" / n).read_text(encoding="utf-8")
        for body in heredoc_bodies(text):
            tree = ast.parse(body)
            locs = module_level_local_imports(tree, names)
            if not locs:
                continue
            boots = bootstrap_positions(tree)
            if not boots or boots[0] > locs[0]:
                missing.append(f"scripts/migrate/{n}")
    # libraries half: every non-program module in scripts/lib, the package marker included
    for p in sorted((root / "scripts" / "lib").glob("*.py")):
        if p.name in inv["LIB_PROGRAMS"]:
            continue
        if calls_run_path(ast.parse(p.read_text(encoding="utf-8"))):
            extra.append(f"scripts/lib/{p.name}")
    return missing, extra


def fresh(code, cwd=None, env=None):
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=cwd, env=env)


class TestBootstrapLint(unittest.TestCase):
    def test_no_sys_path_mutation_outside_the_bootstrap(self):
        hits = scan_mutations()
        self.assertEqual(hits, [], "sys.path mutations outside scripts/_bootstrap.py:\n  " + "\n  ".join(hits))

    def test_every_program_bootstraps_and_no_library_does(self):
        missing, extra = program_violations()
        self.assertEqual(missing, [], "programs without a bootstrap before their first repository import:\n  " + "\n  ".join(missing))
        self.assertEqual(extra, [], "library modules carrying a bootstrap call:\n  " + "\n  ".join(extra))

    def test_lint_inventory_is_exact_and_bin_is_scanned(self):
        inv = computed_inventory()
        self.assertEqual(inv, {"TOP": TOP, "BIN": BIN_PROGRAMS, "LIB_PROGRAMS": LIB_PROGRAMS, "HEREDOCS": HEREDOCS})
        for rel in STDLIB_ONLY_PROGRAMS:
            self.assertNotIn(Path(rel).name, inv["TOP"] + inv["BIN"] + inv["LIB_PROGRAMS"], rel)
        self.assertEqual([p for p in TOOLS.rglob("*.py") if module_level_local_imports(ast.parse(p.read_text()), local_names())], [])
        # a bin/-shaped program with a bare repository import and no bootstrap is reported
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for sub in ("scripts/lib", "scripts/migrate", "bin", "tools"):
                (root / sub).mkdir(parents=True)
            (root / "scripts" / "_bootstrap.py").write_text("import sys\n")
            (root / "scripts" / "lib" / "bridge.py").write_text("X = 1\n")
            fixture = root / "bin" / "vibe-fixture"
            fixture.write_text("#!/usr/bin/env python3\nimport bridge\n")
            fixture.chmod(0o755)
            self.assertEqual(computed_inventory(root)["BIN"], ["vibe-fixture"])
            missing, _ = program_violations(root)
            self.assertEqual(missing, ["bin/vibe-fixture"])
            fixture.write_text("#!/usr/bin/env python3\nimport runpy, pathlib\nrunpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / 'scripts' / '_bootstrap.py'))\nimport bridge\n")
            self.assertEqual(program_violations(root)[0], [])
            # libraries half: a multiline call in a library module and a one-liner in the package marker are
            # both reported, whatever the argument spelling
            (root / "scripts" / "lib" / "advisors.py").write_text(
                "import runpy\nimport pathlib\nrunpy.run_path(\n    str(\n        pathlib.Path(__file__).resolve().parents[1]\n        / 'boot.py'\n    )\n)\nX = 1\n")
            (root / "scripts" / "lib" / "__init__.py").write_text("import runpy; runpy.run_path('scripts/_bootstrap.py')\n")
            self.assertEqual(program_violations(root), ([], ["scripts/lib/__init__.py", "scripts/lib/advisors.py"]))


class TestSingleConfig(unittest.TestCase):
    def test_effective_config_uses_the_shared_config_module(self):
        with tempfile.TemporaryDirectory() as ws:
            code = (
                "import importlib.util, sys, json\n"
                f"s = importlib.util.spec_from_file_location('s', r'{LIB / 'store.py'}')\n"
                "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
                "shared = sys.modules['config']\n"
                "assert m.config is shared, 'store does not bind the shared config module'\n"
                "calls = []\n"
                "def stub(workspace):\n"
                "    calls.append(workspace); return {'engine': {'sentinel': 'from-stub'}}\n"
                "shared.load = stub\n"
                f"r = m.effective_config(r'{ws}')\n"
                "print(json.dumps({'calls': len(calls), 'sentinel': r.get('engine', {}).get('sentinel'), 'keys': sorted(k for k in sys.modules if k in ('config', 'vibe_config'))}))\n"
            )
            proc = fresh(code, cwd=ws)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(out["calls"], 1, out)
            self.assertEqual(out["sentinel"], "from-stub", out)
            self.assertEqual(out["keys"], ["config"], out)

    def test_config_cli_and_store_share_one_config_module(self):
        from unittest import mock
        import runpy
        runpy.run_path(str(BOOTSTRAP))
        import config_cli  # noqa: E402
        import store  # noqa: E402
        self.assertIs(config_cli.config_mod, store.config)
        with tempfile.TemporaryDirectory() as ws, \
                mock.patch.object(config_cli.config_mod, "load", return_value={"engine": {"sentinel": "patched"}}) as load:
            result = store.effective_config(ws)
        load.assert_called_once()
        self.assertEqual(result["engine"]["sentinel"], "patched")


class TestBootstrapModule(unittest.TestCase):
    def test_bootstrap_is_idempotent_in_a_fresh_process(self):
        lib, scripts = str(LIB), str(SCRIPTS)
        code = (
            "import sys, json, runpy\n"
            f"lib, scripts, boot = {lib!r}, {scripts!r}, {str(BOOTSTRAP)!r}\n"
            "sys.path = [p for p in sys.path if p not in (lib, scripts)]\n"
            "assert lib not in sys.path and scripts not in sys.path\n"
            "runpy.run_path(boot)\n"
            "first = list(sys.path)\n"
            "runpy.run_path(boot)\n"
            "second = list(sys.path)\n"
            "print(json.dumps({'lib': first.count(lib), 'scripts': first.count(scripts), 'same': first == second, "
            "'prefix': first[:2], "
            "'mods': sorted(k for k in sys.modules if '_bootstrap' in k and not k.startswith('importlib'))}))\n"
        )
        proc = fresh(code)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual((out["lib"], out["scripts"], out["same"], out["mods"]), (1, 1, True, []), out)
        # the requested precedence: scripts/lib first, then scripts/, ahead of everything else
        self.assertEqual(out["prefix"], [lib, scripts], out)
        # already present: the bootstrap adds nothing and removes nothing
        code2 = (
            "import sys, json, runpy\n"
            f"lib, scripts, boot = {lib!r}, {scripts!r}, {str(BOOTSTRAP)!r}\n"
            "sys.path = [scripts, lib] + [p for p in sys.path if p not in (lib, scripts)]\n"
            "before = list(sys.path); runpy.run_path(boot)\n"
            "print(json.dumps(before == sys.path))\n"
        )
        proc = fresh(code2)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip().splitlines()[-1], "true")

    def test_programs_load_from_a_foreign_cwd(self):
        targets = [LIB / "store.py", LIB / "init_bridge.py", LIB / "unbridge.py", SCRIPTS / "score_engine.py",
                   SCRIPTS / "mirror-sync.py", BIN / "vibe-check"]
        with tempfile.TemporaryDirectory() as td:
            for target in targets:
                with self.subTest(program=target.name):
                    code = (
                        "import importlib.util, importlib.machinery, sys\n"
                        f"path = r'{target}'\n"
                        "loader = importlib.machinery.SourceFileLoader('program_under_test', path)\n"
                        "spec = importlib.util.spec_from_loader('program_under_test', loader)\n"
                        "m = importlib.util.module_from_spec(spec); loader.exec_module(m)\n"
                        "print('loaded')\n"
                    )
                    proc = fresh(code, cwd=td)
                    self.assertEqual(proc.returncode, 0, f"{target.name}: {proc.stderr[-800:]}")
                    self.assertIn("loaded", proc.stdout)


if __name__ == "__main__":
    unittest.main()
