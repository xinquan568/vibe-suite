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
import { STAGED_NOTICE } from "./agy-gate.mjs";

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
        : `agy CLI not found on PATH · ${STAGED_NOTICE} · contract gate not passed — `
          + "see docs/agy-flip-checklist.md",
    };
  }
  const version = boundToken((versionOutcome.stdout ?? "").trim().split("\n")[0] ?? "", 32) || "unknown";

  const smokeOutcome = await run(["--sandbox", "--print", "reply with: ok"], SMOKE_TIMEOUT_MS);
  const text = `${smokeOutcome.stdout ?? ""}\n${smokeOutcome.stderr ?? ""}`.toLowerCase();
  const signedOut = text.includes("authentication required") || text.includes("please sign in");

  let auth = "unknown";
  let smoke = "turn-failed";
  if (smokeOutcome.spawnFailed) {
    smoke = "spawn-failed";
  } else if (smokeOutcome.groupReaped !== true) {
    // Confirmation first, and `=== true` only: an unreaped group is not a healthy lane whatever the
    // output said, and a missing confirmation is not a confirmation.
    smoke = "reap-failed";
  } else if (signedOut) {
    auth = "not-authenticated";
    smoke = "turn-failed";                // set here, not in a trailing override that masked the reap
  } else if (smokeOutcome.timedOut) {
    smoke = "timeout";
  } else if ((smokeOutcome.stdout ?? "").trim()) {
    // The service answered, but agy exposes no auth MODE. Reporting `api-key` would be inventing an
    // observation; `unknown` is the true one.
    auth = "unknown";
    smoke = "ok";
  }

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
    detail: gateOpen
      ? detail
      : `${detail} · ${STAGED_NOTICE} · contract gate not passed — see docs/agy-flip-checklist.md`,
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


/**
 * The runtime rows (vibe-209 / grill P4).
 *
 * The matrix probed AI engines only, so a missing `python3`, `node` or `git` first announced itself
 * as a stack trace mid-run, or as a silent fail-open. Every Node dispatch shells to `python3`, the
 * Python `update` stage shells to `node`, and the Stop gate shells to `git`.
 *
 * **These rows are not engines, and the difference is load-bearing.** They carry `runtime` instead
 * of `engine`, and `auth: null` instead of `auth: "unknown"`. `exitCodeFor` ends with
 * `row.engine !== "agy" && row.auth === "unknown"` — an exception hard-coded to ONE engine name,
 * because agy exposes no auth mode and `"unknown"` is its truthful terminal answer rather than a
 * failed probe. `git` is in exactly that position and is not named there, so reporting the honest
 * `"unknown"` would fail preflight on a healthy machine. The schema already has the right word:
 * `null` means *there is nothing here to learn*, which is why `exitCodeFor` needs no change at all.
 */

/** Floors from the project's own prerequisites. `null` means "any version, just be present". */
export const RUNTIME_FLOORS = {
  python3: [3, 11],
  node: [18],
  git: null,
};

/** Fixed order, so the matrix reads the same way every time. */
export const RUNTIME_NAMES = ["python3", "node", "git"];

/**
 * Each runtime's own `--version` grammar, anchored to the start of a line.
 *
 * **Not "the first dotted number anywhere".** That accepted `wrapper 9.0 warning; Python 3.9.18` as
 * version 9.0 — clearing a 3.11 floor while the actual interpreter was 3.9.18, so preflight called
 * a machine healthy that was not. Anything a wrapper prints ahead of the real banner is noise, and
 * only the runtime's documented form counts.
 */
// `(?!\d)` after every component, and it is load-bearing. Without it `\d{1,4}` TRUNCATES rather
// than rejects: `Python 3.12345` matched as 3.1234 — not a display artefact but a *fabricated*
// version, handed to the floor comparison as if it were read. An implausible component means the
// output is not the banner it looks like, and the honest answer is to fail closed.
const RUNTIME_VERSION_PATTERNS = {
  python3: /^Python (\d{1,4})(?!\d)\.(\d{1,4})(?!\d)(?:\.(\d{1,4})(?!\d))?/m,
  node: /^v(\d{1,4})(?!\d)\.(\d{1,4})(?!\d)(?:\.(\d{1,4})(?!\d))?/m,
  git: /^git version (\d{1,4})(?!\d)\.(\d{1,4})(?!\d)(?:\.(\d{1,4})(?!\d))?/m,
};

/**
 * The runtime's version as integer components, or `null` when its banner is not there.
 *
 * Components are bounded to four digits by the patterns above: an absurd component is a sign the
 * output is not what it claims to be, and `Number` on an arbitrarily long digit run is a value no
 * floor comparison should be asked to interpret.
 */
function parseVersion(name, text) {
  const pattern = RUNTIME_VERSION_PATTERNS[name];
  if (!pattern) return null;
  const match = pattern.exec(String(text ?? ""));
  if (!match) return null;
  return [match[1], match[2], match[3] ?? "0"].map(Number);
}

/**
 * Is `found` at least `floor`, comparing component by component?
 *
 * **Not a decimal comparison.** `parseFloat("3.9") > parseFloat("3.11")` is `true`, so a float
 * compare accepts Python 3.9 as meeting a 3.11 floor — the single likeliest defect here, and the
 * reason this is written out rather than inlined. `>=` at every position, so the floor itself passes.
 */
