#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Parse the auditor metadata block from a PR body on stdin.

The block is how a submitted PR carries its findings' fingerprints and rule ids back to the
registry, so `auditor-track.yml` can attribute an outcome to the findings that caused it. It is
written by `auditor-contribute.yml` as:

    <!-- vibe-suite-auditor-meta-begin {"findings":[...]} vibe-suite-auditor-meta-end -->

THE TAIL-MOST BLOCK WINS. A PR body is editable — by the contributor, by a maintainer, by a
later pipeline run appending a correction — so the last block is the current one. Taking the
first would pin attribution to a superseded edit forever, and it is the natural thing a
non-greedy regex does by default, which is why it is called out here and mutation-tested.

This parser is the ONE implementation of that contract (vibe-167): `auditor-track.yml` pipes
each PR body through it and consumes its output — the workflow's former inline jq regex is
retired, and a test pins both the wiring and the regex's absence, because a second copy would
be free to disagree and silently split attribution.

Output: the parsed JSON object on stdout, or `{}` when no block is present or its payload is
malformed. A malformed payload also warns on stderr and exits non-zero, so a corrupted block
surfaces in the run log instead of silently dropping attribution; stdout stays `{}` so callers
need no special case.
"""
import json
import re
import sys

BLOCK = re.compile(
    r"<!--\s*vibe-suite-auditor-meta-begin\s*(\{.*?\})\s*vibe-suite-auditor-meta-end\s*-->",
    re.DOTALL,
)


def parse(body):
    """Return (payload_json_text, warning_or_None) for the tail-most block in `body`."""
    matches = BLOCK.findall(body)
    if not matches:
        return "{}", None
    raw = matches[-1]                     # tail-most: the current block, not the first
    try:
        return json.dumps(json.loads(raw)), None
    except json.JSONDecodeError as exc:
        return "{}", f"metadata block present but its JSON is malformed: {exc}"


def main():
    out, warning = parse(sys.stdin.read())
    if warning:
        print(f"WARN: {warning}", file=sys.stderr)
    print(out)
    return 1 if warning else 0


if __name__ == "__main__":
    sys.exit(main())
