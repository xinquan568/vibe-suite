#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The issue2pr core/profile split (E5.3 / vibe-42).

F6.2 ports the nine-step three-phase pipeline; §11.3 splits it into a **project-neutral core** plus a
versioned **profile contract**. The invariant that decides every question here: core is project-neutral,
and §11.3's field list is the *minimum* the profile must define — not the maximum core must surrender.
An unenumerated project-bound fact maps onto an existing field or forces a versioned contract
extension; it never stays in core because nobody wrote it down.

**Three tiers, named before anything claims coverage** — the split link 2 arrived at:

- **Executable** — `profile_lint.py`, `profile_manifest.py`, `watch_pr.py` are real programs and are
  driven as subprocesses here.
- **Contract** — what the core *states*: nine citations, `## Round bounds`, the schemas, mode
  semantics, the refusal, zero project literals.
- **Operator** — that a host session *reading the markdown* performs the nine steps. `VIBE_SUITE_CODEX_BIN`
  substitutes the inner codex executable; it does not execute a markdown skill. The golden runs under
  `tests/fixtures/issue2pr/golden/` were performed by hand and committed; what CI checks is that they
  match what the core declares, not that a fresh reading reproduces them.

**Zero project literals needs a subject, and it is not `vibe-suite`.** That string is the plugin
namespace, the config filename, and a component of every core path — grepping for it would fail files
that cannot avoid it. What is forbidden is a *target-project value*: a repo slug, an issue-id prefix, a
branch template, a gate command. This repository is both the product and, in the source skill, a target
project, so `xinquan568/vibe-suite` as a `--repo` value is forbidden while `vibe-suite` as a namespace
is required.
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
SKILL = REPO_ROOT / "skills" / "issue2pr" / "SKILL.md"
CONTRACT_REF = REPO_ROOT / "skills" / "issue2pr" / "references" / "profile-contract.md"
INVENTORY = REPO_ROOT / "skills" / "issue2pr" / "references" / "boundary-inventory.md"
COMMAND = REPO_ROOT / "commands" / "issue2pr.md"
PR_TEMPLATE = REPO_ROOT / "skills" / "issue2pr" / "templates" / "pr-body.md"
ROAMEX = REPO_ROOT / "skills" / "issue2pr" / "examples" / "profiles" / "roamex.md"
LINT = REPO_ROOT / "scripts" / "profile_lint.py"
MANIFEST = REPO_ROOT / "scripts" / "profile_manifest.py"
DRIVER_CONTRACT = REPO_ROOT / "skills" / "issue2pr" / "references" / "driver-contract.md"
OPERATIONAL_MODES = REPO_ROOT / "skills" / "issue2pr" / "references" / "operational-modes.md"
WATCH = REPO_ROOT / "scripts" / "watch_pr.py"
MANIFEST_SCHEMA = REPO_ROOT / "schemas" / "manifest.schema.json"
MANIFEST_ENTRY = REPO_ROOT / "scripts" / "manifest_entry.py"
SLUG_TOOL = REPO_ROOT / "scripts" / "issue2pr_slug.py"
EXAMPLE_MANIFEST = REPO_ROOT / "skills" / "issue2pr" / "examples" / "manifests" / "example.json"
EXAMPLE_BRIEF = REPO_ROOT / "skills" / "issue2pr" / "examples" / "manifests" / "brief.md"
REVIEWER_CONTRACT = REPO_ROOT / "skills" / "vibe-core" / "references" / "reviewer-contract.md"

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "issue2pr"
PROFILES = FIXTURES / "profiles"
MANIFESTS = FIXTURES / "manifests"

#: The core files. `examples/` and `tests/fixtures/` are excluded by construction: a reference profile
#: is *required* to contain project values. `INVENTORY` is excluded for the same reason from the other
#: side: it is the inventory *of* the forbidden literals and so contains every one of them.
CORE_FILES = (SKILL, CONTRACT_REF, COMMAND, PR_TEMPLATE, LINT, MANIFEST,
              DRIVER_CONTRACT, OPERATIONAL_MODES, WATCH,
              MANIFEST_SCHEMA, MANIFEST_ENTRY, SLUG_TOOL)

#: Everything the port must have produced. Wider than `CORE_FILES` — membership here is "this file
#: must exist", not "this file must be project-neutral".
#:
#: This set is what makes the `if not path.is_file(): continue` guards in the content checks below
#: safe. A content check has nothing to read in a missing file, so skipping is right *there*; the
#: defect it used to hide was that nothing asserted the set was complete, so naming a file that did
#: not exist passed every check silently. `test_every_deliverable_exists` closes that, and it does
#: **not** skip.
#: The examples sit here and **not** in `CORE_FILES`, which is `ROAMEX`'s position: reference material
#: is exempt from the literal check because it may legitimately carry project values, not because it
#: is ungoverned. A deliverable that can vanish without failing anything is not a deliverable.
DELIVERABLES = CORE_FILES + (ROAMEX, INVENTORY, EXAMPLE_MANIFEST, EXAMPLE_BRIEF)

#: Target-project values that actually passed through this port. Two projects had material in the
#: source — Roamex, and this repository *as a target* — plus the fixture's.
#: Note what is **not** here: the bare word `roamex`. The core legitimately points at
#: `examples/profiles/roamex.md` — that is a cross-reference to a file, not a project value embedded
#: in configuration. The same distinction as `vibe-suite`-the-namespace versus
#: `xinquan568/vibe-suite`-the-target, one level down. What is forbidden is the value a profile would
#: supply: a repo slug, an id prefix, a branch template, a checkout path.
def _source_literals():
    """The forbidden set, **derived from the boundary inventory** rather than kept here.

    A blacklist maintained in the test file and an inventory maintained in the artifact are two
    statements of one set, and they diverge the first time someone updates only the one they were
    looking at. The inventory is the reviewed artifact, so it is the source.
    """
    text = INVENTORY.read_text(encoding="utf-8")
    match = re.search(r"(?s)<!--\s*source-literals\s*-->\s*```json\s*(\[.*?\])\s*```", text)
    if not match:
        # Returning an empty tuple made every zero-literals assertion pass vacuously — the check
        # would report success precisely when its input had gone missing.
        raise AssertionError("the boundary inventory declares no source-literals block; the "
                             "zero-literals check has no input and must not pass by default")
    literals = tuple(json.loads(match.group(1)))
    if not literals:
        raise AssertionError("the source-literals block is empty")
    return literals


FORBIDDEN_IN_CORE = _source_literals()

CITED_FRAGMENTS = (
    "reviewer-backends", "review-modes", "round-bounds", "verdict-parsing",
    "the-closure-machine", "same-model-refusal-and-self-review", "model-resolution",
    "provenance", "anti-sycophancy", "untrusted-input",   # vibe-187: the tenth section
)

REQUIRED_PROFILE_FIELDS = frozenset({
    "contract_version", "project_id", "repo_id", "repo_path", "base_branch",
    "source_driver", "id_pattern", "url_regex", "branch_template", "gates",
})
OPTIONAL_PROFILE_FIELDS = frozenset({
    "gate_mechanics", "pr_body_template", "tdd_policy", "anti_patterns",
    "mental_model_refs", "category_extensions", "scenario_overrides", "reviewer_backend",
})

ROUND_DOMAIN = {"floor": 2, "ceiling": 5, "default": 2}

MODEL_PIN = re.compile(
    r"\b(?:gpt-\d|o\d-|gemini-\d|claude-(?:opus|sonnet|haiku|fable)-\d|claude-[a-z]+-20\d{2})", re.I)


