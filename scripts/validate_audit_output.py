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

import ipaddress
import json
import re
import sys
from pathlib import Path

#: Keywords this checker enforces. Anything outside this set (and METADATA_KEYWORDS) halts it.
IMPLEMENTED_KEYWORDS = frozenset({
    "type", "required", "properties", "additionalProperties",
    "enum", "minLength", "minItems", "maxItems", "items", "contains",
    "if", "then", "allOf",
    # Added for the manifest input contract (vibe-130). The contract needs all five, and this
    # checker halts on any keyword it does not implement — so without them a conformant schema
    # would be refused outright rather than under-enforced.
    "const", "minimum", "maximum", "pattern", "format",
})

#: `format` values this checker understands. An unknown format is a hard error rather than an
#: ignored annotation: JSON Schema permits ignoring `format`, but a checker that silently skipped
#: it would report success on a document it never examined, which is the posture this file exists
#: to avoid. Validation is **structural only** — resolving a URI would make the result depend on
#: the network.
IMPLEMENTED_FORMATS = frozenset({"uri"})

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

#: RFC 3986 Appendix A, transcribed. Each name below is the RFC's own production name, so a reader
#: can compare this block against the specification rather than against a list of cases. Four rounds
#: of authored rules were each correct for the cases in hand and wrong for the next set; a grammar is
#: finite and can simply be written down.
#:
#: **Every match uses `fullmatch`.** `re.match(..., "$")` succeeds before a terminal newline, so
#: `http://x/\n` validated — a defect no case list found because nobody thinks to try a newline.
#: Anchoring at the production level closes the class rather than the instance.
#:
#: **Syntactic only, and offline.** Resolving a URI would make the verdict depend on the network,
#: which is the opposite of fail-closed. IPv6 is delegated to `ipaddress`: three hand-written versions
#: were each wrong, and the standard library already implements the grammar.
_UNRESERVED = r"A-Za-z0-9\-._~"
_SUB_DELIMS = r"!$&'()*+,;="
_PCT_ENCODED = r"%[0-9A-Fa-f]{2}"
_PCHAR = r"(?:[" + _UNRESERVED + re.escape(_SUB_DELIMS) + r":@]|" + _PCT_ENCODED + r")"

_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+\-.]*")
_USERINFO = re.compile(r"(?:[" + _UNRESERVED + re.escape(_SUB_DELIMS) + r":]|" + _PCT_ENCODED + r")*")
_IPVFUTURE = re.compile(r"[vV][0-9A-Fa-f]+\.[" + _UNRESERVED + re.escape(_SUB_DELIMS) + r":]+")
_REG_NAME = re.compile(r"(?:[" + _UNRESERVED + re.escape(_SUB_DELIMS) + r"]|" + _PCT_ENCODED + r")*")
_PORT = re.compile(r"[0-9]*")                       # port = *DIGIT — empty is legal
_PATH = re.compile(r"(?:/" + _PCHAR + r"*)*")       # path-abempty
_PATH_ROOTLESS = re.compile(_PCHAR + r"+(?:/" + _PCHAR + r"*)*")
_QUERY = re.compile(r"(?:" + _PCHAR + r"|[/?])*")   # query and fragment share this production


def _is_ip_literal(text):
    """IP-literal = "[" ( IPv6address / IPvFuture ) "]" """
    if not (text.startswith("[") and text.endswith("]")):
        return None
    inner = text[1:-1]
    if _IPVFUTURE.fullmatch(inner):
        return True
    # `ipaddress` accepts a *scoped* address (`fe80::1%eth0`, RFC 6874). Appendix A's IPv6address has
    # no zone-identifier production, so delegating without this guard inherits a superset of the
    # grammar — the risk any delegation carries, and the reason it is named rather than assumed.
    if "%" in inner:
        return False
    try:
        ipaddress.IPv6Address(inner)
    except ValueError:
        return False
    return True


def _is_host(text):
    """host = IP-literal / IPv4address / reg-name — IPv4address is a subset of reg-name."""
    literal = _is_ip_literal(text)
    if literal is not None:
        return literal
    return bool(_REG_NAME.fullmatch(text))


def _is_authority(text):
    """authority = [ userinfo "@" ] host [ ":" port ]"""
    userinfo, at, hostport = text.rpartition("@")
    if at and not _USERINFO.fullmatch(userinfo):
        return False
    if hostport.startswith("["):
        close = hostport.find("]")
        if close < 0:
            return False
        host, remainder = hostport[:close + 1], hostport[close + 1:]
        if remainder and not (remainder.startswith(":") and _PORT.fullmatch(remainder[1:])):
            return False
    else:
        host, colon, port = hostport.rpartition(":")
        if not colon:
            host = hostport
        elif not _PORT.fullmatch(port):
            return False
    return _is_host(host)


