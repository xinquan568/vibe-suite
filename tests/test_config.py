#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Tests for the `.vibe-suite.md` schema and its reader (E0.5 / vibe-7).

Three properties shape this suite, and each exists because a weaker version was caught in review.

**The oracle is a reviewed specification fixture, not a derivation.** `EXPECTED_SCHEMA` below is
written by hand. Comparing the reader's registry against `vibe-core`'s table would catch them
drifting apart but not both being wrong together, so the constants here are the third party that
makes coordinated drift detectable.

**Full rows, not key names.** Comparison is over `(type, domain, default)` tuples. A reader with
every key present but `score_threshold` typed as a string, or an enum domain quietly widened, passes
a membership check and fails this one.

**The grammar is a closed subset and its rejections are the specification.** A parser that silently
tolerates a flow collection has a different grammar from the documented one, and no positive test
notices. Every rejected construct therefore gets a negative fixture.

Note on plain scalars: `*`, `?`, `[` and `]` are ordinary characters. `skip_patterns` is the key most
likely to contain them, so a reader that rejects punctuation defensively would break the one field
that needs it most.
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PY = REPO_ROOT / "scripts" / "lib" / "config.py"
VIBE_CORE = REPO_ROOT / "skills" / "vibe-core" / "SKILL.md"
MODEL_SELECTION = REPO_ROOT / "commands" / "shared" / "model-selection.md"


