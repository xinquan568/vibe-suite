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
import shutil
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


def classify(fixture):
    """The failure-classification rule, **applied here** rather than read out of the fixture.

    The first version of this spike wrote `_class` and `_retryable` into each fixture and asserted them
    back — which decorates a decision rather than justifying it, one level deeper than the earlier
    circularity the plan review caught. The fixtures now carry raw facts (status, headers, exit code,
    body) and this function is the rule. A wrong rule fails against the facts; a fixture cannot vouch
    for itself.

    The rule, and why status alone is insufficient:

    - **no response at all** → `unavailable`.
    - **429 → `rate_limited`**, honouring `Retry-After`.
    - **403 carrying `Retry-After`** → `rate_limited` too: a secondary limit is documented as *either*
      status, and the 403 form leaves `remaining` non-zero, so the primary-limit test does not see it.
    - **403 with `x-ratelimit-remaining: 0` and a reset** → `rate_limited` (primary limit).
    - **any other 401/403** → `unauthorized`. A 403 merely *carrying* rate-limit headers is not
      throttling: those headers accompany ordinary responses, so classifying on their presence turns a
      permission failure into an infinite retry.
    - **2xx whose body is not the documented shape** → `unusable`.
    """
    status = fixture.get("http_status")
    headers = {k.lower(): v for k, v in (fixture.get("headers") or {}).items()}

    if status is None:
        return "unavailable", True, None
    if status == 429:
        return "rate_limited", True, headers.get("retry-after")
    if status == 403 and headers.get("x-ratelimit-remaining") == "0" and headers.get("x-ratelimit-reset"):
        return "rate_limited", True, headers.get("x-ratelimit-reset")
    # A secondary limit is documented as **403 or 429**, and the 403 form carries `Retry-After` while
    # leaving `remaining` non-zero. Mapping every non-primary 403 to `unauthorized` stopped a run that
    # would have succeeded after the stated wait.
    if status == 403 and headers.get("retry-after"):
        return "rate_limited", True, headers.get("retry-after")
    if status in (401, 403):
        return "unauthorized", False, None
    if 200 <= status < 300 and not isinstance(fixture.get("body"), (list, dict)):
        return "unusable", False, None
    return None, None, None


def is_observation(fixture):
    """A scenario that succeeded, selected by raw facts rather than by a label.

    `_collection` was a hand-written key doing this job, which made the decisive test depend on a
    conclusion I had written into the data it was checking. A successful call is `exit_code == 0` with
    a 2xx — both of which a real invocation produces.
    """
    status = fixture.get("http_status")
    if fixture.get("exit_code") != 0 or not isinstance(status, int) or not 200 <= status < 300:
        return False
    # The malformed fixture is *also* a 200 that exited 0 — that is its whole point. What separates an
    # observation from it is that the body parsed into the documented structure rather than staying a
    # bare string, which is a fact about the payload and not a label about it.
    return isinstance(fixture.get("body"), (list, dict))


def takes_since(fixture):
    """Whether the recorded invocation actually passes a time parameter.

    Derived from the invocation string, not from a hand-written boolean — the boolean was mine, and a
    test asserting my own label proves only that I wrote it down twice.
    """
    return "since=" in fixture.get("_invocation", "")


