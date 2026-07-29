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
  stdout : JSON {"files":[{"path","tier","score","band","verdict",
           "findings":[{"rule","check","line","penalty"}],"advisories":[{"rule","note"}]}],
           "run":{"files","total_penalty","considered_rows","skipped"}}
  exit   : 0 scored; 2 contract refusal (bad record, bad root); a missing --config file is
           NOT a refusal — defaults apply

Row ledger: scripts/score_engine_rows.md classifies every row of EVERY penalty table in the
scoring skill as `mechanical` (predicate quoted from the owning text) or `advisory-zero`;
this suite asserts the ledger carries every row of every table, that the engine deducts
ONLY on mechanical rows, and (MechanicalRowMatrix) that every mechanical ledger row has at
least one positive and one negative case — the CASES keys are asserted equal to the
ledger's mechanical set, so a future mechanical row without cases fails here.

Tier: each files[] entry carries the artifact's tool tier (`1` open-spec vs
`2-Claude`/`2-Codex`/`2-Antigravity`, classified per file from its canonical path);
tool-specific rows are tier-conditioned and asserted not to fire across tiers
(TierClassification's two-tool trees — one from explicit-type records, one end-to-end
from scanner category letters through the engine's own classify.md routing). Tier 1.5
("open-spec corpora") has no per-file predicate; every tier-`1` entry carries a
zero-penalty tier-boundary advisory naming the possibility instead.
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

    def test_r01_carveout_spelled_out_quantities(self):
        # The measurable-criterion clause is a quantity, not only a digit: spelled-out
        # cardinals from the engine's closed list qualify (review finding 2, iter 2 —
        # the reviewer's own example must not deduct).
        f = score_one(clean_skill() + "\nSet an appropriate timeout of one minute.\n")
        self.assertEqual(r01_total(f), 0, "'appropriate timeout of one minute' is exempt")
        f = score_one(clean_skill() + "\nRetry a reasonable number of times, at most three.\n")
        self.assertEqual(r01_total(f), 0)
        f = score_one(clean_skill() + "\nKeep several buffers, twenty in the worst case.\n")
        self.assertEqual(r01_total(f), 0)
        # and the encoding is no wider than a quantity: a bare term still deducts
        f = score_one(clean_skill() + "\nUse appropriate handling.\n")
        self.assertEqual(r01_total(f), -2, "a bare term with no criterion still deducts")
        f = score_one(clean_skill() + "\nApply appropriate padding to the margin.\n")
        self.assertEqual(r01_total(f), -2, "non-quantity words are not criteria")

    def test_r01_borderline_advisory_surfaces_the_open_ended_carveout(self):
        """conventions §4's third carve-out ("any listed term followed by a
        measurable-criterion clause") is open-ended — the passage enumerates no example
        form of the clause. The engine encodes exactly the quantity forms (digit,
        spelled cardinal) and no others, so a valid nonnumeric criterion (review
        finding 2, iter 2: a condition on an explicit status value) still deducts —
        WITH a borderline advisory naming the rubric's own override as the escape."""
        # A status-value criterion: no digit, no spelled cardinal — deducts, advised.
        f = score_one(
            clean_skill() + "\nWait for an adequate result, meaning status equals READY.\n")
        self.assertEqual(r01_total(f), -2)
        notes = [a["note"] for a in f["advisories"] if a["rule"] == "R01"]
        self.assertTrue(
            any("carve-out forms absent" in n and "rule_overrides.R01" in n for n in notes),
            notes)
        # No counted occurrence (the reviewer's own carved-out case): no advisory.
        f = score_one(clean_skill() + "\nSet an appropriate timeout of one minute.\n")
        self.assertEqual(r01_total(f), 0)
        self.assertEqual([a for a in f["advisories"] if a["rule"] == "R01"], [])
        # The cap still binds and the advisory rides along with the capped finding.
        f = score_one(clean_skill() + "\n" + " ".join(["appropriate"] * 12) + "\n")
        self.assertEqual(r01_total(f), -20)
        self.assertTrue(any("carve-out forms absent" in a["note"]
                            for a in f["advisories"] if a["rule"] == "R01"))
        # The sanctioned escape works end-to-end: rule_overrides.R01 suppress zeroes the
        # deduction, and the borderline advisory yields to the suppression advisory.
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".vibe-suite.md"
            config.write_text(
                "---\nrule_overrides:\n  R01:\n    suppress: true\n---\n", encoding="utf-8")
            d = Path(tmp) / "skills" / "probe"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                clean_skill()
                + "\nWait for an adequate result, meaning status equals READY.\n",
                encoding="utf-8")
            proc = run_engine([("skill", "skills/probe/SKILL.md")], tmp,
                              extra=("--config", str(config)))
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            f = json.loads(proc.stdout.decode())["files"][0]
        self.assertEqual(r01_total(f), 0)
        r01_notes = [a["note"] for a in f["advisories"] if a["rule"] == "R01"]
        self.assertTrue(any("suppressed by rule_overrides" in n for n in r01_notes))
        self.assertFalse(any("carve-out forms absent" in n for n in r01_notes),
                         "a suppressed R01 has no standing deduction to advise about")

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
        self.assertEqual({a["rule"] for a in agent["advisories"]}, {"R10", "R11", "--"})
        # Both files are open-spec (tier 1): each carries the tier-boundary advisory.
        for entry in (skill, agent):
            self.assertEqual(entry["tier"], "1")
            self.assertTrue(any("Tier 1.5" in a["note"] for a in entry["advisories"]))
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
        # An untabled type gets no type/tier table advisories — only the two per-file
        # synthesized ones: the R01 borderline advisory (its counted term had no
        # carve-out form) and the tier-1 boundary advisory (open-spec artifact).
        self.assertEqual([a["rule"] for a in f["advisories"]], ["R01", "--"])
        self.assertIn("rule_overrides.R01", f["advisories"][0]["note"])
        self.assertIn("Tier 1.5", f["advisories"][1]["note"])
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

    def test_schema_conforming_frontmatter_shapes_parse_clean(self):
        # The permissive artifact parser accepts EVERY schema-conforming shape (review
        # finding 5, iter 2): flow mappings (`metadata: {author: x}`), nested block
        # mappings, sequences, quoted scalars, block scalars, hyphenated keys.
        flow = ("---\nname: probe\ndescription: Concrete probe; use when testing keys.\n"
                "metadata: {author: x}\n---\n# probe\n\nBody.\n")
        nested = ("---\nname: \"probe\"\n"
                  "description: 'Concrete probe; use when testing shapes.'\n"
                  "metadata:\n  author: x\n  version: 1.0.0\n"
                  "tags:\n  - alpha\n  - beta\n"
                  "allowed-tools: Bash(git:*), Read\n---\n# probe\n\nBody.\n")
        block = ("---\nname: probe\ndescription: |\n  Concrete probe; use when testing\n"
                 "  block scalars.\nmetadata:\n  author: x\n---\n# probe\n\nBody.\n")
        # Flow collections bracket-match ACROSS lines (review finding 5, iter 3):
        # a multiline flow mapping, a multiline flow sequence, and a nested mix.
        multiline_map = ("---\nname: probe\n"
                         "description: Concrete probe; use when testing spans.\n"
                         "metadata: {author: x,\n  version: 1.0.0}\n---\n# probe\n\nBody.\n")
        multiline_seq = ("---\nname: probe\n"
                         "description: Concrete probe; use when testing spans.\n"
                         "tags: [alpha,\n  beta, gamma]\n---\n# probe\n\nBody.\n")
        multiline_nested = ("---\nname: probe\n"
                            "description: Concrete probe; use when testing spans.\n"
                            "metadata: {tags: [a,\n  b], author: x}\n---\n# probe\n\nBody.\n")
        # A quoted scalar may close on a later line (review finding 5, iter-3 residue):
        # the newline is content, the value parses clean.
        multiline_quoted = ("---\nname: probe\n"
                            "description: \"Concrete probe; use when testing\n"
                            "  multiline quoted scalars.\"\n---\n# probe\n\nBody.\n")
        # Apostrophes in inert contexts must never trigger the multiline merger: in a
        # trailing comment, in a PLAIN scalar value, and inside block-scalar content.
        comment_apostrophe = ("---\nname: probe  # don't merge past this\n"
                              "description: Concrete probe; use when testing comments.\n"
                              "---\n# probe\n\nBody.\n")
        plain_apostrophe = ("---\nname: probe\n"
                            "description: Don't merge this; use when testing plains.\n"
                            "---\n# probe\n\nBody.\n")
        block_apostrophe = ("---\nname: probe\n"
                            "description: |\n  Bob's valid block text; use when\n"
                            "  testing block scalars.\n---\n# probe\n\nBody.\n")
        # Block content may itself LOOK like `key: 'open-quote...` — it is opaque bytes
        # and must never engage the merger (R2 step-9 residue case).
        block_keylike = ("---\nname: probe\n"
                         "description: Concrete probe; use when testing block opacity.\n"
                         "metadata: |\n  example: 'arbitrary block text\n"
                         "  still arbitrary block text\n---\n# probe\n\nBody.\n")
        # Same opacity with an indentation indicator (`|2`) and a chomping+indent form —
        # the indicator grammar must mirror the walker's _BLOCK_HEADER.
        block_indicator = ("---\nname: probe\n"
                           "description: Concrete probe; use when testing indicators.\n"
                           "metadata: |2\n  example: 'arbitrary block text\n"
                           "  still arbitrary block text\n---\n# probe\n\nBody.\n")
        block_chomp_indicator = ("---\nname: probe\n"
                                 "description: Concrete probe; use when testing chomping.\n"
                                 "metadata: |-2\n  example: 'arbitrary block text\n"
                                 "  still arbitrary block text\n---\n# probe\n\nBody.\n")
        for body in (flow, nested, block, multiline_map, multiline_seq,
                     multiline_nested, multiline_quoted, comment_apostrophe,
                     plain_apostrophe, block_apostrophe, block_keylike,
                     block_indicator, block_chomp_indicator):
            with self.subTest(head=body.splitlines()[3]):
                f = score_one(body)
                self.assertEqual(
                    [x for x in f["findings"] if "parse" in x["check"].lower()], [])
                self.assertEqual(f["score"], 100, f["findings"])

    def test_quoted_scalar_trailing_garbage_and_eof_are_minus_25(self):
        # The other direction of the same residue: text after a CLOSED quoted scalar has
        # no reading, and EOF inside a quote is unterminated — both true failures.
        trailing = ("---\nname: \"probe\" garbage\n"
                    "description: Concrete probe; use when testing.\n---\n# probe\nBody.\n")
        unterminated = ("---\nname: probe\n"
                        "description: \"never closed anywhere\n---\n# probe\nBody.\n")
        for body in (trailing, unterminated):
            with self.subTest(head=body.splitlines()[1]):
                f = score_one(body)
                self.assertEqual(
                    [x["penalty"] for x in f["findings"] if "parse" in x["check"].lower()],
                    [-25],
                )

    def test_true_structural_failures_still_minus_25(self):
        # -25 fires ONLY on true structural failure: unbalanced quotes/brackets,
        # tab-broken indentation, a non-mapping top level (the missing-closing-fence case
        # is test_malformed_frontmatter_minus_25_and_continue above), and trailing text
        # after a closed flow collection (review finding 5, iter 3: `key: {a: b} garbage`
        # has no reading under the schema space, so accepting it would be a false parse).
        for body in (
            '---\nname: "unclosed\n---\n# probe\nBody.\n',
            "---\nmetadata: {author: x\n---\n# probe\nBody.\n",
            "---\nmetadata:\n\tauthor: x\n---\n# probe\nBody.\n",
            "---\n- a\n- b\n---\n# probe\nBody.\n",
            "---\nmetadata: {author: x} garbage\n---\n# probe\nBody.\n",
            "---\ntags: [a, b] junk\n---\n# probe\nBody.\n",
        ):
            with self.subTest(head=body.splitlines()[1]):
                f = score_one(body)
                self.assertEqual(
                    [x["penalty"] for x in f["findings"] if "parse" in x["check"].lower()],
                    [-25])

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