def norm(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


def json_block(text, marker):
    """A named ```json block from the core, so a schema is parsed rather than grepped."""
    match = re.search(r"(?s)<!--\s*%s\s*-->\s*```json\s*(.*?)```" % re.escape(marker), text)
    if not match:
        return None
    return json.loads(match.group(1))


class TestArtifacts(unittest.TestCase):
    def test_every_deliverable_exists(self):
        """The completeness assertion the content checks rely on.

        It iterates `DELIVERABLES` rather than a literal tuple of its own: a second list drifts from
        the first, and the drift is invisible because both keep passing. Adding a name to
        `CORE_FILES` before the file exists must fail *here*.
        """
        for path in DELIVERABLES:
            with self.subTest(artifact=path.name):
                self.assertTrue(path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing")

    def test_no_project_named_script_survives(self):
        """`roamex-manifest.py` is genericised, not carried."""
        strays = sorted(p.relative_to(REPO_ROOT).as_posix()
                        for p in (REPO_ROOT / "scripts").rglob("roamex*"))
        self.assertEqual(strays, [], f"a project-named script survived the port: {strays}")

    def test_no_usable_profile_ships(self):
        """D2. The reference example is the only profile in the tree, and it lives under examples/."""
        # A *profile* is a file in a `profiles/` directory. Matching on the name instead caught
        # `profile-contract.md`, which is the contract profiles are written against — the opposite of
        # a shipped profile.
        shipped = sorted(p.relative_to(REPO_ROOT).as_posix()
                         for p in (REPO_ROOT / "skills" / "issue2pr").rglob("*.md")
                         if p.parent.name == "profiles")
        for path in shipped:
            with self.subTest(profile=path):
                self.assertIn("examples/", path,
                              "D2: no usable profile ships; a profile outside examples/ is one")


class TestZeroProjectLiterals(unittest.TestCase):
    """The check that gives §11.3 item 2 teeth — and its stated limit."""

    def test_core_carries_no_target_project_value(self):
        offenders = []
        for path in CORE_FILES:
            if not path.is_file():
                continue
            low = path.read_text(encoding="utf-8").lower()
            for value in FORBIDDEN_IN_CORE:
                if value.lower() in low:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {value!r}")
        self.assertEqual(offenders, [],
                         "core must carry zero target-project values:\n  " + "\n  ".join(offenders))

    def test_the_product_namespace_is_not_forbidden(self):
        """Guards the check against over-reach: `vibe-suite` is required in core, not prohibited."""
        for value in FORBIDDEN_IN_CORE:
            with self.subTest(value=value):
                self.assertNotEqual(value.lower(), "vibe-suite",
                                    "the plugin namespace is not a target-project value")
        self.assertIn("/vibe-suite:", SKILL.read_text(encoding="utf-8"),
                      "core names its own namespace, which the check must permit")

    def test_the_example_profile_is_not_graded_as_core(self):
        """A reference profile is *required* to contain project values."""
        self.assertNotIn(ROAMEX, CORE_FILES)
        self.assertIn("roam", ROAMEX.read_text(encoding="utf-8").lower(),
                      "the reference example must carry real project values to be a reference")


class TestBoundaryInventory(unittest.TestCase):
    """D2 operationalised: a reviewable classification, not a prose rule applied silently."""

    @classmethod
    def setUpClass(cls):
        # Only the tables under the inventory's own sections. The legend table at the top explains
        # what a disposition *is*, and parsing it reported "Meaning" as an unknown disposition.
        text = INVENTORY.read_text(encoding="utf-8")
        body = text[text.index("## Values"):]
        cls.rows = [(fact, disp) for fact, disp in
                    re.findall(r"(?m)^\|\s*(?!-)([^|]+?)\s*\|\s*([\w-]+)\s*\|", body)
                    if disp not in ("disposition", "New")]

    def test_every_row_carries_a_known_disposition(self):
        self.assertTrue(self.rows, "the inventory must classify at least one fact")
        for fact, disposition in self.rows:
            if disposition in ("disposition", "---"):
                continue
            with self.subTest(fact=fact):
                self.assertIn(disposition,
                              ("profile-field", "contract-extension", "example-only", "assumption"),
                              f"unknown disposition {disposition!r}")

    def test_assumptions_are_recorded(self):
        """The entries a grep can never reach: project-shaped prose with no literal to match."""
        dispositions = [d for _, d in self.rows]
        self.assertIn("assumption", dispositions,
                      "an inventory with no assumption entries has not looked for the facts that "
                      "carry no literal")

    def test_every_profile_field_disposition_names_a_real_field(self):
        text = INVENTORY.read_text(encoding="utf-8")
        for field in re.findall(r"(?m)^\|[^|]+\|\s*profile-field\s*\|\s*`([\w]+)`", text):
            with self.subTest(field=field):
                self.assertIn(field, REQUIRED_PROFILE_FIELDS | OPTIONAL_PROFILE_FIELDS,
                              f"{field!r} is not a field the contract defines")


class TestContractCitations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.headings = {
            re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-")
            for h in re.findall(r"(?m)^#{1,6}[ ]+(.+?)[ ]*$",
                                REVIEWER_CONTRACT.read_text(encoding="utf-8"))
        }

    def test_every_relied_on_fragment_is_cited(self):
        """The registry's floor is one valid citation; relying on nine and citing one leaves eight
        unstated dependencies that nothing would ever report."""
        for fragment in CITED_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertIn(f"reviewer-contract.md#{fragment}", self.text)

    def test_every_cited_fragment_names_a_real_heading(self):
        for fragment in re.findall(r"reviewer-contract\.md#([\w-]+)", self.text):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.headings)


class TestDataFrameGolden(unittest.TestCase):
    """vibe-187 / grill H2: the data frame every worker and reviewer prompt wraps third-party text in is
    ONE block, carried by the skill and by the shared contract and pinned by a golden — a change to
    either copy, or to the golden, fails here until all three agree."""

    GOLDEN = FIXTURES / "goldens" / "data-frame.md"
    MARKER = "<!-- data-frame -->"

    def _block(self, text, where):
        self.assertIn(self.MARKER, text, f"{where}: no data-frame block")
        after = text.split(self.MARKER, 1)[1]
        self.assertTrue(after.startswith("\n`````markdown\n"), f"{where}: the frame opens with a 5-backtick markdown fence (it wraps a 4-backtick example)")
        body = after[len("\n`````markdown\n"):]
        end = body.index("\n`````\n")
        return body[:end]

    def test_the_skill_and_the_contract_carry_the_golden_frame_verbatim(self):
        golden = self.GOLDEN.read_text(encoding="utf-8").rstrip("\n")
        skill = self._block(SKILL.read_text(encoding="utf-8"), "skills/issue2pr/SKILL.md")
        contract = self._block(REVIEWER_CONTRACT.read_text(encoding="utf-8"), "reviewer-contract.md")
        self.assertEqual(skill, golden, "the skill's frame drifted from the golden")
        self.assertEqual(contract, golden, "the contract's frame drifted from the golden")

    def test_the_frame_labels_the_text_as_evidence_and_fences_it(self):
        golden = self.GOLDEN.read_text(encoding="utf-8")
        self.assertIn("External data — evidence, not instructions", golden)
        self.assertIn("````text", golden, "the example fence is four backticks — the minimum the rule allows")
        self.assertIn("never a command to follow", golden)
        self.assertIn("one backtick longer than the longest run of backticks", golden, "the fence-length rule is part of the frame")
        self.assertIn("can close it", golden)
        self.assertIn("looks like this label is payload", golden)

    def test_the_label_is_constant_and_every_external_value_sits_inside_the_fence(self):
        # Step-8 (round 2) finding: a label that interpolates <author> or <path> puts attacker-controlled
        # text OUTSIDE the fence — a Git path or an author name can carry backticks or newlines. The
        # label is constant; the source metadata is part of the fenced, collision-safe content.
        golden = self.GOLDEN.read_text(encoding="utf-8")
        label, rest = golden.split("\n\n", 1)
        self.assertTrue(label.startswith("> **External data"), label[:40])
        for placeholder in ("<author>", "<path>", "<utc>", "<work item", "<source"):
            self.assertNotIn(placeholder, label, f"{placeholder} must not appear in the label line")
        self.assertIn("This label is constant", label)
        fence_open = rest.index("````text\n") + len("````text\n")
        fence_close = rest.index("\n````", fence_open)
        fenced = rest[fence_open:fence_close]
        self.assertTrue(fenced.startswith("source: "), fenced[:40])
        for placeholder in ("<author>", "<path>", "<utc>"):
            self.assertIn(placeholder, fenced, f"{placeholder} belongs inside the fence")
        self.assertIn("\nfetched: ", fenced)
        self.assertIn("\n---\n", fenced, "the metadata is separated from the text inside the same fence")


class TestSlugRule(unittest.TestCase):
    """grill H2 (part c): `{slug}` has one declared shape — `[a-z0-9-]{1,40}`, never `-`-led — stated
    once in the profile contract (`<!-- slug-rule -->`), derived by `scripts/issue2pr_slug.py` from a
    title (the declared steps, or a refusal with a reason) and enforced on a supplied `subtask.slug`
    by the manifest schema. The two statements are pinned equal; the script reads the contract and
    every declared member is consumed; the pattern's semantics are pinned by boundary cases, never by
    a third copy of the regex."""

    MARKER = "slug-rule"
    ACCEPTED = ("a", "0", "a" * 40, "0-9", "a-b-c", "widget-cache-eviction")
    REJECTED = ("", "-x", "A", "a" * 41, "a\n", "a\r\n", "\na", "ä", "a b", "a_b", "a.b", "x\ty", "--")

    @classmethod
    def setUpClass(cls):
        cls.contract = CONTRACT_REF.read_text(encoding="utf-8")
        cls.rule = json_block(cls.contract, cls.MARKER)
        cls.schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))

    def slug(self, title=None, check=None, contract=None):
        # the documented invocation: options first, then `--`, then the title — so a title that
        # begins with `-` (the acceptance's own example) is never read as an option
        cmd = [sys.executable, str(SLUG_TOOL)]
        if contract is not None:
            cmd += ["--contract", str(contract)]
        if check is not None:
            cmd += ["--check=" + check]
        if title is not None:
            cmd += ["--", title]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    def contract_with(self, mutate):
        """A temp copy of the contract whose <!-- slug-rule --> block is re-serialised after
        `mutate(rule)` — no regex literal is needed to edit a member. `mutate` may return a
        replacement text for the whole block (a string) to model a malformed block."""
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        text = self.contract
        m = re.search(r"(?s)(<!--\s*%s\s*-->\s*```json\s*)(.*?)(```)" % re.escape(self.MARKER), text)
        self.assertIsNotNone(m)
        rule = json.loads(m.group(2))
        out = mutate(rule)
        body = out if isinstance(out, str) else json.dumps(rule, indent=2) + "\n"
        text = text[:m.start(2)] + body + text[m.end(2):]
        p = Path(d) / "profile-contract.md"
        p.write_text(text, encoding="utf-8")
        return p

    def test_the_contract_declares_the_rule_once_and_the_schema_enforces_the_same_pattern(self):
        self.assertIsNotNone(self.rule, "profile-contract.md declares no <!-- slug-rule --> block")
        self.assertEqual(self.contract.count("<!-- slug-rule -->"), 1, "the rule is declared exactly once")
        self.assertEqual(set(self.rule), {"pattern", "max_length", "normalise", "empty"})
        pattern = self.rule["pattern"]
        re.compile(pattern)
        self.assertEqual(self.rule["max_length"], 40)
        self.assertEqual(self.rule["empty"], "refuse")
        self.assertEqual(self.rule["normalise"], ["nfkd-ascii-fold", "lowercase", "non-alnum-runs-to-hyphen",
                                                  "strip-hyphens", "truncate-then-strip-hyphens"])
        slug_schema = self.schema["properties"]["subtask"]["properties"]["slug"]
        self.assertEqual(slug_schema.get("pattern"), pattern,
                         "the manifest schema must carry the contract's pattern on subtask.slug")
        # the domain, pinned by boundary cases under the validator's own predicate (re.search) and
        # the script's (re.fullmatch) — the two must agree on every case, trailing newline included
        for good in self.ACCEPTED:
            with self.subTest(accepted=good):
                self.assertTrue(re.search(pattern, good) and re.fullmatch(pattern, good))
        for bad in self.REJECTED:
            with self.subTest(rejected=bad):
                self.assertFalse(re.search(pattern, bad), "re.search (the validator) must reject it")
                self.assertFalse(re.fullmatch(pattern, bad), "re.fullmatch (the script) must reject it")
        skill = SKILL.read_text(encoding="utf-8")
        self.assertNotIn(pattern, skill, "the skill cites the rule; it does not restate the pattern")
        self.assertIn("issue2pr_slug.py", skill)
        self.assertIn("slug-rule", skill)
        self.assertIn("issue2pr_slug.py", self.contract)
        self.assertNotIn(pattern, SLUG_TOOL.read_text(encoding="utf-8"),
                         "the script reads the declaration; it carries no pattern of its own")
        self.assertNotIn(pattern, Path(__file__).read_text(encoding="utf-8"),
                         "this test pins semantics by cases, not by a third copy of the regex")
        row = next(l for l in self.contract.splitlines() if l.startswith("| `branch_template` |"))
        self.assertIn("{slug}", row)
        self.assertIn("never `-`-led", row)

    def test_titles_normalise_to_conforming_slugs_or_are_refused_with_a_reason(self):
        pattern = self.rule["pattern"]
        table = (
            ("-- rm -rf /", "rm-rf"),
            ("  Hello, World!  ", "hello-world"),
            ("Ünïcödé  Tïtle", "unicode-title"),
            ("[grill] H2 — issue2pr: constrain {slug}", "grill-h2-issue2pr-constrain-slug"),
            ("tab\ttitles truncate\n", "tab-titles-truncate"),
            ("title\n", "title"),
            ("a" * 50, "a" * 40),
            ("ab-" * 20, ("ab-" * 20)[:40]),          # the 40th character is `a`: 40 stay
            ("a-" * 30, ("a-" * 19) + "a"),            # the 40th character is `-`: 39 stay
            ("---leading and trailing---", "leading-and-trailing"),
            ("E0.1 repo scaffold", "e0-1-repo-scaffold"),
            ("`rm` $(whoami) ; echo \"x\" | cat", "rm-whoami-echo-x-cat"),
            ("--help", "help"),
            ("-v --version", "v-version"),
        )
        self.assertEqual(len(("ab-" * 20)[:40]), 40)
        self.assertEqual(len(("a-" * 19) + "a"), 39)
        for title, expected in table:
            with self.subTest(title=title):
                r = self.slug(title)
                self.assertEqual(r.returncode, 0, r.stderr)
                slug = r.stdout.rstrip("\n")
                self.assertEqual(slug, expected)
                self.assertTrue(re.fullmatch(pattern, slug))
                self.assertLessEqual(len(slug), 40)
                self.assertFalse(slug.startswith("-"))
                again = self.slug(slug)
                self.assertEqual(again.stdout.rstrip("\n"), slug, "normalisation is idempotent")
        for title in ("", "   ", "—", "\U0001f642\U0001f642", "----", "--", "-", "\n", "中文标题"):
            with self.subTest(refused=title):
                r = self.slug(title)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertEqual(r.stdout, "", "a refusal prints no slug")
                self.assertIn("refused", r.stderr)
                self.assertIn("no slug can be made", r.stderr)
                self.assertIn(repr(title), r.stderr, "the reason names the title")
                self.assertNotIn("Traceback", r.stderr)

    def test_a_supplied_slug_is_checked_against_the_same_rule(self):
        for good in self.ACCEPTED:
            with self.subTest(slug=good):
                r = self.slug(check=good)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.rstrip("\n"), good)
        for bad in self.REJECTED + ("Has Space", "ünï", "Upper", "under_score"):
            with self.subTest(slug=bad):
                r = self.slug(check=bad)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertEqual(r.stdout, "")
                self.assertIn("does not match the declared slug rule", r.stderr)
                self.assertIn(self.rule["pattern"], r.stderr, "the refusal names the pattern")

    def test_a_supplied_manifest_slug_outside_the_rule_is_refused_at_the_entry(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        profile = Path(d) / "profile.md"
        profile.write_text("repo_id: example-repo\nbase_branch: trunk\n", encoding="utf-8")
        example = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))

        def entry(manifest):
            path = Path(d) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            return subprocess.run([sys.executable, str(MANIFEST_ENTRY), str(path),
                                   "--profile", str(profile)],
                                  capture_output=True, text=True, timeout=60, cwd=REPO_ROOT)

        ok = entry(example)
        self.assertEqual(ok.returncode, 0, ok.stderr)   # the shipped example conforms
        for bad in ("--evil", "has space", "ünï", "x" * 41, "Upper-Case", "-lead", "a\n"):
            with self.subTest(slug=bad):
                manifest = json.loads(json.dumps(example))
                manifest["subtask"]["slug"] = bad
                r = entry(manifest)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)   # EXIT_SCHEMA
                self.assertIn("schema", r.stderr)
                self.assertIn("subtask.slug", r.stderr, "the refusal names the member")
                self.assertEqual(r.stdout, "", "no run settings are printed for a refused manifest")

    def test_the_script_derives_the_rule_from_the_contract_fail_closed(self):
        def gap(contract, *named, title="hello world"):
            r = self.slug(title, contract=contract)
            self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
            self.assertIn("declaration gap", r.stderr)
            for n in named:
                self.assertIn(n, r.stderr, "the gap names the member")
            self.assertEqual(r.stdout, "")
            self.assertNotIn("Traceback", r.stderr)

        def removed(member):
            def mutate(rule):
                del rule[member]
            return mutate

        def set_to(member, value):
            def mutate(rule):
                rule[member] = value
            return mutate

        with self.subTest(removed="the whole block (a readable contract with no marker)"):
            d = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, d, True)
            no_marker = re.sub(r"(?s)<!--\s*%s\s*-->\s*```json\s*.*?```\n?" % re.escape(self.MARKER), "", self.contract)
            self.assertNotIn(self.MARKER, no_marker)
            p = Path(d) / "profile-contract.md"
            p.write_text(no_marker, encoding="utf-8")
            gap(p, "block", "slug-rule")
        with self.subTest(removed="every member (an empty object)"):
            gap(self.contract_with(lambda rule: "{}\n"), "pattern")   # the first member is missing
        with self.subTest(malformed="not JSON"):
            gap(self.contract_with(lambda rule: "{not json\n"), "block")
        with self.subTest(malformed="not an object"):
            gap(self.contract_with(lambda rule: "[1]\n"), "block")
        for member in ("pattern", "max_length", "normalise", "empty"):
            with self.subTest(removed=member):
                gap(self.contract_with(removed(member)), member)
        for member, value in (("pattern", ""), ("pattern", 7), ("pattern", "^[a-z("),
                              ("max_length", 0), ("max_length", -1), ("max_length", "40"),
                              ("max_length", True), ("max_length", 4.5),
                              ("normalise", "lowercase"), ("normalise", []), ("normalise", ["shout"]),
                              ("normalise", [1]), ("normalise", ["lowercase", "lowercase", "nope"]),
                              ("empty", "allow"), ("empty", None)):
            with self.subTest(unsupported=(member, value)):
                gap(self.contract_with(set_to(member, value)), member)
        with self.subTest(unexpected="note"):
            gap(self.contract_with(set_to("note", "documentation")), "unexpected member", "note")
        with self.subTest(absent="contract"):
            gap(Path(tempfile.mkdtemp()) / "absent.md", "contract")
        # behaviour follows the declaration: a shorter max_length cuts shorter
        r = self.slug("hello wonderful world", contract=self.contract_with(set_to("max_length", 9)))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.rstrip("\n"), "hello-won")
        # ... dropping the lowercase step changes what a title becomes
        without_lower = self.contract_with(lambda rule: rule["normalise"].remove("lowercase"))
        r = self.slug("Hello World", contract=without_lower)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.rstrip("\n"), "ello-orld")
        # ... the declared ORDER is executed, not a canonical one: with `lowercase` moved after
        # `non-alnum-runs-to-hyphen`, an upper-case letter is still a separator when the runs are
        # replaced, so the same title yields a different slug than under the shipped order
        def swap_lower_after_runs(rule):
            steps = rule["normalise"]
            steps.remove("lowercase")
            steps.insert(steps.index("non-alnum-runs-to-hyphen") + 1, "lowercase")
        reordered = self.contract_with(swap_lower_after_runs)
        r = self.slug("Hello World", contract=reordered)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.rstrip("\n"), "ello-orld", "the altered order is what ran")
        self.assertEqual(self.slug("Hello World").stdout.rstrip("\n"), "hello-world", "the shipped order")
        # ... dropping the strip step lets a leading hyphen through to the pattern, which refuses it
        # (the final truncate step strips on the RIGHT only — rstrip — so the leading `-` survives)
        without_strip = self.contract_with(lambda rule: rule["normalise"].remove("strip-hyphens"))
        r = self.slug("--x", contract=without_strip)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("does not match the declared slug rule", r.stderr)
        # ... and a pattern the declaration narrows is what --check enforces
        narrowed = self.contract_with(set_to("pattern", "^[a-c]+(?![\\s\\S])"))
        self.assertEqual(self.slug(check="abc", contract=narrowed).returncode, 0)
        self.assertEqual(self.slug(check="abd", contract=narrowed).returncode, 2)

    def test_the_cli_refuses_an_ambiguous_or_unseparated_invocation(self):
        neither = self.slug()
        self.assertNotEqual(neither.returncode, 0)
        both = self.slug("title", check="slug")
        self.assertNotEqual(both.returncode, 0)
        # a `-`-led title passed WITHOUT the documented `--` is an option to argparse: the call
        # fails before any slug exists (no run starts on it), and it fails in words
        raw = subprocess.run([sys.executable, str(SLUG_TOOL), "-x"], capture_output=True, text=True, timeout=60)
        self.assertNotEqual(raw.returncode, 0)
        self.assertEqual(raw.stdout, "", "no slug is printed")
        self.assertNotIn("Traceback", neither.stderr + both.stderr + raw.stderr)


