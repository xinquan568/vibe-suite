# SPDX-License-Identifier: ISC
"""E3.8 (vibe-33) acceptance: /vibe-suite:spec-sync + spec-researcher.

Rung 0/1 pins contracts, the freshness normalization, and the fixture oracle. The live
research step is the agent's judgment lane: CI performs no network fetch. What runs
mechanically here is the one-to-one comparison of a RECORDED manual dry run against the
hand-authored expectation — the recording's provenance header states when and how it
was produced.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMAND = REPO_ROOT / "commands" / "spec-sync.md"
AGENT = REPO_ROOT / "agents" / "spec-researcher.md"
SPEC = REPO_ROOT / ".vibe-test" / "spec-researcher.spec.md"
FIX = REPO_ROOT / "tests" / "fixtures" / "spec-sync"
EXPECTED = FIX / "expected-report.md"
RECORDED = FIX / "recorded-dry-run.md"
OVERLAYS = {
    "claude": REPO_ROOT / "skills" / "conventions-claude" / "SKILL.md",
    "codex": REPO_ROOT / "skills" / "conventions-codex" / "SKILL.md",
    "antigravity": REPO_ROOT / "skills" / "conventions-antigravity" / "SKILL.md",
}

#: D6's exact canonical post-state lines (verbatim, including the ≥ character in the
#: preserved Claude qualification).
CANONICAL = {
    "claude": "**Spec freshness:** verified 2026-06-07 against the official Claude Code "
              "docs map dated 2026-06-05 (code.claude.com/docs/en/)",
    "codex": "**Spec freshness:** verified 2026-06-07 against Codex CLI 0.137.0, "
             "released 2026-06-04 (developers.openai.com/codex)",
    "antigravity": "**Spec freshness:** UNVERIFIED — research written 2026-05-25, six "
                   "days after the Antigravity 2.0 announcement of 2026-05-19; the "
                   "verification pass described in §10 has not landed "
                   "(developers.googleblog.com)",
}
PRESERVED = {
    "claude": "That map tracks Claude Code ≥ v2.1.16x; where earlier notes conflicted "
              "with this refresh, the newer facts below are canonical.",
    "codex": "Pre-releases existed up to 0.138.0-alpha.6 at refresh time.",
    "antigravity": "the spec has not settled since Antigravity 2.0, so most "
                   "tool-specific checks stay advisory",
}
SUPERSEDED = ["Freshness: refreshed 2026-06-07", "Refresh state: verified 2026-06-07"]

TAGS = ["RESOLVED", "REMOVE", "FIX", "ADD", "CONFIRM"]


def squash(text):
    return re.sub(r"\s+", " ", text)


def report_rows(text):
    """Parse a gap-report table into (seed, section, tag, confidence) tuples."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| Seed") or set(
                line.replace("|", "").strip()) <= set("-: "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 4 and cells[0].isdigit():
            rows.append(tuple(cells[:4]))
    return rows


class Deliverables(unittest.TestCase):
    def test_artifacts_and_registration(self):
        self.assertTrue(COMMAND.is_file())
        self.assertTrue(AGENT.is_file())
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("./commands/spec-sync.md", manifest["commands"])
        self.assertIn("./agents/spec-researcher.md", manifest["agents"])
        # at least the E3.8 state; later items add more (membership above pins ours)
        self.assertGreaterEqual(len(manifest["commands"]), 18)
        self.assertGreaterEqual(len(manifest["agents"]), 7)

    def test_agent_frontmatter_matches_its_shipped_spec(self):
        body = AGENT.read_text(encoding="utf-8")
        self.assertRegex(body, r"(?m)^description: Use when")
        self.assertRegex(body, r"(?m)^model: (haiku|sonnet|opus)$")
        # exact allowlist — adding Write (or any tool) is a contract change
        self.assertRegex(body, r"(?m)^tools: WebFetch, WebSearch, Read$")
        spec = SPEC.read_text(encoding="utf-8")
        self.assertIn("FIX/REMOVE/ADD/CONFIRM/RESOLVED", spec)
        flat = squash(body)
        self.assertIn("first-party", flat.lower())
        self.assertRegex(flat, r"(?i)one dispatch per overlay|per-overlay dispatch")
        # the output-table contract, field by field
        self.assertIn("| Seed/claim | Section | Tag | Confidence or reason | "
                      "Source label | URL |", flat)
        for tag in TAGS:
            self.assertIn(tag, body, f"agent must state tag {tag}")
        for reason in ("source-silent", "source-conflict"):
            self.assertIn(reason, body)
        # D4/D5 evidence rules, each bound: per-row label AND URL; a quoted statement
        # with its URL for every graded row; deficient evidence routed to UNCLASSIFIED
        self.assertIn("and the full page URL", flat)
        self.assertIn("Every graded row (`high` or `medium`) must quote the source "
                      "statement it relied on together with that URL", flat)
        self.assertIn("a row without a quotable statement and URL is not graded "
                      "evidence and belongs in `UNCLASSIFIED`", flat)

    def test_no_deprecated_vocabulary(self):
        # R51 is enforced on commands/** and agents/** (E3.7).
        for path in (COMMAND, AGENT):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"(?i)\bimplement\b")