def run_tree(files, records):
    """Materialize a mini-tree, run the engine over `records`, return the parsed output."""
    with tempfile.TemporaryDirectory() as tmp:
        for rel, content in files.items():
            target = Path(tmp) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        proc = run_engine(records, tmp)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr.decode())
        return json.loads(proc.stdout.decode())


class TierClassification(unittest.TestCase):
    """The deterministic Tier 1 / 2-Claude / 2-Codex / 2-Antigravity classifier and the
    tier-conditioned do-not-penalize behavior it drives."""

    def test_classify_tier_markers(self):
        engine = load_engine()
        for path, tier in (
            ("skills/demo/SKILL.md", "1"),
            ("docs/notes.md", "1"),
            ("commands/score.md", "1"),
            (".claude/skills/demo/SKILL.md", "2-Claude"),
            (".claude/settings.json", "2-Claude"),
            (".claude-plugin/plugin.json", "2-Claude"),
            ("CLAUDE.md", "2-Claude"),
            (".mcp.json", "2-Claude"),
            (".lsp.json", "2-Claude"),
            ("monitors/monitors.json", "2-Claude"),
            ("hooks/hooks.json", "2-Claude"),
            ("home/.claude/projects/p/memory/note.md", "2-Claude"),
            (".codex/config.toml", "2-Codex"),
            (".codex/hooks.json", "2-Codex"),
            (".codex-plugin/plugin.json", "2-Codex"),
            (".agents/skills/demo/SKILL.md", "2-Codex"),
            (".agents/plugins/marketplace.json", "2-Codex"),
            ("AGENTS.md", "2-Codex"),
            ("agents/openai.yaml", "2-Codex"),
            (".gemini/commands/x.toml", "2-Antigravity"),
            (".agent/skills/demo/SKILL.md", "2-Antigravity"),
            ("gemini-extension.json", "2-Antigravity"),
            ("./agents/openai.yaml", "2-Codex"),
        ):
            with self.subTest(path=path):
                self.assertEqual(engine.classify_tier(path), tier)

    def test_two_tool_tree_tier_gated_hook_rows(self):
        # One mini-repo, Claude tree + Codex tree + Antigravity tree, byte-identical hook
        # configs: PreCompact is a confirmed Codex event but not a Claude one; SessionEnd
        # is a confirmed Claude event but not a Codex one. The SAME BYTES must deduct on
        # one tier and stay clean on the other — the tier-conditioned do-not-penalize rule
        # made observable in both directions. Antigravity findings stay advisory-zero per
        # their owning text even on a bogus event.
        precompact = json.dumps({"hooks": {"PreCompact": []}}, indent=2)
        sessionend = json.dumps({"hooks": {"SessionEnd": []}}, indent=2)
        out = run_tree(
            {
                "hooks/claude-a.json": precompact,
                "hooks/claude-b.json": sessionend,
                ".codex/hooks-a.json": precompact,
                ".codex/hooks-b.json": sessionend,
                ".gemini/hooks.json": json.dumps({"hooks": {"TotallyBogus": []}}, indent=2),
            },
            [
                ("A", "hooks/claude-a.json"),          # scanner category → engine classifies
                ("A", "hooks/claude-b.json"),
                ("hook-config", ".codex/hooks-a.json"),
                ("hook-config", ".codex/hooks-b.json"),
                ("hook-config", ".gemini/hooks.json"),
            ],
        )
        claude_a, claude_b, codex_a, codex_b, agy = out["files"]
        self.assertEqual([f["tier"] for f in out["files"]],
                         ["2-Claude", "2-Claude", "2-Codex", "2-Codex", "2-Antigravity"])
        # PreCompact: deducts on the Claude tier, clean on the Codex tier.
        self.assertEqual(
            [(x["rule"], x["check"], x["penalty"]) for x in claude_a["findings"]],
            [("R27", "event names valid", -15)])
        self.assertEqual(claude_a["score"], 85)
        self.assertEqual(codex_a["findings"], [])
        self.assertEqual(codex_a["score"], 100)
        # SessionEnd: the mirror image — clean on Claude, deducts on Codex.
        self.assertEqual(claude_b["findings"], [])
        self.assertEqual(
            [(x["rule"], x["check"], x["penalty"]) for x in codex_b["findings"]],
            [("R27", "event names valid", -15)])
        # Antigravity: even a bogus event never deducts; the R27 rows surface as advisories.
        self.assertEqual(agy["findings"], [])
        self.assertEqual(agy["score"], 100)
        agy_notes = [a["note"] for a in agy["advisories"] if a["rule"] == "R27"]
        self.assertEqual(len(agy_notes), 2)
        for note in agy_notes:
            self.assertIn("advisory", note)
        # Tier-conditioned advisories on the tool tables.
        self.assertTrue(any("MCP matcher format" in a["note"]
                            for a in claude_a["advisories"]))
        self.assertTrue(any("hooks config key" in a["note"]
                            for a in codex_a["advisories"]))
        # Row accounting: universal 5 + per-tool table (Claude 4 ×2, Codex 3 ×2,
        # Antigravity 2) + the two R01 rows per file.
        self.assertEqual(out["run"]["considered_rows"], (9 + 2) * 2 + (8 + 2) * 2 + (7 + 2))

    def test_hook_type_row_is_claude_tier_only(self):
        bad_type = json.dumps({"hooks": {"PreToolUse": [{"type": "weird"}]}}, indent=2)
        out = run_tree(
            {"hooks/hooks.json": bad_type, ".codex/hooks.json": bad_type},
            [("A", "hooks/hooks.json"), ("hook-config", ".codex/hooks.json")],
        )
        claude, codex = out["files"]
        self.assertIn("hook type valid", [x["check"] for x in claude["findings"]])
        self.assertNotIn("hook type valid", [x["check"] for x in codex["findings"]])

    def test_tier_boundary_advisory_on_open_spec_files_only(self):
        """Tier 1.5's whole definition in the owning text is "open-spec corpora" — a
        collection property with no per-file predicate. The engine therefore emits
        tier `1` and states the boundary: every open-spec file carries a zero-penalty
        tier-boundary advisory naming the 1.5 possibility; tool-tree (tier-2) files
        never do. The ledger documents the same boundary in its own words."""
        open_spec = score_one(clean_skill())
        self.assertEqual(open_spec["tier"], "1")
        boundary = [a for a in open_spec["advisories"] if "Tier 1.5" in a["note"]]
        self.assertEqual(len(boundary), 1)
        self.assertIn("open-spec corpora", boundary[0]["note"])
        self.assertIn("no per-file predicate", boundary[0]["note"])
        out = run_tree({"hooks/hooks.json": HOOK_OK}, [("A", "hooks/hooks.json")])
        claude = out["files"][0]
        self.assertEqual(claude["tier"], "2-Claude")
        self.assertEqual([a for a in claude["advisories"] if "Tier 1.5" in a["note"]], [])
        # The ledger quotes the defining sentence and states why no per-file predicate
        # exists — the documented boundary this advisory implements.
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("**Tier 1.5** — open-spec corpora.", ledger)
        self.assertIn("no per-file predicate", ledger)

    def test_two_tool_end_to_end_from_category_records(self):
        """End-to-end from scanner CATEGORY letters only: every route below is resolved
        by the engine's own classify.md rules — no explicit-type records.

        Production cannot produce a routed Codex hook-config: classify.md row 7 routes
        `hooks/**/*.json` (anchored, so the Claude plugin hooks tree only) to
        `hook-config`, and no other row matches a Codex-tree config — `.codex/hooks.json`
        falls through to the `document` fallback (the ledger's Hooks (Codex CLI) note:
        "no classify.md path yields a Codex hook-config type"). This test asserts THAT
        documented unrouted behavior on the Codex hook path, and exercises the tier gate
        through the closest fully-routable two-tool pair instead: `.mcp.json` at the root
        (2-Claude) vs `.codex/.mcp.json` (2-Codex) — classify.md row 10 (`basename is
        .mcp.json`) routes both, and the server-command row is tier-conditioned to
        2-Claude, so the same bytes deduct on one tier and stay clean on the other."""
        precompact = json.dumps({"hooks": {"PreCompact": []}}, indent=2)
        sessionend = json.dumps({"hooks": {"SessionEnd": []}}, indent=2)
        no_command = json.dumps({"mcpServers": {"a": {}}}, indent=2)
        out = run_tree(
            {
                "hooks/hooks.json": precompact,
                ".codex/hooks.json": sessionend,
                ".mcp.json": no_command,
                ".codex/.mcp.json": no_command,
            },
            [
                ("A", "hooks/hooks.json"),
                ("A", ".codex/hooks.json"),
                ("B", ".mcp.json"),
                ("B", ".codex/.mcp.json"),
            ],
        )
        claude_hook, codex_hook, claude_mcp, codex_mcp = out["files"]
        self.assertEqual([f["tier"] for f in out["files"]],
                         ["2-Claude", "2-Codex", "2-Claude", "2-Codex"])
        # The routed Claude hook-config deducts on the Codex-only event.
        self.assertEqual(
            [(x["rule"], x["check"], x["penalty"]) for x in claude_hook["findings"]],
            [("R27", "event names valid", -15)])
        # The Codex hook path is UNROUTED: category routing classifies it `document`
        # (a type with no table), so the Claude-only event inside deducts nothing, no
        # hook-table advisory appears, and only the two generic R01 rows are consulted.
        self.assertEqual(codex_hook["findings"], [])
        self.assertEqual(codex_hook["advisories"], [])
        self.assertEqual(codex_hook["score"], 100)
        # The tier gate, end-to-end on a fully-routable pair: same bytes, an MCP entry
        # with no command — deducts at 2-Claude, tier-gated to clean at 2-Codex.
        self.assertEqual(
            [(x["rule"], x["check"], x["penalty"]) for x in claude_mcp["findings"]],
            [("--", "server command present", -15)])
        self.assertEqual(codex_mcp["findings"], [])
        self.assertEqual(codex_mcp["score"], 100)
        # Row accounting: hook-config@2-Claude (5 universal + 4 Claude + 2 generic),
        # document (2 generic), mcp-config x2 (2 table + 2 generic each).
        self.assertEqual(out["run"]["considered_rows"], 11 + 2 + 4 + 4)


