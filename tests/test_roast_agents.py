#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Content contract for the six roast agents (E4.2 / vibe-36).

E3.6 already froze six NL-TDD specs under `.vibe-test/` — triggering, output header, frontmatter —
before any of these artifacts existed. This module covers what those specs do **not**: the per-agent
ownership deconfliction, recon's hard limits, the shared vocabulary across the five specialists, and
F5.2's single-pattern-database requirement.

Three things here are easy to get wrong and are asserted rather than assumed.

**`tools` is a comma-separated scalar, not a YAML sequence.** All eight previously-shipped agents
write `tools: Read, Glob, Bash`. A test that only checked "is a list" would accept both a different
serialization and a wider grant, so the grant is parsed and compared for **equality** — a superset
fails.

**`[GOOD]` is exclusive, not additive.** `schemas/audit-output.schema.json`'s first `allOf`
conditional caps `findings` at one item when any finding is `[GOOD]`. An agent that appends a `[GOOD]`
summary alongside real findings emits output that fails validation, so each agent must state the
exclusivity, not merely the sentinel.

**The five specialists must agree with each other, not merely each be correct.** Six artifacts written
in one change can drift in wording while each reads well alone. The shared paragraphs are asserted
equal across the five.
"""

import ast
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS = REPO_ROOT / "agents"
MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "roast" / "deconfliction"

RECON = "recon"
SPECIALISTS = ("architecture", "error-handling", "security", "testing", "edge-cases")
SIX = (RECON,) + SPECIALISTS

#: Exact tool grants. F3.2 gives recon Read/Glob/Grep/Bash; F3.3-F3.7 give the five specialists
#: "tools Read/Glob/Grep only" -- the word *only* is why this is equality, not containment.
TOOLS = {
    "recon": {"Read", "Glob", "Grep", "Bash"},
    "architecture": {"Read", "Glob", "Grep"},
    "error-handling": {"Read", "Glob", "Grep"},
    "security": {"Read", "Glob", "Grep"},
    "testing": {"Read", "Glob", "Grep"},
    "edge-cases": {"Read", "Glob", "Grep"},
}
#: Tier aliases only (P9). recon is haiku-class because a survey is non-judgmental (F3.2, fixing
#: grill's W10 cost concern); the five reviewers are sonnet-class.
MODELS = dict.fromkeys(SPECIALISTS, "sonnet") | {"recon": "haiku"}
TIER_ALIASES = {"haiku", "sonnet", "opus"}
FORBIDDEN_TOOLS = ("Write", "Edit", "Task", "NotebookEdit", "WebFetch")

#: Ownership, from F3.3-F3.7. `claims` are topics the agent owns; `defers` are (topic, owner) pairs
#: it must hand off. The deconfliction is directional: a topic deferred by one agent is claimed by
#: exactly one other.
OWNERSHIP = {
    "architecture": {
        "claims": ("entry point", "module boundar", "dependency graph", "data flow", "pattern"),
        "defers": (("config", "error-handling"),),
    },
    "error-handling": {
        "claims": ("error pattern", "recovery", "logging", "observability", "config"),
        "defers": (("secret", "security"), ("PII", "security")),
    },
    "security": {
        "claims": ("authn", "authz", "injection", "secret", "dependenc", "transport"),
        "defers": (),
    },
    "testing": {
        "claims": ("coverage", "quality", "infrastructure", "CI/CD"),
        "defers": (),
    },
    "edge-cases": {
        "claims": ("race", "boundary value", "partial failure", "error-propagation",
                   "implicit assumption"),
        "defers": (),
    },
}

#: recon's permitted Bash forms, as an EXACT set. An allowlist of bare verbs would bound nothing --
#: `find` deletes through `-delete` and any verb writes through redirection -- so the artifact
#: allowlists complete forms and refuses the shell outright. Membership-only assertions were the round-1
#: weakness: deleting an entry removed an assertion instead of guarding a fix, so the artifact could
#: keep a row and still pass. `git status --porcelain` is deliberately absent -- it answers none of
#: the seven survey items, and its read-only status depends on git configuration the artifact cannot
#: see (optional index locks, index refresh, a configured core.fsmonitor helper).
RECON_COMMANDS = (
    "git ls-files",
    "git ls-files -- <path>",
    "git rev-parse --abbrev-ref HEAD",
    "git log --oneline -n <N>",
    "wc -l <path>",
)
RECON_BANNED_METACHARACTERS = (">>", ">", "<", "||", "|", "&&", "&", ";", "$(", "`")
RECON_SECRET_GLOBS = (".env", "*.pem", "*.key", "*secret*", "id_rsa")
RECON_SURVEY_ITEMS = ("language", "framework", "architecture", "database", "CI/CD",
                      "entry point", "size", "notable config")

#: Instructions that describe output the canonical schema cannot express. `schemas/audit-output.schema.json`
#: is closed at {agent, findings} with one report-level `agent` and no per-finding owner, so an agent
#: cannot emit a finding attributed to a different agent. Matched semantically rather than as one
#: literal: round 1 expressed the same instruction three ways, and matching only the first would pass
#: a rephrasing of the other two.
FORBIDDEN_HANDOFF = (
    r"attribute it to `?vibe-suite:",
    r"[Hh]and-offs? are named in your findings",
    r"do not grade it yourself",
)

#: The blocks the five specialists must share byte-for-byte, each extracted by its own stable anchor.
#: Enumerated rather than discovered: a paragraph that drifts stops matching whatever pattern found
#: it, so dynamic discovery reports agreement among the paragraphs that still agree.
SHARED_BLOCKS = {
    "untrusted-input": (r"\*\*Untrusted input\.\*\*", "blank"),
    "finding-contract": (r"\*\*The finding contract is not yours\.\*\*", "blank"),
    "zero-findings": (r"\*\*Zero findings\.\*\*", "blank"),
    "boundaries": (r"## Boundaries", "heading"),
}

MODEL_PIN = re.compile(
    r"\b(?:gpt-\d|o\d-|gemini-\d|claude-(?:opus|sonnet|haiku|fable)-\d|claude-[a-z]+-20\d{2})", re.I)


def read(name):
    return (AGENTS / f"{name}.md").read_text(encoding="utf-8")


def frontmatter(text):
    """Key/value view of the frontmatter, with surrounding quotes stripped.

    Unquoting matters: a description containing a colon MUST be quoted to be valid YAML (see
    `TestPlainScalarColonRule`), so a reader that returned the quotes would report the value as
    starting with `"` and every content assertion against it would be wrong. This function is a
    convenience for the assertions below and is deliberately NOT a YAML parser -- the one grammar
    rule this module enforces is checked separately, against the raw text.
    """
    if not text.startswith("---\n"):
        return {}
    block = text.split("---\n", 2)[1]
    out = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            out[k.strip()] = v
    return out


def tool_set(value):
    """The shipped house form is a comma-separated scalar (`tools: Read, Glob, Bash`)."""
    return {t.strip() for t in value.split(",") if t.strip()}


def body(text):
    return text.split("---\n", 2)[2] if text.startswith("---\n") else text


def permitted_forms(text):
    """The allowlist table's first column, as a set. Parsed from the artifact so the test compares
    what the agent actually permits rather than what a constant says it permits."""
    forms = set()
    for line in text.splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|", line)
        if m:
            forms.add(m.group(1).strip())
    return forms


def shared_block(text, anchor, terminator):
    """One named block, from its anchor to a stable boundary. Returns None when absent -- absence is
    a failure, not an exclusion."""
    m = re.search(anchor, text)
    if not m:
        return None
    rest = text[m.start():]
    end = re.search(r"\n\s*\n", rest) if terminator == "blank" else re.search(r"(?m)^##\s", rest[3:])
    if terminator == "heading" and end:
        return rest[: end.start() + 3].strip()
    return rest[: end.start()].strip() if end else rest.strip()


class AgentTestCase(unittest.TestCase):
    def setUp(self):
        missing = [n for n in SIX if not (AGENTS / f"{n}.md").is_file()]
        if missing:
            self.skipTest("agents not written yet: %s" % ", ".join(missing))


class TestAgentsExist(unittest.TestCase):
    def test_all_six_are_present(self):
        missing = [n for n in SIX if not (AGENTS / f"{n}.md").is_file()]
        self.assertEqual(missing, [], "missing roast agents: %s" % ", ".join(missing))


class TestFrontmatter(AgentTestCase):
    def test_name_matches_the_filename(self):
        for name in SIX:
            with self.subTest(agent=name):
                self.assertEqual(frontmatter(read(name)).get("name"), name)

    def test_description_is_present_and_trigger_style(self):
        """Each spec's `Frontmatter Valid` requires a trigger-style description ("Use when...")."""
        for name in SIX:
            with self.subTest(agent=name):
                desc = frontmatter(read(name)).get("description", "")
                self.assertTrue(desc, "%s has no description" % name)
                self.assertTrue(desc.startswith("Use when "),
                                "%s: description must be trigger-style" % name)

    def test_tools_are_the_exact_grant_in_the_house_serialization(self):
        for name in SIX:
            with self.subTest(agent=name):
                raw = frontmatter(read(name)).get("tools", "")
                self.assertTrue(raw, "%s has no tools field" % name)
                self.assertFalse(raw.startswith("["),
                                 "%s: the house form is a comma-separated scalar, not a sequence"
                                 % name)
                self.assertEqual(tool_set(raw), TOOLS[name],
                                 "%s: tool grant must be exactly %s" % (name, sorted(TOOLS[name])))

    def test_no_agent_holds_a_writing_or_dispatching_tool(self):
        """Named individually so a failure says what leaked, not just that the sets differ."""
        for name in SIX:
            granted = tool_set(frontmatter(read(name)).get("tools", ""))
            for tool in FORBIDDEN_TOOLS:
                with self.subTest(agent=name, tool=tool):
                    self.assertNotIn(tool, granted, "%s must not hold %s" % (name, tool))

    def test_model_is_the_expected_tier_alias(self):
        for name in SIX:
            with self.subTest(agent=name):
                model = frontmatter(read(name)).get("model", "")
                self.assertIn(model, TIER_ALIASES, "%s: model must be a tier alias (P9)" % name)
                self.assertEqual(model, MODELS[name])

    def test_no_versioned_model_id_anywhere(self):
        for name in SIX:
            with self.subTest(agent=name):
                hit = MODEL_PIN.search(read(name))
                self.assertIsNone(hit, "%s pins a model id: %s"
                                  % (name, hit.group(0) if hit else ""))


