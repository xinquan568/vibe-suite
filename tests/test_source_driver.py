#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The source-driver interface (E5.4 / vibe-43).

#42 declared a driver protocol before anything implemented it, which makes it a hypothesis. This issue
implements it, and the implementation is what tests the hypothesis.

**The spike came first, and it overturned two of three proposed refinements.** The fixtures under
`tests/fixtures/issue2pr/gh-responses/` record, per scenario, the invocation that produces it and where
its shape is documented — because a fixture nobody can reproduce is a guess with a filename. They
decided:

- **`since` survives**, with its meaning fixed: only two of five observation scenarios can filter at the
  source, so the driver filters by whatever means its system allows. What the core never does is
  receive everything and diff.
- **`updated_at` was rejected.** Four independent collections with their own timestamps mean one
  timestamp says *that* something changed, not *what* — leaving the caller to re-read everything, which
  is the diffing the seam exists to prevent.
- **A single `unavailable` error was rejected.** The failure fixtures produce classes that differ in
  what the caller does next: retry, wait-then-retry, stop. Collapsing them makes an infinite retry loop
  look like a transient failure.

**The derivations must fail independently.** Everything here derives from the core's declared blocks —
the goldens, the seam tests, the conformance checklist. A wrong block propagates consistently to all of
them, which looks exactly like agreement. So each side is pinned to something the other cannot move,
and mutation is one side at a time.
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "issue2pr" / "SKILL.md"
DRIVER_CONTRACT = REPO_ROOT / "skills" / "issue2pr" / "references" / "driver-contract.md"
GITHUB_DRIVER = REPO_ROOT / "skills" / "issue2pr" / "drivers" / "github.md"
JIRA_DRIVER = REPO_ROOT / "skills" / "issue2pr" / "drivers" / "jira.md"
BOUNDARY_LINT = REPO_ROOT / "scripts" / "gh_boundary_lint.py"
SPIKE = REPO_ROOT / "tests" / "fixtures" / "issue2pr" / "gh-responses"

#: What the spike established. Not a preference — each entry traces to a fixture.
FAILURE_CLASSES = ("unavailable", "rate_limited", "unauthorized", "unusable")

OPERATIONS = ("fetch_item", "refresh_item", "open_change", "update_change",
              "read_change_state", "link_closure")


def json_block(text, marker):
    match = re.search(r"(?s)<!--\s*%s\s*-->\s*```json\s*(.*?)```" % re.escape(marker), text)
    return json.loads(match.group(1)) if match else None


def norm(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


class TestSpikeFixtures(unittest.TestCase):
    """The evidence. Every protocol claim below must trace to one of these."""

    @classmethod
    def setUpClass(cls):
        cls.fixtures = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                        for p in sorted(SPIKE.glob("*.json"))}

    def test_the_scenario_set_is_complete(self):
        expected = {"new-general-comment", "new-review-comment", "review-submitted",
                    "check-failed", "merged", "failure-transport", "failure-auth",
                    "failure-rate-limit", "failure-malformed"}
        self.assertEqual(set(self.fixtures), expected)

    def test_every_fixture_records_how_it_was_obtained(self):
        """A fixture nobody can reproduce is a guess with a filename."""
        for name, payload in self.fixtures.items():
            with self.subTest(fixture=name):
                for key in ("_invocation", "_docs", "_observation"):
                    self.assertIn(key, payload, f"{name} does not record {key}")
                    self.assertTrue(str(payload[key]).strip())

    def test_no_scenario_is_unresolved(self):
        """An unresolved scenario blocks the refinement that depended on it — that is the gate."""
        unresolved = [n for n, p in self.fixtures.items() if p.get("_unresolved")]
        self.assertEqual(unresolved, [],
                         f"unresolved scenarios block their refinements: {unresolved}")

    def test_the_observation_scenarios_disagree_about_since(self):
        """The fact that decided `since`'s meaning: some sources can filter, some cannot."""
        supported = {n: p["_since_supported"] for n, p in self.fixtures.items()
                     if "_since_supported" in p}
        self.assertEqual(len(supported), 5, "five observation scenarios")
        self.assertTrue(any(supported.values()), "some source filtering is possible")
        self.assertFalse(all(supported.values()),
                         "if every source could filter, the driver-filters rule would be moot")

    def test_the_failure_fixtures_are_not_one_class(self):
        """The fact that rejected a single `unavailable`: they differ in what the caller does next."""
        classes = {p["_class"]: p["_retryable"] for p in self.fixtures.values() if "_class" in p}
        self.assertEqual(set(classes), set(FAILURE_CLASSES))
        self.assertTrue(any(classes.values()), "some failures are retryable")
        self.assertFalse(all(classes.values()), "some are not — which is the whole distinction")

    def test_the_rate_limited_fixture_carries_when_to_retry(self):
        """`rate_limited` is retryable *later*, and without the time it is indistinguishable from
        `unavailable` — which would make a wait into a spin."""
        fixture = self.fixtures["failure-rate-limit"]
        self.assertTrue(fixture["_retryable"])
        self.assertIn("_retry_after", fixture)

    def test_the_four_observation_collections_are_distinct(self):
        """The fact that rejected `updated_at`: one timestamp cannot say which of these moved."""
        collections = set()
        for name in ("new-general-comment", "new-review-comment", "review-submitted", "check-failed"):
            payload = self.fixtures[name]
            keys = [k for k in payload if not k.startswith("_")]
            collections.update(keys)
        self.assertGreaterEqual(len(collections), 4,
                                f"expected four independent collections, found {sorted(collections)}")


