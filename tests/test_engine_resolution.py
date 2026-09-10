#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""M8 (vibe-221): the engine-resolution ladder has ONE executable statement — `scripts/lib/engine_resolution.py`
behind `config_cli.py resolve-engine`. These tests EXECUTE it (user wins; project file wins; the caller's default;
DEFER is `None`; `both` is a composition), hold the partial's vocabulary and output contract to the code, and check
that the Node bridge's `resolveModel` — which the runners consume — returns what the seam returns (regression
coverage of the delegation; the Node side has no model rule of its own any more)."""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB = REPO_ROOT / "scripts" / "lib"
PARTIAL = REPO_ROOT / "commands" / "shared" / "model-selection.md"


def load(name):
    spec = importlib.util.spec_from_file_location(name, LIB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = load("config")
er = load("engine_resolution")
ENGINES = tuple(config.SCHEMA["engine"].domain.split("|"))


def resolve(cfg, **kw):
    base = {"engine": None, "cross_model_audit_engine": "codex", "model_overrides": {}}
    base.update(cfg)
    return er.resolve(base, engines=ENGINES, **kw)


class TestLadder(unittest.TestCase):
    def test_user_choice_wins(self):
        self.assertEqual(resolve({"engine": "both"}, engine="codex")["engine"], "codex")

    def test_the_project_file_wins_when_the_user_says_nothing(self):
        self.assertEqual(resolve({"engine": "codex"})["engine"], "codex")

    def test_nothing_yields_the_callers_default(self):
        self.assertEqual(resolve({})["engine"], er.DEFAULT_ENGINE)
        self.assertEqual(er.DEFAULT_ENGINE, "claude")
        self.assertEqual(resolve({}, default="codex")["engine"], "codex")

    def test_an_unknown_engine_or_default_is_refused_not_coerced(self):
        for bad in ({"engine": "bogus"}, {"default": "bogus"}):
            with self.subTest(**bad):
                with self.assertRaises(er.EngineResolutionError) as ctx:
                    resolve({}, **bad)
                self.assertIn("bogus", str(ctx.exception))
        with self.assertRaises(er.EngineResolutionError):
            resolve({"engine": "bogus"})          # a bad value in the project file is refused too

    def test_cross_model_audit_engine_follows_the_reader(self):
        self.assertEqual(resolve({"cross_model_audit_engine": "codex"})["cross_model_audit_engine"], "codex")
        self.assertEqual(resolve({})["cross_model_audit_engine"], "codex")


class TestModel(unittest.TestCase):
    def test_the_users_model_wins(self):
        self.assertEqual(resolve({"engine": "codex", "model_overrides": {"codex": "cfg-model"}}, model="user-model")["model"], "user-model")

    def test_model_overrides_is_read_for_the_resolved_lane_only(self):
        self.assertEqual(resolve({"engine": "codex", "model_overrides": {"codex": "c"}})["model"], "c")

    def test_defer_is_none(self):
        self.assertIsNone(resolve({"engine": "codex"})["model"])

    def test_the_in_session_engine_never_names_a_model(self):
        self.assertIsNone(resolve({"engine": "claude", "model_overrides": {"codex": "c"}})["model"])
        self.assertIsNone(resolve({}, model="user-model")["model"], "claude has no model even when the user names one")


class TestBoth(unittest.TestCase):
    def test_both_is_claude_plus_the_cross_model_engine(self):
        out = resolve({"engine": "both", "cross_model_audit_engine": "codex", "model_overrides": {"codex": "c"}})
        self.assertEqual(out["lanes"], ["claude", "codex"])
        self.assertEqual(out["model"], "c", "the one external constituent's model")
        out = resolve({"engine": "both", "cross_model_audit_engine": "codex", "model_overrides": {"codex": "c"}})
        self.assertEqual(out["lanes"], ["claude", "codex"]); self.assertEqual(out["model"], "c")

    def test_a_single_engine_is_its_own_lane(self):
        self.assertEqual(resolve({"engine": "codex"})["lanes"], ["codex"])
        self.assertEqual(resolve({})["lanes"], ["claude"])

    def test_the_output_shape_is_exactly_four_keys(self):
        self.assertEqual(sorted(resolve({})), ["cross_model_audit_engine", "engine", "lanes", "model"])


class TestVocabularyAgreesWithCode(unittest.TestCase):
    """The partial keeps the vocabulary; the code keeps the ladder and the schema. Where both speak, they agree."""

    def test_the_partials_four_engine_values_are_the_schemas_domain(self):
        text = PARTIAL.read_text(encoding="utf-8")
        for value in ENGINES:
            with self.subTest(value=value):
                self.assertIn(f"`{value}`", text)
        self.assertEqual(len(ENGINES), 3)

    def test_the_four_documented_keys_are_in_the_reader_schema(self):
        # The partial's vocabulary table names these; the schema (config.SCHEMA) is where they are defined.
        for key in ("engine", "cross_model_audit_engine", "reviewer_backend", "reviewer_model"):
            with self.subTest(key=key):
                self.assertIn(key, config.SCHEMA)

    def test_the_partial_states_the_output_contract_and_no_precedence(self):
        # The partial says what the seam RETURNS; the order in which the code decides is the code's and its
        # tests' (TestLadder) — a prose restatement is what this issue removed, so its return is a failure here.
        text = PARTIAL.read_text(encoding="utf-8")
        for key in ("`engine`", "`cross_model_audit_engine`", "`lanes`", "`model`"):
            with self.subTest(key=key):
                self.assertIn(key, text)
        self.assertRegex(text, r"`null`[^\n]*no model flag", "null's meaning — pass no model flag — is the contract")
        lowered = text.lower()
        for phrase in ("highest wins", "then `.vibe-suite.md`", "then the tool default", "then the caller's default",
                       "use_value", "## priority ladder"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, lowered, "the partial restates precedence")

    def test_the_partial_carries_no_ladder_table_and_no_schema_table(self):
        text = PARTIAL.read_text(encoding="utf-8")
        self.assertNotIn("## Priority ladder", text)
        self.assertNotIn("## `.vibe-suite.md` keys", text)
        self.assertIn("resolve-engine", text)
        self.assertIn("scripts/lib/config.py", text, "the canonical reader stays named")


class TestTheNodeAndPythonModelRulesAgree(unittest.TestCase):
    """The runners get `model` from `config-bridge.mjs resolveModel`, which spawns the seam. Regression coverage of
    that delegation: for three (project file, user model) pairs the bridge returns exactly what the seam returns."""

    def node(self, root, model):
        script = ("import { resolveModel } from %r;"
                  "process.stdout.write(JSON.stringify(resolveModel(%s, { engine: 'codex', model: %s })));") % (
                      str(LIB / "config-bridge.mjs"), json.dumps(root), json.dumps(model))
        r = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_three_pairs(self):
        cases = [("---\nmodel_overrides:\n  codex: c\n---\n", "u", "u"),
                 ("---\nmodel_overrides:\n  codex: c\n---\n", None, "c"),
                 (None, None, None)]
        for frontmatter, user_model, want in cases:
            with self.subTest(frontmatter=frontmatter, user_model=user_model), tempfile.TemporaryDirectory() as root:
                if frontmatter is not None:
                    (Path(root) / ".vibe-suite.md").write_text(frontmatter, encoding="utf-8")
                py = er.resolve(config.load(root), engine="codex", model=user_model, engines=ENGINES)["model"]
                self.assertEqual(py, want)
                self.assertEqual(self.node(root, user_model), want)


if __name__ == "__main__":
    unittest.main()
