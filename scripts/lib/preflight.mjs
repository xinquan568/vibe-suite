// SPDX-License-Identifier: ISC
// Engine-readiness probes for /vibe-suite:preflight (E1.3 / vibe-13, implements F1.5).
//
// Two rules govern every line here:
//
// 1. **Output is normalized and bounded.** Raw CLI text is used for classification and then
//    DISCARDED — `commands/shared/fallback.md` forbids echoing command output that may carry
//    credentials, and fencing does not fix disclosure; only non-echo does. Every reported field is
//    an enum, a validated short token, or a capped control-stripped string.
// 2. **Zero model names (P9).** Discovery reads whatever `models_cache.json` holds and reports it
//    as data. There is no known-good list, no fallback slug, no validation against names.
//
// The smoke is judged by the event stream, never the exit code (the E1.1 lesson: codex-cli exits 0
// on upstream failure while emitting `turn.failed`). All external calls run deadline-bounded and
// detached, so a hanging CLI cannot outlive its deadline even with descendants.

import { homedir } from "node:os";
import { readFileSync } from "node:fs";
import path from "node:path";

import { runWithDeadline } from "./process.mjs";

export const MODELS_CACHE_TTL_MS = 24 * 60 * 60 * 1000;
export const ROW_KEYS = ["engine", "available", "version", "auth", "smoke", "models", "detail"];
export const AUTH_MODES = new Set(["chatgpt", "api-key", "not-authenticated", "unknown"]);
export const SMOKE_RESULTS = new Set(["ok", "turn-failed", "timeout", "spawn-failed", "reap-failed"]);

const VERSION_TIMEOUT_MS = 10_000;
const AUTH_TIMEOUT_MS = 10_000;
const SMOKE_TIMEOUT_MS = 60_000;
const TOKEN_CAP = 64;
const SLUG_COUNT_CAP = 50;

/** Cap and clean a value destined for the matrix: printable, control-free, bounded. */
function boundToken(value, cap = TOKEN_CAP) {
  if (typeof value !== "string") return null;
  const clean = value
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, "")
    .replace(/[\x00-\x1f\x7f-\u009f]/g, "");
  return clean.length > cap ? clean.slice(0, cap) : clean;
}

export function codexHome(env) {
  return env.CODEX_HOME ?? path.join(env.HOME ?? homedir(), ".codex");
}

/**
 * The models cache, read as local data. The cache belongs to the codex CLI — preflight never
 * fetches the network; staleness is reported, not repaired.
 */
export function readModelsCache(env, { now = Date.now } = {}) {
  const nowMs = typeof now === "function" ? now() : now;
  let raw;
  try {
    raw = readFileSync(path.join(codexHome(env), "models_cache.json"), "utf8");
  } catch {
    return { status: "missing", slugs: [] };
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { status: "malformed", slugs: [] };
  }
  const fetchedAt = Date.parse(parsed?.fetched_at);
  if (!Array.isArray(parsed?.models) || Number.isNaN(fetchedAt)) {
    return { status: "malformed", slugs: [] };
  }
  const slugs = parsed.models
    .map((model) => boundToken(model?.slug))
    .filter((slug) => typeof slug === "string" && slug.length > 0)
    .slice(0, SLUG_COUNT_CAP);
  const status = nowMs - fetchedAt <= MODELS_CACHE_TTL_MS ? "fresh" : "stale";
  return { status, slugs };
}

/** The agy effect: same discipline, different binary and seam. */
async function defaultAgyRun(args, timeoutMs, env) {
  try {
    return await runWithDeadline({
      command: env.VIBE_SUITE_AGY_BIN ?? "agy",
      args, env, timeoutMs,
      detached: true,        // agy blocks on OAuth regardless of stdin: only a group kill bounds it
    });
  } catch (error) {
    if (error?.code === "ENOENT" || error?.code === "EACCES") {
      return { exitCode: null, stdout: "", stderr: "", timedOut: false, spawnFailed: true };
    }
    throw error;
  }
}

/** The default effect: the codex binary (seam-overridable), detached, deadline-bounded. */
async function defaultRun(args, timeoutMs, env) {
  try {
    return await runWithDeadline({
      command: env.VIBE_SUITE_CODEX_BIN ?? "codex",
      args,
      env,
      timeoutMs,
      detached: true,
    });
  } catch (error) {
    if (error?.code === "ENOENT" || error?.code === "EACCES") {
      return { exitCode: null, stdout: "", stderr: "", timedOut: false, spawnFailed: true };
    }
    throw error;
  }
}