class TestCoreSchemas(unittest.TestCase):
    """Parsed, not adjacent. Exact key sets with types at every level."""

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_the_state_schema_is_exact(self):
        state = json_block(self.text, "state-schema")
        self.assertIsNotNone(state, "the core must declare its state schema as a named json block")
        self.assertEqual(set(state), {
            "schema_version", "run_id", "source_id", "profile", "scenario", "review_mode",
            "max_review_rounds", "max_review_rounds_overrides", "current_step", "current_round",
            "status", "areas_confirmed", "repos_in_scope", "pr",
        })
        self.assertIsInstance(state["max_review_rounds_overrides"], dict,
                              "the override map is an object keyed by string round numbers")
        self.assertIsInstance(state["areas_confirmed"], list)
        self.assertIsInstance(state["repos_in_scope"], list)
        self.assertNotIn("crates_confirmed", state, "the fossil does not survive the port")

    def test_the_timeline_entry_is_exact_and_typed(self):
        entry = json_block(self.text, "timeline-entry")
        self.assertIsNotNone(entry, "the core must declare its timeline entry shape")
        self.assertEqual(set(entry), {"step", "phase", "at", "actor", "outcome", "note"})
        self.assertIsInstance(entry["step"], int)
        self.assertIsInstance(entry["note"], str)

    def test_the_snapshot_and_delta_shapes_are_exact_and_typed(self):
        snapshot = json_block(self.text, "source-snapshot")
        delta = json_block(self.text, "source-delta")
        self.assertIsNotNone(snapshot, "the core must declare its source snapshot shape")
        self.assertIsNotNone(delta, "the core must declare its source delta shape")
        self.assertEqual(set(snapshot), {"source_id", "fetched_at", "title", "body", "comments"})
        self.assertIsInstance(snapshot["comments"], list)
        self.assertEqual(set(delta), {"since", "title_changed", "body_changed", "new_comments"})
        self.assertIsInstance(delta["title_changed"], bool)
        self.assertIsInstance(delta["new_comments"], list)

    def test_the_phases_cover_the_nine_steps_without_overlap(self):
        phases = json_block(self.text, "phases")
        self.assertIsNotNone(phases, "the core must declare its phase ranges")
        covered = []
        for name, span in phases.items():
            self.assertEqual(len(span), 2, f"{name}: a phase is a [first, last] pair")
            covered.extend(range(span[0], span[1] + 1))
        self.assertEqual(sorted(covered), list(range(1, 10)),
                         "the three phases must cover steps 1-9 exactly once")

    def test_canonical_step_numbering_is_preserved_in_every_mode(self):
        """A mode that skips a step does not renumber the steps that remain."""
        self.assertRegex(norm(self.text), r"canonical step numbering|step numbers?[^.]{0,40}(never|not) renumber")

    def test_the_severity_rules_are_stated(self):
        low = norm(self.text)
        self.assertRegex(low, r"blocker[^.]{0,60}stops the round")
        self.assertRegex(low, r"major[^.]{0,60}(bounded|update\+verify|loop)")


