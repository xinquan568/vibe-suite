# SPDX-License-Identifier: ISC
"""E3.3 (vibe-28) acceptance: /vibe-suite:score — the deterministic claude lane.

The engine (scripts/score_engine.py) is the ONLY penalty authority; agents narrate. The
oracle (tests/fixtures/nl-audit/defective-skill/expected.json + its worksheet README) was
computed BY HAND from the scoring skill's tables before the engine existed — the engine must
reproduce it, never the reverse. AC-3 is an EXACT whole-object comparison: expected.json is
the engine's files[0] object verbatim, advisories included.

Engine CLI contract pinned here:
  stdin  : records `<type-or-category>\\x1f<relative-path>\\x00` (same lossless framing as
           ls_counts); a first field of `A`-`F` is a scanner discovery category and the
           engine classifies the path itself, agreeing with commands/shared/classify.md
  args   : --root <dir> [--config <file>] [--history <file>] [--scope <tag>]
  stdout : JSON {"files":[{"path","score","band","verdict",
           "findings":[{"rule","check","line","penalty"}],"advisories":[{"rule","note"}]}],
           "run":{"files","total_penalty","considered_rows","skipped"}}
  exit   : 0 scored; 2 contract refusal (bad record, bad root); a missing --config file is
           NOT a refusal — defaults apply

Row ledger: scripts/score_engine_rows.md classifies every row of EVERY penalty table in the
scoring skill as `mechanical` (predicate quoted from the owning text) or `advisory-zero`;
this suite asserts the ledger carries every row of every table and that the engine deducts
ONLY on mechanical rows.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
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


def load_engine():
    """Import the engine in-process (for the classifier and the injected history failure)."""
    spec = importlib.util.spec_from_file_location("vibe_score_engine", ENGINE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score_one(body, extra=(), name="probe", dirname=None, record_type="skill"):
    """Score a synthetic one-file tree; returns the engine's file object."""
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / "skills" / (dirname or name)
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
        rel = f"skills/{dirname or name}/SKILL.md"
        proc = run_engine([(record_type, rel)], tmp, extra)
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


def skill_with_body(body_lines, name="probe", description="Concrete probe; use when testing."):
    """A skill whose MARKDOWN BODY (frontmatter excluded) is exactly `body_lines` lines."""
    head = ["---", f"name: {name}", f"description: {description}", "---"]
    body = [f"Body line {i} of deterministic filler content." for i in range(body_lines)]
    return "\n".join(head + body) + "\n"


def agent_md(model=True, tools=True, examples=2, output_heading=True):
    lines = ["---", "name: helper",
             "description: Scores helper agents; use when testing the agents table."]
    if model:
        lines.append("model: haiku")
    if tools:
        lines.append("tools: Read")
    lines += ["---", "", "# helper", ""]
    if output_heading:
        lines += ["## Output format", "", "One line per file.", ""]
    for _ in range(examples):
        lines += ["<example>", "Context: probe.", "user: go?", "assistant: going.", "</example>"]
    return "\n".join(lines) + "\n"


def r01_total(entry):
    return sum(x["penalty"] for x in entry["findings"] if x["rule"] == "R01")


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

    def test_scorer_invocation_is_record_framed_stdin(self):
        # The engine takes no positional targets; the scorer's example must show the
        # record protocol, or the agent would invoke a contract that exits 2.
        body = SCORER.read_text(encoding="utf-8")
        self.assertIn('< "<record-file>"', body)
        self.assertNotIn("<targets", body, "positional targets are not part of the contract")
        self.assertIn("\\x1f", body)
        self.assertIn("\\x00", body)

    def test_command_config_is_conditional(self):
        # A project without the optional .vibe-suite.md is scored with defaults, never
        # refused — so the invocation note must not pass --config unconditionally.
        body = COMMAND.read_text(encoding="utf-8")
        self.assertIn("only when that file exists", body)
        self.assertNotIn('--config "<target>/.vibe-suite.md" --history', body)

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
        procs = [run_engine(self._fixture_records(), FIXTURE) for _ in range(3)]
        for proc in procs:
            # A missing or crashing engine produces identical EMPTY stdout three times;
            # the equality below is meaningful only after each run demonstrably scored.
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        outs = [proc.stdout for proc in procs]
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[1], outs[2])

    def test_ac3_engine_reproduces_the_hand_oracle_exactly(self):
        oracle = json.loads(ORACLE.read_text(encoding="utf-8"))
        proc = run_engine(self._fixture_records(), FIXTURE)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        got = json.loads(proc.stdout.decode())["files"][0]
        # Exact whole-object equality — every field, findings AND the advisories list.
        self.assertEqual(got, oracle)
        # The worksheet arithmetic, restated independently of the JSON shapes.
        self.assertEqual(sum(f["penalty"] for f in got["findings"]), -55)
        self.assertEqual(got["score"], 45)
        self.assertEqual(got["band"], "Rewrite")
        self.assertEqual(got["verdict"], "fail")


