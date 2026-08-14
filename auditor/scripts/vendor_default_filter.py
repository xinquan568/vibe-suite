#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Drop discovery candidates the contribute pipeline cannot land a PR against.

Filtering here saves the whole audit cost. The contribute workflow has runtime policy gates for
these cases, but they fire LATE — after the API calls and model tokens have been spent — so a
candidate that can never accept a PR is worth excluding at discovery.

Three reasons, each a documented observation rather than a guess:

  * **DENY_OWNERS** — the org's stated policy forbids external PRs outright.
  * **DENY_REPOS** — repo-level deny, finer than owner-wide, for the case where one repo blocks
    contribution and the owner's others do not.
  * **CLA_REQUIRED_OWNERS** — PRs land but stall indefinitely on a CLA status check unless the
    contributing identity is the CLA signer.

The lists are deliberately SHORT. A broad denylist silently drops repos that would have been
good audits, and a silent drop is indistinguishable from "we never found it". Add an owner only
with a written reason.

Two behaviours are contractual and both are mutation-tested:

  * comparison is CASE-INSENSITIVE. GitHub owners are case-preserving but case-insensitive, so
    `Anthropics/x` and `anthropics/x` are one repo. A case-sensitive check would let the exact
    same repo through depending on how discovery happened to spell it.
  * an unrecognised record shape PASSES THROUGH. Dropping records without a known repo key
    would make a schema change look like an empty discovery run — the pipeline would go quiet
    instead of failing, which is the worst way for this to break.

Usage:
    cat candidates.jsonl | python3 auditor/scripts/vendor_default_filter.py > kept.jsonl
    from vendor_default_filter import is_vendor_default
"""
from __future__ import annotations

import argparse
import json
import sys

#: Orgs whose stated policy is that external PRs are not accepted.
DENY_OWNERS: frozenset[str] = frozenset({"anthropics"})

#: Repo-level denies, where the owner's other repos remain fair game.
#: openai/codex and openai/codex-action auto-close unsolicited external PRs on a stale timer;
#: ours are unsolicited by definition, so they would be closed unreviewed. Owner-wide deny would
#: be wrong — openai's other repos are not NL-artifact repos and never pass the artifact probe.
DENY_REPOS: frozenset[str] = frozenset({"openai/codex", "openai/codex-action"})

#: Orgs requiring every commit to be CLA-signed. PRs land and then stall on the CLA check unless
#: the contributing identity is the signer. chromedevtools is Google-operated despite the name
#: and uses the same CLA bot — listed because it was observed, not inferred from the name.
CLA_REQUIRED_OWNERS: frozenset[str] = frozenset({
    "google", "google-gemini", "googleworkspace", "google-labs-code",
    "googleapis", "googlecloudplatform", "chromedevtools",
})

#: First-party / reference-implementation owners: auditing them yields findings the maintainer
#: already knows. Empty, and left as a documented hook — nothing has justified an entry.
ECOSYSTEM_VENDORS: frozenset[str] = frozenset()

#: Record shapes discovery emits. `fullName` is the gh-search shape; `repo_name` the query shape.
REPO_KEYS = ("fullName", "repo_name", "full_name")


def is_vendor_default(repo):
    """`(should_drop, reason)` for an `owner/name` string. `reason` is '' when keeping."""
    if not repo or "/" not in repo:
        return False, ""
    lowered = repo.lower()
    if lowered in DENY_REPOS:
        return True, f"deny-repo:{lowered} (unsolicited external PRs auto-closed)"
    owner = lowered.split("/", 1)[0]
    if owner in DENY_OWNERS:
        return True, f"deny:{owner} (policy: no external PRs)"
    if owner in CLA_REQUIRED_OWNERS:
        return True, f"cla-required:{owner} (commits must be CLA-signed)"
    if owner in ECOSYSTEM_VENDORS:
        return True, f"vendor:{owner} (first-party / reference)"
    return False, ""


def read_jsonl(stream):
    """Records from JSONL, skipping blanks; a malformed line warns and is dropped."""
    out = []
    for n, line in enumerate(stream, 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"WARN stdin:{n} malformed JSON: {exc}", file=sys.stderr)
    return out


def extract_repo(record):
    """The `owner/name` this record refers to, or None if the shape is unrecognised."""
    if not isinstance(record, dict):
        return None
    for key in REPO_KEYS:
        value = record.get(key)
        if value:
            return value
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vendor-default discovery filter.")
    parser.add_argument("--report", action="store_true",
                        help="always emit the stderr summary, even when nothing was dropped")
    args = parser.parse_args(argv)

    records = read_jsonl(sys.stdin)
    kept, dropped = [], {}
    for record in records:
        repo = extract_repo(record)
        if not repo:
            kept.append(record)          # unknown shape: pass through, never silently drop
            continue
        skip, reason = is_vendor_default(repo)
        if skip:
            dropped[reason] = dropped.get(reason, 0) + 1
        else:
            kept.append(record)

    for record in kept:
        print(json.dumps(record, ensure_ascii=False))

    if dropped or args.report:
        print(f"vendor-default filter: kept {len(kept)} of {len(records)}; "
              f"dropped {len(records) - len(kept)}", file=sys.stderr)
        for reason, count in sorted(dropped.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {count:>4}  {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