class CommandContract(unittest.TestCase):
    def setUp(self):
        self.body = COMMAND.read_text(encoding="utf-8")
        self.flat = squash(self.body)

    def test_targets_field_complete(self):
        # D1: three tokens, `all` as default, floor excluded — each asserted by content
        for token in ("claude", "codex", "antigravity", "all"):
            self.assertIn(f"`{token}`", self.body, f"target token missing: {token}")
        self.assertIn("`all` (the default)", self.flat)
        self.assertIn("`skills/conventions/` floor is never a target", self.flat)

    def test_modes_and_change_predicate(self):
        self.assertIn("--dry-run", self.body)
        self.assertIn("--apply", self.body)
        self.assertIn("remains writable after the confidence threshold", self.flat)
        self.assertRegex(self.flat, r"(?i)no-change branch")
        self.assertRegex(self.flat, r"(?i)never commits")
        # D2: RESOLVED and a retiring CONFIRM are both actionable — deleting either
        # from the predicate fails here
        self.assertIn("FIX, REMOVE, ADD, or RESOLVED", self.flat)
        self.assertIn("CONFIRM that retires a correction note", self.flat)

    #: D3's five rows, EXACTLY and IN ORDER. A dict collapsed duplicates and hid
    #: reordering; an ordered list of full rows admits neither.
    D3_TABLE = [
        ["1", "`RESOLVED`", "carries an explicit hedge about X", "now settles X",
         "retire the hedge, state the settled fact"],
        ["2", "`REMOVE`", "states X", "X withdrawn/absent, no replacement",
         "delete the claim"],
        ["3", "`FIX`", "states X", "states not-X, with a replacement",
         "correct the claim in place"],
        ["4", "`ADD`", "silent on X, X in scope", "states X", "add the claim"],
        ["5", "`CONFIRM`", "states X definitely (no hedge)", "states X",
         "none, except note retirement (below)"],
    ]

    def test_tag_precedence_table_is_exact_and_ordered(self):
        rows = []
        for line in self.body.splitlines():
            if line.startswith("| ") and "`" in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if cells and cells[0].isdigit():
                    rows.append(cells)
        self.assertEqual(rows, self.D3_TABLE,
                         "the precedence table must match the frozen semantics exactly, "
                         "in order, with no extra or duplicate rows")

    def test_disjointness_rules_stated(self):
        self.assertIn("requires a replacement fact", self.flat)
        self.assertRegex(self.flat, r"(?i)CONFIRM requires .*un-hedged|no hedge")

    def test_confidence_and_threshold(self):
        self.assertIn("UNCLASSIFIED", self.body)
        self.assertIn("source-silent", self.body)
        self.assertIn("source-conflict", self.body)
        self.assertIn("--min-confidence", self.body)
        self.assertRegex(self.flat, r"(?i)default(s)? (to )?`?medium`?")
        self.assertIn("(withheld: below --min-confidence)", self.flat)
        # D4: both grade DEFINITIONS and the orthogonality statement
        self.assertIn("`high` is an explicit first-party statement", self.flat)
        self.assertIn("`medium` is first-party but indirect", self.flat)
        self.assertIn("grade the evidence, never the tag", self.flat)
        self.assertIn("Insufficient evidence is not a grade", self.flat)

    def test_evidence_contract_command_side(self):
        # the note carries BOTH label and URL, and the freshness line's label-only
        # convention is stated as a DISTINCTION, not a conflation
        self.assertIn("`<source label>` is the overlay-style bare domain path and "
                      "`<URL>` is the full first-party page URL", self.flat)
        self.assertIn("the note records BOTH", self.flat)
        self.assertIn("follows the overlays' existing label-only convention", self.flat)
        self.assertIn("not full URLs", self.flat)

    def test_correction_notes(self):
        self.assertIn(
            "<!-- spec-sync <run-date>: <tag> — <source label>, <URL> "
            "(confidence: high|medium) -->", self.body)
        self.assertIn("replaces its note rather than adding one", self.flat)
        self.assertIn("one note per claim, never accumulating", self.flat)
        self.assertIn("## Correction notes", self.body)
        self.assertRegex(self.flat, r"(?i)not valid YAML|conforming parser")
        # retirement is reachable: a note-retiring CONFIRM is writable
        self.assertRegex(self.flat,
                         r"(?i)CONFIRM .*retires .*(is writable|counts toward)")

    def test_overlay_root_semantics(self):
        self.assertIn("--overlay-root", self.body)
        self.assertRegex(self.flat, r"(?i)replaces the (selected )?overlay set")
        self.assertRegex(self.flat, r"(?i)requires an explicit target|refuses")

    #: The frozen 23-token sweep set — the command must SHIP it, not reference it.
    SWEEP_TOKENS = [
        ".claude/", ".codex/", ".agent/", ".gemini/", "AGENTS.md", "GEMINI.md",
        "CLAUDE.md", "hooks.json", "settings.json", "config.toml", ".mcp.json",
        "mcpServers", "marketplace.json", "plugin.json", "CLAUDE_PLUGIN_ROOT",
        "PreToolUse", "PostToolUse", "SessionStart", "SessionEnd", "SubagentStop",
        "PreCompact", "UserPromptSubmit", "gemini-extension",
    ]

    def _token_block(self):
        """The fenced token block itself — not the whole document, so a token that
        also appears elsewhere (CLAUDE_PLUGIN_ROOT is in the verify command) cannot
        satisfy the sweep definition by accident."""
        m = re.search(r"\*Tokens \((\d+) alternatives[^)]*\):\*\s*\n```\n(.*?)```",
                      self.body, re.S)
        self.assertIsNotNone(m, "the sweep's token block is missing")
        declared = int(m.group(1))
        tokens = m.group(2).split()
        return declared, tokens

    def test_sweep_token_block_is_exact(self):
        declared, tokens = self._token_block()
        # the declared count, the actual count, and the frozen set must all agree —
        # a removed token, an added token, or a stale count each fails
        self.assertEqual(declared, 23, "declared alternative count drifted")
        self.assertEqual(len(tokens), 23, f"token block holds {len(tokens)} tokens")
        self.assertEqual(sorted(tokens), sorted(self.SWEEP_TOKENS),
                         "token block differs from the frozen sweep set")

    def test_sweep_scope_is_exact(self):
        # the scope sentence, verbatim: EXCLUDING (not INCLUDING) those three trees
        self.assertIn(
            "every file in `git ls-files` EXCLUDING the `tests/`, `docs/`, and "
            "`.github/` trees", self.flat)

    def test_propagation_rules(self):
        for kind in ("SOURCE", "DOCUMENTARY", "ENCODED", "OPERATIONAL"):
            self.assertIn(f"**{kind}**", self.body, f"class missing: {kind}")
        self.assertIn("code-change-required", self.body)
        self.assertRegex(self.flat, r"(?i)never edited\*{0,2} by this command")
        # both citation forms (D7.4)
        self.assertIn("conventions-<tool> §N", self.body)
        self.assertIn("Markdown link to the overlay", self.flat)

    def test_verify_step_fully_pinned(self):
        self.assertIn(
            'python3 "${CLAUDE_PLUGIN_ROOT}/bin/vibe-check" "${CLAUDE_PLUGIN_ROOT}"',
            self.body)
        self.assertRegex(self.flat, r"(?i)exit status")


