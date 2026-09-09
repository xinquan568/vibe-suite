#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""M12 (vibe-220): ONE inventory of what init owns in a workspace — `bridge.OWNED_TARGETS` — from
which `TARGETS`, `OWNED_BLOCKS`, and unbridge's JSON-key and exclusive-file views derive.

Two kinds of assertion, on purpose. VALUE assertions pin today's derived views (so a consumer that
reads them sees exactly what it saw before). DEPENDENCE assertions show the views actually derive:
a fresh interpreter rebinds `bridge.OWNED_TARGETS` before `init_bridge`/`unbridge` import and each
view must follow; `bridge`'s own two views, computed at its import, are held by a source-binding
guard instead. Equality alone cannot tell a derivation from a hand-written copy.
"""

import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB = REPO_ROOT / "scripts" / "lib"


def load(name):
    spec = importlib.util.spec_from_file_location(name, LIB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = load("bridge")

TODAYS_TARGETS = (".gitignore", "AGENTS.md", "CLAUDE.md", "GEMINI.md", ".codex/config.toml",
                  ".mcp.json", ".codex/hooks.json", ".vibe-suite.md", ".claude/vibe-history.json")
TODAYS_BLOCKS = (("AGENTS.md", "memory", "md"), ("CLAUDE.md", "import", "md"),
                 ("GEMINI.md", "import", "md"), (".gitignore", "ignore", "text"),
                 (".gitignore", "advisor-ignore", "text"),
                 (".codex/config.toml", "server:vibe-mcp", "text"))


class TestTheOneTable(unittest.TestCase):
    def test_targets_and_blocks_derive_from_the_one_table(self):
        self.assertEqual(bridge.TARGETS, TODAYS_TARGETS, "nine paths, creation order — a persisted shape")
        self.assertEqual(bridge.OWNED_BLOCKS, TODAYS_BLOCKS,
                         "six rows, md before text — the order unbridge reads paths in")
        self.assertEqual(tuple(rel for rel, _, _ in bridge.OWNED_TARGETS), bridge.TARGETS)
        for rel, kind, blocks in bridge.OWNED_TARGETS:
            with self.subTest(rel=rel):
                self.assertIn(kind, bridge.OWNED_KINDS)
                self.assertIsInstance(blocks, tuple)
                if kind == "exclusive-json":
                    self.assertEqual(blocks, ())
                else:
                    self.assertTrue(blocks, f"{rel}: a {kind} row names what is ours")
        self.assertEqual(bridge.OWNED_TARGETS[0], (".gitignore", "text-block", ("ignore", "advisor-ignore")))

    def _derivation(self, name):
        """The module-level assignment to `name` in bridge.py, checked to be `tuple(<genexp>)` whose
        comprehension(s) iterate the Name OWNED_TARGETS — the only shape that IS a derivation."""
        import ast
        source = (LIB / "bridge.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        nodes = [n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(tg, ast.Name) and tg.id == name for tg in n.targets)]
        self.assertEqual(len(nodes), 1, f"{name} must be assigned exactly once at module level")
        value = nodes[0].value
        self.assertTrue(isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "tuple"
                        and len(value.args) == 1 and isinstance(value.args[0], ast.GeneratorExp),
                        f"{name} must be tuple(<generator expression>), not a literal or tuple([...])")
        iterated = {gen.iter.id for gen in value.args[0].generators if isinstance(gen.iter, ast.Name)}
        self.assertIn("OWNED_TARGETS", iterated, f"{name}'s comprehension must iterate OWNED_TARGETS")
        return ast.get_source_segment(source, nodes[0])

    def test_bridges_own_views_derive_from_the_table_by_construction(self):
        # (c) computed at bridge's import, so checked by SOURCE SHAPE and by ISOLATED EXECUTION
        statements = self._derivation("TARGETS") + "\n" + self._derivation("OWNED_BLOCKS")
        perturbed = (("EXTRA.md", "md-block", ("extra",)),) + bridge.OWNED_TARGETS
        ns = {"OWNED_TARGETS": perturbed}
        exec(statements, ns)   # the production statements, over a table they have never seen
        self.assertEqual(ns["TARGETS"], ("EXTRA.md",) + TODAYS_TARGETS)
        self.assertEqual(ns["OWNED_BLOCKS"], (("EXTRA.md", "extra", "md"),) + TODAYS_BLOCKS)
        ns = {"OWNED_TARGETS": bridge.OWNED_TARGETS}
        exec(statements, ns)
        self.assertEqual(ns["TARGETS"], bridge.TARGETS); self.assertEqual(ns["OWNED_BLOCKS"], bridge.OWNED_BLOCKS)

    def test_every_block_belongs_to_a_target_and_the_docstring_names_the_table(self):
        self.assertLessEqual({rel for rel, _, _ in bridge.OWNED_BLOCKS}, set(bridge.TARGETS))
        self.assertIn("OWNED_TARGETS", bridge.__doc__)
        self.assertNotIn("six targets", bridge.__doc__, "the docstring counted blocks as targets")
        self.assertIn("nine owned targets", bridge.__doc__)

    def test_the_legacy_config_block_is_declared_and_no_longer_written(self):
        self.assertIn((".codex/config.toml", "server:vibe-mcp", "text"), bridge.OWNED_BLOCKS)
        init_source = (LIB / "init_bridge.py").read_text(encoding="utf-8")
        self.assertNotIn("server:vibe-mcp", init_source.split("def install", 1)[1],
                         "install() writes no server:vibe-mcp block since vibe-191; the row is for teardown")


class TestConsumersFollowTheTable(unittest.TestCase):
    """init_bridge and unbridge bootstrap and import bridge; their views are module-level derivations."""

    def test_value_assertions(self):
        r = subprocess.run([sys.executable, "-c", (
            "import runpy, sys, json; runpy.run_path(%r); import bridge, init_bridge, unbridge; "
            "print(json.dumps({'targets_is': init_bridge.TARGETS is bridge.TARGETS, "
            "'blocks_is': unbridge.BLOCKS is bridge.OWNED_BLOCKS, "
            "'json_keys': {k: list(v) for k, v in unbridge.OWNED_JSON_KEYS.items()}, "
            "'exclusive_json': list(unbridge.EXCLUSIVE_JSON), 'exclusive_files': list(unbridge.EXCLUSIVE_FILES)}))"
        ) % str(REPO_ROOT / "scripts" / "_bootstrap.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertTrue(got["targets_is"]); self.assertTrue(got["blocks_is"])
        self.assertEqual(got["json_keys"], {".mcp.json": ["mcpServers"], ".codex/hooks.json": ["hooks"]})
        self.assertEqual(got["exclusive_json"], [".claude/vibe-history.json"])
        self.assertEqual(got["exclusive_files"], [".vibe-suite.md", ".claude/vibe-history.json"])

    def test_dependence_a_perturbed_table_is_followed_by_every_derived_view(self):
        # bridge is imported first; its module-level views are already computed, so the perturbation
        # can only be observed through the consumers that derive at THEIR import — which is the claim
        perturbed = (
            ("EXTRA.md", "md-block", ("extra",)),
            (".gitignore", "text-block", ("ignore", "advisor-ignore")),
            (".mcp.json", "json-keys", ("renamedServers",)),
            (".codex/hooks.json", "json-keys", ("hooks",)),
            (".vibe-suite.md", "exclusive-md", ("config",)),
        )
        sentinel = TODAYS_TARGETS + ("SENTINEL.md",)
        r = subprocess.run([sys.executable, "-c", (
            "import runpy, sys, json; runpy.run_path(%r); import bridge; "
            "bridge.OWNED_TARGETS = %r; bridge.TARGETS = %r; import init_bridge, unbridge; "
            "print(json.dumps({'targets': list(init_bridge.TARGETS), 'targets_is': init_bridge.TARGETS is bridge.TARGETS, "
            "'json_keys': {k: list(v) for k, v in unbridge.OWNED_JSON_KEYS.items()}, "
            "'exclusive_json': list(unbridge.EXCLUSIVE_JSON), 'exclusive_files': list(unbridge.EXCLUSIVE_FILES), "
            "'blocks_is': unbridge.BLOCKS is bridge.OWNED_BLOCKS}))"
        ) % (str(REPO_ROOT / "scripts" / "_bootstrap.py"), perturbed, sentinel)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout.strip().splitlines()[-1])
        # (b) init_bridge.TARGETS is an ALIAS of bridge.TARGETS, bound at init_bridge's import: a sentinel
        # bound before that import is what it must be — a hand-written tuple there is neither `is` nor has it
        self.assertTrue(got["targets_is"]); self.assertIn("SENTINEL.md", got["targets"])
        # (a) unbridge's comprehensions run at its import and follow the rebound table
        self.assertEqual(got["json_keys"], {".mcp.json": ["renamedServers"], ".codex/hooks.json": ["hooks"]})
        self.assertEqual(got["exclusive_json"], [])
        self.assertEqual(got["exclusive_files"], [".vibe-suite.md"])
        self.assertTrue(got["blocks_is"])


if __name__ == "__main__":
    unittest.main()