def _load(path, name):
    if not path.exists():
        raise AssertionError(f"not found: {path.relative_to(REPO_ROOT)}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = _load(CONFIG_PY, "vibe_config")


# --------------------------------------------------------------- the independent oracle
# Hand-written specification fixture. Never regenerated from any artifact.

EXPECTED_SCHEMA = {
    "engine":                   ("enum",   "claude|codex|agy|both",                  "unset"),
    "cross_model_audit_engine": ("enum",   "codex|agy",                              "codex"),
    "reviewer_backend":         ("enum",   "codex",                                  "codex"),
    "reviewer_model":           ("string", "open",                                   "unset"),
    "effort":                   ("enum",   "low|medium|high",                        "medium"),
    "sandbox":                  ("enum",   "read-only|workspace-write|danger-full-access", "read-only"),
    "audit_depth":              ("enum",   "mini|full",                              "unset"),
    "model_overrides":          ("map",    "codex|agy",                              "empty-map"),
    "skip_patterns":            ("list",   "open",                                   "empty-list"),
    "focus_instructions":       ("string", "open",                                   "empty-string"),
    "project_instructions":     ("string", "open",                                   "empty-string"),
    "score_threshold":          ("int",    "0-100",                                  "70"),
    "rule_overrides":           ("map",    "closed",                                 "empty-map"),
    "issue2pr_profile":         ("string", "id",                                     "unset"),
    "gate":                     ("map",    "closed",                                 "unset"),
}

SHADOWABLE = {"gate.stop_review_gate", "gate.model", "gate.fail_policy"}
PATH_VALUED = {"rule_overrides.R51.vocabulary_skill", "issue2pr_profile"}


def write_config(root, frontmatter, body="\n# notes\n"):
    path = Path(root) / ".vibe-suite.md"
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


class TestRoundTrip(unittest.TestCase):
    """The acceptance criterion, over every shape the grammar admits."""

    def test_scalars_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "engine: codex\nscore_threshold: 85\n")
            cfg = config.load(root)
            self.assertEqual(cfg["engine"], "codex")
            self.assertEqual(cfg["score_threshold"], 85)

    def test_list_round_trips(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "skip_patterns:\n  - '**/*.md'\n  - vendor/**\n")
            self.assertEqual(config.load(root)["skip_patterns"], ["**/*.md", "vendor/**"])

    def test_glob_metacharacters_are_ordinary_scalar_text(self):
        # The key most likely to contain `*`, `?`, `[`: a defensively punctuation-rejecting
        # reader would break exactly this field.
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "skip_patterns:\n  - src/**/*.[ch]\n  - '?tmp/*'\n")
            self.assertEqual(config.load(root)["skip_patterns"], ["src/**/*.[ch]", "?tmp/*"])

    def test_three_level_nesting_round_trips(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "rule_overrides:\n  R51:\n    enabled: true\n")
            self.assertIs(config.load(root)["rule_overrides"]["R51"]["enabled"], True)

    def test_literal_block_scalar_keeps_newlines(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "focus_instructions: |\n  line one\n  line two\n")
            self.assertEqual(config.load(root)["focus_instructions"], "line one\nline two\n")

    def test_folded_block_scalar_joins_with_spaces(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "focus_instructions: >\n  line one\n  line two\n")
            self.assertEqual(config.load(root)["focus_instructions"], "line one line two\n")

    def test_chomping_indicators(self):
        cases = [("|", "a\n"), ("|-", "a"), ("|+", "a\n\n")]
        for indicator, want in cases:
            with self.subTest(indicator=indicator):
                with tempfile.TemporaryDirectory() as root:
                    write_config(root, f"focus_instructions: {indicator}\n  a\n\n")
                    self.assertEqual(config.load(root)["focus_instructions"], want)

    def test_hash_inside_block_content_is_not_a_comment(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "focus_instructions: |\n  # heading\n")
            self.assertEqual(config.load(root)["focus_instructions"], "# heading\n")

    def test_quoted_scalars_are_always_strings(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, 'reviewer_model: "true"\nissue2pr_profile: "42"\n')
            cfg = config.load(root)
            self.assertEqual(cfg["reviewer_model"], "true")
            self.assertEqual(cfg["issue2pr_profile"], "42")

    def test_body_after_the_closing_marker_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "engine: codex\n", body="\n# notes\n\nengine: agy\n")
            self.assertEqual(config.load(root)["engine"], "codex")

    def test_missing_file_yields_defaults(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = config.load(root)
            self.assertEqual(cfg["score_threshold"], 70)
            self.assertEqual(cfg["skip_patterns"], [])


class TestSchemaAgreement(unittest.TestCase):
    """Three artifacts, one contract, compared as full rows against the hand-written oracle."""

    def test_reader_registry_matches_the_oracle(self):
        for key, want in EXPECTED_SCHEMA.items():
            with self.subTest(key=key):
                row = config.SCHEMA.get(key)
                self.assertIsNotNone(row, f"{key} missing from the reader registry")
                self.assertEqual((row.type, row.domain, config.canonical_default(row.default, row.type)), want)

    def test_reader_registry_has_no_extra_keys(self):
        self.assertEqual(set(config.SCHEMA) - set(EXPECTED_SCHEMA), set())

    def test_vibe_core_table_matches_the_oracle(self):
        documented = config.parse_schema_table(VIBE_CORE.read_text(encoding="utf-8"))
        for key, want in EXPECTED_SCHEMA.items():
            with self.subTest(key=key):
                self.assertIn(key, documented, f"{key} undocumented in vibe-core")
                self.assertEqual(documented[key], want)

    def test_model_selection_partial_matches_the_oracle(self):
        # The merged contract from #74. A divergence in either artifact fails here.
        partial = config.parse_schema_table(MODEL_SELECTION.read_text(encoding="utf-8"))
        for key in ("engine", "cross_model_audit_engine", "reviewer_backend", "reviewer_model"):
            with self.subTest(key=key):
                self.assertEqual(partial[key], EXPECTED_SCHEMA[key])


class TestGrammarRejections(unittest.TestCase):
    """The accepted subset is only as good as what it refuses."""

    def _rejects(self, frontmatter):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, frontmatter)
            with self.assertRaises(config.ConfigSyntaxError):
                config.load(root)

    def test_flow_mapping(self):        self._rejects("gate: {stop_review_gate: true}\n")
    def test_flow_sequence(self):       self._rejects("skip_patterns: [a, b]\n")
    def test_tag(self):                 self._rejects("engine: !!str codex\n")
    def test_anchor(self):              self._rejects("engine: &a codex\n")
    def test_merge_key(self):           self._rejects("gate:\n  <<: *base\n")
    def test_directive(self):           self._rejects("%YAML 1.2\nengine: codex\n")
    def test_explicit_key(self):        self._rejects("? engine\n: codex\n")
    def test_document_end_marker(self): self._rejects("engine: codex\n...\n")
    def test_tab_indentation(self):     self._rejects("gate:\n\tmodel: x\n")
    def test_over_depth_map(self):      self._rejects("a:\n  b:\n    c:\n      d: 1\n")
    def test_nested_sequence_item(self):self._rejects("skip_patterns:\n  - - a\n")
    def test_mapping_sequence_item(self):self._rejects("skip_patterns:\n  - a: 1\n")
    def test_unterminated_quote(self):  self._rejects('engine: "codex\n')
    def test_unknown_escape(self):      self._rejects('engine: "co\\qdex"\n')
    def test_trailing_junk_after_quote(self): self._rejects('engine: "codex" extra\n')
    def test_duplicate_key_top_level(self):   self._rejects("engine: codex\nengine: agy\n")

    def test_duplicate_key_when_nested(self):
        self._rejects("rule_overrides:\n  R51:\n    enabled: true\n    enabled: false\n")


