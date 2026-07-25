#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Validate the audit-output finding contract (E0.2 / vibe-4).

Three concerns:

1. The schema exists, parses, and declares its draft.
2. The hand-written sample report validates against it — the issue's acceptance criterion.
3. The checker *rejects* what the contract forbids. This matters more than (2): a checker that
   accepted everything would pass a positive-only suite while validating nothing, so every
   constraint the schema expresses has a matching rejection case here.

Plus a keyword invariant. The checker fails closed, so the schema may use only keywords the checker
implements. That set is derived from the two artefacts themselves — the schema's own keys and the
checker's dispatch table — never from a list written here, because a hand-written list can only
catch keywords its author thought of.
"""

import copy
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "audit-output.schema.json"
SAMPLE_PATH = REPO_ROOT / "tests" / "fixtures" / "sample-report.json"
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _load(path):
    if not path.exists():
        raise AssertionError(f"not found: {path.relative_to(REPO_ROOT)}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _validator():
    import validate_audit_output as v
    return v


class TestSchemaDocument(unittest.TestCase):
    def test_schema_parses_and_declares_draft(self):
        schema = _load(SCHEMA_PATH)
        self.assertIn("$schema", schema)
        self.assertIn("2020-12", schema["$schema"])


class TestSampleValidates(unittest.TestCase):
    """The acceptance criterion: schema validates a hand-written sample report."""

    def test_sample_report_validates(self):
        v = _validator()
        v.validate(_load(SAMPLE_PATH), _load(SCHEMA_PATH))  # must not raise


class TestContractRejections(unittest.TestCase):
    """One rejection case per constraint the schema expresses."""

    def setUp(self):
        self.v = _validator()
        self.schema = _load(SCHEMA_PATH)
        self.sample = _load(SAMPLE_PATH)

    def _reject(self, report, because):
        with self.assertRaises(self.v.ValidationError, msg=f"should reject: {because}"):
            self.v.validate(report, self.schema)

    def _first_substantive(self, report):
        for finding in report["findings"]:
            if finding["severity"] != "[GOOD]":
                return finding
        raise AssertionError("sample has no substantive finding")

    def test_rejects_missing_required_field(self):
        r = copy.deepcopy(self.sample)
        del self._first_substantive(r)["observation"]
        self._reject(r, "required field absent")

    def test_rejects_severity_outside_enum(self):
        r = copy.deepcopy(self.sample)
        self._first_substantive(r)["severity"] = "[SEVERE]"
        self._reject(r, "severity not in enum")

    def test_rejects_unknown_property(self):
        r = copy.deepcopy(self.sample)
        self._first_substantive(r)["urgency"] = "high"
        self._reject(r, "additionalProperties false")

    def test_rejects_wrong_type(self):
        r = copy.deepcopy(self.sample)
        self._first_substantive(r)["observation"] = 42
        self._reject(r, "string field given an integer")

    def test_rejects_empty_string_for_minlength_field(self):
        r = copy.deepcopy(self.sample)
        self._first_substantive(r)["evidence"] = ""
        self._reject(r, "minLength 1 violated")

    def test_rejects_empty_findings_array(self):
        r = copy.deepcopy(self.sample)
        r["findings"] = []
        self._reject(r, "minItems 1 — zero findings must carry a [GOOD] sentinel")

    def test_rejects_malformed_array_item(self):
        r = copy.deepcopy(self.sample)
        r["findings"].append("not an object")
        self._reject(r, "items subschema violated")

    def test_rejects_non_good_finding_without_file(self):
        r = copy.deepcopy(self.sample)
        del self._first_substantive(r)["file"]
        self._reject(r, "file required unless severity is [GOOD]")

    def test_rejects_security_finding_without_exploit_scenario(self):
        r = copy.deepcopy(self.sample)
        for finding in r["findings"]:
            if "exploit_scenario" in finding:
                del finding["exploit_scenario"]
                break
        else:
            self.fail("sample has no security finding")
        self._reject(r, "exploit_scenario required for security findings")

    def test_rejects_edge_case_finding_without_risk_matrix(self):
        # Which variant is mandatory depends on the emitting agent, so an edge-cases report is a
        # separate document from the security sample — one agent cannot owe both.
        report = {
            "agent": "vibe-suite:edge-cases",
            "findings": [{
                "file": "scripts/lib/config.py:141",
                "observation": "Duplicate keys resolve silently to the last occurrence.",
                "severity": "[MEDIUM]",
                "evidence": "The parser assigns successively with no duplicate check.",
                "proposed_change": "Warn on repeated keys, naming both line numbers.",
                "tradeoff": "One extra pass over the raw lines.",
            }],
        }
        self._reject(report, "risk_matrix required for edge-case findings")

    def test_accepts_edge_case_finding_with_risk_matrix(self):
        v = _validator()
        v.validate({
            "agent": "vibe-suite:edge-cases",
            "findings": [{
                "file": "scripts/lib/config.py:141",
                "observation": "Duplicate keys resolve silently to the last occurrence.",
                "severity": "[MEDIUM]",
                "evidence": "The parser assigns successively with no duplicate check.",
                "proposed_change": "Warn on repeated keys, naming both line numbers.",
                "tradeoff": "One extra pass over the raw lines.",
                "risk_matrix": "Likelihood: medium. Impact: low — last value wins. Detection: none today.",
            }],
        }, self.schema)  # must not raise

    def test_rejects_good_sentinel_alongside_substantive_findings(self):
        r = copy.deepcopy(self.sample)
        r["findings"].append({
            "severity": "[GOOD]",
            "observation": "No issues found.",
            "evidence": "Reviewed all files in scope.",
            "proposed_change": "None.",
            "tradeoff": "None.",
        })
        self._reject(r, "[GOOD] is exclusive — it asserts there was nothing to report")

    def test_accepts_lone_good_sentinel_without_file(self):
        v = _validator()
        v.validate({
            "agent": "vibe-suite:recon",
            "findings": [{
                "severity": "[GOOD]",
                "observation": "No issues found.",
                "evidence": "Reviewed all files in scope.",
                "proposed_change": "None.",
                "tradeoff": "None.",
            }],
        }, self.schema)  # must not raise: file is optional for the sentinel


class TestAgentNameIsCanonical(unittest.TestCase):
    """The variant rules key on `agent`, so an unqualified name must not slip past them."""

    def setUp(self):
        self.v = _validator()
        self.schema = _load(SCHEMA_PATH)

    def test_rejects_unqualified_agent_name(self):
        report = {
            "agent": "security",  # bare, not vibe-suite:security
            "findings": [{
                "file": "a.py:1", "observation": "x", "severity": "[HIGH]",
                "evidence": "y", "proposed_change": "z", "tradeoff": "w",
            }],
        }
        with self.assertRaises(self.v.ValidationError):
            self.v.validate(report, self.schema)

    def test_rejects_unknown_agent_name(self):
        report = {
            "agent": "vibe-suite:invented",
            "findings": [{
                "file": "a.py:1", "observation": "x", "severity": "[LOW]",
                "evidence": "y", "proposed_change": "z", "tradeoff": "w",
            }],
        }
        with self.assertRaises(self.v.ValidationError):
            self.v.validate(report, self.schema)


class TestJsonSemantics(unittest.TestCase):
    """JSON Schema's data model differs from Python's in two ways that bite hand-rolled checkers."""

    def setUp(self):
        self.v = _validator()

    def test_integral_float_is_a_json_integer(self):
        self.v.validate(1.0, {"type": "integer"})  # must not raise: 1.0 is integral

    def test_non_integral_float_is_not_an_integer(self):
        with self.assertRaises(self.v.ValidationError):
            self.v.validate(1.5, {"type": "integer"})

    def test_boolean_is_not_an_integer(self):
        with self.assertRaises(self.v.ValidationError):
            self.v.validate(True, {"type": "integer"})

    def test_boolean_does_not_satisfy_numeric_enum(self):
        # Python says True == 1; JSON Schema does not.
        with self.assertRaises(self.v.ValidationError):
            self.v.validate(True, {"enum": [1]})

    def test_boolean_inside_array_does_not_match_numeric_array(self):
        # Python: [True] == [1]. JSON Schema: they are different values.
        with self.assertRaises(self.v.ValidationError):
            self.v.validate([True], {"enum": [[1]]})

    def test_boolean_inside_object_does_not_match_numeric_object(self):
        with self.assertRaises(self.v.ValidationError):
            self.v.validate({"x": True}, {"enum": [{"x": 1}]})

    def test_matching_nested_value_still_accepted(self):
        self.v.validate([1], {"enum": [[1]]})          # must not raise
        self.v.validate({"x": True}, {"enum": [{"x": True}]})

    def test_number_accepts_boolean_never(self):
        with self.assertRaises(self.v.ValidationError):
            self.v.validate(False, {"type": "number"})


class TestCheckerFailsClosed(unittest.TestCase):
    """The checker must halt on anything it does not implement, never skip it."""

    def setUp(self):
        self.v = _validator()

    def test_raises_on_unimplemented_keyword(self):
        with self.assertRaises(self.v.UnsupportedSchemaError):
            self.v.validate({}, {"type": "object", "patternProperties": {"^x": {}}})

    def test_raises_on_malformed_type(self):
        with self.assertRaises(self.v.UnsupportedSchemaError):
            self.v.validate({}, {"type": 123})

    def test_raises_on_malformed_required(self):
        with self.assertRaises(self.v.UnsupportedSchemaError):
            self.v.validate({}, {"type": "object", "required": "file"})

    def test_raises_on_malformed_enum(self):
        with self.assertRaises(self.v.UnsupportedSchemaError):
            self.v.validate("x", {"enum": {}})


class TestKeywordInvariant(unittest.TestCase):
    """Every keyword the schema uses must be one the checker implements.

    Both sets are derived from the artefacts — the schema's keys and the checker's declared
    dispatch set — so a keyword neither author anticipated still gets compared. A hand-written
    list here would only ever check what its author remembered.
    """

    def test_schema_uses_only_implemented_keywords(self):
        v = _validator()
        schema = _load(SCHEMA_PATH)

        def keys_of(node):
            found = set()
            if isinstance(node, dict):
                for key, value in node.items():
                    found.add(key)
                    found |= keys_of(value)
            elif isinstance(node, list):
                for item in node:
                    found |= keys_of(item)
            return found

        known = v.IMPLEMENTED_KEYWORDS | v.METADATA_KEYWORDS
        used = {k for k in keys_of(schema) if k in v.ALL_JSON_SCHEMA_KEYWORDS}
        unhandled = used - known
        self.assertEqual(
            unhandled, set(),
            f"schema uses keyword(s) the checker does not handle: {sorted(unhandled)}. "
            "The checker fails closed, so it would halt on this schema.",
        )


if __name__ == "__main__":
    unittest.main()