class TestProtocolRefinement(unittest.TestCase):
    """The core's declaration, asserted against exact values rather than names."""

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.protocol = json_block(cls.text, "driver-protocol")
        cls.state = json_block(cls.text, "change-state")

    def test_read_change_state_takes_since(self):
        self.assertIn("since", self.protocol["read_change_state"]["in"],
                      "the caller asks a question with a time in it, or the core ends up diffing")

    def test_change_state_carries_what_is_new_per_collection(self):
        """`updated_at` was rejected: four collections move independently."""
        self.assertNotIn("updated_at", self.state,
                         "a single timestamp says that something changed, not what")
        for collection in ("comments", "review_comments", "reviews", "checks"):
            with self.subTest(collection=collection):
                self.assertIn(collection, self.state)

    def test_every_operation_declares_all_four_failure_classes(self):
        """They are not interchangeable: their whole content is what the caller does next."""
        for name, spec in self.protocol.items():
            with self.subTest(operation=name):
                for failure in FAILURE_CLASSES:
                    self.assertIn(failure, spec["errors"],
                                  f"{name} cannot report {failure}")

    def test_each_operation_keeps_its_own_item_level_errors(self):
        """The failure classes are additions, not replacements."""
        self.assertIn("not_found", self.protocol["fetch_item"]["errors"])
        self.assertIn("not_an_item", self.protocol["fetch_item"]["errors"])
        self.assertIn("exists", self.protocol["open_change"]["errors"])
        self.assertIn("rejected", self.protocol["open_change"]["errors"])

    def test_the_operation_set_is_unchanged(self):
        """The spike did not find a missing operation; it found wrong fields and errors."""
        self.assertEqual(set(self.protocol), set(OPERATIONS))


class TestDriverContract(unittest.TestCase):
    """The checklist is derived from the protocol, and its rows say something."""

    @classmethod
    def setUpClass(cls):
        cls.text = DRIVER_CONTRACT.read_text(encoding="utf-8")
        cls.protocol = json_block(SKILL.read_text(encoding="utf-8"), "driver-protocol")
        cls.rows = dict(re.findall(r"(?m)^\|\s*`(\w+)`\s*\|\s*(.+?)\s*\|\s*$", cls.text))

    def test_every_operation_has_exactly_one_obligation_row(self):
        self.assertEqual(set(self.rows) & set(self.protocol), set(self.protocol),
                         f"operations without a row: {sorted(set(self.protocol) - set(self.rows))}")

    def test_no_row_names_an_operation_the_protocol_does_not_declare(self):
        strays = [r for r in self.rows if r not in self.protocol and r in OPERATIONS]
        self.assertEqual(strays, [])

    def test_each_row_names_its_operation_s_own_errors(self):
        """A row saying 'implement fetch_item' is a row that says nothing."""
        for name, obligation in self.rows.items():
            if name not in self.protocol:
                continue
            with self.subTest(operation=name):
                self.assertGreater(len(obligation), 60,
                                   "an obligation must say what implementing means")
                item_errors = [e for e in self.protocol[name]["errors"]
                               if e not in FAILURE_CLASSES]
                for error in item_errors:
                    self.assertIn(error, obligation,
                                  f"{name}'s row does not mention its {error} case")

    def test_the_cross_cutting_obligations_are_present(self):
        low = norm(self.text)
        for phrase in ("never runs a gate", "never writes to the worktree",
                       "nothing more", "decides nothing"):
            with self.subTest(obligation=phrase):
                self.assertIn(phrase, low)

    def test_the_mapping_records_what_the_spike_overturned(self):
        """The decisions are visible, not embedded in whichever refinement shipped."""
        low = norm(self.text)
        self.assertIn("rejected", low)
        self.assertIn("updated_at", self.text)
        for name in ("unavailable", "rate_limited", "unauthorized", "unusable"):
            with self.subTest(cls=name):
                self.assertIn(name, self.text)

    def test_every_spike_scenario_appears_in_the_mapping(self):
        """A scenario with no row is a case the contract does not say how to map."""
        low = norm(self.text)
        for phrase in ("general comment", "review comment", "review submitted",
                       "check failed", "merged", "transport", "auth", "rate limit", "malformed"):
            with self.subTest(scenario=phrase):
                self.assertIn(phrase, low)