class TestAdversarialGrammar(unittest.TestCase):
    """Inputs a hand-written parser accepts by accident. Each was found by attacking the code."""

    def _rejects(self, frontmatter):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, frontmatter)
            with self.assertRaises(config.ConfigSyntaxError):
                config.load(root)

    def test_malformed_single_quote_is_rejected(self):
        # `'a'b'` had decoded to a'b: the naive check was starts-and-ends-with-a-quote.
        self._rejects("reviewer_model: 'a'b'\n")

    def test_doubled_quote_inside_single_quotes_still_works(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "reviewer_model: 'it''s fine'\n")
            self.assertEqual(config.load(root)["reviewer_model"], "it's fine")

    def test_junk_after_a_block_header_is_rejected(self):
        self._rejects("focus_instructions: |garbage\n  x\n")

    def test_over_indented_sequence_item_is_rejected(self):
        # Indentation-based nesting was silently flattened into the parent list.
        self._rejects("skip_patterns:\n  - a\n    - b\n")

    def test_an_indented_marker_inside_block_content_is_content(self):
        # The closing delimiter is recognised only at document level. Treating an indented `---`
        # as the marker truncated the file and discarded everything after it.
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "focus_instructions: |\n  ---\n  after\n")
            self.assertEqual(config.load(root)["focus_instructions"], "---\nafter\n")

    def test_profile_id_rejects_a_trailing_newline(self):
        # `$` matches before a final newline; only fullmatch excludes it.
        with tempfile.TemporaryDirectory() as root:
            write_config(root, 'issue2pr_profile: "safe\\n"\n')
            with self.assertRaises(config.ConfigValueError):
                config.load(root)

    def test_an_explicitly_empty_value_falls_back_to_the_default(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "engine:\nscore_threshold:\n")
            cfg = config.load(root)
            self.assertIsNone(cfg["engine"])
            self.assertEqual(cfg["score_threshold"], 70, "an empty value means absent")

    def test_model_overrides_values_must_be_strings(self):
        for bad in ("model_overrides:\n  codex: true\n", "model_overrides:\n  codex:\n    a: b\n"):
            with self.subTest(fragment=bad):
                with tempfile.TemporaryDirectory() as root:
                    write_config(root, bad)
                    with self.assertRaises(config.ConfigValueError):
                        config.load(root)


