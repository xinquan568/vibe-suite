// SPDX-License-Identifier: ISC
// Codex `--json` event-stream reader (E1.1 / vibe-11).
//
// **The stream is the authority, not the exit code.** codex-cli 0.144.6 was observed exiting 0 after
// an upstream outage, writing no result and emitting a `turn.failed` event; the issue2pr skill
// records the incident. A runner that read the exit code would have filed that job as `completed`
// and six downstream consumers would have believed it. So success is defined here, from the events,
// and `process.mjs` deliberately refuses to interpret anything.
//
// Unparseable lines are skipped rather than treated as fatal: codex interleaves human-readable
// diagnostics with the JSON. Skipping them is safe precisely because the absence of a terminal event
// is itself a failure — a stream whose terminal event we could not parse cannot be read as success.

const TERMINAL = { "turn.completed": "completed", "turn.failed": "failed" };

/** Parse one NDJSON line, or return null if it is not an event. */
function parseLine(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed[0] !== "{") return null;
  try {
    const value = JSON.parse(trimmed);
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

/**
 * Reduce a raw `--json` stream to the facts the job engine needs.
 *
 * Returns `{ threadId, terminal, usage, errorMessage, errorCode, malformedLines }` where `terminal` is
 * `"completed"`, `"failed"`, or `null` when no terminal event was seen at all.
 */
export function readEventStream(raw) {
  let threadId = null;
  let terminal = null;
  let usage = null;
  let errorMessage = null;
  let errorCode = null;
  let malformedLines = 0;

  for (const line of String(raw ?? "").split("\n")) {
    if (!line.trim()) continue;
    const event = parseLine(line);
    if (event === null) {
      malformedLines += 1;
      continue;
    }
    if (event.type === "thread.started") {
      threadId = event.thread_id ?? event.threadId ?? threadId;
      continue;
    }
    const mapped = TERMINAL[event.type];
    if (!mapped) continue;
    // First terminal event wins; a stream cannot un-fail.
    if (terminal === null) {
      terminal = mapped;
      usage = event.usage ?? (event.turn && event.turn.usage) ?? null;
      if (mapped === "failed") {
        errorMessage = event.error?.message ?? event.message ?? "turn.failed";
        // Machine-set and stable, where the backend supplies it. Prose is neither, so a classifier
        // that reads only the message is at the mercy of wording changes upstream.
        errorCode = event.error?.code ?? event.error?.type ?? null;
      }
    }
  }

  return { threadId, terminal, usage, errorMessage, errorCode, malformedLines };
}

/**
 * Bill only what was actually consumed.
 *
 * `input_tokens` includes `cached_input_tokens`; charging the total conflates context size with
 * spend and overstates it by an order of magnitude on any prompt that shares a prefix.
 */
export function billableTokens(usage) {
  if (!usage) return null;
  const input = usage.input_tokens ?? 0;
  const cached = usage.cached_input_tokens ?? 0;
  const output = usage.output_tokens ?? 0;
  return Math.max(0, input - cached) + output;
}