class TestOutputContract(AgentTestCase):
    def test_output_header_is_the_exact_qualified_form(self):
        """`schemas/audit-output.schema.json`'s closed `agent` enum keys its variant rules on this
        string, and its own description says a bare name would bypass them."""
        for name in SIX:
            with self.subTest(agent=name):
                self.assertIn("## [Agent: vibe-suite:%s] Findings" % name, read(name))

    def test_finding_shape_is_bound_to_vibe_core_not_restated(self):
        for name in SIX:
            with self.subTest(agent=name):
                self.assertIn("skills/vibe-core/SKILL.md", read(name))

    def test_good_is_stated_as_exclusive(self):
        """The schema caps `findings` at one item when any is `[GOOD]`, so an agent that permits a
        `[GOOD]` summary beside real findings emits invalid output."""
        for name in SIX:
            with self.subTest(agent=name):
                text = body(read(name))
                self.assertIn("[GOOD]", text)
                self.assertRegex(
                    text, r"(?i)\[GOOD\][^.]*\bonly\b|only[^.]*\[GOOD\]|\[GOOD\][^.]*sole|"
                          r"no other finding",
                    "%s: the [GOOD] entry must be stated as the ONLY entry, not one among others"
                    % name)

    def test_security_owes_an_exploit_scenario_and_edge_cases_a_risk_matrix(self):
        """Mirrors the schema's two agent-keyed conditionals, so artifact and validator agree by
        construction rather than by coincidence."""
        self.assertRegex(read("security"), r"(?i)exploit scenario")
        self.assertRegex(read("edge-cases"), r"(?i)risk matrix")
        self.assertRegex(read("edge-cases"), r"(?i)worst case verdict")

    def test_every_agent_reports_and_never_edits(self):
        for name in SIX:
            with self.subTest(agent=name):
                self.assertRegex(read(name), r"(?i)never (edit|change|modif|write)")