class TestCanonicalDefaultIsNotLossy(unittest.TestCase):
    """A normaliser on both sides can hide a difference as easily as expose one."""

    def test_empty_containers_are_distinguished_by_type(self):
        self.assertNotEqual(config.canonical_default([], "list"),
                            config.canonical_default({}, "map"))
        self.assertNotEqual(config.canonical_default([], "list"),
                            config.canonical_default("", "string"))
        self.assertNotEqual(config.canonical_default({}, "map"),
                            config.canonical_default("", "string"))

    def test_none_is_not_the_string_unset_after_normalisation_of_a_typed_default(self):
        # Both map to "unset" by design — absence is absence — but a *populated* string default
        # must never collapse into it.
        self.assertNotEqual(config.canonical_default("codex", "enum"),
                            config.canonical_default(None, "enum"))

    def test_a_wrong_empty_default_in_the_reader_would_fail(self):
        # The concrete regression: skip_patterns defaulting to {} rather than [].
        self.assertNotEqual(config.canonical_default({}, "list"),
                            EXPECTED_SCHEMA["skip_patterns"][2])


class TestDocumentedDefaults(unittest.TestCase):
    """The documented default column is parsed, not borrowed from the code."""

    def test_parse_schema_table_reads_the_default_cell(self):
        table = ("| Key | Type | Domain | Default |\n|---|---|---|---|\n"
                 "| `score_threshold` | int | `0-100` | `999` |\n")
        self.assertEqual(config.parse_schema_table(table)["score_threshold"][2], "999",
                         "the documented default must come from the document")

    def test_a_wrong_documented_default_is_detectable(self):
        # Previously parse_schema_table substituted SCHEMA's default, so documentation could say
        # anything and the comparison still passed.
        table = ("| Key | Type | Domain | Default |\n|---|---|---|---|\n"
                 "| `score_threshold` | int | `0-100` | `999` |\n")
        self.assertNotEqual(config.parse_schema_table(table)["score_threshold"],
                            EXPECTED_SCHEMA["score_threshold"])


class TestFailureModes(unittest.TestCase):
    """One mode warns; four are fatal. Conflating them is the defect this separates."""

    def test_unknown_top_level_key_warns_and_continues(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "reviewer_backedn: codex\nengine: codex\n")
            cfg, warnings = config.load_with_warnings(root)
            self.assertEqual(cfg["engine"], "codex", "a warning must not abort the load")
            self.assertTrue(any("reviewer_backedn" in w for w in warnings))

    def test_a_warning_never_echoes_the_value(self):
        # An unrecognised key may be a typo whose value is a credential.
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "reviewer_backedn: hunter2\n")
            _, warnings = config.load_with_warnings(root)
            self.assertTrue(warnings)
            for warning in warnings:
                self.assertNotIn("hunter2", warning)

    def test_unknown_key_inside_an_open_map_warns(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "model_overrides:\n  codex: some-model\n")
            _, warnings = config.load_with_warnings(root)
            self.assertEqual(warnings, [])

    def test_unknown_key_inside_a_closed_map_errors(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "gate:\n  nonsense: true\n")
            with self.assertRaises(config.ConfigValueError):
                config.load(root)

    def test_invalid_enum_errors_naming_the_domain_not_the_value(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "engine: sekrit-value\n")
            with self.assertRaises(config.ConfigValueError) as caught:
                config.load(root)
            message = str(caught.exception)
            self.assertIn("engine", message)
            self.assertIn("claude", message, "the expected domain should be shown")
            self.assertNotIn("sekrit-value", message, "the offending value must not be echoed")

    def test_out_of_range_int_errors(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "score_threshold: 300\n")
            with self.assertRaises(config.ConfigValueError):
                config.load(root)

    def test_wrong_type_errors(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "score_threshold: high\n")
            with self.assertRaises(config.ConfigValueError):
                config.load(root)


