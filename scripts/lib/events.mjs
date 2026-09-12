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
 * Returns `{ threadId, terminal, usage, errorMessage, errorCode, agentMessage, malformedLines }`
 * where `terminal` is
 * `"completed"`, `"failed"`, or `null` when no terminal event was seen at all.
 */
/**
 * The verdict line of an assistant message, or `null` when it carries none (vibe-305).
 *
 * ONE rule, two callers: the Stop gate parses a verdict out of a capture, and `resultLine` projects
 * the same verdict onto the wire. Two copies of this rule would be a second derivation of one fact —
 * exactly the defect vibe-305 exists to remove — so it lives here and both callers import it.
 *
 * The rule is the gate's, unchanged: the first line that is non-empty after trimming, kept only if it
 * matches `VERDICT_RE`. `.` cannot cross a line terminator, so a line carrying U+2028/U+2029 does not
 * match and is reported as no verdict — the same answer the gate gives today.
 */
export const VERDICT_RE = /^(ALLOW|BLOCK):\s*(.*)$/;

export function verdictLineOf(text) {
  if (text === null || text === undefined) return null;
  const first = String(text).split("\n").map((l) => l.trim()).find((l) => l.length > 0) ?? "";
  return VERDICT_RE.test(first) ? first : null;
}

/** `{verdict, reason}` for a line that carries one, else `null`. Null-safe by design: the wire's
 *  `verdictLine` is `null` whenever the untruncated stream carried no verdict. */
export function parseVerdictLine(line) {
  if (line === null || line === undefined) return null;
  const match = VERDICT_RE.exec(String(line));
  return match ? { verdict: match[1], reason: match[2] } : null;
}

/**
 * The verdict a result line carries, preferring what the runner already derived (vibe-305).
 *
 * **Precedence is by property PRESENCE, not truthiness.** A line that HAS `verdictLine` is
 * authoritative even when the value is `null` — `null` means "the untruncated stream carried no
 * verdict", which is an answer, not a gap. Only a line written before this key existed lacks the
 * property, and only that falls back to re-parsing the capture. A falsiness test would let an
 * authoritative `null` resurrect a stale verdict out of a bounded `rawOutput`.
 */
export function verdictFromResult(result) {
  if (result && Object.hasOwn(result, "verdictLine")) return parseVerdictLine(result.verdictLine);
  return parseVerdictLine(verdictLineOf(readEventStream(result?.rawOutput).agentMessage));
}

export function readEventStream(raw) {
  let threadId = null;
  let terminal = null;
  let usage = null;
  let errorMessage = null;
  let errorCode = null;
  // The verdict text. `null` means no `agent_message` item arrived at all, which is a different
  // fact from one arriving empty — the distinction the Output capture obligation exists to preserve.
  let agentMessage = null;
  let malformedLines = 0;

  for (const line of String(raw ?? "").split("\n")) {
    if (!line.trim()) continue;
    const event = parseLine(line);
    if (event === null) {
      malformedLines += 1;
      continue;
    }
    if (event.type === "item.completed" && event.item?.type === "agent_message") {
      // Last one wins: a turn may emit several, and the final assistant message is the verdict.
      agentMessage = event.item.text ?? agentMessage;
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

  return { threadId, terminal, usage, errorMessage, errorCode, agentMessage, malformedLines };
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

// ---- M6 / vibe-218: the ONE quota/auth vocabulary and the predicates over it. Three consumers used to carry
// three tables of three kinds (codex error codes + regexes over an event stream; plain-text substrings;
// status-signature substrings). They live here now; each consumer keeps its matching policy.

/** An exhausted allowance, or a substantive rejection?
 *
 * The contract calls this row "the one most easily collapsed into the others and the one that must
 * not be": a quota is retryable later, a rejection is a judgement, and a loop that confuses them
 * either retries a verdict or abandons a round it could have finished.
 *
 * **Structured fields first.** A `code` or `type` on the error is machine-set and stable; prose is
 * neither. Phrase matching is the fallback for backends that supply only a message, and it is a
 * table so a new variant is a data change.
 */
export const QUOTA_CODES = new Set([
  "insufficient_quota", "quota_exceeded", "rate_limit_exceeded", "resource_exhausted",
  "usage_limit_reached", "too_many_requests",
]);
export const QUOTA_PHRASES = [
  /\bquota\b/i, /\brate.?limit/i, /\busage (?:limit|cap)\b/i, /\bexceeded your\b/i,
  /\btoo many requests\b/i, /\bresource exhausted\b/i, /\bout of credits?\b/i,
];

export function classifyFailure(events) {
  const code = String(events.errorCode ?? events.errorType ?? "").toLowerCase();
  if (code && QUOTA_CODES.has(code)) return "quota";
  const message = events.errorMessage ?? "";
  return QUOTA_PHRASES.some((pattern) => pattern.test(message)) ? "quota" : "failure";
}

/** Plain-text quota vocabulary for a lane that reports prose rather than a typed event stream. */
export const QUOTA_TEXT_MARKERS = ["quota", "resource exhausted", "rate limit"];
/** The runner's stdout auth markers — deliberately narrow: "auth" inside "author" is agent prose, not a failure. */
export const AUTH_TEXT_MARKERS = ["authentication required", "please sign in"];
/** A short status/error signature, where the bare substring is safe. */
export const AUTH_SIGNATURE_MARKERS = ["unauthenticated", "auth"];

/** True when the lower-cased text contains any marker. */
export function mentionsAny(text, markers) {
  const lowered = String(text ?? "").toLowerCase();
  return markers.some((marker) => lowered.includes(marker));
}

/** True when text reads as a quota failure: plain substrings OR codex's phrase regexes (the union preserves every pre-M6 match). */
export function mentionsQuota(text) {
  const value = String(text ?? "");
  return mentionsAny(value, QUOTA_TEXT_MARKERS) || QUOTA_PHRASES.some((pattern) => pattern.test(value));
}