class TestPerAgentOwnership(AgentTestCase):
    """The deconfliction, as a relation between artifacts rather than a property of one."""

    def test_each_specialist_claims_its_own_topics(self):
        for name, spec in OWNERSHIP.items():
            text = read(name).lower()
            for topic in spec["claims"]:
                with self.subTest(agent=name, claims=topic):
                    self.assertIn(topic.lower(), text,
                                  "%s does not claim '%s'" % (name, topic))

    def test_each_deferral_names_its_owner(self):
        for name, spec in OWNERSHIP.items():
            text = read(name)
            for topic, owner in spec["defers"]:
                with self.subTest(agent=name, defers=topic, to=owner):
                    window = re.search(
                        r"[^.]*%s[^.]*%s[^.]*\.|[^.]*%s[^.]*%s[^.]*\."
                        % (re.escape(topic), re.escape(owner), re.escape(owner),
                           re.escape(topic)), text, re.I)
                    self.assertIsNotNone(
                        window,
                        "%s must defer '%s' to %s in one sentence" % (name, topic, owner))

    def test_no_agent_instructs_cross_attribution(self):
        """`schemas/audit-output.schema.json` is closed at {agent, findings} with ONE report-level
        `agent` and no per-finding owner field, so a finding attributed to a different agent is
        output that cannot be emitted. Deferral is therefore omission: the deferring agent does not
        report the topic, and coverage comes from the owning agent also running.

        Matched semantically rather than by one literal -- round 1 expressed the same instruction
        three ways, and matching only the first would pass a rephrasing of the other two."""
        for name in SIX:
            text = read(name)
            for pattern in FORBIDDEN_HANDOFF:
                with self.subTest(agent=name, pattern=pattern):
                    self.assertIsNone(
                        re.search(pattern, text),
                        "%s instructs a hand-off the finding schema cannot express" % name)

    def test_architecture_defers_config_and_error_handling_owns_it(self):
        """The acceptance's named case, asserted as the pair it is: a config finding lands with
        error-handling, not architecture."""
        arch = read("architecture")
        errh = read("error-handling")
        self.assertRegex(arch, r"(?i)config[^.]*error-handling|error-handling[^.]*config",
                         "architecture must defer config findings to error-handling")
        self.assertRegex(errh, r"(?i)config[^.]*(primary owner|owns|owner)|"
                               r"(primary owner|owns|owner)[^.]*config",
                         "error-handling must claim primary ownership of config")