class TestEffectiveCapResolution(unittest.TestCase):
    """vibe-69. `iterate` may raise the cap for a new round; something must say which cap applies.

    The field recording that override was improvised as a hand-edit before it was declared, and #131
    then referenced it from `operational-modes.md` while the schema still did not carry it. These
    tests close that gap and pin the rule that resolves it.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.modes = (REPO_ROOT / "skills" / "issue2pr" / "references"
                     / "operational-modes.md").read_text(encoding="utf-8")

    def round_bounds_block(self):
        match = re.search(r"(?ms)^## Round bounds[ ]*$(.*?)(?=^## )", self.text)
        self.assertIsNotNone(match, "the core must have a `## Round bounds` section")
        return match.group(1)

    def test_the_schema_declares_the_override_map(self):
        """`operational-modes.md` names this field twice. A document referring to a field the schema
        does not define is the defect vibe-127 existed to correct."""
        state = json_block(self.text, "state-schema")
        self.assertIn("max_review_rounds_overrides", state)
        self.assertIsInstance(state["max_review_rounds_overrides"], dict)

    def formula(self):
        """The fenced resolution, as an ordered list of its fallback terms.

        Extracted structurally rather than matched loosely: an earlier version of this test asserted
        only that two identifiers *occurred* in the section, which a reversed fallback or a changed
        default would have satisfied. The order is the whole content of the rule.
        """
        block = self.round_bounds_block()
        fence = re.search(r"(?s)```\n(effective cap =.*?)```", block)
        self.assertIsNotNone(fence, "the resolution must be a parseable fenced formula")
        terms = []
        for line in fence.group(1).splitlines():
            line = re.sub(r"#.*$", "", line).strip()
            line = re.sub(r"^effective cap\s*=\s*", "", line)
            line = re.sub(r"^\?\?\s*", "", line).strip()
            if line:
                terms.append(line)
        return terms

    def test_the_resolution_falls_back_in_the_specified_order(self):
        """override → base → 2. Reversing the first two makes `iterate` unable to raise the cap at
        all, which is the entire subject of this issue."""
        terms = self.formula()
        self.assertEqual(len(terms), 3, f"three fallback terms expected, got {terms}")
        self.assertIn("max_review_rounds_overrides[current_round]", terms[0].replace(" ", ""),
                      "the per-round override is consulted first, or it can never take effect")
        self.assertRegex(terms[1], r"max_review_rounds\b",
                         "the run-start value is the second term")
        self.assertNotIn("overrides", terms[1], "the second term is the base, not the map again")
        self.assertEqual(terms[2].strip(), "2", "the final fallback is the contract's default of 2")

    def test_the_formula_lives_in_round_bounds_and_nowhere_else(self):
        """Stated once. Two statements of one rule diverge the first time someone edits one.

        The predicate is the **resolution**, not the field name: the schema must be free to declare
        `max_review_rounds_overrides`, and prose must be free to name it. What may not appear twice
        is the ordered fallback that decides which cap applies.
        """
        block = self.round_bounds_block()
        outside = self.text.replace(block, "")
        self.assertIn("effective cap =", block, "the formula belongs here")
        self.assertNotIn("effective cap =", outside,
                         "the core states the resolution once, in `## Round bounds`")

    def test_the_cap_is_defined_as_the_effective_value_not_the_run_start_one(self):
        """Edit (7). A loop bounded by the run-start cap ignores the override entirely."""
        self.assertRegex(norm(self.round_bounds_block()), r"effective",
                         "`## Round bounds` must define the cap the loop uses as the *effective* one")

    def test_an_absent_override_map_means_no_override(self):
        """Legacy tolerance, which is a different predicate from the goldens carrying `{}`.

        Runs written before the field existed have no such key, and they must still resolve rather
        than raise.
        """
        block = self.round_bounds_block()
        # "absent" alone would be satisfied by "an absent map is an error". The rule is what an
        # absent map *resolves to*, so the empty object has to appear with it.
        self.assertRegex(
            norm(block), r"absent[^.]*\{\}|\{\}[^.]*absent",
            "an absent override map must be stated to read as `{}`, not merely mentioned")

    def test_the_override_map_is_keyed_by_string_round_numbers(self):
        """`{"2": 4}`, not `{2: 4}` — JSON round-trips give strings, and the mechanism this was
        modelled on already uses them. A test that ignored the key type would let the two diverge."""
        self.assertRegex(norm(self.text), r'string-typed|"2"',
                         "the core must state that override keys are string-typed round numbers")

    def test_the_three_reference_sites_cite_the_formula(self):
        """Comment 1 on #69: stated once and referenced from resume, iterate and pre-flight."""
        for mode in ("resume", "iterate"):
            section = re.search(r"(?sm)^##\s+`%s`\s*$(.*?)(?=^##\s|\Z)" % mode, self.modes)
            with self.subTest(site=mode):
                self.assertIsNotNone(section)
                self.assertIn("#round-bounds", section.group(1),
                              f"`{mode}` must cite the resolution rather than restate it")
        with self.subTest(site="pre-flight"):
            self.assertRegex(norm(self.text), r"pre-flight[^.]*effective cap|effective cap[^.]*pre-flight",
                             "pre-flight resolves the effective cap and must say so")