# ------------------------------------------------------------- mechanical-row case matrix
# One entry per ledger row classified `mechanical`, keyed by the ledger's own
# (section, rule, check, condition) cells. Each entry carries at least one positive case
# (the row deducts, exact value) and one negative case (clean); numeric rows carry
# boundary cases. `test_cases_cover_the_ledger_mechanical_set_exactly` asserts the key set
# equals the parsed ledger's mechanical set, so a future mechanical row without cases
# fails before it can ship untested.

S_SKILLS = "Skills"
S_AGENTS = "Agents"
S_COMMANDS = "Commands"
S_PARTIALS = "Shared Partials"
S_RULES = "Rules"
S_HOOKS_U = "Hooks — universal (all tools)"
S_HOOKS_CLAUDE = "Hooks (Claude Code, Tier 2-Claude)"
S_HOOKS_CODEX = "Hooks (Codex CLI, Tier 2-Codex)"
S_MANIFEST = "plugin.json (Claude, `.claude-plugin/plugin.json`)"
S_MCP = ".mcp.json (Claude, repo root)"
S_LSP = ".lsp.json (Tier 2-Claude)"
S_SETTINGS = "Settings files (.claude/settings.json, .claude/settings.local.json)"
S_CLAUDE_MD = "CLAUDE.md"
S_MEMORY = "Memory files (`.md` under `~/.claude/projects/*/memory/`)"
S_R01 = "All types: vague quantifiers"

