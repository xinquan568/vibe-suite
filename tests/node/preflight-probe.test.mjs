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
  agyRow, buildMatrix, MODELS_CACHE_TTL_MS, probeCodex, readModelsCache, ROW_KEYS,
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

test("the agy slot and the codex row share ONE exact schema", async () => {
  const { env, now } = freshCacheEnv();
  const { run } = scriptedRun(OK_ANSWERS);
  const codex = await probeCodex({ run, env, now });
  const agy = agyRow();
  assert.deepEqual(Object.keys(codex), ROW_KEYS);
  assert.deepEqual(Object.keys(agy), ROW_KEYS, "E1.7 fills values, never reshapes");
  assert.equal(agy.available, null, "pending never counts as unavailable");
  assert.equal(agy.models.status, "pending");
  assert.deepEqual(agy.models.slugs, []);
  assert.ok(agy.detail.includes("probe pending"), "the acceptance's exact column wording");

  const matrix = buildMatrix([codex, agy]);
  assert.deepEqual(matrix.map((r) => r.engine), ["codex", "agy"]);
});
