#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Dispatch the next batch of eligible repositories.

    batch-process.py --data-dir DIR --stage STAGE [--batch-size N] [--apply]

Default is a dry run listing what would happen and issuing NO mutating call. `--apply` labels
the issues and dispatches the workflow.

AN UNREADABLE REGISTRY REFUSES; IT IS NOT AN EMPTY ONE. This is the difference between "no
repositories are eligible" and "I could not tell which repositories are eligible", and the two
are indistinguishable downstream: both produce an empty list. Treating the second as the first
means a corrupt or missing registry leads to dispatching against defaults, or to a run that
reports success having done nothing — while the registry that would have said otherwise sits
unread. Every `gh` call here is a label change or a workflow dispatch against a third party's
repository, so guessing is not recoverable by re-running.

THE BATCH SIZE IS A RATE LIMIT ON OTHER PEOPLE'S REPOSITORIES, not a performance tuning knob.
Exceeding it means more issues labelled and more workflows dispatched than the operator
authorised, against repositories belonging to people who did not ask us to. It is enforced by
slicing the eligible list before any call is made, so a failure part-way through cannot let a
retry push the total over.

Eligibility is decided entirely from the registry before any call, and the plan is printed
before it is executed, so a dry run shows exactly the calls an apply would make.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

#: stage -> (required current status, label to add, workflow to dispatch)
STAGES = {
    "audit": ("discovered", "audit-ready", "auditor-audit.yml"),
    "contribute": ("audited", "contribute-approved", "auditor-contribute.yml"),
    "case-study": ("contributed", "case-study-ready", "auditor-case-study.yml"),
}
DEFAULT_BATCH_SIZE = 5


def refuse(reason: str) -> None:
    print(f"REFUSE:batch-process:{reason}", file=sys.stderr)
    raise SystemExit(1)


def gh(args, apply: bool):
    """Run a `gh` command, or describe it. Returns True on success."""
    printable = "gh " + " ".join(args)
    if not apply:
        print(f"  would run: {printable}")
        return True
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAILED: {printable}: {result.stderr.strip()}", file=sys.stderr)
        return False
    print(f"  ran: {printable}")
    return True


def eligible(repos, required_status):
    """Repositories in the required state, with an issue number, in a stable order."""
    out = []
    for repo in sorted(repos):
        entry = repos.get(repo)
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status") or "") != required_status:
            continue
        issue = entry.get("issue_number") or entry.get("issue")
        if issue is None:
            continue
        out.append((repo, str(issue)))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Dispatch the next batch of repositories.")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR"))
    parser.add_argument("--stage", default=None, choices=sorted(STAGES))
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--host-repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--apply", action="store_true", help="issue the calls; default dry run")
    args = parser.parse_args(argv)

    if not args.stage:
        refuse("stage-required")
    if not args.data_dir:
        refuse("data-dir-required")
    if args.batch_size < 1:
        refuse("batch-size-invalid")
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        refuse("data-dir-missing")

    registry_path = data_dir / "registry" / "repos.json"
    # Each of these is a way the registry can fail to answer the question. None may degrade to
    # an empty list: "nothing is eligible" and "I cannot tell" look identical afterwards.
    if not registry_path.is_file():
        refuse("registry-missing")
    try:
        raw = registry_path.read_text(encoding="utf-8")
    except OSError:
        refuse("registry-unreadable")
    try:
        registry = json.loads(raw)
    except json.JSONDecodeError:
        refuse("registry-unreadable")
    repos = registry.get("repos") if isinstance(registry, dict) else None
    if not isinstance(repos, dict):
        refuse("registry-malformed")

    required_status, label, workflow = STAGES[args.stage]
    candidates = eligible(repos, required_status)
    # Sliced BEFORE any call, so a failure part-way through cannot let a retry exceed the cap.
    batch = candidates[:args.batch_size]

    print(f"batch-process: stage={args.stage} eligible={len(candidates)} "
          f"batch={len(batch)} (cap {args.batch_size})"
          f"{'' if args.apply else ' — dry run, no mutating calls'}")

    failures = 0
    for repo, issue in batch:
        print(f"{repo} (issue #{issue})")
        if not gh(["issue", "edit", issue, "--add-label", label], args.apply):
            failures += 1
            continue
        dispatch = ["workflow", "run", workflow, "-f", f"repo={repo}", "-f", f"issue_number={issue}"]
        if args.host_repo:
            dispatch += ["--repo", args.host_repo]
        if not gh(dispatch, args.apply):
            failures += 1

    if failures:
        print(f"batch-process: {failures} call(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