SKILL_AT = ("skill", "skills/probe/SKILL.md")
AGENT_AT = ("agent", "agents/helper.md")
HOOK_AT = ("hook-config", "hooks/hooks.json")
CODEX_HOOK_AT = ("hook-config", ".codex/hooks.json")
MEMORY_AT = ("memory", "proj/memory/note.md")

AGENT_NO_DESC = (
    "---\nname: helper\nmodel: haiku\ntools: Read\n---\n\n# helper\n\n"
    "## Output format\n\nOne line per file.\n\n"
    + "<example>\nContext: probe.\nuser: go?\nassistant: going.\n</example>\n" * 2
)
UI_SKILL = ("---\nname: probe\ndescription: Concrete probe; use when testing blocks.\n"
            "user_invocable: true\n---\n# probe\nBody.\n")
MANIFEST_FULL = json.dumps(
    {"name": "probe", "version": "1.2.3", "description": "A probe plugin."}, indent=2)
MEMORY_FULL = "---\nname: n\ndescription: d\ntype: user\n---\nBody.\n"
HOOK_OK = json.dumps({"hooks": {"PreToolUse": [
    {"type": "command", "timeout": 5, "matcher": "Bash", "command": "echo ok"}]}}, indent=2)


def hooks_json(**kwargs):
    return json.dumps({"hooks": kwargs}, indent=2)


