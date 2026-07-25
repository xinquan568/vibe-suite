#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Fail-closed validator for the audit-output finding contract (E0.2 / vibe-4).

**This is not a general JSON Schema implementation.** It implements the keyword subset
`schemas/audit-output.schema.json` uses, and it **halts on anything else**. A schema using `$ref`,
`oneOf`, `patternProperties`, or any other unimplemented keyword raises `UnsupportedSchemaError`
rather than being partially checked.

That behaviour is the point. A validator that silently skipped what it did not understand would
report success on documents nothing had examined — a contract everyone believed was enforced and
nothing was enforcing. Failing closed converts that invisible gap into a loud error, so extending the
schema and extending this checker are necessarily one change.

The tradeoff is friction: adding a keyword to the schema requires adding it here. `IMPLEMENTED_KEYWORDS`
and the invariant test in `tests/test_audit_output_schema.py` make that requirement mechanical rather
than a matter of remembering.

Usage:
    python3 scripts/validate_audit_output.py <report.json> [schema.json]
"""

import json
import sys
from pathlib import Path

#: Keywords this checker enforces. Anything outside this set (and METADATA_KEYWORDS) halts it.
IMPLEMENTED_KEYWORDS = frozenset({
    "type", "required", "properties", "additionalProperties",
    "enum", "minLength", "minItems", "maxItems", "items", "contains",
    "if", "then", "allOf",
})

#: Annotation keywords carrying no validation semantics. Accepted and ignored.
METADATA_KEYWORDS = frozenset({"$schema", "$id", "title", "description", "$comment", "examples"})

#: The JSON Schema vocabulary this checker knows *about* — used by the invariant test to tell a
#: schema keyword apart from an ordinary property name. A keyword here but not in
#: IMPLEMENTED_KEYWORDS is one we deliberately do not support.
ALL_JSON_SCHEMA_KEYWORDS = frozenset({
    "$schema", "$id", "$ref", "$defs", "$anchor", "$comment", "$dynamicRef", "$dynamicAnchor",
    "title", "description", "default", "examples", "deprecated", "readOnly", "writeOnly",
    "type", "enum", "const",
    "multipleOf", "maximum", "exclusiveMaximum", "minimum", "exclusiveMinimum",
    "maxLength", "minLength", "pattern", "format",
    "items", "prefixItems", "contains", "maxContains", "minContains",
    "maxItems", "minItems", "uniqueItems",
    "properties", "patternProperties", "additionalProperties", "propertyNames",
    "maxProperties", "minProperties", "required", "dependentRequired", "dependentSchemas",
    "allOf", "anyOf", "oneOf", "not", "if", "then", "else",  # allOf/if/then implemented
    "unevaluatedItems", "unevaluatedProperties", "contentEncoding", "contentMediaType",
})

_TYPES = {
    "object": dict, "array": list, "string": str,
    "integer": int, "number": (int, float), "boolean": bool, "null": type(None),
}


class ValidationError(Exception):
    """The instance does not satisfy the schema."""


class UnsupportedSchemaError(Exception):
    """The schema uses a construct this checker does not implement, or a malformed one.

    Raised rather than skipping, so an unenforceable schema can never look enforced.
    """


def _check_schema_supported(schema, path="$"):
    """Walk the schema and reject unknown or malformed constructs before validating anything."""
    if not isinstance(schema, dict):
        raise UnsupportedSchemaError(f"{path}: schema must be an object, got {type(schema).__name__}")

    for key, value in schema.items():
        if key in METADATA_KEYWORDS:
            continue
        if key not in IMPLEMENTED_KEYWORDS:
            raise UnsupportedSchemaError(
                f"{path}: keyword '{key}' is not implemented by this checker. "
                "Implement it or remove it from the schema — it cannot be silently skipped."
            )

        if key == "type":
            if not isinstance(value, str) or value not in _TYPES:
                raise UnsupportedSchemaError(f"{path}.type: expected one of {sorted(_TYPES)}, got {value!r}")
        elif key == "required":
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise UnsupportedSchemaError(f"{path}.required: expected an array of strings, got {value!r}")
        elif key == "enum":
            if not isinstance(value, list) or not value:
                raise UnsupportedSchemaError(f"{path}.enum: expected a non-empty array, got {value!r}")
        elif key in ("minLength", "minItems", "maxItems"):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise UnsupportedSchemaError(f"{path}.{key}: expected a non-negative integer, got {value!r}")
        elif key == "additionalProperties":
            if not isinstance(value, bool):
                raise UnsupportedSchemaError(f"{path}.additionalProperties: only booleans are implemented, got {value!r}")
        elif key == "properties":
            if not isinstance(value, dict):
                raise UnsupportedSchemaError(f"{path}.properties: expected an object, got {value!r}")
            for name, sub in value.items():
                _check_schema_supported(sub, f"{path}.properties.{name}")
        elif key in ("items", "contains", "if", "then"):
            _check_schema_supported(value, f"{path}.{key}")
        elif key == "allOf":
            if not isinstance(value, list) or not value:
                raise UnsupportedSchemaError(f"{path}.allOf: expected a non-empty array, got {value!r}")
            for index, sub_schema in enumerate(value):
                _check_schema_supported(sub_schema, f"{path}.allOf[{index}]")


def _matches(instance, schema):
    """Does the instance satisfy the schema? Used for `if` and `contains`, which select rather than assert."""
    try:
        _validate(instance, schema, "$")
        return True
    except ValidationError:
        return False


def _validate(instance, schema, path):
    if "type" in schema:
        expected = schema["type"]
        py = _TYPES[expected]
        # bool is a subclass of int; JSON Schema treats them as distinct.
        if expected in ("integer", "number") and isinstance(instance, bool):
            raise ValidationError(f"{path}: expected {expected}, got boolean")
        if not isinstance(instance, py):
            raise ValidationError(f"{path}: expected {expected}, got {type(instance).__name__}")

    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{path}: {instance!r} is not one of {schema['enum']}")

    if "minLength" in schema and isinstance(instance, str):
        if len(instance) < schema["minLength"]:
            raise ValidationError(f"{path}: shorter than minLength {schema['minLength']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise ValidationError(f"{path}: {len(instance)} items, minItems is {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise ValidationError(f"{path}: {len(instance)} items, maxItems is {schema['maxItems']}")
        if "items" in schema:
            for index, item in enumerate(instance):
                _validate(item, schema["items"], f"{path}[{index}]")
        if "contains" in schema:
            if not any(_matches(item, schema["contains"]) for item in instance):
                raise ValidationError(f"{path}: no item satisfies 'contains'")

    if isinstance(instance, dict):
        for name in schema.get("required", []):
            if name not in instance:
                raise ValidationError(f"{path}: required property '{name}' is missing")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for name in instance:
                if name not in properties:
                    raise ValidationError(f"{path}: property '{name}' is not permitted")
        for name, sub in properties.items():
            if name in instance:
                _validate(instance[name], sub, f"{path}.{name}")

    if "allOf" in schema:
        for sub_schema in schema["allOf"]:
            _validate(instance, sub_schema, path)

    if "if" in schema and "then" in schema:
        if _matches(instance, schema["if"]):
            _validate(instance, schema["then"], path)


def validate(instance, schema):
    """Validate `instance` against `schema`.

    Raises UnsupportedSchemaError if the schema uses anything unimplemented or malformed;
    ValidationError if the instance does not conform. Returns None on success.
    """
    _check_schema_supported(schema)
    _validate(instance, schema, "$")


def main(argv):
    if not 2 <= len(argv) <= 3:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    report_path = Path(argv[1])
    schema_path = Path(argv[2]) if len(argv) == 3 else (
        Path(__file__).resolve().parent.parent / "schemas" / "audit-output.schema.json"
    )
    with report_path.open(encoding="utf-8") as handle:
        report = json.load(handle)
    with schema_path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    try:
        validate(report, schema)
    except (ValidationError, UnsupportedSchemaError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"ok: {report_path} conforms to {schema_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
