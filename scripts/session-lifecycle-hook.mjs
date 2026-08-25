#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// SessionStart / SessionEnd lifecycle hygiene (E1.6 / vibe-16).
//
// Deliberately small, and deliberately non-authoritative: this hook **reaps orphan temps and
// REPORTS** — it never rewrites a job record it does not own. Settling abandoned jobs belongs to
// `/vibe-suite:jobs --settle-abandoned` (E1.2); two authorities over one record is the defect
// class E1.1's store design exists to avoid.
//
// Three F2.6 lifecycle behaviours are deferred, with causes (see hooks/README.md): session-scoped
// job cleanup (job records carry no session id — a schema change that belongs with the store
// contract, not a hook), environment export (no bridge consumes it yet — F1.6/E2.x), and
// stale-registration migration (E0.8's engine, invoked by init in E2.1).
//
// **Always exits 0 for runtime faults.** A convenience hook that can break a session is not a
// convenience — a damaged store or a failed reap is reported and swallowed. The one exception is a
// USAGE error: an unknown or missing `--event` exits 2, because that is misconfiguration, not a
// session runtime condition.
//
// **Node floor: 18.** No top-level await.

import { isAbandoned, listRecords, reapOrphanTemps, TERMINAL_STATUSES } from "./lib/jobs.mjs";

function parseArgs(argv) {
  const index = argv.indexOf("--event");
  const event = index === -1 ? null : argv[index + 1];
  // A misconfigured hook is a USAGE error, not something to paper over: an unknown (or missing)
  // --event must fail loudly (exit 2) rather than silently masquerade as `start`. Runtime faults
  // (a damaged store, a failed reap) still exit 0 below — only misuse exits non-zero.
  if (event !== "start" && event !== "end") {
    process.stderr.write(
      `session-lifecycle-hook: expected --event start|end, got ${event === null ? "(none)" : JSON.stringify(event)}\n`);
    process.exit(2);
  }
  return { event };
}

async function main() {
  const { event } = parseArgs(process.argv.slice(2));
  const workspace = process.cwd();

  // vibe-203 (observability): a SessionStart hook's stdout is added to the session context, so the
  // operator actually sees these reports; SessionEnd stdout is not shown, so its reports stay on
  // stderr (transcript). Routing by event is the whole point of the fix.
  const report = (msg) => (event === "start" ? process.stdout : process.stderr).write(msg);

  const reaped = await reapOrphanTemps(workspace).catch(() => 0);
  if (reaped > 0) report(`vibe-suite ${event}: reaped ${reaped} orphan temp file(s)\n`);

  const { records, invalid } = await listRecords(workspace).catch(() => ({ records: [], invalid: [] }));
  for (const entry of invalid) {
    report(`vibe-suite ${event}: job ${entry.jobId} is unreadable (${entry.reason})\n`);
  }

  const live = records.filter((r) => !TERMINAL_STATUSES.has(r.status) && r.background);
  for (const record of live.filter((r) => isAbandoned(r))) {
    report(
      `vibe-suite ${event}: job ${record.jobId} looks abandoned (stale heartbeat, worker gone) — ` +
      `settle it with /vibe-suite:jobs status --settle-abandoned\n`);
  }
  if (event === "end") {
    for (const record of live.filter((r) => !isAbandoned(r))) {
      process.stderr.write(
        `vibe-suite end: job ${record.jobId} is still running — /vibe-suite:jobs status\n`);
    }
  }
}

main().catch((error) => {
  process.stderr.write(`vibe-suite lifecycle: ${error?.stack ?? error}\n`);
}).finally(() => {
  process.exitCode = 0;
});
