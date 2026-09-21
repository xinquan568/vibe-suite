#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The reproducibility gates' skip census (vibe-228 / M33).

Two gates in `tests/test_coverage_check.py` check that a vendored manifest still describes the tree
it stands for. Neither can run without a root that lives outside this repository, so on any machine
that has not supplied one they **skip** — and a skip is the right answer there. What is not right is
a skip nobody sees: M33's charge was that a reproducibility gate which never executes gives exactly
the same green as one that passes.

So this reports. It runs both gates, counts the result, and prints every skip **by test id and
reason**; under GitHub Actions it appends the same table to the run summary. Exit status is 0 unless
something failed or errored — a counted skip is not a failure, it is the documented answer, and
turning the weekly job red for it would teach everyone to ignore the job.

The count comes from `unittest`'s **result object**, never from its printed prose. A census that
grepped `OK (skipped=N)` would be one wording change away from reporting zero for ever, which is the
same silent-green failure the census exists to end.

    python3 tests/reproducibility_census.py
"""

import io
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The gates this census speaks for. Pinned by `test_the_gate_names_resolve_to_the_intended_classes`:
#: a renamed class must fail that test rather than quietly shrink the census to nothing.
GATES = (
    "tests.test_coverage_check.TestManifestsAreReproducible",
    "tests.test_coverage_check.TestWorkspaceManifestIsReproducible",
)

#: The environment variables each gate needs before it can do anything. Printed with the census so a
#: reader does not have to go and find out what the skip is asking for.
ROOTS = (
    ("VIBE_SUITE_PINNED_TREES", "the cc-suite / grill-for-claude / nlpm checkouts"),
    ("VIBE_SUITE_WORKSPACE_SKILLS", "the live .claude/skills directory"),
)


def load_gates(gate_ids=GATES):
    """The suite for `gate_ids`. Loader errors surface as `_FailedTest` entries, which the
    pinning test rejects — an unresolvable name must not look like a gate that ran."""
    return unittest.TestLoader().loadTestsFromNames(list(gate_ids))


def run_gates(gate_ids=GATES, stream=None):
    """Run the gates and hand back the raw result object."""
    runner = unittest.TextTestRunner(stream=stream or io.StringIO(), verbosity=2)
    return runner.run(load_gates(gate_ids))


def _owner(test):
    """The TestCase a result entry belongs to.

    `subTest` reports each failing sub-case as its own `_SubTest` object carrying a `test_case`
    back-reference. `testsRun` counts the PARENT once, so mixing the two scales is how a census
    arrives at a negative number of passes: the pinned-tree gate checks three repositories under
    `subTest`, and one broken root produces three failure entries against one test run.
    """
    return getattr(test, "test_case", test)


def census(result):
    """{ran, passed, skipped, failed, errored, *_events, skips}.

    Read off the result object, never off the runner's printed prose.

    **Every count is per TEST, and they sum to `ran`.** `subTest` reports each sub-case
    individually — failures, errors *and skips alike* — while `testsRun` counts the parent once, so
    a count taken from the entry lists is on a different scale from `ran`. One test skipping three
    roots would otherwise report `ran=1, skipped=3`.

    A test can also land in several buckets at once (one root skipped, another failed), so the
    buckets are resolved by precedence — **failed beats errored beats skipped** — and a test is
    counted exactly once. The `*_events` figures keep the finer sub-case tally, which is what a
    reader wants when one test reports several broken repositories, and `skips` keeps every
    individual reason for the table.
    """
    skips = [(str(test), reason) for test, reason in result.skipped]
    failed_tests = {str(_owner(test)) for test, _ in result.failures}
    errored_tests = {str(_owner(test)) for test, _ in result.errors} - failed_tests
    skipped_tests = ({str(_owner(test)) for test, _ in result.skipped}
                     - failed_tests - errored_tests)
    accounted = len(failed_tests) + len(errored_tests) + len(skipped_tests)
    return {
        "ran": result.testsRun,
        "skipped": len(skipped_tests),
        "failed": len(failed_tests),
        "errored": len(errored_tests),
        "failure_events": len(result.failures),
        "error_events": len(result.errors),
        "skip_events": len(skips),
        "passed": result.testsRun - accounted,
        "skips": skips,
    }


def render(counts, gate_ids=GATES):
    """The census as markdown. Every number in the prose is taken from `counts`, the same dict
    that produced the rows — a sentence written by hand drifts from its own table."""
    lines = ["### Reproducibility gates", ""]
    lines.append("Gates in this census: " + ", ".join(f"`{g}`" for g in gate_ids) + ".")
    lines.append("")
    lines.append(
        "**{ran} test(s): {passed} passed, {skipped} skipped, {failed} failed, "
        "{errored} errored.**".format(**counts))
    if (counts["failure_events"] > counts["failed"] or counts["error_events"] > counts["errored"]
            or counts["skip_events"] > counts["skipped"]):
        lines.append("")
        lines.append("({failure_events} failure, {error_events} error and {skip_events} skip "
                     "event(s) across those tests — a test checking several roots reports one "
                     "per root.)".format(**counts))
    lines.append("")
    if counts["skips"]:
        lines.append(f"{counts['skipped']} gate(s) DID NOT RUN:")
        lines.append("")
        lines.append("| test | why it did not run |")
        lines.append("| --- | --- |")
        for test, reason in counts["skips"]:
            lines.append(f"| `{test}` | {reason} |")
        lines.append("")
        lines.append("Supply a root to make one run:")
        lines.append("")
        for name, what in ROOTS:
            lines.append(f"- `{name}` — {what}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None, run=run_gates, out=None, summary_path=None):
    """Print the census, append it to the step summary, and report failures in the exit status.

    `summary_path` overrides the GitHub variable for testing — but it is never the only path to
    the file, because a suite that always injects would stay green with the environment lookup
    deleted, and the run summary is the whole point of the census.
    """
    out = sys.stdout if out is None else out
    counts = census(run())
    text = render(counts)
    out.write(text)
    if summary_path is None:
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        # Append: other steps write to this file too, and truncating it would delete their output.
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(text)
    # Failures and errors are checked independently: a shared truthiness test would let an
    # error-only regression ride out on the failure path's coverage.
    if counts["failed"] or counts["errored"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT))
    sys.exit(main())
