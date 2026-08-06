# SPDX-License-Identifier: ISC
"""E3.9 (vibe-34) acceptance: /vibe-suite:security-scan + security-scanner.

Rung 0/1 pins the contracts, the shared-artifact edits, and the fixture oracle. Live
scanning is the agent's judgment lane — CI makes no model call. What runs mechanically is
the one-to-one comparison of a RECORDED manual scan against the independently hand-authored
expectation, plus schema validation of that recorded output.

The scanner's report is one COMPOSITE contract: the skill says the audit-report section
carries a severity table and a six-column Findings table, and that the scanner's report
"additionally" carries surface counts and Risk level. "Additionally" is cumulative, so the
agent owes all of it, and the two findings renderings must agree row for row.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMAND = REPO_ROOT / "commands" / "security-scan.md"
AGENT = REPO_ROOT / "agents" / "security-scanner.md"
SPEC = REPO_ROOT / ".vibe-test" / "security-scanner.spec.md"
SKILL = REPO_ROOT / "skills" / "security" / "SKILL.md"
CORE = REPO_ROOT / "skills" / "vibe-core" / "SKILL.md"
SCHEMA = REPO_ROOT / "schemas" / "audit-output.schema.json"
VALIDATOR = REPO_ROOT / "scripts" / "validate_audit_output.py"
FIX = REPO_ROOT / "tests" / "fixtures" / "security-scan"
EXPECTED = FIX / "expected-findings.md"
RECORDED = FIX / "recorded-scan.md"

IDENTITY = "vibe-suite:security-scanner"
BANNERS = ["SECURITY GATE: PASSED", "SECURITY GATE: REVIEW NEEDED",
           "SECURITY GATE: BLOCKED"]
RULE = "─" * 60

#: D2c — Risk level grades the highest severity present; the gate is coarser, collapsing
#: Low into PASS and both High and Critical into BLOCK.
RISK_LADDER = [
    ("none", "CLEAR", "PASS"),
    ("Low", "LOW", "PASS"),
    ("Medium", "MEDIUM", "REVIEW"),
    ("High", "HIGH", "BLOCK"),
    ("Critical", "CRITICAL", "BLOCK"),
]


def squash(text):
    return re.sub(r"\s+", " ", text)


def table_rows(text):
    """Findings rows: six columns, first cell an integer ordinal.

    The width matters — the severity-counts table also leads with a digit, and accepting
    it would silently add a phantom finding to every comparison.
    """
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == 6 and cells[0].isdigit():
            rows.append(cells)
    return rows


def skill_pattern_names():
    """The permitted pattern names, PARSED from the security skill.

    Derived rather than restated: the skill is the single pattern DB (F5.2), so a name the
    scanner permits but the skill does not carry would be exactly the drift F5.2 forbids.
    """
    text = SKILL.read_text(encoding="utf-8")

    def section(start, end):
        i = text.index(start)
        return text[i:text.index(end, i)]

    names = []
    for start, end in (("### Critical patterns", "### High patterns"),
                       ("### High patterns", "### Medium patterns"),
                       ("### Medium patterns", "## MCP configuration"),
                       ("## MCP configuration", "## Hook safety")):
        for line in section(start, end).splitlines():
            if line.startswith("| ") and "---" not in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if cells and cells[0] not in ("Pattern", "Check"):
                    names.append(cells[0])
    for start, end in (("## Hook safety", "## Dependency supply chain"),
                       ("## Dependency supply chain", "## Prompt injection surfaces"),
                       ("## Prompt injection surfaces", "## Severity definitions")):
        names.extend(re.findall(r"(?m)^- \*\*(.+?)\*\* — ", section(start, end)))
    return names


#: The 40 permitted pattern names, frozen. Parsed from the skill at test time and compared
#: to this set: a count alone cannot see a rename, and set equality alone cannot see a check
#: added without a name — both failures are tested separately below.
FROZEN_PATTERN_NAMES = {
    "Pipe to shell", "Eval with variables", "Reverse shell", "Base64 decode and execute",
    "SSH key exfiltration", "Token exfiltration", "subprocess with shell=True",
    "os.system", "Dynamic require/import", "Dynamic new Function",
    "File write outside repo", "sudo", "PATH modification", "Network calls",
    "Environment access", "File reads outside repo", "Runtime package install",
    "Shell exec helpers",
    "Remote server (`url` not localhost)", "Server domain not on the safe list",
    "Broad `permissions` (wildcard or extensive grant)", "`fs` / `filesystem` capability",
    "`shell` / exec capability", "Remote server missing `auth`",
    "Unpinned server (`npx -y`, or a versionless remote)",
    "Hook references a script", "Hook interpolates unsanitized input",
    "Hook without a tool filter", "Hook writes on every tool call",
    "Hook makes network calls",
    "postinstall script", "preinstall script", "Git-URL dependency", "Unpinned version",
    "Git-protocol Python dependency", "Unpinned Python dependency",
    "Direct HTTP download URL",
    "File content into Bash", "Unsanitized command arguments into Bash",
    "Hook template expansion with user-controlled values",
}


#: SHA-256 of the two contract texts. The clause tests above assert a required sentence is
#: PRESENT, and a contract can be broken by ADDING one that contradicts it while every
#: required sentence stays put — a dash permitted in substantive rows, [GOOD] allowed beside
#: findings, PASS allowed for a Medium-only report. Presence checks cannot see that; only
#: pinning the text can. This lives in test code, not a fixture, so re-blessing a fixture
#: does not re-bless it.
#: Re-blessed by E4.5 (vibe-39), which added the --second-opinion lane. The clause tests above were
#: updated FIRST, in the same commit, so this hash was recomputed over text a clause test already
#: accepts -- re-blessing before that would silence the outer layer while the inner one still failed.
#: Re-blessed again by E7.4 (vibe-56): the AC-7 release gate scores every shipped artifact at
#: Strict 80, and this agent scored 75 -- missing the mandatory <example> blocks (R09, -15) and
#: an output-format heading (R12, -10). Two examples were added and "## Step 3 -- report" became
#: "## Step 3 -- report (output format)". NO contract sentence was added, removed or reworded:
#: every clause test above passed unchanged BEFORE this hash was recomputed, which is the same
#: ordering vibe-39 established.
CONTRACT_SHA256 = {
    "agent": "5de90ababd4d9beb6a6409134e83f7cf94261c733216446bb7c6d36504d18d50",
    "command": "f26d3f99c6b4aaff471bc9b642d9cd91f30b6a72deba871666cc89eac338e13f",
}


class FrozenContractSeal(unittest.TestCase):
    def test_contract_texts_are_sealed(self):
        for key, path in (("agent", AGENT), ("command", COMMAND)):
            with self.subTest(artifact=key):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), CONTRACT_SHA256[key],
                    f"{key} text changed. Nothing may be added, removed or reworded in a "
                    "frozen contract without updating CONTRACT_SHA256 in the same commit — "
                    "see the clause tests for what each rule requires.")


#: SHA-256 of the two security-skill SECTIONS this item consumes. The skill is the declared
#: single source of truth for the report shape and the gate ladder, so a contradicting
#: sentence added THERE defeats the scanner's contract without touching the scanner — and
#: the agent/command seals cannot see it.
#:
#: Only these two sections are sealed, not the file. The skill is a living pattern database
#: that other items extend; freezing it whole would make every future pattern addition fail
#: this item's tests. What is frozen is exactly what this item depends on.
SKILL_SECTION_SHA256 = {
    "report-contract": "ddd0adabd3f336ec5ed7c51c4c9699e6ef480ab4701825c6d91574cd128e3127",
    "risk-gate": "666ffa37b979d12183e8f74ea79792a7aa6aa020f2299f307b1f2a661d3fc1d6",
}

SKILL_SECTION_BOUNDS = {
    "report-contract": ("## Report contract", "## Risk gate and banner semantics"),
    "risk-gate": ("## Risk gate and banner semantics", "## Related skills"),
}


class SkillSectionSeal(unittest.TestCase):
    def test_consumed_sections_are_sealed(self):
        text = SKILL.read_text(encoding="utf-8")
        for key, (start, end) in SKILL_SECTION_BOUNDS.items():
            with self.subTest(section=key):
                self.assertIn(start, text)
                begin = text.index(start)
                body = text[begin:text.index(end, begin)]
                self.assertEqual(
                    hashlib.sha256(body.encode()).hexdigest(),
                    SKILL_SECTION_SHA256[key],
                    f"the skill's {key} section changed. It is the source of truth the "
                    "scanner consumes, so a change here is a contract change — update "
                    "SKILL_SECTION_SHA256 in the same commit.")


class Deliverables(unittest.TestCase):
    def test_artifacts_and_registration(self):
        self.assertTrue(COMMAND.is_file())
        self.assertTrue(AGENT.is_file())
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("./commands/security-scan.md", manifest["commands"])
        self.assertIn("./agents/security-scanner.md", manifest["agents"])
        self.assertGreaterEqual(len(manifest["commands"]), 19)
        self.assertGreaterEqual(len(manifest["agents"]), 8)

    def test_agent_frontmatter_matches_its_shipped_spec(self):
        body = AGENT.read_text(encoding="utf-8")
        # the source's description is capability-style ("Scan NL programming plugins…");
        # the shipped E3.6 spec requires trigger style, so the source supplies behaviour,
        # not text
        self.assertRegex(body, r"(?m)^description: Use when")
        self.assertRegex(body, r"(?m)^model: (haiku|sonnet|opus)$")
        self.assertRegex(body, r"(?m)^tools: Read, Glob, Grep$")
        spec = SPEC.read_text(encoding="utf-8")
        self.assertIn("execution-surface inventory", spec)
        self.assertIn("risk-level classification", spec)

    def test_agent_has_no_mutation_tool(self):
        # the spec's non-trigger "fix the dangerous hook" puts mutation out of contract
        tools = re.search(r"(?m)^tools: (.*)$", AGENT.read_text(encoding="utf-8")).group(1)
        for forbidden in ("Write", "Edit", "Bash", "NotebookEdit"):
            self.assertNotIn(forbidden, tools, f"scanner must not carry {forbidden}")

    def test_no_deprecated_vocabulary(self):
        for path in (COMMAND, AGENT):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"(?i)\bimplement\b")


class CommandContract(unittest.TestCase):
    def setUp(self):
        self.flat = squash(COMMAND.read_text(encoding="utf-8"))

    def test_precondition_and_error_strings(self):
        for marker in (".claude-plugin/", "agents/", "commands/", "skills/", "hooks/",
                       "scripts/"):
            self.assertIn(marker, self.flat)
        self.assertIn("Directory not found: {path}", self.flat)
        self.assertIn("Not a Claude Code plugin directory", self.flat)

    def test_body_is_verbatim_and_surrounding_sections_are_enumerated(self):
        """E4.5 (vibe-39) narrowed this clause, and the rewrite ADDS assertions rather than trading
        one for another.

        The old rule was `verbatim` + "append nothing else". The second phrase forbade an
        unenumerated everything, which also forbade F9.5's diagnostic header -- a run-level
        disclosure the fallback partial requires to OPEN the report. The guarantee the phrase was
        protecting is that nobody edits the scanner's findings, so it is now stated as
        "insert nothing into it" plus an explicit enumeration of what may surround the body, in a
        fixed order. Enumerating is tighter than forbidding-everything, not looser.
        """
        self.assertIn("verbatim", self.flat)
        self.assertIn("insert nothing into it", self.flat)
        for part in ("diagnostic header", "Second opinion", "SECURITY GATE"):
            self.assertIn(part, self.flat, f"the report's parts must be enumerated: {part}")
        body = self.flat
        header_at = body.index("diagnostic header")
        report_at = body.index("security-scanner agent report")
        opinion_at = body.index("## Second opinion")
        banner_at = body.index("SECURITY GATE:")
        self.assertLess(header_at, report_at, "the F9.5 header opens the report")
        self.assertLess(report_at, opinion_at, "the second opinion follows the verbatim body")
        self.assertLess(opinion_at, banner_at, "the banner is last")
        self.assertIn("Never mutates the target", self.flat)

    def test_banner_strings_and_rule(self):
        body = COMMAND.read_text(encoding="utf-8")
        for banner in BANNERS:
            self.assertIn(banner, body, f"missing banner: {banner}")
        self.assertIn(RULE, body, "the banner is framed by 60 box-drawing characters")

    def test_ladder_is_ordered_not_a_set_of_conditions(self):
        # a Medium-only report satisfies both "no Critical or High" and "only Medium";
        # the fix is an ORDER, so the command must state one
        self.assertIn("first match wins", self.flat)
        self.assertRegex(self.flat, r"BLOCK on any Critical or High.*"
                                    r"otherwise REVIEW on any Medium.*otherwise PASS")

    def test_disagreement_branch_declines_to_gate(self):
        self.assertIn("Scan inconsistent: agent recommended <X>, findings imply <Y>. "
                      "Not gating; rerun /vibe-suite:security-scan.", self.flat)
        self.assertIn("print **no banner**", self.flat)

    def test_empty_report_is_a_failure_not_a_pass(self):
        self.assertIn("An empty agent report is a failed scan, not a clean one", self.flat)


class CompositeReport(unittest.TestCase):
    """D2 — seven parts, and the two findings renderings must agree."""

    def setUp(self):
        self.agent = AGENT.read_text(encoding="utf-8")
        self.flat = squash(self.agent)

    def test_qualified_header(self):
        self.assertIn(f"## [Agent: {IDENTITY}] Findings", self.agent)

    def test_all_seven_parts_are_stated(self):
        for part in ("Severity counts", "| # | Severity | File | Line | Pattern | "
                     "Description |", "Surface inventory", "Risk level", "Recommendation",
                     "Exploit scenario", "[GOOD]"):
            self.assertIn(part, self.agent, f"composite is missing: {part}")

    def test_six_fields_plus_exploit(self):
        for field in ("File", "Observation", "Severity", "Evidence", "Proposed change",
                      "Tradeoff", "Exploit scenario"):
            self.assertIn(f"**{field}**", self.agent, f"missing six-field entry: {field}")

    def test_observation_syntax_makes_pattern_derivable(self):
        # free prose would leave `Pattern` unbound; the em-dash split is what makes the
        # summary table derivable instead of re-judged
        self.assertIn("`<Pattern name> — <prose>`", self.agent)
        self.assertIn("the text before the", self.flat)

    def test_risk_ladder_rows(self):
        for highest, risk, rec in RISK_LADDER:
            with self.subTest(highest=highest):
                self.assertRegex(
                    self.flat,
                    rf"\|\s*{re.escape(highest)}\s*\|\s*`?{risk}`?\s*\|\s*`?{rec}`?\s*\|",
                    f"missing risk row: {highest} -> {risk}/{rec}")

    def test_good_sentinel_row_and_its_exemption(self):
        self.assertIn("| 1 | [GOOD] | — | — | — |", self.agent)
        self.assertIn("exclusive", self.flat)
        self.assertIn("cannot appear beside a substantive finding", self.flat)
        # the exemption must be CONFINED — otherwise a substantive finding could carry
        # `—` where its location should be, and nothing would object
        self.assertIn("Only a `[GOOD]` row may carry `—` in File, Line or Pattern.",
                      self.agent)
        self.assertRegex(self.flat, r"Every row whose Severity is .*owes a real location "
                                    r"and a real pattern name")

    def test_summary_table_has_its_heading(self):
        # the heading is named in prose AND shown in the example block; asserting the bare
        # string passes when either survives, so bind them together as one unit
        self.assertIn("under the heading `### Findings`", self.agent)
        self.assertRegex(
            self.agent,
            r"### Findings\n\n\| # \| Severity \| File \| Line \| Pattern \| Description \|",
            "the example must show the heading immediately above the table")

    def test_good_entry_has_a_six_field_shape(self):
        # the sentinel is a finding, not a special case bolted on; it owes the same fields
        good = self.agent[self.agent.index("## Zero findings"):]
        for field in ("**File**", "**Observation**", "**Severity**", "**Evidence**",
                      "**Proposed change**", "**Tradeoff**"):
            self.assertIn(field, good, f"the [GOOD] entry must define {field}")
        self.assertIn("no Exploit scenario", good)

    def test_both_zero_cases_are_distinguished(self):
        self.assertRegex(
            self.flat,
            r"all zeros when discovery found no surfaces, and non-zero when it found "
            r"surfaces but nothing to report")


class SkillIsTheSingleSourceOfTruth(unittest.TestCase):
    """Cross-artifact equalities. Each shared artifact this item edits gets an assertion,
    not a claim of coverage."""

    def test_agent_references_the_skill_by_literal_path(self):
        # E4.2's acceptance is a grep test over both security front-ends
        self.assertIn("skills/security/SKILL.md", AGENT.read_text(encoding="utf-8"))

    def test_agent_inlines_untrusted_input_and_references_redaction(self):
        flat = squash(AGENT.read_text(encoding="utf-8"))
        self.assertIn("never instructions", flat)   # F9.2 requires inlining, per agent
        self.assertIn("first four and last four", flat)
        self.assertIn("vibe-core", flat)            # referenced, never restated

    def test_permitted_pattern_names_equal_the_frozen_set(self):
        # a count is not a set: renaming an unused check keeps 39 and would pass, so the
        # names themselves are frozen here and compared by equality
        self.assertEqual(set(skill_pattern_names()), FROZEN_PATTERN_NAMES)
        self.assertEqual(len(skill_pattern_names()), 40, "names must not duplicate")

    def test_no_check_in_any_family_is_left_unnamed(self):
        """Adding an unnamed bullet to a prose family previously passed everything.

        The count stays 39 because an unnamed check contributes nothing to the parse — so
        the gap is invisible to a count and to set equality alike. Only reading every
        bullet in those families catches it.
        """
        text = SKILL.read_text(encoding="utf-8")

        def section(start, end):
            i = text.index(start)
            return text[i:text.index(end, i)]

        for start, end in (("## Hook safety", "## Dependency supply chain"),
                           ("## Dependency supply chain", "## Prompt injection surfaces"),
                           ("## Prompt injection surfaces", "## Severity definitions")):
            body = section(start, end)
            for line in body.splitlines():
                if line.startswith("- ") and "→" in line:
                    with self.subTest(family=start, check=line[:48]):
                        self.assertRegex(
                            line, r"^- \*\*[^*]+\*\* — ",
                            "every check must carry a name the scanner can cite")

    def test_scanner_permission_rule_is_closed(self):
        # the rule itself was untested: replacing it with "any name" passed everything,
        # because only the RECORDED patterns were checked against the skill
        self.assertIn(
            "MUST be one of the\n  check names enumerated in `skills/security/SKILL.md`, "
            "and no other value is permitted.",
            AGENT.read_text(encoding="utf-8"))

    def test_scanner_permits_exactly_the_skill_names(self):
        # the scanner's permitted set is DERIVED from the skill at test time; if it were a
        # separate list in the agent, the two could drift — which is the F5.2 failure
        recorded_patterns = {row[4] for row in table_rows(RECORDED.read_text(encoding="utf-8"))
                             if row[1] != "[GOOD]"}
        self.assertTrue(recorded_patterns)
        self.assertLessEqual(recorded_patterns, FROZEN_PATTERN_NAMES)

    def test_every_recorded_pattern_is_a_skill_name(self):
        permitted = set(skill_pattern_names())
        for row in table_rows(RECORDED.read_text(encoding="utf-8")):
            with self.subTest(row=row[0]):
                if row[1] == "[GOOD]":
                    continue
                self.assertIn(row[4], permitted,
                              f"pattern {row[4]!r} is not a name the skill carries")

    def test_vibe_core_lists_exactly_the_schema_identities(self):
        # comparing only the English count let the list and the schema drift; the IDENTITIES
        # are what the variant rules key on, so they are what must match
        schema_enum = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]["agent"]["enum"]
        core = CORE.read_text(encoding="utf-8")
        listed = re.findall(r"(?m)^- `(vibe-suite:[a-z-]+)`$", core)
        self.assertEqual(listed, schema_enum,
                         "vibe-core must list exactly the schema's agent enum, in order")
        self.assertIn("seven canonical names", core)

    def test_security_skill_carries_the_same_ordered_ladder(self):
        flat = squash(SKILL.read_text(encoding="utf-8"))
        self.assertIn("ordered ladder, first match wins", flat)
        self.assertRegex(flat, r"1\. \*\*BLOCK\*\*.*2\. \*\*REVIEW\*\*.*3\. \*\*PASS\*\*")


class RecordedScanAgainstTheOracle(unittest.TestCase):
    """The judgment lane's evidence, compared mechanically."""

    def setUp(self):
        self.expected = table_rows(EXPECTED.read_text(encoding="utf-8"))
        self.recorded = table_rows(RECORDED.read_text(encoding="utf-8"))

    def test_provenance_header(self):
        text = RECORDED.read_text(encoding="utf-8")
        for field in ("**Date:**", "**Model:**", "**Command:**", "**Target:**"):
            self.assertIn(field, text, f"recording must state {field}")
        self.assertIn("/vibe-suite:security-scan", text)

    def test_one_to_one_with_no_extras(self):
        self.assertEqual(len(self.recorded), len(self.expected),
                         "the recording must contain exactly the expected findings")
        for exp, got in zip(self.expected, self.recorded):
            with self.subTest(row=exp[0]):
                self.assertEqual(got, exp)

    def test_both_renderings_agree(self):
        text = RECORDED.read_text(encoding="utf-8")
        six_field = re.findall(r"\*\*File\*\* `([^`]+)`\n\*\*Observation\*\* (.+)", text)
        self.assertEqual(len(six_field), len(self.recorded),
                         "the six-field and summary renderings must have equal row counts")
        severities = re.findall(r"(?m)^\*\*Severity\*\* (\S+)$", text)
        self.assertEqual(len(severities), len(self.recorded))
        for ordinal, ((loc, observation), row, severity) in enumerate(
                zip(six_field, self.recorded, severities), start=1):
            with self.subTest(row=row[0]):
                # ordinal and severity were previously unbound, so the two renderings
                # could disagree in exactly the columns the summary exists to carry
                self.assertEqual(row[0], str(ordinal), "summary rows must be in order")
                self.assertEqual(row[1], severity)
                path, _, line = loc.rpartition(":")
                self.assertEqual(row[2], path)
                self.assertEqual(row[3], line)
                pattern, _, description = observation.partition(" — ")
                self.assertEqual(row[4], pattern)
                self.assertEqual(row[5], description)

    def test_suppressions_are_absent(self):
        rows = self.recorded
        # each is a distinct rule with its own seed; an absence assertion is the only way
        # to test a drop
        self.assertFalse([r for r in rows if r[2] == "scripts/install.sh" and r[3] == "6"],
                         "echo-wrapped match must be dropped")
        self.assertFalse([r for r in rows if r[2] == "scripts/install.sh" and r[3] == "10"],
                         "heredoc body match must be dropped")
        self.assertFalse([r for r in rows if r[2] == "package.json" and r[3] == "3"],
                         "unpinned dependency must be suppressed by the lockfile")

    def test_md_finding_is_capped_not_dropped(self):
        capped = [r for r in self.recorded if r[2] == "commands/notes.md"]
        self.assertEqual(len(capped), 1, "the .md match is capped, not dropped")
        self.assertEqual(capped[0][1], "[LOW]")

    def test_derived_values_follow_the_ladder(self):
        text = RECORDED.read_text(encoding="utf-8")
        self.assertIn("Risk level: CRITICAL", text)
        self.assertIn("Recommendation: BLOCK", text)
        self.assertEqual(len(re.findall(r"(?m)^Recommendation: ", text)), 1,
                         "exactly one Recommendation line")


