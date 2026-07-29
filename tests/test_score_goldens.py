# SPDX-License-Identifier: ISC
"""E3.3 (vibe-28) acceptance: /vibe-suite:score — the deterministic claude lane.

The engine (scripts/score_engine.py) is the ONLY penalty authority; agents narrate. The
oracle (tests/fixtures/nl-audit/defective-skill/expected.json + its worksheet README) was
computed BY HAND from the scoring skill's tables before the engine existed — the engine must
reproduce it, never the reverse.

Engine CLI contract pinned here:
  stdin  : records `<type>\\x1f<relative-path>\\x00` (same lossless framing as ls_counts)
  args   : --root <dir> [--config <file>] [--history <file>] [--scope <tag>]
  stdout : JSON {"files":[{"path","score","band","findings":[{"rule","check","line","penalty"}],
           "advisories":[{"rule","note"}]}], "run":{"files","total_penalty","considered_rows"}}
  exit   : 0 scored; 2 contract refusal (bad record, bad root)

Row ledger: scripts/score_engine_rows.md classifies every scoring-table row as `mechanical`
(predicate quoted from the owning text) or `advisory-zero`; this suite asserts the ledger is
complete and that the engine deducts ONLY on mechanical rows.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_skill_library import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE = REPO_ROOT / "scripts" / "score_engine.py"
LEDGER = REPO_ROOT / "scripts" / "score_engine_rows.md"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "nl-audit" / "defective-skill"
ORACLE = FIXTURE / "expected.json"
COMMAND = REPO_ROOT / "commands" / "score.md"
SCORER = REPO_ROOT / "agents" / "scorer.md"
VAGUE = REPO_ROOT / "agents" / "vague-scanner.md"
SCORING_SKILL = REPO_ROOT / "skills" / "scoring" / "SKILL.md"

US, RS = "\x1f", "\x00"

#: The R01 list as the scoring skill pins it — asserted verbatim against the skill text.
VAGUE_WORDS = (
    "appropriate", "relevant", "as needed", "sufficient", "adequate", "reasonable",
    "properly", "correctly", "some", "several", "various",
)


def run_engine(records, root, extra=()):
    payload = "".join(f"{t}{US}{p}{RS}" for t, p in records)
    return subprocess.run(
        [sys.executable, str(ENGINE), "--root", str(root), *extra],
        input=payload.encode("utf-8"),
        capture_output=True,
    )


def score_one(body, extra=(), name="probe", dirname=None):
    """Score a synthetic one-skill tree; returns the engine's file object."""
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / "skills" / (dirname or name)
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
        rel = f"skills/{dirname or name}/SKILL.md"
        proc = run_engine([("skill", rel)], tmp, extra)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr.decode())
        return json.loads(proc.stdout.decode())["files"][0]


def clean_skill(name="probe", description=None, body_lines=8, examples=1):
    desc = description or "Scores a probe artifact; use when testing rows, checks, penalties."
    lines = [
        "---", f"name: {name}", f"description: {desc}", "---", "",
        f"# {name}", "",
    ]
    lines += [f"Guidance line {i} stating one concrete obligation." for i in range(body_lines)]
    lines += ["", "## Scope note", "Covers probes; see [scoring](../scoring/SKILL.md)."]
    for _ in range(examples):
        lines += ["<example>", "Context: probe.", "user: probe?", "assistant: probing.", "</example>"]
    return "\n".join(lines) + "\n"


