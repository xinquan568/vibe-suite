#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Content contract for `/vibe-suite:nl-audit` and the auditing skill (E4.1 / vibe-35).

F4.9 collapses six cc-suite auditors into one typed command and claims **zero dimension loss**:
seven dimensions for each of five per-artifact types, plus fifteen check sets for `repo` mode. That
claim is prose until something compares it to the artifacts, so this module is the comparison. It was
written before either artifact existed (TDD RED), in the same spirit as the delegate content contract
in `test_commands.py`.

Two things here are easy to get subtly wrong and are therefore asserted explicitly.

**`plugin`'s mini/full split is irregular.** The other four per-artifact types put D0-D3 in
`mini+full` and D4-D6 in `full`. `plugin` does not: D2 Security Posture is full-only and D6
Maintainability is mini+full. A test that assumed the regular split would pass a wrong artifact, so
the membership table below is transcribed per type rather than generated from a rule.

**A dimension is more than a heading.** Preserving the seven *names* while dropping their check
bullets and severity rules would satisfy a name-only test and lose exactly what F4.9 says carries over
"at functional parity". Every dimension is therefore asserted to carry both.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMAND = REPO_ROOT / "commands" / "nl-audit.md"
SKILL = REPO_ROOT / "skills" / "auditing" / "SKILL.md"
MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"

#: The six `--type` values. An exact closed set: a seventh type is dimension inflation, a missing one
#: is dimension loss, and both are the failure F4.9's "zero dimension loss" claim is about.
TYPES = ("skill", "command", "agent", "rules", "plugin", "repo")

#: Per-type dimension names with mini/full membership, transcribed from F4.9 (merge proposal lines
#: 281-285). `True` == mini+full, `False` == full only.
DIMENSIONS = {
    "skill": {
        "D0": ("Frontmatter Schema", True),
        "D1": ("Description Quality", True),
        "D2": ("Content Structure", True),
        "D3": ("Context Efficiency", True),
        "D4": ("Scope Boundaries", False),
        "D5": ("Cross-References & Integration", False),
        "D6": ("Actionability", False),
    },
    "command": {
        "D0": ("Frontmatter Schema", True),
        "D1": ("Workflow Clarity", True),
        "D2": ("Tool Selection", True),
        "D3": ("Output Specification", True),
        "D4": ("Error Handling", False),
        "D5": ("Argument Safety", False),
        "D6": ("Shared Partial Usage", False),
    },
    "agent": {
        "D0": ("Frontmatter Schema", True),
        "D1": ("Triggering Quality", True),
        "D2": ("System Prompt Quality", True),
        "D3": ("Tool Selection", True),
        "D4": ("Scope & Boundaries", False),
        "D5": ("Output Specification", False),
        "D6": ("Safety & Trust", False),
    },
    "rules": {
        "D0": ("Schema & Formatting", True),
        "D1": ("Enforceability", True),
        "D2": ("Token Budget", True),
        "D3": ("Conflict Detection", True),
        "D4": ("Path Scoping", False),
        "D5": ("Tooling Overlap", False),
        "D6": ("Staleness & Relevance", False),
    },
    # The irregular one. D2 is full-only; D6 is mini+full.
    "plugin": {
        "D0": ("YAML Schema Validation", True),
        "D1": ("Specification Quality", True),
        "D2": ("Security Posture", False),
        "D3": ("Structural Integrity", True),
        "D4": ("Behavioral Consistency", False),
        "D5": ("Robustness & Edge Cases", False),
        "D6": ("Maintainability", True),
    },
}

#: `repo` mode's fifteen category-specific check sets (F4.9, merge proposal line 286). Note the ids
#: collide by name with the per-artifact D1-D3 -- they live in the `repo` type's own namespace, which
#: is why every assertion below is scoped to a type rather than to a bare id.
REPO_CHECKS = {
    "A1": "Schema Validation",
    "A2": "Cross-Component Integrity",
    "A3": "Behavioral Consistency",
    "B1": "CLAUDE.md Quality",
    "B2": "Rules Quality",
    "B3": "Settings Consistency",
    "C1": "Prompt Effectiveness",
    "C2": "Prompt Safety",
    "C3": "Prompt Consistency",
    "D1": "Framework Structure",
    "D2": "Cross-Agent Consistency",
    "D3": "Completeness",
    "E1": "Internal Consistency",
    "E2": "Completeness",
    "E3": "Currency",
}