function classifyAuth(outcome) {
  if (outcome.timedOut || outcome.spawnFailed || outcome.groupReaped !== true) return "unknown";
  const text = (outcome.stdout + "\n" + outcome.stderr).toLowerCase();
  if (outcome.exitCode !== 0) return "not-authenticated";
  if (text.includes("not logged in")) return "not-authenticated";
  if (text.includes("chatgpt")) return "chatgpt";
  if (text.includes("api key") || text.includes("api-key")) return "api-key";
  return "unknown";
}

function classifySmoke(outcome) {
  if (outcome.spawnFailed) return "spawn-failed";
  // Fail closed: only a CONFIRMED reap counts. `false` means the group survived escalation;
  // anything else (missing, null) means confirmation never happened — either way, whatever the
  // stream said cannot make the lane "ok" while descendants may still be alive.
  if (outcome.groupReaped !== true) return "reap-failed";
  if (outcome.timedOut) return "timeout";
  for (const line of outcome.stdout.split("\n")) {
    try {
      const event = JSON.parse(line);
      if (event?.type === "turn.completed") return "ok";
      if (event?.type === "turn.failed") return "turn-failed";
    } catch {
      // Interleaved diagnostics are expected; only parseable events decide.
    }
  }
  return "turn-failed";
}

function classifyVersion(outcome) {
  if (outcome.timedOut || outcome.spawnFailed || outcome.groupReaped !== true) return "unknown";
  // Anchored, not substring: a valid-looking version embedded in arbitrary leading text is
  // arbitrary text. Oversized components are refused, never truncated into a plausible lie.
  const match = /^codex-cli (\d+\.\d+\.\d+)\b/.exec(outcome.stdout.trim());
  if (!match || match[1].length > 20) return "unknown";
  return `codex-cli ${match[1]}`;
}

/**
 * The codex row. `deps.run(args, timeoutMs)` is the injected effect; raw outcomes never leave this
 * function — only enums and bounded tokens do.
 */
export async function probeCodex(deps = {}) {
  const { env = process.env, now = Date.now } = deps;
  const rawRun = deps.run ?? ((args, timeoutMs) => defaultRun(args, timeoutMs, env));
  // The matrix must survive ANY probe failure: an unexpected subprocess error becomes a bounded
  // spawn-failed outcome, never a stack trace in place of the report.
  const run = async (args, timeoutMs) => {
    try {
      return await rawRun(args, timeoutMs);
    } catch {
      return { exitCode: null, stdout: "", stderr: "", timedOut: false, spawnFailed: true };
    }
  };

  const models = readModelsCache(env, { now });

  const versionOutcome = await run(["--version"], VERSION_TIMEOUT_MS);
  if (versionOutcome.spawnFailed) {
    return {
      engine: "codex", available: false, version: null, auth: null, smoke: null, models,
      detail: "codex CLI not found on PATH",
    };
  }
  // Fail closed on a broken deadline contract: if this probe's group survived escalation, later
  // probes would spawn more of the same — stop, report, investigate.
  if (versionOutcome.groupReaped !== true) {
    return {
      engine: "codex", available: false, version: "unknown", auth: null, smoke: null, models,
      detail: "probe process group survived escalation — investigate before trusting this lane",
    };
  }
  const version = classifyVersion(versionOutcome);

  const authOutcome = await run(["login", "status"], AUTH_TIMEOUT_MS);
  const auth = classifyAuth(authOutcome);
  if (authOutcome.groupReaped !== true) {
    return {
      engine: "codex", available: false, version, auth: "unknown", smoke: null, models,
      detail: "probe process group survived escalation — investigate before trusting this lane",
    };
  }

  const smoke = classifySmoke(await run([
    "exec", "-s", "read-only", "--skip-git-repo-check", "-c", "reasoning.effort=low", "--json",
    "reply with: ok",
  ], SMOKE_TIMEOUT_MS));

  // Available means: the smoke proved the lane end-to-end. Version and auth inform, the smoke
  // decides — a lane whose exec path is broken is unavailable no matter what `login status` says.
  const available = smoke === "ok";
  const detail = available
    ? "ready"
    : auth === "not-authenticated" ? "not authenticated"
      : `smoke failed (${smoke})`;

  return { engine: "codex", available, version, auth, smoke, models, detail };
}

