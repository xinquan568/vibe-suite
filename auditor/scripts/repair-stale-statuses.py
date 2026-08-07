#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Repair registry statuses that a two-way merge race reverted.

Before the three-way merge landed, a concurrent push could overwrite a repo's status with the
pushing workflow's stale view — an audit would complete, then an unrelated run would put the
entry back to `discovered`. This finds the entries that were reverted and restores what the
evidence on disk says actually happened.

Two corruption patterns, and only these two:

  * `status == discovered` while `commit_sha_at_audit` is set — the audit demonstrably ran, so
    the status was reverted. Repair to `audited`.
  * `status in {discovered, audited}` while `pipeline_prs` is non-empty — contribute
    demonstrably ran. Repair to `contributed`.

Both are inferences from evidence the pipeline could not have written unless the stage
completed, which is why they are safe to apply automatically.

WHAT IT DELIBERATELY DOES NOT TOUCH. `tracked` and `complete` belong to the track workflow,
downstream of contribute — "repairing" them here would fabricate progress from nothing. Nor
does it write `prs[]`, the human-curated list; only `pipeline_prs` is machine-managed.

SCORE RECOVERY AND THE ZERO. A missing score is recovered from the audit report. The test is
`is None`, NEVER truthiness: **0/100 is a real and legitimate audit outcome** — a catastrophic
one, and exactly the result worth keeping. Treating it as missing overwrites the worst genuine
score in the corpus with whatever the report happens to say, and no schema check would notice.

`--dry-run` reports without writing. Paths follow M-1, under `--data-dir`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCORE = re.compile(r"\*\*NL Score\*\*:\s*(\d+)\s*/\s*100")

#: Statuses the track workflow owns. Never repaired here, in either direction.
DOWNSTREAM = ("tracked", "complete")


def read_score(audits_dir, slug):
    """The score in this repo's audit report, or None when absent or unparseable."""
    path = Path(audits_dir) / f"{slug.replace('/', '-')}.md"
    if not path.is_file():
        return None
    for line in path.read_text(errors="replace").splitlines():
        found = SCORE.search(line)
        if found:
            return int(found.group(1))
    return None


def repair(registry, audits_dir):
    """Repair `registry` in place; return the counts of each change."""
    counts = {"audited": 0, "contributed": 0, "score_recovered": 0}
    for slug, entry in registry.get("repos", {}).items():
        status = entry.get("status")
        if status in DOWNSTREAM:
            continue                       # the track workflow owns these

        if status == "discovered" and entry.get("commit_sha_at_audit"):
            entry["status"] = "audited"
            counts["audited"] += 1

        # `is None`, not truthiness: a real 0 must survive.
        if entry.get("score") is None:
            score = read_score(audits_dir, slug)
            if score is not None:
                entry["score"] = score
                counts["score_recovered"] += 1

        if (entry.get("pipeline_prs") or []) and entry.get("status") in ("discovered", "audited"):
            entry["status"] = "contributed"
            counts["contributed"] += 1
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Repair reverted registry statuses.")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR", "."))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    registry_path = data_dir / "registry" / "repos.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REFUSE:repair-stale-statuses:registry-unreadable {registry_path}: {exc}",
              file=sys.stderr)
        return 1
    if not isinstance(registry.get("repos"), dict):
        print("REFUSE:repair-stale-statuses:registry-has-no-repos-map", file=sys.stderr)
        return 1

    counts = repair(registry, data_dir / "audits")
    print(json.dumps(counts, sort_keys=True))

    if args.dry_run:
        return 0
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