def rule_of_lines(total):
    head = ["---", "description: Rule budget probe.", "---"]
    return "\n".join(head + ["Line."] * (total - 3)) + "\n"


def claude_md_of_lines(total):
    return "\n".join(["# Title"] + ["A plain line."] * (total - 1)) + "\n"


def case(kind, files, record, row, expect, note=""):
    return {"kind": kind, "files": files, "record": record, "row": row,
            "expect": expect, "note": note}


def _skill(body):
    return {"skills/probe/SKILL.md": body}


def _agent(body):
    return {"agents/helper.md": body}


def _r01_cases():
    word_pos = clean_skill() + "\nUse appropriate handling here.\n"
    return [
        case("positive", _skill(word_pos), SKILL_AT, ("R01", "vague quantifier"), -2),
        case("negative", _skill(clean_skill()), SKILL_AT, ("R01", "vague quantifier"), 0),
        case("negative", _skill(clean_skill() + "\nSet an appropriate timeout of one minute.\n"),
             SKILL_AT, ("R01", "vague quantifier"), 0, "measurable-criterion carve-out"),
    ]


def _r01_cap_cases():
    def rep(n):
        return _skill(clean_skill() + "\n" + " ".join(["appropriate"] * n) + "\n")
    return [
        case("positive", rep(12), SKILL_AT, ("R01", "vague quantifier"), -20, "cap binds"),
        case("boundary", rep(10), SKILL_AT, ("R01", "vague quantifier"), -20, "exact reach"),
        case("boundary", rep(11), SKILL_AT, ("R01", "vague quantifier"), -20, "first clamp"),
        case("negative", rep(3), SKILL_AT, ("R01", "vague quantifier"), -6, "below the cap"),
    ]


