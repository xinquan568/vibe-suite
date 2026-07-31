# SPDX-License-Identifier: ISC
"""E3.1 (vibe-26) acceptance: the knowledge-skill library.

Owns exactly the issue's self-contained acceptance surface: the 19-directory roster exists,
every SKILL.md carries frontmatter that actually parses (strict subset, proved by negative
cases below — not a fence count), the rules skill defines exactly R01-R51 and claims that
count wherever it states one, no skill file hard-links into ops data (the nlpm S7 class),
no source-ecosystem reference survives the port, and every SKILL.md respects the corpus's
own R05 size rule (<500 lines).

Deliberately NOT asserted here: manifest<->disk consistency (owned by
tests/test_manifests.py:test_registered_skills_match_disk_exactly) and model-id pinning
(owned by tools/model-pin-lint.py, which CI's lint job runs). Stdlib only — the repo's
test suite takes no third-party dependencies (#71 precedent).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

#: The F4.8 roster: nlpm's 17 knowledge skills + cc-suite's 2, minus the conventions-claude
#: merge, plus vibe-core (E0.2), auditing (E4.1 — the nl-audit dimension corpus) and roasting
#: (E4.3 — the roast code-review dimensions).
#: Asserted as EXACT equality with what is on disk — a later stage that ships a new skill
#: extends this tuple in the same PR, which keeps the roster an explicit, reviewed fact
#: rather than a drifting side effect.
ROSTER = (
    "agent-design",
    "auditing",
    "conventions",
    "conventions-antigravity",
    "conventions-claude",
    "conventions-codex",
    "orchestration",
    "patterns",
    "refine-proposal",
    "roasting",
    "rules",
    "scoring",
    "security",
    "testing",
    "vibe-core",
    "vocabulary",
    "writing-agents",
    "writing-hooks",
    "writing-plugins",
    "writing-prompts",
    "writing-rules",
    "writing-skills",
)

#: Source-ecosystem identifiers that must not survive the port (D7 / anti-pattern 2). The
#: allowlist is empty by policy; any future entry needs a justifying comment here and a
#: reviewer's eyes on the diff that adds it.
FORBIDDEN_SUBSTRINGS = (
    "/nlpm:",
    "/cc-suite:",
    "/grill:",
    "[[nlpm:",
    "[[cc-suite:",
    "nlpm-exemplar-citation",
    "nlpm-history",
    "nlpm.local",
    ".cc-suite",
    "cc-suite-state",
    ".nlpm-test",
)

#: Ops-data coupling markers (the acceptance grep): a skill may carry the vibe placeholder
#: marker, but never a link into the auditor data tree.
OPS_DATA_SUBSTRINGS = ("auditor/exemplars", "../../../auditor")

MARKER = "vibe-exemplar-citation"

_KEY_LINE = re.compile(r"^([a-z][a-z0-9_-]*):[ ](\S.*)$")


class FrontmatterError(ValueError):
    """The frontmatter block is malformed."""


def parse_frontmatter(text, required=("name", "description")):
    """Parse the strict frontmatter subset vibe-suite artifacts use.

    Grammar: line 1 is exactly ``---``; a closing ``---`` must follow; every line between
    is a single ``key: value`` pair (lowercase key, one space, non-empty value); no tabs,
    no continuations, no nesting, no duplicate keys; a value that opens with a quote must
    close it. ``required`` names the mandatory keys — skills demand name+description (the
    default); other artifact kinds pass their own set. Returns the field dict; raises
    FrontmatterError otherwise.
    """
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        raise FrontmatterError("missing opening fence")
    fields = {}
    for lineno, line in enumerate(lines[1:], start=2):
        if line == "---":
            if not fields:
                raise FrontmatterError("empty frontmatter block")
            for key in required:
                if key not in fields:
                    raise FrontmatterError("missing mandatory key %r" % key)
            return fields
        if "\t" in line:
            raise FrontmatterError("tab character on line %d" % lineno)
        match = _KEY_LINE.match(line)
        if match is None:
            raise FrontmatterError("line %d is not a simple 'key: value' pair" % lineno)
        key, value = match.group(1), match.group(2)
        if key in fields:
            raise FrontmatterError("duplicate key %r" % key)
        if value[0] in "\"'" and (len(value) < 2 or value[-1] != value[0]):
            raise FrontmatterError("unclosed quote in value of %r" % key)
        fields[key] = value
    raise FrontmatterError("missing closing fence")


class FrontmatterParserSelfTest(unittest.TestCase):
    """Negative cases first: the parser must reject malformation, or the acceptance
    assertions below prove nothing."""

    def test_accepts_the_canonical_shape(self):
        fields = parse_frontmatter("---\nname: rules\ndescription: The 51 rules.\n---\nbody")
        self.assertEqual(fields["name"], "rules")

    def test_rejects_missing_closing_fence(self):
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("---\nname: rules\ndescription: x\nbody with no fence")

    def test_rejects_duplicate_key(self):
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("---\nname: a\nname: b\n---\n")

    def test_rejects_tab_indentation(self):
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("---\nname: a\n\tdescription: x\n---\n")

    def test_rejects_empty_value(self):
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("---\nname: a\ndescription:\n---\n")

    def test_rejects_nested_mapping_line(self):
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("---\nname: a\nmeta:\n  nested: x\n---\n")

    def test_rejects_unclosed_quote(self):
        with self.assertRaises(FrontmatterError):
            parse_frontmatter('---\nname: a\ndescription: "half open\n---\n')

    def test_rejects_empty_block(self):
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("---\n---\nbody")

    def test_rejects_missing_mandatory_key(self):
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("---\nname: a\n---\nbody")
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("---\ndescription: x\n---\nbody")


def _skill_md_files():
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _skill_tree_files():
    return sorted(p for p in SKILLS_DIR.rglob("*") if p.is_file())


class SkillLibraryAcceptance(unittest.TestCase):
    def test_roster_directories_exist_with_skill_md(self):
        missing = [
            name
            for name in ROSTER
            if not (SKILLS_DIR / name / "SKILL.md").is_file()
        ]
        self.assertEqual(
            missing, [],
            "E3.1 roster directories missing a SKILL.md: %s" % ", ".join(missing),
        )

    def test_on_disk_skills_match_roster_exactly(self):
        on_disk = sorted(d.name for d in SKILLS_DIR.iterdir() if d.is_dir())
        self.assertEqual(
            on_disk, sorted(ROSTER),
            "skills/ diverges from the declared roster; a new skill extends "
            "ROSTER in the same PR",
        )

    def test_every_skill_frontmatter_parses(self):
        for path in _skill_md_files():
            with self.subTest(skill=path.parent.name):
                fields = parse_frontmatter(path.read_text(encoding="utf-8"))
                self.assertIn("name", fields, "%s: frontmatter lacks name" % path)
                self.assertIn(
                    "description", fields, "%s: frontmatter lacks description" % path
                )
                self.assertEqual(
                    fields["name"], path.parent.name,
                    "%s: frontmatter name must equal the directory name" % path,
                )

    def test_rules_skill_defines_exactly_r01_through_r51(self):
        text = (SKILLS_DIR / "rules" / "SKILL.md").read_text(encoding="utf-8")
        ids = re.findall(r"^\*\*R(\d{2})\.", text, re.MULTILINE)
        self.assertEqual(
            len(ids), len(set(ids)), "a rule id is introduced more than once"
        )
        self.assertEqual(
            sorted(set(ids)), ["%02d" % n for n in range(1, 52)],
            "the rules skill must define exactly R01-R51",
        )

    def test_rules_skill_count_claims_say_51(self):
        text = (SKILLS_DIR / "rules" / "SKILL.md").read_text(encoding="utf-8")
        claims = re.findall(r"[Tt]he (\d+) rules", text)
        self.assertTrue(claims, "the rules skill must state its rule count at least once")
        for claim in claims:
            self.assertEqual(
                claim, "51", "a stated rule count disagrees with the 51 rules defined"
            )

    def test_no_hard_link_into_ops_data(self):
        for path in _skill_tree_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for needle in OPS_DATA_SUBSTRINGS + ("nlpm-exemplar-citation",):
                self.assertNotIn(
                    needle, text, "%s links into ops data (%r)" % (path, needle)
                )

    def test_citation_placeholders_are_link_free(self):
        for path in _skill_tree_files():
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if MARKER in line:
                    self.assertNotIn(
                        "](", line,
                        "%s:%d: citation placeholder carries a link" % (path, lineno),
                    )
                    self.assertNotIn(
                        ".md", line,
                        "%s:%d: citation placeholder references a file" % (path, lineno),
                    )

    def test_no_stale_source_ecosystem_reference(self):
        for path in _skill_tree_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for needle in FORBIDDEN_SUBSTRINGS:
                self.assertNotIn(
                    needle, text,
                    "%s carries a source-ecosystem reference (%r)" % (path, needle),
                )

    def test_every_skill_md_respects_r05_size_rule(self):
        for path in _skill_md_files():
            with self.subTest(skill=path.parent.name):
                line_count = len(path.read_text(encoding="utf-8").splitlines())
                self.assertLess(
                    line_count, 500,
                    "%s is %d lines; R05 caps a SKILL.md under 500" % (path, line_count),
                )


if __name__ == "__main__":
    unittest.main()