class TestSpikeFixtures(unittest.TestCase):
    """The evidence, and it must be evidence rather than a label.

    Each fixture records the invocation that produces it, a documentation URL for the shape, and the
    **raw** response facts. Nothing here reads a conclusion out of a fixture: the conclusions are
    computed above and compared against what the driver and the protocol claim.
    """

    @classmethod
    def setUpClass(cls):
        cls.fixtures = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                        for p in sorted(SPIKE.glob("*.json"))}

    def test_the_scenario_set_is_complete(self):
        expected = {"new-general-comment", "new-review-comment", "review-submitted",
                    "check-failed", "merged", "failure-transport", "failure-auth",
                    "failure-auth-403", "failure-rate-limit", "failure-secondary-limit",
                    "failure-secondary-limit-403", "failure-malformed"}
        self.assertEqual(set(self.fixtures), expected)

    def test_every_fixture_records_a_concrete_invocation_and_a_documentation_url(self):
        """`invocation: any` and a prose label are not records — the earlier set had both."""
        for name, payload in self.fixtures.items():
            with self.subTest(fixture=name):
                invocation = payload.get("_invocation", "")
                self.assertRegex(invocation, r"^gh\s+\w",
                                 f"{name}: the invocation must be a concrete gh command")
                self.assertRegex(payload.get("_docs", ""), r"^https://",
                                 f"{name}: _docs must be a documentation URL, not a description")

    def test_every_fixture_carries_raw_response_facts(self):
        for name, payload in self.fixtures.items():
            with self.subTest(fixture=name):
                for field in ("http_status", "headers", "exit_code", "body"):
                    self.assertIn(field, payload, f"{name} omits the raw field {field}")
                for verdict in ("_class", "_retryable", "_since_supported", "_collection"):
                    self.assertNotIn(verdict, payload,
                                     f"{name} carries a hand-written verdict; the rule computes it")

    def test_the_rule_classifies_every_failure_fixture(self):
        expected = {
            "failure-transport": ("unavailable", True),
            "failure-auth": ("unauthorized", False),
            "failure-auth-403": ("unauthorized", False),
            "failure-rate-limit": ("rate_limited", True),
            "failure-secondary-limit": ("rate_limited", True),
            "failure-secondary-limit-403": ("rate_limited", True),
            "failure-malformed": ("unusable", False),
        }
        for name, (want_class, want_retryable) in expected.items():
            with self.subTest(fixture=name):
                got_class, got_retryable, _when = classify(self.fixtures[name])
                self.assertEqual(got_class, want_class)
                self.assertEqual(got_retryable, want_retryable)

    def test_a_403_without_throttling_evidence_is_not_retryable(self):
        """The fixture that makes status-alone insufficient.

        Rate-limit headers accompany **ordinary** responses, so a 403 that merely carries them is not
        throttled. Classifying on their presence would turn a permission failure into an infinite
        retry — which is the failure the four classes exist to prevent.
        """
        cls, retryable, _ = classify(self.fixtures["failure-auth-403"])
        self.assertEqual(cls, "unauthorized")
        self.assertFalse(retryable)
        headers = self.fixtures["failure-auth-403"]["headers"]
        self.assertIn("x-ratelimit-remaining", headers,
                      "the point of this fixture is that the headers ARE present")
        self.assertNotEqual(headers["x-ratelimit-remaining"], "0")

    def test_both_throttling_forms_carry_when_to_retry(self):
        """Without a time, `rate_limited` is indistinguishable from `unavailable` and a wait is a spin.
        Primary limits give a reset; secondary limits give `Retry-After`."""
        for name in ("failure-rate-limit", "failure-secondary-limit",
                     "failure-secondary-limit-403"):
            with self.subTest(fixture=name):
                cls, retryable, when = classify(self.fixtures[name])
                self.assertEqual(cls, "rate_limited")
                self.assertTrue(retryable)
                self.assertIsNotNone(when, "a retryable-later class must say when")

    def test_the_observation_scenarios_disagree_about_since(self):
        """Derived from the invocations. This is what fixed `since`'s meaning."""
        supported = {n: takes_since(p) for n, p in self.fixtures.items() if is_observation(p)}
        self.assertEqual(len(supported), 5, "five observation scenarios")
        self.assertTrue(any(supported.values()), "some sources can filter")
        self.assertFalse(all(supported.values()),
                         "if every source could filter, the driver-filters rule would be moot")

    def test_a_since_bearing_invocation_uses_an_explicit_get(self):
        """`gh api` sends POST once fields are added, so a query parameter needs `-X GET`."""
        for name, payload in self.fixtures.items():
            if not takes_since(payload):
                continue
            with self.subTest(fixture=name):
                self.assertIn("-X GET", payload["_invocation"],
                              "adding a field without -X GET turns the read into a write")

    def test_the_observation_scenarios_are_four_or_more_distinct_endpoints(self):
        """The fact that rejected `updated_at` — and every input to it is raw.

        Scenarios are selected by `exit_code`/`http_status`; endpoints come from `_invocation`. No
        hand-written label participates, which was the defect the last two attempts kept: the first
        read `_collection` as a conclusion, the second stopped reading it as a conclusion but still used
        it to choose which fixtures to look at.
        """
        endpoints = {re.sub(r"\{[^}]+\}", "*", p["_invocation"])
                     for p in self.fixtures.values() if is_observation(p)}
        self.assertGreaterEqual(len(endpoints), 4,
                                f"a single timestamp cannot speak for {len(endpoints)} endpoints: "
                                f"{sorted(endpoints)}")

    def test_no_two_observation_scenarios_share_an_endpoint(self):
        """Two scenarios on one endpoint would be one observation described twice."""
        seen = {}
        for name, payload in self.fixtures.items():
            if not is_observation(payload):
                continue
            endpoint = re.sub(r"\{[^}]+\}", "*", payload["_invocation"])
            with self.subTest(scenario=name):
                self.assertNotIn(endpoint, seen,
                                 f"{name} and {seen.get(endpoint)} read the same endpoint")
            seen[endpoint] = name

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
        # A **list**, not a dict. Converting to a dict collapsed duplicate rows before the test named
        # "exactly one" could see them — so a contract with two conflicting rows for an operation
        # passed the check that exists to forbid exactly that.
        cls.rows = re.findall(r"(?m)^\|\s*`(\w+)`\s*\|\s*(.+?)\s*\|\s*$", cls.text)
        cls.by_operation = {}
        for name, obligation in cls.rows:
            cls.by_operation.setdefault(name, []).append(obligation)

    def test_every_operation_has_exactly_one_obligation_row(self):
        from collections import Counter
        counts = Counter(name for name, _ in self.rows)
        for operation in self.protocol:
            with self.subTest(operation=operation):
                self.assertEqual(counts[operation], 1,
                                 f"{operation} has {counts[operation]} rows; two conflicting "
                                 f"obligations is worse than none")

    def test_no_operation_shaped_row_is_undeclared(self):
        """Restricting strays to a fixed tuple let an arbitrary invented operation row pass."""
        declared = set(self.protocol)
        for name, _obligation in self.rows:
            if name in FAILURE_CLASSES or not re.fullmatch(r"[a-z]+_[a-z_]+", name):
                continue                       # a failure class or a field name, not an operation
            with self.subTest(row=name):
                self.assertIn(name, declared,
                              f"{name!r} reads as an operation the protocol does not declare")

    def test_each_row_names_its_operation_s_own_errors(self):
        """A row saying 'implement fetch_item' is a row that says nothing."""
        for name, obligation in self.rows:
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


