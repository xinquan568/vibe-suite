#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Collect rule-suppression configs published across audited repositories.

    scan-suppressions.py --data-dir DIR --host-repo OWNER/NAME [--query Q] [--apply]

Default is a dry run. `--apply` appends to `<data-dir>/feedback/suppressions.jsonl`.

A maintainer who suppresses a rule is telling us something the audit cannot: that the rule
misfires on their codebase, or that they disagree with it. Aggregated, those overrides are the
strongest available signal about which rules are wrong — far better than our own false-positive
marks, because they come from the people the findings were sent to.

THE HOST REPOSITORY IS EXCLUDED, and this is not tidiness. This repository's own tests and
templates contain suppression configs as FIXTURES. Ingesting them records overrides nobody
ever set, attributed to rules nobody ever complained about, into the dataset used to decide
which rules to weaken or retire. The corruption is silent and self-reinforcing: our fixtures
argue for changing our own rules, and every subsequent scan finds them again.

DEDUPE IS ON (repo, sha, path), ALL THREE. Each alone is wrong:

  * repo alone — a repository with configs in two directories loses one of them;
  * path alone — every repository using the conventional filename collapses to one record;
  * repo+path without sha — an edited config never registers as changed, so the record keeps
    the first version forever and a maintainer who later suppressed six more rules is recorded
    as having suppressed none of them.

The sha is the blob sha of the file itself, so an unchanged config rescanned daily appends
nothing while a genuine edit appends a new record and leaves the old one as history.

Appends only, to `feedback/` rather than `ledgers/`: SCHEMAS.md reserves the ledgers for the
four pipeline logs, and this is an observation about other repositories' opinions of our rules,
so it sits with the rule-health feedback it feeds. A config that disappears from a repository
is not deleted here — that it once existed is the fact worth keeping.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_QUERY = "filename:.vibe-suppressions.yml"


def refuse(reason: str) -> None:
    print(f"REFUSE:scan-suppressions:{reason}", file=sys.stderr)
    raise SystemExit(1)


def parser_module():
    """`parse-suppressions.py`, imported for its stdlib frontmatter parser.

    Imported rather than reimplemented: it exists precisely because PyYAML is absent, and a
    second parser here would be a second chance to get the subset subtly wrong — with the
    failure showing up as suppressions silently misread rather than as an error.
    """
    spec = importlib.util.spec_from_file_location("_supp", HERE / "parse-suppressions.py")
    if spec is None or spec.loader is None:
        refuse("parser-missing")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True          # auditor/scripts/ is a closed, asserted inventory
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def gh_json(args):
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


#: GitHub's code search caps a page at 100 and the whole result set at 1000.
PAGE_SIZE = 100
MAX_PAGES = 10


def search(query):
    """Every page, not just the first.

    A single page silently truncates the corpus at the default page size, and the truncation is
    invisible: the scan reports a tidy count and the missing repositories simply never appear
    in the rule-health evidence. "We found no suppressions for that rule" and "we stopped
    looking" are indistinguishable afterwards.
    """
    payload = []
    for page in range(1, MAX_PAGES + 1):
        # The WHOLE response, not `.items`. GitHub can answer a code search with HTTP 200 and
        # `incomplete_results: true` when it times out mid-query — a partial page that looks
        # exactly like a final one if it holds fewer than PAGE_SIZE results. Projecting to
        # `.items` threw away the only field that says so, and --apply then recorded an
        # under-counted corpus as though the search had finished.
        response = gh_json(["api", "-X", "GET", "search/code", "-f", f"q={query}",
                            "-f", f"per_page={PAGE_SIZE}", "-f", f"page={page}"])
        if not isinstance(response, dict):
            # A failed page mid-way is not an empty result: returning what we have would
            # silently narrow the corpus, which is the failure this pagination exists to fix.
            return None
        if response.get("incomplete_results"):
            print("REFUSE:scan-suppressions:search-incomplete "
                  "(GitHub returned incomplete_results=true; the corpus would be partial)",
                  file=sys.stderr)
            return None
        chunk = response.get("items")
        if not isinstance(chunk, list) or not chunk:
            break
        payload.extend(chunk)
        if len(chunk) < PAGE_SIZE:
            break
    else:
        print(f"WARN search truncated at {MAX_PAGES * PAGE_SIZE} results; "
              f"narrow the query", file=sys.stderr)

    items = []
    for item in payload if isinstance(payload, list) else []:
        repo = ((item.get("repository") or {}).get("full_name"))
        if repo and item.get("path") and item.get("sha"):
            items.append({"repo": repo, "path": str(item["path"]), "sha": str(item["sha"])})
    return items


