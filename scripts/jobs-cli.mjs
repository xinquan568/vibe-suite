#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// The /vibe-suite:jobs CLI (E1.2 / vibe-12, implements F2.5).
//
// Canonical call (from `commands/jobs.md`, which invokes this via ${CLAUDE_PLUGIN_ROOT} because an
// installed plugin does not live in the user's cwd):
//
//   node scripts/jobs-cli.mjs [status [<job-id>]] [--all] [--json] [--settle-abandoned]
//   node scripts/jobs-cli.mjs result <job-id>
//   node scripts/jobs-cli.mjs cancel [<job-id>]
//   node scripts/jobs-cli.mjs prune [--older-than <n>d|h|m|s]      (vibe-204: terminal jobs, whole)
//
// Default subcommand is `status`; a bare job id means `status <job-id>`. The workspace is
// `process.cwd()` — identical to codex-runner.mjs, so both sides of the store agree on where it is:
// `<workspace>/.vibe-suite-state/jobs/<jobId>.json`.
//
// Exit codes: 0 — done (including "already finished" cancels); 1 — a true answer that is not
// success (result not finished, nothing to cancel, ambiguous target, invalid/missing record, group
// outlived escalation); 2 — usage. Callers branch on the exit code, never on output shape.
//
// **Node floor: 18.** No top-level await — `main()` is invoked, not awaited at module scope
// (cc-suite W7 class). All command logic lives here and in scripts/lib/, never in markdown
// snippets, so the no-top-level-await sweep covers every line that can execute.

import { isAbandoned, pruneTerminalJobs, resultLine, TERMINAL_STATUSES } from "./lib/jobs.mjs";
import {
  abandonedIds, cancelJob, parseOlderThan, resolveResultJob, resolveStatusJobs, settleAbandoned,
  OLDER_THAN_DEFAULT, ResolveError,
} from "./lib/resolve.mjs";
import {
  renderCancelOutcome, renderDetail, renderJson, renderPruneOutcome, renderStatusTable,
} from "./lib/render.mjs";

const SUBCOMMANDS = new Set(["status", "result", "cancel", "prune"]);
const FLAGS = new Set(["--all", "--json", "--settle-abandoned", "--older-than"]);

class UsageError extends Error {}

function parseArgs(argv) {
  const options = {
    subcommand: null, jobId: null, all: false, json: false, settle: false, olderThan: null, olderThanMs: null,
  };
  const positional = [];
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--all") options.all = true;
    else if (arg === "--json") options.json = true;
    else if (arg === "--settle-abandoned") options.settle = true;
    else if (arg === "--older-than" || arg.startsWith("--older-than=")) {
      // The one value-taking flag: `--older-than 7d` or `--older-than=7d`.
      const value = arg.includes("=") ? arg.slice("--older-than=".length) : argv[i += 1];
      if (value === undefined) throw new UsageError("--older-than requires a value (e.g. 7d, 12h, 30m, or 0)");
      options.olderThan = value;
    }
    else if (arg.startsWith("--")) throw new UsageError(`unknown flag: ${arg} (known: ${[...FLAGS].join(", ")})`);
    else positional.push(arg);
  }
  if (positional.length === 0) {
    options.subcommand = "status";
  } else if (SUBCOMMANDS.has(positional[0])) {
    options.subcommand = positional[0];
    if (positional.length > 2) throw new UsageError(`too many arguments: ${positional.slice(2).join(" ")}`);
    options.jobId = positional[1] ?? null;
  } else if (positional.length === 1 && positional[0].startsWith("job_")) {
    options.subcommand = "status";                     // `jobs <id>` reads as `status <id>`
    options.jobId = positional[0];
  } else {
    throw new UsageError(`unknown subcommand: ${positional[0]} (expected status | result | cancel)`);
  }
  if (options.subcommand === "result" && options.jobId === null) {
    throw new UsageError("result requires a job id (see: status --all)");
  }
  if (options.subcommand !== "status") {
    // Status-only flags are refused, not ignored: `cancel --settle-abandoned <id>` silently
    // cancelling would be an answer to a question nobody asked (Step-8 review, finding 4).
    for (const [flag, set] of [["--all", options.all], ["--json", options.json],
      ["--settle-abandoned", options.settle]]) {
      if (set) throw new UsageError(`${flag} applies to status only`);
    }
  }
  if (options.subcommand === "prune") {
    // vibe-204: prune is a sweep, never a per-job command — a job id here is a misunderstanding of
    // what it does, so it is refused rather than narrowed to that job.
    if (options.jobId !== null) {
      throw new UsageError("prune takes no job id — it removes every terminal job older than the cutoff");
    }
    try {
      options.olderThanMs = parseOlderThan(options.olderThan ?? OLDER_THAN_DEFAULT);
    } catch (error) {
      if (!(error instanceof ResolveError)) throw error;
      throw new UsageError(error.message);
    }
  } else if (options.olderThan !== null) {
    throw new UsageError("--older-than applies to prune only");
  }
  return options;
}