#: Every binding rule from the frozen plan, each pinned to an EXACT phrase in the
#: artifact that owns it. Adding a rule to the plan means adding a row here; deleting a
#: rule from an artifact fails the corresponding case. Phrases are matched against
#: whitespace-squashed text so line wrapping cannot mask a deletion.
REQUIRED_CLAUSES = [
    # (rule, file-key, exact phrase)
    ("D1 default", "command", "`all` (the default)"),
    ("D1 all selects three", "command", "selects those three"),
    ("D1 floor excluded", "command", "`skills/conventions/` floor is never a target"),
    ("D2 dry-run default", "command", "`--dry-run` (the default)"),
    ("D2 actionable set", "command", "FIX, REMOVE, ADD, or RESOLVED"),
    ("D2 retiring CONFIRM", "command", "CONFIRM that retires a correction note"),
    ("D4 high grade", "command", "`high` is an explicit first-party statement"),
    ("D4 medium grade", "command", "`medium` is first-party but indirect"),
    ("D4 orthogonality", "command", "grade the evidence, never the tag"),
    ("D4 not-a-grade", "command", "Insufficient evidence is not a grade"),
    ("D4 threshold default", "command", "**default `medium`**"),
    ("D5 every correction", "command", "Every applied correction carries a note"),
    ("D5 run-date semantics", "command",
     "is the ISO date of the run that writes it"),
    ("D5 body placement", "command",
     "the line immediately following the corrected or added claim"),
    ("D5 frontmatter placement", "command",
     "the note never goes inside the YAML block"),
    ("D5 retirement condition", "command",
     "`CONFIRM` at `high` confidence against a source dated at or after the note's own"),
    ("D5 one note per claim", "command", "one note per claim, never accumulating"),
    ("D6 label-only distinction", "command", "not full URLs"),
    ("D7 case sensitivity", "command", "case-sensitively"),
    ("D7 scope", "command",
     "every file in `git ls-files` EXCLUDING the `tests/`, `docs/`, and `.github/` trees"),
    ("D7 required targets", "command", "with the citing line quoted"),
    ("D7 never edited", "command", "**never edited** by this command"),
    ("D8 verify target", "command",
     'python3 "${CLAUDE_PLUGIN_ROOT}/bin/vibe-check" "${CLAUDE_PLUGIN_ROOT}"'),
    ("D9 first-party only", "agent", "**First-party only.**"),
    ("D9 page date", "agent", "plus the page's own date when it carries one"),
    ("D9 graded quote+URL", "agent",
     "Every graded row (`high` or `medium`) must quote the source statement it relied "
     "on together with that URL"),
    ("D9 unclassified routing", "agent",
     "a row without a quotable statement and URL is not graded evidence and belongs in "
     "`UNCLASSIFIED`"),
    ("D9 research not apply", "agent",
     "You research and report; applying corrections belongs to"),
    # --- rows added after the round-3 probe pass named them (each was deletable)
    ("D1 token->overlay mapping", "command",
     "`claude`, `codex`, and `antigravity` each select one overlay skill"),
    ("D3 RESOLVED action", "command", "retire the hedge, state the settled fact"),
    ("D5 REMOVE note placement", "command",
     "for REMOVE in place of the deleted claim"),
    ("D7 documentary changed-fact only", "command",
     "updated ONLY when the fact it restates is one this run changed"),
    ("D7 citation changed-section only", "command",
     "reported as REQUIRED targets ONLY when the cited section is one this run changed"),
]