class TestDriverTemporalObligations(unittest.TestCase):
    """The two operations that take a time, and what implementing that actually requires."""

    @classmethod
    def setUpClass(cls):
        cls.text = GITHUB_DRIVER.read_text(encoding="utf-8")
        cls.protocol = json_block(SKILL.read_text(encoding="utf-8"), "driver-protocol")

    def test_the_since_bearing_calls_use_an_explicit_get(self):
        """`gh api` becomes a POST once a field is added, so the obvious spelling turns a read into a
        write. This is not a style point."""
        for line in self.text.splitlines():
            if "since=" in line and line.strip().startswith("gh api"):
                with self.subTest(line=line.strip()):
                    self.assertIn("-X GET", line)

    def test_the_collections_that_cannot_filter_declare_their_predicate(self):
        """Three of five take no time parameter, so the driver filters — and must say how."""
        low = norm(self.text)
        for predicate in ("submitted_at", "completed_at", "started_at", "updatedat"):
            with self.subTest(predicate=predicate):
                self.assertIn(predicate, low)

    def test_state_and_mergeable_are_described_as_current_not_deltas(self):
        """Reporting them unconditionally makes every poll look like a transition."""
        low = norm(self.text)
        self.assertRegex(low, r"current values, not deltas|not deltas")

    def test_refresh_item_takes_the_previous_snapshot(self):
        """`title_changed`/`body_changed` cannot come from a re-read: no per-field history exists, and
        `updatedAt` moves for any edit. A driver that remembered instead would give answers that
        depend on which process asked."""
        self.assertIn("previous_snapshot", self.protocol["refresh_item"]["in"])
        self.assertIn("previous_snapshot", self.text)


