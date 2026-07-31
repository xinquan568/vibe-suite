#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The `/vibe-suite:refine-proposal` port (E5.2 / vibe-41).

F6.1 ports the workspace `refine-proposal` skill. Three things change and the rest is carried: dispatch
moves to E1.1's runner, the pinned reviewer model goes away (D6/P9), and the command ships under
`/vibe-suite:`. **P6** is what governs the first two — a port fixes inherited defects rather than
carrying them across because they were there.

**What CI can and cannot reach here, stated before anything claims coverage.** The skill and command are
markdown, interpreted by a host session; no process in this repository reads them and runs the loop.
`VIBE_SUITE_CODEX_BIN` substitutes the *inner* codex executable — it does not execute a markdown skill —
so nothing calls the runner in CI, because the thing that would call it is prose. Three tiers:

- **Executable** — `scripts/render_final.py` is a real shell script and is driven as a subprocess here.
- **Contract** — what the markdown *states*: the nine cited fragments, the round-bounds block, the v6
  field set, flag domains, the degradation conditionals, no pinned ids.
- **Operator** — that a host session running the loop behaves as specified, and that a real reviewer
  finds the flaws seeded in the AC-3 fixture. Not here, and not claimed here.

The shared reviewer contract's own conformance registry (`tests/test_reviewer_contract.py`) grades this
directory the moment it exists — this is the first real subject that registry has ever had. It is not
duplicated here. What it does not reach is: it accepts **any one** valid citation, so passing it shows
the skill cites *something*. The nine fragments this loop relies on are asserted individually below.
"""

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
SKILL = REPO_ROOT / "skills" / "refine-proposal" / "SKILL.md"
RUBRIC = REPO_ROOT / "skills" / "refine-proposal" / "references" / "review-rubric.md"
COMMAND = REPO_ROOT / "commands" / "refine-proposal.md"
RENDERER = REPO_ROOT / "scripts" / "render_final.py"
CONTRACT = REPO_ROOT / "skills" / "vibe-core" / "references" / "reviewer-contract.md"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "refine-proposal" / "flawed-plan"

#: Every contract section this loop relies on. The registry is satisfied by one; relying on nine and
#: citing one would leave eight unstated dependencies that no check would ever report.
CITED_FRAGMENTS = (
    "reviewer-backends",
    "review-modes",
    "round-bounds",
    "verdict-parsing",
    "the-closure-machine",
    "same-model-refusal-and-self-review",
    "model-resolution",
    "provenance",
    "anti-sycophancy",
)

#: schema_version 6, exactly. A field with no behaviour records something the skill does not do; a
#: behaviour with no field is state that does not survive a resume.
V6_FIELDS = frozenset({
    "schema_version", "second_language", "review_translation", "translation_review",
    "reviewer", "carried_forward",
})

STOP_SEVERITIES = ("blocker", "major", "minor")
REVIEW_MODES = ("none", "single", "full")

MODEL_PIN = re.compile(
    r"\b(?:gpt-\d|o\d-|gemini-\d|claude-(?:opus|sonnet|haiku|fable)-\d|claude-[a-z]+-20\d{2})", re.I)


def norm(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


class TestArtifactsExist(unittest.TestCase):
    def test_the_four_artifacts_are_present(self):
        for path in (SKILL, RUBRIC, COMMAND, RENDERER):
            with self.subTest(artifact=path.name):
                self.assertTrue(path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing")

    def test_no_second_dispatch_path_survives_the_port(self):
        """P6: the source shells out through its own review script. E1.1's runner owns dispatch, and
        two dispatch paths would be two places for `exit 0 is not success` to be forgotten."""
        strays = sorted(p.relative_to(REPO_ROOT).as_posix()
                        for p in REPO_ROOT.rglob("codex_review.sh"))
        self.assertEqual(strays, [], f"a second dispatch path survived the port: {strays}")

    def test_the_renderer_is_executable_and_isc(self):
        self.assertTrue(os.access(RENDERER, os.X_OK), "the renderer must be executable")
        self.assertIn("SPDX-License-Identifier: ISC", RENDERER.read_text(encoding="utf-8"))

    def test_the_renderer_writes_through_the_audited_primitive(self):
        """P6, and a rule this repository already settled.

        The ported source rendered through a shell script that wrote with `> "$target"`. The shell
        allowlist in `tests/test_write_discipline.py` is deliberately **empty** — a redirection follows
        a destination symlink and an AST lint cannot see it — so carrying the shell version across
        would have re-opened a closed question.
        """
        text = RENDERER.read_text(encoding="utf-8")
        self.assertIn("bridge.write_atomic", text)
        self.assertIn("bridge.assert_root", text)
        self.assertFalse((REPO_ROOT / "scripts" / "render_final.sh").exists(),
                         "the shell renderer must not survive alongside the audited one")


class TestCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = COMMAND.read_text(encoding="utf-8")

    def test_frontmatter_has_description_and_argument_hint(self):
        block = self.text.split("---\n", 2)[1]
        self.assertRegex(block, r"(?m)^description:\s*\S")
        self.assertRegex(block, r"(?m)^argument-hint:\s*\S")

    def test_the_namespace_is_vibe_suite(self):
        self.assertIn("/vibe-suite:refine-proposal", self.text)
        for stale in ("/vibe:", "/cc-suite:", "/nlpm:", "/grill:"):
            with self.subTest(prefix=stale):
                self.assertNotIn(stale, self.text)

    def test_the_command_points_at_the_skill(self):
        self.assertIn("skills/refine-proposal", self.text)


class TestContractCitations(unittest.TestCase):
    """The nine fragments, individually. The registry's floor is one."""

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.headings = {
            re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-")
            for h in re.findall(r"(?m)^#{1,6}[ ]+(.+?)[ ]*$", CONTRACT.read_text(encoding="utf-8"))
        }

    def test_every_relied_on_fragment_is_cited(self):
        for fragment in CITED_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertIn(f"reviewer-contract.md#{fragment}", self.text,
                              f"the skill relies on '{fragment}' and must cite it")

    def test_every_cited_fragment_names_a_real_heading(self):
        """A citation pointing at a heading that does not exist is a citation of nothing."""
        for fragment in re.findall(r"reviewer-contract\.md#([\w-]+)", self.text):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.headings,
                              f"'{fragment}' is not a heading in the reviewer contract")


class TestSkillContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.norm = norm(cls.text)

    def test_the_state_schema_is_exactly_v6(self):
        """Parsed, not grepped.

        Counting key *names* anywhere in the blob passed a `schema_version` of 7, accepted arbitrary
        extra fields, and could not tell a top-level key from one nested inside a round. The example is
        real JSON, so it is loaded and compared level by level.
        """
        block = re.search(r"(?s)```json\s*(\{.*?\})\s*```", self.text)
        self.assertIsNotNone(block, "the skill must show its state shape as a JSON block")
        state = json.loads(block.group(1))

        self.assertEqual(state.get("schema_version"), 6,
                         "the port carries schema_version 6; a bump needs a migration, not an edit")
        self.assertEqual(set(state) & V6_FIELDS, V6_FIELDS - {"reviewer"},
                         f"top level is missing {sorted(V6_FIELDS - {'reviewer'} - set(state))}")

        self.assertIsInstance(state.get("rounds"), list)
        self.assertTrue(state["rounds"], "the example must show at least one round")
        self.assertIn("reviewer", state["rounds"][0],
                      "`reviewer` is per round: one run can mix a dispatched critic with a "
                      "self-reviewed round, and a summary reporting only one would misdescribe it")

        self.assertIsInstance(state.get("carried_forward"), list)
        self.assertIsInstance(state.get("translation_review"), dict)
        self.assertIn("reviewer", state["translation_review"])

    def test_stop_severity_domain_and_default(self):
        self.assertIn("--stop-severity", self.text)
        for value in STOP_SEVERITIES:
            with self.subTest(value=value):
                self.assertIn(value, self.norm)
        self.assertRegex(self.norm, r"--stop-severity[^.]{0,160}default[^.]{0,20}major")

    def test_stop_severity_gates_on_open_findings(self):
        """It is an early-stop over *open* findings, not a restatement of the closure machine."""
        self.assertRegex(self.norm, r"open[^.]{0,60}(at or above|>=|severity)")

    def test_review_mode_values_are_stated(self):
        for mode in REVIEW_MODES:
            with self.subTest(mode=mode):
                self.assertIn(mode, self.norm)

    def test_english_is_always_first_in_the_bilingual_output(self):
        self.assertIn("--second-language", self.text)
        self.assertRegex(self.norm, r"english[^.]{0,24}first")
        self.assertIn("final-bilingual.md", self.text)

    def test_translation_review_degradation_is_a_conditional(self):
        """Both branches. With the flag, self-review; without it, a recorded skip — and neither
        aborts finalize, or an optional feature becomes load-bearing."""
        self.assertRegex(self.norm, r"--allow-self-review")
        self.assertIn("recorded skip", self.norm)
        self.assertRegex(self.norm, r"never abort|does not abort|without aborting")

    def test_a_self_reviewed_round_is_marked(self):
        """An unmarked self-review produces a run that looks reviewed and is not."""
        self.assertIn('reviewer: "self"', self.text)
        self.assertRegex(self.norm, r"no usage|usage null|absent usage")

    def test_dispatch_goes_through_the_runner(self):
        self.assertIn("scripts/codex-runner.mjs", self.text)

    def test_the_artifact_contract_is_unchanged(self):
        for artifact in ("review.md", "review.json"):
            with self.subTest(artifact=artifact):
                self.assertIn(artifact, self.text)


