#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""No module-level name is bound twice in the same Python module (M6 / vibe-218 — `ruff F811`'s core case).

`scripts/lib/bridge.py` carried `_ROOT_PIN` and `pin_root` twice, byte-identically; Python's last binding
won, so nothing failed and nothing noticed. The gate battery runs `ruff check --select F811` where ruff is
installed (dev-only); this stdlib walk is the pin that holds without the dependency: every `scripts/**/*.py`
and every shebang-Python program under `bin/` has each top-level function, class and simple-assignment name
bound exactly once. Alternative bindings under `if`/`try` are not module-level statements and are not counted.
"""

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def python_modules():
    for p in sorted((REPO_ROOT / "scripts").rglob("*.py")):
        yield p.relative_to(REPO_ROOT).as_posix(), p.read_text(encoding="utf-8")
    for p in sorted((REPO_ROOT / "bin").iterdir()):
        if p.is_file():
            first = p.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
            if first and first[0].startswith("#!") and "python" in first[0]:
                yield p.relative_to(REPO_ROOT).as_posix(), p.read_text(encoding="utf-8")


def redefinitions(source):
    """Names bound more than once by module-level def / class / simple assignment statements."""
    seen, dup = {}, []
    for node in ast.parse(source).body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            names = [node.target.id]
        for name in names:
            if name in seen:
                dup.append((name, seen[name], node.lineno))
            else:
                seen[name] = node.lineno
    return dup


class NoModuleLevelRedefinitions(unittest.TestCase):
    def test_the_detector_sees_a_duplicate_and_ignores_alternatives(self):
        self.assertEqual(redefinitions("X = 1\ndef f():\n    pass\nX = 2\n"), [("X", 1, 4)])
        self.assertEqual(redefinitions("try:\n    import a as m\nexcept ImportError:\n    m = None\n"), [])
        self.assertEqual(redefinitions("def f():\n    pass\n\ndef f():\n    pass\n"), [("f", 1, 4)])

    def test_the_corpus_is_not_empty(self):
        names = [n for n, _ in python_modules()]
        self.assertGreater(len(names), 20, names)
        self.assertIn("scripts/lib/bridge.py", names)
        self.assertIn("bin/vibe-report", names)

    def test_no_module_binds_a_top_level_name_twice(self):
        offenders = []
        for rel, source in python_modules():
            for name, first, again in redefinitions(source):
                offenders.append(f"{rel}: {name} bound at {first} and again at {again}")
        self.assertEqual(offenders, [], "module-level redefinitions (ruff F811's core case):\n  " + "\n  ".join(offenders))


if __name__ == "__main__":
    unittest.main()