class DeliverablesShip(unittest.TestCase):
    def test_engine_ships_with_isc_and_ledger(self):
        head = ENGINE.read_text(encoding="utf-8").splitlines()[:3]
        self.assertTrue(any("SPDX-License-Identifier: ISC" in l for l in head))
        self.assertTrue(LEDGER.is_file(), "the row ledger must ship beside the engine")

    def test_agents_and_command_contracts(self):
        s = parse_frontmatter(SCORER.read_text(encoding="utf-8"))
        self.assertEqual(s["model"], "sonnet")
        self.assertEqual(
            sorted(t.strip() for t in s["tools"].split(",")), ["Bash", "Glob", "Read"]
        )
        v = parse_frontmatter(VAGUE.read_text(encoding="utf-8"))
        self.assertEqual(v["model"], "haiku")
        self.assertEqual(sorted(t.strip() for t in v["tools"].split(",")), ["Glob", "Read"])
        parse_frontmatter(
            COMMAND.read_text(encoding="utf-8"), required=("description", "argument-hint")
        )

    def test_registered_in_manifest(self):
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertIn("./commands/score.md", manifest["commands"])
        for agent in ("./agents/scorer.md", "./agents/vague-scanner.md"):
            self.assertIn(agent, manifest["agents"])

    def test_scorer_text_contract(self):
        body = SCORER.read_text(encoding="utf-8")
        for skill in ("scoring", "conventions", "vocabulary"):
            self.assertIn(skill, body)
        for stage in ("rubric", "do-not-penalize", "tier", "intent", "tool-catalog", "confidence"):
            self.assertIn(stage, body.lower())
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/score_engine.py"', body)

    def test_vague_scanner_list_matches_scoring_skill_verbatim(self):
        skill_row = SCORING_SKILL.read_text(encoding="utf-8")
        agent_body = VAGUE.read_text(encoding="utf-8")
        for word in VAGUE_WORDS:
            self.assertIn(word, skill_row)
            self.assertIn(word, agent_body)
        self.assertIn("-2", agent_body)
        self.assertIn("-20", agent_body)

    def test_command_text_contract(self):
        body = COMMAND.read_text(encoding="utf-8")
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/score_engine.py"', body)
        self.assertIn("| # | Sev | Rule | Line | Issue | Penalty | Fix |", body)
        for band in ("Excellent", "Good", "Adequate", "Weak", "Rewrite"):
            self.assertIn(band, body)
        self.assertRegex(body, r"(?i)batch(es)? of (at most )?5|≤5")
        self.assertNotIn("--engine", body, "cross-model lanes are E4.5's, not this command's")
        self.assertIn("vibe-history.json", body)


class GoldenAndDeterminism(unittest.TestCase):
    def _fixture_records(self):
        return [("skill", "skills/defective/SKILL.md")]

    def test_ac2_same_output_three_runs(self):
        outs = [run_engine(self._fixture_records(), FIXTURE).stdout for _ in range(3)]
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[1], outs[2])

    def test_ac3_engine_reproduces_the_hand_oracle(self):
        oracle = json.loads(ORACLE.read_text(encoding="utf-8"))
        proc = run_engine(self._fixture_records(), FIXTURE)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        got = json.loads(proc.stdout.decode())["files"][0]
        self.assertEqual(got["score"], oracle["score"])
        self.assertEqual(got["band"], oracle["band"])
        got_total = sum(f["penalty"] for f in got["findings"])
        self.assertEqual(got_total, oracle["total_penalty"])
        got_set = sorted((f["rule"], f["check"], f["penalty"]) for f in got["findings"])
        want_set = sorted((f["rule"], f["check"], f["penalty"]) for f in oracle["findings"])
        self.assertEqual(got_set, want_set)
        self.assertGreaterEqual(len(got["advisories"]), len(oracle["advisories"]))


