# SPDX-License-Identifier: ISC
"""E3.4 (vibe-29) acceptance: /vibe-suite:check — cross-component consistency.
STAGED DRAFT (authored during the classifier outage; place as tests/test_check_goldens.py
after the plan verify clears and adjust only if the verify demands plan changes).

The engine (scripts/check_engine.py) owns the mechanical classes AND the composition; the
checker agent owns the two judgment classes by authored contract. Oracles are hand-derived
(the worksheet in tests/fixtures/check/broken/README.md predates the engine).

Engine CLI: --root <dir> [--config <file>] [--judgment <file>]; artifacts self-discovered
under the root (classify-routed); exit 0 scored, 2 refusal (bad root, <2 artifacts, unknown
judgment class). Output JSON: {"verdict": "CLEAN"|"<N> issues", "issues": [...],
"checked": {...}}. Composition: issues = mechanical + judgment; CLEAN iff empty.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from tests.test_skill_library import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE = REPO_ROOT / "scripts" / "check_engine.py"
BROKEN = REPO_ROOT / "tests" / "fixtures" / "check" / "broken"
CLEAN = REPO_ROOT / "tests" / "fixtures" / "check" / "clean"
ORACLE_MECH = BROKEN / "expected-mechanical.json"
ORACLE_COMPOSED = BROKEN / "expected-composed.json"
JUDGMENT = BROKEN / "judgment-input.json"
COMMAND = REPO_ROOT / "commands" / "check.md"
CHECKER = REPO_ROOT / "agents" / "checker.md"
PARTIAL = REPO_ROOT / "commands" / "shared" / "plugin-discover.md"

#: F4.3's four reportable reference-integrity directions (the constant half of the matrix).
F43_DIRECTIONS = {"command-partial", "agent-skills", "hook-script", "claude-md-listing"}
#: plugin-discover.md's map edges, parsed live in the matrix test.
PARTIAL_EDGES = {"command-agent", "command-partial", "agent-skill", "hook-script"}


def run_engine(root, extra=()):
    return subprocess.run(
        [sys.executable, str(ENGINE), "--root", str(root), *extra],
        capture_output=True,
    )


class DeliverablesShip(unittest.TestCase):
    def test_engine_ships_with_isc(self):
        head = ENGINE.read_text(encoding="utf-8").splitlines()[:3]
        self.assertTrue(any("SPDX-License-Identifier: ISC" in l for l in head))

    def test_agent_and_command_contracts(self):
        c = parse_frontmatter(CHECKER.read_text(encoding="utf-8"))
        self.assertEqual(c["model"], "sonnet")
        self.assertEqual(sorted(t.strip() for t in c["tools"].split(",")),
                         ["Bash", "Glob", "Read"])
        parse_frontmatter(COMMAND.read_text(encoding="utf-8"),
                          required=("description", "argument-hint"))

    def test_registered_in_manifest(self):
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("./commands/check.md", manifest["commands"])
        self.assertIn("./agents/checker.md", manifest["agents"])

    def test_checker_contract_carries_both_judgment_procedures(self):
        body = CHECKER.read_text(encoding="utf-8")
        self.assertIn("pairwise obligation comparison", body.lower())
        self.assertIn("clustering", body.lower())
        # the explicit clean conditions (no-finding conditions) must be stated
        self.assertRegex(body, r"(?i)zero obligation pairs")
        self.assertRegex(body, r"(?i)one name per concept")
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/check_engine.py"', body)

    def test_command_text_contract(self):
        body = COMMAND.read_text(encoding="utf-8")
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/check_engine.py"', body)
        self.assertRegex(body, r"(?i)at least two.*artifacts|>=2 artifacts")
        self.assertIn("CLEAN", body)
        for excluded in ("manifest-vs-disk", "frontmatter presence"):
            self.assertIn(excluded, body, "the E3.5 boundary must be stated")


class MechanicalGolden(unittest.TestCase):
    def test_per_class_catch_and_exact_golden(self):
        proc = run_engine(BROKEN)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        got = json.loads(proc.stdout.decode())
        want = json.loads(ORACLE_MECH.read_text(encoding="utf-8"))
        self.assertEqual(got["issues"], want["issues"])
        self.assertEqual(got["verdict"], want["verdict"])
        classes = [i["class"] for i in got["issues"]]
        self.assertEqual(classes.count("reference-integrity"), 4)
        self.assertIn("orphan", classes)
        self.assertIn("r51-drift", classes)
        directions = {i.get("direction") for i in got["issues"] if "direction" in i}
        self.assertEqual(directions, F43_DIRECTIONS)

    def test_verdict_n_fidelity(self):
        got = json.loads(run_engine(BROKEN).stdout.decode())
        self.assertEqual(got["verdict"], f"{len(got['issues'])} issues")

    def test_determinism_three_runs(self):
        outs = []
        for _ in range(3):
            proc = run_engine(BROKEN)
            self.assertEqual(proc.returncode, 0)
            outs.append(proc.stdout)
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[1], outs[2])

    def test_r51_disabled_default_excludes_the_class(self):
        # Same fixture, config suppressed via --config pointing at a missing file → defaults.
        proc = run_engine(BROKEN, extra=("--config", str(BROKEN / "no-such-config.md")))
        got = json.loads(proc.stdout.decode())
        self.assertNotIn("r51-drift", [i["class"] for i in got["issues"]])
        self.assertEqual(got["verdict"], "5 issues")


class Composition(unittest.TestCase):
    def test_composed_golden(self):
        proc = run_engine(BROKEN, extra=("--judgment", str(JUDGMENT)))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        got = json.loads(proc.stdout.decode())
        want = json.loads(ORACLE_COMPOSED.read_text(encoding="utf-8"))
        self.assertEqual(got["verdict"], want["verdict"])
        self.assertEqual(got["issues"], want["issues"])

    def test_composition_rule(self):
        mech = json.loads(run_engine(BROKEN).stdout.decode())
        composed = json.loads(
            run_engine(BROKEN, extra=("--judgment", str(JUDGMENT))).stdout.decode())
        judgment = json.loads(JUDGMENT.read_text(encoding="utf-8"))
        self.assertEqual(len(composed["issues"]), len(mech["issues"]) + len(judgment))

    def test_unknown_judgment_class_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text('[{"class": "invented-class", "detail": "x", "sources": []}]',
                           encoding="utf-8")
            proc = run_engine(BROKEN, extra=("--judgment", str(bad)))
            self.assertEqual(proc.returncode, 2)

    def test_clean_fixture_is_clean_both_modes(self):
        import tempfile
        for extra in ((), None):
            proc = run_engine(CLEAN) if extra == () else None
            if proc is None:
                with tempfile.TemporaryDirectory() as tmp:
                    empty = Path(tmp) / "empty.json"
                    empty.write_text("[]", encoding="utf-8")
                    proc = run_engine(CLEAN, extra=("--judgment", str(empty)))
            got = json.loads(proc.stdout.decode())
            self.assertEqual(got["verdict"], "CLEAN")
            self.assertEqual(got["issues"], [])


class Refusals(unittest.TestCase):
    def test_fewer_than_two_artifacts_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "skills" / "solo"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                "---\nname: solo\ndescription: one artifact only.\n---\n# solo\n",
                encoding="utf-8")
            proc = run_engine(tmp)
            self.assertEqual(proc.returncode, 2)
            self.assertIn(">=2 artifacts", proc.stderr.decode())

    def test_bad_root_refused(self):
        proc = run_engine(REPO_ROOT / "no-such-dir")
        self.assertEqual(proc.returncode, 2)


class DirectionMatrix(unittest.TestCase):
    def test_three_set_matrix(self):
        # Set A: the partial's map edges (parsed live from its reference-direction table).
        text = PARTIAL.read_text(encoding="utf-8")
        a = set()
        for pair, token in (("command", "agent"), ("command", "partial"),
                            ("agent", "skill"), ("hook", "script")):
            # the partial phrases the partial edge as "command → shared partial"
            self.assertRegex(text.lower(),
                             pair + r"\s*(→|->|to)\s*(shared\s+)?" + token,
                             f"the partial must still document the {pair}->{token} edge")
            a.add(f"{pair}-{token}")
        self.assertEqual(a, PARTIAL_EDGES)
        # Set B: F4.3's reportable directions (constant). Intersection: three edges.
        inter = {"command-partial", "hook-script"}
        # agent-skill (partial) and agent-skills (F4.3) are the same edge, named per source
        self.assertEqual(len(F43_DIRECTIONS & {"command-partial", "hook-script"}), 2)
        self.assertIn("claude-md-listing", F43_DIRECTIONS - {d for d in PARTIAL_EDGES})
        # command-agent is orphan-input only: the engine must not report it as a direction.
        got = json.loads(run_engine(BROKEN).stdout.decode())
        self.assertNotIn("command-agent",
                         {i.get("direction") for i in got["issues"] if "direction" in i})


if __name__ == "__main__":
    unittest.main()