#: Frontmatter values the frozen plan fixes exactly (a tier alias, never a pinned id).
REQUIRED_FRONTMATTER = [("agent", "model", "sonnet")]


class RequiredClauses(unittest.TestCase):
    """One case per binding rule — the table above is the contract's inventory."""

    def test_every_rule_is_present(self):
        sources = {"command": squash(COMMAND.read_text(encoding="utf-8")),
                   "agent": squash(AGENT.read_text(encoding="utf-8"))}
        for rule, key, phrase in REQUIRED_CLAUSES:
            with self.subTest(rule=rule):
                self.assertIn(phrase, sources[key],
                              f"{rule}: required clause missing from {key}")

    def test_required_frontmatter_values(self):
        # D9 fixes the agent at sonnet-class; haiku or opus is a contract change
        sources = {"agent": AGENT.read_text(encoding="utf-8"),
                   "command": COMMAND.read_text(encoding="utf-8")}
        for key, field, value in REQUIRED_FRONTMATTER:
            with self.subTest(field=field):
                self.assertRegex(sources[key], rf"(?m)^{field}: {value}$",
                                 f"{key} {field} must be {value}")

    def test_worksheet_note_schema_matches_the_command(self):
        # the worksheet must not document a superseded schema (step-9 finding 2)
        worksheet = (FIX / "README.md").read_text(encoding="utf-8")
        self.assertIn("<source label>, <URL> (confidence: high|medium)", worksheet)
        self.assertNotIn("<tag> — <source label> (confidence", worksheet)


