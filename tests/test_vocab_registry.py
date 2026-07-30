# SPDX-License-Identifier: ISC
"""E3.7 (vibe-32) acceptance: /vibe-suite:vocab + the suite's own registry.

Rung 0/1 pins: the suite registry parses under the REAL fail-closed reader and the
suite passes its own R51 check via a REAL engine run; the config enables R51; the five
vocabulary-skill statement edits; the extractor's mechanical contract on its fixture;
the inline init stub's validity; the command/agent contracts (drift clustering quality
is the agent's judgment lane and is not simulated).
"""

import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "skills" / "vocabulary" / "registry.yaml"
SKILL = REPO_ROOT / "skills" / "vocabulary" / "SKILL.md"
CONFIG = REPO_ROOT / ".vibe-suite.md"
EXTRACTOR = REPO_ROOT / "scripts" / "vocab_extract.py"
COMMAND = REPO_ROOT / "commands" / "vocab.md"
AGENT = REPO_ROOT / "agents" / "vocab-drift-scanner.md"
SPEC = REPO_ROOT / ".vibe-test" / "vocab-drift-scanner.spec.md"
FIX = REPO_ROOT / "tests" / "fixtures" / "vocab"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

CANONICAL_VERBS = ["score", "check", "test", "scan", "ls", "audit", "review",
                   "delegate"]
ARTIFACT_NOUNS = ["command", "agent", "skill", "rule", "hook", "manifest",
                  "frontmatter", "artifact"]
OUTPUT_NOUNS = ["finding", "violation", "penalty", "score", "snapshot", "inventory",
                "report", "spec"]
ROLE_PAIRS = {"scorer": "score", "checker": "check", "tester": "test",
              "scanner": "ls"}


def load_check_engine():
    loader = importlib.machinery.SourceFileLoader(
        "check_engine_mod", str(REPO_ROOT / "scripts" / "check_engine.py"))
    spec = importlib.util.spec_from_loader("check_engine_mod", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class SuiteRegistry(unittest.TestCase):
    def test_parses_under_the_real_reader_with_the_frozen_term_table(self):
        engine = load_check_engine()
        terms = engine.registry_terms(REGISTRY)
        self.assertEqual(terms, [("implement", "delegate",
                                  ["commands/**", "agents/**"])])

    def test_suite_passes_its_own_r51_check(self):
        # THE acceptance clause: a real engine run over the repo root (default config
        # reads the new .vibe-suite.md) must yield zero r51-drift issues. Other
        # classes are other items' concerns and are filtered.
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "check_engine.py"),
             "--root", str(REPO_ROOT)],
            capture_output=True)
        self.assertIn(proc.returncode, (0, 1), proc.stderr.decode())
        got = json.loads(proc.stdout.decode())
        r51 = [i for i in got["issues"] if i["class"] == "r51-drift"]
        self.assertEqual(r51, [])

    def test_config_enables_r51(self):
        import config
        resolved, warnings = config.load_with_warnings(str(REPO_ROOT))
        self.assertEqual(warnings, [])
        r51 = resolved["rule_overrides"]["R51"]
        self.assertIs(r51["enabled"], True)
        self.assertEqual(r51["vocabulary_skill"], "skills/vocabulary")


class SkillEdits(unittest.TestCase):
    def _text(self):
        return SKILL.read_text(encoding="utf-8")

    def test_five_statement_edits(self):
        text = self._text()
        gone = [
            "flagged by `/vibe-suite:check` and\npenalized by `/vibe-suite:score`",
            "does not ship with this skill",
            "Readers: only the check and score paths read the registry",
            "If either is missing, R51 cannot fire and\n  the scorer emits an advisory note instead",
        ]
        for old in gone:
            self.assertNotIn(old, text, f"stale statement remains: {old[:50]}")
        present = [
            "penalization is DEFERRED",
            "When score enforcement lands:",
            "the check path reads and enforces today",
            "The registry SHIPS as of E3.7",
            "fires WHENEVER R51 is enabled",
        ]
        for new in present:
            self.assertIn(new, text, f"missing new statement: {new}")

    def test_authoritative_tables_and_candidates_note(self):
        text = self._text()
        self.assertIn("## The suite registry (authoritative tables)", text)
        for verb in CANONICAL_VERBS:
            self.assertRegex(text, rf"\|\s*`{verb}`", f"verb row missing: {verb}")
        self.assertIn("`implement`", text)
        self.assertIn("plan-i1-r1.md:672", text)
        for decision in ("engine", "cross_model_audit_engine", "reviewer backend"):
            self.assertIn(decision, text)
        self.assertIn("Candidate deprecations (pending prose cleanup", text)
        for blocked in ("lint", "validate", "analyze"):
            self.assertIn(blocked, text)


