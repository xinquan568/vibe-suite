// SPDX-License-Identifier: ISC
// Command-level dispatch and F9.5 assertions for /vibe-suite:nl-audit (E4.1 / vibe-35, AC-9(b)).
//
// AC-9(b) names its mechanism: the two fallback states are "exercised via PATH manipulation
// regardless of real agy availability". Every other engine-touching test in this repository uses the
// `VIBE_SUITE_*_BIN` override seam, which is hermetic but bypasses executable discovery entirely —
// so it cannot answer the question AC-9(b) asks. These tests therefore build a temporary directory
// of executable shims, set PATH to **only** that directory, and **unset both override variables**,
// so resolution runs through ordinary command lookup.
//
// PATH is replaced rather than prepended. Prepending leaves the developer's real `codex` reachable
// behind the shim, and an "absent binary" case that silently found a real one would pass for the
// wrong reason. Each shim spawns its fake through an absolute interpreter path, because a PATH
// holding one directory cannot resolve `node` either.
//
// One state cannot be expressed through PATH: the contract gate is a committed *record*, not a
// binary, so the simulated post-flip record still arrives via VIBE_SUITE_AGY_GATE_FILE — the seam
// `agy-gate.mjs` documents for exactly this. That is a record path, not an executable lookup, so it
// does not weaken the mechanism above.
//
// **Node floor: 18.** No top-level await.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { chmodSync, readFileSync, writeFileSync } from "node:fs";

import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { MANDATORY_CHECKS } from "../../scripts/lib/agy-gate.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const AUDIT_CLI = path.join(REPO_ROOT, "scripts", "agy-audit-cli.mjs");
const CODEX_RUNNER = path.join(REPO_ROOT, "scripts", "codex-runner.mjs");
const COMMAND = path.join(REPO_ROOT, "commands", "nl-audit.md");
const FAKE_CODEX = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex", "emitter.mjs");
const FAKE_AGY = path.join(REPO_ROOT, "tests", "fixtures", "fake-agy", "writer.mjs");

/**
 * A PATH containing exactly the named engine shims, plus `python3`.
 *
 * `python3` is not an engine and is not part of the fixture: `codex-runner.mjs` reads project
 * configuration through `scripts/lib/config-bridge.mjs`, which shells out to the suite's single
 * config reader. With a one-directory PATH the runner cannot find an interpreter and fails before it
 * ever looks for an engine — which would make every case below pass or fail for a reason that has
 * nothing to do with engine discovery. It is a **passthrough** to the real interpreter, resolved
 * once from the current PATH, so it grants the child nothing this process did not already have and
 * leaves no engine reachable.
 */
const REAL_PYTHON3 = (() => {
  const found = spawnSync("sh", ["-c", "command -v python3"], { encoding: "utf8" });
  const resolved = (found.stdout || "").trim();
  assert.ok(resolved, "python3 must be on PATH to build the shim directory");
  return resolved;
})();

function shimPath(shims) {
  const dir = tmpWorkspace("nl-audit-path-");
  const write = (name, line) => {
    const file = path.join(dir, name);
    writeFileSync(file, `#!/bin/sh\n${line}\n`);
    chmodSync(file, 0o755);
  };
  // Engine shims run their fake through an absolute interpreter path: a PATH holding only this
  // directory cannot resolve `node` either.
  for (const [name, target] of Object.entries(shims)) {
    write(name, `exec ${JSON.stringify(process.execPath)} ${JSON.stringify(target)} "$@"`);
  }
  write("python3", `exec ${JSON.stringify(REAL_PYTHON3)} "$@"`);
  return dir;
}

function openGate() {
  const file = path.join(tmpWorkspace("nl-audit-gate-"), "gate-status.json");
  writeFileSync(file, JSON.stringify({
    schema: 1, status: "passed", agy_version: "1.1.2", recorded_at: "2026-07-28T00:00:00Z",
    checks: Object.fromEntries(MANDATORY_CHECKS.map((n) => [n, { state: "passed", note: "simulated" }])),
  }));
  return file;
}

/**
 * Run a script with PATH holding only the given shims. Both binary overrides are deleted from the
 * environment — if either survived, the test would be exercising the seam it exists to avoid.
 */
function runOnPath(script, args, { shims = {}, gate = null } = {}) {
  const cwd = tmpWorkspace("nl-audit-ws-");
  const env = { ...process.env, PATH: shimPath(shims) };
  delete env.VIBE_SUITE_AGY_BIN;
  delete env.VIBE_SUITE_CODEX_BIN;
  delete env.VIBE_SUITE_AGY_GATE_FILE;
  if (gate) env.VIBE_SUITE_AGY_GATE_FILE = gate;
  const result = spawnSync(process.execPath, [script, ...args], {
    cwd, encoding: "utf8", timeout: 90_000, env,
  });
  return { ...result, cwd, env };
}