CASES = {
    (S_SKILLS, "--", "name present", "missing"): [
        case("positive",
             _skill("---\ndescription: Concrete probe; use when testing.\n---\n# x\nBody.\n"),
             SKILL_AT, ("--", "name present"), -25),
        case("negative", _skill(clean_skill()), SKILL_AT, ("--", "name present"), 0),
    ],
    (S_SKILLS, "--", "name matches parent dir",
     "frontmatter name differs from parent directory name (conventions §5; open-spec MUST)"): [
        case("positive", _skill(clean_skill(name="other")), SKILL_AT,
             ("--", "name matches parent dir"), -15),
        case("negative", _skill(clean_skill()), SKILL_AT,
             ("--", "name matches parent dir"), 0),
    ],
    (S_SKILLS, "R04", "description present", "missing"): [
        case("positive", _skill("---\nname: probe\n---\n# x\nBody.\n"), SKILL_AT,
             ("R04", "description present"), -25),
        case("negative", _skill(clean_skill()), SKILL_AT, ("R04", "description present"), 0),
    ],
    (S_SKILLS, "R04", "description length", "500–800 chars"): [
        case("positive", _skill(clean_skill(description="x" * 600)), SKILL_AT,
             ("R04", "description length"), -5),
        case("boundary", _skill(clean_skill(description="x" * 499)), SKILL_AT,
             ("R04", "description length"), 0),
        case("boundary", _skill(clean_skill(description="x" * 500)), SKILL_AT,
             ("R04", "description length"), -5),
        case("boundary", _skill(clean_skill(description="x" * 800)), SKILL_AT,
             ("R04", "description length"), -5),
        case("negative", _skill(clean_skill()), SKILL_AT, ("R04", "description length"), 0),
    ],
    (S_SKILLS, "R04", "description length", "over 800 chars"): [
        case("positive", _skill(clean_skill(description="x" * 801)), SKILL_AT,
             ("R04", "description length"), -10),
        case("boundary", _skill(clean_skill(description="x" * 800)), SKILL_AT,
             ("R04", "description length"), -5, "mutually exclusive with the 500-800 band"),
        case("negative", _skill(clean_skill(description="x" * 100)), SKILL_AT,
             ("R04", "description length"), 0),
    ],
    (S_SKILLS, "R05", "body length", "400–500 lines"): [
        case("positive", _skill(skill_with_body(450)), SKILL_AT, ("R05", "body length"), -5),
        case("boundary", _skill(skill_with_body(399)), SKILL_AT, ("R05", "body length"), 0),
        case("boundary", _skill(skill_with_body(400)), SKILL_AT, ("R05", "body length"), -5),
        case("boundary", _skill(skill_with_body(500)), SKILL_AT, ("R05", "body length"), -5),
        case("negative", _skill(skill_with_body(100)), SKILL_AT, ("R05", "body length"), 0),
    ],
    (S_SKILLS, "R05", "body length", "over 500 lines"): [
        case("positive", _skill(skill_with_body(501)), SKILL_AT, ("R05", "body length"), -10),
        case("boundary", _skill(skill_with_body(500)), SKILL_AT, ("R05", "body length"), -5,
             "a mutually exclusive band that never stacks"),
        case("negative", _skill(skill_with_body(399)), SKILL_AT, ("R05", "body length"), 0),
    ],
    (S_SKILLS, "R06", "example blocks",
     "zero `<example>` blocks on a `user_invocable: true` skill"): [
        case("positive", _skill(UI_SKILL), SKILL_AT, ("R06", "example blocks"), -10),
        case("negative",
             _skill(UI_SKILL + "<example>\nContext: p.\nuser: p?\nassistant: p.\n</example>\n"),
             SKILL_AT, ("R06", "example blocks"), 0),
        case("negative", _skill(clean_skill(examples=0)), SKILL_AT,
             ("R06", "example blocks"), 0, "without user_invocable the row cannot fire"),
    ],
    (S_AGENTS, "R09", "description present", "missing"): [
        case("positive", _agent(AGENT_NO_DESC), AGENT_AT, ("R09", "description present"), -25),
        case("negative", _agent(agent_md()), AGENT_AT, ("R09", "description present"), 0),
    ],
    (S_AGENTS, "R09", "example blocks", "exactly 1 example"): [
        case("positive", _agent(agent_md(examples=1)), AGENT_AT, ("R09", "example blocks"), -5),
        case("negative", _agent(agent_md(examples=2)), AGENT_AT, ("R09", "example blocks"), 0),
    ],
    (S_AGENTS, "R09", "example blocks", "zero examples"): [
        case("positive", _agent(agent_md(examples=0)), AGENT_AT, ("R09", "example blocks"), -15),
        case("boundary", _agent(agent_md(examples=1)), AGENT_AT, ("R09", "example blocks"), -5),
        case("boundary", _agent(agent_md(examples=2)), AGENT_AT, ("R09", "example blocks"), 0),
        case("negative", _agent(agent_md()), AGENT_AT, ("R09", "example blocks"), 0),
    ],
    (S_AGENTS, "R10", "model declared", "not declared"): [
        case("positive", _agent(agent_md(model=False)), AGENT_AT, ("R10", "model declared"), -5),
        case("negative", _agent(agent_md()), AGENT_AT, ("R10", "model declared"), 0),
    ],
    (S_AGENTS, "R11", "tools declared", "not declared"): [
        case("positive", _agent(agent_md(tools=False)), AGENT_AT, ("R11", "tools declared"), -5),
        case("negative", _agent(agent_md()), AGENT_AT, ("R11", "tools declared"), 0),
    ],
    (S_AGENTS, "R12", "output format", "no output format spec in body"): [
        case("positive", _agent(agent_md(output_heading=False)), AGENT_AT,
             ("R12", "output format"), -10),
        case("negative", _agent(agent_md()), AGENT_AT, ("R12", "output format"), 0),
    ],
    (S_COMMANDS, "--", "description present", "missing"): [
        case("positive", {"commands/go.md": "---\nargument-hint: x\n---\n# go\nBody.\n"},
             ("command", "commands/go.md"), ("--", "description present"), -25),
        case("negative", {"commands/go.md": "---\ndescription: Runs go.\n---\n# go\nBody.\n"},
             ("command", "commands/go.md"), ("--", "description present"), 0),
    ],
    (S_PARTIALS, "R19", "`user-invocable: false`", "missing or true"): [
        case("positive", {"commands/shared/x.md": "---\ndescription: Shared.\n---\nBody.\n"},
             ("shared-partial", "commands/shared/x.md"),
             ("R19", "`user-invocable: false`"), -25, "missing"),
        case("positive", {"commands/shared/x.md": "---\nuser-invocable: true\n---\nBody.\n"},
             ("shared-partial", "commands/shared/x.md"),
             ("R19", "`user-invocable: false`"), -25, "true"),
        case("negative", {"commands/shared/x.md": "---\nuser-invocable: false\n---\nBody.\n"},
             ("shared-partial", "commands/shared/x.md"),
             ("R19", "`user-invocable: false`"), 0),
    ],
    (S_RULES, "R21", "description present", "missing frontmatter description"): [
        case("positive", {".claude/rules/01-x.md": "---\nname: x\n---\n**Do X.** Because.\n"},
             ("rule", ".claude/rules/01-x.md"), ("R21", "description present"), -10),
        case("negative", {".claude/rules/01-x.md": rule_of_lines(10)},
             ("rule", ".claude/rules/01-x.md"), ("R21", "description present"), 0),
    ],
    (S_RULES, "R23", "budget", "rule file over 500 lines"): [
        case("positive", {".claude/rules/01-x.md": rule_of_lines(501)},
             ("rule", ".claude/rules/01-x.md"), ("R23", "budget"), -15),
        case("boundary", {".claude/rules/01-x.md": rule_of_lines(500)},
             ("rule", ".claude/rules/01-x.md"), ("R23", "budget"), 0),
        case("negative", {".claude/rules/01-x.md": rule_of_lines(10)},
             ("rule", ".claude/rules/01-x.md"), ("R23", "budget"), 0),
    ],
    (S_HOOKS_U, "--", "valid syntax", "config fails to parse (JSON or TOML per tool)"): [
        case("positive", {"hooks/hooks.json": "{broken"}, HOOK_AT, ("--", "valid syntax"), -25),
        case("negative", {"hooks/hooks.json": HOOK_OK}, HOOK_AT, ("--", "valid syntax"), 0),
    ],
    (S_HOOKS_U, "--", "command safety",
     "dangerous patterns (`rm -rf`, `git push --force`, `DROP TABLE`)"): [
        case("positive",
             {"hooks/hooks.json": hooks_json(PreToolUse=[
                 {"type": "command", "command": "rm -rf /tmp/x"}])},
             HOOK_AT, ("--", "command safety"), -15),
        case("negative", {"hooks/hooks.json": HOOK_OK}, HOOK_AT, ("--", "command safety"), 0),
    ],
    (S_HOOKS_U, "--", "matcher regex valid", "does not compile"): [
        case("positive",
             {"hooks/hooks.json": hooks_json(PreToolUse=[{"type": "command", "matcher": "("}])},
             HOOK_AT, ("--", "matcher regex valid"), -10),
        case("negative", {"hooks/hooks.json": HOOK_OK}, HOOK_AT,
             ("--", "matcher regex valid"), 0),
    ],
    (S_HOOKS_U, "--", "timeout reasonable", "timeout over 30s"): [
        case("positive",
             {"hooks/hooks.json": hooks_json(PreToolUse=[{"type": "command", "timeout": 31}])},
             HOOK_AT, ("--", "timeout reasonable"), -5),
        case("boundary",
             {"hooks/hooks.json": hooks_json(PreToolUse=[{"type": "command", "timeout": 30}])},
             HOOK_AT, ("--", "timeout reasonable"), 0),
        case("negative", {"hooks/hooks.json": HOOK_OK}, HOOK_AT,
             ("--", "timeout reasonable"), 0),
    ],
    (S_HOOKS_CLAUDE, "R27", "event names valid",
     "unrecognized event; confirmed Claude events: SessionStart, SessionEnd, "
     "UserPromptSubmit, PreToolUse, PostToolUse, PermissionRequest, Stop, StopFailure, "
     "FileChanged"): [
        case("positive", {"hooks/hooks.json": hooks_json(PreCompact=[])}, HOOK_AT,
             ("R27", "event names valid"), -15, "a Codex-only event on the Claude tier"),
        case("negative", {"hooks/hooks.json": HOOK_OK}, HOOK_AT,
             ("R27", "event names valid"), 0),
        case("negative", {".codex/hooks.json": hooks_json(PreCompact=[])}, CODEX_HOOK_AT,
             ("R27", "event names valid"), 0, "tier-conditioned: same bytes, Codex tier"),
    ],
    (S_HOOKS_CLAUDE, "R27", "case correct", "wrong case (e.g. lowercase pretooluse)"): [
        case("positive", {"hooks/hooks.json": hooks_json(pretooluse=[])}, HOOK_AT,
             ("R27", "case correct"), -10),
        case("negative", {"hooks/hooks.json": HOOK_OK}, HOOK_AT, ("R27", "case correct"), 0),
    ],
    (S_HOOKS_CLAUDE, "--", "hook type valid",
     "unrecognized type; confirmed types: command, http, mcp_tool, prompt, agent"): [
        case("positive", {"hooks/hooks.json": hooks_json(PreToolUse=[{"type": "weird"}])},
             HOOK_AT, ("--", "hook type valid"), -10),
        case("negative", {"hooks/hooks.json": HOOK_OK}, HOOK_AT, ("--", "hook type valid"), 0),
        case("negative", {".codex/hooks.json": hooks_json(PreToolUse=[{"type": "weird"}])},
             CODEX_HOOK_AT, ("--", "hook type valid"), 0,
             "tier-conditioned: the row is the Claude table's"),
    ],
    (S_HOOKS_CODEX, "R27", "event names valid",
     "unrecognized event; confirmed Codex events: SessionStart, UserPromptSubmit, "
     "PreToolUse, PostToolUse, PermissionRequest, PreCompact, PostCompact, SubagentStart, "
     "SubagentStop, Stop"): [
        case("positive", {".codex/hooks.json": hooks_json(SessionEnd=[])}, CODEX_HOOK_AT,
             ("R27", "event names valid"), -15, "a Claude-only event on the Codex tier"),
        case("negative", {".codex/hooks.json": hooks_json(PreCompact=[])}, CODEX_HOOK_AT,
             ("R27", "event names valid"), 0),
        case("negative", {"hooks/hooks.json": hooks_json(SessionEnd=[])}, HOOK_AT,
             ("R27", "event names valid"), 0, "tier-conditioned: same bytes, Claude tier"),
    ],
    (S_HOOKS_CODEX, "R27", "case correct", "wrong case"): [
        case("positive", {".codex/hooks.json": hooks_json(precompact=[])}, CODEX_HOOK_AT,
             ("R27", "case correct"), -10),
        case("negative", {".codex/hooks.json": hooks_json(PreCompact=[])}, CODEX_HOOK_AT,
             ("R27", "case correct"), 0),
    ],
    (S_MANIFEST, "--", "name present", "missing"): [
        case("positive",
             {".claude-plugin/plugin.json": json.dumps({"version": "1.0.0",
                                                        "description": "d"})},
             ("manifest", ".claude-plugin/plugin.json"), ("--", "name present"), -25),
        case("negative", {".claude-plugin/plugin.json": MANIFEST_FULL},
             ("manifest", ".claude-plugin/plugin.json"), ("--", "name present"), 0),
    ],
    (S_MANIFEST, "--", "version is semver", "present but invalid"): [
        case("positive",
             {".claude-plugin/plugin.json": json.dumps({"name": "x", "version": "nope",
                                                        "description": "d"})},
             ("manifest", ".claude-plugin/plugin.json"), ("--", "version is semver"), -10),
        case("negative", {".claude-plugin/plugin.json": MANIFEST_FULL},
             ("manifest", ".claude-plugin/plugin.json"), ("--", "version is semver"), 0),
        case("negative",
             {".claude-plugin/plugin.json": json.dumps({"name": "x", "description": "d"})},
             ("manifest", ".claude-plugin/plugin.json"), ("--", "version is semver"), 0,
             "an absent version never fires (present but invalid)"),
    ],
    (S_MANIFEST, "--", "description present", "missing"): [
        case("positive",
             {".claude-plugin/plugin.json": json.dumps({"name": "x", "version": "1.0.0"})},
             ("manifest", ".claude-plugin/plugin.json"), ("--", "description present"), -5),
        case("negative", {".claude-plugin/plugin.json": MANIFEST_FULL},
             ("manifest", ".claude-plugin/plugin.json"), ("--", "description present"), 0),
    ],
    (S_MCP, "--", "valid JSON", "parse fail"): [
        case("positive", {".mcp.json": "{broken"}, ("mcp-config", ".mcp.json"),
             ("--", "valid JSON"), -25),
        case("negative",
             {".mcp.json": json.dumps({"mcpServers": {"a": {"command": "x"}}})},
             ("mcp-config", ".mcp.json"), ("--", "valid JSON"), 0),
    ],
    (S_MCP, "--", "server command present", "MCP entry missing its command field"): [
        case("positive", {".mcp.json": json.dumps({"mcpServers": {"a": {}}})},
             ("mcp-config", ".mcp.json"), ("--", "server command present"), -15),
        case("negative",
             {".mcp.json": json.dumps({"mcpServers": {"a": {"command": "x"}}})},
             ("mcp-config", ".mcp.json"), ("--", "server command present"), 0),
    ],
    (S_LSP, "--", "valid JSON", "parse fail"): [
        case("positive", {".lsp.json": "{broken"}, ("lsp-config", ".lsp.json"),
             ("--", "valid JSON"), -25),
        case("negative", {".lsp.json": "{}"}, ("lsp-config", ".lsp.json"),
             ("--", "valid JSON"), 0),
    ],
    (S_SETTINGS, "--", "valid JSON", "parse fail"): [
        case("positive", {".claude/settings.json": "{broken"},
             ("settings", ".claude/settings.json"), ("--", "valid JSON"), -25),
        case("negative", {".claude/settings.json": "{}"},
             ("settings", ".claude/settings.json"), ("--", "valid JSON"), 0),
    ],
    (S_SETTINGS, "--", "hook definitions valid",
     "hooks key present → check event names + case"): [
        case("positive",
             {".claude/settings.json": json.dumps({"hooks": {"bogusA": [], "bogusB": []}})},
             ("settings", ".claude/settings.json"), ("--", "hook definitions valid"), -20,
             "-10 per invalid, twice"),
        case("boundary",
             {".claude/settings.json": json.dumps({"hooks": {"bogusA": []}})},
             ("settings", ".claude/settings.json"), ("--", "hook definitions valid"), -10),
        case("negative",
             {".claude/settings.json": json.dumps({"hooks": {"PreToolUse": []}})},
             ("settings", ".claude/settings.json"), ("--", "hook definitions valid"), 0),
    ],
    (S_CLAUDE_MD, "--", "under 200 lines", "exceeds 200 lines"): [
        case("positive", {"CLAUDE.md": claude_md_of_lines(201)}, ("claude-md", "CLAUDE.md"),
             ("--", "under 200 lines"), -5),
        case("boundary", {"CLAUDE.md": claude_md_of_lines(200)}, ("claude-md", "CLAUDE.md"),
             ("--", "under 200 lines"), 0),
        case("negative", {"CLAUDE.md": claude_md_of_lines(5)}, ("claude-md", "CLAUDE.md"),
             ("--", "under 200 lines"), 0),
    ],
    (S_CLAUDE_MD, "R36", "valid `@` imports", "an `@` import references a nonexistent file"): [
        case("positive", {"CLAUDE.md": "@missing.md\n"}, ("claude-md", "CLAUDE.md"),
             ("R36", "valid `@` imports"), -10),
        case("negative", {"CLAUDE.md": "@AGENTS.md\n", "AGENTS.md": "# memory\n"},
             ("claude-md", "CLAUDE.md"), ("R36", "valid `@` imports"), 0),
    ],
    (S_MEMORY, "--", "has YAML frontmatter", "—"): [
        case("positive", {"proj/memory/note.md": "# just a body\n"}, MEMORY_AT,
             ("--", "has YAML frontmatter"), -15),
        case("negative", {"proj/memory/note.md": MEMORY_FULL}, MEMORY_AT,
             ("--", "has YAML frontmatter"), 0),
    ],
    (S_MEMORY, "--", "name in frontmatter", "—"): [
        case("positive", {"proj/memory/note.md": "---\ndescription: d\ntype: user\n---\nB.\n"},
             MEMORY_AT, ("--", "name in frontmatter"), -10),
        case("negative", {"proj/memory/note.md": MEMORY_FULL}, MEMORY_AT,
             ("--", "name in frontmatter"), 0),
    ],
    (S_MEMORY, "--", "description in frontmatter", "—"): [
        case("positive", {"proj/memory/note.md": "---\nname: n\ntype: user\n---\nB.\n"},
             MEMORY_AT, ("--", "description in frontmatter"), -10),
        case("negative", {"proj/memory/note.md": MEMORY_FULL}, MEMORY_AT,
             ("--", "description in frontmatter"), 0),
    ],
    (S_MEMORY, "--", "type in frontmatter (values: user/feedback/project/reference)", "—"): [
        case("positive", {"proj/memory/note.md": "---\nname: n\ndescription: d\n---\nB.\n"},
             MEMORY_AT,
             ("--", "type in frontmatter (values: user/feedback/project/reference)"), -5,
             "absent"),
        case("positive",
             {"proj/memory/note.md": "---\nname: n\ndescription: d\ntype: bogus\n---\nB.\n"},
             MEMORY_AT,
             ("--", "type in frontmatter (values: user/feedback/project/reference)"), -5,
             "outside the closed list"),
        case("negative", {"proj/memory/note.md": MEMORY_FULL}, MEMORY_AT,
             ("--", "type in frontmatter (values: user/feedback/project/reference)"), 0),
    ],
    (S_R01, "R01", "vague quantifier",
     "each occurrence of: appropriate, relevant, as needed, sufficient, adequate, "
     "reasonable, properly, correctly, some, several, various — without measurable "
     "criteria"): _r01_cases(),
    (S_R01, "R01", "cap", "cap on total vague-quantifier penalty"): _r01_cap_cases(),
}