class ClosedSets(unittest.TestCase):
    """Every set the contract closes is compared by EQUALITY, so an addition, a swap,
    a duplicate, or a reordering fails — membership checks could see none of those."""

    def setUp(self):
        self.command = COMMAND.read_text(encoding="utf-8")
        self.agent = AGENT.read_text(encoding="utf-8")

    def test_propagation_classes_are_exactly_four(self):
        classes = re.findall(r"^- \*\*([A-Z]+)\*\* —", self.command, re.M)
        self.assertEqual(classes,
                         ["SOURCE", "DOCUMENTARY", "ENCODED", "OPERATIONAL"],
                         "the propagation classes are a closed, ordered set of four")

    def test_agent_tag_table_matches_d3_exactly(self):
        tags = [m.group(1) for m in
                re.finditer(r"^\| \d \| `([A-Z]+)` \|", self.agent, re.M)]
        self.assertEqual(tags, [row[1].strip("`") for row in
                                CommandContract.D3_TABLE],
                         "the agent's tag table must carry exactly D3's five tags, "
                         "in D3's order")

    def test_confidence_vocabulary_is_exactly_high_and_medium(self):
        # the graded vocabulary is closed: a `low` grade is a contract change, since
        # insufficient evidence routes to UNCLASSIFIED instead
        grades = set(re.findall(r"`(high|medium|low)`", self.command))
        self.assertEqual(grades, {"high", "medium"},
                         f"confidence grades must be exactly high/medium, got {grades}")
        self.assertNotRegex(self.command, r"(?i)confidence[^.]*\blow\b")
        reasons = set(re.findall(r"`(source-[a-z]+)`", self.command))
        self.assertEqual(reasons, {"source-silent", "source-conflict"})

    def test_targets_and_modes_are_closed(self):
        modes = set(re.findall(r"`(--dry-run|--apply)`", self.command))
        self.assertEqual(modes, {"--dry-run", "--apply"})
        thresholds = set(re.findall(r"--min-confidence (high|medium)\b", self.command))
        self.assertTrue(thresholds <= {"high", "medium"}, thresholds)


