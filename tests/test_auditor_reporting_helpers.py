# SPDX-License-Identifier: ISC
"""Behavioural tests for the E8.3 reporting helpers and their resources.

Covers the daily report, the dashboard renderer, the per-repository renderer, and the
templates/assets/docs contract those renderers consume. The mutation contract and the shared
primitives are in `auditor_helpers_support`.
"""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditor_helpers_support import NOOP, REPO, SCRIPTS  # noqa: E402


class Test_generate_daily_report(unittest.TestCase):
    """`generate-daily-report.py` — the status page, and the two rates on it."""

    HELPER = SCRIPTS / "generate-daily-report.py"
    ACCEPT_ANCHOR = 'ACCEPTED = ("merged", "applied_separately")'
    ACCEPT_MUTANT = 'ACCEPTED = ("merged",)'
    DATE = "2026-08-07"

    def _run(self, script_text=None, outcomes=None, empty=False):
        d = Path(tempfile.mkdtemp())
        if not empty:
            (d / "report-cache").mkdir()
            (d / "report-cache" / "registry-stats.json").write_text(
                json.dumps({"total": 9, "by_status": {"discovered": 4, "audited": 3,
                                                        "contributed": 2}}), encoding="utf-8")
            (d / "report-cache" / "pr-outcomes.json").write_text(
                json.dumps(outcomes if outcomes is not None else
                           {"merged": 3, "applied_separately": 2, "rejected": 5, "open": 7}),
                encoding="utf-8")
            (d / "report-cache" / "rule-health.json").write_text(
                json.dumps({"R01": {"findings": 10, "accepted": 4}}), encoding="utf-8")
            (d / "report-cache" / "recent-activity.json").write_text(
                json.dumps(["audited acme/widget"]), encoding="utf-8")
        helper = Path(tempfile.mkdtemp()) / "helper.py"
        helper.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
        r = subprocess.run([sys.executable, str(helper), "--data-dir", str(d),
                            "--date", self.DATE], capture_output=True, text=True)
        report = d / "reports" / f"{self.DATE}.md"
        return r, (report.read_text() if report.exists() else "")

    # --- oracle -------------------------------------------------------------------------
    def test_acceptance_counts_applied_separately_not_only_merges(self):
        """A maintainer who applies the fix themselves and closes the PR HAS accepted the
        finding. Counting only merges undercounts the pipeline and pushes readers to optimise
        for merges rather than for fixes."""
        _, text = self._run()
        self.assertIn("| **acceptance rate** (merged + applied separately) | **50%** |", text,
                      "3 merged + 2 applied of 10 resolved is 50%")
        self.assertIn("| merge-only rate | 30% |", text, "3 merged of 10 resolved is 30%")

    def test_open_prs_are_not_counted_as_resolved(self):
        """Dividing by open PRs makes the rate drift downward as new PRs appear, which says
        nothing about whether findings are accepted."""
        _, text = self._run()
        self.assertIn("| resolved | 10 |", text, "open PRs leaked into the denominator")

    def test_stage_counts_are_exact(self):
        _, text = self._run()
        for stage, count in (("discovered", 4), ("audited", 3), ("contributed", 2),
                             ("tracked", 0), ("complete", 0)):
            self.assertIn(f"| {stage} | {count} |", text, f"{stage} count wrong")
        self.assertIn("| **total** | **9** |", text)

    def test_missing_inputs_still_render(self):
        """A missing section is information; it is not a reason to fail the run."""
        r, text = self._run(empty=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("N/A", text)
        self.assertIn("_No notable events._", text)

    def test_no_resolved_prs_gives_na_not_a_division_error(self):
        r, text = self._run(outcomes={"open": 4})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("**N/A**", text)

    def test_the_same_date_and_inputs_render_identically(self):
        _, first = self._run()
        _, second = self._run()
        self.assertEqual(first, second)


    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        _, text = self._run(NOOP[".py"])
        self.assertEqual(text, "", "sanity: a no-op writes no report")

    def test_the_merges_only_mutant_understates_acceptance(self):
        """The plausible wrong implementation: acceptance = merged / resolved.

        It produces a perfectly well-formed report with a plausible percentage — nothing looks
        wrong — while systematically understating the pipeline's effect.
        """
        src = self.HELPER.read_text()
        self.assertIn(self.ACCEPT_ANCHOR, src, "mutation anchor missing")
        _, text = self._run(src.replace(self.ACCEPT_ANCHOR, self.ACCEPT_MUTANT, 1))
        # RESOLVED is derived from ACCEPTED, so this mutation shrinks the DENOMINATOR too:
        # 3 merged of (3 merged + 5 rejected) = 38%, not 3 of 10. Asserting "not 50%" states
        # the property — acceptance is understated — without depending on that coupling.
        self.assertNotIn("| **acceptance rate** (merged + applied separately) | **50%** |", text,
                         "mutation ineffective: the mutant still reports the true rate")
        self.assertIn("| **acceptance rate** (merged + applied separately) | **38%** |", text,
                      "the mutant should understate acceptance")



class Test_report_resources(unittest.TestCase):
    """I4.1 — the report templates and assets the renderers consume.

    These are RESOURCES rather than helpers, so they have no no-op mutant. What they need is a
    contract test: the placeholder set each template carries must be exactly what its renderer
    substitutes, because a template with a stale set substitutes nothing and renders literal
    braces on the published page.

    TWO TEMPLATE FAMILIES WITH DIFFERENT OWNERS, and the table below is the record of which is
    which. `single.html` belongs to `bin/vibe-report` — a self-contained corpus report that
    inlines its own bundle, covered by `tests/test_report.py`. The auditor's pages
    (`dashboard.html`, `repo-audit.html`, `docs/index.html`) are a linked set sharing one
    `assets/`, `vendor/` and `docs/`. Reading `single.html` as the auditor's per-repo template
    is a live mistake — its name invites it and the two really do render the same subject — so
    the ownership is asserted here rather than left to be inferred.
    """

    TEMPLATES = REPO / "templates" / "report"
    #: template -> the placeholders ITS OWN renderer supplies. Anything else is drift.
    CONTRACT = {
        # owned by bin/vibe-report, not by the auditor
        "single.html": {"G6_BUNDLE", "RENDER_JS", "DATA_JSON", "VOCAB_GRAPH_JSON",
                        "SCORE_SECTION", "CHECK_SECTION", "VOCAB_SECTION", "GRAPH_SECTION",
                        "HISTORY_SECTION", "DRIFT_SECTION"},
        # the auditor's linked set
        "dashboard.html": {"GENERATED_AT", "DATA_JSON"},
        "repo-audit.html": {"PROJECT", "GENERATED_AT", "DATA_JSON"},
        "docs/index.html": {"GENERATED_AT", "PRINCIPLES", "RULES", "SCORING", "VOCAB",
                            "ARTIFACT_TYPES", "DRIFT", "WARRANT"},
    }
    #: The auditor's own pages — the ones that share assets and must stay offline-clean.
    AUDITOR_PAGES = ("dashboard.html", "repo-audit.html", "docs/index.html")
    ASSETS = ("vibe-report.css", "vibe-report.js", "vibe-dashboard.css",
              "vibe-dashboard.js", "vibe-docs.css")

    @staticmethod
    def _placeholders(text):
        return set(re.findall(r"\{\{([A-Z_0-9]+)\}\}", text))

    def test_each_template_carries_exactly_its_renderers_placeholders(self):
        for name, expected in self.CONTRACT.items():
            with self.subTest(template=name):
                path = self.TEMPLATES / name
                self.assertTrue(path.is_file(), f"{name} missing")
                found = self._placeholders(path.read_text(encoding="utf-8"))
                self.assertEqual(found, expected,
                                 f"{name} placeholder set drifted from the renderer contract")

    def test_every_referenced_asset_exists(self):
        """A missing stylesheet renders an unstyled page rather than an error, so the reference
        is checked here instead of being noticed by eye."""
        for name in self.CONTRACT:
            path = self.TEMPLATES / name
            for ref in re.findall(r'(?:href|src)="([^"]+)"', path.read_text(encoding="utf-8")):
                if ref.startswith(("http:", "https:", "#")):
                    continue
                with self.subTest(template=name, asset=ref):
                    self.assertTrue((path.parent / ref).resolve().is_file(),
                                    f"{name} references missing {ref}")

    def test_assets_carry_an_spdx_header(self):
        for name in self.ASSETS:
            with self.subTest(asset=name):
                head = (self.TEMPLATES / "assets" / name).read_text(encoding="utf-8")[:200]
                self.assertIn("SPDX-License-Identifier: ISC", head)

    def test_no_external_hosts_are_referenced(self):
        """These pages are opened offline and from artifact downloads. A CDN reference renders
        a blank panel with no indication why, so the graph bundle is vendored instead."""
        for name in self.AUDITOR_PAGES:
            text = (self.TEMPLATES / name).read_text(encoding="utf-8")
            for ref in re.findall(r'(?:href|src)="(https?://[^"]+)"', text):
                self.fail(f"{name} references an external host: {ref}")


class Test_render_dashboard(unittest.TestCase):
    """`render-dashboard.py` — the cross-repository aggregate page."""

    HELPER = SCRIPTS / "render-dashboard.py"
    PAIR_ANCHOR = '    return records, malformed'
    PAIR_MUTANT = '    return records, 0'
    STAMP = "2026-08-07T00:00:00Z"

    def _data_dir(self, malformed=False):
        d = Path(tempfile.mkdtemp())
        (d / "ledgers").mkdir()
        (d / "registry").mkdir()
        (d / "registry" / "repos.json").write_text(json.dumps({"repos": {
            "acme/old": {"status": "audited", "score": 71, "security": "BLOCKED"},
            "acme/new": {"status": "audited", "score": 88, "security": "OK"},
        }}), encoding="utf-8")
        findings = [
            {"repo": "acme/old", "rule_id": "R01", "confidence": "high",
              "timestamp": "2026-01-01T00:00:00Z"},
            {"repo": "acme/old", "rule_id": "R02", "confidence": "medium",
              "timestamp": "2026-01-01T00:00:00Z"},
            {"repo": "acme/new", "rule_id": "R01", "confidence": "high",
              "timestamp": "2026-06-01T00:00:00Z"},
        ]
        lines = [json.dumps(f) for f in findings]
        if malformed:
            lines.insert(1, '{"repo": "acme/old", TRUNCATED')
        (d / "ledgers" / "findings.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (d / "ledgers" / "vocab-advisories.jsonl").write_text("\n".join(json.dumps(a) for a in [
            {"repo": "acme/old", "terms": ["agent", "subagent"], "confidence": "high",
              "timestamp": "2026-01-01T00:00:00Z"},
            {"repo": "acme/new", "terms": ["agent", "subagent"], "confidence": "low",
              "timestamp": "2026-06-01T00:00:00Z"},
        ]) + "\n", encoding="utf-8")
        (d / "ledgers" / "events.jsonl").write_text(json.dumps(
            {"timestamp": "2026-06-01T09:00:00Z", "event": "audited"}) + "\n", encoding="utf-8")
        return d

    def _run(self, d, script_text=None, extra=()):
        helper = self.HELPER
        if script_text is not None:
            # The helper locates its templates as `parents[2]` of its own path, so a mutant
            # dropped in a bare temp directory refuses for want of a template no matter what
            # was mutated — every mutant would "fail" identically and the comparison would
            # prove nothing. Mirror the real layout and link the resources it reads.
            root = Path(tempfile.mkdtemp())
            (root / "auditor" / "scripts").mkdir(parents=True)
            for name in ("templates", "skills"):
                (root / name).symlink_to(REPO / name)
            helper = root / "auditor" / "scripts" / "render-dashboard.py"
            helper.write_text(script_text, encoding="utf-8")
        r = subprocess.run([sys.executable, str(helper), "--data-dir", str(d),
                            "--generated-at", self.STAMP, *extra],
                           capture_output=True, text=True)
        sidecar = d / "reports" / "dashboard.json"
        return r, (json.loads(sidecar.read_text()) if sidecar.exists() else None)

    # --- oracle ---------------------------------------------------------------------------
    def test_aggregate_counts_are_exact(self):
        r, data = self._run(self._data_dir())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(data["summary"]["total_findings"], 3)
        self.assertEqual(data["summary"]["high_findings"], 2)
        self.assertEqual(data["summary"]["repos_blocked"], 1)
        self.assertEqual(data["summary"]["repos_with_drift"], 2)
        rules = {row["rule_id"]: row for row in data["rule_distribution"]}
        self.assertEqual(rules["R01"]["total"], 2)
        self.assertEqual(rules["R01"]["repos_affected"], 2,
                         "repos_affected must count distinct repos, not findings")

    def test_since_filters_records_and_says_how_many(self):
        """The two reasons a record is absent are reported separately: a --since drop is the
        operator's own request, a malformed line is data loss."""
        d = self._data_dir()
        _, data = self._run(d, extra=("--since", "2026-03-01"))
        self.assertEqual(data["summary"]["total_findings"], 1, "--since was ignored")
        self.assertEqual(data["input_health"]["filtered_by_since"]["findings"], 2)
        self.assertEqual(data["input_health"]["malformed_lines"]["findings"], 0)

    def test_malformed_lines_reach_the_sidecar(self):
        """A truncated append makes the dashboard under-report. Without this the smaller number
        is rendered with exactly the same confident styling as a correct one."""
        _, data = self._run(self._data_dir(malformed=True))
        self.assertEqual(data["input_health"]["malformed_lines"]["findings"], 1)
        self.assertEqual(data["summary"]["total_findings"], 3, "valid lines must still parse")

    def test_malformed_telemetry_survives_since_filtering(self):
        """The regression the pair return exists to prevent: an attribute-carried count is
        erased by the first list comprehension, i.e. exactly when --since is in play."""
        d = self._data_dir(malformed=True)
        _, data = self._run(d, extra=("--since", "2026-03-01"))
        self.assertEqual(data["input_health"]["malformed_lines"]["findings"], 1,
                         "the malformed count was lost while filtering")

    def test_html_assets_vendor_and_docs_are_all_written(self):
        d = self._data_dir()
        self._run(d)
        out = d / "reports"
        for rel in ("dashboard.html", "dashboard.json", "docs/index.html",
                    "vendor/g6.min.js", "assets/vibe-dashboard.css", "assets/vibe-dashboard.js",
                    "assets/vibe-report.css", "assets/vibe-report.js", "assets/vibe-docs.css"):
            with self.subTest(path=rel):
                self.assertTrue((out / rel).is_file(), f"{rel} not written")

    def test_no_placeholder_survives_in_any_rendered_page(self):
        """A leftover placeholder renders as literal braces on the published page."""
        d = self._data_dir()
        self._run(d)
        for rel in ("dashboard.html", "docs/index.html"):
            text = (d / "reports" / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                self.assertEqual(re.findall(r"\{\{[A-Z_0-9]+\}\}", text), [])

    def test_every_docs_section_resolves_to_real_content(self):
        """Section headings are matched by name. A retitled heading would blank a section on the
        published page and nothing else would fail, so it is asserted here."""
        d = self._data_dir()
        self._run(d)
        text = (d / "reports" / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("Not available in this build.", text,
                         "a docs section resolved empty — a source heading was probably renamed")

    def test_the_inline_payload_cannot_close_the_script_block(self):
        d = self._data_dir()
        (d / "ledgers" / "findings.jsonl").write_text(json.dumps(
            {"repo": "acme/</script><script>x", "rule_id": "R01"}) + "\n", encoding="utf-8")
        self._run(d)
        html = (d / "reports" / "dashboard.html").read_text(encoding="utf-8")
        self.assertNotIn("</script><script>x", html)
        self.assertIn("<\\/script>", html)

    def test_output_is_reproducible_for_the_same_input(self):
        d = self._data_dir()
        self._run(d)
        first = (d / "reports" / "dashboard.json").read_text()
        self._run(d)
        self.assertEqual(first, (d / "reports" / "dashboard.json").read_text())

    def test_rankings_do_not_depend_on_input_order(self):
        """Counter.most_common breaks ties by insertion order, so reordering the ledger would
        reshuffle equal-count rules and make two runs over identical data differ."""
        d = self._data_dir()
        self._run(d)
        forward = json.loads((d / "reports" / "dashboard.json").read_text())
        lines = (d / "ledgers" / "findings.jsonl").read_text().strip().splitlines()
        (d / "ledgers" / "findings.jsonl").write_text("\n".join(reversed(lines)) + "\n", encoding="utf-8")
        self._run(d)
        reversed_run = json.loads((d / "reports" / "dashboard.json").read_text())
        self.assertEqual(forward["rule_distribution"], reversed_run["rule_distribution"])
        self.assertEqual(forward["drift_network"], reversed_run["drift_network"])

    def test_a_missing_data_dir_is_refused(self):
        r = subprocess.run([sys.executable, str(self.HELPER), "--data-dir", "/nonexistent"],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:render-dashboard:data-dir-missing", r.stderr)

    def test_an_empty_data_dir_still_renders(self):
        """A freshly provisioned auditor has no findings yet; that is a state, not a failure."""
        d = Path(tempfile.mkdtemp())
        r, data = self._run(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(data["summary"]["total_findings"], 0)
        self.assertTrue((d / "reports" / "dashboard.html").is_file())

    def test_the_renderer_does_not_shell_out_to_the_docs_builder(self):
        """bin/vibe-build-docs requires --corpus and emits VitePress Markdown; invoking it here
        yields docs/index.md where every rule badge links to docs/index.html.

        Asserted as "spawns no child process at all" rather than as a search for the builder's
        name: the name appears in this helper's own docstring explaining why it is NOT used, so
        a substring check would fail on the explanation rather than on the behaviour.
        """
        tree = ast.parse(self.HELPER.read_text(encoding="utf-8"))
        imported = {alias.name.split(".")[0]
                    for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names}
        imported |= {node.module.split(".")[0]
                     for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.module}
        self.assertNotIn("subprocess", imported, "the renderer must not shell out")

    def test_enveloped_and_flat_ledger_rows_both_aggregate(self):
        """SCHEMAS.md section 2 documents a FLAT finding record; auditor-audit.yml appends
        through its `envelope` helper, so what is on disk is enveloped. Reading only one shape
        drops every row of the other — and dropped rows aggregate to zero of everything, which
        renders as a complete, confident dashboard rather than an error.
        """
        d = self._data_dir()
        flat = {"repo": "acme/old", "rule_id": "R09", "confidence": "high",
                "timestamp": "2026-01-01T00:00:00Z"}
        enveloped = {"timestamp": "2026-01-02T00:00:00Z", "workflow": "auditor-audit",
                     "event": "finding", "run_id": "1", "run_number": 1,
                     "data": {"repo": "acme/new", "rule_id": "R10", "confidence": "high"}}
        (d / "ledgers" / "findings.jsonl").write_text(
            json.dumps(flat) + "\n" + json.dumps(enveloped) + "\n", encoding="utf-8")
        _, data = self._run(d)
        rules = {row["rule_id"] for row in data["rule_distribution"]}
        self.assertIn("R09", rules, "the flat row was dropped")
        self.assertIn("R10", rules, "the enveloped row was dropped")
        self.assertEqual(data["summary"]["total_findings"], 2)

    def test_an_unwrapped_row_keeps_its_own_fields(self):
        """Envelope context fills gaps; it must never shadow a payload field of the same name."""
        d = self._data_dir()
        (d / "ledgers" / "findings.jsonl").write_text(json.dumps({
            "timestamp": "2026-01-02T00:00:00Z", "event": "finding", "run_id": "1",
            "data": {"repo": "acme/new", "rule_id": "R11", "confidence": "high",
                     "timestamp": "2025-12-31T00:00:00Z"}}) + "\n", encoding="utf-8")
        _, data = self._run(d, extra=("--since", "2026-01-01"))
        self.assertEqual(data["summary"]["total_findings"], 0,
                         "the payload's own timestamp must win over the envelope's")

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        _, data = self._run(self._data_dir(), NOOP[".py"])
        self.assertIsNone(data, "sanity: a no-op writes no sidecar")

    def test_the_dropped_telemetry_mutant_under_reports_silently(self):
        """The plausible wrong implementation: parse malformed lines away and report zero.

        Everything still renders, every number still looks right, and the page gives no
        indication that a line was dropped — which is the whole reason the count exists.
        """
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.PAIR_ANCHOR, src, "mutation anchor missing")
        r, data = self._run(self._data_dir(malformed=True),
                            src.replace(self.PAIR_ANCHOR, self.PAIR_MUTANT, 1))
        self.assertEqual(r.returncode, 0, "the mutant renders cleanly — that is the danger")
        self.assertEqual(data["input_health"]["malformed_lines"]["findings"], 0,
                         "mutation ineffective: the mutant should report no malformed lines")



class Test_render_repo_report(unittest.TestCase):
    """`render-repo-report.py` — one repository's page, and the identifier it is keyed on."""

    HELPER = SCRIPTS / "render-repo-report.py"
    FILTER_ANCHOR = '    findings = [f for f in all_findings if f.get("repo") == args.repo]'
    FILTER_MUTANT = '    findings = list(all_findings)'
    STAMP = "2026-08-07T00:00:00Z"

    def _data_dir(self, repos=None):
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        (d / "ledgers").mkdir(exist_ok=True)
        (d / "registry" / "repos.json").write_text(json.dumps({"repos": repos if repos is not None
            else {"acme/widget": {"status": "audited", "score": 71, "security": "OK"},
                  "acme/other": {"status": "audited", "score": 90, "security": "OK"}}}),
            encoding="utf-8")
        (d / "ledgers" / "findings.jsonl").write_text("\n".join(json.dumps(f) for f in [
            {"repo": "acme/widget", "rule_id": "R01", "confidence": "high",
             "file": "b.md", "line": 3},
            {"repo": "acme/widget", "rule_id": "R02", "confidence": "medium",
             "file": "a.md", "line": 9},
            {"repo": "acme/other", "rule_id": "R01", "confidence": "high",
             "file": "z.md", "line": 1},
        ]) + "\n", encoding="utf-8")
        (d / "ledgers" / "vocab-advisories.jsonl").write_text(json.dumps(
            {"repo": "acme/widget", "terms": ["agent", "subagent"], "confidence": "high"}
        ) + "\n", encoding="utf-8")
        return d

    def _run(self, d, repo="acme/widget", script_text=None, extra=()):
        helper = self.HELPER
        if script_text is not None:
            # parents[1] of the helper locates templates/, and the sibling dashboard helper is
            # imported by name. A mutant in a bare temp directory would refuse for want of
            # those regardless of the mutation, making every mutant fail identically.
            root = Path(tempfile.mkdtemp())
            (root / "auditor" / "scripts").mkdir(parents=True)
            for name in ("templates", "skills"):
                (root / name).symlink_to(REPO / name)
            (root / "auditor" / "scripts" / "render-dashboard.py").symlink_to(
                SCRIPTS / "render-dashboard.py")
            helper = root / "auditor" / "scripts" / "render-repo-report.py"
            helper.write_text(script_text, encoding="utf-8")
        argv = [sys.executable, str(helper), "--data-dir", str(d), "--generated-at", self.STAMP]
        if repo is not None:
            argv += ["--repo", repo]
        r = subprocess.run(argv + list(extra), capture_output=True, text=True)
        sidecar = d / "reports" / "acme-widget.json"
        return r, (json.loads(sidecar.read_text()) if sidecar.exists() else None)

    # --- oracle ---------------------------------------------------------------------------
    def test_only_the_named_repositorys_records_appear(self):
        r, data = self._run(self._data_dir())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(data["project"], "acme/widget")
        self.assertEqual(data["summary"]["total_findings"], 2)
        self.assertEqual({f["repo"] for f in data["findings"]}, {"acme/widget"})
        self.assertEqual(data["summary"]["total_advisories"], 1)

    def test_registry_facts_are_carried_onto_the_page(self):
        _, data = self._run(self._data_dir())
        self.assertEqual(data["registry"]["score"], 71)
        self.assertEqual(data["registry"]["status"], "audited")

    def test_the_page_and_its_shared_resources_are_written(self):
        d = self._data_dir()
        self._run(d)
        for rel in ("acme-widget.html", "acme-widget.json", "docs/index.html",
                    "assets/vibe-report.css", "assets/vibe-report.js", "vendor/g6.min.js"):
            with self.subTest(path=rel):
                self.assertTrue((d / "reports" / rel).is_file(), f"{rel} not written")

    def test_the_docs_link_on_the_page_resolves(self):
        """Every rule badge links into docs/index.html. Rendering a repo report alone -- a
        single-repo re-audit -- must not leave that link dangling."""
        d = self._data_dir()
        self._run(d)
        html = (d / "reports" / "acme-widget.html").read_text(encoding="utf-8")
        self.assertIn('href="docs/index.html"', html)
        self.assertTrue((d / "reports" / "docs" / "index.html").is_file())

    def test_no_placeholder_survives(self):
        d = self._data_dir()
        self._run(d)
        html = (d / "reports" / "acme-widget.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"\{\{[A-Z_0-9]+\}\}", html), [])
        self.assertIn("acme/widget", html)

    def test_it_uses_its_own_template_not_bin_vibe_reports(self):
        """single.html belongs to bin/vibe-report and inlines its own bundle. Rendering this
        page from it would substitute nothing -- the placeholder sets do not overlap."""
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn("repo-audit.html", src)
        self.assertNotIn('"single.html"', src)

    def test_output_is_reproducible(self):
        d = self._data_dir()
        self._run(d)
        first = (d / "reports" / "acme-widget.json").read_text()
        self._run(d)
        self.assertEqual(first, (d / "reports" / "acme-widget.json").read_text())


    def test_rendering_leaves_no_bytecode_beside_the_helpers(self):
        """auditor/scripts/ is a closed, asserted inventory of thirty names. Importing the
        sibling dashboard helper writes a __pycache__ there unless suppressed, which fails the
        inventory check on any machine that has run this helper once -- and puts writable state
        in a checkout the auditor commits from."""
        before = {p.name for p in SCRIPTS.iterdir()}
        self._run(self._data_dir())
        self.assertEqual({p.name for p in SCRIPTS.iterdir()} - before, set())

    # --- refusals -------------------------------------------------------------------------
    def test_a_missing_registry_is_refused(self):
        d = self._data_dir()
        (d / "registry" / "repos.json").unlink()
        r, _ = self._run(d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:render-repo-report:registry-missing", r.stderr)

    def test_a_slug_passed_as_the_repo_is_refused(self):
        """The specification's rule: $TARGET_REPO, never $SLUG. A slug cannot be reversed, so
        accepting one would publish some other repository's audit under a plausible title."""
        r, _ = self._run(self._data_dir(), repo="acme-widget")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("repo-not-owner-name", r.stderr)

    def test_a_repo_absent_from_the_registry_is_refused(self):
        r, _ = self._run(self._data_dir(), repo="ghost/repo")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("repo-not-in-registry", r.stderr)

    def test_a_slug_collision_is_refused_rather_than_overwritten(self):
        """`a/b-c` and `a-b/c` both slug to `a-b-c`. Whichever renders second would silently
        overwrite the first, publishing one repository's audit under another's name -- and the
        file would exist, parse, and read plausibly."""
        d = self._data_dir(repos={"acme/w-x": {"status": "audited"},
                                  "acme-w/x": {"status": "audited"}})
        r, _ = self._run(d, repo="acme/w-x")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:render-repo-report:slug-collision", r.stderr)

    def test_a_missing_repo_argument_is_refused(self):
        r, _ = self._run(self._data_dir(), repo=None)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("repo-required", r.stderr)

    def test_a_repo_with_no_findings_still_renders(self):
        """A clean repository is a result, not an error."""
        d = self._data_dir()
        (d / "ledgers" / "findings.jsonl").write_text("", encoding="utf-8")
        (d / "ledgers" / "vocab-advisories.jsonl").write_text("", encoding="utf-8")
        r, data = self._run(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(data["summary"]["total_findings"], 0)
        self.assertTrue((d / "reports" / "acme-widget.html").is_file())

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        _, data = self._run(self._data_dir(), script_text=NOOP[".py"])
        self.assertIsNone(data, "sanity: a no-op writes no report")

    def test_the_unfiltered_mutant_publishes_other_repositories_findings(self):
        """The plausible wrong implementation: render every finding in the corpus.

        The page renders, the title is right, the counts look reasonable, and the report
        attributes other repositories' findings to this one -- which is exactly the kind of
        error that reaches a maintainer as a wrong claim about their code.
        """
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.FILTER_ANCHOR, src, "mutation anchor missing")
        r, data = self._run(self._data_dir(),
                            script_text=src.replace(self.FILTER_ANCHOR, self.FILTER_MUTANT, 1))
        self.assertEqual(r.returncode, 0, "the mutant renders cleanly -- that is the danger")
        self.assertEqual(data["summary"]["total_findings"], 3,
                         "mutation ineffective: the mutant should leak all three findings")



class Test_renderer_workflow_composition(unittest.TestCase):
    """I4.4 — the invocation in auditor-audit.yml, extracted and actually run.

    Every other test here calls the helper the way the TEST thinks the workflow calls it. That
    proves the helper and proves nothing about the workflow: the previous invocation passed
    `$SLUG` positionally to a helper that takes `--repo`, and no test noticed because no test
    ran the workflow's own command line. This extracts the real `run:` block and executes it.
    """

    WORKFLOW = REPO / "auditor" / "workflows" / "auditor-audit.yml"

    def _render_block(self):
        text = self.WORKFLOW.read_text(encoding="utf-8")
        marker = "render-repo-report.py"
        self.assertIn(marker, text, "the renderer invocation vanished from the workflow")
        start = text.rindex("      - run: |", 0, text.index(marker))
        end = text.index("\n      - ", start + 20)
        block = text[start:end]
        body = "\n".join(ln[10:] if ln.startswith(" " * 10) else ln
                         for ln in block.splitlines()[1:])
        return body

    def _render_code(self):
        """The block with comments stripped.

        Asserted against code rather than raw text: this step's comments explain the warn-only
        swallow that was REMOVED and name the SLUG that must not be passed, so a substring
        search over the whole block matches the explanation and fails on the documentation.
        """
        return "\n".join(ln for ln in self._render_block().splitlines()
                          if not ln.lstrip().startswith("#"))

    def test_the_workflows_own_command_line_renders_a_report(self):
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        (d / "ledgers").mkdir(exist_ok=True)
        (d / "registry" / "repos.json").write_text(
            json.dumps({"repos": {"acme/widget": {"status": "audited", "score": 71}}}),
            encoding="utf-8")
        (d / "ledgers" / "findings.jsonl").write_text(json.dumps(
            {"repo": "acme/widget", "rule_id": "R01", "confidence": "high",
             "file": "a.md", "line": 1}) + "\n", encoding="utf-8")
        env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp"),
               "CODE_DIR": str(REPO), "DATA_DIR": str(d), "TARGET_REPO": "acme/widget"}
        r = subprocess.run(["bash", "-c", self._render_block()],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((d / "reports" / "acme-widget.html").is_file(),
                        "the workflow's own invocation produced no report")

    def test_the_render_step_is_fail_closed(self):
        """It was `|| echo "report render failed (warn-only)"`. An audit could be published,
        committed and announced while its report silently never rendered."""
        block = self._render_code()
        self.assertNotIn("warn-only", block)
        self.assertNotIn("||", block, "the render failure must propagate")

    def test_the_step_passes_owner_name_not_the_slug(self):
        block = self._render_code()
        self.assertIn('--repo "$TARGET_REPO"', block)
        self.assertNotIn("$SLUG", block, "the slug is lossy and cannot be reversed")

    def test_a_render_failure_fails_the_step(self):
        """The property the removed `|| echo` destroyed: a broken render stops the run."""
        d = Path(tempfile.mkdtemp())
        env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp"),
               "CODE_DIR": str(REPO), "DATA_DIR": str(d), "TARGET_REPO": "acme/widget"}
        r = subprocess.run(["bash", "-c", self._render_block()],
                           capture_output=True, text=True, env=env)
        self.assertNotEqual(r.returncode, 0, "a missing registry must fail the step")
        self.assertIn("REFUSE:render-repo-report:", r.stderr)

    def test_rule_id_drift_blocks_before_any_mutation(self):
        """E8.6 (vibe-63) SUPERSEDES the warn-only regression that lived here.

        The old reading — drift as telemetry, not a defect — let an audit keyed on rule ids
        the rulebook does not carry publish anyway; E8.6's acceptance says the validator
        BLOCKS a seeded drift. Position matters as much as failure: the old call site ran
        after stage-logic:audit had appended ledgers, updated the registry and transitioned
        labels, so a refusal fired only after externally visible success. The validation now
        precedes the aggregation step, and a failed step stops the job before any of those
        mutations run (Actions never executes subsequent steps of a failed job).
        """
        text = self.WORKFLOW.read_text(encoding="utf-8")
        call = text.index("validate-rule-ids.py")
        self.assertLess(call, text.index("# stage-logic:audit"),
                        "the validation runs after the aggregation step — a drift refusal "
                        "would fire only after ledgers, registry and labels have changed")
        self.assertNotIn("warn-only", text[call:call + 200],
                         "the drift check still swallows its failure")
        drift = Path(tempfile.mkdtemp()) / "acme-widget.findings.jsonl"
        drift.write_text(json.dumps({"rule_id": "R99-NOT-A-RULE", "file": "a.md"}) + "\n",
                         encoding="utf-8")
        r = subprocess.run(["python3", str(SCRIPTS / "validate-rule-ids.py"), str(drift)],
                           capture_output=True, text=True)
        self.assertNotEqual(0, r.returncode, "a seeded rule-id drift did not block")
        self.assertIn("drift", (r.stdout + r.stderr).lower())


if __name__ == "__main__":
    unittest.main()
