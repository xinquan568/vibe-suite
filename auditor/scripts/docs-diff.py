#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Fetch every cited doc URL, hash the body, and report which ones drifted.

Cited docs are external pages the rules quote. When one changes underneath us the citation may
have gone stale, so this hashes each body and diffs against the stored hash.

Reads   <data>/ledgers/docs-citations.json   URL -> metadata (`_`-prefixed keys are metadata
                                             about the file itself and are skipped)
        <data>/ledgers/docs-hashes.json      URL -> {hash, last_seen}; absent on first run
Writes  <data>/ledgers/docs-hashes.json      rewritten atomically
        the --changed-out file               one drifted URL per line
Prints  {"changed": N, "bootstrapped": N, "unchanged": N, "fetch_failed": N}

THE CONTRACT ON FAILURE. A URL we could not fetch is SKIPPED — its stored hash is left exactly
as it was and it is not listed as changed. Recording a failure as drift would raise a false
alarm on every network blip; recording it as a new hash would be worse, silently adopting
"unreachable" as the baseline so the real change is never detected afterwards. `fetch_failed`
is counted and surfaces in the summary so an outage is visible rather than inferred.

Paths resolve under `--data-dir` (default `$AUDITOR_DATA_DIR`, then `.`), because our data
lives on a separate branch rather than inside the code tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = "vibe-suite-docs-diff/1.0"
FETCH_TIMEOUT = 30


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def save_atomic(path, data):
    """Write via a same-directory tempfile then rename, so a crash cannot truncate the store."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def fetch(url, opener=urlopen):
    """The body at `url`, or None on any failure. `opener` is injectable for tests."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=FETCH_TIMEOUT) as response:
            return response.read().decode("utf-8", errors="replace")
    except (URLError, HTTPError, TimeoutError, ConnectionError, ValueError, OSError):
        return None


def run(citations_path, hashes_path, changed_out, opener=urlopen):
    citations = load_json(citations_path, {})
    hashes = load_json(hashes_path, {})
    urls = [k for k in citations if not k.startswith("_")]
    counts = {"changed": 0, "bootstrapped": 0, "unchanged": 0, "fetch_failed": 0}
    if not urls:
        return counts

    changed_urls = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for url in urls:
        body = fetch(url, opener)
        if body is None:
            # Skip entirely: no hash update, not listed as changed. See the module docstring.
            print(f"WARN: could not fetch {url} — leaving its stored hash untouched",
                  file=sys.stderr)
            counts["fetch_failed"] += 1
            continue

        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        stored = hashes.get(url) or {}
        previous = stored.get("hash") if isinstance(stored, dict) else None

        if not previous:
            counts["bootstrapped"] += 1
        elif previous != digest:
            counts["changed"] += 1
            changed_urls.append(url)
        else:
            counts["unchanged"] += 1

        hashes[url] = {"hash": digest, "last_seen": now}

    Path(changed_out).parent.mkdir(parents=True, exist_ok=True)
    Path(changed_out).write_text("".join(f"{u}\n" for u in changed_urls), encoding="utf-8")
    save_atomic(hashes_path, hashes)
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Diff cited doc URLs against stored hashes.")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR", "."))
    parser.add_argument("--citations", default=None)
    parser.add_argument("--hash-store", default=None)
    parser.add_argument("--changed-out", default=None)
    args = parser.parse_args(argv)

    data = Path(args.data_dir)
    citations = Path(args.citations or data / "ledgers" / "docs-citations.json")
    hashes = Path(args.hash_store or data / "ledgers" / "docs-hashes.json")
    changed = Path(args.changed_out or data / "ledgers" / "changed-urls.txt")

    print(json.dumps(run(citations, hashes, changed), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
