# SPDX-License-Identifier: ISC
"""E8.2 weekly-cap CAS reservation (vibe-59, plan task T4).

The `reserve` job clones `auditor-data`, reads `ledgers/contact-reservations.jsonl`, counts the
DISTINCT repos reserved in the trailing 7 days from the ENVELOPED fields (`data.repo`,
`timestamp`), proceeds when this repo already holds a reservation in the window (repeat contact
consumes no slot), refuses with `SKIP:weekly-cap` when the distinct count is already 2, else
appends a record and pushes WITHOUT force. A rejected push means another run advanced the tip:
it re-fetches, re-evaluates from scratch, and the loser correctly observes the slot consumed.

Every case runs against a REAL disposable git repo (a bare `auditor-data` remote + a clone) with
real git, including a competing submission simulated by advancing the bare remote from a second
clone between the read and the push.

There is no `reserve` job today, so these tests drive the CURRENT weekly-cap path --
auditor-contribute.yml's `# gate:pr-caps`, which reads `WEEK_CONTACT_COUNT` from the environment
and never derives it from the ledger. The tests therefore fail behaviorally: production derives
0 distinct repos from a populated reservation ledger and writes no reservation record.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from tests.test_auditor_state_machine import Sandbox, extract

WF = Path(__file__).resolve().parent.parent / "auditor" / "workflows" / "auditor-contribute.yml"
RESERVATIONS = "ledgers/contact-reservations.jsonl"
HAS_GIT = shutil.which("git") is not None
REAL_GIT = shutil.which("git") or "/usr/bin/git"

GIT_ENV = {"GIT_AUTHOR_NAME": "auditor-test", "GIT_AUTHOR_EMAIL": "auditor@example.invalid",
           "GIT_COMMITTER_NAME": "auditor-test", "GIT_COMMITTER_EMAIL": "auditor@example.invalid",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}

# PATH shim: counts pushes and, on the FIRST push only, lets a rival advance the bare remote
# between the reserve job's read and its push -- the competing-submission race.
GIT_SHIM = """#!/usr/bin/env bash
for a in "$@"; do
  if [ "$a" = "push" ]; then
    n=$(cat "$PUSH_COUNT" 2>/dev/null || echo 0)
    echo $((n+1)) > "$PUSH_COUNT"
    if [ "$n" -eq 0 ] && [ -x "${COMPETITOR:-}" ]; then "$COMPETITOR" >/dev/null 2>&1 || true; fi
    break
  fi