class TestNoPinnedModel(unittest.TestCase):
    def test_no_artifact_names_a_model_id(self):
        for path in (SKILL, RUBRIC, COMMAND, RENDERER):
            with self.subTest(artifact=path.name):
                hits = [l for l in path.read_text(encoding="utf-8").splitlines()
                        if MODEL_PIN.search(l) and "never" not in l.lower()]
                self.assertEqual(hits, [], f"P9/D6: pinned model id in {path.name}: {hits}")


class TestRenderer(unittest.TestCase):
    """The one deliverable CI can actually execute.

    Driven as a subprocess with `pandoc` present and absent. The absent case is the one that matters:
    finalize must degrade to a markdown pointer with a warning, not fail.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        # `.resolve()` matters: on macOS `/var` is a symlink to `/private/var`, and the containment
        # check compares real paths. An unresolved root fails as an escape attempt.
        self.ws = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)
        self.bin = self.ws / "bin"
        self.bin.mkdir()

    def write(self, name, body):
        path = self.ws / name
        path.write_text(body, encoding="utf-8")
        return path

    def fake_pandoc(self):
        """A pandoc stand-in reached through `VIBE_SUITE_PANDOC_BIN`.

        Emptying `PATH` to simulate an absent pandoc also removes `bash`, so the script would fail for
        the wrong reason. The binary-override seam is how `codex-runner.mjs` solves the same problem.
        """
        script = self.bin / "pandoc"
        # Emits on stdout, because the renderer pipes: it writes nothing itself, so a fake that only
        # wrote to `-o` would leave the renderer with an empty result and no way to say why.
        script.write_text(
            "#!/bin/sh\n"
            "cat > /dev/null\n"
            'printf "<!doctype html><html><body>rendered</body></html>"\n',
            encoding="utf-8")
        script.chmod(0o755)
        return str(script)

    def run_renderer(self, *args, pandoc=None):
        env = dict(os.environ)
        # absent by default: a path that does not exist, so the lookup fails cleanly
        env["VIBE_SUITE_PANDOC_BIN"] = pandoc or str(self.ws / "no-such-pandoc")
        return subprocess.run([sys.executable, str(RENDERER), "--root", str(self.ws), *args],
                              cwd=self.ws, env=env, capture_output=True, text=True, timeout=60)

    def test_pandoc_present_produces_a_self_contained_document(self):
        source = self.write("final.md", "# Plan\n\nbody\n")
        result = self.run_renderer(str(source), pandoc=self.fake_pandoc())
        self.assertEqual(result.returncode, 0, result.stderr)
        html = self.ws / "FINAL.html"
        self.assertTrue(html.exists(), f"no FINAL.html; stdout={result.stdout} stderr={result.stderr}")
        body = html.read_text(encoding="utf-8")
        self.assertNotRegex(body, r'(?:src|href)="https?://',
                            "a self-contained render must reference no external host")

    def test_pandoc_absent_degrades_to_a_markdown_pointer(self):
        """The documented fallback. Finalize degrades; it does not fail."""
        source = self.write("final.md", "# Plan\n\nbody\n")
        result = self.run_renderer(str(source))          # no pandoc
        self.assertEqual(result.returncode, 0,
                         "an absent pandoc must not fail the render: " + result.stderr)
        self.assertRegex((result.stdout + result.stderr).lower(), r"warn|pandoc")
        # Existence is not the assertion. On a case-insensitive filesystem `FINAL.md` resolves to the
        # source `final.md`, so `.exists()` is true whether or not the fallback ever wrote anything —
        # a mutation removing the write passed this test until the marker was asserted instead.
        pointer = (self.ws / "FINAL.md").read_text(encoding="utf-8")
        self.assertIn("pandoc unavailable", pointer,
                      "the markdown pointer must actually be written, not merely resolve to the source")

    def test_a_case_colliding_source_name_does_not_self_destruct(self):
        """`final.md` and `FINAL.md` are the same file on a case-insensitive filesystem.

        Writing the fallback straight to the target while `cat`-ing the source truncated the source
        mid-read and looped until the process was killed. The staging file is what makes the collision
        harmless, and this is the regression that found it.
        """
        source = self.write("final.md", "# Plan\n\nalpha beta\n")
        result = self.run_renderer(str(source))          # no pandoc -> the fallback path
        self.assertEqual(result.returncode, 0, result.stderr)
        pointer = (self.ws / "FINAL.md").read_text(encoding="utf-8")
        self.assertIn("pandoc unavailable", pointer,
                      "the pointer must be the written fallback, not the source seen through a "
                      "case-insensitive lookup")
        self.assertIn("alpha beta", pointer, "the source content must survive the fallback")
        self.assertLess(len(pointer), 4096, "the fallback must not have written into itself")

    def test_the_metadata_banner_carries_counts(self):
        source = self.write("final.md", "# Plan\n\nalpha beta gamma delta\n")
        result = self.run_renderer(str(source), pandoc=self.fake_pandoc())
        self.assertEqual(result.returncode, 0, result.stderr)
        banner = (self.ws / "FINAL.html").read_text(encoding="utf-8") + result.stdout
        self.assertRegex(banner.lower(), r"\bword", "the banner must report a word count")

    def test_bilingual_source_is_preferred_when_present(self):
        """The branch a bilingual run depends on, and it is pure file logic."""
        self.write("final.md", "# English only\n")
        bilingual = self.write("final-bilingual.md", "# English\n\n# Translation\n")
        result = self.run_renderer(str(bilingual), pandoc=self.fake_pandoc())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.ws / "FINAL.html").exists())


class TestAcceptanceFixture(unittest.TestCase):
    """The AC-3 fixture is a **specification** fixture, bound to the plan it describes.

    CI checks it is well-formed, that each row points at real text at the line it names, and that every
    category is one the rubric can express. CI does **not** check that a review finds the flaws — that
    needs the loop to run, and the ≥2-of-3 clause is a reviewer's judgement. It is an operator check,
    with this fixture as the thing the operator runs against.

    The previous version of this class never opened `plan.md`: replacing the plan with flawless prose
    left every test green, and two of the three line numbers were wrong. A specification fixture that
    is not bound to its subject specifies nothing.
    """

    @classmethod
    def setUpClass(cls):
        cls.plan_lines = (FIXTURE / "plan.md").read_text(encoding="utf-8").splitlines()
        expected = (FIXTURE / "expected-findings.md").read_text(encoding="utf-8")
        cls.rows = []
        for row in re.findall(r"(?m)^\|\s*(F\d+)\s*\|(.+)$", expected):
            cells = [c.strip() for c in row[1].split("|")]
            cls.rows.append({"id": row[0], "category": cells[0], "severity": cells[1],
                             "line": cells[2], "anchor": cells[3].strip("`")})

    def test_the_fixture_exists_with_a_plan_and_its_expected_findings(self):
        self.assertTrue((FIXTURE / "plan.md").is_file(), "the flawed plan is missing")
        self.assertTrue((FIXTURE / "expected-findings.md").is_file(),
                        "the expected findings are missing; without them the fixture asserts nothing")

    def test_three_flaws_are_seeded_with_distinct_ids(self):
        ids = [r["id"] for r in self.rows]
        self.assertEqual(len(ids), 3, f"AC-3 seeds three flaws; found {ids}")
        self.assertEqual(len(set(ids)), 3, "finding ids must be distinct")

    def test_each_row_points_at_real_text_at_the_line_it_names(self):
        """This is the binding. Rewrite the plan and these fail, which is the whole point."""
        for row in self.rows:
            with self.subTest(finding=row["id"]):
                self.assertRegex(row["line"], r"^\d+$", "the line cell must be a line number")
                index = int(row["line"]) - 1
                self.assertLess(index, len(self.plan_lines),
                                f"{row['id']} names line {row['line']}, past the end of plan.md")
                self.assertIn(row["anchor"], self.plan_lines[index],
                              f"{row['id']}: plan.md line {row['line']} does not contain its anchor")

    def test_each_row_names_a_severity_from_the_scale(self):
        for row in self.rows:
            with self.subTest(finding=row["id"]):
                self.assertIn(row["severity"], ("blocker", "major", "minor"))

    def test_the_seeded_flaws_fall_within_the_rubric(self):
        """A seeded flaw the rubric cannot express would be unfindable by construction."""
        rubric = norm(RUBRIC.read_text(encoding="utf-8"))
        for row in self.rows:
            with self.subTest(category=row["category"]):
                self.assertIn(row["category"].lower(), rubric,
                              f"'{row['category']}' is not a rubric dimension, so no review could "
                              f"raise it")

    def test_the_three_flaws_are_three_different_failure_classes(self):
        """A fixture whose flaws are all one kind tests one thing three times."""
        categories = {r["category"] for r in self.rows}
        self.assertEqual(len(categories), 3, f"expected three distinct categories, got {categories}")


if __name__ == "__main__":
    unittest.main()