async function runStatus(workspace, options) {
  let settledIds = [];
  if (options.settle) {
    const scope = await resolveStatusJobs(workspace, { jobId: options.jobId, all: options.all });
    const settled = await settleAbandoned(workspace, scope.records);
    settledIds = settled.map((record) => record.jobId);
    for (const record of settled) {
      // stderr: stdout must stay one parseable document under --json (Step-8 review, finding 3).
      process.stderr.write(`settled abandoned job ${record.jobId} -> failed\n`);
    }
  }
  const { records, invalid } = await resolveStatusJobs(workspace, {
    jobId: options.jobId, all: options.all,
  });
  const abandoned = abandonedIds(records);
  if (options.json) {
    process.stdout.write(
      renderJson({ records, invalid, abandoned: [...abandoned], settled: settledIds }) + "\n");
  } else if (options.jobId !== null) {
    process.stdout.write(renderDetail(records[0], { abandoned }) + "\n");
  } else {
    process.stdout.write(renderStatusTable(records, { invalid, abandoned }) + "\n");
  }
  // Invalid records are rendered AND surfaced in the exit code — a scope containing a record the
  // store cannot vouch for is a true answer that is not success (Step-8 review, finding 5).
  return invalid.length > 0 ? 1 : 0;
}

async function runResult(workspace, options) {
  const record = await resolveResultJob(workspace, options.jobId);
  if (!TERMINAL_STATUSES.has(record.status)) {
    const state = isAbandoned(record) ? "running but looks abandoned (see: status)" : record.status;
    process.stdout.write(`job ${record.jobId} is not finished: ${state}\n`);
    return 1;
  }
  process.stdout.write(resultLine(record) + "\n");
  return 0;
}

async function runCancel(workspace, options) {
  const outcome = await cancelJob(workspace, options.jobId);
  process.stdout.write(renderCancelOutcome(outcome) + "\n");
  if (outcome.outcome === "cancelled" && outcome.signalled && !outcome.groupDead) return 1;
  return 0;
}

/**
 * `prune` (vibe-204): delete terminal jobs older than the cutoff, whole. The store decides what is
 * eligible and proves ownership of every file it removes; this side only parses and renders. Exit 1
 * when something in scope could not be vouched for or removed — a sweep that reports clean while
 * leaving files behind would be the same defect as a silent reaper.
 */
async function runPrune(workspace, options) {
  const report = await pruneTerminalJobs(workspace, { olderThanMs: options.olderThanMs });
  process.stdout.write(
    renderPruneOutcome(report, { olderThan: options.olderThan ?? OLDER_THAN_DEFAULT }) + "\n");
  return report.invalid.length > 0 || report.leftovers.length > 0 || report.blocked.length > 0 ? 1 : 0;
}

async function main() {
  const workspace = process.cwd();
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    if (!(error instanceof UsageError)) throw error;
    process.stderr.write(`jobs-cli: ${error.message}\n`);
    return 2;
  }

  try {
    if (options.subcommand === "result") return await runResult(workspace, options);
    if (options.subcommand === "cancel") return await runCancel(workspace, options);
    if (options.subcommand === "prune") return await runPrune(workspace, options);
    return await runStatus(workspace, options);
  } catch (error) {
    if (error instanceof ResolveError) {
      process.stderr.write(`jobs-cli: ${error.message}\n`);
      return error.code === "usage" ? 2 : 1;
    }
    throw error;
  }
}

main()
  .then((code) => { process.exitCode = code; })
  .catch((error) => {
    process.stderr.write(`jobs-cli: ${error?.stack ?? error}\n`);
    process.exitCode = 1;
  });