class TestRecon(AgentTestCase):
    def test_survey_template_items_are_all_present(self):
        text = read(RECON).lower()
        for item in RECON_SURVEY_ITEMS:
            with self.subTest(item=item):
                self.assertIn(item.lower(), text)

    def test_output_is_capped_at_eighty_lines(self):
        self.assertRegex(read(RECON), r"(?i)80 lines")

    def test_unknown_is_the_stated_fallback(self):
        self.assertRegex(read(RECON), r"(?i)Unknown\s*[-—]\s*do not guess")

    def test_secret_files_are_never_read_only_noted(self):
        text = read(RECON)
        for glob in RECON_SECRET_GLOBS:
            with self.subTest(glob=glob):
                self.assertIn(glob, text)
        self.assertRegex(text, r"(?i)existence")

    def test_prior_reports_are_excluded(self):
        self.assertIn("vibe-report-", read(RECON))

    def test_bash_allowlist_is_exactly_the_expected_complete_forms(self):
        """Equality, not membership. A membership-only assertion is weakened by deleting an entry --
        the artifact could keep a permitted row and still pass."""
        self.assertEqual(permitted_forms(read(RECON)), set(RECON_COMMANDS))

    def test_git_status_is_not_permitted(self):
        """Named separately so the failure says which row leaked. It answers none of the seven survey
        items, and its read-only status depends on git configuration the artifact cannot see:
        optional index locks, index-metadata refresh, and a configured core.fsmonitor helper."""
        for form in permitted_forms(read(RECON)):
            self.assertNotIn("git status", form,
                             "git status is not strictly read-only and serves no survey item")

    def test_shell_composition_is_refused(self):
        text = read(RECON)
        for char in RECON_BANNED_METACHARACTERS:
            with self.subTest(metacharacter=char):
                self.assertIn(char, text,
                              "recon must name %r among the refused shell metacharacters" % char)
        self.assertRegex(text, r"(?i)refus\w+", "a banned form must be refused, not filtered")

    def test_find_is_not_a_permitted_command(self):
        """`Glob` does what recon needs `find` for and has no `-exec`, `-ok` or `-delete` to forbid.
        Choosing a tool that cannot express the dangerous operation beats permitting one that can."""
        self.assertNotRegex(read(RECON), r"(?m)^\|\s*`?find\b",
                            "find must not appear as a permitted command form")