done
exec REAL_GIT_PATH "$@"
"""

COMPETITOR = """#!/usr/bin/env bash
set -e
cd "$RIVAL_CLONE"
REAL_GIT_PATH pull --rebase -q origin main
printf '%s\\n' "$RIVAL_RECORD" >> LEDGER_PATH
REAL_GIT_PATH add -A
REAL_GIT_PATH -c user.name=rival -c user.email=rival@example.invalid commit -q -m "rival reservation"
REAL_GIT_PATH push -q origin main
"""


def git(*args, cwd, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), check=check, text=True,
                          capture_output=True, env=dict(os.environ, **GIT_ENV))


def iso(delta_seconds):
    t = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=delta_seconds)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(repo, delta_seconds, run_number=1):
    """A reservation record in the canonical envelope (auditor/SCHEMAS.md)."""
    return {"timestamp": iso(delta_seconds), "workflow": "auditor-contribute",
            "event": "contact_reserved", "run_id": f"run-{run_number}",
            "run_number": run_number, "data": {"repo": repo}}


DAY = 86400


def reserve_block(test):
    """`reserve`'s logic block once it exists; today, production's only weekly-cap enforcement."""
    b = extract(WF, "logic", "reserve")
    if b is None:
        b = extract(WF, "gate", "pr-caps")
    test.assertIsNotNone(b, "neither a reserve logic block nor gate:pr-caps exists")
    return b


def derived_distinct(out):
    """The distinct-repo count production derived from the ledger (0 when it derived none)."""
    hits = re.findall(r"DISTINCT:(\d+)", out)
    return int(hits[-1]) if hits else 0


@unittest.skipUnless(HAS_GIT, "git is required for the CAS reservation tests")
class ReservationBase(unittest.TestCase):
    def setup_data(self, records, registry="registry.json"):
        """Bare `auditor-data` remote + a clone carrying the enveloped reservation ledger."""
        sb = Sandbox(registry=registry)
        self.addCleanup(sb.cleanup)
        bare = sb.root / "auditor-data.git"
        git("init", "--bare", "-b", "main", str(bare), cwd=sb.root)  # -b main: without it HEAD is an unborn "master", so pushes to main leave the
    # remote log empty and the rival clone has no local main to race with.
        git("init", cwd=sb.data)
        git("checkout", "-b", "main", cwd=sb.data, check=False)
        for c in ("reports", "audits", "ledgers", "articles", "exemplars", "registry"):
            (sb.data / c / ".gitkeep").write_text("")
        (sb.data / RESERVATIONS).write_text(
            "".join(json.dumps(r) + "\n" for r in records))
        git("add", "-A", cwd=sb.data)
        git("commit", "-m", "seed reservations", cwd=sb.data)
        git("remote", "add", "origin", str(bare), cwd=sb.data)
        git("push", "-u", "origin", "main", cwd=sb.data)
        sb.bare = bare
        sb.push_count = sb.root / "push-count"
        return sb

    def env(self, sb, candidate, extra=None):
        # E8.2b (vibe-164): the weekly cap is no longer read from the environment. gates
        # derives it and publishes context.json; reserve consumes that. Passing WEEKLY_CAP
        # here would be a test supplying a value the graph must derive -- the exact thing
        # the acceptance clause forbids and the W-scan flags. The cap still has a value in
        # these tests; it just arrives the way production delivers it.
        ctx = sb.root / "context.json"
        ctx.write_text(json.dumps({
            "version": 1, "repo": candidate, "issue": "42",
            "expected_fork_slug": "vibe-bot/" + candidate.split("/")[-1],
            "audited_sha": "cafebabe", "base_branch": "main",
            "author_name": "vibe-suite auditor bot", "author_email": "auditor@example.invalid",
            "weekly_cap": 2, "patch_cap": 3}))
        e = {"REPO": candidate, "OWNER": candidate.split("/")[0],
             "RESERVATIONS": str(sb.data / RESERVATIONS),
             "RESERVATION_LEDGER": str(sb.data / RESERVATIONS),
             "DATA_REMOTE": str(sb.bare), "CONTEXT_FILE": str(ctx),
             "PUSH_COUNT": str(sb.push_count),
             "FIRST_CONTACT": "true", "PLANNED_COUNT": "2"}
        e.update(GIT_ENV)
        e.update(extra or {})
        return e

    def reserve(self, sb, candidate, extra=None):
        return sb.run(reserve_block(self), env=self.env(sb, candidate, extra))

    @staticmethod
    def remote_records(sb):
        r = subprocess.run(["git", f"--git-dir={sb.bare}", "show", f"main:{RESERVATIONS}"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return []
        return [json.loads(x) for x in r.stdout.splitlines() if x.strip()]

    @staticmethod
    def local_records(sb):
        p = sb.data / RESERVATIONS
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

    @staticmethod
    def repos_of(records):
        return {(rec.get("data") or {}).get("repo", rec.get("repo")) for rec in records}


class TestWeeklyCap(ReservationBase):
    def test_third_distinct_repo_is_capped(self):
        sb = self.setup_data([envelope("acme/one", -2 * DAY, 1),
                              envelope("acme/two", -3 * DAY, 2)])
        r = self.reserve(sb, "acme/three")
        out = r.stdout + r.stderr
        self.assertEqual(derived_distinct(out), 2,
                         "production derived 0 distinct repos from a ledger holding two "
                         "reservations inside the trailing 7 days -- the weekly cap reads "
                         f"WEEK_CONTACT_COUNT from the environment, not the ledger. Output: {out!r}")
        self.assertIn("SKIP:weekly-cap", out,
                      "a third distinct repo in the window must be refused with SKIP:weekly-cap")
        self.assertNotIn("acme/three", self.repos_of(self.local_records(sb)),
                         "a capped run appended a reservation record")
        self.assertNotIn("acme/three", self.repos_of(self.remote_records(sb)),
                         "a capped run pushed a reservation record to auditor-data")

    def test_repeat_contact_consumes_no_new_slot(self):
        sb = self.setup_data([envelope("acme/one", -2 * DAY, 1),
                              envelope("acme/two", -3 * DAY, 2)])
        r = self.reserve(sb, "acme/two")
        out = r.stdout + r.stderr
        self.assertEqual(derived_distinct(out), 2,
                         "production derived 0 distinct repos; a repeat contact must be evaluated "
                         f"against the ledger's real distinct count. Output: {out!r}")
        self.assertNotIn("SKIP:weekly-cap", out,
                         "a repo that already holds a reservation in the window must proceed -- "
                         "repeat contact consumes no new slot")
        self.assertEqual(self.repos_of(self.remote_records(sb)), {"acme/one", "acme/two"},
                         "a repeat contact must not widen the distinct-repo set")

    def test_many_events_for_one_repo_count_one(self):
        sb = self.setup_data([envelope("acme/one", -i * 3600, i) for i in range(1, 8)])
        r = self.reserve(sb, "acme/two")
        out = r.stdout + r.stderr
        self.assertEqual(derived_distinct(out), 1,
                         "seven reservation events for ONE repo must count as 1 distinct repo; "
                         f"production derived {derived_distinct(out)}. Output: {out!r}")
        self.assertNotIn("SKIP:weekly-cap", out,
                         "1 distinct repo is below the cap of 2, so the candidate must proceed")
        self.assertIn("acme/two", self.repos_of(self.remote_records(sb)),
                      "the granted reservation was never appended and pushed to auditor-data")


class TestSevenDayBoundary(ReservationBase):
    """A reservation exactly 7 days old: BOTH sides asserted explicitly."""

    def test_just_inside_seven_days_counts(self):
        sb = self.setup_data([envelope("acme/one", -1 * DAY, 1),
                              envelope("acme/two", -(7 * DAY) + 60, 2)])
        out = self.reserve(sb, "acme/three").stdout
        self.assertEqual(derived_distinct(out), 2,
                         "a reservation 7 days minus one minute old is INSIDE the trailing-7-day "
                         f"window and must count; production derived {derived_distinct(out)}")
        self.assertIn("SKIP:weekly-cap", out,
                      "with the just-inside reservation counted the cap of 2 is reached")

    def test_just_outside_seven_days_does_not_count(self):
        sb = self.setup_data([envelope("acme/one", -1 * DAY, 1),
                              envelope("acme/two", -(7 * DAY) - 60, 2)])
        out = self.reserve(sb, "acme/three").stdout
        self.assertEqual(derived_distinct(out), 1,
                         "a reservation 7 days plus one minute old is OUTSIDE the window and must "
                         f"NOT count; production derived {derived_distinct(out)}")
        self.assertNotIn("SKIP:weekly-cap", out,
                         "with only one in-window reservation the candidate must proceed")
        self.assertIn("acme/three", self.repos_of(self.remote_records(sb)),
                      "the granted reservation was never appended and pushed to auditor-data")


class TestCompetingSubmission(ReservationBase):
    """The CAS retry: the first push is rejected, the retry re-reads the ADVANCED tip."""

    def _arm_race(self, sb, rival_repo):
        rival = sb.root / "rival"
        subprocess.run(["git", "clone", "-q", str(sb.bare), str(rival)], check=True,
                       capture_output=True, text=True, env=dict(os.environ, **GIT_ENV))
        comp = sb.bin / "competitor.sh"
        comp.write_text(COMPETITOR.replace("REAL_GIT_PATH", REAL_GIT)
                        .replace("LEDGER_PATH", RESERVATIONS))
        comp.chmod(0o755)
        shim = sb.bin / "git"
        shim.write_text(GIT_SHIM.replace("REAL_GIT_PATH", REAL_GIT))
        shim.chmod(0o755)
        return {"COMPETITOR": str(comp), "RIVAL_CLONE": str(rival),
                "RIVAL_RECORD": json.dumps(envelope(rival_repo, -60, 99))}

    def test_rejected_push_retries_against_the_advanced_tip(self):
        sb = self.setup_data([envelope("acme/one", -2 * DAY, 1)])
        extra = self._arm_race(sb, "acme/rival")
        r = self.reserve(sb, "acme/three", extra)
        out = r.stdout + r.stderr
        pushes = int(sb.push_count.read_text().strip() or 0) if sb.push_count.exists() else 0
        self.assertEqual(derived_distinct(out), 2,
                         "after the rejected push the retry must re-fetch and re-evaluate against "
                         "the ADVANCED tip, counting {acme/one, acme/rival} = 2; production "
                         f"derived {derived_distinct(out)} and never pushed at all. Output: {out!r}")
        self.assertGreaterEqual(pushes, 2,
                                f"the CAS retry never happened: {pushes} push attempt(s). A "
                                "non-force push rejected by an advanced tip must be re-tried "
                                "after a re-fetch and a fresh evaluation.")
        self.assertIn("SKIP:weekly-cap", out,
                      "the loser of the race must observe the slot consumed and skip")
        self.assertNotIn("acme/three", self.repos_of(self.remote_records(sb)),
                         "the losing run still landed its reservation on the advanced tip")
        self.assertIn("acme/rival", self.repos_of(self.remote_records(sb)),
                      "the rival's reservation is missing from the bare remote")


if __name__ == "__main__":
    unittest.main()
