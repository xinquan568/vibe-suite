// SPDX-License-Identifier: ISC
// Unit contracts for the preflight probes (E1.3 / vibe-13), with every effect injected: `run`
// returns scripted CLI outcomes per grammar, `env` points CODEX_HOME at a temp dir. No process is
// ever spawned here — the subprocess layer is preflight-cli.test.mjs.
//
// The one rule under test everywhere: probe output is NORMALIZED AND BOUNDED. Raw CLI text is
// classified, then discarded — never echoed (fallback.md's credential rule) — and every reported
// field is an enum, a validated short token, or a capped control-free string.

import { strict as assert } from "node:assert";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import {
  agyRow, buildMatrix, AUTH_MODES, MODELS_CACHE_TTL_MS, probeAgy, probeCodex, readModelsCache,
  ROW_KEYS, SMOKE_RESULTS,
} from "../../scripts/lib/preflight.mjs";

function tempHome() {
  return mkdtempSync(path.join(tmpdir(), "preflight-home-"));
}

function writeCache(home, payload) {
  mkdirSync(home, { recursive: true });
  writeFileSync(path.join(home, "models_cache.json"),
    typeof payload === "string" ? payload : JSON.stringify(payload));
}

/** Scripted `run`: answers by grammar, records calls. */
function scriptedRun(answers) {
  const calls = [];
  return {
    calls,
    run: async (args) => {
      const key = args[0] === "exec" ? "exec" : args[0] === "login" ? "login" : args[0];
      calls.push(key);
      return {
        exitCode: 0, stdout: "", stderr: "", timedOut: false, spawnFailed: false,
        groupReaped: true,          // the real detached path always reports a boolean
        ...(answers[key] ?? {}),
      };
    },
  };
}

const OK_ANSWERS = {
  "--version": { stdout: "codex-cli 0.144.6\n" },
  login: { stdout: "Logged in using ChatGPT\n" },
  exec: { stdout: '{"type":"thread.started"}\n{"type":"turn.completed","usage":{}}\n' },
};

function freshCacheEnv(now = Date.parse("2026-07-28T00:00:00Z")) {
  const home = tempHome();
  writeCache(home, {
    fetched_at: new Date(now - 1000).toISOString(),
    models: [{ slug: "some-discovered-model" }, { slug: "another-one" }],
  });
  return { env: { CODEX_HOME: home }, now: () => now };
}

test("a healthy lane: available, enums populated, version token validated and bounded", async () => {
  const { env, now } = freshCacheEnv();
  const { run } = scriptedRun(OK_ANSWERS);
  const row = await probeCodex({ run, env, now });
  assert.equal(row.engine, "codex");
  assert.equal(row.available, true);
  assert.equal(row.version, "codex-cli 0.144.6");
  assert.equal(row.auth, "chatgpt");
  assert.equal(row.smoke, "ok");
  assert.equal(row.models.status, "fresh");
  assert.deepEqual(row.models.slugs, ["some-discovered-model", "another-one"]);
});

test("auth classification: api-key, not-authenticated, unknown — raw text never surfaces", async () => {
  const cases = [
    [{ login: { stdout: "Logged in using an API key\n" } }, "api-key"],
    [{ login: { exitCode: 1, stderr: "Not logged in. last-token=sk-HOSTILE-CREDENTIAL-LEAK\n" } }, "not-authenticated"],
    [{ login: { stdout: "session state: kaleidoscope\n" } }, "unknown"],
    [{ login: { timedOut: true, exitCode: null } }, "unknown"],
  ];
  for (const [override, expected] of cases) {
    const { env, now } = freshCacheEnv();
    const { run } = scriptedRun({ ...OK_ANSWERS, ...override });
    const row = await probeCodex({ run, env, now });
    assert.equal(row.auth, expected);
    const rendered = JSON.stringify(row);
    assert.ok(!rendered.includes("sk-HOSTILE-CREDENTIAL-LEAK"),
      "credential-shaped CLI output must be discarded after classification");
    assert.ok(!rendered.includes("kaleidoscope"),
      "unrecognized auth wording is classified, not echoed");
  }
});