def _is_uri(text):
    """URI = scheme ":" hier-part [ "?" query ] [ "#" fragment ]"""
    if not isinstance(text, str):
        return False
    text, hashed, fragment = text.partition("#")
    if hashed and not _QUERY.fullmatch(fragment):
        return False                                  # a second '#' fails here, as the grammar says
    text, marked, query = text.partition("?")
    if marked and not _QUERY.fullmatch(query):
        return False
    scheme, colon, hier = text.partition(":")
    if not colon or not _SCHEME.fullmatch(scheme):
        return False
    if hier.startswith("//"):                         # "//" authority path-abempty
        authority, slash, tail = hier[2:].partition("/")
        return bool(_is_authority(authority)
                    and _PATH.fullmatch("/" + tail if slash else ""))
    if hier.startswith("/"):                          # path-absolute
        return bool(_PATH.fullmatch(hier))
    if hier == "":                                    # path-empty
        return True
    return bool(_PATH_ROOTLESS.fullmatch(hier))       # path-rootless


_TYPES = {
    "object": dict, "array": list, "string": str,
    "integer": int, "number": (int, float), "boolean": bool, "null": type(None),
}


def _is_json_type(instance, expected):
    """JSON Schema's type predicate, which is not Python's.

    Two divergences matter. `True` is a Python `int`, but JSON Schema treats booleans as a distinct
    type. And `1.0` is a JSON *integer* — the spec judges by mathematical value, not representation.
    """
    if isinstance(instance, bool):
        return expected == "boolean"
    if expected == "integer":
        if isinstance(instance, int):
            return True
        return isinstance(instance, float) and instance.is_integer()
    if expected == "boolean":
        return False  # only real booleans, handled above
    return isinstance(instance, _TYPES[expected])


def _json_equal(a, b):
    """Equality with JSON's type distinctions, so `True` does not equal `1`.

    Recursive, because the distinction has to hold inside containers too: Python says
    `[True] == [1]` and `{"x": True} == {"x": 1}`, JSON does not. A shallow check would compare
    the outer types, find both are lists, and fall through to Python equality.
    """
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_json_equal(a[k], b[k]) for k in a)
    return a == b


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
        # Malformed keyword *values* are rejected here rather than at validation time. A bad
        # `minimum` on a string property would otherwise sit inert until some instance happened to
        # be a number, and a `pattern` that does not compile would raise a Python error mid-run.
        if key in ("minimum", "maximum") and (
                not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise UnsupportedSchemaError(f"{path}: {key} must be a number, got {value!r}")
        if key == "pattern":
            if not isinstance(value, str):
                raise UnsupportedSchemaError(f"{path}: pattern must be a string, got {value!r}")
            try:
                re.compile(value)
            except re.error as exc:
                raise UnsupportedSchemaError(
                    f"{path}: pattern {value!r} does not compile: {exc}") from exc
        if key == "format" and (
                not isinstance(value, str) or value not in IMPLEMENTED_FORMATS):
            raise UnsupportedSchemaError(f"{path}: unsupported format {value!r}")
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
        if not _is_json_type(instance, expected):
            raise ValidationError(f"{path}: expected {expected}, got {type(instance).__name__}")

    if "enum" in schema:
        if not any(_json_equal(instance, option) for option in schema["enum"]):
            raise ValidationError(f"{path}: {instance!r} is not one of {schema['enum']}")

    if "const" in schema:
        if not _json_equal(instance, schema["const"]):
            raise ValidationError(f"{path}: {instance!r} is not {schema['const']!r}")

    if "minLength" in schema and isinstance(instance, str):
        if len(instance) < schema["minLength"]:
            raise ValidationError(f"{path}: shorter than minLength {schema['minLength']}")

    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            raise ValidationError(f"{path}: {instance!r} does not match {schema['pattern']!r}")
        if "format" in schema:
            fmt = schema["format"]
            if fmt not in IMPLEMENTED_FORMATS:
                raise UnsupportedSchemaError(f"{path}: unsupported format {fmt!r}")
            if fmt == "uri" and not _is_uri(instance):
                raise ValidationError(f"{path}: {instance!r} is not a URI")

    # `bool` is a subclass of `int` in Python; a boolean is not a number here.
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ValidationError(f"{path}: {instance} is below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise ValidationError(f"{path}: {instance} is above maximum {schema['maximum']}")

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
