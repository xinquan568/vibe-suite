#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Read and write issue2pr run manifests (E5.3 / vibe-42).

    profile_manifest.py read <manifest.json>
    profile_manifest.py write --root <dir> <manifest.json> < payload.json

Genericised from a project-named script in the source: nothing here knows which project a manifest
describes. That knowledge lives in the profile.

**`crates_confirmed` → `areas_confirmed` is three obligations, not one.** Rename the field, bump the
schema version, **and read the old spelling**. A port that does the first two has made every existing
manifest unreadable while looking finished — which is why the read path accepts both and normalises to
the new name, so nothing downstream ever sees the fossil.

A manifest carrying **both** spellings is refused rather than resolved. Two values that disagree cannot
both be the answer, and picking one silently is worse than saying so.

Writes go through `bridge.write_atomic`.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402

EXIT_OK, EXIT_BAD_INPUT, EXIT_BAD_ROOT, EXIT_WRITE_FAILED = 0, 1, 2, 3

CURRENT_SCHEMA = 2
LEGACY_FIELD = "crates_confirmed"
CURRENT_FIELD = "areas_confirmed"


def normalise(payload):
    """Return the manifest in current-schema terms, or raise on an ambiguity.

    The rename is invisible after this point: callers see `areas_confirmed` whichever spelling the file
    used, and no downstream code has to know the fossil existed.
    """
    has_legacy = LEGACY_FIELD in payload
    has_current = CURRENT_FIELD in payload

    if has_legacy and has_current:
        raise ValueError(
            "manifest carries both %s and %s; two values that disagree cannot both be the answer, "
            "and choosing between them silently would be worse than refusing"
            % (LEGACY_FIELD, CURRENT_FIELD))

    result = dict(payload)
    if has_legacy:
        result[CURRENT_FIELD] = result.pop(LEGACY_FIELD)
        result["schema_version"] = CURRENT_SCHEMA
    return result


def read(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("profile_manifest: %s" % exc, file=sys.stderr)
        return None
    try:
        return normalise(payload)
    except ValueError as exc:
        print("profile_manifest: %s" % exc, file=sys.stderr)
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read or write an issue2pr run manifest.")
    sub = parser.add_subparsers(dest="mode", required=True)

    reader = sub.add_parser("read")
    reader.add_argument("manifest")

    writer = sub.add_parser("write")
    writer.add_argument("manifest")
    writer.add_argument("--root", required=True)

    args = parser.parse_args(argv)

    if args.mode == "read":
        payload = read(args.manifest)
        if payload is None:
            return EXIT_BAD_INPUT
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_OK

    try:
        payload = normalise(json.loads(sys.stdin.read()))
    except ValueError as exc:
        print("profile_manifest: %s" % exc, file=sys.stderr)
        return EXIT_BAD_INPUT

    root = Path(args.root).absolute()
    try:
        bridge.assert_root(root)
        bridge.pin_root(root)
        bridge.write_atomic(root, Path(args.manifest).absolute(),
                            json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except (bridge.BridgeError, ValueError) as exc:
        print("profile_manifest: refusing to write %s: %s" % (args.manifest, exc), file=sys.stderr)
        return EXIT_WRITE_FAILED

    print("profile_manifest: wrote %s" % args.manifest)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
