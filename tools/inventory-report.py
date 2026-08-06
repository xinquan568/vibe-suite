#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""§5.0 inventory report and counts-vs-disk check (AC-7's fourth sub-check, E7.4 / vibe-56).

§5.0 of the merge proposal is "the counts everything else derives from". It was written on
2026-07-18 and disk has moved in BOTH directions since:

  * categories that GREW — later stages shipped more than the inventory froze;
  * categories that are EMPTY — their artifacts belong to stage S8, which has not run.

So a literal equality check over every row cannot pass today for reasons no release can fix,
and a check that cannot pass is not a gate. This module therefore reports every §5.0 category
against disk and **fails `--check` on any category whose §5.0 figure is reachable today**,
while categories whose figure describes unshipped S8 work are reported with their target and
their owning stage, and are asserted to be EMPTY (their honest current value) rather than
waved through. When S8 ships, those rows move to `EXACT` by editing this table — the same
"an entry is a reviewed claim" discipline the mirror and sweep tables use.

Growth rows are asserted as `>=` their §5.0 figure with the drift printed, because a suite
that shipped more commands than the 2026-07-18 plan predicted is not a release defect; a
suite that LOST one is.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

EXACT, ATLEAST, PENDING_S8, RECONCILED = ("exact", "at-least", "pending-S8", "reconciled")

#: (label, §5.0 figure, rule, counter). The rule is a reviewed claim per row.
ROWS = [
    ("Slash commands", 26, ATLEAST,
     lambda r: len([p for p in (r / "commands").glob("*.md")])),
    ("Workflow skills (user-invocable)", 3, EXACT,
     lambda r: len([n for n in ("issue2pr", "refine-proposal", "runs-stats")
                    if (r / "skills" / n / "SKILL.md").is_file()])),
    ("Agents", 14, EXACT,
     lambda r: len(list((r / "agents").glob("*.md")))),
    ("Knowledge skills", 19, ATLEAST,
     lambda r: len([d for d in (r / "skills").iterdir()
                    if d.is_dir() and (d / "SKILL.md").is_file()
                    and d.name not in ("issue2pr", "refine-proposal", "runs-stats")])),
    # 8 in §5.0, 6 on disk: `codex-call` was delivered as scripts/codex-runner.mjs and
    # `append-history` as scripts/trend_engine.py (docs/disposition.yaml rows cc-suite:19 and
    # nlpm:16). The row asserts the 6 partials PLUS both reconciliation targets existing, so
    # losing either is still a failure.
    ("Shared partials", 8, RECONCILED,
     lambda r: len(list((r / "commands" / "shared").glob("*.md")))
     + sum((r / x).is_file() for x in ("scripts/codex-runner.mjs",
                                       "scripts/trend_engine.py"))),
    ("Plugin hook registrations", 4, EXACT,
     lambda r: len(json.loads((r / "hooks" / "hooks.json").read_text()).get("hooks", {}))),
    # 8 in §5.0, of which 5 are the site-build tools of F10.3 — stage S8. The 3 shipped ones
    # (vibe-check, vibe-report, vibe-badge) are asserted exactly; the rest are the S8 row.
    ("Python bin tools (shipped subset)", 3, EXACT,
     lambda r: len([p for p in (r / "bin").iterdir()
                    if p.is_file() and p.name != "README.md"])),
    ("Python bin tools (site builders)", 5, PENDING_S8,
     lambda r: len([p for p in (r / "bin").glob("vibe-build-*")])),
    ("Auditor-unit workflows", 24, PENDING_S8,
     lambda r: len(list((r / "auditor").rglob("*.yml")))),
    ("Auditor helper scripts", 30, PENDING_S8,
     lambda r: len(list((r / "auditor").rglob("*.py")))),
]


def measure(root):
    out = []
    for label, target, rule, counter in ROWS:
        try:
            actual = counter(root)
        except (OSError, ValueError, KeyError) as exc:
            out.append((label, target, rule, None, str(exc)))
            continue
        out.append((label, target, rule, actual, None))
    return out


def verdicts(rows):
    """(label, ok, note) per row — the check's whole judgment."""
    for label, target, rule, actual, err in rows:
        if err is not None:
            yield label, False, f"uncountable: {err}"
        elif rule == EXACT:
            yield label, actual == target, f"{actual} (§5.0: {target}, exact)"
        elif rule == ATLEAST:
            yield label, actual >= target, (f"{actual} (§5.0: {target}, at-least"
                                            f"{f'; +{actual - target} since' if actual > target else ''})")
        elif rule == RECONCILED:
            yield label, actual >= target, (f"{actual} incl. reconciliation targets "
                                            f"(§5.0: {target})")
        else:   # PENDING_S8 — the honest current value is zero until stage S8 ships
            yield label, actual == 0, f"{actual} (§5.0 target {target}; pending S8)"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--check", action="store_true",
                        help="exit nonzero on any row whose rule is violated")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    rows = measure(root)
    bad = 0
    print("§5.0 inventory vs disk")
    for label, ok, note in verdicts(rows):
        print(f"  {'ok ' if ok else 'FAIL'} {label}: {note}")
        if not ok:
            bad += 1
    if args.check:
        print(f"inventory-report: {bad} row(s) violate their rule")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