class TestRuleOverridesPerRule(unittest.TestCase):
    """`rule_overrides` opened per-rule for the scoring engine (E3.3 / vibe-28).

    Any `R<n>` key accepts the closed leaf set {suppress, enabled, max_penalty, threshold};
    R51 keeps its `vocabulary_skill` extra. The map stays closed: unknown leaves and
    non-rule keys are still rejected.
    """

    def test_per_rule_override_leaves_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "rule_overrides:\n"
                               "  R01:\n    suppress: true\n    max_penalty: -4\n"
                               "  R05:\n    enabled: false\n    threshold: 300\n")
            cfg = config.load(root)
            self.assertEqual(cfg["rule_overrides"]["R01"],
                             {"suppress": True, "max_penalty": -4})
            self.assertEqual(cfg["rule_overrides"]["R05"],
                             {"enabled": False, "threshold": 300})

    def test_r51_keeps_enabled_and_vocabulary_skill(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "vocab.md").write_text("x", encoding="utf-8")
            write_config(root, "rule_overrides:\n  R51:\n    enabled: true\n"
                               "    vocabulary_skill: vocab.md\n    suppress: true\n")
            cfg = config.load(root)
            self.assertIs(cfg["rule_overrides"]["R51"]["enabled"], True)
            self.assertEqual(cfg["rule_overrides"]["R51"]["vocabulary_skill"], "vocab.md")

    def test_unknown_leaf_under_a_rule_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "rule_overrides:\n  R01:\n    nonsense: true\n")
            with self.assertRaises(config.ConfigValueError):
                config.load(root)

    def test_vocabulary_skill_stays_r51_only(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "rule_overrides:\n  R01:\n    vocabulary_skill: vocab.md\n")
            with self.assertRaises(config.ConfigValueError):
                config.load(root)

    def test_non_rule_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "rule_overrides:\n  bogus:\n    suppress: true\n")
            with self.assertRaises(config.ConfigValueError):
                config.load(root)

    def test_leaf_types_are_enforced(self):
        for bad in ("rule_overrides:\n  R01:\n    suppress: 3\n",
                    "rule_overrides:\n  R01:\n    max_penalty: true\n",
                    "rule_overrides:\n  R01:\n    threshold: soft\n"):
            with self.subTest(fragment=bad):
                with tempfile.TemporaryDirectory() as root:
                    write_config(root, bad)
                    with self.assertRaises(config.ConfigValueError):
                        config.load(root)

    def test_top_level_score_threshold_still_defaults_to_70(self):
        # The engine's pass threshold lives beside the overrides; opening the map must not
        # disturb it.
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "rule_overrides:\n  R01:\n    suppress: true\n")
            self.assertEqual(config.load(root)["score_threshold"], 70)


class TestContainment(unittest.TestCase):
    """Component-wise, after canonicalising both sides."""

    def test_profile_id_rejects_a_separator(self):
        # Traversal dies at the lexical level, before a path exists.
        for bad in ("../evil", "a/b", "a.b"):
            with self.subTest(value=bad):
                with tempfile.TemporaryDirectory() as root:
                    write_config(root, f"issue2pr_profile: '{bad}'\n")
                    with self.assertRaises(config.ConfigValueError):
                        config.load(root)

    def test_traversal_in_a_path_valued_key_errors(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "rule_overrides:\n  R51:\n    vocabulary_skill: ../../etc/passwd\n")
            with self.assertRaises(config.ConfigContainmentError):
                config.load(root)

    def test_absolute_external_path_errors(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "rule_overrides:\n  R51:\n    vocabulary_skill: /etc/passwd\n")
            with self.assertRaises(config.ConfigContainmentError):
                config.load(root)

    def test_symlink_escaping_the_root_errors(self):
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "secret.md").write_text("x", encoding="utf-8")
            with tempfile.TemporaryDirectory() as root:
                os.symlink(Path(outside) / "secret.md", Path(root) / "link.md")
                write_config(root, "rule_overrides:\n  R51:\n    vocabulary_skill: link.md\n")
                with self.assertRaises(config.ConfigContainmentError):
                    config.load(root)

    def test_a_symlinked_root_is_still_its_own_root(self):
        # Canonicalising only the candidate would make every path look external here.
        with tempfile.TemporaryDirectory() as real:
            inner = Path(real) / "proj"
            inner.mkdir()
            (inner / "vocab.md").write_text("x", encoding="utf-8")
            write_config(inner, "rule_overrides:\n  R51:\n    vocabulary_skill: vocab.md\n")
            with tempfile.TemporaryDirectory() as holder:
                link = Path(holder) / "linked-root"
                os.symlink(inner, link)
                cfg = config.load(link)
                self.assertEqual(cfg["rule_overrides"]["R51"]["vocabulary_skill"], "vocab.md")

    def test_sibling_directory_sharing_the_root_prefix_errors(self):
        # `/tmp/proj-evil` starts with `/tmp/proj`; a string-prefix check would admit it.
        with tempfile.TemporaryDirectory() as holder:
            root = Path(holder) / "proj"
            sibling = Path(holder) / "proj-evil"
            root.mkdir(); sibling.mkdir()
            (sibling / "vocab.md").write_text("x", encoding="utf-8")
            write_config(root, "rule_overrides:\n  R51:\n    vocabulary_skill: ../proj-evil/vocab.md\n")
            with self.assertRaises(config.ConfigContainmentError):
                config.load(root)