class Extractor(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(EXTRACTOR), *args],
                              capture_output=True)

    def test_isc_and_fixture_contract(self):
        head = EXTRACTOR.read_text(encoding="utf-8").splitlines()[:3]
        self.assertTrue(any("SPDX-License-Identifier: ISC" in l for l in head))
        proc = self._run("--root", str(FIX / "extract"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        got = json.loads(proc.stdout.decode())
        rows = {t["term"]: t for t in got["terms"]}
        self.assertEqual(rows["wombat"]["count"], 4)
        self.assertEqual(len(rows["wombat"]["files"]), 3)
        self.assertEqual(rows["quokka"]["count"], 3)
        self.assertEqual(len(rows["quokka"]["files"]), 3)
        self.assertEqual(rows["numbat"]["count"], 1)
        self.assertEqual(rows["numbat"]["files"], ["CLAUDE.md"])

    def test_min_count_and_determinism(self):
        proc = self._run("--root", str(FIX / "extract"), "--min-count", "4")
        got = json.loads(proc.stdout.decode())
        terms = [t["term"] for t in got["terms"]]
        self.assertIn("wombat", terms)
        self.assertNotIn("quokka", terms)
        self.assertNotIn("numbat", terms)
        a = self._run("--root", str(FIX / "extract")).stdout
        b = self._run("--root", str(FIX / "extract")).stdout
        self.assertEqual(a, b)

    def test_canonical_warrant_over_the_suite(self):
        proc = self._run("--root", str(REPO_ROOT))
        got = json.loads(proc.stdout.decode())
        rows = {t["term"]: t for t in got["terms"]}
        for term in CANONICAL_VERBS + ARTIFACT_NOUNS + OUTPUT_NOUNS:
            self.assertIn(term, rows, f"no literary warrant for {term}")
            self.assertGreater(len(rows[term]["files"]), 0, term)


class CommandContract(unittest.TestCase):
    def _body(self):
        return COMMAND.read_text(encoding="utf-8")

    def test_init_contract_and_stub_validity(self):
        body = self._body()
        for token in ("layout detection", "R51 opt-in", "refuse"):
            self.assertIn(token.lower(), body.lower())
        m = re.search(r"```yaml\n(scopes:.*?)```", body, re.S)
        self.assertIsNotNone(m, "no inline registry stub fence")
        stub_path = FIX / "extract" / "_stub_tmp.yaml"
        stub_path.write_text(m.group(1), encoding="utf-8")
        try:
            engine = load_check_engine()
            engine.registry_terms(stub_path)   # must not raise
        finally:
            stub_path.unlink()

    def test_drift_contract(self):
        body = self._body()
        flat = re.sub(r"\s+", " ", body)
        self.assertRegex(flat, r"(?i)at least 5|≥5|fewer than 5")
        self.assertRegex(flat, r"(?i)cap(ped)? (of |at )?20")
        for d in ("drift", "likely", "co-occurrence", "ambiguous"):
            self.assertIn(d, flat)
        self.assertIn("cross_scope_homonyms", flat)
        self.assertRegex(flat, r"(?i)never penalizes|advisory[- ]only")

    def test_registered(self):
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("./commands/vocab.md", manifest["commands"])
        self.assertIn("./agents/vocab-drift-scanner.md", manifest["agents"])
        self.assertEqual(len(manifest["commands"]), 17)
        self.assertEqual(len(manifest["agents"]), 6)


class AgentVsSpec(unittest.TestCase):
    def test_frontmatter_valid_rows(self):
        body = AGENT.read_text(encoding="utf-8")
        self.assertRegex(body, r"(?m)^description: Use when")
        self.assertRegex(body, r"(?m)^model: (haiku|sonnet|opus)$")
        self.assertRegex(body, r"(?m)^tools: ")

    def test_output_contains_rows(self):
        body = AGENT.read_text(encoding="utf-8").lower()
        spec = SPEC.read_text(encoding="utf-8")
        self.assertIn("dispositions", body)
        self.assertRegex(body, r"advisory")
        # the spec's Output Contains elements are echoed by the agent's contract
        for element in ("clusters with dispositions", "advisory-only"):
            self.assertIn(element.split()[0], body)
        self.assertIn("vocab-drift-scanner", spec)


class Fixtures(unittest.TestCase):
    def test_drift_fixture_six_artifacts_two_terms(self):
        files = sorted((FIX / "drift").glob("*.md"))
        self.assertEqual(len(files), 6)
        text = " ".join(f.read_text(encoding="utf-8") for f in files)
        self.assertIn("report", text)
        self.assertIn("dossier", text)

    def test_init_existing_fixture(self):
        self.assertTrue(
            (FIX / "init-existing" / "skills" / "demo" / "vocabulary" /
             "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