test("smoke is judged by the event stream, never the exit code", async () => {
  const cases = [
    [{ exec: { stdout: '{"type":"turn.failed","error":"boom"}\n', exitCode: 0 } }, "turn-failed"],
    [{ exec: { stdout: "no events at all\n", exitCode: 0 } }, "turn-failed"],
    [{ exec: { timedOut: true, exitCode: null } }, "timeout"],
    [{ exec: { spawnFailed: true } }, "spawn-failed"],
  ];
  for (const [override, expected] of cases) {
    const { env, now } = freshCacheEnv();
    const { run } = scriptedRun({ ...OK_ANSWERS, ...override });
    const row = await probeCodex({ run, env, now });
    assert.equal(row.smoke, expected);
    assert.equal(row.available, false, "available means: the smoke proved the lane end-to-end");
  }
});

test("hostile CLI output degrades to bounded fields; no hostile byte survives", async () => {
  const noise = "\x1b[2J\x1b[31mHOSTILE ``````` " + "z".repeat(64 * 1024);
  const { env, now } = freshCacheEnv();
  const { run } = scriptedRun({
    "--version": { stdout: noise },
    login: { stdout: noise },
    exec: { stdout: noise, exitCode: 0 },
  });
  const row = await probeCodex({ run, env, now });
  assert.equal(row.version, "unknown");
  assert.equal(row.auth, "unknown");
  assert.equal(row.smoke, "turn-failed");
  const rendered = JSON.stringify(row);
  assert.ok(!rendered.includes("HOSTILE") && !rendered.includes("\\u001b") && !rendered.includes("```"),
    "raw hostile bytes must not appear in any field");
  assert.ok(rendered.length < 4096, "every field is bounded — a 64 KB CLI output cannot inflate the row");
});

test("models cache: fresh, stale, missing, malformed — and slug bounding", async () => {
  const now = Date.parse("2026-07-28T00:00:00Z");
  const fresh = tempHome();
  writeCache(fresh, { fetched_at: new Date(now - MODELS_CACHE_TTL_MS + 60_000).toISOString(),
    models: [{ slug: "fine" }] });
  assert.equal(readModelsCache({ CODEX_HOME: fresh }, { now: () => now }).status, "fresh");

  const stale = tempHome();
  writeCache(stale, { fetched_at: new Date(now - MODELS_CACHE_TTL_MS - 60_000).toISOString(),
    models: [{ slug: "old-but-listed" }] });
  const staleResult = readModelsCache({ CODEX_HOME: stale }, { now: () => now });
  assert.equal(staleResult.status, "stale");
  assert.deepEqual(staleResult.slugs, ["old-but-listed"], "stale still lists — with the stale note");

  assert.equal(readModelsCache({ CODEX_HOME: tempHome() }, { now: () => now }).status, "missing");

  const malformed = tempHome();
  writeCache(malformed, "not json {{{");
  assert.equal(readModelsCache({ CODEX_HOME: malformed }, { now: () => now }).status, "malformed");

  const hostile = tempHome();
  writeCache(hostile, { fetched_at: new Date(now).toISOString(),
    models: [{ slug: "ok-slug" }, { slug: "\x1b[31m" + "s".repeat(500) }, { slug: 42 }, {}] });
  const bounded = readModelsCache({ CODEX_HOME: hostile }, { now: () => now });
  assert.equal(bounded.slugs[0], "ok-slug");
  for (const slug of bounded.slugs) {
    assert.ok(slug.length <= 64 && !slug.includes("\x1b"), `unbounded or dirty slug: ${slug}`);
  }
});

