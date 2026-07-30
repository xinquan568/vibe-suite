# SPDX-License-Identifier: ISC
"""E3.4 (vibe-29) acceptance: /vibe-suite:check — cross-component consistency.

The engine (scripts/check_engine.py) owns the mechanical classes AND the composition; the
checker agent owns the two judgment classes by authored contract. Oracles are hand-derived
(the worksheet in tests/fixtures/check/broken/README.md predates the engine).

Engine CLI: --root <dir> [--config <file>] [--judgment <file>]; artifacts self-discovered
under the root (classify-routed); exit 0 scored, 2 refusal (bad root, <2 artifacts,
malformed config, malformed registry, malformed/unreadable/unknown-class judgment).
Output JSON: {"verdict": "CLEAN"|"<N> issues", "issues": [...], "checked": {...}} —
goldens compare the COMPLETE object. Composition: issues = mechanical + judgment; CLEAN
iff empty.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_skill_library import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE = REPO_ROOT / "scripts" / "check_engine.py"
BROKEN = REPO_ROOT / "tests" / "fixtures" / "check" / "broken"
CLEAN = REPO_ROOT / "tests" / "fixtures" / "check" / "clean"
ORACLE_MECH = BROKEN / "expected-mechanical.json"
ORACLE_COMPOSED = BROKEN / "expected-composed.json"
JUDGMENT = BROKEN / "judgment-input.json"
COMMAND = REPO_ROOT / "commands" / "check.md"
CHECKER = REPO_ROOT / "agents" / "checker.md"
PARTIAL = REPO_ROOT / "commands" / "shared" / "plugin-discover.md"

#: F4.3's four reportable reference-integrity directions (the constant half of the matrix).
F43_DIRECTIONS = {"command-partial", "agent-skills", "hook-script", "claude-md-listing"}
#: plugin-discover.md's map edges, parsed live in the matrix test.
PARTIAL_EDGES = {"command-agent", "command-partial", "agent-skill", "hook-script"}
#: The partial names the skill edge in the singular, F4.3 in the plural — one edge, two
#: spellings, normalized before the intersection is taken.
EDGE_NORMALIZE = {"agent-skill": "agent-skills"}

CLEAN_CHECKED = {"agent": 1, "claude-md": 1, "command": 1, "hook-config": 0,
                 "partial": 0, "script": 0, "skill": 1}


def run_engine(root, extra=()):
    return subprocess.run(
        [sys.executable, str(ENGINE), "--root", str(root), *extra],
        capture_output=True,
    )


def config_variant(tmp, body):
    path = Path(tmp) / "variant.md"
    path.write_text(f"---\n{body}---\n", encoding="utf-8")
    return path


class DeliverablesShip(unittest.TestCase):
    def test_engine_ships_with_isc(self):
        head = ENGINE.read_text(encoding="utf-8").splitlines()[:3]
        self.assertTrue(any("SPDX-License-Identifier: ISC" in l for l in head))

    def test_agent_and_command_contracts(self):
        c = parse_frontmatter(CHECKER.read_text(encoding="utf-8"))
        self.assertEqual(c["model"], "sonnet")
        self.assertEqual(sorted(t.strip() for t in c["tools"].split(",")),
                         ["Bash", "Glob", "Read"])
        parse_frontmatter(COMMAND.read_text(encoding="utf-8"),
                          required=("description", "argument-hint"))

    def test_registered_in_manifest(self):
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("./commands/check.md", manifest["commands"])
        self.assertIn("./agents/checker.md", manifest["agents"])

    def test_checker_contract_carries_both_judgment_procedures(self):
        body = CHECKER.read_text(encoding="utf-8")
        self.assertIn("pairwise obligation comparison", body.lower())
        self.assertIn("clustering", body.lower())
        # the explicit clean conditions (no-finding conditions) must be stated
        self.assertRegex(body, r"(?i)zero obligation pairs")
        self.assertRegex(body, r"(?i)one name per concept")
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/check_engine.py"', body)

    def test_command_text_contract(self):
        body = COMMAND.read_text(encoding="utf-8")
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/check_engine.py"', body)
        self.assertRegex(body, r"(?i)at least two.*artifacts|>=2 artifacts")
        self.assertIn("CLEAN", body)
        for excluded in ("manifest-vs-disk", "frontmatter presence"):
            self.assertIn(excluded, body, "the E3.5 boundary must be stated")


class MechanicalGolden(unittest.TestCase):
    def test_whole_object_golden(self):
        proc = run_engine(BROKEN)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        got = json.loads(proc.stdout.decode())
        want = json.loads(ORACLE_MECH.read_text(encoding="utf-8"))
        self.assertEqual(got, want)

    def test_per_class_catch(self):
        got = json.loads(run_engine(BROKEN).stdout.decode())
        classes = [i["class"] for i in got["issues"]]
        self.assertEqual(classes.count("reference-integrity"), 5)
        self.assertIn("orphan", classes)
        self.assertIn("r51-drift", classes)
        directions = {i.get("direction") for i in got["issues"] if "direction" in i}
        self.assertEqual(directions, F43_DIRECTIONS)

    def test_hook_target_extracted_exactly(self):
        # The dangling target carries no quote, backslash, or trailing argument, and the
        # resolving quoted+argument hook keeps its script off the orphan list.
        got = json.loads(run_engine(BROKEN).stdout.decode())
        hook_targets = [i["target"] for i in got["issues"]
                        if i.get("direction") == "hook-script"]
        self.assertEqual(hook_targets, ["scripts/missing-hook.sh"])
        orphans = [i["source"] for i in got["issues"] if i["class"] == "orphan"]
        self.assertNotIn("scripts/present-hook.mjs", orphans)

    def test_verdict_n_fidelity(self):
        got = json.loads(run_engine(BROKEN).stdout.decode())
        self.assertEqual(got["verdict"], f"{len(got['issues'])} issues")

    def test_determinism_three_runs(self):
        outs = []
        for _ in range(3):
            proc = run_engine(BROKEN)
            self.assertEqual(proc.returncode, 0)
            outs.append(proc.stdout)
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[1], outs[2])


class R51Preconditions(unittest.TestCase):
    def _classes(self, extra):
        proc = run_engine(BROKEN, extra=extra)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        got = json.loads(proc.stdout.decode())
        return got, [i["class"] for i in got["issues"]]

    def test_disabled_default_excludes_the_class(self):
        # --config pointing at a missing file → defaults; R51 is opt-in, disabled default.
        got, classes = self._classes(("--config", str(BROKEN / "no-such-config.md")))
        self.assertNotIn("r51-drift", classes)
        self.assertEqual(got["verdict"], "6 issues")

    def test_disabled_explicit_survives_other_enabled_rules(self):
        # R51 must be armed by ITS OWN enabled leaf, never another rule's.
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config_variant(
                tmp,
                "rule_overrides:\n"
                "  R51:\n    enabled: false\n    vocabulary_skill: skills/util\n"
                "  R07:\n    enabled: true\n")
            got, classes = self._classes(("--config", str(cfg)))
        self.assertNotIn("r51-drift", classes)
        self.assertEqual(got["verdict"], "6 issues")

    def test_enabled_without_vocabulary_skill_cannot_fire(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config_variant(tmp, "rule_overrides:\n  R51:\n    enabled: true\n")
            got, classes = self._classes(("--config", str(cfg)))
        self.assertNotIn("r51-drift", classes)
        self.assertEqual(got["verdict"], "6 issues")

    def test_enabled_without_registry_cannot_fire(self):
        # skills/orphaned exists but ships no registry.yaml sidecar.
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config_variant(
                tmp,
                "rule_overrides:\n  R51:\n    enabled: true\n"
                "    vocabulary_skill: skills/orphaned\n")
            got, classes = self._classes(("--config", str(cfg)))
        self.assertNotIn("r51-drift", classes)
        self.assertEqual(got["verdict"], "6 issues")

    def test_malformed_config_refused(self):
        # enabled takes a bool; a quoted string is a config error, and the posture is
        # fail-closed (exit 2), never a silent default.
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config_variant(
                tmp, 'rule_overrides:\n  R51:\n    enabled: "true"\n')
            proc = run_engine(BROKEN, extra=("--config", str(cfg)))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("config", proc.stderr.decode())

    def test_scope_and_deferred_exemptions_pinned_by_golden(self):
        # helper.md's "utilize" is outside the verb's commands/** scope; go.md's "triage"
        # is deferred-pending-warrant. Neither may appear as an r51 source/why.
        got = json.loads(run_engine(BROKEN).stdout.decode())
        r51 = [i for i in got["issues"] if i["class"] == "r51-drift"]
        self.assertEqual([i["source"] for i in r51], ["commands/go.md"])
        self.assertNotIn("triage", json.dumps(r51))


#: A minimal registry carrying every one of the documented schema's six top-level keys.
REGISTRY_OK = """\
scopes:
  - id: s
    description: scope
    paths:
      - commands/**
cross_scope_homonyms:
  verbs: []
verbs:
  s: []
deferred_pending_warrant: []
rejected_by_higher_principle: []
nouns:
  artifact_class: []
  output_class: []
  role_nouns: []
"""


def registry_root(tmp, registry_text):
    """A tmp root with R51 armed at skills/vocab and the given registry text."""
    root = Path(tmp)
    (root / ".vibe-suite.md").write_text(
        "---\nrule_overrides:\n  R51:\n    enabled: true\n"
        "    vocabulary_skill: skills/vocab\n---\n", encoding="utf-8")
    for name in ("vocab", "extra"):
        d = root / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: fixture.\n---\n# {name}\n",
            encoding="utf-8")
    (root / "skills" / "vocab" / "registry.yaml").write_text(
        registry_text, encoding="utf-8")
    return root


class RegistryFailClosed(unittest.TestCase):
    def _run(self, registry_text):
        with tempfile.TemporaryDirectory() as tmp:
            return run_engine(registry_root(tmp, registry_text))

    def test_documented_schema_accepted(self):
        proc = self._run(REGISTRY_OK)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_missing_top_level_key_refused(self):
        proc = self._run(REGISTRY_OK.replace(
            "nouns:\n  artifact_class: []\n  output_class: []\n  role_nouns: []\n", ""))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("registry", proc.stderr.decode())

    def test_unknown_nested_key_refused(self):
        proc = self._run(REGISTRY_OK.replace(
            "verbs:\n  s: []\n",
            "verbs:\n  s:\n    - canonical: use\n      deprecated: []\n"
            "      output: none\n      judgment: false\n      bogus: extra\n"))
        self.assertEqual(proc.returncode, 2)

    def test_missing_required_verb_field_refused(self):
        proc = self._run(REGISTRY_OK.replace(
            "verbs:\n  s: []\n",
            "verbs:\n  s:\n    - canonical: use\n      deprecated: []\n"
            "      output: none\n"))
        self.assertEqual(proc.returncode, 2)

    def test_malformed_section_scalar_refused(self):
        proc = self._run(REGISTRY_OK.replace(
            "deferred_pending_warrant: []\n", "deferred_pending_warrant: nonsense\n"))
        self.assertEqual(proc.returncode, 2)

    def test_undeclared_verbs_scope_refused(self):
        proc = self._run(REGISTRY_OK.replace("verbs:\n  s: []\n", "verbs:\n  t: []\n"))
        self.assertEqual(proc.returncode, 2)

    def test_null_leaf_refused(self):
        # A YAML null is not a string; a required string leaf must refuse, not coerce.
        proc = self._run(REGISTRY_OK.replace(
            "verbs:\n  s: []\n",
            "verbs:\n  s:\n    - canonical: null\n      deprecated: []\n"
            "      output: none\n      judgment: false\n"))
        self.assertEqual(proc.returncode, 2)

    def test_flow_constructs_refused(self):
        # Flow mappings and non-empty flow lists are outside the accepted grammar.
        proc = self._run(REGISTRY_OK.replace(
            "    paths:\n      - commands/**\n", "    paths: [commands/**]\n"))
        self.assertEqual(proc.returncode, 2)
        proc = self._run(REGISTRY_OK.replace(
            "verbs:\n  s: []\n",
            "verbs:\n  s:\n    - canonical: use\n      deprecated: []\n"
            "      output: none\n      judgment: false\n      notes: {oops: 1}\n"))
        self.assertEqual(proc.returncode, 2)

    def test_unterminated_quoted_scalar_refused(self):
        proc = self._run(REGISTRY_OK.replace(
            "    description: scope\n", '    description: "unterminated\n'))
        self.assertEqual(proc.returncode, 2)

    def test_non_string_homonym_members_refused(self):
        for member in ("null", "1.5"):
            proc = self._run(REGISTRY_OK.replace(
                "cross_scope_homonyms:\n  verbs: []\n",
                f"cross_scope_homonyms:\n  verbs:\n    - {member}\n"))
            self.assertEqual(proc.returncode, 2, f"member {member!r} must refuse")

    def _description(self, value):
        return self._run(REGISTRY_OK.replace(
            "    description: scope\n", f"    description: {value}\n"))

    def test_keyword_lookalikes_refused(self):
        # YAML's case-variant null/bool spellings are typed forms, never silent strings.
        for lookalike in ("Null", "NULL", "TRUE", "Yes", "off", "y", "Y", "n", "N"):
            self.assertEqual(self._description(lookalike).returncode, 2, lookalike)

    def test_numeric_lookalikes_refused(self):
        # Exponents, signs, bare dots, inf/nan, and radix forms are ambiguous unquoted.
        for form in ("1e3", "-2E-4", "+2", ".5", "1.", ".inf", ".NaN", "0x1F", "0.0.1"):
            self.assertEqual(self._description(form).returncode, 2, form)

    def test_quote_syntax_refusals(self):
        # Escaped terminal double quote, doubled terminal single quote, trailing junk,
        # and unsupported escapes are all unterminated/off-grammar, not accepted strings.
        for value in ('"foo\\"', "'foo''", '"foo" bar', '"a\\qb"'):
            self.assertEqual(self._description(value).returncode, 2, value)

    def test_inline_comments_stripped_before_decode(self):
        # A YAML inline comment is not part of the value: comment-suffixed ambiguous
        # scalars refuse, comment-suffixed plain strings parse, and a # inside quotes
        # is content, not a comment.
        for value in ("y # note", "NULL # note", "1e3 # note"):
            self.assertEqual(self._description(value).returncode, 2, value)
        for value in ("scope # trailing note", '"a # not a comment"'):
            proc = self._description(value)
            self.assertEqual(proc.returncode, 0, f"{value}: {proc.stderr.decode()}")

    def test_ambiguous_mapping_keys_refused(self):
        # Keys get the same discipline as values: even with the scope id declared (as a
        # quoted string), an UNQUOTED YAML keyword spelling is ambiguous as a dynamic
        # verbs key; quoting is the explicit string-key spelling.
        for key in ("y", "NULL", "on"):
            registry = REGISTRY_OK.replace("  - id: s\n", f'  - id: "{key}"\n').replace(
                "verbs:\n  s: []\n", f"verbs:\n  {key}: []\n")
            self.assertEqual(self._run(registry).returncode, 2, key)

    def test_quoted_mapping_key_accepted(self):
        registry = REGISTRY_OK.replace("  - id: s\n", '  - id: "y"\n').replace(
            "verbs:\n  s: []\n", 'verbs:\n  "y": []\n')
        proc = self._run(registry)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_list_item_mapping_heads_disambiguated(self):
        # A list item containing ':' + whitespace is YAML mapping syntax, never a silent
        # string: TAB-separated heads and phrase keys refuse inside string lists; a
        # colon-space STRING item takes the quoted spelling.
        proc = self._run(REGISTRY_OK.replace(
            "      - commands/**\n", "      - commands:\tfoo\n"))
        self.assertEqual(proc.returncode, 2, "tab-separated mapping head")
        proc = self._run(REGISTRY_OK.replace(
            "      - commands/**\n", "      - some phrase: x\n"))
        self.assertEqual(proc.returncode, 2, "phrase mapping head")
        proc = self._run(REGISTRY_OK.replace(
            "      - commands/**\n", '      - "with: colon"\n'))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        proc = self._run(REGISTRY_OK.replace(
            "      - commands/**\n", '      - "x" y\n'))
        self.assertEqual(proc.returncode, 2, "trailing junk after quoted item")

    def test_quoted_list_head_key_accepted(self):
        # Quoted keys work on the list-head surface too, symmetrically with map keys.
        registry = REGISTRY_OK.replace('  - id: s\n', '  - "id": "y"\n').replace(
            "verbs:\n  s: []\n", 'verbs:\n  "y": []\n')
        proc = self._run(registry)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_colon_whitespace_in_unquoted_scalars_refused(self):
        # An unquoted scalar containing ':'+whitespace (or ending ':') is YAML mapping
        # syntax in block context, never a plain string — on every surface. Colon WITHOUT
        # following whitespace stays a plain scalar (YAML agrees); quoting is the
        # spelling for genuine colon-space strings.
        proc = self._run(REGISTRY_OK.replace(
            "      - commands/**\n", "      - foo:bar: baz\n"))
        self.assertEqual(proc.returncode, 2, "multi-colon mapping-shaped list item")
        proc = self._run(REGISTRY_OK.replace(
            "cross_scope_homonyms:\n  verbs: []\n",
            "cross_scope_homonyms:\n  foo:bar: baz\n"))
        self.assertEqual(proc.returncode, 2, "multi-colon mapping-shaped map line")
        self.assertEqual(self._description("has: colon").returncode, 2,
                         "nested mapping in a value")
        self.assertEqual(self._description("dangling:").returncode, 2,
                         "trailing-colon value")
        self.assertEqual(self._description("a:b").returncode, 0,
                         "colon without whitespace is a plain scalar")
        self.assertEqual(self._description('"has: colon"').returncode, 0,
                         "quoted colon-space string")

    def test_yaml_indicator_leading_scalars_refused(self):
        # The complex-key indicator '?' followed by whitespace is mapping syntax
        # ({key: null}), and the flow/reserved indicators , ] } % @ ` cannot begin a
        # YAML plain scalar at all — none may pass as a silent string.
        proc = self._run(REGISTRY_OK.replace(
            "      - commands/**\n", "      - ? commands/**\n"))
        self.assertEqual(proc.returncode, 2, "complex-key list item")
        self.assertEqual(self._description("? x").returncode, 2, "complex-key value")
        for lead in (", x", "] x", "} x", "% x", "@ x", "` x"):
            self.assertEqual(self._description(lead).returncode, 2, lead)
        # '?' and ':' followed by a NON-space are legal YAML plain scalars.
        self.assertEqual(self._description("?x").returncode, 0)
        self.assertEqual(self._description(":x").returncode, 0)
        self.assertEqual(self._description('"? quoted"').returncode, 0)

    def test_colon_without_whitespace_is_not_a_map_separator(self):
        # YAML's mapping separator is ':'+whitespace (or line end). description:scope is
        # malformed YAML, not a {description: scope} entry — it must refuse, while a TAB
        # separator and end-of-line ':' remain valid separators.
        proc = self._run(REGISTRY_OK.replace(
            "    description: scope\n", "    description:scope\n"))
        self.assertEqual(proc.returncode, 2, "colon without whitespace at map level")
        proc = self._run(REGISTRY_OK.replace(
            "    description: scope\n", "    description:\tscope\n"))
        self.assertEqual(proc.returncode, 2, "TAB separator (PyYAML ScannerError)")

    def test_tab_in_indentation_refused(self):
        # YAML forbids tabs in indentation; a TAB hiding after (or before) the indent
        # spaces must refuse, never be silently stripped into a valid line.
        proc = self._run(REGISTRY_OK.replace("  - id: s\n", "  \t- id: s\n"))
        self.assertEqual(proc.returncode, 2, "tab after indent spaces")
        proc = self._run(REGISTRY_OK.replace("verbs:\n  s: []\n", "verbs:\n\ts: []\n"))
        self.assertEqual(proc.returncode, 2, "tab as indentation")

    def test_bare_equals_value_special_refused(self):
        # YAML 1.1 resolves a bare '=' as tag:yaml.org,2002:value, not a string;
        # '=x' is an ordinary plain scalar and the quoted spelling round-trips.
        self.assertEqual(self._description("=").returncode, 2)
        self.assertEqual(self._description("=x").returncode, 0)
        self.assertEqual(self._description('"="').returncode, 0)

    def test_forbidden_stream_characters_refused(self):
        # YAML's reader forbids C0/C1 controls (beyond tab/LF/CR), DEL, and we refuse
        # the exotic line breaks (NEL, LS, PS) as outside the accepted subset — a
        # form feed must never be silently stripped into a valid line.
        for ch in ("\x0c", "\x07", "\x00", "\x85", "\u2028", "\x7f"):
            proc = self._run(REGISTRY_OK.replace(
                "    description: scope\n", f"    description: {ch}scope\n"))
            self.assertEqual(proc.returncode, 2, repr(ch))

    def test_non_ascii_whitespace_is_content(self):
        # NBSP is Python-whitespace but YAML content: it must survive into the value,
        # not be stripped — the engine and YAML agree the leaf is a plain string.
        proc = self._run(REGISTRY_OK.replace(
            "    description: scope\n", "    description: \xa0scope\n"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_invalid_utf8_registry_refused(self):
        # Undecodable bytes are a reader-level refusal (YAML raises), never a silent
        # U+FFFD substitution into an accepted document.
        with tempfile.TemporaryDirectory() as tmp:
            root = registry_root(tmp, REGISTRY_OK)
            reg = Path(root) / "skills" / "vocab" / "registry.yaml"
            reg.write_bytes(REGISTRY_OK.encode("utf-8").replace(
                b"description: scope", b"description: sc\xffpe"))
            proc = run_engine(root)
        self.assertEqual(proc.returncode, 2)

    def test_invalid_utf8_config_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "variant.md"
            cfg.write_bytes(b"---\nfocus_instructions: sc\xffpe\n---\n")
            proc = run_engine(BROKEN, extra=("--config", str(cfg)))
        self.assertEqual(proc.returncode, 2)

    def test_tabs_outside_quotes_refused(self):
        # PyYAML rejects tabs in block structure (ScannerError); the accepted subset is
        # spaces-only outside quoted scalars — a literal TAB inside quotes stays content.
        proc = self._run(REGISTRY_OK.replace(
            "    description: scope\n", "    description: scope\t\n"))
        self.assertEqual(proc.returncode, 2, "trailing TAB")
        proc = self._run(REGISTRY_OK.replace(
            "    description: scope\n", '    description: "a\tb"\n'))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_whitespace_only_lines_with_tabs_refused(self):
        # A TAB on a whitespace-only line (bare, or left behind by comment stripping)
        # is still a tab in block structure — PyYAML raises ScannerError; the blank-line
        # skip must not bypass the tab guard.
        proc = self._run(REGISTRY_OK.replace("verbs:\n", "verbs:\n\t\n", 1))
        self.assertEqual(proc.returncode, 2, "TAB-only line")
        proc = self._run(REGISTRY_OK.replace("verbs:\n", "verbs:\n  \t# note\n", 1))
        self.assertEqual(proc.returncode, 2, "spaces+TAB before a comment")

    def test_crlf_registry_accepted(self):
        # CRLF line endings are translated by universal-newline decoding before any
        # guard runs — a CRLF registry is the same document.
        with tempfile.TemporaryDirectory() as tmp:
            root = registry_root(tmp, REGISTRY_OK)
            reg = Path(root) / "skills" / "vocab" / "registry.yaml"
            reg.write_bytes(REGISTRY_OK.replace("\n", "\r\n").encode("utf-8"))
            proc = run_engine(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_mid_scalar_quotes_are_content(self):
        # A quote glued to preceding content is plain-scalar CONTENT per YAML — it must
        # not open quote mode: the comment after foo' still strips, and a tab after
        # foo' is still a bare tab (PyYAML ScannerError).
        proc = self._run(REGISTRY_OK.replace(
            "    description: scope\n", "    description: foo' # note\n"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        proc = self._run(REGISTRY_OK.replace(
            "    description: scope\n", "    description: foo'\tbar\n"))
        self.assertEqual(proc.returncode, 2, "tab hidden by a mid-scalar quote")

    def test_glued_dash_is_not_a_marker(self):
        # 'foo- ' is plain-scalar content — only the line's leading '- ' is a list
        # marker. The quote after a glued dash is content: the comment still strips
        # (PyYAML decodes "foo- 'bar") and a tab inside it is still a bare tab.
        proc = self._run(REGISTRY_OK.replace(
            "    description: scope\n", "    description: foo- 'bar # note'\n"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        proc = self._run(REGISTRY_OK.replace(
            "    description: scope\n", "    description: foo- 'bar\tbaz'\n"))
        self.assertEqual(proc.returncode, 2, "tab hidden after a glued dash")

    def test_scan_semantics_whitebox(self):
        # The scan helpers themselves: comment stripping and decoded values must match
        # YAML's reading (PyYAML decodes description as "foo'" in the glued case).
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        try:
            import check_engine
        finally:
            sys.path.pop(0)
        strip = check_engine._reg_strip_comment
        self.assertEqual(strip("    description: foo' # note"),
                         "    description: foo' ")
        self.assertEqual(strip("    description: 'a # b' # c"),
                         "    description: 'a # b' ")
        self.assertEqual(strip("    key: a#b"), "    key: a#b")
        self.assertEqual(strip("    description: foo- 'bar # note'"),
                         "    description: foo- 'bar ")
        self.assertEqual(strip("  - 'a # b' # c"), "  - 'a # b' ")

    def test_quoted_strings_accepted(self):
        # Quoting is the documented spelling for anything exotic: keywords, numbers,
        # colons, and escaped quotes all parse to plain strings.
        for value in ('"TRUE"', '"1e3"', '"with: colon"', "'it''s a scope'",
                      '"a \\"quoted\\" word"'):
            proc = self._description(value)
            self.assertEqual(proc.returncode, 0, f"{value}: {proc.stderr.decode()}")


class Composition(unittest.TestCase):
    def test_whole_object_composed_golden(self):
        proc = run_engine(BROKEN, extra=("--judgment", str(JUDGMENT)))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        got = json.loads(proc.stdout.decode())
        want = json.loads(ORACLE_COMPOSED.read_text(encoding="utf-8"))
        self.assertEqual(got, want)

    def test_composition_rule(self):
        mech = json.loads(run_engine(BROKEN).stdout.decode())
        composed = json.loads(
            run_engine(BROKEN, extra=("--judgment", str(JUDGMENT))).stdout.decode())
        judgment = json.loads(JUDGMENT.read_text(encoding="utf-8"))
        self.assertEqual(len(composed["issues"]), len(mech["issues"]) + len(judgment))

    def test_clean_fixture_is_clean_both_modes(self):
        want = {"verdict": "CLEAN", "issues": [], "checked": CLEAN_CHECKED}
        self.assertEqual(json.loads(run_engine(CLEAN).stdout.decode()), want)
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.json"
            empty.write_text("[]", encoding="utf-8")
            proc = run_engine(CLEAN, extra=("--judgment", str(empty)))
        self.assertEqual(json.loads(proc.stdout.decode()), want)


class Refusals(unittest.TestCase):
    def _refused(self, judgment_text):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(judgment_text, encoding="utf-8")
            proc = run_engine(BROKEN, extra=("--judgment", str(bad)))
        self.assertEqual(proc.returncode, 2, proc.stdout.decode())

    def test_unknown_judgment_class_refused(self):
        self._refused('[{"class": "invented-class", "detail": "x", "sources": []}]')

    def test_non_object_judgment_entry_refused(self):
        self._refused('["not-an-object"]')

    def test_judgment_missing_detail_refused(self):
        self._refused('[{"class": "terminology-drift", "sources": []}]')

    def test_judgment_sources_not_a_string_list_refused(self):
        self._refused('[{"class": "behavioral-contradiction", "detail": "d", '
                      '"sources": "not-a-list"}]')
        self._refused('[{"class": "behavioral-contradiction", "detail": "d", '
                      '"sources": [1]}]')

    @unittest.skipIf(os.geteuid() == 0, "permission bits do not bind root")
    def test_unreadable_judgment_file_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("[]", encoding="utf-8")
            bad.chmod(0)
            try:
                proc = run_engine(BROKEN, extra=("--judgment", str(bad)))
            finally:
                bad.chmod(0o600)
        self.assertEqual(proc.returncode, 2)

    def test_fewer_than_two_artifacts_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "skills" / "solo"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                "---\nname: solo\ndescription: one artifact only.\n---\n# solo\n",
                encoding="utf-8")
            proc = run_engine(tmp)
            self.assertEqual(proc.returncode, 2)
            self.assertIn(">=2 artifacts", proc.stderr.decode())

    def test_bad_root_refused(self):
        proc = run_engine(REPO_ROOT / "no-such-dir")
        self.assertEqual(proc.returncode, 2)


class DirectionMatrix(unittest.TestCase):
    def test_three_set_matrix(self):
        # Set A: the partial's map edges (parsed live from its reference-direction list).
        text = PARTIAL.read_text(encoding="utf-8")
        a = set()
        for pair, token in (("command", "agent"), ("command", "partial"),
                            ("agent", "skill"), ("hook", "script")):
            # the partial phrases the partial edge as "command → shared partial"
            self.assertRegex(text.lower(),
                             pair + r"\s*(→|->|to)\s*(shared\s+)?" + token,
                             f"the partial must still document the {pair}->{token} edge")
            a.add(f"{pair}-{token}")
        self.assertEqual(a, PARTIAL_EDGES)
        # Set B: F4.3's reportable directions (constant). The intersection, after
        # normalizing the two spellings of the skill edge, is exactly three edges;
        # claude-md-listing is the direction the partial lacks.
        a_normalized = {EDGE_NORMALIZE.get(edge, edge) for edge in a}
        self.assertEqual(a_normalized & F43_DIRECTIONS,
                         {"command-partial", "agent-skills", "hook-script"})
        self.assertEqual(F43_DIRECTIONS - a_normalized, {"claude-md-listing"})
        # command-agent is orphan-input only: the engine must not report it as a direction.
        self.assertEqual(a_normalized - F43_DIRECTIONS, {"command-agent"})
        got = json.loads(run_engine(BROKEN).stdout.decode())
        self.assertNotIn("command-agent",
                         {i.get("direction") for i in got["issues"] if "direction" in i})


if __name__ == "__main__":
    unittest.main()