class TestSharedVocabulary(AgentTestCase):
    """The five specialists must agree with one another, which per-file correctness cannot show."""

    def _shared_sentence(self, text, pattern):
        match = re.search(pattern, text, re.I)
        return match.group(0).strip() if match else None

    def test_every_named_shared_block_is_byte_identical_across_the_five(self):
        """Enumerated, not discovered. Dynamic discovery is circular: a paragraph that drifts stops
        matching whatever pattern found it, so it leaves the comparison and the test reports
        agreement among the paragraphs that still agree. A block missing from any one of the five is
        a failure here, not an exclusion."""
        for block, (anchor, terminator) in SHARED_BLOCKS.items():
            extracted = {n: shared_block(read(n), anchor, terminator) for n in SPECIALISTS}
            with self.subTest(block=block):
                missing = [n for n, v in extracted.items() if v is None]
                self.assertEqual(missing, [],
                                 "%s block absent from: %s" % (block, ", ".join(missing)))
                self.assertEqual(
                    len(set(extracted.values())), 1,
                    "the %s block has drifted across the five specialists:\n%s"
                    % (block, json.dumps(extracted, indent=2)))

    def test_every_specialist_both_inlines_the_rule_and_loads_vibe_core(self):
        """F3.3-F3.7 require both, deliberately: belt-and-braces against grill's W6, where an
        ignored frontmatter preload would silently drop the guard."""
        for name in SPECIALISTS:
            with self.subTest(agent=name):
                text = read(name)
                self.assertRegex(text, r"(?i)data,? never instructions|DATA to analyse")
                self.assertIn("skills/vibe-core/SKILL.md", text)

    def test_the_vibe_core_reference_path_is_identical(self):
        paths = {n: re.findall(r"\.\./skills/vibe-core/SKILL\.md", read(n)) for n in SPECIALISTS}
        for name, found in paths.items():
            self.assertTrue(found, "%s does not reference vibe-core by the house relative path"
                            % name)