class TestChannels(unittest.TestCase):
    """The API and the CLI differ, and both are specified."""

    def test_the_api_writes_nothing_to_stdout(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "reviewer_backedn: x\nengine: codex\n")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                config.load_with_warnings(root)
            self.assertEqual(buffer.getvalue(), "", "a warning on stdout corrupts the CLI's JSON")

    def test_the_api_raises_typed_exceptions(self):
        for name in ("ConfigSyntaxError", "ConfigValueError", "ConfigContainmentError"):
            with self.subTest(exception=name):
                self.assertTrue(issubclass(getattr(config, name), Exception))

    def test_the_cli_emits_json_on_stdout_and_warnings_on_stderr(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "reviewer_backedn: x\nengine: codex\n")
            result = subprocess.run([sys.executable, str(CONFIG_PY), "--json", root],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["engine"], "codex")
            self.assertIn("reviewer_backedn", result.stderr)

    def test_the_cli_exits_non_zero_on_a_fatal_error(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "engine: nope\n")
            result = subprocess.run([sys.executable, str(CONFIG_PY), "--json", root],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout.strip(), "", "stdout stays JSON-only or empty")

    def test_api_and_cli_agree(self):
        with tempfile.TemporaryDirectory() as root:
            write_config(root, "engine: codex\nscore_threshold: 42\nskip_patterns:\n  - a/**\n")
            result = subprocess.run([sys.executable, str(CONFIG_PY), "--json", root],
                                    capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout), config.load(root))


class TestConsumerWiring(unittest.TestCase):
    """"One shared reader used by all commands" is about invocation, not agreement."""

    def test_each_consuming_partial_names_the_canonical_invocation(self):
        for partial in (MODEL_SELECTION, REPO_ROOT / "commands" / "shared" / "scope-parse.md"):
            with self.subTest(partial=partial.name):
                self.assertIn("scripts/lib/config.py", partial.read_text(encoding="utf-8"))


