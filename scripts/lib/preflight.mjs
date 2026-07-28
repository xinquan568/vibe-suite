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
export const SMOKE_RESULTS = new Set(["ok", "turn-failed", "timeout", "spawn-failed"]);

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
  if (outcome.timedOut || outcome.spawnFailed) return "unknown";
  const text = (outcome.stdout + "\n" + outcome.stderr).toLowerCase();
  if (outcome.exitCode !== 0) return "not-authenticated";
  if (text.includes("not logged in")) return "not-authenticated";
  if (text.includes("chatgpt")) return "chatgpt";
  if (text.includes("api key") || text.includes("api-key")) return "api-key";
  return "unknown";
}

function classifySmoke(outcome) {
  if (outcome.spawnFailed) return "spawn-failed";
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
  if (outcome.timedOut || outcome.spawnFailed) return "unknown";
  const match = /codex-cli (\d+\.\d+\.\d+)/.exec(outcome.stdout);
  return match ? boundToken(`codex-cli ${match[1]}`, 32) : "unknown";
}

/**
 * The codex row. `deps.run(args, timeoutMs)` is the injected effect; raw outcomes never leave this
 * function — only enums and bounded tokens do.
 */
export async function probeCodex(deps = {}) {
  const { env = process.env, now = Date.now } = deps;
  const run = deps.run ?? ((args, timeoutMs) => defaultRun(args, timeoutMs, env));

  const models = readModelsCache(env, { now });

  const versionOutcome = await run(["--version"], VERSION_TIMEOUT_MS);
  if (versionOutcome.spawnFailed) {
    return {
      engine: "codex", available: false, version: null, auth: null, smoke: null, models,
      detail: "codex CLI not found on PATH",
    };
  }
  const version = classifyVersion(versionOutcome);

  const auth = classifyAuth(await run(["login", "status"], AUTH_TIMEOUT_MS));

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
 * The agy slot (F2.7 staged rollout): same shape, no probe. E1.7 (#17) owns the agy CLI contract
 * and fills these values; until then the column reports exactly "probe pending". `available: null`
 * is load-bearing — pending never counts as unavailable in the exit code.
 */
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