test("groupReaped:false fails closed — a completed-looking smoke cannot make the lane available", async () => {
  const { env, now } = freshCacheEnv();
  const { run } = scriptedRun({
    ...OK_ANSWERS,
    exec: { stdout: '{"type":"turn.completed","usage":{}}\n', groupReaped: false },
  });
  const row = await probeCodex({ run, env, now });
  assert.equal(row.smoke, "reap-failed",
    "a probe whose group survived escalation broke the deadline contract — the stream cannot override that");
  assert.equal(row.available, false);

  // Missing confirmation fails closed too: only groupReaped === true counts as reaped.
  const missing = scriptedRun({
    ...OK_ANSWERS,
    exec: { stdout: '{"type":"turn.completed","usage":{}}\n', groupReaped: undefined },
  });
  const { env: env2, now: now2 } = freshCacheEnv();
  const row2 = await probeCodex({ run: missing.run, env: env2, now: now2 });
  assert.equal(row2.smoke, "reap-failed");
  assert.equal(row2.available, false);
});

test("groupReaped:false on an early probe stops the sequence — no further processes are spawned", async () => {
  const { env, now } = freshCacheEnv();
  const { run, calls } = scriptedRun({
    ...OK_ANSWERS,
    "--version": { stdout: "codex-cli 0.144.6\n", groupReaped: false },
  });
  const row = await probeCodex({ run, env, now });
  assert.equal(row.available, false);
  assert.ok(row.detail.includes("survived escalation"), row.detail);
  assert.deepEqual(calls, ["--version"], "later probes must not spawn after a reap failure");
});

test("an unexpectedly rejecting run still yields a bounded row — the matrix never dies", async () => {
  const { env, now } = freshCacheEnv();
  const row = await probeCodex({
    run: async () => { throw new Error("EPERM: something exotic"); }, env, now,
  });
  assert.equal(row.engine, "codex");
  assert.equal(row.available, false);
  assert.ok(!JSON.stringify(row).includes("exotic"), "unexpected errors are normalized, not echoed");
});

test("version is anchored and size-limited: embedded or oversized versions are refused", async () => {
  for (const stdout of [
    "warning: something\ncodex-cli 1.2.3\n",       // embedded after leading text
    "prefix codex-cli 1.2.3\n",                    // embedded mid-line
    `codex-cli ${"1".repeat(30)}.2.3\n`,           // oversized component
  ]) {
    const { env, now } = freshCacheEnv();
    const { run } = scriptedRun({ ...OK_ANSWERS, "--version": { stdout } });
    const row = await probeCodex({ run, env, now });
    assert.equal(row.version, "unknown", `accepted: ${JSON.stringify(stdout)}`);
  }
});

test("the CLI absent: available false, nothing else probed", async () => {
  const { env, now } = freshCacheEnv();
  const { run, calls } = scriptedRun({ "--version": { spawnFailed: true } });
  const row = await probeCodex({ run, env, now });
  assert.equal(row.available, false);
  assert.equal(row.version, null);
  assert.equal(row.auth, null);
  assert.equal(row.smoke, null);
  assert.deepEqual(calls, ["--version"], "absence short-circuits the remaining probes");
  assert.ok(row.detail.includes("not found"));
});

test("the agy slot and the codex row share ONE exact schema, down to nested keys and types", async () => {
  const { env, now } = freshCacheEnv();
  const { run } = scriptedRun(OK_ANSWERS);
  const codex = await probeCodex({ run, env, now });
  const agy = agyRow();

  const MODEL_STATUSES = new Set(["fresh", "stale", "missing", "malformed", "pending"]);
  for (const row of [codex, agy]) {
    assert.deepEqual(Object.keys(row), ROW_KEYS, "E1.7 fills values, never reshapes");
    assert.ok(row.available === true || row.available === false || row.available === null);
    assert.ok(row.version === null || typeof row.version === "string");
    assert.ok(row.auth === null || AUTH_MODES.has(row.auth), `auth outside its enum: ${row.auth}`);
    assert.ok(row.smoke === null || SMOKE_RESULTS.has(row.smoke), `smoke outside its enum: ${row.smoke}`);
    assert.deepEqual(Object.keys(row.models), ["status", "slugs"], "the nested models shape is part of the contract");
    assert.ok(MODEL_STATUSES.has(row.models.status));
    assert.ok(Array.isArray(row.models.slugs) && row.models.slugs.every((s) => typeof s === "string"));
    assert.equal(typeof row.detail, "string");
  }
  assert.equal(agy.available, null, "pending never counts as unavailable");
  assert.deepEqual([agy.version, agy.auth, agy.smoke], [null, null, null],
    "the slot claims nothing it has not probed");
  assert.equal(agy.models.status, "pending");
  assert.deepEqual(agy.models.slugs, []);
  assert.ok(agy.detail.includes("probe pending"),
    "agyRow() remains the pre-probe slot; probeAgy() is what E1.7 wired in");

  const matrix = buildMatrix([codex, agy]);
  assert.deepEqual(matrix.map((r) => r.engine), ["codex", "agy"]);
});

