// SPDX-License-Identifier: ISC
// Unit contracts for the preflight probes (E1.3 / vibe-13), with every effect injected: `run`
// returns scripted CLI outcomes per grammar, `env` points CODEX_HOME at a temp dir. No process is
// ever spawned here — the subprocess layer is preflight-cli.test.mjs.
//
// The one rule under test everywhere: probe output is NORMALIZED AND BOUNDED. Raw CLI text is
// classified, then discarded — never echoed (fallback.md's credential rule) — and every reported
// field is an enum, a validated short token, or a capped control-free string.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { mkdirSync, writeFileSync } from "node:fs";

import path from "node:path";
import test from "node:test";

import {
  buildMatrix, AUTH_MODES, exitCodeFor, MODELS_CACHE_TTL_MS, probeCodex,
  readModelsCache, ROW_KEYS, SMOKE_RESULTS,
} from "../../scripts/lib/preflight.mjs";

function tempHome() {
  return tmpWorkspace("preflight-home-");
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

test("the codex row matches ONE exact schema, down to nested keys and types", async () => {
  // vibe-298: this pinned codex and the agy slot against the same frozen shape. The lane is gone;
  // the property is not — ROW_KEYS and the nested `models` contract still govern every row the
  // matrix carries, and a row that quietly grew or lost a key is the defect this catches.
  const { env, now } = freshCacheEnv();
  const { run } = scriptedRun(OK_ANSWERS);
  const codex = await probeCodex({ run, env, now });

  const MODEL_STATUSES = new Set(["fresh", "stale", "missing", "malformed", "pending"]);
  assert.deepEqual(Object.keys(codex), ROW_KEYS, "values are filled, never reshaped");
  assert.ok(codex.available === true || codex.available === false || codex.available === null);
  assert.ok(codex.version === null || typeof codex.version === "string");
  assert.ok(codex.auth === null || AUTH_MODES.has(codex.auth), `auth outside its enum: ${codex.auth}`);
  assert.ok(codex.smoke === null || SMOKE_RESULTS.has(codex.smoke), `smoke outside its enum: ${codex.smoke}`);
  assert.deepEqual(Object.keys(codex.models), ["status", "slugs"], "the nested models shape is part of the contract");
  assert.ok(MODEL_STATUSES.has(codex.models.status));
  assert.ok(Array.isArray(codex.models.slugs) && codex.models.slugs.every((s) => typeof s === "string"));
  assert.equal(typeof codex.detail, "string");

  const matrix = buildMatrix([codex]);
  assert.deepEqual(matrix.map((r) => r.engine), ["codex"], "one lane, and it is codex");
});