function meetsFloor(found, floor) {
  if (floor === null) return true;
  for (let i = 0; i < floor.length; i += 1) {
    const have = found[i] ?? 0;
    if (have > floor[i]) return true;
    if (have < floor[i]) return false;
  }
  return true;                                   // equal through the floor's components: it meets it
}

const floorText = (floor) => (floor === null ? null : floor.join("."));

/** The default effect: run `<name> --version` on PATH, bounded by the same deadline as the engines. */
async function defaultRuntimeRun(name, timeoutMs, env) {
  try {
    // `detached: true`, like the engine probes. A runtime on PATH may be a wrapper script that
    // spawns descendants, and only a group-wide deadline reaps those; a non-detached kill leaves
    // them holding the inherited pipes. The engine lanes already learned this (E1.3 / vibe-13).
    return await runWithDeadline({ command: name, args: ["--version"], env, timeoutMs,
      detached: true });
  } catch (error) {
    if (error?.code === "ENOENT" || error?.code === "EACCES") {
      return { exitCode: null, stdout: "", stderr: "", timedOut: false, spawnFailed: true };
    }
    throw error;
  }
}

/**
 * One runtime row. Shape mirrors an engine row where the fields mean the same thing, and omits the
 * ones that do not exist for a runtime (`smoke`, `models`).
 */
export async function probeRuntime(name, deps = {}) {
  const { env = process.env } = deps;
  const run = deps.run ?? ((timeoutMs) => defaultRuntimeRun(name, timeoutMs, env));
  const floor = RUNTIME_FLOORS[name] ?? null;
  const wanted = floorText(floor);

  const outcome = await run(VERSION_TIMEOUT_MS);
  if (outcome.spawnFailed) {
    return {
      runtime: name, available: false, version: null, auth: null,
      detail: wanted ? `not found on PATH (needs ${name} ${wanted} or newer)`
                     : `not found on PATH (needs ${name})`,
    };
  }
  if (outcome.timedOut) {
    return { runtime: name, available: false, version: "unknown", auth: null,
      detail: `${name} --version did not return within the probe deadline` };
  }

  // Confirmation, not a timer: an unreaped group means descendants may still be running, and a
  // probe that could not be bounded is not a probe that succeeded.
  if (outcome.groupReaped !== true) {
    return { runtime: name, available: false, version: "unknown", auth: null,
      detail: `${name} --version could not be confirmed reaped — investigate before trusting it` };
  }
  // A non-zero exit means the command FAILED, whatever it printed on the way. Reporting a runtime
  // as available because a failing invocation happened to mention a version is the same class of
  // defect as reading a verdict out of a stream instead of an assistant message.
  if (outcome.exitCode !== 0) {
    return { runtime: name, available: false, version: "unknown", auth: null,
      detail: `${name} --version exited ${outcome.exitCode}` };
  }

  // Both streams: `python3 --version` printed to stderr on 3.3 and earlier, and a wrapper may still.
  const text = `${outcome.stdout ?? ""}\n${outcome.stderr ?? ""}`.trim();
  const parsed = parseVersion(name, text);
  if (parsed === null) {
    return { runtime: name, available: false, version: "unknown", auth: null,
      detail: `could not read a ${name} version banner from --version` };
  }
  // The reported token is the matched BANNER, not the first line: a wrapper's own chatter has no
  // business in the matrix. No `boundToken` here, deliberately — the anchored pattern IS the bound.
  // It matches a fixed literal plus components of at most four digits, so the result cannot exceed
  // ~30 characters and cannot contain a control character. Passing it through `boundToken` would be
  // a line no input can change, which the mutation ledger correctly refused to certify.
  const version = RUNTIME_VERSION_PATTERNS[name].exec(text)[0];

  const ok = meetsFloor(parsed, floor);
  return {
    runtime: name,
    available: ok,
    version,
    // `null`, never `"unknown"` — see the note above `RUNTIME_FLOORS`.
    auth: null,
    detail: ok
      ? (wanted ? `meets the ${wanted} floor` : "present")
      : `below the ${wanted} floor — found ${parsed.join(".")}`,
  };
}

/** Every runtime row, in fixed order. */
export async function probeRuntimes(deps = {}) {
  const rows = [];
  for (const name of RUNTIME_NAMES) rows.push(await probeRuntime(name, deps));
  return rows;
}

/**
 * The exit rule, unchanged by vibe-209 and deliberately so.
 *
 * Runtime rows are counted by the two rules that apply to them — `available !== true` and
 * `version === "unknown"` — and slip past the third because they carry `auth: null` rather than
 * `auth: "unknown"`. That is not a workaround: `null` means "there is nothing here to learn", which
 * is the truth for a tool with no auth mode, while `"unknown"` means "a probe failed to learn
 * something knowable" and rightly fails a preflight.
 *
 * Exported so a test can pin that reasoning directly — see R-AUTH in preflight-cli.test.mjs.
 */
export function exitCodeFor(rows) {
  for (const row of rows) {
    if (row.available === null) continue;              // pending never counts against
    if (row.available !== true) return 1;
    // A degraded probe is one that FAILED TO LEARN something knowable. `auth: "unknown"` means that
    // for codex, which exposes its auth mode — but agy exposes none, so `unknown` there is the
    // truthful terminal answer, not a failure to look. Treating them alike would fail a preflight
    // over a fact that cannot be discovered.
    if (row.version === "unknown") return 1;
    if (row.engine !== "agy" && row.auth === "unknown") return 1;
  }
  return 0;
}

/** The matrix: rows in fixed engine order, each already normalized. */
export function buildMatrix(rows) {
  return rows;
}