class TestRoundBounds(unittest.TestCase):
    """The registry checks this too; here it is checked against the reason as well as the numbers."""

    def test_the_domain_is_this_loop_s_own(self):
        text = SKILL.read_text(encoding="utf-8")
        block = re.search(r"(?ms)^##[ ]Round bounds[ ]*$(.*?)(?=^#{1,2}[ ]|\Z)", text)
        self.assertIsNotNone(block, "the core must declare a '## Round bounds' block")
        body = block.group(1)
        for label, value in ROUND_DOMAIN.items():
            with self.subTest(label=label):
                self.assertRegex(body, r"(?i)\b%s\b\W{0,20}?%d\b" % (label, value))
        self.assertRegex(norm(body), r"because|since|so that",
                         "the floor's reason is part of the contract, not a courtesy")

    def test_the_floor_reason_is_the_update_verify_pairing(self):
        text = norm(SKILL.read_text(encoding="utf-8"))
        self.assertRegex(text, r"update\s*\+?\s*verify|verified",
                         "floor 2 exists because a cap of 1 admits an update no reviewer verified")


class TestCapRename(unittest.TestCase):
    def test_the_cap_uses_the_contract_s_name(self):
        for path in (SKILL, COMMAND):
            with self.subTest(artifact=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("--max-review-rounds", text)
                self.assertNotIn("--max-review-iterations", text,
                                 "the contract's name is `max_review_rounds`; the source spelling "
                                 "does not survive the port")


class TestRefusal(unittest.TestCase):
    """D2's shipped default, and the first thing every user meets."""

    def test_a_run_without_a_profile_refuses_and_points_at_the_scaffolder(self):
        low = norm(SKILL.read_text(encoding="utf-8"))
        self.assertRegex(low, r"refus\w+")
        self.assertIn("profile init", low)

    def test_the_resolution_order_is_stated(self):
        low = norm(SKILL.read_text(encoding="utf-8"))
        self.assertIn("--profile", low)
        self.assertIn(".vibe-suite.md", low)
        self.assertIn("issue2pr_profile", low)


class TestNoPinnedModel(unittest.TestCase):
    def test_no_artifact_names_a_model_id(self):
        for path in DELIVERABLES:
            if not path.is_file():
                continue
            with self.subTest(artifact=path.name):
                hits = [l for l in path.read_text(encoding="utf-8").splitlines()
                        if MODEL_PIN.search(l) and "never" not in l.lower()]
                self.assertEqual(hits, [], f"P9/D6: pinned model id in {path.name}: {hits}")


class TestWatcherIsDriven(unittest.TestCase):
    """The third Executable-tier program, actually run.

    This module's docstring has named `watch_pr.py` as "driven as subprocesses here" since the port.
    It was not — the file did not exist, and nothing invoked it. A tier claimed and not exercised is
    the defect vibe-127 exists to correct, so the claim is discharged here rather than reworded.

    Behaviour lives in `test_issue2pr_modes.py`, which drives the poll loop in-process against an
    injected `gh` and clock. What belongs *here* is the tier's own claim: it is a program, and it
    answers as one.
    """

    def watch(self, *args):
        return subprocess.run([sys.executable, str(WATCH), *args],
                              capture_output=True, text=True, timeout=60)

    def test_it_answers_help(self):
        result = self.watch("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--merge-when-green", result.stdout)

    def test_a_usage_error_exits_one_and_not_argparses_two(self):
        """Exit 2 already means "closed without merge". A typo reporting that code would make a
        chain mark the link `closed_unmerged` and pause."""
        self.assertEqual(self.watch("owner/repo").returncode, 1)

    def test_it_carries_no_repository_of_its_own(self):
        """The repo is an argument. A watcher with a default target is a project literal with a
        control flow attached."""
        self.assertIn("repo", self.watch("--help").stdout)


class LintCase(unittest.TestCase):
    def lint(self, profile, *extra):
        return subprocess.run(
            [sys.executable, str(LINT), "--root", str(REPO_ROOT), str(profile), *extra],
            capture_output=True, text=True, timeout=60)


class TestProfileLint(LintCase):
    """Both directions. A lint tested only on rejection might reject everything."""

    def test_a_conformant_profile_passes(self):
        result = self.lint(PROFILES / "fixture.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_minimal_profile_passes(self):
        """Required fields only. This is what `profile init` emits first, and a lint demanding an
        optional field would block that scaffolder two links from now."""
        result = self.lint(PROFILES / "minimal.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_each_missing_required_field_fails_and_is_named(self):
        base = (PROFILES / "fixture.md").read_text(encoding="utf-8")
        for field in sorted(REQUIRED_PROFILE_FIELDS):
            with self.subTest(field=field):
                broken = re.sub(r"(?m)^%s:.*$\n?" % re.escape(field), "", base, count=1)
                self.assertNotEqual(broken, base, f"could not remove {field} from the fixture")
                path = self._write(broken, f"missing-{field}.md")
                result = self.lint(path)
                self.assertNotEqual(result.returncode, 0, f"{field} missing must fail")
                self.assertIn(field, result.stdout + result.stderr,
                              "the failure must name the field")

    def test_a_wrong_typed_field_fails(self):
        base = (PROFILES / "fixture.md").read_text(encoding="utf-8")
        broken = base.replace("gates:\n  - 'make lint'\n  - 'make test'\n", "gates: 'make test'\n")
        self.assertNotEqual(broken, base)
        result = self.lint(self._write(broken, "gates-scalar.md"))
        self.assertNotEqual(result.returncode, 0, "gates is a list; a scalar must fail")

    def test_an_uncompilable_regex_fails(self):
        base = (PROFILES / "fixture.md").read_text(encoding="utf-8")
        broken = base.replace("id_pattern: '^fx-(\\d+)$'", "id_pattern: '^fx-(\\d+$'")
        self.assertNotEqual(broken, base)
        result = self.lint(self._write(broken, "bad-regex.md"))
        self.assertNotEqual(result.returncode, 0)

    def test_an_unknown_field_fails(self):
        """A typo'd optional field would otherwise be silently ignored."""
        base = (PROFILES / "fixture.md").read_text(encoding="utf-8")
        broken = base.replace("base_branch: trunk", "base_branch: trunk\ntdd_polcy: strict")
        result = self.lint(self._write(broken, "typo-field.md"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tdd_polcy", result.stdout + result.stderr)

    def test_reviewer_backend_defers_to_the_configuration_schema(self):
        """`codex` alone. `copilot-cli` was dropped by operator decision and must be rejected here
        too, rather than each artifact keeping its own idea of the domain."""
        base = (PROFILES / "fixture.md").read_text(encoding="utf-8")
        good = base.replace("base_branch: trunk", "base_branch: trunk\nreviewer_backend: codex")
        self.assertEqual(self.lint(self._write(good, "backend-ok.md")).returncode, 0)
        bad = base.replace("base_branch: trunk", "base_branch: trunk\nreviewer_backend: copilot-cli")
        result = self.lint(self._write(bad, "backend-bad.md"))
        self.assertNotEqual(result.returncode, 0)

    def test_a_contract_version_mismatch_fails(self):
        base = (PROFILES / "fixture.md").read_text(encoding="utf-8")
        broken = base.replace("contract_version: 1", "contract_version: 99")
        result = self.lint(self._write(broken, "version-99.md"))
        self.assertNotEqual(result.returncode, 0)

    def _write(self, text, name):
        import tempfile
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(directory, ignore_errors=True))
        path = directory / name
        path.write_text(text, encoding="utf-8")
        return path


class TestValidationContexts(LintCase):
    """Two contexts, because one would make the shipped reference unshippable.

    A reference profile cannot assume its project is checked out on the machine reading it. Structural
    conformance is portable; environmental validation needs a repository.
    """

    def test_the_roamex_example_conforms_structurally(self):
        result = self.lint(ROAMEX, "--structural-only")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_roamex_example_fails_environmental_validation_and_that_is_correct(self):
        result = self.lint(ROAMEX)
        self.assertNotEqual(result.returncode, 0,
                            "the reference names a repo nobody has checked out; full validation "
                            "should say so rather than pretend")

    def test_environmental_validation_passes_against_the_fixture_repository(self):
        result = self.lint(PROFILES / "fixture.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_non_resolving_repo_path_fails_full_validation(self):
        base = (PROFILES / "fixture.md").read_text(encoding="utf-8")
        broken = base.replace("repo_path: ./tests/fixtures/issue2pr/fixture-repo",
                              "repo_path: ./no/such/place")
        import tempfile
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(directory, ignore_errors=True))
        path = directory / "no-repo.md"
        path.write_text(broken, encoding="utf-8")
        self.assertNotEqual(self.lint(path).returncode, 0)


class TestManifestReadCompat(unittest.TestCase):
    """The third obligation of the rename, and the one that can be silently dropped."""

    def manifest(self, path):
        return subprocess.run(
            [sys.executable, str(MANIFEST), "read", str(path)],
            capture_output=True, text=True, timeout=60)

    def test_a_new_schema_manifest_reads(self):
        result = self.manifest(MANIFESTS / "new-schema.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["areas_confirmed"], ["ingest", "queue"])

    def test_an_old_schema_manifest_reads_and_normalises(self):
        """A rename plus a version bump satisfies two obligations while making every existing
        manifest unreadable. This is the third."""
        result = self.manifest(MANIFESTS / "old-schema.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["areas_confirmed"], ["ingest", "queue"])
        self.assertNotIn("crates_confirmed", parsed,
                         "the old spelling normalises away, so nothing downstream sees it")

    def test_a_manifest_carrying_both_spellings_is_refused(self):
        """Choosing silently between two disagreeing values is worse than refusing."""
        result = self.manifest(MANIFESTS / "both-spellings.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("both", (result.stdout + result.stderr).lower())


class TestGoldenRuns(unittest.TestCase):
    """The three runs, and the property that keeps them honest.

    These artifacts were produced by a **hand-performed** run — three of them, one per mode, with the
    stub at `tests/fixtures/fake-codex/issue2pr-stub.mjs` supplying verdicts. No process in this
    repository reads a markdown skill and executes it, so nothing here re-runs them; `VIBE_SUITE_CODEX_BIN`
    substitutes the inner codex executable, not the host.

    What CI can do is refuse to let the goldens and the core drift apart. **The expectation is derived
    from the core's own declarations** — its phase ranges and its state schema — rather than written
    beside them. Change the core and these fail; change a golden and these fail. A fixture that merely
    sat next to a description would stay green through either.
    """

    GOLDEN = FIXTURES / "golden"
    MODE_STEPS = {"none": [1, 4, 7], "single": list(range(1, 10)), "full": list(range(1, 10))}

    @classmethod
    def setUpClass(cls):
        cls.core = SKILL.read_text(encoding="utf-8")
        cls.phases = json_block(cls.core, "phases")
        cls.state_shape = json_block(cls.core, "state-schema")
        cls.timeline_shape = json_block(cls.core, "timeline-entry")

    def state(self, mode):
        return json.loads((self.GOLDEN / mode / "state.json").read_text(encoding="utf-8"))

    def timeline(self, mode):
        return json.loads((self.GOLDEN / mode / "timeline.json").read_text(encoding="utf-8"))

    def test_all_three_modes_produced_a_run(self):
        for mode in self.MODE_STEPS:
            with self.subTest(mode=mode):
                self.assertTrue((self.GOLDEN / mode / "state.json").is_file(),
                                f"no golden run for --review-mode {mode}")

    def test_each_golden_state_matches_the_core_s_declared_schema(self):
        """Derived, not restated: the expected key set comes from the core's own block."""
        for mode in self.MODE_STEPS:
            with self.subTest(mode=mode):
                self.assertEqual(set(self.state(mode)), set(self.state_shape),
                                 "the golden state and the core's declared schema have diverged")

    def test_each_timeline_entry_matches_the_core_s_declared_shape(self):
        for mode in self.MODE_STEPS:
            for entry in self.timeline(mode):
                with self.subTest(mode=mode, step=entry.get("step")):
                    self.assertEqual(set(entry), set(self.timeline_shape))

    def test_step_numbering_is_canonical_in_every_mode(self):
        """`none` runs 1, 4, 7 — and they keep those numbers. A mode that renumbered would make two
        runs of the same item incomparable, which is why the core states this rather than implying it.
        """
        for mode, expected in self.MODE_STEPS.items():
            with self.subTest(mode=mode):
                self.assertEqual([e["step"] for e in self.timeline(mode)], expected)

    def test_each_step_is_filed_under_the_phase_the_core_assigns_it(self):
        """The phase of a step is the core's declaration, so a golden cannot invent one."""
        for mode in self.MODE_STEPS:
            for entry in self.timeline(mode):
                with self.subTest(mode=mode, step=entry["step"]):
                    span = self.phases[entry["phase"]]
                    self.assertTrue(span[0] <= entry["step"] <= span[1],
                                    f"step {entry['step']} filed under {entry['phase']}, whose "
                                    f"declared range is {span}")

    def test_none_engages_no_reviewer_and_the_others_do(self):
        """The mode-gated absence, observed in the artifacts rather than asserted about the prose."""
        self.assertFalse((self.GOLDEN / "none" / "reviewer-result.json").exists(),
                         "--review-mode none must not dispatch a reviewer")
        for mode in ("single", "full"):
            with self.subTest(mode=mode):
                self.assertTrue((self.GOLDEN / mode / "reviewer-result.json").is_file(),
                                f"--review-mode {mode} must dispatch a reviewer")
        actors = {e["actor"] for e in self.timeline("none")}
        self.assertEqual(actors, {"worker"}, "no reviewer acts under --review-mode none")

    def test_the_dispatch_really_went_through_the_runner(self):
        """A golden nobody generated is a fixture someone wrote. The runner's own result contract is
        the evidence that this one was produced rather than typed."""
        for mode in ("single", "full"):
            with self.subTest(mode=mode):
                result = json.loads(
                    (self.GOLDEN / mode / "reviewer-result.json").read_text(encoding="utf-8"))
                self.assertEqual(set(result), {"jobId", "status", "threadId", "rawOutput", "verdictState"})
                self.assertEqual(result["status"], "completed")
                self.assertIn("verdict: approve", result["rawOutput"])

    def test_every_driver_call_names_a_declared_operation(self):
        """The goldens exercise the seam, not just the folder layout.

        They were previously hand-written summaries that would have stayed green through the driver
        protocol being deleted. Every call is now checked against the core's own declaration.
        """
        protocol = json_block(self.core, "driver-protocol")
        for mode in self.MODE_STEPS:
            calls = json.loads((self.GOLDEN / mode / "driver-calls.json").read_text(encoding="utf-8"))
            self.assertTrue(calls, f"the {mode} run recorded no source-system calls")
            for call in calls:
                with self.subTest(mode=mode, operation=call["operation"]):
                    self.assertIn(call["operation"], protocol)
                    self.assertEqual(call["out"], protocol[call["operation"]]["out"],
                                     "a golden call disagrees with the declared output shape")

    def test_the_disclosure_matches_the_core_s_mode_mapping(self):
        """Rendered from the mode, and checked against the mapping rather than against itself."""
        mapping = json_block(self.core, "disclosure-by-mode")
        self.assertIsNotNone(mapping, "the core must declare the mode-to-disclosure mapping")
        for mode in self.MODE_STEPS:
            with self.subTest(mode=mode):
                text = (self.GOLDEN / mode / "disclosure.txt").read_text(encoding="utf-8")
                # **Reconstructed, not searched for.** `assertIn` is a substring test: shortening the
                # mapping's `full` value to a prefix of what the golden already said would have left
                # the golden unchanged and still passed, so changing the mapping did not have to fail.
                expected = ("Produced by the nine-step /vibe-suite:issue2pr pipeline %s "
                            "(review-mode `%s`)." % (mapping[mode], mode))
                if mode != "none":
                    expected += " Reviewer: a non-worker model via the codex backend."
                self.assertEqual(text.strip(), expected,
                                 "the golden disclosure must be exactly what the mapping renders")
                if mode == "none":
                    self.assertNotIn("backend", text,
                                     "naming a backend under `none` implies one was dispatched")

    def test_the_state_values_are_checked_not_only_its_keys(self):
        """Key-set equality passed a `completed` run with no change recorded at all."""
        for mode, steps in self.MODE_STEPS.items():
            with self.subTest(mode=mode):
                state = self.state(mode)
                self.assertEqual(state["review_mode"], mode)
                self.assertEqual(state["current_step"], steps[-1])
                self.assertEqual(state["status"], "completed")
                self.assertIsInstance(state["areas_confirmed"], list)
                self.assertIsNotNone(state["pr"],
                                     "every mode reaches step 7, so a completed run has a change")
                self.assertEqual(set(state["pr"]), set(json_block(self.core, "change-ref")))

    def test_every_step_left_an_artifact(self):
        for mode, steps in self.MODE_STEPS.items():
            for step in steps:
                with self.subTest(mode=mode, step=step):
                    result = self.GOLDEN / mode / "phases" / f"step-{step}" / "result.md"
                    self.assertTrue(result.is_file(), f"step {step} left nothing behind")
                    phase = next(n for n, (lo, hi) in self.phases.items() if lo <= step <= hi)
                    self.assertIn(phase, result.read_text(encoding="utf-8"),
                                  "an artifact must name the phase the core assigns its step")

    def test_the_stub_is_reusable_by_the_loop_bounds_issue(self):
        """E5.6 (#45) stresses this loop against a reviewer that never returns clean. It should extend
        this fixture rather than build a second one, so the two agree about the dispatch shape."""
        stub = (REPO_ROOT / "tests" / "fixtures" / "fake-codex" / "issue2pr-stub.mjs")
        self.assertTrue(stub.is_file())
        text = stub.read_text(encoding="utf-8")
        self.assertIn("VIBE_TEST_STUB_VERDICT", text,
                      "the verdict must be selectable, or #45 cannot reuse this")
        self.assertIn("approve_with_revisions", text)


class TestParserIsClosed(LintCase):
    """The grammar rejects rather than guesses. A profile carries commands this pipeline will run."""

    def profile_text(self, text):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        path = directory / "candidate.md"
        path.write_text(text, encoding="utf-8")
        return path

    def base(self):
        return (PROFILES / "fixture.md").read_text(encoding="utf-8")

    def test_a_duplicate_top_level_key_is_refused(self):
        """Last-wins silently discards a value someone wrote deliberately."""
        broken = self.base().replace("base_branch: trunk", "base_branch: trunk\nbase_branch: main")
        result = self.lint(self.profile_text(broken))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr)

    def test_a_duplicate_mapping_member_is_refused(self):
        broken = self.base().replace(
            "gates:", "category_extensions:\n  step-2: a\n  step-2: b\ngates:")
        result = self.lint(self.profile_text(broken))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr)

    def test_an_unbalanced_quote_is_refused(self):
        broken = self.base().replace("id_pattern: '^fx-(\\d+)$'", "id_pattern: '^fx-(\\d+)$")
        result = self.lint(self.profile_text(broken))
        self.assertNotEqual(result.returncode, 0)

    def test_an_unindented_sequence_item_is_refused(self):
        """The grammar says two spaces under the key. The sequence branch did not enforce it, so a
        flush-left `- item` was accepted by a parser that advertises a closed grammar."""
        broken = self.base().replace("gates:\n  - 'make lint'", "gates:\n- 'make lint'")
        result = self.lint(self.profile_text(broken))
        self.assertNotEqual(result.returncode, 0)

    def test_odd_indentation_is_refused(self):
        broken = self.base().replace("gates:\n  - 'make lint'", "gates:\n   - 'make lint'")
        result = self.lint(self.profile_text(broken))
        self.assertNotEqual(result.returncode, 0)

    def test_a_mapping_where_a_regex_belongs_refuses_rather_than_crashes(self):
        broken = self.base().replace("id_pattern: '^fx-(\\d+)$'", "id_pattern:\n  a: b")
        result = self.lint(self.profile_text(broken))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr, "a type error must refuse, not crash")

    def test_an_unknown_backend_domain_is_an_error_not_permission(self):
        """The domain is read from the installed plugin, and an unreadable one fails **closed**.

        The earlier lookup resolved under `--root` — the *target* workspace — which has no
        `skills/vibe-core/SKILL.md` in any consumer repository, so the check silently allowed anything.
        """
        import os
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        (directory / "scripts").mkdir()
        stray = directory / "scripts" / "profile_lint.py"
        stray.write_text(LINT.read_text(encoding="utf-8"), encoding="utf-8")
        broken = self.base().replace("base_branch: trunk",
                                     "base_branch: trunk\nreviewer_backend: codex")
        profile = self.profile_text(broken)
        result = subprocess.run(
            [sys.executable, str(stray), "--root", str(REPO_ROOT), str(profile), "--structural-only"],
            capture_output=True, text=True, timeout=60)
        self.assertNotEqual(result.returncode, 0,
                            "an unreadable domain must fail closed, not allow every value")
        self.assertIn("domain is unknown", result.stderr)


class TestManifestWritePath(unittest.TestCase):
    """The write surface had no tests at all — only reads were exercised.

    A mutation that misrouted the destination or bypassed containment was invisible. Every case below
    is a refusal that must happen *before* anything is written.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)

    def write(self, target, payload, root=None):
        return subprocess.run(
            [sys.executable, str(MANIFEST), "write", str(target), "--root", str(root or self.ws)],
            input=json.dumps(payload), capture_output=True, text=True, timeout=60)

    def test_an_in_root_write_succeeds_and_round_trips(self):
        target = self.ws / "manifest.json"
        result = self.write(target, {"schema_version": 2, "areas_confirmed": ["a"]})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(target.read_text())["areas_confirmed"], ["a"])

    def test_the_legacy_spelling_normalises_on_write_too(self):
        target = self.ws / "legacy.json"
        result = self.write(target, {"schema_version": 1, "crates_confirmed": ["a"]})
        self.assertEqual(result.returncode, 0, result.stderr)
        written = json.loads(target.read_text())
        self.assertEqual(written["areas_confirmed"], ["a"])
        self.assertNotIn("crates_confirmed", written)

    def test_both_spellings_are_refused_on_the_write_path(self):
        result = self.write(self.ws / "both.json",
                            {"crates_confirmed": ["a"], "areas_confirmed": ["b"]})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.ws / "both.json").exists(), "nothing may be written before the refusal")

    def test_a_destination_outside_the_root_is_refused(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        result = self.write(outside / "escape.json", {"areas_confirmed": []})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr, "it must refuse in words, not by traceback")
        self.assertFalse((outside / "escape.json").exists())

    def test_a_parent_traversal_destination_is_refused(self):
        nested = self.ws / "nested"
        nested.mkdir()
        result = self.write(nested / ".." / ".." / "escape.json", {"areas_confirmed": []},
                            root=nested)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)

    def test_malformed_json_on_stdin_is_refused(self):
        result = subprocess.run(
            [sys.executable, str(MANIFEST), "write", str(self.ws / "x.json"), "--root", str(self.ws)],
            input="{not json", capture_output=True, text=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)


class TestRepoPathContainment(LintCase):
    """`repo_path` names a checkout inside the workspace. Existence alone accepted `..` and `/tmp`."""

    def profile_with(self, repo_path):
        base = (PROFILES / "fixture.md").read_text(encoding="utf-8")
        broken = base.replace("repo_path: ./tests/fixtures/issue2pr/fixture-repo",
                              "repo_path: %s" % repo_path)
        assert broken != base
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        path = directory / "candidate.md"
        path.write_text(broken, encoding="utf-8")
        return path

    def test_an_absolute_repo_path_is_refused(self):
        result = self.lint(self.profile_with("/tmp"))
        self.assertNotEqual(result.returncode, 0, "an absolute path is not a workspace checkout")
        self.assertIn("absolute", result.stderr)

    def test_a_parent_traversal_repo_path_is_refused_as_an_escape(self):
        """Refused for the right reason. `..` also happens to fail the looks-like-a-checkout test, so
        asserting only a non-zero exit passed even with the containment check removed."""
        result = self.lint(self.profile_with(".."))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("escapes the workspace root", result.stderr,
                      "traversal must be refused as an escape, not incidentally")

    def test_a_symlink_escape_is_refused(self):
        """The case a lexical check alone would miss."""
        target = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, target, True)
        (target / "README.md").write_text("outside\n", encoding="utf-8")
        link = REPO_ROOT / "tests" / "fixtures" / "issue2pr" / "escape-link"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target)
        self.addCleanup(lambda: link.unlink(missing_ok=True))
        result = self.lint(self.profile_with("./tests/fixtures/issue2pr/escape-link"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("escapes the workspace root", result.stderr)

    def test_a_directory_with_only_a_readme_is_not_a_checkout(self):
        """A README was the earlier evidence of a repository, and most directories have one."""
        holder = REPO_ROOT / "tests" / "fixtures" / "issue2pr" / "readme-only"
        holder.mkdir(exist_ok=True)
        (holder / "README.md").write_text("not a project root\n", encoding="utf-8")
        self.addCleanup(shutil.rmtree, holder, True)
        result = self.lint(self.profile_with("./tests/fixtures/issue2pr/readme-only"))
        self.assertNotEqual(result.returncode, 0, "a README is not evidence of a project root")
        self.assertIn("project root", result.stderr)

    def test_an_existing_directory_that_is_not_a_checkout_is_refused(self):
        result = self.lint(self.profile_with("./scripts/lib"))
        self.assertNotEqual(result.returncode, 0,
                            "an arbitrary existing directory is not a repository")


class TestDriverSeam(unittest.TestCase):
    """The seam #43 extracts. Without it that issue rewrites the pipeline instead."""

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.protocol = json_block(cls.text, "driver-protocol")

    def test_the_protocol_is_declared(self):
        self.assertIsNotNone(self.protocol,
                             "a `source_driver` field with no protocol behind it is a name, not a seam")

    def test_every_operation_declares_its_inputs_outputs_and_errors(self):
        for name, spec in self.protocol.items():
            with self.subTest(operation=name):
                self.assertEqual(set(spec), {"in", "out", "errors"})
                self.assertIsInstance(spec["in"], list)
                self.assertIsInstance(spec["errors"], list)
                self.assertTrue(spec["errors"], f"{name} declares no failure mode")

    def test_the_lifecycle_operations_are_present(self):
        for operation in ("fetch_item", "refresh_item", "open_change", "update_change",
                          "read_change_state", "link_closure"):
            with self.subTest(operation=operation):
                self.assertIn(operation, self.protocol)

    def test_every_declared_output_names_a_shape_the_core_declares(self):
        """An operation returning a shape nothing defines is a seam with a hole in it."""
        for name, spec in self.protocol.items():
            out = spec["out"]
            if out.endswith(("snapshot", "delta")):
                with self.subTest(operation=name):
                    self.assertIsNotNone(json_block(self.text, out),
                                         f"{name} returns {out}, which the core does not declare")

    def test_the_steps_bind_to_operations_rather_than_commands(self):
        low = norm(self.text)
        for operation in ("fetch_item", "open_change", "read_change_state", "update_change"):
            with self.subTest(operation=operation):
                self.assertIn(operation, low)
        self.assertNotIn("gh issue view", low, "a step naming a command has bypassed the seam")
        self.assertNotIn("gh pr create", low)


class TestTerminalState(unittest.TestCase):
    def test_the_pipeline_does_not_merge(self):
        """Merging changes the default branch on the strength of a review the pipeline produced.
        Every other artifact said the machine terminates in a reviewed PR; step 9 said 'then merge'."""
        text = SKILL.read_text(encoding="utf-8")
        self.assertRegex(norm(text), r"does not merge")
        # The real property: no step in the nine-step list performs a merge. Asserting the absence of
        # one phrasing let "and then merges." through while the disclaimer above it stayed put — the
        # document would have contradicted itself and passed.
        steps = text[text.index("## The nine steps"):]
        offenders = [line for line in steps.splitlines()
                     if re.match(r"^\d\.", line.strip()) and "merge" in line.lower()]
        self.assertEqual(offenders, [], f"a step performs a merge: {offenders}")


class TestDisclosureHonesty(unittest.TestCase):
    """A fixed disclosure is false under `none` and an overstatement under `single`."""

    def test_the_disclosure_is_rendered_per_mode(self):
        text = PR_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("{disclosure}", text)
        for mode in ("none", "single", "full"):
            with self.subTest(mode=mode):
                self.assertRegex(text, r"(?m)^\s*%s\s+Produced by" % mode)

    def test_no_fixed_sentence_claims_verified_closure(self):
        body = PR_TEMPLATE.read_text(encoding="utf-8").split("<!--")[0]
        self.assertNotIn("verified finding", body,
                         "the unconditional claim is what made this false in two of three modes")


if __name__ == "__main__":
    unittest.main()
