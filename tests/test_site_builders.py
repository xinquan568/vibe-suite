#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""T2 (E8.4 / vibe-61) — the five `bin/vibe-build-*` site builders.

Design decision D-C: **an empty corpus is a first-class state, not an error.** There is no
`auditor-data` corpus until E8.5, so a builder whose inputs are absent must still exit 0 and
emit schema-valid, visibly-empty output carrying a "no audit data yet" notice — an empty site
must read as *pre-migration*, never as broken. Only malformed input is an error.

The uniform CLI contract every builder honours:

    bin/vibe-build-<name> --corpus <dir> --out <dir>

writing `<out>/data/<slug>.json` (the schema-valid data file) and `<out>/<page>` (the rendered
page). The corpus root carries `manifest.json`; absent corpus directory = empty state,
unparseable `manifest.json` = a named error on stderr with a non-zero exit.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN = REPO_ROOT / "bin"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "site"
CORPUS = FIXTURES / "corpus"
MALFORMED_SRC = FIXTURES / "malformed" / "manifest.json.broken"


def materialise_malformed(tmp):
    """Copy the broken manifest into `tmp` as a real `manifest.json`.

    The fixture is stored with a `.broken` suffix because CI parses EVERY tracked `*.json`
    ("Every other JSON file parses"), and a deliberately-unparseable one fails that gate. The
    corpus the builder actually sees still has to be named `manifest.json`, so the test creates
    it at run time instead of committing it.
    """
    dest = Path(tmp) / "manifest.json"
    dest.write_bytes(MALFORMED_SRC.read_bytes())
    return Path(tmp)

NOTICE = "no audit data yet"

#: (executable, data slug, rendered page) — the five builders of F10.3 / I1.
BUILDERS = (
    ("vibe-build-reference-md", "reference", "reference/index.md"),
    ("vibe-build-vocab-data", "vocab", "vocab/index.md"),
    ("vibe-build-site-report-pages", "reports", "reports/index.md"),
    ("vibe-build-case-studies-index", "case-studies", "case-studies/index.md"),
    ("vibe-build-docs", "docs", "docs/index.md"),
)


def run_builder(name, corpus, out):
    return subprocess.run(
        [sys.executable, str(BIN / name), "--corpus", str(corpus), "--out", str(out)],
        capture_output=True, text=True, cwd=str(REPO_ROOT))


class BuilderBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="site-builders-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def out_dir(self, name):
        d = self.tmp / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def read_data(self, out, slug, name, state):
        path = out / "data" / f"{slug}.json"
        self.assertTrue(path.is_file(),
                        f"{name} emitted no data file at data/{slug}.json for {state}; "
                        f"produced {sorted(p.name for p in out.rglob('*') if p.is_file())}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"{name} emitted unparseable JSON for {state}: {exc}")

    def assertSchema(self, payload, name, state):
        self.assertIsInstance(payload, dict,
                             f"{name} data must be an object for {state}")
        self.assertEqual(payload.get("builder"), name,
                         f"{name} data must name its builder for {state}")
        self.assertIsInstance(payload.get("entries"), list,
                             f"{name} data must carry an entries list for {state}")

    def read_page(self, out, page, name, state):
        path = out / page
        self.assertTrue(path.is_file(),
                        f"{name} rendered no page at {page} for {state}; produced "
                        f"{sorted(str(p.relative_to(out)) for p in out.rglob('*') if p.is_file())}")
        return path.read_text(encoding="utf-8")


class Contract(BuilderBase):
    def test_every_builder_exists_and_is_executable(self):
        for name, _, _ in BUILDERS:
            with self.subTest(builder=name):
                self.assertTrue((BIN / name).is_file(), f"bin/{name} is missing")

    def test_every_builder_carries_the_isc_header(self):
        for name, _, _ in BUILDERS:
            with self.subTest(builder=name):
                head = "\n".join((BIN / name).read_text(encoding="utf-8").splitlines()[:3])
                self.assertIn("SPDX-License-Identifier: ISC", head)

    def test_the_fixture_corpus_is_present(self):
        # Guards the RED capture: a fixture-not-found failure would prove nothing.
        self.assertTrue((CORPUS / "manifest.json").is_file(), f"{CORPUS} fixture missing")
        self.assertTrue(MALFORMED_SRC.is_file(), f"{MALFORMED_SRC} missing")


class AbsentCorpus(BuilderBase):
    """D-C: absent inputs are the honest pre-migration state, and exit 0."""

    def absent(self):
        return self.tmp / "no-such-corpus"

    def test_exits_zero(self):
        for name, _, _ in BUILDERS:
            with self.subTest(builder=name):
                result = run_builder(name, self.absent(), self.out_dir(name))
                self.assertEqual(result.returncode, 0,
                                 f"{name} exited {result.returncode} on an absent corpus; "
                                 f"an empty corpus is a state, not an error. "
                                 f"stderr={result.stderr!r}")

    def test_emits_schema_valid_empty_data(self):
        for name, slug, _ in BUILDERS:
            with self.subTest(builder=name):
                out = self.out_dir(name)
                run_builder(name, self.absent(), out)
                payload = self.read_data(out, slug, name, "an absent corpus")
                self.assertSchema(payload, name, "an absent corpus")
                self.assertEqual(payload["entries"], [],
                                 f"{name} must emit zero entries for an absent corpus")

    def test_renders_the_no_audit_data_notice(self):
        for name, _, page in BUILDERS:
            with self.subTest(builder=name):
                out = self.out_dir(name)
                run_builder(name, self.absent(), out)
                text = self.read_page(out, page, name, "an absent corpus")
                self.assertIn(NOTICE, text.lower(),
                              f"{name} rendered no {NOTICE!r} notice, so an empty site "
                              f"reads as broken rather than pre-migration")


class PopulatedCorpus(BuilderBase):
    def test_exits_zero(self):
        for name, _, _ in BUILDERS:
            with self.subTest(builder=name):
                result = run_builder(name, CORPUS, self.out_dir(name))
                self.assertEqual(result.returncode, 0,
                                 f"{name} exited {result.returncode} on the fixture corpus; "
                                 f"stderr={result.stderr!r}")

    def test_emits_schema_valid_populated_data(self):
        for name, slug, _ in BUILDERS:
            with self.subTest(builder=name):
                out = self.out_dir(name)
                run_builder(name, CORPUS, out)
                payload = self.read_data(out, slug, name, "the fixture corpus")
                self.assertSchema(payload, name, "the fixture corpus")
                self.assertTrue(payload["entries"],
                                f"{name} produced zero entries from a populated corpus")

    def test_page_drops_the_empty_notice(self):
        for name, _, page in BUILDERS:
            with self.subTest(builder=name):
                out = self.out_dir(name)
                run_builder(name, CORPUS, out)
                text = self.read_page(out, page, name, "the fixture corpus")
                self.assertNotIn(NOTICE, text.lower(),
                                 f"{name} still renders the empty notice with data present")


class MalformedCorpus(BuilderBase):
    def test_exits_nonzero(self):
        for name, _, _ in BUILDERS:
            with self.subTest(builder=name):
                with tempfile.TemporaryDirectory() as md:
                    result = run_builder(name, materialise_malformed(md), self.out_dir(name))
                self.assertNotEqual(result.returncode, 0,
                                    f"{name} exited 0 on a malformed corpus manifest; "
                                    f"corrupt input must never render as healthy")

    def test_names_the_error(self):
        for name, _, _ in BUILDERS:
            with self.subTest(builder=name):
                with tempfile.TemporaryDirectory() as md:
                    result = run_builder(name, materialise_malformed(md), self.out_dir(name))
                report = (result.stderr + result.stdout).lower()
                self.assertIn("manifest", report,
                              f"{name} must name the malformed input; got {report!r}")

    def test_does_not_emit_a_healthy_empty_page(self):
        # A malformed corpus silently degrading to the empty state would hide corruption.
        for name, _, page in BUILDERS:
            with self.subTest(builder=name):
                out = self.out_dir(name)
                with tempfile.TemporaryDirectory() as md:
                    run_builder(name, materialise_malformed(md), out)
                rendered = out / page
                if rendered.is_file():
                    self.assertNotIn(NOTICE, rendered.read_text(encoding="utf-8").lower(),
                                     f"{name} rendered the empty-state notice for a "
                                     f"MALFORMED corpus, disguising corruption as no data")


# ---------------------------------------------------------------------------------------------
# vibe-196 / M23 — corpus strings render as text, never as markup or template code.
#
# Every builder interpolates corpus strings into Markdown that VitePress compiles as a Vue
# template. Three things in such a string are live there: HTML (markdown-it `html: true`, the
# VitePress default), a Vue mustache (`{{ }}` is evaluated wherever it appears in template text,
# inline code included), and a table pipe (ends a GFM cell). `scripts/site_markdown.md_escape`
# closes all three for scalar positions; `site/.vitepress/config.ts` turns raw HTML off for every
# page; corpus prose (a rule body) is wrapped in VitePress's `::: v-pre` container.
#
# RED on the base tree: `scripts/site_markdown.py` does not exist, every page carries `<script>`
# and `{{ 1+1 }}` verbatim, and config.ts has no `markdown` key.
# ---------------------------------------------------------------------------------------------

import importlib.util
import os
import re

SCRIPT = "<script>alert(1)</script>"
MUSTACHE = "{{ 1+1 }}"
HOSTILE = f"{SCRIPT} {MUSTACHE} a | b &amp; `tick`"
ESCAPED_SCRIPT = "&lt;script&gt;alert(1)&lt;/script&gt;"
ESCAPED_MUSTACHE = "&#123;&#123; 1+1 }}"
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
SITE_CONFIG = REPO_ROOT / "site" / ".vitepress" / "config.ts"
VITEPRESS = REPO_ROOT / "site" / "node_modules" / ".bin" / "vitepress"


def write_hostile_corpus(root):
    """A corpus in the fixture's shape whose every string position carries HOSTILE."""
    root = Path(root)
    (root / "audits").mkdir(parents=True)
    (root / "articles").mkdir()
    (root / "rules").mkdir()
    (root / "framework").mkdir()
    (root / "manifest.json").write_text(json.dumps({
        "corpus_version": 1,
        "repos": [{"name": f"repo {HOSTILE}", "audit": "audits/repo.json"}],
        "articles": ["articles/2026-01-repo.md"],
        "vocabulary": "registry.yaml",
        "rules": ["rules/testing.md"],
        "docs": ["framework/reference.md"],
    }), encoding="utf-8")
    # `score` is audit-supplied JSON, so a hostile STRING score is a real input — kept hostile here so
    # the page-wide assertions catch an omitted escape at that sink (a numeric score is covered as a
    # declared benign case in ConstrainedSinks).
    (root / "audits" / "repo.json").write_text(json.dumps({
        "repo": f"repo {HOSTILE}", "score": f"score {HOSTILE}",
        "findings": [{"id": f"R7{SCRIPT}", "severity": f"major {MUSTACHE}", "title": HOSTILE}],
    }), encoding="utf-8")
    # The front-matter `date` is free text, so it is a real sink — kept hostile so an omitted escape
    # on the date is caught by the page-wide assertions.
    (root / "articles" / "2026-01-repo.md").write_text(
        f"---\ntitle: Auditing {HOSTILE}\ndate: date {HOSTILE}\nrepo: {HOSTILE}\n---\n\n"
        f"Summary {HOSTILE}\n", encoding="utf-8")
    # The body carries a raw HTML block AND a bare `:::` line followed by a mustache — a container
    # closer that would break a fixed-length v-pre wrapper and re-expose the mustache (vibe-196).
    (root / "rules" / "testing.md").write_text(
        f"# R7 — tests {HOSTILE}\n\nBody {HOSTILE}\n<div onclick=alert(1)>raw block</div>\n"
        f":::\n{MUSTACHE} after a bare closer\n",
        encoding="utf-8")
    (root / "framework" / "reference.md").write_text(
        f"# Framework {HOSTILE}\n\nLead {HOSTILE}\n\n## Section {HOSTILE}\n", encoding="utf-8")
    (root / "registry.yaml").write_text(
        f"nouns:\n  - canonical: finding{SCRIPT}\n    deprecated: ['issue {MUSTACHE}', 'x | y']\n"
        f"verbs:\n  - canonical: audit\n    deprecated: [review]\n", encoding="utf-8")
    return root


class MdEscape(unittest.TestCase):
    """`scripts/site_markdown.md_escape` — the one escape the five builders share."""

    def setUp(self):
        path = REPO_ROOT / "scripts" / "site_markdown.py"
        self.assertTrue(path.is_file(), f"{path} is missing: the builders have no shared escape")
        spec = importlib.util.spec_from_file_location("site_markdown", path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_each_live_character_is_neutralised(self):
        cases = (
            ("html tag", SCRIPT, ESCAPED_SCRIPT),
            ("ampersand", "a & b", "a &amp; b"),
            ("existing entity is literalised", "&lt;", "&amp;lt;"),
            ("greater-than", "a > b", "a &gt; b"),
            ("mustache opener", MUSTACHE, ESCAPED_MUSTACHE),
            ("triple brace leaves one inert brace", "{{{ x }}}", "&#123;&#123;{ x }}}"),
            ("table pipe", "a | b", "a \\| b"),
            ("input backslash cannot re-arm a pipe", "a\\|b", "a\\\\\\|b"),
            ("none renders empty", None, ""),
            ("non-string scalar", 82, "82"),
        )
        for name, raw, expected in cases:
            with self.subTest(case=name):
                self.assertEqual(self.mod.md_escape(raw), expected)

    def test_v_pre_wraps_a_prose_block_in_the_container(self):
        self.assertEqual(self.mod.v_pre("body"), "::: v-pre\nbody\n:::")
        self.assertEqual(self.mod.v_pre("\n\nfirst\n\nsecond\n"), "::: v-pre\nfirst\n\nsecond\n:::")

    def test_v_pre_fence_outruns_any_colon_line_in_the_body(self):
        # A body line that is a run of colons would close a fixed-length wrapper; the fence must be
        # strictly longer than the longest such run so corpus content cannot terminate it early.
        for body, opener in (
            ("a\n:::\nb", "::::"),           # bare ::: -> 4-colon fence
            ("a\n::::::\nb", ":::::::"),      # 6 -> 7
            ("a\n  ::::  \nb", ":::::"),      # spaced 4 -> 5
            ("plain prose", ":::"),          # no colon line -> the 3-colon default
        ):
            with self.subTest(body=body):
                wrapped = self.mod.v_pre(body)
                self.assertTrue(wrapped.startswith(opener + " v-pre\n"), wrapped)
                self.assertTrue(wrapped.endswith("\n" + opener), wrapped)
                fence_len = len(opener)
                for line in body.splitlines():
                    run = line.strip()
                    if run and set(run) == {":"}:
                        self.assertLess(len(run), fence_len,
                                        f"a {len(run)}-colon body line can close a {fence_len}-colon fence")


class HostileCorpus(BuilderBase):
    """Every builder writes corpus strings as text at the Markdown layer."""

    def setUp(self):
        super().setUp()
        self.corpus = write_hostile_corpus(self.tmp / "hostile")

    def pages(self, name):
        out = self.out_dir(name)
        result = run_builder(name, self.corpus, out)
        self.assertEqual(result.returncode, 0, f"{name} failed on the hostile corpus: {result.stderr!r}")
        return {str(p.relative_to(out)): p.read_text(encoding="utf-8") for p in out.rglob("*.md")}

    def test_no_page_carries_a_raw_tag_or_mustache_in_a_scalar_position(self):
        for name, _, _ in BUILDERS:
            with self.subTest(builder=name):
                for page, text in self.pages(name).items():
                    scalar_text = text
                    if page.startswith("reference/") and page != "reference/index.md":
                        # The rule body is corpus prose inside the v-pre container (asserted below);
                        # only the part before the container is a scalar position.
                        scalar_text = re.split(r"\n:{3,} v-pre\n", text, 1)[0]
                    self.assertNotIn(SCRIPT, scalar_text, f"{name} {page} carries a raw <script>")
                    self.assertNotIn(MUSTACHE, scalar_text, f"{name} {page} carries a live mustache")
                    self.assertIn(ESCAPED_SCRIPT, scalar_text, f"{name} {page} lost the escaped title")
                    self.assertIn(ESCAPED_MUSTACHE, scalar_text, f"{name} {page} lost the escaped mustache")

    def test_the_rule_body_is_wrapped_in_the_v_pre_container(self):
        text = self.pages("vibe-build-reference-md")["reference/r7.md"]
        m = re.search(r"\n(:{3,}) v-pre\n(.*)\n\1\n?$", text, re.DOTALL)
        self.assertTrue(m, f"the rule body is not wrapped in a v-pre container: {text!r}")
        fence, body = m.group(1), m.group(2)
        self.assertTrue(text.startswith(f"# R7 — tests {ESCAPED_SCRIPT}"), f"heading not escaped: {text[:80]!r}")
        self.assertIn("<div onclick=alert(1)>raw block</div>", body,
                      "the body must keep its own Markdown verbatim inside the container")
        # The body's bare `:::` closer cannot match the (longer) fence, so nothing in it escapes.
        for line in body.splitlines():
            run = line.strip()
            if run and set(run) == {":"}:
                self.assertLess(len(run), len(fence),
                                f"a {len(run)}-colon body line can close the {len(fence)}-colon fence")

    def test_table_rows_keep_their_cell_count(self):
        reports = self.pages("vibe-build-site-report-pages")
        [index_row] = [l for l in reports["reports/index.md"].splitlines() if l.startswith("| [")]
        # repo name AND the hostile score both carry a `|`; escaped, the row keeps its 4 structural pipes.
        self.assertEqual(len(UNESCAPED_PIPE.findall(index_row)), 4, f"index row split by a pipe: {index_row!r}")
        self.assertTrue(index_row.rstrip().endswith("| 1 |"), f"findings cell lost: {index_row!r}")
        [severity_row] = [l for l in reports["reports/repo-script-alert-1-script-1-1-a-b-amp-tick.md"]
                          .splitlines() if l.startswith("| major")]
        self.assertEqual(len(UNESCAPED_PIPE.findall(severity_row)), 3, severity_row)
        vocab = self.pages("vibe-build-vocab-data")["vocab/index.md"]
        [noun_row] = [l for l in vocab.splitlines() if l.startswith("| finding")]
        self.assertEqual(len(UNESCAPED_PIPE.findall(noun_row)), 3, f"vocab row split by a pipe: {noun_row!r}")
        self.assertIn("x \\| y", noun_row)

    def test_corpus_scalars_are_not_placed_in_code_spans(self):
        # A code span cannot be escaped (its content renders literally, entities included) and a
        # backtick in the value would end it — so the builders render these scalars as plain text.
        report = self.pages("vibe-build-site-report-pages")["reports/repo-script-alert-1-script-1-1-a-b-amp-tick.md"]
        self.assertRegex(report, rf"(?m)^- \*\*R7{re.escape(ESCAPED_SCRIPT)}\*\* — major {re.escape(ESCAPED_MUSTACHE)}: ")
        vocab = self.pages("vibe-build-vocab-data")["vocab/index.md"]
        self.assertRegex(vocab, rf"(?m)^\| finding{re.escape(ESCAPED_SCRIPT)} \| issue {re.escape(ESCAPED_MUSTACHE)}, x \\\| y \|$")
        studies = self.pages("vibe-build-case-studies-index")["case-studies/index.md"]
        # title and repo both escaped; the repo sits in plain parens, not a code span (date is hostile too).
        self.assertRegex(studies, rf"(?m)^- \*\*Auditing {re.escape(ESCAPED_SCRIPT)}.*\({re.escape(ESCAPED_SCRIPT)}")
        docs = self.pages("vibe-build-docs")
        [doc_page] = [t for p, t in docs.items() if p.startswith("docs/") and p != "docs/index.md"]
        self.assertIn("Source: framework/reference.md (markdown).", doc_page)


class ConstrainedSinks(BuilderBase):
    """The matrix sinks that cannot carry a live character, pinned by exact render.

    Three sinks in the interpolation matrix are structurally benign — a numeric score, the reference
    rule id (heading regex `[A-Za-z]+[-_]?\\d+`), and the doc `source` (a manifest path). A page-wide
    "no <script>" assertion cannot catch an omitted escape there because the value has no live
    character, so these are pinned by exact-render assertions instead: an omission is caught by the
    literal string, and the escape stays a no-op on values that are already inert.
    """

    def build(self, name, corpus):
        out = self.out_dir(name)
        self.assertEqual(run_builder(name, corpus, out).returncode, 0)
        return {str(p.relative_to(out)): p.read_text(encoding="utf-8") for p in out.rglob("*.md")}

    def test_numeric_score_renders_as_the_number(self):
        corpus = self.tmp / "numeric"
        (corpus / "audits").mkdir(parents=True)
        (corpus / "manifest.json").write_text(json.dumps({
            "repos": [{"name": "repo-alpha", "audit": "audits/a.json"}]}), encoding="utf-8")
        (corpus / "audits" / "a.json").write_text(json.dumps({
            "repo": "repo-alpha", "score": 82, "findings": []}), encoding="utf-8")
        pages = self.build("vibe-build-site-report-pages", corpus)
        self.assertRegex(pages["reports/index.md"], r"\| \[repo-alpha\]\(repo-alpha\.md\) \| 82 \| 0 \|")
        self.assertIn("Score: **82**", pages["reports/repo-alpha.md"])

    def test_reference_id_is_regex_constrained_and_rendered_exactly(self):
        corpus = self.tmp / "ref"
        (corpus / "rules").mkdir(parents=True)
        (corpus / "manifest.json").write_text(json.dumps({"rules": ["rules/r.md"]}), encoding="utf-8")
        # A heading whose id part cannot hold <,&,{,| by the HEADING regex; the title carries the payload.
        (corpus / "rules" / "r.md").write_text(f"# R7 — tests {SCRIPT}\n\nbody\n", encoding="utf-8")
        pages = self.build("vibe-build-reference-md", corpus)
        self.assertIn(f"- [R7 — tests {ESCAPED_SCRIPT}](r7.md)", pages["reference/index.md"])
        self.assertTrue(pages["reference/r7.md"].startswith(f"# R7 — tests {ESCAPED_SCRIPT}\n"))

    def test_doc_source_path_rendered_exactly(self):
        corpus = self.tmp / "doc"
        (corpus / "framework").mkdir(parents=True)
        (corpus / "manifest.json").write_text(json.dumps({"docs": ["framework/ref.md"]}), encoding="utf-8")
        (corpus / "framework" / "ref.md").write_text(f"# Doc {SCRIPT}\n\nlead\n", encoding="utf-8")
        pages = self.build("vibe-build-docs", corpus)
        [doc] = [t for p, t in pages.items() if p.startswith("docs/") and p != "docs/index.md"]
        self.assertIn("Source: framework/ref.md (markdown).", doc)


class SiteConfig(unittest.TestCase):
    def test_vitepress_renders_raw_html_as_text(self):
        text = SITE_CONFIG.read_text(encoding="utf-8")
        self.assertRegex(text, r"markdown:\s*\{[^}]*\bhtml:\s*false",
                         "site/.vitepress/config.ts must set markdown.html to false (VitePress defaults to true)")


class RenderedSite(BuilderBase):
    """The built page shows the hostile strings literally — runs wherever VitePress is installed.

    CI's `test` job has no site/node_modules, so this class skips there and runs in
    `site-validate`, which installs the site toolchain before invoking this module.
    """

    def setUp(self):
        super().setUp()
        if not VITEPRESS.is_file():
            self.skipTest("VitePress is not installed under site/node_modules (site-validate installs it)")
        self.corpus = write_hostile_corpus(self.tmp / "hostile")
        tree = self.tmp / "tree"
        tree.mkdir()
        os.symlink(REPO_ROOT / "bin", tree / "bin")
        os.symlink(REPO_ROOT / "scripts", tree / "scripts")
        site = tree / "site"
        shutil.copytree(REPO_ROOT / "site", site,
                        ignore=shutil.ignore_patterns("node_modules", "dist", "cache", "data", "reports",
                                                      "reference", "vocab", "case-studies", "docs"))
        os.symlink(REPO_ROOT / "site" / "node_modules", site / "node_modules")
        self.site = site

    def test_hostile_strings_render_literally_in_the_built_pages(self):
        result = subprocess.run(["bash", str(self.site / "build.sh"), "--corpus", str(self.corpus),
                                 "--out", str(self.site)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"site build failed: {result.stdout[-800:]}{result.stderr[-800:]}")
        dist = self.site / ".vitepress" / "dist"
        pages = {str(p.relative_to(dist)): p.read_text(encoding="utf-8") for p in dist.rglob("*.html")}
        generated = [p for p in pages if p.split("/")[0] in ("reports", "reference", "vocab", "case-studies", "docs")]
        self.assertTrue(generated, f"no generated pages in {sorted(pages)}")
        for page in generated:
            with self.subTest(page=page):
                html = pages[page]
                self.assertNotIn(SCRIPT, html, "a raw <script> element reached the built page")
                self.assertNotRegex(html, r"<[a-zA-Z][^>]*\sonclick=",
                                    "an element with an event handler reached the built page")
                self.assertIn(ESCAPED_SCRIPT, html, "the escaped tag is not shown as text")
                self.assertIn(MUSTACHE, html, "the mustache was not rendered literally (Vue evaluated it?)")
        self.assertIn("<td>1</td></tr>", pages["reports/index.html"], "the index row lost its findings cell")
        self.assertIn(f"issue {MUSTACHE}, x | y", pages["vocab/index.html"])
        # The rule body's raw block is corpus prose: under markdown.html=false it is shown as text.
        self.assertIn("&lt;div onclick=alert(1)&gt;raw block&lt;/div&gt;", pages["reference/r7.html"])
        # The bare `:::` closer inside the body must not break the wrapper: the mustache after it
        # is still literal, not evaluated to `2`.
        self.assertIn(f"{MUSTACHE} after a bare closer", pages["reference/r7.html"],
                      "the post-::: mustache was evaluated — the v-pre container broke out")


if __name__ == "__main__":
    unittest.main()
