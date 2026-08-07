#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Append a legacy report's findings to a sidecar that is missing them.

    backfill-findings.py --repo OWNER/NAME --report PATH --sidecar PATH [--apply]

Default is a dry run: it prints what would be appended and writes nothing. `--apply` performs
the append.

APPEND-ONLY, BY FINGERPRINT. Existing lines are never rewritten, reordered or reformatted —
they are the records other ledgers already join to, and re-emitting one with different key
order or spacing would produce a diff on every run and invite a reviewer to "fix" whichever
copy looks wrong. Only findings whose fingerprint is absent get written.

THE TRAILING NEWLINE IS LOAD-BEARING TWICE OVER, in two unrelated places, and both fail
silently:

  * In the DIGEST. `compute-fingerprint.sh` hashes jq's output including its trailing newline.
    Dropping it yields a different, equally stable-looking fingerprint — every backfilled
    finding would then be a duplicate of one already recorded, and the dedupe here would never
    notice because it compares the wrong keys.
  * At the END OF THE FILE. A sidecar whose last line has no newline turns the first append
    into `{...}{...}` on one physical line. Both records are then unreadable, and JSONL has no
    framing to notice: the file simply contains one unparseable line where two findings used
    to be.

So a rerun over an unchanged report appends nothing and leaves the file byte-identical, and a
sidecar with no final newline gets one before anything is appended.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def refuse(reason: str) -> None:
    print(f"REFUSE:backfill-findings:{reason}", file=sys.stderr)
    raise SystemExit(1)


def synthesizer():
    """The synthesizer, imported for its parser and its digest.

    Imported rather than reimplemented: the helper set is a closed inventory of thirty names so
    a shared module cannot be added, and a second copy of the fingerprint routine would be free
    to drift from the first — which, since the fingerprint is a join key, means silently
    re-keying findings rather than failing.
    """
    spec = importlib.util.spec_from_file_location("_synth", HERE / "synthesize-sidecar.py")
    if spec is None or spec.loader is None:
        refuse("synthesizer-missing")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True          # auditor/scripts/ is a closed, asserted inventory
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def read_existing(path: Path, synth, repo):
    """`(fingerprints, ends_with_newline)`; a missing sidecar is empty rather than an error."""
    if not path.is_file():
        return set(), True
    raw = path.read_text(encoding="utf-8")
    if not raw:
        return set(), True
    seen = set()
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            # A malformed line is skipped for DEDUPE purposes but deliberately left in place.
            # Rewriting the file to drop it would be a silent repair of data this helper was
            # not asked to touch.
            continue
        # COMPUTED, not read. Section 4 sidecars carry no fingerprint — the aggregation
        # post-step adds it. Deduping on a field the file never contains means nothing ever
        # matches, so every rerun appends the whole report again.
        seen.add(synth.fingerprint(repo, record))
    return seen, raw.endswith("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Backfill findings from a legacy report.")
    parser.add_argument("--repo", default=None, help="owner/name")
    parser.add_argument("--report", default=None)
    parser.add_argument("--sidecar", default=None)
    parser.add_argument("--apply", action="store_true", help="write; default is a dry run")
    args = parser.parse_args(argv)

    if not args.repo:
        refuse("repo-required")
    if "/" not in args.repo:
        refuse("repo-not-owner-name")
    if not args.report:
        refuse("report-required")
    if not args.sidecar:
        refuse("sidecar-required")
    report = Path(args.report)
    if not report.is_file():
        refuse("report-missing")

    synth = synthesizer()
    findings = synth.parse_report(report.read_text(encoding="utf-8"))

    sidecar = Path(args.sidecar)
    seen, ends_with_newline = read_existing(sidecar, synth, args.repo)

    missing, added = [], set()
    for finding in findings:
        # The digest identifies the finding for dedupe; it is NOT written into the sidecar,
        # which section 4 says carries none.
        key = synth.fingerprint(args.repo, finding)
        # `added` as well as `seen`: one report can describe the same finding twice, and
        # without this the first run would append the duplicate that every later run refuses.
        if key not in seen and key not in added:
            missing.append(finding)
            added.add(key)

    if not missing:
        print(f"backfill-findings: {len(findings)} finding(s) in report, 0 to append")
        return 0

    if not args.apply:
        print(f"backfill-findings: would append {len(missing)} finding(s) "
              f"of {len(findings)} (dry run; pass --apply)")
        for finding in missing:
            print(f"  {synth.fingerprint(args.repo, finding)} {finding.get('file')} "
                  f"{finding.get('rule_id')}")
        return 0

    sidecar.parent.mkdir(parents=True, exist_ok=True)
    with sidecar.open("a", encoding="utf-8") as handle:
        if not ends_with_newline:
            handle.write("\n")
        for finding in missing:
            handle.write(json.dumps(finding, ensure_ascii=False, sort_keys=True) + "\n")

    print(f"backfill-findings: appended {len(missing)} finding(s) to {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
