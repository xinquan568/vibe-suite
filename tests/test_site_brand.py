#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""T1 (E8.4 / vibe-61) — `tools/site-brand-check.sh`, the rendered-surface brand gate.

Design decision D-A: `tools/legacy-string-sweep.sh` catches the retired *namespaces* over the
*tracked* tree, which leaves two gaps AC-6 structurally cannot see — a bare brand word (no
namespace colon) and generated output (never tracked). This check closes both, as a SEPARATE
tool: it takes a **directory argument**, recurses, is case-insensitive, and applies **no
exception to anything that renders**. A fenced code block appears on the page and a visible
provenance line appears on the page, so quoting history is not a licence to display the
retired brand; provenance belongs in a non-rendered comment.

The sweep's own pattern set is pinned here verbatim: the new check must not widen, weaken or
duplicate the retired-namespace gate.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECK = REPO_ROOT / "tools" / "site-brand-check.sh"
SWEEP = REPO_ROOT / "tools" / "legacy-string-sweep.sh"

#: Pinned VERBATIM from tools/legacy-string-sweep.sh line 26 as of this change. D-A: the
#: site brand check is additive; if this line moves, the retired-namespace gate changed and
#: that must be a deliberate, separately-reviewed edit.
PINNED_PATTERNS = "PATTERNS='/cc-suite:|/nlpm:|/grill:|/codex-toolkit:|/vibe:'"

#: The retired product brand, bare — no namespace colon, so the sweep cannot see it.
BRAND = "nlpm"

CLEAN_PAGE = "# vibe-suite\n\nAn audit suite for natural-language artifacts.\n"


def run_check(*args):
    return subprocess.run(["bash", str(CHECK), *[str(a) for a in args]],
                          capture_output=True, text=True, cwd=str(REPO_ROOT))


class BrandCheckBase(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CHECK.is_file(), f"{CHECK} must exist before this suite runs")
        self.tmp = Path(tempfile.mkdtemp(prefix="site-brand-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def seed(self, rel, text):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def assertFlags(self, result, where):
        self.assertNotEqual(
            result.returncode, 0,
            f"site-brand-check returned 0 for a bare brand string in {where}; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}")

    def assertClean(self, result, where):
        self.assertEqual(
            result.returncode, 0,
            f"site-brand-check returned {result.returncode} for {where}, which does not "
            f"render; stdout={result.stdout!r} stderr={result.stderr!r}")


class Contract(BrandCheckBase):
    def test_isc_header_in_first_three_lines(self):
        head = "\n".join(CHECK.read_text(encoding="utf-8").splitlines()[:3])
        self.assertIn("SPDX-License-Identifier: ISC", head)

    def test_legacy_sweep_patterns_are_unchanged(self):
        text = SWEEP.read_text(encoding="utf-8")
        self.assertIn(PINNED_PATTERNS, text,
                      "the retired-namespace pattern set moved; D-A forbids this check "
                      "widening, weakening or duplicating it")

    def test_clean_directory_exits_zero(self):
        self.seed("index.md", CLEAN_PAGE)
        self.assertClean(run_check(self.tmp), "a tree with no retired brand")

    def test_missing_directory_argument_is_a_usage_error(self):
        result = run_check()
        self.assertEqual(result.returncode, 2,
                         "a run with no directory argument must be a usage error (exit 2), "
                         f"got {result.returncode}")

    def test_nonexistent_directory_is_an_error(self):
        result = run_check(self.tmp / "does-not-exist")
        self.assertNotEqual(result.returncode, 0,
                            "a directory that does not exist must not report clean")


class RenderedSurfaceFails(BrandCheckBase):
    """Everything that reaches the page is flagged — D-A admits no rendered exception."""

    def test_tracked_site_page(self):
        self.seed("site/why.md", f"# Why\n\nBuilt on the {BRAND} rule engine.\n")
        self.assertFlags(run_check(self.tmp), "a tracked site page")

    def test_generated_output_under_the_directory_argument(self):
        # The gap AC-6 cannot see: site/data/ and site/reports/ are gitignored (D-D), so a
        # tracked-file sweep never reads them. The directory argument is what closes it.
        self.seed("dist/reports/repo-alpha.html",
                  f"<h1>repo-alpha</h1><p>Scored by {BRAND}.</p>\n")
        self.assertFlags(run_check(self.tmp / "dist"), "generated output under the argument")

    def test_fenced_code_block(self):
        self.seed("site/install.md",
                  "# Install\n\n```console\n$ " + BRAND + " score .\n```\n")
        self.assertFlags(run_check(self.tmp), "a fenced code block (which renders)")

    def test_visible_provenance_line(self):
        self.seed("site/how-it-works.md",
                  f"# How it works\n\n_Derived from the {BRAND} scoring rules._\n")
        self.assertFlags(run_check(self.tmp), "a visible provenance line (which renders)")

    def test_case_insensitive_upper(self):
        self.seed("site/index.md", "# vibe-suite\n\nSuccessor to NLPM.\n")
        self.assertFlags(run_check(self.tmp), "an upper-case NLPM")

    def test_case_insensitive_title(self):
        self.seed("site/index.md", "# vibe-suite\n\nSuccessor to Nlpm.\n")
        self.assertFlags(run_check(self.tmp), "a title-case Nlpm")

    def test_recurses_into_subdirectories(self):
        self.seed("index.md", CLEAN_PAGE)
        self.seed("guide/deep/nested/page.md", f"Ported from {BRAND}.\n")
        self.assertFlags(run_check(self.tmp), "a file three directories down")

    def test_report_names_the_offending_path_and_line(self):
        self.seed("site/why.md", f"# Why\n\nline two\nBuilt on {BRAND}.\n")
        result = run_check(self.tmp)
        self.assertFlags(result, "a tracked site page")
        report = result.stdout + result.stderr
        self.assertRegex(report, r"why\.md[: ]",
                         f"the report must name the offending path; got {report!r}")
        self.assertRegex(report, r"why\.md:4\b",
                         f"the report must name the offending line; got {report!r}")


class NonRenderedPasses(BrandCheckBase):
    """The only allowed forms: provenance that never reaches the page."""

    def test_html_comment_is_not_rendered(self):
        self.seed("site/why.md",
                  f"<!-- provenance: adapted from the {BRAND} rule set -->\n{CLEAN_PAGE}")
        self.assertClean(run_check(self.tmp), "an HTML comment")

    def test_source_comment_in_a_config_file(self):
        self.seed("site/.vitepress/config.ts",
                  "// SPDX-License-Identifier: ISC\n"
                  f"// Layout adapted from the {BRAND} reference site.\n"
                  "export default { title: 'vibe-suite' }\n")
        self.assertClean(run_check(self.tmp), "a source comment in a config file")

    def test_source_comment_in_a_theme_file(self):
        self.seed("site/.vitepress/theme/index.ts",
                  "// SPDX-License-Identifier: ISC\n"
                  f"/* Palette derived from {BRAND}. */\n"
                  "export default {}\n")
        self.assertClean(run_check(self.tmp), "a source comment in a theme file")


if __name__ == "__main__":
    unittest.main()