class FreshnessNormalization(unittest.TestCase):
    def test_exact_canonical_lines(self):
        for name, path in OVERLAYS.items():
            with self.subTest(overlay=name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(CANONICAL[name], squash(text))
                self.assertEqual(text.count("**Spec freshness:**"), 1)
                self.assertIn(PRESERVED[name], squash(text))

    def test_canonical_line_is_first_content_after_h1(self):
        for name, path in OVERLAYS.items():
            with self.subTest(overlay=name):
                lines = path.read_text(encoding="utf-8").splitlines()
                h1 = next(i for i, l in enumerate(lines) if l.startswith("# "))
                after = [l for l in lines[h1 + 1:] if l.strip()]
                self.assertTrue(after[0].startswith("**Spec freshness:**"),
                                f"{name}: first content after H1 is {after[0][:60]!r}")

    def test_no_superseded_marker_and_no_dated_description(self):
        for name, path in OVERLAYS.items():
            with self.subTest(overlay=name):
                text = path.read_text(encoding="utf-8")
                for old in SUPERSEDED:
                    self.assertNotIn(old, text)
                description = next(
                    (l for l in text.splitlines() if l.startswith("description:")), "")
                self.assertNotRegex(description, r"\d{4}-\d{2}-\d{2}")


class FixtureOracle(unittest.TestCase):
    def test_fixture_seeds_present(self):
        overlay = (FIX / "stale-overlay" / "SKILL.md").read_text(encoding="utf-8")
        for n in range(1, 8):
            self.assertIn(f"SEED {n}", overlay)
        self.assertTrue((FIX / "stale-overlay" / "consumer-linked.md").is_file())
        self.assertTrue((FIX / "stale-overlay" / "consumer-uncited.md").is_file())

    def test_recorded_dry_run_matches_the_oracle_one_to_one(self):
        self.assertTrue(RECORDED.is_file(),
                        "the recorded manual dry run is missing")
        recorded = RECORDED.read_text(encoding="utf-8")
        self.assertRegex(recorded.splitlines()[0] + recorded.splitlines()[1],
                         r"(?i)provenance|recorded")
        self.assertIn("--overlay-root", recorded)
        expected_rows = report_rows(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(len(expected_rows), 7, "the oracle must carry seven seeds")
        recorded_rows = report_rows(recorded)
        self.assertEqual(recorded_rows, expected_rows,
                         "recorded run drifted from the hand-authored oracle")
        # every row well-formed: a known tag, and a confidence/reason from the
        # closed vocabulary — a malformed or invented row fails here
        allowed = set(TAGS) | {"UNCLASSIFIED"}
        vocab = {"high", "medium", "source-silent", "source-conflict"}
        for seed, section, tag, conf in recorded_rows:
            self.assertIn(tag, allowed, f"seed {seed}: unknown tag {tag!r}")
            self.assertIn(conf, vocab, f"seed {seed}: bad confidence/reason {conf!r}")
            self.assertTrue(section.startswith("§"), f"seed {seed}: section {section!r}")
        self.assertEqual(len({r[0] for r in recorded_rows}), 7, "seeds must be unique")

    def test_dry_run_wrote_nothing(self):
        recorded = squash(RECORDED.read_text(encoding="utf-8"))
        self.assertRegex(recorded, r"(?i)no file (was )?written|dry run: no write")
        self.assertRegex(recorded, r"(?i)no verify|verify skipped")


class ThresholdRegressions(unittest.TestCase):
    """The two cases the plan review required (step-6 finding 6)."""

    def test_default_is_medium(self):
        flat = squash(COMMAND.read_text(encoding="utf-8"))
        self.assertIn("(**default `medium`**", flat)

    def test_all_medium_under_high_takes_no_change_branch(self):
        flat = squash(COMMAND.read_text(encoding="utf-8"))
        self.assertRegex(
            flat,
            r"(?i)all-medium run under `--min-confidence high` applies nothing")
        self.assertRegex(flat, r"(?i)no write, no bump, no propagation, no verify")


if __name__ == "__main__":
    unittest.main()
