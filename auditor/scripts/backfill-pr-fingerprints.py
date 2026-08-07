#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Attach finding provenance to PRs that predate the metadata block.

    backfill-pr-fingerprints.py --data-dir DIR [--repo OWNER/NAME] [--apply]

Default is a dry run. `--apply` writes the registry.

Modern contribution PRs carry a sentinel-bounded metadata block naming the findings they fix,
so `auditor-track` can join outcomes back to findings. PRs opened before that block existed
have empty `fingerprints` and `rule_ids`, which makes every outcome they earned invisible to
rule health — the rules those PRs validated look untested rather than confirmed.

ATTRIBUTION IS BY CHANGED FILE, AND THAT IS THE ONLY THING KEEPING THIS HONEST. The obvious
implementation attaches every finding in the repository's sidecar to every PR against that
repository. It runs clean, fills in every empty field, and produces a tidy registry in which a
PR that fixed one typo is credited with validating forty rules. Rule health is computed from
exactly these fields, so the result is not a cosmetic error: it is a rules dataset that says
rules were confirmed by changes that never touched the files they were about.

So a finding is attributed only when its `file` is among the paths the PR actually changed,
read from the PR itself.

Existing values are UNIONED, never replaced. A PR may already carry provenance from its
metadata block; overwriting it with whatever this pass infers would discard the auditor's own
first-hand record in favour of a reconstruction. Union also makes reruns idempotent: the same
evidence produces the same set, so a second pass appends nothing.

The registry is written through a same-directory temporary file and renamed, so a run that
dies midway leaves the previous registry intact rather than a half-written one. Every other
stage reads this file.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def refuse(reason: str) -> None:
    print(f"REFUSE:backfill-pr-fingerprints:{reason}", file=sys.stderr)
    raise SystemExit(1)


def slug_for(repo: str) -> str:
    return repo.replace("/", "-")


def pr_files(repo: str, number) -> list[str] | None:
    """Paths the PR changed, or None when the PR cannot be read.

    None is distinct from `[]`: a PR that genuinely changed nothing attributes nothing, while a
    PR that could not be fetched must be SKIPPED. Collapsing them would let a network failure
    look like a PR that touched no files, and this helper would then confidently record "no
    findings apply" as though it had checked.
    """
    result = subprocess.run(
        ["gh", "pr", "view", str(number), "--repo", repo, "--json", "files"],
        capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    files = payload.get("files")
    if not isinstance(files, list):
        return None
    return [str(entry.get("path")) for entry in files
            if isinstance(entry, dict) and entry.get("path")]


def read_findings(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    findings = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            findings.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return findings


def atomic_write(path: Path, text: str) -> None:
    """Same-directory temp file plus rename, so rename(2) is atomic on this filesystem.

    A temp file in /tmp would make this a cross-device copy, which is not atomic and can leave
    a truncated registry behind.
    """
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent),
                                         prefix=path.name + ".", delete=False)
    try:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, path)
    except BaseException:
        os.unlink(handle.name)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Backfill PR finding provenance.")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR"))
    parser.add_argument("--repo", default=None, help="limit to one owner/name")
    parser.add_argument("--apply", action="store_true", help="write; default is a dry run")
    args = parser.parse_args(argv)

    if not args.data_dir:
        refuse("data-dir-required")
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        refuse("data-dir-missing")
    registry_path = data_dir / "registry" / "repos.json"
    if not registry_path.is_file():
        refuse("registry-missing")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        refuse("registry-unreadable")
    repos = registry.get("repos") if isinstance(registry, dict) else None
    if not isinstance(repos, dict):
        refuse("registry-malformed")
    if args.repo and args.repo not in repos:
        refuse(f"repo-not-in-registry {args.repo}")

    targets = [args.repo] if args.repo else sorted(repos)
    changed, skipped = 0, 0

    for repo in targets:
        entry = repos.get(repo)
        if not isinstance(entry, dict) or not isinstance(entry.get("prs"), dict):
            continue
        findings = read_findings(data_dir / "audits" / f"{slug_for(repo)}.findings.jsonl")
        if not findings:
            continue
        by_file: dict[str, list[dict]] = {}
        for finding in findings:
            if finding.get("file") and finding.get("fingerprint"):
                by_file.setdefault(str(finding["file"]), []).append(finding)

        for number in sorted(entry["prs"], key=lambda n: str(n)):
            record = entry["prs"][number]
            if not isinstance(record, dict):
                continue
            paths = pr_files(repo, record.get("number", number))
            if paths is None:
                skipped += 1
                print(f"  skip {repo}#{number}: PR could not be read", file=sys.stderr)
                continue

            attributed = [f for path in paths for f in by_file.get(path, [])]
            if not attributed:
                continue

            existing_fp = list(record.get("fingerprints") or [])
            existing_rules = list(record.get("rule_ids") or [])

            # `rule_ids` is PARALLEL to `fingerprints` — SCHEMAS.md pairs them by position.
            # Sorting and de-duplicating each independently destroys that pairing: sort two
            # lists separately and entry i of one no longer describes entry i of the other, so
            # every finding is attributed to some other finding's rule. The registry still
            # looks well-formed, and rule health silently credits the wrong rules.
            #
            # So the PAIR is the unit: dedupe on it, and order by it.
            pairs = list(zip(existing_fp, existing_rules))
            if len(existing_fp) != len(existing_rules):
                # Already unpaired — pad rather than zip-truncate, which would drop provenance.
                pairs = [(fp, existing_rules[i] if i < len(existing_rules) else None)
                         for i, fp in enumerate(existing_fp)]
            for finding in attributed:
                pairs.append((finding["fingerprint"], finding.get("rule_id")))

            seen_pairs, ordered = set(), []
            for pair in pairs:
                if pair[0] and pair not in seen_pairs:
                    seen_pairs.add(pair)
                    ordered.append(pair)
            ordered.sort(key=lambda pair: (str(pair[0]), str(pair[1] or "")))
            merged_fp = [fp for fp, _ in ordered]
            merged_rules = [rule for _, rule in ordered]
            if merged_fp == existing_fp and merged_rules == existing_rules:
                continue
            record["fingerprints"] = merged_fp
            record["rule_ids"] = merged_rules
            changed += 1
            print(f"  {repo}#{number}: {len(merged_fp)} fingerprint(s), "
                  f"{len(merged_rules)} rule id(s)")

    if not args.apply:
        print(f"backfill-pr-fingerprints: would update {changed} PR(s), "
              f"{skipped} unreadable (dry run; pass --apply)")
        return 0

    if changed:
        atomic_write(registry_path,
                     json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(f"backfill-pr-fingerprints: updated {changed} PR(s), {skipped} unreadable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