def fetch(repo, path, sha):
    """The blob the SEARCH found, addressed by its sha — not whatever that path holds now.

    The record keys dedupe on (repo, sha, path). Fetching `contents/<path>` reads the current
    default branch, so a file edited between search and fetch is stored under the OLD sha: the
    ledger then carries content that never existed at that sha, and every later scan dedupes
    against that false provenance and skips the real version forever.

    A blob is immutable, so addressing it by sha makes the recorded sha true by construction.
    """
    payload = gh_json(["api", f"repos/{repo}/git/blobs/{sha}"])
    if not isinstance(payload, dict):
        return None
    if payload.get("sha") and str(payload["sha"]) != str(sha):
        print(f"  skip {repo}:{path}: blob sha mismatch", file=sys.stderr)
        return None
    if payload.get("encoding") == "base64" and payload.get("content"):
        try:
            return base64.b64decode(payload["content"]).decode("utf-8", "replace")
        except (ValueError, TypeError):
            return None
    return payload.get("content")


def extract(supp, text):
    """`(overrides, error)` in the shape `parse-suppressions.py` prints.

    No frontmatter is not an error — a config file without it declares no suppressions, which
    is the ordinary state.
    """
    found = supp.FRONTMATTER.match(text or "")
    if not found:
        return [], None
    try:
        overrides = supp.parse_overrides(found.group(1))
    except ValueError as exc:
        return [], str(exc)
    return [{"rule_id": str(rule), "override": value}
            for rule, value in overrides.items()], None


def read_ledger(path: Path):
    if not path.is_file():
        return set(), True
    raw = path.read_text(encoding="utf-8")
    seen = set()
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("repo") and record.get("path") and record.get("sha"):
            seen.add((record["repo"], record["sha"], record["path"]))
    return seen, (raw.endswith("\n") or not raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect published rule suppressions.")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR"))
    parser.add_argument("--host-repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--observed-at", default=None, help="ISO stamp; default now (UTC)")
    parser.add_argument("--apply", action="store_true", help="write; default is a dry run")
    args = parser.parse_args(argv)

    if not args.data_dir:
        refuse("data-dir-required")
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        refuse("data-dir-missing")
    if not args.host_repo:
        # Without it every scan would ingest this repository's own fixtures as real
        # suppressions, so an unset value is refused rather than defaulted to "exclude nothing".
        refuse("host-repo-required")

    items = search(args.query)
    if items is None:
        refuse("search-failed")

    # `feedback/`, not `ledgers/`: SCHEMAS.md reserves ledgers for the four pipeline
    # logs. This is an observation about OTHER repositories' opinions of our rules, so
    # it sits with the rule-health feedback it feeds. Declared in SCHEMAS.md rather
    # than invented here.
    ledger = data_dir / "feedback" / "suppressions.jsonl"
    seen, ends_with_newline = read_ledger(ledger)
    observed = args.observed_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supp = parser_module()

    fresh, self_hits, duplicates = [], 0, 0
    for item in items:
        if item["repo"] == args.host_repo:
            self_hits += 1
            continue
        key = (item["repo"], item["sha"], item["path"])
        if key in seen:
            duplicates += 1
            continue
        text = fetch(item["repo"], item["path"], item["sha"])
        if text is None:
            print(f"  skip {item['repo']}:{item['path']}: unreadable", file=sys.stderr)
            continue
        overrides, error = extract(supp, text)
        seen.add(key)
        record = {
            "repo": item["repo"],
            "path": item["path"],
            "sha": item["sha"],
            "observed_at": observed,
            "override_count": len(overrides),
            "overrides": overrides,
            "rule_ids": sorted({o["rule_id"] for o in overrides if o.get("rule_id")}),
        }
        if error:
            # Recorded rather than dropped, and rather than aborting the scan. One repository's
            # broken config must not stop the other hundred, but it must also not read as
            # "this maintainer suppressed nothing" — which is what an empty list would mean.
            record["parse_error"] = error
            print(f"  {item['repo']}:{item['path']}: malformed config: {error}", file=sys.stderr)
        fresh.append(record)

    print(f"scan-suppressions: {len(items)} hit(s), {self_hits} self, "
          f"{duplicates} already recorded, {len(fresh)} new")
    if not fresh:
        return 0
    if not args.apply:
        for record in fresh:
            print(f"  would append {record['repo']}:{record['path']} "
                  f"({record['override_count']} override(s))")
        return 0

    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        if not ends_with_newline:
            handle.write("\n")
        for record in fresh:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"scan-suppressions: appended {len(fresh)} record(s) to {ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
