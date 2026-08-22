// SPDX-License-Identifier: ISC
// The one renderer for /vibe-suite:jobs output (E1.2 / vibe-12, implements F2.5).
//
// One security property, held everywhere: record fields are DATA. `rawOutput` and `error` were
// written by an external process; they are fenced and truncated on display, never interpolated
// where they could read as instructions to the session that runs the command. The five-key result
// line is deliberately NOT rendered here — callers print `resultLine` from jobs.mjs, so the
// contract has exactly one producer.

/** External text longer than this is cut, and the cut is announced — silent truncation reads as
 * "that was all of it". */
export const RAW_TRUNCATE = 400;

/**
 * Terminal-control sequences are removed, not displayed: ANSI escapes in external text can
 * restyle, overwrite, or spoof the operator's terminal. Newlines and tabs survive; every other
 * control character goes.
 */
function stripControls(text) {
  return text
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, "")                  // CSI sequences
    .replace(/\x1b[@-_]/g, "")                                  // remaining two-byte escapes
    // Every control except \n and \t: C0 including \r (carriage return overwrites the line —
    // a spoofing primitive), DEL, and the C1 range (0x9b is a one-byte CSI).
    .replace(/[\x00-\x08\x0b-\x1f\x7f-\u009f]/g, "");
}

function fenceExternal(label, text) {
  if (text === null || text === undefined) return [];
  const body = stripControls(String(text));
  const shown = body.length > RAW_TRUNCATE
    ? `${body.slice(0, RAW_TRUNCATE)}\n… [truncated: ${body.length - RAW_TRUNCATE} more characters]`
    : body;
  // A fixed ``` fence is escapable by content containing one (Step-8 review, finding 2): the fence
  // must be strictly longer than every backtick run in what it encloses.
  const longestRun = Math.max(0, ...(shown.match(/`+/g) ?? []).map((run) => run.length));
  const fence = "`".repeat(Math.max(3, longestRun + 1));
  return [`${label} (external text, shown as data):`, fence, shown, fence];
}

function age(iso, now) {
  if (!iso) return "-";
  const ms = Math.max(0, now - Date.parse(iso));
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 1) return `${Math.floor(ms / 1000)}s`;
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return hours < 48 ? `${hours}h${minutes % 60}m` : `${Math.floor(hours / 24)}d`;
}

function displayStatus(record, abandoned) {
  return abandoned.has(record.jobId) ? "abandoned (stale heartbeat)" : record.status;
}

function pad(value, width) {
  const text = String(value);
  return text.length >= width ? text : text + " ".repeat(width - text.length);
}

/**
 * The `status` table. `abandoned` is a display verdict computed by the caller — rendering never
 * mutates a record and never decides policy. Invalid store entries are listed with their reasons:
 * a job that silently vanished from `status` would read as data loss.
 */
export function renderStatusTable(records, { invalid = [], abandoned = new Set(), now = Date.now() } = {}) {
  const lines = [];
  if (records.length === 0) {
    lines.push("no matching jobs");
  } else {
    const rows = records.map((record) => [
      record.jobId,
      record.kind,
      displayStatus(record, abandoned),
      record.background ? "background" : "foreground",
      age(record.createdAt, now),
    ]);
    const header = ["JOB ID", "KIND", "STATUS", "MODE", "AGE"];
    const widths = header.map((h, i) => Math.max(h.length, ...rows.map((r) => String(r[i]).length)));
    lines.push(header.map((h, i) => pad(h, widths[i])).join("  "));
    for (const row of rows) lines.push(row.map((cell, i) => pad(cell, widths[i])).join("  "));
  }
  for (const entry of invalid) {
    lines.push(`invalid record: ${entry.jobId} — ${entry.reason} (excluded from every operation)`);
  }
  return lines.join("\n");
}

/** One record in full, external text fenced. */
export function renderDetail(record, { abandoned = new Set(), now = Date.now() } = {}) {
  const lines = [
    `job:        ${record.jobId}`,
    `kind:       ${record.kind}`,
    `status:     ${displayStatus(record, abandoned)}`,
    `mode:       ${record.background ? "background" : "foreground"}`,
    `sandbox:    ${record.sandbox}`,
    `model:      ${record.model ?? "(engine default — P9)"}`,
    `created:    ${record.createdAt} (${age(record.createdAt, now)} ago)`,
    `started:    ${record.startedAt ?? "-"}`,
    `ended:      ${record.endedAt ?? "-"}`,
    `heartbeat:  ${record.heartbeatAt ?? "-"}`,
    `worker pid: ${record.workerPid ?? "-"}  pgid: ${record.pgid ?? "-"}`,
    `thread:     ${record.threadId ?? "-"}`,
    `exit code:  ${record.exitCode ?? "-"}`,
    `pipes:      ${record.pipesLeaked === true
      ? "LEAKED — a descendant held the engine's stdio open past its exit; output may be incomplete"
      : record.pipesLeaked === false ? "released" : "-"}`,
  ];
  lines.push(...fenceExternal("error", record.error));
  lines.push(...fenceExternal("rawOutput", record.rawOutput));
  return lines.join("\n");
}

/** The cancel verdict, one shape per outcome — each distinct enough to grep a transcript for. */
export function renderCancelOutcome(outcome) {
  const id = outcome.record.jobId;
  if (outcome.outcome === "already-terminal") {
    return `job ${id} already finished: ${outcome.record.status} — nothing to cancel`;
  }
  if (!outcome.signalled) {
    return `job ${id} cancelled (no live process to signal)`;
  }
  if (outcome.groupDead) {
    return `job ${id} cancelled; process group ${outcome.record.pgid} confirmed dead`;
  }
  return `job ${id}: record cancelled, but process group ${outcome.record.pgid} is STILL ALIVE ` +
    `after SIGTERM/SIGKILL escalation — investigate manually`;
}

/** `--json`: the records verbatim, for tooling. Pretty-printed; still one JSON document. */
export function renderJson(payload) {
  return JSON.stringify(payload, null, 2);
}