const PROMPT = ["--", "audit this repository"];

// --- the mechanism itself -----------------------------------------------------------------------

test("the harness really does use PATH: no binary override survives into the child", () => {
  const { env } = runOnPath(CODEX_RUNNER, ["--sandbox", "read-only", "--kind", "audit", ...PROMPT],
    { shims: { codex: FAKE_CODEX } });
  assert.equal(env.VIBE_SUITE_CODEX_BIN, undefined);
  assert.equal(env.VIBE_SUITE_AGY_BIN, undefined);
  assert.equal(env.PATH.split(path.delimiter).length, 1, "PATH must hold exactly the shim dir");
});

test("an absent engine is genuinely absent: no real binary is reachable on the shim PATH", () => {
  // Without this, a case that expects "codex is missing" could silently find the developer's real
  // installation and pass for the wrong reason. PATH is replaced rather than prepended precisely so
  // this assertion can hold.
  const dir = shimPath({});
  for (const engine of ["codex", "agy"]) {
    const found = spawnSync("sh", ["-c", `command -v ${engine}`],
      { encoding: "utf8", env: { ...process.env, PATH: dir } });
    assert.equal((found.stdout || "").trim(), "", `${engine} must not be reachable`);
  }
});

// --- the v1 codex lane (the defect the plan review caught) --------------------------------------

test("pre-gate default lane: codex answers directly, without the gate refusing it", () => {
  const result = runOnPath(CODEX_RUNNER, ["--sandbox", "read-only", "--kind", "audit", ...PROMPT],
    { shims: { codex: FAKE_CODEX } });
  assert.equal(result.status, 0, `${result.stdout}${result.stderr}`);
  const line = result.stdout.trim().split("\n").filter(Boolean).at(-1);
  assert.equal(JSON.parse(line).status, "completed",
    "the v1 default lane must reach codex; routing it through the gated audit CLI would exit 2");
});

test("pre-gate explicit agy: refused with the gate status, nothing dispatched", () => {
  const result = runOnPath(AUDIT_CLI, PROMPT, { shims: { agy: FAKE_AGY, codex: FAKE_CODEX } });
  assert.equal(result.status, 2, `${result.stdout}${result.stderr}`);
  assert.match(result.stderr, /gated shut/);
  assert.match(result.stderr, /agy-flip-checklist/);
  assert.equal(result.stdout.trim(), "",
    "a refusal is not a degradation: nothing may reach stdout");
});

// --- AC-9(b): the two post-flip states, through PATH --------------------------------------------

const HEADER_FIELDS = [/binary on PATH/i, /authentication/i, /suggested fix/i];

test("post-flip, agy absent from PATH: codex answers, with the three-field diagnostic header", () => {
  const result = runOnPath(AUDIT_CLI, PROMPT, { shims: { codex: FAKE_CODEX }, gate: openGate() });
  assert.equal(result.status, 0, `${result.stdout}${result.stderr}`);
  const line = result.stdout.trim().split("\n").filter(Boolean).at(-1);
  assert.equal(JSON.parse(line).status, "completed", "codex's result belongs on stdout");
  for (const field of HEADER_FIELDS) {
    assert.match(result.stderr, field,
      `the diagnostic header must carry every field commands/shared/fallback.md specifies`);
  }
});

test("post-flip, both absent from PATH: manual fallback signal, exit 3, header retained", () => {
  const result = runOnPath(AUDIT_CLI, PROMPT, { shims: {}, gate: openGate() });
  assert.equal(result.status, 3, `${result.stdout}${result.stderr}`);
  const signal = JSON.parse(result.stdout.trim().split("\n").filter(Boolean).at(-1));
  assert.equal(signal.fallback, "manual");
  for (const field of HEADER_FIELDS) {
    assert.match(result.stderr, field);
  }
});

test("the header names an engine and a remedy a user can act on now", () => {
  const result = runOnPath(AUDIT_CLI, PROMPT, { shims: {}, gate: openGate() });
  assert.match(result.stderr, /codex/i, "the header must name which engine was unreachable");
  assert.match(result.stderr, /npm install -g @openai\/codex|codex login|preflight/i,
    "the suggested fix must be an actionable command, not a description of the problem");
});

// --- the command artifact's half of "command-level" ----------------------------------------------

test("the command binds the dispatch paths and the degradation contract", () => {
  const text = readFileSync(COMMAND, "utf8");
  assert.match(text, /scripts\/codex-runner\.mjs/, "the codex lane's dispatch must be named");
  assert.match(text, /scripts\/agy-audit-cli\.mjs/, "the graduated agy lane's dispatch must be named");
  assert.match(text, /commands\/shared\/fallback\.md/, "the degradation contract must be bound");
});