class TestDriverDocuments(unittest.TestCase):
    """What each driver declares it implements, checked against the protocol."""

    def declared(self, path):
        return json_block(path.read_text(encoding="utf-8"), "implements")

    def test_the_github_driver_implements_the_whole_protocol(self):
        protocol = json_block(SKILL.read_text(encoding="utf-8"), "driver-protocol")
        self.assertEqual(set(self.declared(GITHUB_DRIVER)), set(protocol),
                         "there is no partial conformance: a caller cannot know which half it has")

    def test_the_jira_driver_implements_nothing(self):
        """A stub returning 'not implemented' would make `source_driver: jira` a value the lint
        accepts and the pipeline fails on later. The obligation is documented instead."""
        self.assertEqual(self.declared(JIRA_DRIVER), [],
                         "an obligation document that claims an operation is the stub this rejects")

    def test_the_jira_document_names_what_a_driver_would_have_to_satisfy(self):
        text = JIRA_DRIVER.read_text(encoding="utf-8")
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                self.assertIn(operation, text)

    def test_the_jira_document_names_where_the_protocol_assumes_github(self):
        """The useful part of an obligation: where a second driver would force a protocol change."""
        low = norm(JIRA_DRIVER.read_text(encoding="utf-8"))
        self.assertRegex(low, r"assum|would force|does not map")

    def test_the_github_driver_maps_every_failure_class_in_its_table(self):
        """Each class needs a **mapping row**, not a mention.

        Asserting the word appeared anywhere in the file passed with the `unauthorized` row deleted,
        because the prose below the table also names it — while explaining a distinction the table no
        longer drew.
        """
        text = GITHUB_DRIVER.read_text(encoding="utf-8")
        rows = re.findall(r"(?m)^\|([^|]+)\|\s*`(\w+)`\s*\|([^|]+)\|\s*$", text)
        mapped = {cls for _signal, cls, _action in rows}
        self.assertEqual(mapped & set(FAILURE_CLASSES), set(FAILURE_CLASSES),
                         f"classes with no mapping row: "
                         f"{sorted(set(FAILURE_CLASSES) - mapped)}")
        for signal, cls, action in rows:
            if cls in FAILURE_CLASSES:
                with self.subTest(cls=cls):
                    self.assertTrue(signal.strip(), f"{cls} has no signal")
                    self.assertTrue(action.strip(), f"{cls} has no action")


class TestBoundaryLint(unittest.TestCase):
    """`gh` is invoked in one place. The rule is syntactic — no judgement is left in it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)

    def lint(self, *paths, root=None):
        return subprocess.run(
            [sys.executable, str(BOUNDARY_LINT), "--root", str(root or self.ws), *map(str, paths)],
            capture_output=True, text=True, timeout=60)

    def write(self, name, text):
        path = self.ws / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_the_repository_passes_its_own_check(self):
        result = subprocess.run(
            [sys.executable, str(BOUNDARY_LINT), "--root", str(REPO_ROOT)],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_fenced_invocation_fails(self):
        path = self.write("core.md", "# core\n\n```sh\ngh pr create --fill\n```\n")
        result = self.lint(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("core.md", result.stdout + result.stderr)

    def test_an_inline_code_span_invocation_fails(self):
        path = self.write("core.md", "# core\n\nRun `gh issue view 4` to fetch it.\n")
        self.assertNotEqual(self.lint(path).returncode, 0)

    def test_a_bare_mention_passes(self):
        path = self.write("core.md", "# core\n\nThe gh CLI is reached through the driver.\n")
        self.assertEqual(self.lint(path).returncode, 0, "a bare mention is not an invocation")

    def test_a_cross_reference_passes(self):
        path = self.write("core.md", "# core\n\nSee [the github driver](drivers/github.md).\n")
        self.assertEqual(self.lint(path).returncode, 0)

    def test_subcommands_beyond_the_obvious_three_are_caught(self):
        """One command form proving the check works says nothing about the others."""
        for subcommand in ("repo", "run", "workflow", "release", "auth"):
            with self.subTest(subcommand=subcommand):
                path = self.write(f"core-{subcommand}.md",
                                  "# core\n\n```sh\ngh %s list\n```\n" % subcommand)
                self.assertNotEqual(self.lint(path).returncode, 0)

    def test_a_subprocess_argument_in_a_script_is_caught(self):
        path = self.write("helper.py",
                          "import subprocess\n"
                          "subprocess.run(['gh', 'pr', 'view'])\n")
        self.assertNotEqual(self.lint(path).returncode, 0)

    def test_a_string_invocation_in_a_script_is_caught(self):
        path = self.write("helper.py", 'CMD = "gh api repos/o/r/issues/1"\n')
        self.assertNotEqual(self.lint(path).returncode, 0)

    def test_bare_gh_with_no_subcommand_never_fails(self):
        path = self.write("core.md", "# core\n\n```sh\ngh\n```\n")
        self.assertEqual(self.lint(path).returncode, 0,
                         "`gh` alone is not a command form and flagging it would be noise")

    def test_the_github_driver_is_the_one_place_it_is_allowed(self):
        allowed = self.write("skills/issue2pr/drivers/github.md",
                             "# github\n\n```sh\ngh pr create --fill\n```\n")
        result = self.lint(allowed)
        self.assertEqual(result.returncode, 0, "the driver is where gh belongs")


if __name__ == "__main__":
    unittest.main()