#: Rows whose condition is numeric (a count, length, or cap): boundary cases required.
NUMERIC_ROWS = {
    key for key in CASES
    if key[3] in ("500–800 chars", "over 800 chars", "400–500 lines", "over 500 lines",
                  "rule file over 500 lines", "timeout over 30s", "exceeds 200 lines",
                  "cap on total vague-quantifier penalty", "zero examples")
    or key[1:3] == ("--", "hook definitions valid")
}


class MechanicalRowMatrix(unittest.TestCase):
    """Positive/negative/boundary coverage for EVERY mechanical ledger row, table-driven."""

    @staticmethod
    def ledger_mechanical_rows():
        rows, section = [], None
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                section = line[3:].strip()
                continue
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 5 and cells[3] == "mechanical":
                rows.append((section, cells[0], cells[1], cells[2]))
        return rows

    def test_cases_cover_the_ledger_mechanical_set_exactly(self):
        ledger_rows = self.ledger_mechanical_rows()
        self.assertGreaterEqual(len(ledger_rows), 40, "the ledger parse found too few rows")
        self.assertEqual(len(ledger_rows), len(set(ledger_rows)), "duplicate ledger rows")
        self.assertEqual(
            set(CASES), set(ledger_rows),
            "CASES must cover the ledger's mechanical set exactly — a mechanical row "
            "without cases (or a case for a row the ledger no longer carries) fails here",
        )
        for key, cases in CASES.items():
            kinds = {entry["kind"] for entry in cases}
            self.assertIn("positive", kinds, key)
            self.assertIn("negative", kinds, key)
        for key in NUMERIC_ROWS:
            self.assertIn("boundary", {entry["kind"] for entry in CASES[key]}, key)

    def test_every_mechanical_row_case(self):
        for key, cases in sorted(CASES.items()):
            for entry in cases:
                with self.subTest(row=key[1:3], kind=entry["kind"], note=entry["note"]):
                    out = run_tree(entry["files"], [entry["record"]])
                    rule, check = entry["row"]
                    got = sum(f["penalty"] for f in out["files"][0]["findings"]
                              if f["rule"] == rule and f["check"] == check)
                    self.assertEqual(got, entry["expect"])


class EngineContract(unittest.TestCase):
    def test_refuses_bad_records_and_roots(self):
        self.assertEqual(run_engine([("skill", "/abs/path.md")], FIXTURE).returncode, 2)
        self.assertEqual(run_engine([("skill", "../escape.md")], FIXTURE).returncode, 2)
        self.assertEqual(run_engine([("skill", "missing.md")], FIXTURE).returncode, 2)


if __name__ == "__main__":
    unittest.main()
