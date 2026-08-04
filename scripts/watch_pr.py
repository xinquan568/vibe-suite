#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Watch a pull request and exit with the reason it stopped being worth watching.

Chain mode runs links serially: a link's change opens a PR, and the chain waits for that PR to reach
a state worth acting on before starting the next link. This program is that wait. It is **read-only**
— it never merges, comments, or closes; it reports, and the core decides.

`gh` is the only dependency. The repository is an argument, never a constant.

**Exit codes are the interface**, and the mode surface maps each to a chain action:

    0  merged                     4  a completed check failed
    1  usage error                5  timeout
    2  closed without merge       6  ten consecutive state-probe failures
    3  activity newer than cursor 7  green and unarmed (--merge-when-green only)

**Two properties that a re-implementation gets wrong by default**, both encoded below:

- **Exit 5 is a timeout, not a state.** It is evaluated at the top of the iteration, *before* the
  state probe, so the PR's state at that moment is unobserved — a PR that merged during the
  preceding sleep still exits 5. Do not describe it as "still open"; nothing asked.
- **Exit 6 counts state-probe failures only.** The rollup and activity calls degrade to a benign
  value on failure, so a rate-limited check query never trips the error exit.
"""

import argparse
import json
import subprocess
import sys
import time

EXIT_MERGED = 0
EXIT_USAGE = 1
EXIT_CLOSED = 2
EXIT_ACTIVITY = 3
EXIT_CHECKS_FAILED = 4
EXIT_TIMEOUT = 5
EXIT_GH_ERRORS = 6
EXIT_GREEN = 7

#: `--merge-when-green` waits this long before calling a check set complete. Checks register
#: asynchronously, so an empty or partial set early in a PR's life is not evidence of success.
GREEN_FLOOR_SECONDS = 180

#: Consecutive *state-probe* failures before giving up. Any success resets the count.
MAX_CONSECUTIVE_FAILURES = 10

FAILING_CONCLUSIONS = frozenset({"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT"})
PASSING_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})


class GhError(RuntimeError):
    """A `gh` invocation that did not return usable output."""


def project(body, fields):
    """What `gh pr view --json a,b` returns when the response object carries more than a and b.

    Recorded fixtures are captured from whatever call the observer happened to make, so a body is
    routinely a superset of what a given call requests. Projection is the reconciliation, and it is
    exactly what `gh` itself does.
    """
    return {field: body[field] for field in fields if field in body}


def reduce(body, field):
    """What `gh api --paginate --jq '.[].<field> // empty'` writes to stdout.

    Newline-delimited values, not JSON, and empty values dropped — a review with no `submitted_at`
    is pending, and emitting a blank line for it would make an unsubmitted review look like activity.
    """
    values = [element.get(field) for element in body if isinstance(element, dict)]
    return "\n".join(str(v) for v in values if v not in (None, ""))


def _run_gh(argv):
    result = subprocess.run(["gh"] + argv, capture_output=True, text=True)
    if result.returncode != 0:
        raise GhError(result.stderr.strip() or f"gh exited {result.returncode}")
    return result.stdout


class Watcher:
    """One poll loop.

    `gh`, `clock` and `max_polls` are seams. In production they default to the real `gh`, the real
    clock, and an unbounded loop; the suite injects a fake `gh` so no test touches the network, a
    fake clock so the timeout and the 180 s floor are reachable without waiting, and a poll bound so
    a non-terminating condition fails a test rather than hanging CI.
    """

    def __init__(self, repo, pr, cursor, poll=90, max_wait=21600, merge_when_green=False,
                 gh=None, clock=None, max_polls=None):
        self.repo = repo
        self.pr = str(pr)
        self.cursor = "" if cursor in ("-", None) else cursor
        self.poll = poll
        self.max_wait = max_wait
        self.merge_when_green = merge_when_green
        self.gh = gh or _run_gh
        self.clock = clock or time.time
        self.max_polls = max_polls
        self.consecutive_failures = 0

    # -- the five calls, in the shape this port commits to --------------------------------------
    #
    # `pr view` drops `--jq` and reduces here, so the reduction is reachable by a test rather than
    # buried in a jq expression. The paginated `api` calls keep `--jq`, because `--paginate` without
    # a reducer emits concatenated JSON arrays, which are not a parseable document.

    def _pr_view(self, fields):
        raw = self.gh(["pr", "view", self.pr, "--repo", self.repo, "--json", fields])
        try:
            return project(json.loads(raw), fields.split(","))
        except (ValueError, TypeError) as exc:
            raise GhError(f"unparseable response for --json {fields}: {exc}") from exc

    def _state(self):
        return self._pr_view("state").get("state")

    def _rollup(self):
        try:
            checks = self._pr_view("statusCheckRollup").get("statusCheckRollup") or []
        except GhError:
            return []                      # degrades: never counts toward EXIT_GH_ERRORS
        return [(c.get("conclusion") or c.get("state") or "") for c in checks]

    def _latest_activity(self):
        endpoints = ((f"repos/{self.repo}/issues/{self.pr}/comments", "updated_at"),
                     (f"repos/{self.repo}/pulls/{self.pr}/reviews", "submitted_at"),
                     (f"repos/{self.repo}/pulls/{self.pr}/comments", "updated_at"))
        stamps = []
        for path, field in endpoints:
            try:
                raw = self.gh(["api", "--paginate", path, "--jq", f".[].{field} // empty"])
            except GhError:
                continue                   # degrades, like the rollup
            stamps.extend(line for line in raw.splitlines() if line.strip())
        return max(stamps) if stamps else None

    # -- one poll -------------------------------------------------------------------------------

    def poll_once(self, elapsed):
        """The exit code this poll produces, or `None` to keep waiting.

        The order below *is* the precedence. Reordering it changes behaviour that the suite pins
        one case per edge.
        """
        try:
            state = self._state()
        except GhError:
            self.consecutive_failures += 1
            if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                return EXIT_GH_ERRORS
            return None
        self.consecutive_failures = 0

        if state == "MERGED":
            return EXIT_MERGED
        if state == "CLOSED":
            return EXIT_CLOSED

        conclusions = self._rollup()
        if any(c in FAILING_CONCLUSIONS for c in conclusions):
            return EXIT_CHECKS_FAILED

        if self.merge_when_green and elapsed >= GREEN_FLOOR_SECONDS:
            if conclusions and all(c in PASSING_CONCLUSIONS for c in conclusions):
                return EXIT_GREEN

        latest = self._latest_activity()
        if latest and (not self.cursor or latest > self.cursor):
            return EXIT_ACTIVITY
        return None

    def run(self):
        start = self.clock()
        polls = 0
        while True:
            elapsed = self.clock() - start
            # Before the probe, deliberately. See the module docstring: at this point the PR's
            # state is unobserved, so this is a timeout and not an assertion that it is open.
            if elapsed >= self.max_wait:
                return EXIT_TIMEOUT
            if self.max_polls is not None and polls >= self.max_polls:
                # The bounded-poll seam reports the same "stopped waiting" outcome as the clock,
                # so the exit set stays at eight.
                return EXIT_TIMEOUT

            outcome = self.poll_once(elapsed)
            if outcome is not None:
                return outcome

            polls += 1
            if self.poll:
                time.sleep(self.poll)


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error; this interface says 1.

    The exit codes are the contract a chain reads, and 2 already means "closed without merge". A
    malformed invocation reporting the code for a closed PR would make the chain mark a link
    `closed_unmerged` and pause on a typo.
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        raise SystemExit(EXIT_USAGE)


def main(argv=None):
    parser = _Parser(
        prog="watch_pr.py",
        description="Watch a pull request; exit with the reason it stopped being worth watching.")
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("pr", type=int, help="pull-request number")
    parser.add_argument("cursor", help="ISO-8601 activity cursor, or - to treat any activity as new")
    parser.add_argument("poll", nargs="?", type=int, default=90, help="seconds between polls")
    parser.add_argument("max_wait", nargs="?", type=int, default=21600, help="seconds before timeout")
    parser.add_argument("--merge-when-green", action="store_true",
                        help="also exit 7 once every registered check has passed")
    args = parser.parse_args(argv)

    watcher = Watcher(args.repo, args.pr, args.cursor, poll=args.poll, max_wait=args.max_wait,
                      merge_when_green=args.merge_when_green)
    return watcher.run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(EXIT_USAGE)