class SchemaConformance(unittest.TestCase):
    """Validate the EMITTED output, not the hand oracle — and prove the extended variant
    branch actually keys on the new identity."""

    def _serialize(self, drop_exploit=False, agent=IDENTITY):
        text = RECORDED.read_text(encoding="utf-8")
        findings = []
        blocks = re.findall(
            r"\*\*File\*\* `([^`]+)`\n\*\*Observation\*\* (.+)\n\*\*Severity\*\* (\S+)\n"
            r"\*\*Evidence\*\* (.+)\n\*\*Proposed change\*\* (.+)\n\*\*Tradeoff\*\* (.+)\n"
            r"\*\*Exploit scenario\*\* ((?:.|\n)+?)(?=\n\n)", text)
        self.assertTrue(blocks, "no six-field findings parsed from the recording")
        for loc, observation, severity, evidence, change, tradeoff, exploit in blocks:
            entry = {
                "file": loc, "observation": observation, "severity": severity,
                "evidence": evidence, "proposed_change": change, "tradeoff": tradeoff,
            }
            if not drop_exploit:
                entry["exploit_scenario"] = " ".join(exploit.split())
            findings.append(entry)
        return {"agent": agent, "findings": findings}

    def _validate(self, payload):
        # the suite's own validator, invoked exactly as CI would — reimplementing schema
        # checking here would test my reimplementation, not the contract
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            report = handle.name
        try:
            proc = subprocess.run([sys.executable, str(VALIDATOR), report],
                                  capture_output=True, text=True, timeout=60)
            return proc.returncode
        finally:
            os.unlink(report)

    def test_identity_is_registered(self):
        enum = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]["agent"]["enum"]
        self.assertIn(IDENTITY, enum)

    def test_security_variant_keys_on_both_identities(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        branches = [b for b in schema.get("allOf", [])
                    if IDENTITY in b.get("if", {}).get("properties", {})
                    .get("agent", {}).get("enum", [])]
        self.assertEqual(len(branches), 1,
                         "the scanner must inherit the security variant, not bypass it")
        self.assertIn("vibe-suite:security",
                      branches[0]["if"]["properties"]["agent"]["enum"])

    def test_recorded_output_validates(self):
        self.assertEqual(self._validate(self._serialize()), 0,
                         "the emitted report must satisfy the schema")

    def test_missing_exploit_scenario_is_rejected(self):
        self.assertNotEqual(self._validate(self._serialize(drop_exploit=True)), 0,
                            "the security variant must require an Exploit scenario")

    def test_unqualified_identity_is_rejected(self):
        self.assertNotEqual(self._validate(self._serialize(agent="security-scanner")), 0,
                            "a bare name would bypass the variant rules")


#: SHA-256 of every frozen fixture, keyed by path relative to the fixture root. The seals
#: close the set; the tests above bind the content. Both are needed: a seal alone permits a
#: meaningless re-bless, and content assertions alone permit additions.
FIXTURE_SHA256 = {
    "README.md":
        "7192b912ecb308c4a46951edc5e1e82382912d522bedd7851556733086af071a",
    "expected-findings.md":
        "d9c77b16a5d139fad12751f59f2872c84bf26b9a96176c3bf5f68a835138d256",
    "recorded-scan.md":
        "b6f0846fe9ce125a2e237cc75060b55962b778cf65b52cef042cf1b3e2615edf",
    "seeded-plugin/.claude-plugin/plugin.json":
        "0ea21b8045f2f6276c6726dfbc633191262bcdea8913642c760547829e088ecc",
    "seeded-plugin/.mcp.json":
        "a07f1baa288a87dd916f7a8bd3085c5c8d0ea36b07578f9e54f99cc74256b6cb",
    "seeded-plugin/commands/notes.md":
        "d7b145501ca7fedb2d265b6ee6359319a5426969e79fee068911da8c476244da",
    "seeded-plugin/hooks/hooks.json":
        "3905d95c618ff7ec8863ce1753ad3bb6bf9a559531323a782a937db6e41e091c",
    "seeded-plugin/package-lock.json":
        "7f48ae6b4b222c871ec29c21d64e6a64bca2005665810a93200693fd40a15bac",
    "seeded-plugin/package.json":
        "06c030d9549962a8576b326feea312b0678310b3c78b5303c4522ba33a278342",
    "seeded-plugin/scripts/install.sh":
        "c4e2819d668d97c4ddc2fb9d2c255d75adcd68c28764b6e40c3af60870277a82",
}


class FixtureSeal(unittest.TestCase):
    def test_no_fixture_file_escapes_the_seal(self):
        on_disk = {str(p.relative_to(FIX)) for p in FIX.rglob("*") if p.is_file()}
        self.assertEqual(on_disk, set(FIXTURE_SHA256))
        for rel, digest in FIXTURE_SHA256.items():
            with self.subTest(fixture=rel):
                self.assertEqual(
                    hashlib.sha256((FIX / rel).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