#: The six shared partials the command consumes. Every one already ships; the command is a consumer,
#: not an author, and a missing binding means a contract is being re-implemented in place.
PARTIALS = (
    "commands/shared/discover.md",
    "commands/shared/classify.md",
    "commands/shared/scope-parse.md",
    "commands/shared/model-selection.md",
    "commands/shared/plugin-discover.md",
    "commands/shared/fallback.md",
)

#: The six cc-suite names this command retires (D1-revised / AC-6). Matched as *references* -- a
#: slash-prefixed token, a `:`-prefixed token, or a backticked bare name -- never as a raw substring,
#: because "audit-plugin" as English prose is not a command reference. This extends the retired-name
#: discipline `test_commands.py` established for `implement`.
RETIRED = ("audit-skill", "audit-command", "audit-agent", "audit-rules", "audit-plugin", "audit-nlp")

#: Versioned model identifiers (P9). `tools/model-pin-lint.py` owns the repo-wide scan; this is the
#: artifact-local check, so a pin cannot ride in on a file the lint's scope happens to miss.
MODEL_PIN = re.compile(
    r"\b(?:gpt-\d|o\d-|gemini-\d|claude-(?:opus|sonnet|haiku|fable)-\d|claude-[a-z]+-20\d{2})",
    re.I,
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalized(text):
    """Phrase-assertion view: markdown emphasis stripped, whitespace collapsed."""
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


class TestArtifactsExist(unittest.TestCase):
    def test_command_and_skill_are_present(self):
        self.assertTrue(COMMAND.is_file(),
                        "commands/nl-audit.md does not exist -- the vibe-35 deliverable is missing")
        self.assertTrue(SKILL.is_file(),
                        "skills/auditing/SKILL.md does not exist -- the dimension corpus is missing")


class TestCommandSurface(unittest.TestCase):
    def setUp(self):
        if not COMMAND.is_file():
            self.skipTest("commands/nl-audit.md does not exist yet")
        self.text = _read(COMMAND)
        self.norm = _normalized(self.text)

    def test_frontmatter_has_description_and_argument_hint(self):
        self.assertTrue(self.text.startswith("---\n"), "no YAML frontmatter")
        block = self.text.split("---\n", 2)[1]
        self.assertRegex(block, r"^description:", "frontmatter lacks a description")
        self.assertRegex(block, r"(?m)^argument-hint:", "frontmatter lacks an argument-hint")

    def test_argument_hint_covers_the_whole_f49_surface(self):
        block = self.text.split("---\n", 2)[1]
        hint = re.search(r"(?m)^argument-hint:\s*(.+)$", block).group(1)
        for token in ("--type", "--full", "--mini", "--engine", "--background", "--wait"):
            self.assertIn(token, hint, "argument-hint omits %s" % token)

    def test_argument_surface_adds_no_flag_beyond_f49(self):
        """F4.9 fixes the surface. `--json` in particular was rejected in planning: the acceptance
        evaluator reads a file the session writes, so the command needs no output-format flag."""
        block = self.text.split("---\n", 2)[1]
        hint = re.search(r"(?m)^argument-hint:\s*(.+)$", block).group(1)
        self.assertNotIn("--json", hint,
                         "--json is not part of F4.9's argument surface for this command")

    def test_the_six_types_are_a_closed_set(self):
        for name in TYPES:
            self.assertIn(name, self.norm, "type '%s' is not named" % name)

    def test_repo_mode_names_discovery_categories_a_through_e(self):
        for letter in "ABCDE":
            self.assertRegex(self.norm, r"\b%s\b" % letter,
                             "repo mode does not name discovery category %s" % letter)

    def test_plugin_type_is_local_only(self):
        self.assertRegex(
            self.norm, r"(?i)plugin[^.]*?(no model call|local analysis|without a model call)",
            "the command does not state that --type plugin makes no model call")

    def test_every_shared_partial_is_bound(self):
        for partial in PARTIALS:
            self.assertIn(partial, self.text, "the command does not bind %s" % partial)

    def test_dispatch_branches_around_the_gate(self):
        """The defect the plan review caught: routing the v1 codex default through
        `agy-audit-cli.mjs` would hit its pre-gate refusal and never reach codex."""
        self.assertIn("scripts/codex-runner.mjs", self.text,
                      "the codex lane must dispatch codex-runner.mjs directly")
        self.assertIn("scripts/agy-audit-cli.mjs", self.text,
                      "the graduated agy lane must dispatch agy-audit-cli.mjs")
        self.assertRegex(self.norm, r"(?i)refus\w*[^.]*agy|agy[^.]*refus\w*",
                         "a pre-gate --engine agy request must be refused, not degraded")

    def test_wait_is_the_default_and_background_is_specified(self):
        self.assertRegex(self.norm, r"(?i)--wait[^.]*default|default[^.]*--wait",
                         "--wait is not stated as the default")
        self.assertIn("--background", self.text)

    def test_untrusted_input_rule_is_stated_and_sourced(self):
        self.assertRegex(self.norm, r"(?i)data,? never instructions",
                         "the untrusted-input rule is not stated")
        self.assertIn("skills/vibe-core/SKILL.md", self.text,
                      "the untrusted-input rule does not cite vibe-core")

    def test_provenance_is_disclosed_on_dispatch(self):
        self.assertRegex(self.norm, r"(?i)provenance")

    def test_depth_flags_are_consumed_before_scope_parsing(self):
        """`scope-parse.md` records that every caller strips --full/--mini as depth first; a caller
        that passed them through would hit the partial's deliberately unreachable `--full` row."""
        self.assertRegex(self.norm, r"(?i)(depth|--full[^.]*--mini)[^.]*before[^.]*scope|"
                                    r"scope[^.]*after[^.]*depth")

    def test_command_stays_lean(self):
        """Progressive disclosure: judgment criteria live in the skill. The shipped corpus runs 48-163
        lines per command; a command carrying the dimension corpus inline would be several times that."""
        lines = len(self.text.splitlines())
        self.assertLessEqual(lines, 200,
                             "commands/nl-audit.md is %d lines; judgment criteria belong in "
                             "skills/auditing/SKILL.md" % lines)


class TestSkillDimensionCorpus(unittest.TestCase):
    def setUp(self):
        if not SKILL.is_file():
            self.skipTest("skills/auditing/SKILL.md does not exist yet")
        self.text = _read(SKILL)
        self.norm = _normalized(self.text)

    def _type_section(self, artifact_type):
        """The slice of the skill owned by one --type, so a D1 assertion cannot be satisfied by
        another type's D1."""
        pattern = re.compile(r"(?m)^##\s+`?--type\s+%s`?\b" % re.escape(artifact_type))
        match = pattern.search(self.text)
        self.assertIsNotNone(
            match, "skills/auditing/SKILL.md has no '## --type %s' section" % artifact_type)
        rest = self.text[match.end():]
        nxt = re.search(r"(?m)^##\s+", rest)
        return rest[: nxt.start()] if nxt else rest

    def test_frontmatter_parses_with_name_and_description(self):
        self.assertTrue(self.text.startswith("---\n"))
        block = self.text.split("---\n", 2)[1]
        self.assertRegex(block, r"(?m)^name:\s*auditing\s*$",
                         "skill name must be 'auditing' and match its directory")
        self.assertRegex(block, r"(?m)^description:\s*\S")

    def test_every_dimension_name_and_membership_is_exact(self):
        for artifact_type, dims in DIMENSIONS.items():
            section = _normalized(self._type_section(artifact_type))
            for did, (name, mini) in dims.items():
                with self.subTest(type=artifact_type, dimension=did):
                    self.assertIn(name, section,
                                  "%s %s '%s' is missing" % (artifact_type, did, name))
                    row = re.search(
                        re.escape(did) + r"[^|\n]*" + re.escape(name) + r"(.{0,80})", section)
                    self.assertIsNotNone(row, "%s %s has no membership marker" % (artifact_type, did))
                    marker = row.group(1)
                    if mini:
                        self.assertIn("mini+full", marker,
                                      "%s %s must be mini+full" % (artifact_type, did))
                    else:
                        self.assertNotIn("mini+full", marker,
                                         "%s %s must be full-only" % (artifact_type, did))
                        self.assertIn("full", marker,
                                      "%s %s has no depth marker" % (artifact_type, did))

    def test_plugin_membership_is_irregular_as_specified(self):
        """Guards the transcription itself: if a future edit regularises plugin to D0-D3/D4-D6, the
        per-dimension test above would still pass against a self-consistent wrong table. This asserts
        the shape directly."""
        mini = {d for d, (_, m) in DIMENSIONS["plugin"].items() if m}
        self.assertEqual(mini, {"D0", "D1", "D3", "D6"},
                         "plugin's mini+full set is D0, D1, D3, D6 -- not the regular D0-D3")

    def test_every_dimension_carries_check_bullets_and_a_severity_rule(self):
        """F4.9 says the per-dimension check bullets and severity rules carry over at functional
        parity. Names alone are not parity."""
        for artifact_type, dims in DIMENSIONS.items():
            section = self._type_section(artifact_type)
            for did, (name, _) in dims.items():
                with self.subTest(type=artifact_type, dimension=did):
                    start = section.find(name)
                    self.assertNotEqual(start, -1)
                    body = section[start: start + 1400]
                    self.assertRegex(body, r"(?m)^\s*[-*]\s+\S",
                                     "%s %s has no check bullets" % (artifact_type, did))
                    self.assertRegex(
                        body, r"(?i)\b(blocker|critical|high|major|medium|minor|low|nit)\b",
                        "%s %s states no severity rule" % (artifact_type, did))

    def test_repo_mode_has_all_fifteen_check_sets(self):
        section = _normalized(self._type_section("repo"))
        for cid, name in REPO_CHECKS.items():
            with self.subTest(check=cid):
                self.assertRegex(section, re.escape(cid) + r"\b",
                                 "repo check set %s is missing" % cid)
                self.assertIn(name, section, "repo check %s '%s' is missing" % (cid, name))

    def test_plugin_delegates_its_security_dimension(self):
        section = self._type_section("plugin")
        self.assertIn("security-scan", section,
                      "plugin D2 Security Posture must delegate to the security-scan pass")

    def test_finding_shape_is_bound_to_vibe_core(self):
        self.assertIn("skills/vibe-core/SKILL.md", self.text,
                      "the finding contract must be bound to vibe-core, not restated")

    def test_untrusted_input_rule_is_stated(self):
        self.assertRegex(_normalized(self.text), r"(?i)data,? never instructions")


class TestNamespaceAndModelDiscipline(unittest.TestCase):
    """D1-revised, AC-6 and P9, asserted on both new artifacts."""

    def _artifacts(self):
        return [p for p in (COMMAND, SKILL) if p.is_file()]

    def test_command_is_referenced_under_the_vibe_suite_prefix(self):
        if not COMMAND.is_file():
            self.skipTest("commands/nl-audit.md does not exist yet")
        self.assertIn("/vibe-suite:nl-audit", _read(COMMAND))

    def test_no_retired_source_name_survives_as_a_command_reference(self):
        artifacts = self._artifacts()
        if not artifacts:
            self.skipTest("neither artifact exists yet")
        patterns = []
        for name in RETIRED:
            patterns.append((name, re.compile(r"/vibe-suite:%s\b" % re.escape(name))))
            patterns.append((name, re.compile(r"(?<![\w-]):%s\b" % re.escape(name))))
            patterns.append((name, re.compile(r"`%s`" % re.escape(name))))
        for path in artifacts:
            text = _read(path)
            for name, pattern in patterns:
                with self.subTest(artifact=path.name, retired=name):
                    self.assertIsNone(
                        pattern.search(text),
                        "%s references the retired name '%s'" % (path.name, name))

    def test_no_versioned_model_id_is_pinned(self):
        artifacts = self._artifacts()
        if not artifacts:
            self.skipTest("neither artifact exists yet")
        for path in artifacts:
            with self.subTest(artifact=path.name):
                hit = MODEL_PIN.search(_read(path))
                self.assertIsNone(hit, "%s pins a model id: %s"
                                  % (path.name, hit.group(0) if hit else ""))

    def test_dispatch_passes_no_model_flag(self):
        if not COMMAND.is_file():
            self.skipTest("commands/nl-audit.md does not exist yet")
        for line in _read(COMMAND).splitlines():
            if "codex-runner.mjs" in line or "agy-audit-cli.mjs" in line:
                self.assertNotRegex(line, r"(?<![\w-])-m\s|\B--model\b",
                                    "dispatch names a model (P9): %s" % line.strip())


class TestManifestRegistration(unittest.TestCase):
    def test_command_and_skill_are_registered(self):
        manifest = json.loads(_read(MANIFEST))
        self.assertIn("./commands/nl-audit.md", manifest["commands"],
                      "plugin.json does not register the command; an unregistered command is not a "
                      "command (the /vibe-suite: prefix comes from this manifest)")
        self.assertIn("./skills/auditing", manifest["skills"],
                      "plugin.json does not register the auditing skill")


if __name__ == "__main__":
    unittest.main()