class TestF52SharedPatternDatabase(AgentTestCase):
    """F5.2: one pattern database, two front-ends, so a pattern update lands in both.

    Compared rather than grepped: extracting the path from each artifact and asserting equality is
    what fails when *either* drifts. Grepping one file for a literal would not.
    """

    def _security_skill_path(self, text):
        found = re.findall(r"(?:\.\./)?skills/security/SKILL\.md", text)
        return sorted(set(found))

    def test_both_security_front_ends_name_the_identical_skill(self):
        specialist = self._security_skill_path(read("security"))
        scanner = self._security_skill_path(read("security-scanner"))
        self.assertTrue(specialist, "agents/security.md does not reference skills/security/SKILL.md")
        self.assertTrue(scanner, "agents/security-scanner.md lost its security skill reference")
        self.assertEqual(specialist, scanner,
                         "the two security front-ends reference different paths; a pattern update "
                         "would land in only one")

    def test_the_specialist_does_not_restate_the_pattern_database(self):
        self.assertRegex(read("security"), r"(?i)(does not|never) (restate|extend|duplicate)|"
                                           r"you apply it")


class TestDeconflictionFixture(unittest.TestCase):
    """Built for two consumers: this issue's static check, and E4.3's orchestrator, which will have a
    runtime to dispatch against it."""

    def setUp(self):
        # FAIL, never skip. The fixture is a required acceptance artifact, so deleting it must not
        # be a way for the suite to pass quietly.
        self.assertTrue((FIXTURE / "ownership.json").is_file(),
                        "the deconfliction fixture is a required acceptance artifact and is absent")
        self.spec = json.loads((FIXTURE / "ownership.json").read_text(encoding="utf-8"))

    def test_the_fixture_declares_owner_and_non_owner(self):
        for key in ("finding", "owner", "not_owner", "rationale"):
            self.assertIn(key, self.spec)

    def test_both_named_agents_are_in_the_schema_enum(self):
        schema = json.loads(
            (REPO_ROOT / "schemas" / "audit-output.schema.json").read_text(encoding="utf-8"))
        enum = set(schema["properties"]["agent"]["enum"])
        self.assertIn(self.spec["owner"], enum)
        self.assertIn(self.spec["not_owner"], enum)

    def test_the_declared_source_exists(self):
        self.assertIn("file", self.spec, "ownership.json must declare the source it refers to")
        self.assertTrue((FIXTURE / self.spec["file"]).is_file(),
                        "declared source %r is not on disk" % self.spec["file"])

    def test_the_seeded_construct_is_present_and_proven_by_parsing(self):
        """Asserted with `ast`, not by matching text: a comment mentioning KeyError would satisfy a
        string search without the defect existing."""
        src = (FIXTURE / self.spec["file"]).read_text(encoding="utf-8")
        tree = ast.parse(src)
        swallowed = [
            h for node in ast.walk(tree) if isinstance(node, ast.Try)
            for h in node.handlers
            if isinstance(h.type, ast.Name) and h.type.id == "KeyError"
            and len(h.body) == 1 and isinstance(h.body[0], ast.Pass)
        ]
        self.assertTrue(swallowed,
                        "the seeded defect (try/except KeyError whose handler body is only `pass`) "
                        "is not present in %s" % self.spec["file"])
        self.swallowed_lines = {h.lineno for h in swallowed}

    def test_ownership_line_is_nonblank_and_in_the_seeded_construct(self):
        """A blank or arbitrary line satisfies "the declared line resolves"; it must point at the
        construct itself."""
        src = (FIXTURE / self.spec["file"]).read_text(encoding="utf-8").splitlines()
        line = self.spec.get("line")
        self.assertIsInstance(line, int, "ownership.json must cite an integer line")
        self.assertTrue(1 <= line <= len(src), "cited line %s is outside the file" % line)
        self.assertTrue(src[line - 1].strip(), "cited line %s is blank" % line)
        tree = ast.parse("\n".join(src))
        handler_lines = {
            h.lineno for node in ast.walk(tree) if isinstance(node, ast.Try)
            for h in node.handlers
            if isinstance(h.type, ast.Name) and h.type.id == "KeyError"
            and len(h.body) == 1 and isinstance(h.body[0], ast.Pass)
        }
        self.assertIn(line, handler_lines,
                      "cited line %s does not participate in the seeded construct" % line)

    def test_the_artifacts_agree_with_the_fixture(self):
        owner = self.spec["owner"].split(":", 1)[1]
        not_owner = self.spec["not_owner"].split(":", 1)[1]
        self.assertTrue((AGENTS / f"{owner}.md").is_file(), "%s.md is absent" % owner)
        self.assertRegex(read(owner), r"(?i)config",
                         "the declared owner does not claim config")
        self.assertRegex(read(not_owner), r"(?i)config[^.]*%s" % re.escape(owner),
                         "the declared non-owner does not defer config to the owner")


