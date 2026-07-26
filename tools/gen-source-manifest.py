#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Snapshot a pinned source tree's file list for `tools/coverage-check.py` (E0.6 / vibe-8).

AC-1's coverage walk runs in CI, where the three referenced repositories are not checked out. These
manifests stand in for them. That makes the manifests the only record CI has of what the trees
contain — so a snapshot that omits a file cannot be contradicted by anything, and coverage would
pass over artifacts that are simply missing from the evidence.

Two properties defend against that, and both shape the format:

**The list is unfiltered.** Whatever the allowlist and exclusions are, they are applied by the
checker at check time, never here. Filtering before the snapshot destroys the evidence that the
filtering was right, and it would put a second copy of those lists in this file — which AC-1
forbids in as many words ("the single definition").

**A manifest can be checked against its own commit.** Re-running this against a checkout at the
recorded commit must reproduce the file byte for byte, so drift is a reviewable diff rather than
silence. CI cannot run that check; a developer holding the pinned trees can, and the test suite does
when they are present.

Usage:  gen-source-manifest.py <tree-path> --repo <name> --out <path>
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPOS = ("cc-suite", "grill-for-claude", "nlpm")

#: The three workspace skills are the owner's own work. They are **not** in the vibe-suite
#: repository and the directory holding them is not a git checkout, so CI — which clones only
#: vibe-suite — cannot see them at all. They therefore need a snapshot exactly as the pinned trees
#: do, but an unpinned one: `commit` is null and regeneration is from the workspace rather than
#: from a commit. What makes it a *complete* tree rather than an allowlisted one is that the
#: checker applies no allowlist to it, per AC-1's "complete file trees ... not just the SKILL.md".
WORKSPACE = "workspace"
WORKSPACE_ROOTS = ("issue2pr", "refine-proposal", "runs-stats")


def git_files(tree):
    """Every tracked path, decoded so an undecodable byte cannot silently drop a file."""
    raw = subprocess.run(["git", "-C", str(tree), "ls-files", "-z"],
                         capture_output=True, check=True).stdout
    return sorted(part.decode("utf-8", "surrogateescape")
                  for part in raw.split(b"\0") if part)


def workspace_files(root):
    """Every file beneath the three skill roots, relative to `root`.

    Unfiltered, exactly like the git listings. An earlier version dropped OS junk here, which put a
    second filtering rule outside the checker — the thing AC-1's "single definition" forbids. The
    checker excludes those names anyway, so the snapshot stays faithful and the rule stays in one
    place.
    """
    out = []
    for skill in WORKSPACE_ROOTS:
        base = Path(root) / skill
        if not base.is_dir():
            raise SystemExit(f"error: {base} not found")
        out += [str(p.relative_to(root)) for p in base.rglob("*") if p.is_file()]
    return sorted(out)


def head_commit(tree):
    return subprocess.run(["git", "-C", str(tree), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def render(repo, commit, files):
    """Deterministic bytes: sorted, fixed separators, trailing newline."""
    return json.dumps({"repo": repo, "commit": commit,
                       "generated_by": "tools/gen-source-manifest.py",
                       "files": files},
                      indent=2, sort_keys=True) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    parser.add_argument("--repo", required=True, choices=REPOS + (WORKSPACE,))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.repo == WORKSPACE:
        commit, files = None, workspace_files(args.tree)
    else:
        if not (args.tree / ".git").exists():
            sys.stderr.write(f"error: {args.tree} is not a git checkout\n")
            return 1
        commit, files = head_commit(args.tree), git_files(args.tree)
    args.out.write_text(render(args.repo, commit, files), encoding="utf-8")
    sys.stderr.write(f"{args.repo}: {len(files)} files at "
                     f"{commit[:7] if commit else 'unpinned'} -> {args.out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