/**
 * The agy row (E1.7 / vibe-17 fills the slot E1.3 froze — same ROW_KEYS, same enums, values now
 * observed rather than pending).
 *
 * Two shapes of honesty live here. **While the contract gate is shut, `available` stays `null`**:
 * the lane is not unavailable, it is not yet permitted, and reporting `false` would read as "agy is
 * broken" when the truth is "agy has not been verified". And a **signed-out CLI is
 * `not-authenticated`** — the frozen enum, not a new word — with the explanation in `detail`, so
 * consumers that switch on `auth` keep working.
 */
export async function probeAgy(deps = {}) {
  const { env = process.env, now = Date.now, gate = null } = deps;
  const run = deps.run ?? ((args, timeoutMs) => defaultAgyRun(args, timeoutMs, env));
  void now;

  const gateOpen = gate?.passed === true;

  const versionOutcome = await run(["--version"], VERSION_TIMEOUT_MS);
  if (versionOutcome.spawnFailed) {
    return {
      engine: "agy",
      // Gate shut ⇒ pending even when the binary is missing: an unverified lane that nobody may
      // use is not a broken dependency, and reporting `false` would fail an exit code over it.
      available: gateOpen ? false : null,
      version: null, auth: null, smoke: null,
      models: { status: gateOpen ? "missing" : "pending", slugs: [] },
      detail: gateOpen
        ? "agy CLI not found on PATH"
        : "agy CLI not found on PATH · contract gate not passed — see docs/agy-flip-checklist.md",
    };
  }
  const version = boundToken((versionOutcome.stdout ?? "").trim().split("\n")[0] ?? "", 32) || "unknown";

  const smokeOutcome = await run(["--sandbox", "--print", "reply with: ok"], SMOKE_TIMEOUT_MS);
  const text = `${smokeOutcome.stdout ?? ""}\n${smokeOutcome.stderr ?? ""}`.toLowerCase();
  const signedOut = text.includes("authentication required") || text.includes("please sign in");

  let auth = "unknown";
  let smoke = "turn-failed";
  if (signedOut) {
    auth = "not-authenticated";
  } else if (smokeOutcome.timedOut) {
    smoke = "timeout";
  } else if (smokeOutcome.spawnFailed) {
    smoke = "spawn-failed";
  } else if (smokeOutcome.groupReaped !== undefined && smokeOutcome.groupReaped !== true) {
    smoke = "reap-failed";                // the group survived escalation: not a healthy lane
  } else if ((smokeOutcome.stdout ?? "").trim()) {
    // The service answered, but agy exposes no auth MODE. Reporting `api-key` would be inventing an
    // observation; `unknown` is the true one.
    auth = "unknown";
    smoke = "ok";
  }
  if (signedOut) smoke = "turn-failed";

  // `agy models` refuses when signed out. An empty list would read as "this engine has no models".
  let models = { status: "missing", slugs: [] };
  if (!signedOut) {
    const listed = await run(["models"], VERSION_TIMEOUT_MS);
    const slugs = String(listed.stdout ?? "").split("\n")
      .map((line) => boundToken(line.trim()))
      .filter((slug) => slug && !slug.toLowerCase().startsWith("error"))
      .slice(0, SLUG_COUNT_CAP);
    if (slugs.length > 0) models = { status: "fresh", slugs };
  }

  const detail = signedOut
    ? "not authenticated: agy prints an OAuth prompt and blocks even with stdin closed; "
      + "`agy models` is unavailable until you sign in"
    : smoke === "ok" ? "ready" : `smoke failed (${smoke})`;

  return {
    engine: "agy",
    // Gate shut ⇒ pending (null), never "unavailable": the lane is unverified, not broken.
    available: gateOpen ? smoke === "ok" : null,
    version, auth, smoke, models,
    detail: gateOpen ? detail : `${detail} · contract gate not passed — see docs/agy-flip-checklist.md`,
  };
}

/** The pre-E1.7 static slot, kept for callers that report before any probe runs. */
export function agyRow() {
  return {
    engine: "agy", available: null, version: null, auth: null, smoke: null,
    models: { status: "pending", slugs: [] },
    detail: "probe pending — contract lands in E1.7 (#17)",
  };
}

/** The matrix: rows in fixed engine order, each already normalized. */
export function buildMatrix(rows) {
  return rows;
}