class TestFailureMappingMatchesTheRule(unittest.TestCase):
    """The driver's table and the rule the tests apply must agree, or one of them is decoration."""

    def test_the_driver_distinguishes_a_403_that_is_not_throttling(self):
        low = norm(GITHUB_DRIVER.read_text(encoding="utf-8"))
        self.assertIn("x-ratelimit-remaining: 0", low)
        self.assertRegex(low, r"accompany ordinary responses|proves nothing")

    def test_the_driver_maps_secondary_limits(self):
        low = norm(GITHUB_DRIVER.read_text(encoding="utf-8"))
        self.assertIn("429", low)
        self.assertIn("retry-after", low)

    def test_the_driver_bounds_retries(self):
        low = norm(GITHUB_DRIVER.read_text(encoding="utf-8"))
        self.assertRegex(low, r"bounded|not to retry indefinitely")


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

    def test_only_the_exact_driver_path_is_exempt(self):
        """A boundary a caller can step around by naming a file is not a boundary.

        The basename fallback exempted any `drivers/github.md` — including one the recursive corpus
        finds at a nested path, which is a direct route around the check.
        """
        nested = self.write("skills/issue2pr/vendor/drivers/github.md",
                            "# not the driver\n\n```sh\ngh pr create --fill\n```\n")
        result = self.lint(nested, root=self.ws)
        self.assertNotEqual(result.returncode, 0,
                            "only skills/issue2pr/drivers/github.md is exempt")

    def test_a_target_outside_the_root_is_refused_rather_than_judged(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        stray = outside / "github.md"
        stray.write_text("```sh\ngh pr create\n```\n", encoding="utf-8")
        result = self.lint(stray, root=self.ws)
        self.assertNotEqual(result.returncode, 0)

    def test_a_tilde_fence_is_scanned_too(self):
        """CommonMark has two fence forms; recognising one let commands through a scanned location."""
        path = self.write("core.md", "# core\n\n~~~sh\ngh pr create --fill\n~~~\n")
        self.assertNotEqual(self.lint(path).returncode, 0)

    def test_unparseable_python_fails_closed(self):
        """Returning no hits treated 'I could not look' as 'there is nothing there'."""
        path = self.write("broken.py", 'def f(:\n    CMD = "gh pr create"\n')
        result = self.lint(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unparseable", (result.stdout + result.stderr).lower())

    def test_profile_init_is_the_one_pre_profile_exemption(self):
        """`profile init` runs when no profile exists, and the driver is chosen by `source_driver`
        **in a profile** — so routing it through a driver would need the profile it is creating.

        The exemption is narrow on purpose: that one file, for identity and reachability probes only.
        A sibling reference does not inherit it.
        """
        allowed = self.write("skills/issue2pr/references/profile-init.md",
                             "# init\n\n```sh\ngh issue list --limit 1\n```\n")
        self.assertEqual(self.lint(allowed).returncode, 0)
        sibling = self.write("skills/issue2pr/references/profile-contract.md",
                             "# contract\n\n```sh\ngh issue list --limit 1\n```\n")
        self.assertNotEqual(self.lint(sibling).returncode, 0,
                            "the exemption is one file, not the references directory")

    def test_the_bootstrap_exemption_covers_only_the_two_named_probes(self):
        """A per-file skip cannot enforce a claim about *which* probes.

        The exemption is argued as "two read-only probes"; skipping the whole file would also have
        exempted a mutating `gh pr create` placed in it, which is a different and much larger claim.
        """
        mutating = self.write("skills/issue2pr/references/profile-init.md",
                              "# init\n\n```sh\ngh pr create --fill\n```\n")
        result = self.lint(mutating)
        self.assertNotEqual(result.returncode, 0,
                            "a mutating command is not one of the named probes")

    def test_a_probe_chained_with_a_mutating_command_is_not_allowed(self):
        """An exemption is a claim about a line, so it has to hold for all of it.

        Matching the first invocation and exempting the whole snippet let everything after `&&` ride
        along on the prefix.
        """
        chained = self.write("skills/issue2pr/references/profile-init.md",
                             "# init\n\n```sh\ngh api user && gh pr create --fill\n```\n")
        self.assertNotEqual(self.lint(chained).returncode, 0)

    def test_both_named_probes_are_allowed_in_the_bootstrap_file(self):
        for probe in ("gh api user --jq .login", "gh issue list --repo o/r --limit 1"):
            with self.subTest(probe=probe):
                allowed = self.write("skills/issue2pr/references/profile-init.md",
                                     "# init\n\n```sh\n%s\n```\n" % probe)
                self.assertEqual(self.lint(allowed).returncode, 0)

    def test_the_github_driver_is_the_one_place_it_is_allowed(self):
        allowed = self.write("skills/issue2pr/drivers/github.md",
                             "# github\n\n```sh\ngh pr create --fill\n```\n")
        result = self.lint(allowed)
        self.assertEqual(result.returncode, 0, "the driver is where gh belongs")


if __name__ == "__main__":
    unittest.main()