class TestPlainScalarColonRule(unittest.TestCase):
    """One YAML grammar rule, scanned across every agent in the plugin.

    **What this establishes and what it does not.** A YAML *plain* (unquoted) scalar may not contain
    a colon followed by whitespace: the parser reads it as a key separator. That is the exact
    construct that made `agents/recon.md` unloadable in round 1 of this issue. It is **not** a general
    strict-YAML validation -- that would need a conforming parser, and PyYAML is not a dependency of
    this repository.

    It is scanned here rather than added to `tests/test_skill_library.py::parse_frontmatter`, which
    E3.1 owns and the whole corpus consumes: tightening a shared parser could fail artifacts this
    issue has no remit over. Scanning all fourteen agents from this module gets the coverage without
    the ownership problem.

    The reason this class exists at all is that the round-1 test *certified* the defect: it split each
    frontmatter line on its first colon, so it saw a well-formed key and value where a real parser saw
    a syntax error. A checker more permissive than the thing it stands in for does not merely miss a
    defect -- it blesses it.
    """

    def _violations(self, path):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            return []
        out = []
        for lineno, line in enumerate(text.split("---\n", 2)[1].splitlines(), start=2):
            if not line.strip() or line.startswith((" ", "\t", "#")) or ":" not in line:
                continue
            _, _, value = line.partition(":")
            value = value.strip()
            if value.startswith(('"', "'")):        # a quoted scalar may contain anything
                continue
            if re.search(r":\s", value):
                out.append((lineno, line.strip()[:100]))
        return out

    def test_no_agent_has_a_colon_space_in_an_unquoted_frontmatter_value(self):
        offenders = {}
        for path in sorted(AGENTS.glob("*.md")):
            found = self._violations(path)
            if found:
                offenders[path.name] = found
        self.assertEqual(
            offenders, {},
            "unquoted frontmatter values containing ': ' are invalid YAML plain scalars; quote them "
            "as commands/bridge.md does:\n%s" % json.dumps(offenders, indent=2))

    def test_the_rule_is_scanned_over_the_whole_agent_roster(self):
        """Guards the guard: a scan that silently narrowed to the six new agents would stop covering
        the eight it also protects."""
        self.assertEqual(len(list(AGENTS.glob("*.md"))), 14)

    def test_the_checker_rejects_the_construct_it_exists_to_catch(self):
        """A seeded failure, so the check cannot pass by being inert."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.md"
            bad.write_text("---\nname: bad\ndescription: A survey, not a review: it records facts.\n---\n\nbody\n",
                           encoding="utf-8")
            self.assertTrue(self._violations(bad), "the checker failed to flag a known-bad scalar")
            good = Path(tmp) / "good.md"
            good.write_text('---\nname: good\ndescription: "A survey, not a review: it records facts."\n---\n\nbody\n',
                            encoding="utf-8")
            self.assertEqual(self._violations(good), [], "the checker flagged a correctly quoted value")


class TestManifestRegistration(unittest.TestCase):
    def test_all_six_are_registered(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for name in SIX:
            with self.subTest(agent=name):
                self.assertIn("./agents/%s.md" % name, manifest["agents"])

    def test_the_manifest_now_carries_the_frozen_fourteen(self):
        """`test_vibe_test_specs.py`'s FOURTEEN is the spec inventory; this is the registration list.
        Nothing enforces that they match, so it is asserted rather than assumed."""
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["agents"]), 14)


if __name__ == "__main__":
    unittest.main()
