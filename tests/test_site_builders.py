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
MALFORMED = FIXTURES / "malformed"

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
        self.assertTrue((MALFORMED / "manifest.json").is_file(), f"{MALFORMED} missing")


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
                result = run_builder(name, MALFORMED, self.out_dir(name))
                self.assertNotEqual(result.returncode, 0,
                                    f"{name} exited 0 on a malformed corpus manifest; "
                                    f"corrupt input must never render as healthy")

    def test_names_the_error(self):
        for name, _, _ in BUILDERS:
            with self.subTest(builder=name):
                result = run_builder(name, MALFORMED, self.out_dir(name))
                report = (result.stderr + result.stdout).lower()
                self.assertIn("manifest", report,
                              f"{name} must name the malformed input; got {report!r}")

    def test_does_not_emit_a_healthy_empty_page(self):
        # A malformed corpus silently degrading to the empty state would hide corruption.
        for name, _, page in BUILDERS:
            with self.subTest(builder=name):
                out = self.out_dir(name)
                run_builder(name, MALFORMED, out)
                rendered = out / page
                if rendered.is_file():
                    self.assertNotIn(NOTICE, rendered.read_text(encoding="utf-8").lower(),
                                     f"{name} rendered the empty-state notice for a "
                                     f"MALFORMED corpus, disguising corruption as no data")


if __name__ == "__main__":
    unittest.main()