// ---------------------------------------------------------------------------------------------
// The agy matrix (E1.7 / vibe-17 closes the assertion E1.3 deferred). The row keeps the frozen
// schema and the frozen enums — a signed-out CLI is `not-authenticated`, not a new word — and the
// gate decides `pending` versus `unavailable`, because an unverified lane is not a broken one.

const GATE_OPEN = { passed: true };
const GATE_SHUT = { passed: false, reason: "checks not verified" };

function agyRun(answers) {
  return async (args) => {
    const key = args[0] === "models" ? "models" : args[0] === "--version" ? "--version" : "print";
    return {
      exitCode: 0, stdout: "", stderr: "", timedOut: false, spawnFailed: false, groupReaped: true,
      ...(answers[key] ?? {}),
    };
  };
}

const HEALTHY = {
  "--version": { stdout: "1.1.2\n" },
  print: { stdout: "ok\n" },
  models: { stdout: "gemini-a\ngemini-b\n" },
};

test("agy healthy under an OPEN gate: available, models discovered, frozen row shape", async () => {
  const row = await probeAgy({ run: agyRun(HEALTHY), gate: GATE_OPEN, env: {} });
  assert.deepEqual(Object.keys(row), ROW_KEYS);
  assert.equal(row.available, true);
  assert.equal(row.version, "1.1.2");
  assert.ok(AUTH_MODES.has(row.auth), `auth outside the frozen enum: ${row.auth}`);
  assert.equal(row.smoke, "ok");
  assert.deepEqual(row.models, { status: "fresh", slugs: ["gemini-a", "gemini-b"] });
});

test("agy healthy but the gate is SHUT: pending, never counted against the exit code", async () => {
  const row = await probeAgy({ run: agyRun(HEALTHY), gate: GATE_SHUT, env: {} });
  assert.equal(row.available, null, "an unverified lane is pending, not unavailable");
  assert.match(row.detail, /contract gate not passed/);
  assert.match(row.detail, /agy-flip-checklist/);
});

test("agy signed out: the FROZEN not-authenticated enum, with the explanation in detail", async () => {
  const row = await probeAgy({
    run: agyRun({
      ...HEALTHY,
      print: { stdout: "Authentication required. Please visit the URL to log in:\n" },
    }),
    gate: GATE_OPEN, env: {},
  });
  assert.equal(row.auth, "not-authenticated", "the frozen enum, not a new vocabulary");
  assert.ok(AUTH_MODES.has(row.auth));
  assert.equal(row.available, false);
  assert.equal(row.models.status, "missing", "`agy models` refuses when signed out");
  assert.deepEqual(row.models.slugs, [], "an empty list must not read as 'no models exist'");
  assert.match(row.detail, /blocks even with stdin closed/,
    "the OAuth block is the fact a caller most needs");
});

test("agy absent: unavailable under an open gate, pending under a shut one", async () => {
  const missing = agyRun({ "--version": { spawnFailed: true } });
  const open = await probeAgy({ run: missing, gate: GATE_OPEN, env: {} });
  assert.equal(open.available, false);
  assert.match(open.detail, /not found on PATH/);

  const shut = await probeAgy({ run: missing, gate: GATE_SHUT, env: {} });
  assert.equal(shut.available, null);
  assert.deepEqual(Object.keys(shut), ROW_KEYS, "the frozen shape holds on every path");
});