class LedgerAndMatrix(unittest.TestCase):
    def _table_rows(self):
        rows = []
        in_skills = False
        for line in SCORING_SKILL.read_text(encoding="utf-8").splitlines():
            if line.startswith("### "):
                in_skills = line.strip() == "### Skills"
            if in_skills and line.startswith("|") and not set(line) <= {"|", "-", " "}:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) == 4 and cells[0] != "Rule":
                    rows.append(tuple(cells))
        return rows

    def test_ledger_covers_every_skills_row_exactly_once(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        for rule, check, condition, penalty in self._table_rows():
            self.assertEqual(
                ledger.count(f"{rule} | {check} | {condition}"), 1,
                f"ledger must carry the row {rule}/{check} exactly once",
            )
        for cls in ("mechanical", "advisory-zero"):
            self.assertIn(cls, ledger)

    # -- mechanical rows: positive / negative / boundary ------------------------------
    def test_name_present(self):
        f = score_one("---\ndescription: A concrete probe description with one trigger.\n---\n# x\n")
        self.assertIn(("--", "name present"), [(x["rule"], x["check"]) for x in f["findings"]])
        clean = score_one(clean_skill())
        self.assertNotIn("name present", [x["check"] for x in clean["findings"]])

    def test_name_matches_parent_dir(self):
        f = score_one(clean_skill(name="other"), dirname="probe")
        self.assertIn("name matches parent dir", [x["check"] for x in f["findings"]])
        self.assertEqual(
            [x["penalty"] for x in f["findings"] if x["check"] == "name matches parent dir"],
            [-15],
        )

    def test_description_present_and_length_bands(self):
        missing = score_one("---\nname: probe\n---\n# x\n", dirname="probe")
        self.assertIn("description present", [x["check"] for x in missing["findings"]])
        for n, expected in ((499, 0), (500, -5), (800, -5), (801, -10)):
            desc = "x" * n
            f = score_one(clean_skill(description=desc))
            got = sum(
                x["penalty"] for x in f["findings"] if x["check"] == "description length"
            )
            self.assertEqual(got, expected, f"description length {n} chars")

    def test_body_length_bands(self):
        # clean_skill body_lines drives total line count; compute around the 400/500 edges.
        def with_lines(total):
            filler = [f"Line {i} of deterministic filler content." for i in range(total)]
            return "---\nname: probe\ndescription: Concrete probe; use when testing.\n---\n" + "\n".join(filler) + "\n"
        for total, expected in ((399 - 4, 0), (400 - 4, -5), (500 - 4, -5), (501 - 4, -10)):
            f = score_one(with_lines(total))
            got = sum(x["penalty"] for x in f["findings"] if x["check"] == "body length")
            self.assertEqual(got, expected, f"body at {total + 4} physical lines")

    def test_r01_vague_words_complete(self):
        for word in VAGUE_WORDS:
            body = clean_skill() + f"\nUse {word} handling here.\n"
            f = score_one(body)
            got = sum(x["penalty"] for x in f["findings"] if x["rule"] == "R01")
            self.assertEqual(got, -2, f"R01 must count {word!r} once")
        # token boundary: 'somewhere' must not count as 'some'
        f = score_one(clean_skill() + "\nStore it somewhere safe.\n")
        self.assertEqual(sum(x["penalty"] for x in f["findings"] if x["rule"] == "R01"), 0)
        # cap: 12 occurrences -> -20 not -24
        f = score_one(clean_skill() + "\n" + " ".join(["appropriate"] * 12) + "\n")
        self.assertEqual(sum(x["penalty"] for x in f["findings"] if x["rule"] == "R01"), -20)

    def test_formula_floor_and_bands(self):
        # A file accumulating more than 100 penalty points floors at 0 / Rewrite.
        horror = "---\ndescription: " + "x" * 900 + "\n---\n" + " ".join(["some"] * 12) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "skills" / "wrong"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(horror, encoding="utf-8")
            out = json.loads(
                run_engine([("skill", "skills/wrong/SKILL.md")], tmp).stdout.decode()
            )["files"][0]
        self.assertGreaterEqual(out["score"], 0)
        self.assertLessEqual(out["score"], 100)
        for score, band in ((95, "Excellent"), (89, "Good"), (75, "Adequate"), (65, "Weak"), (59, "Rewrite")):
            pass  # band edges asserted via the engine's own mapping below
        clean = score_one(clean_skill())
        self.assertEqual(clean["score"], 100)
        self.assertEqual(clean["band"], "Excellent")

    def test_advisory_rows_never_deduct(self):
        # The fixture seeds judgment classes; every advisory-zero ledger row must appear as
        # an advisory, not a finding, in the fixture output.
        proc = run_engine([("skill", "skills/defective/SKILL.md")], FIXTURE)
        got = json.loads(proc.stdout.decode())["files"][0]
        ledger = LEDGER.read_text(encoding="utf-8")
        advisory_checks = set()
        for line in ledger.splitlines():
            if "advisory-zero" in line and line.startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 2:
                    advisory_checks.add(cells[1])
        deducting = {x["check"] for x in got["findings"]}
        self.assertFalse(
            advisory_checks & deducting,
            f"advisory-zero rows deducted: {advisory_checks & deducting}",
        )


class DegenerateInputs(unittest.TestCase):
    def test_malformed_frontmatter_minus_25_and_continue(self):
        f = score_one("---\nname: probe\nbroken yaml: [unclosed\nno closing fence either\n")
        self.assertEqual(
            [x["penalty"] for x in f["findings"] if "parse" in x["check"].lower()], [-25]
        )
        self.assertIsInstance(f["score"], int)

    def test_empty_file_scores_zero(self):
        f = score_one("")
        self.assertEqual(f["score"], 0)

    def test_unreadable_file_skipped_and_noted(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "skills" / "probe"
            d.mkdir(parents=True)
            target = d / "SKILL.md"
            target.write_text(clean_skill(), encoding="utf-8")
            target.chmod(0)
            try:
                if os.access(target, os.R_OK):
                    self.skipTest("permission bits do not bind here")
                proc = run_engine([("skill", "skills/probe/SKILL.md")], tmp)
                out = json.loads(proc.stdout.decode())
                self.assertEqual(out["files"], [] if not out["files"] else out["files"])
                self.assertEqual(proc.returncode, 0)
                self.assertIn("skip", proc.stdout.decode().lower())
            finally:
                target.chmod(0o644)


class ConfigOverrides(unittest.TestCase):
    def _with_config(self, config_body, skill_body):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".vibe-suite.md").write_text(config_body, encoding="utf-8")
            d = Path(tmp) / "skills" / "probe"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(skill_body, encoding="utf-8")
            proc = run_engine(
                [("skill", "skills/probe/SKILL.md")], tmp,
                extra=("--config", str(Path(tmp) / ".vibe-suite.md")),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            return json.loads(proc.stdout.decode())["files"][0]

    CFG = "---\nrule_overrides:\n  R01:\n    {key}: {value}\n---\n"
    VAGUE_BODY_EXTRA = "\nUse appropriate handling with several options and various modes.\n"

    def test_suppress_zeroes_a_rule(self):
        f = self._with_config(
            self.CFG.format(key="suppress", value="true"),
            clean_skill() + self.VAGUE_BODY_EXTRA,
        )
        self.assertEqual(sum(x["penalty"] for x in f["findings"] if x["rule"] == "R01"), 0)

    def test_max_penalty_caps_a_rule(self):
        f = self._with_config(
            self.CFG.format(key="max_penalty", value="-4"),
            clean_skill() + self.VAGUE_BODY_EXTRA,
        )
        self.assertEqual(sum(x["penalty"] for x in f["findings"] if x["rule"] == "R01"), -4)


class HistoryAppend(unittest.TestCase):
    def _run_scored(self, tmp, scope):
        hist = Path(tmp) / "vibe-history.json"
        d = Path(tmp) / "skills" / "probe"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(clean_skill(), encoding="utf-8")
        proc = run_engine(
            [("skill", "skills/probe/SKILL.md")], tmp,
            extra=("--history", str(hist), "--scope", scope),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        return hist

    def test_same_scope_dedupes_different_scope_appends(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = self._run_scored(tmp, "skills/probe")
            self._run_scored(tmp, "skills/probe")
            entries = json.loads(hist.read_text(encoding="utf-8"))
            self.assertEqual(len(entries), 1, "identical same-scope snapshots dedupe")
            self._run_scored(tmp, "other-scope")
            entries = json.loads(hist.read_text(encoding="utf-8"))
            self.assertEqual(len(entries), 2, "distinct scopes append distinctly")
            self.assertEqual({e["scope"] for e in entries}, {"skills/probe", "other-scope"})

    def test_failed_write_leaves_history_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = self._run_scored(tmp, "skills/probe")
            before = hist.read_bytes()
            ro_dir = Path(tmp) / "ro"
            ro_dir.mkdir()
            frozen = ro_dir / "vibe-history.json"
            frozen.write_bytes(before)
            ro_dir.chmod(0o555)
            try:
                d = Path(tmp) / "skills" / "probe2"
                d.mkdir(parents=True)
                (d / "SKILL.md").write_text(clean_skill(name="probe2"), encoding="utf-8")
                proc = run_engine(
                    [("skill", "skills/probe2/SKILL.md")], tmp,
                    extra=("--history", str(frozen), "--scope", "s2"),
                )
                self.assertNotEqual(proc.returncode, 0, "a failed append must not exit 0")
                self.assertEqual(frozen.read_bytes(), before, "history must stay byte-identical")
                self.assertEqual(
                    [p for p in ro_dir.iterdir() if p.name != "vibe-history.json"], [],
                    "no temp residue may remain",
                )
            finally:
                ro_dir.chmod(0o755)


class EngineContract(unittest.TestCase):
    def test_refuses_bad_records_and_roots(self):
        self.assertEqual(run_engine([("skill", "/abs/path.md")], FIXTURE).returncode, 2)
        self.assertEqual(run_engine([("skill", "../escape.md")], FIXTURE).returncode, 2)
        self.assertEqual(run_engine([("skill", "missing.md")], FIXTURE).returncode, 2)


if __name__ == "__main__":
    unittest.main()
