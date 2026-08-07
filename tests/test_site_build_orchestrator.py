#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""T2b (E8.4 / vibe-61) — `site/build.sh`, the single build entry point.

I2b: local verification, `site-validate`, `site-preview` and `deploy-site` all build through
this one script, because `site/data/` and `site/reports/` are gitignored (D-D) and a clean
checkout contains none of their output. The orchestrator runs the five builders, then
VitePress, and **atomically replaces** the generated directories — so a populated→empty
rebuild leaves no obsolete page behind. That transition is the stale-output assertion; a
build that merely overwrites what it regenerates passes the first two states and fails this
one.

    bash site/build.sh --corpus <dir> --out <dir> [--skip-vitepress]

`--skip-vitepress` is the seam these tests use: the Node toolchain is not a prerequisite for
asserting the orchestrator's own contract (stdlib-only tests, no network).
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD = REPO_ROOT / "site" / "build.sh"
CORPUS = REPO_ROOT / "tests" / "fixtures" / "site" / "corpus"

NOTICE = "no audit data yet"
FIXTURE_REPO = "repo-alpha"

#: The pages the orchestrator always renders, empty corpus or not (I2b).
ALWAYS_RENDERED = ("dashboard.md", "featured-audits.md")

#: The five data files, one per builder (T2's contract).
DATA_FILES = ("reference.json", "vocab.json", "reports.json",
              "case-studies.json", "docs.json")

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")


def run_build(corpus, out):
    return subprocess.run(
        ["bash", str(BUILD), "--corpus", str(corpus), "--out", str(out),
         "--skip-vitepress"],
        capture_output=True, text=True, cwd=str(REPO_ROOT))


class OrchestratorBase(unittest.TestCase):
    def setUp(self):
        self.assertTrue(BUILD.is_file(), f"{BUILD} must exist before this suite runs")
        self.tmp = Path(tempfile.mkdtemp(prefix="site-build-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = self.tmp / "out"
        self.out.mkdir()
        self.empty = self.tmp / "empty-corpus"   # deliberately never created

    def produced(self):
        return sorted(str(p.relative_to(self.out))
                      for p in self.out.rglob("*") if p.is_file())


class Contract(OrchestratorBase):
    def test_isc_header_in_first_three_lines(self):
        head = "\n".join(BUILD.read_text(encoding="utf-8").splitlines()[:3])
        self.assertIn("SPDX-License-Identifier: ISC", head)

    def test_fixture_corpus_is_present(self):
        self.assertTrue((CORPUS / "manifest.json").is_file(), f"{CORPUS} fixture missing")


class CleanCheckoutEmptyCorpus(OrchestratorBase):
    """State 1 — a clean checkout with no audit corpus (D-C): a complete, empty site."""

    def test_exits_zero(self):
        result = run_build(self.empty, self.out)
        self.assertEqual(result.returncode, 0,
                         f"site/build.sh exited {result.returncode} on an empty corpus; "
                         f"stderr={result.stderr!r}")

    def test_produces_the_five_data_files(self):
        run_build(self.empty, self.out)
        for data in DATA_FILES:
            with self.subTest(data=data):
                self.assertTrue((self.out / "data" / data).is_file(),
                                f"orchestrator produced no data/{data}; it produced "
                                f"{self.produced()}")

    def test_renders_the_notice_on_the_always_rendered_pages(self):
        run_build(self.empty, self.out)
        for page in ALWAYS_RENDERED:
            with self.subTest(page=page):
                path = self.out / page
                self.assertTrue(path.is_file(),
                                f"orchestrator rendered no {page}; it produced "
                                f"{self.produced()}")
                self.assertIn(NOTICE, path.read_text(encoding="utf-8").lower(),
                              f"{page} carries no {NOTICE!r} notice, so an empty site "
                              f"reads as broken rather than pre-migration")


class PopulatedCorpus(OrchestratorBase):
    """State 2 — pages generated per fixture repo."""

    def test_exits_zero(self):
        result = run_build(CORPUS, self.out)
        self.assertEqual(result.returncode, 0,
                         f"site/build.sh exited {result.returncode} on the fixture corpus; "
                         f"stderr={result.stderr!r}")

    def test_generates_a_page_per_fixture_repo(self):
        run_build(CORPUS, self.out)
        page = self.out / "reports" / f"{FIXTURE_REPO}.md"
        self.assertTrue(page.is_file(),
                        f"orchestrator generated no reports/{FIXTURE_REPO}.md from the "
                        f"fixture corpus; it produced {self.produced()}")
        self.assertIn(FIXTURE_REPO, page.read_text(encoding="utf-8"))

    def test_drops_the_empty_notice_from_the_dashboard(self):
        run_build(CORPUS, self.out)
        dashboard = self.out / "dashboard.md"
        self.assertTrue(dashboard.is_file(),
                        f"orchestrator rendered no dashboard.md; it produced "
                        f"{self.produced()}")
        self.assertNotIn(NOTICE, dashboard.read_text(encoding="utf-8").lower(),
                         "the dashboard still shows the empty notice with data present")


class StaleOutput(OrchestratorBase):
    """State 3 — populated→empty. The generated dirs are REPLACED, not merged into."""

    def test_second_build_leaves_no_page_from_the_first(self):
        first = run_build(CORPUS, self.out)
        page = self.out / "reports" / f"{FIXTURE_REPO}.md"
        self.assertTrue(page.is_file(),
                        f"precondition: the populated build generated no "
                        f"reports/{FIXTURE_REPO}.md (exit {first.returncode}, "
                        f"stderr={first.stderr!r}), so the stale-output transition cannot "
                        f"be exercised")

        second = run_build(self.empty, self.out)
        self.assertEqual(second.returncode, 0,
                         f"the empty rebuild exited {second.returncode}; "
                         f"stderr={second.stderr!r}")
        self.assertFalse(page.is_file(),
                         f"reports/{FIXTURE_REPO}.md survived a rebuild against an empty "
                         f"corpus — the orchestrator overwrites rather than atomically "
                         f"replacing site/data and site/reports (I2b)")

    def test_second_build_restores_the_empty_notice(self):
        run_build(CORPUS, self.out)
        run_build(self.empty, self.out)
        dashboard = self.out / "dashboard.md"
        self.assertTrue(dashboard.is_file(),
                        f"the empty rebuild rendered no dashboard.md; it produced "
                        f"{self.produced()}")
        self.assertIn(NOTICE, dashboard.read_text(encoding="utf-8").lower(),
                      "after a populated→empty rebuild the dashboard still claims data")


class LinkCheck(OrchestratorBase):
    """A local link check over the built output — every relative target must resolve."""

    def test_built_output_has_no_broken_relative_links(self):
        run_build(CORPUS, self.out)
        pages = [p for p in self.out.rglob("*.md")]
        self.assertTrue(pages,
                        f"the populated build rendered no markdown pages, so the link "
                        f"check has nothing to verify; it produced {self.produced()}")

        broken = []
        for page in pages:
            for target in LINK.findall(page.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "mailto:", "#", "//")):
                    continue
                base = target.split("#", 1)[0].split("?", 1)[0]
                if not base:
                    continue
                root = self.out if base.startswith("/") else page.parent
                resolved = (root / base.lstrip("/")).resolve()
                candidates = (resolved, resolved.with_suffix(".md"),
                              resolved / "index.md", resolved.with_suffix(".html"))
                if not any(c.exists() for c in candidates):
                    broken.append(f"{page.relative_to(self.out)} -> {target}")
        self.assertEqual(broken, [], f"broken relative links in the built output: {broken}")


if __name__ == "__main__":
    unittest.main()