class TestRender(unittest.TestCase):
    """`render` is the write half of E0.5's grammar ownership (E0.8 / vibe-10).

    Round-tripping alone would prove only that the renderer and the reader share a convention —
    including a wrong one. So the expectations here are **golden**: exact bytes, written by hand.
    The round-trip tests that follow then prove those bytes mean what they are supposed to mean.
    """

    def test_scalars_render_exactly(self):
        self.assertEqual(
            config.render({"engine": "codex", "score_threshold": 42}),
            "---\nengine: codex\nscore_threshold: 42\n---\n")

    def test_key_order_follows_the_schema_not_the_input(self):
        # `engine` precedes `audit_depth` in SCHEMA but follows it alphabetically, so this pair
        # distinguishes schema order from sorted order. A pair that agrees under both — such as
        # engine/score_threshold — cannot, and a mutation test caught that version passing against
        # a renderer that sorted its keys.
        self.assertLess(list(config.SCHEMA).index("engine"),
                        list(config.SCHEMA).index("audit_depth"))
        self.assertGreater("engine", "audit_depth")
        self.assertEqual(config.render({"audit_depth": "full", "engine": "codex"}),
                         "---\nengine: codex\naudit_depth: full\n---\n")
        self.assertEqual(config.render({"audit_depth": "full", "engine": "codex"}),
                         config.render({"engine": "codex", "audit_depth": "full"}))

    def test_list_renders_as_a_block_sequence(self):
        self.assertEqual(config.render({"skip_patterns": ["a/**", "b/*.py"]}),
                         "---\nskip_patterns:\n  - a/**\n  - b/*.py\n---\n")

    def test_nested_map_renders_indented_with_sorted_keys(self):
        self.assertEqual(
            config.render({"gate": {"stop_review_gate": True, "model": "x"}}),
            "---\ngate:\n  model: x\n  stop_review_gate: true\n---\n")

    def test_multiline_string_renders_as_a_literal_block(self):
        self.assertEqual(config.render({"focus_instructions": "one\ntwo\n"}),
                         "---\nfocus_instructions: |\n  one\n  two\n---\n")

    def test_values_needing_quotes_get_them(self):
        # A bare `a: b` would parse as a nested key; `42` would decode as an int.
        self.assertEqual(config.render({"reviewer_model": "a: b"}),
                         '---\nreviewer_model: "a: b"\n---\n')
        self.assertEqual(config.render({"reviewer_model": "42"}),
                         '---\nreviewer_model: "42"\n---\n')
        self.assertEqual(config.render({"reviewer_model": "# not a comment"}),
                         '---\nreviewer_model: "# not a comment"\n---\n')

    def test_defaults_are_omitted_because_the_grammar_cannot_express_them(self):
        """`key:` with no child parses as absent, so `[]` and `{}` have no written form.

        Omitting a key at its default is therefore not an optimisation, it is the only
        representation the accepted subset has for one.
        """
        self.assertEqual(config.render({"skip_patterns": [], "model_overrides": {},
                                        "engine": "codex"}),
                         "---\nengine: codex\n---\n")

    def test_unknown_keys_are_refused(self):
        with self.assertRaises(config.ConfigValueError):
            config.render({"not_a_schema_key": 1})

    def test_invalid_values_are_refused(self):
        with self.assertRaises(config.ConfigValueError):
            config.render({"engine": "nonesuch"})
        with self.assertRaises(config.ConfigValueError):
            config.render({"score_threshold": 101})


class TestRenderRoundTrip(unittest.TestCase):
    """The golden bytes above are only correct if the reader agrees with them."""

    def _round_trip(self, mapping):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / config.CONFIG_FILENAME).write_text(config.render(mapping),
                                                             encoding="utf-8")
            return config.load(root)

    def test_every_rendered_value_reads_back_through_the_public_loader(self):
        mapping = {
            "engine": "codex",
            "reviewer_model": "a: b",
            "score_threshold": 42,
            "skip_patterns": ["a/**", "b/*.py"],
            "focus_instructions": "one\ntwo\n",
            "gate": {"stop_review_gate": True, "model": "x"},
        }
        loaded = self._round_trip(mapping)
        for key, want in mapping.items():
            with self.subTest(key=key):
                self.assertEqual(loaded[key], want)

    def test_rendered_output_parses_under_the_strict_grammar(self):
        text = config.render({"engine": "codex", "skip_patterns": ["*.py"],
                              "focus_instructions": "x\n"})
        self.assertEqual(config.parse_frontmatter(text)["skip_patterns"], ["*.py"])


if __name__ == "__main__":
    unittest.main()