class LedgerAndMatrix(unittest.TestCase):
    #: Recognized penalty-table headers and how their cells map onto (rule, check, condition).
    HEADERS = {
        ("Rule", "Check", "Condition", "Penalty"): lambda c: (c[0], c[1], c[2]),
        ("Check", "Condition", "Penalty"): lambda c: ("--", c[0], c[1]),
        ("Rule", "Check", "Penalty on fail"): lambda c: (c[0], c[1], ""),
    }

    def _all_penalty_rows(self):
        """Every row of every penalty table in the scoring skill, as (rule, check, condition).

        Parses ALL tables between `## Penalty Tables` and `## Score Bands`. Fails closed: an
        unrecognized table header raises rather than silently skipping a table, and a floor
        on the row count guards against a parse that quietly finds nothing.
        """
        text = SCORING_SKILL.read_text(encoding="utf-8")
        section = text[text.index("## Penalty Tables"):text.index("## Score Bands")]
        rows, header = [], None
        for line in section.splitlines():
            if line.startswith("### "):
                header = None
                continue
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if header is None:
                header = tuple(cells)
                if header not in self.HEADERS:
                    raise AssertionError(f"unrecognized penalty-table header {header}")
                continue
            rows.append(self.HEADERS[header](cells))
        self.assertGreaterEqual(len(rows), 100, "the table parse found too few rows to be real")
        return rows

    def test_ledger_covers_every_row_of_every_table(self):
        rows = self._all_penalty_rows()
        ledger = LEDGER.read_text(encoding="utf-8")
        for (rule, check, condition), multiplicity in Counter(rows).items():
            needle = f"{rule} | {check} | {condition} |" if condition else f"{rule} | {check} |"
            with self.subTest(rule=rule, check=check):
                self.assertEqual(
                    ledger.count(needle), multiplicity,
                    f"ledger must carry {needle!r} exactly {multiplicity} time(s)",
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

    def test_body_length_bands_counted_in_body_lines(self):
        # R05's domain is the MARKDOWN BODY: the frontmatter block (fences included) is
        # excluded. skill_with_body() builds a body of exactly N lines behind a 4-line
        # frontmatter block, so the boundaries below are stated directly in body lines.
        for body_lines, expected in ((399, 0), (400, -5), (500, -5), (501, -10)):
            f = score_one(skill_with_body(body_lines))
            got = sum(x["penalty"] for x in f["findings"] if x["check"] == "body length")
            self.assertEqual(got, expected, f"body of {body_lines} lines")

    def test_body_threshold_override_moves_only_the_upper_boundary(self):
        # conventions §6: R05 `threshold: 600` (from 500 lines) — the upper boundary moves
        # to 600 (-10 above it, -5 in 400..600); the 400 lower boundary stays.
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".vibe-suite.md"
            config.write_text(
                "---\nrule_overrides:\n  R05:\n    threshold: 600\n---\n", encoding="utf-8")
            for body_lines, expected in ((399, 0), (400, -5), (550, -5), (600, -5), (601, -10)):
                d = Path(tmp) / "skills" / "probe"
                d.mkdir(parents=True, exist_ok=True)
                (d / "SKILL.md").write_text(skill_with_body(body_lines), encoding="utf-8")
                proc = run_engine([("skill", "skills/probe/SKILL.md")], tmp,
                                  extra=("--config", str(config)))
                self.assertEqual(proc.returncode, 0, proc.stderr.decode())
                f = json.loads(proc.stdout.decode())["files"][0]
                got = sum(x["penalty"] for x in f["findings"] if x["check"] == "body length")
                self.assertEqual(got, expected, f"body of {body_lines} lines at threshold 600")

    def test_r01_vague_words_complete(self):
        for word in VAGUE_WORDS:
            body = clean_skill() + f"\nUse {word} handling here.\n"
            f = score_one(body)
            self.assertEqual(r01_total(f), -2, f"R01 must count {word!r} once")
        # token boundary: 'somewhere' must not count as 'some'
        f = score_one(clean_skill() + "\nStore it somewhere safe.\n")
        self.assertEqual(r01_total(f), 0)
        # repeats on one line each count
        f = score_one(clean_skill() + "\nDrop some rows, then some more, then some again.\n")
        self.assertEqual(r01_total(f), -6)
        # cap: 12 occurrences -> -20 not -24
        f = score_one(clean_skill() + "\n" + " ".join(["appropriate"] * 12) + "\n")
        self.assertEqual(r01_total(f), -20)

    def test_r01_carveout_relevant_in_heading(self):
        f = score_one(clean_skill() + "\n## Relevant commands\n\nNone yet.\n")
        self.assertEqual(r01_total(f), 0, "'relevant' inside a markdown header is exempt")
        # the header carve-out is for `relevant` ONLY — no new contextual rules
        f = score_one(clean_skill() + "\n## Appropriate use\n\nNone yet.\n")
        self.assertEqual(r01_total(f), -2, "other terms in a heading still count")

    def test_r01_carveout_relevant_to_named_scope(self):
        f = score_one(clean_skill() + "\nThis applies when relevant to skills/scoring.\n")
        self.assertEqual(r01_total(f), 0, "'relevant to <named-scope>' is exempt")
        f = score_one(clean_skill() + "\nCollect the relevant columns.\n")
        self.assertEqual(r01_total(f), -2, "bare 'relevant' still counts")

    def test_r01_carveout_measurable_criterion(self):
        f = score_one(clean_skill() + "\nAllocate sufficient memory for the batch (512 MB).\n")
        self.assertEqual(r01_total(f), 0, "a term followed by a measurable criterion is exempt")
        f = score_one(clean_skill() + "\nRetry a reasonable number of times: at most 3.\n")
        self.assertEqual(r01_total(f), 0)
        f = score_one(clean_skill() + "\nAllocate sufficient memory for the batch.\n")
        self.assertEqual(r01_total(f), -2, "no criterion, no exemption")
        # the criterion clause must follow the term — a number on the NEXT line is not one
        f = score_one(clean_skill() + "\nUse adequate padding.\nSet width to 3.\n")
        self.assertEqual(r01_total(f), -2)

    def test_r01_cap_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".vibe-suite.md"
            config.write_text(
                "---\nrule_overrides:\n  R01:\n    threshold: 10\n---\n", encoding="utf-8")
            d = Path(tmp) / "skills" / "probe"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                clean_skill() + "\n" + " ".join(["appropriate"] * 12) + "\n", encoding="utf-8")
            proc = run_engine([("skill", "skills/probe/SKILL.md")], tmp,
                              extra=("--config", str(config)))
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            f = json.loads(proc.stdout.decode())["files"][0]
            self.assertEqual(r01_total(f), -10, "R01 threshold overrides the -20 cap")

    def test_r06_example_blocks_on_user_invocable(self):
        head = ("---\nname: probe\ndescription: Concrete probe; use when testing blocks.\n"
                "user_invocable: true\n---\n# probe\nBody.\n")
        f = score_one(head)
        self.assertEqual(
            [x["penalty"] for x in f["findings"] if x["check"] == "example blocks"], [-10])
        f = score_one(head + "<example>\nContext: p.\nuser: p?\nassistant: p.\n</example>\n")
        self.assertEqual(
            [x for x in f["findings"] if x["check"] == "example blocks"], [])
        # without user_invocable: true the row cannot fire (worksheet #5)
        f = score_one(clean_skill(examples=0))
        self.assertEqual(
            [x for x in f["findings"] if x["check"] == "example blocks"], [])

    def test_band_edges_via_known_deduction_combos(self):
        cases = (
            (clean_skill(description="x" * 500), 95, "Excellent"),   # R04 length -5
            (clean_skill(name="other"), 85, "Good"),                 # name mismatch -15
            ("---\ndescription: Concrete probe; use when testing.\n---\n# x\nBody.\n",
             75, "Adequate"),                                        # name missing -25
            (skill_with_body(501).replace("name: probe\n", ""), 65, "Weak"),
            # name missing -25 + R05 -10
            ("---\ndescription: Concrete probe; use when testing.\n---\n# x\n"
             + "\n".join(["Drop some rows now."] * 10) + "\n", 55, "Rewrite"),
            # name missing -25 + 10 x R01 -2 = -45
        )
        for body, want_score, want_band in cases:
            with self.subTest(score=want_score):
                f = score_one(body, dirname="probe", name="other")
                self.assertEqual(f["score"], want_score)
                self.assertEqual(f["band"], want_band)
        clean = score_one(clean_skill())
        self.assertEqual(clean["score"], 100)
        self.assertEqual(clean["band"], "Excellent")
        self.assertEqual(clean["verdict"], "pass")

    def test_floor_binds_below_minus_100(self):
        # A settings file with nine invalid hook events (-10 per invalid = -90) plus twelve
        # R01 words (capped -20) accumulates -110; the formula floors the score at 0.
        hooks = {f"bogus{letter}": [] for letter in "ABCDEFGHI"}
        body = json.dumps(
            {"hooks": hooks, "note": " ".join(["appropriate"] * 12)}, indent=2)
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / ".claude"
            d.mkdir()
            (d / "settings.json").write_text(body, encoding="utf-8")
            proc = run_engine([("B", ".claude/settings.json")], tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            f = json.loads(proc.stdout.decode())["files"][0]
        self.assertEqual(sum(x["penalty"] for x in f["findings"]), -110)
        self.assertEqual(f["score"], 0)
        self.assertEqual(f["band"], "Rewrite")
        self.assertEqual(f["verdict"], "fail")

    def test_advisory_rows_never_deduct(self):
        # The fixture seeds judgment classes; no advisory-zero ledger row may appear as a
        # deducting finding in the fixture output.
        proc = run_engine([("skill", "skills/defective/SKILL.md")], FIXTURE)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        got = json.loads(proc.stdout.decode())["files"][0]
        ledger = LEDGER.read_text(encoding="utf-8")
        # Check names repeat across tables (an unrouted table's `name present` is
        # advisory-zero while the Skills row is mechanical), so the advisory set is
        # collected ONLY from the sections routed to the fixture's type: skill.
        advisory_checks = set()
        section = None
        for line in ledger.splitlines():
            if line.startswith("## "):
                section = line[3:].strip()
                continue
            if section not in ("Skills", "All types: vague quantifiers",
                               "Worksheet defect classes with no penalty-table row"):
                continue
            if "advisory-zero" in line and line.startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 2:
                    advisory_checks.add(cells[1])
        self.assertGreaterEqual(len(advisory_checks), 8, "the ledger sections must parse")
        deducting = {x["check"] for x in got["findings"]}
        self.assertFalse(
            advisory_checks & deducting,
            f"advisory-zero rows deducted: {advisory_checks & deducting}",
        )
        # R07 in particular moved to advisory-zero: it must appear as an advisory, never
        # as a finding.
        self.assertNotIn("R07", [x["rule"] for x in got["findings"]])
        self.assertIn("R07", [a["rule"] for a in got["advisories"]])


class MultiTypeScoring(unittest.TestCase):
    """The type interface end-to-end: category records over a two-type mini-tree."""

    def test_two_type_tree_scored_in_one_run_via_category_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "demo"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(clean_skill(name="demo"), encoding="utf-8")
            agent_dir = Path(tmp) / "agents"
            agent_dir.mkdir()
            (agent_dir / "helper.md").write_text(
                agent_md(model=False, examples=1), encoding="utf-8")
            proc = run_engine(
                [("A", "skills/demo/SKILL.md"), ("A", "agents/helper.md")], tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            out = json.loads(proc.stdout.decode())
        self.assertEqual([f["path"] for f in out["files"]],
                         ["skills/demo/SKILL.md", "agents/helper.md"])
        skill, agent = out["files"]
        # The skill scored on the Skills table: clean, and it carries the skill advisories.
        self.assertEqual(skill["score"], 100)
        self.assertEqual(skill["findings"], [])
        self.assertIn("R07", [a["rule"] for a in skill["advisories"]])
        # The agent scored on the Agents table: R10 model declared -5, R09 one example -5.
        self.assertEqual(
            [(x["rule"], x["check"], x["penalty"]) for x in agent["findings"]],
            [("R10", "model declared", -5), ("R09", "example blocks", -5)],
        )
        self.assertEqual(agent["score"], 90)
        self.assertEqual({a["rule"] for a in agent["advisories"]}, {"R10", "R11"})
        # Row accounting: 12+2 skill rows plus 9+2 agent rows.
        self.assertEqual(out["run"]["considered_rows"], 25)

    def test_agent_table_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = Path(tmp) / "agents"
            agent_dir.mkdir()
            cases = (
                (agent_md(), []),
                (agent_md(examples=0), [("R09", "example blocks", -15)]),
                (agent_md(tools=False), [("R11", "tools declared", -5)]),
                (agent_md(output_heading=False), [("R12", "output format", -10)]),
            )
            for body, want in cases:
                (agent_dir / "helper.md").write_text(body, encoding="utf-8")
                proc = run_engine([("agent", "agents/helper.md")], tmp)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode())
                got = json.loads(proc.stdout.decode())["files"][0]
                self.assertEqual(
                    [(x["rule"], x["check"], x["penalty"]) for x in got["findings"]], want)

    def test_untabled_type_takes_only_the_generic_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            docs.mkdir()
            (docs / "notes.md").write_text("# Notes\n\nDrop some rows.\n", encoding="utf-8")
            proc = run_engine([("E", "docs/notes.md")], tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            out = json.loads(proc.stdout.decode())
        f = out["files"][0]
        self.assertEqual([(x["rule"], x["penalty"]) for x in f["findings"]], [("R01", -2)])
        self.assertEqual(f["advisories"], [])
        self.assertEqual(out["run"]["considered_rows"], 2)


class ClassifierAgreement(unittest.TestCase):
    """The engine's path classifier must agree with commands/shared/classify.md."""

    def test_engine_classifier_matches_the_partial(self):
        from tests.test_shared_partials import EXPECTED, classify, parse_classify_rules
        engine = load_engine()
        rules = parse_classify_rules()
        corpus = list(EXPECTED) + [
            "commands/score.md", "commands/shared/discover.md", "docs/schema.json",
            "templates/plain.md", "other/skills/demo/SKILL.md",
            "skills/s/references/ref.md", "random/thing.txt", ".claude-plugin/plugin.json",
            "home/.claude/projects/p/memory/note.md", "./agents/a.md",
        ]
        for path in corpus:
            with self.subTest(path=path):
                self.assertEqual(engine.classify_path(path), classify(path, rules))

    def test_category_records_classify_types_and_explicit_types_pass_through(self):
        engine = load_engine()
        self.assertEqual(engine.resolve_type("A", "skills/x/SKILL.md"), "skill")
        self.assertEqual(engine.resolve_type("A", "agents/a.md"), "agent")
        self.assertEqual(engine.resolve_type("B", ".claude/settings.json"), "settings")
        self.assertEqual(engine.resolve_type("skill", "anything.md"), "skill")
        self.assertEqual(engine.resolve_type("agent", "anything.md"), "agent")


class DegenerateInputs(unittest.TestCase):
    def test_malformed_frontmatter_minus_25_and_continue(self):
        f = score_one("---\nname: probe\nbroken yaml: [unclosed\nno closing fence either\n")
        self.assertEqual(
            [x["penalty"] for x in f["findings"] if "parse" in x["check"].lower()], [-25]
        )
        self.assertIsInstance(f["score"], int)

    def test_valid_hyphenated_frontmatter_keys_are_not_penalized(self):
        # `allowed-tools` is part of the documented SKILL.md schema; a conforming skill
        # must not take the malformed-frontmatter -25 (review finding 5).
        body = ("---\nname: probe\ndescription: Concrete probe; use when testing keys.\n"
                "allowed-tools: Bash(git:*), Read\n---\n# probe\n\nBody.\n")
        f = score_one(body)
        self.assertEqual([x for x in f["findings"] if "parse" in x["check"].lower()], [])
        self.assertEqual(f["score"], 100)

    def test_truly_broken_yaml_still_minus_25(self):
        body = "---\nname: [probe\n---\n# probe\nBody.\n"
        f = score_one(body)
        self.assertEqual(
            [x["penalty"] for x in f["findings"] if "parse" in x["check"].lower()], [-25])

    def test_empty_file_scores_zero(self):
        f = score_one("")
        self.assertEqual(f["score"], 0)
        self.assertEqual(f["band"], "Rewrite")
        self.assertEqual(f["verdict"], "fail")

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
                self.assertEqual(proc.returncode, 0)
                out = json.loads(proc.stdout.decode())
                self.assertEqual(out["files"], [], "an unreadable file must not be scored")
                self.assertEqual(out["run"]["skipped"], ["skills/probe/SKILL.md"])
                self.assertEqual(len(out["run"]["skipped"]), 1)
                self.assertEqual(out["run"]["files"], 0)
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
        self.assertEqual(r01_total(f), 0)

    def test_enabled_false_zeroes_a_rule(self):
        f = self._with_config(
            self.CFG.format(key="enabled", value="false"),
            clean_skill() + self.VAGUE_BODY_EXTRA,
        )
        self.assertEqual(r01_total(f), 0)
        self.assertTrue(
            any(a["rule"] == "R01" and "zeroed" in a["note"] for a in f["advisories"]),
            "a zeroed rule surfaces as an advisory, not silently",
        )

    def test_max_penalty_caps_a_rule(self):
        f = self._with_config(
            self.CFG.format(key="max_penalty", value="-4"),
            clean_skill() + self.VAGUE_BODY_EXTRA,
        )
        self.assertEqual(r01_total(f), -4)

    def test_score_threshold_drives_the_verdict_not_the_bands(self):
        # 75 (name missing -25) fails an 80 threshold and passes the default 70; the band
        # stays Adequate either way — bands are fixed, only the verdict moves.
        body = "---\ndescription: Concrete probe; use when testing.\n---\n# x\nBody.\n"
        f = self._with_config("---\nscore_threshold: 80\n---\n", body)
        self.assertEqual((f["score"], f["band"], f["verdict"]), (75, "Adequate", "fail"))
        f = self._with_config("---\nscore_threshold: 70\n---\n", body)
        self.assertEqual((f["score"], f["band"], f["verdict"]), (75, "Adequate", "pass"))

    def test_missing_config_file_means_defaults_not_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "skills" / "probe"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(clean_skill(), encoding="utf-8")
            proc = run_engine(
                [("skill", "skills/probe/SKILL.md")], tmp,
                extra=("--config", str(Path(tmp) / ".vibe-suite.md")),  # does not exist
            )
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            f = json.loads(proc.stdout.decode())["files"][0]
        self.assertEqual(f["score"], 100)
        self.assertEqual(f["verdict"], "pass", "the default threshold 70 applies")


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

    def test_injected_replace_failure_leaves_history_intact(self):
        # The promised injected-failure test: the atomic-rename primitive itself fails
        # (os.replace raises), in-process, so the property is proven for ANY rename
        # failure, not only the permission-denied shape the subprocess test below covers.
        engine = load_engine()
        with tempfile.TemporaryDirectory() as tmp:
            hist = Path(tmp) / "vibe-history.json"
            seed = [{"scope": "s", "score": 100, "band": "Excellent",
                     "total_penalty": 0, "file": "a"}]
            hist.write_text(json.dumps(seed, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
            before = hist.read_bytes()

            def boom(*args, **kwargs):
                raise OSError("injected replace failure")

            original = engine.bridge.os.replace
            engine.bridge.os.replace = boom
            try:
                with self.assertRaises(OSError):
                    engine._append_history(
                        hist, "s2", [{"path": "b", "score": 90, "band": "Excellent"}], [-10])
            finally:
                engine.bridge.os.replace = original
            self.assertEqual(hist.read_bytes(), before, "prior bytes must stay untouched")
            self.assertEqual(
                [p.name for p in Path(tmp).iterdir()], ["vibe-history.json"],
                "no temp residue may remain",
            )

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
