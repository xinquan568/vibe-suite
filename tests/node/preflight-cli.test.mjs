// SPDX-License-Identifier: ISC
// End-to-end subprocess tests for the /vibe-suite:preflight CLI (E1.3 / vibe-13).
//
// The acceptance's present/absent matrix is exercised with REAL PATH manipulation — present is an
// executable named `codex` in a temp bin dir on a controlled PATH (no seam), absent is the same
// controlled PATH without it — so a discovery defect that only the seam papers over fails here.
// Seam-based variants (VIBE_SUITE_CODEX_BIN) cover auth and hostile-output behavior.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CLI = path.join(REPO_ROOT, "scripts", "preflight-cli.mjs");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex");

function tempDir(prefix) {
  return mkdtempSync(path.join(tmpdir(), prefix));
}

function freshHome() {
  const home = tempDir("preflight-home-");
  writeFileSync(path.join(home, "models_cache.json"), JSON.stringify({
    fetched_at: new Date().toISOString(),
    models: [{ slug: "discovered-model-a" }],
  }));
  return home;
}

/**
 * A controlled PATH. Three shapes:
 *  - present:    [temp bin with an executable named `codex` → fixture, node's dir] — the wrapper
 *                shadows any real codex that happens to live beside node (npm global installs put
 *                both in the same bin dir, which is exactly why the absent case must NOT include
 *                node's dir).
 *  - seam cases: [node's dir] — fixtures resolve node via their shebang; codex is never looked up
 *                on PATH because the seam names the binary directly.
 *  - absent:     [an empty temp dir] — nothing named codex is reachable, and no fixture needs node.
 */
function controlledPath({ codexFixture = null, includeNode = codexFixture !== null } = {}) {
  const entries = [];
  if (codexFixture) {
    const bin = tempDir("preflight-bin-");
    const wrapper = path.join(bin, "codex");
    writeFileSync(wrapper, `#!/bin/sh\nexec "${process.execPath}" "${codexFixture}" "$@"\n`);
    chmodSync(wrapper, 0o755);
    entries.push(bin);
  }
  if (includeNode) entries.push(path.dirname(process.execPath));
  if (entries.length === 0) entries.push(tempDir("preflight-empty-"));
  return entries.join(path.delimiter);
}

function cli({ pathVar, seam = null, home = freshHome(), args = [], agy = null, gate = null }) {
  const env = {
    HOME: home, CODEX_HOME: home, PATH: pathVar,
    // ALWAYS pinned: "no test invokes the real agy" must be enforced, not true by accident of this
    // machine's PATH layout. A guaranteed-missing path is the default.
    VIBE_SUITE_AGY_BIN: agy ?? "/nonexistent/definitely-not-installed-agy",
  };
  if (seam) env.VIBE_SUITE_CODEX_BIN = seam;
  if (gate) env.VIBE_SUITE_AGY_GATE_FILE = gate;
  return spawnSync(process.execPath, [CLI, ...args], {
    cwd: tempDir("preflight-cwd-"), env, encoding: "utf8", timeout: 60_000,
  });
}

test("PRESENT via PATH: an executable named codex on a controlled PATH yields the available matrix, exit 0", () => {
  const result = cli({ pathVar: controlledPath({ codexFixture: path.join(FIXTURES, "preflight-ok.mjs") }) });
  assert.equal(result.status, 0, `stdout: ${result.stdout}\nstderr: ${result.stderr}`);
  for (const expected of ["codex", "available", "chatgpt", "codex-cli 0.0.7", "discovered-model-a",
    "agy", "contract gate not passed"]) {
    assert.ok(result.stdout.includes(expected), `missing '${expected}' in:\n${result.stdout}`);
  }
});

test("ABSENT via PATH: a controlled PATH with no codex yields the absent matrix, exit 1", () => {
  const result = cli({ pathVar: controlledPath() });
  assert.equal(result.status, 1, `stdout: ${result.stdout}\nstderr: ${result.stderr}`);
  assert.ok(result.stdout.includes("not found"), result.stdout);
  assert.ok(result.stdout.includes("contract gate not passed"),
    "the agy column must render regardless, and say why it is pending");
});

test("--json is one parseable document with both rows in the exact schema", () => {
  const result = cli({
    pathVar: controlledPath({ codexFixture: path.join(FIXTURES, "preflight-ok.mjs") }),
    args: ["--json"],
  });
  assert.equal(result.status, 0, result.stderr);
  const payload = JSON.parse(result.stdout);
  assert.deepEqual(payload.engines.map((r) => r.engine), ["codex", "agy"]);
  for (const row of payload.engines) {
    assert.deepEqual(Object.keys(row),
      ["engine", "available", "version", "auth", "smoke", "models", "detail"]);
    assert.deepEqual(Object.keys(row.models), ["status", "slugs"],
      "the nested models shape is part of the schema contract");
    assert.ok(Array.isArray(row.models.slugs) && row.models.slugs.every((s) => typeof s === "string"));
  }
  assert.equal(payload.engines[1].available, null);
  assert.deepEqual(
    [payload.engines[1].version, payload.engines[1].auth, payload.engines[1].smoke],
    [null, null, null]);
});

test("authless lane: not-authenticated, exit 1, and the credential token never surfaces", () => {
  const result = cli({ seam: path.join(FIXTURES, "preflight-authless.mjs"),
    pathVar: controlledPath({ includeNode: true }) });
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.ok(result.stdout.includes("not-authenticated"), result.stdout);
  assert.ok(!(result.stdout + result.stderr).includes("sk-HOSTILE-CREDENTIAL-LEAK"),
    "auth output is classified and DISCARDED — echoing it leaks credentials");
});

test("hostile lane: matrix still prints in both modes, all fields bounded, no hostile bytes, exit 1", () => {
  const text = cli({ seam: path.join(FIXTURES, "preflight-hostile.mjs"),
    pathVar: controlledPath({ includeNode: true }) });
  assert.equal(text.status, 1, text.stdout + text.stderr);
  assert.ok(text.stdout.includes("unknown"), text.stdout);
  const all = text.stdout + text.stderr;
  assert.ok(!all.includes("HOSTILE-BYTES") && !all.includes("\x1b") && !all.includes("```"),
    "hostile CLI bytes must never reach preflight's own output");
  assert.ok(all.length < 16_384, "output stays bounded even when the CLI screams 64 KB");

  const json = cli({ seam: path.join(FIXTURES, "preflight-hostile.mjs"),
    pathVar: controlledPath({ includeNode: true }), args: ["--json"] });
  assert.equal(json.status, 1);
  const payload = JSON.parse(json.stdout);
  assert.equal(payload.engines[0].auth, "unknown");
  assert.ok(!json.stdout.includes("HOSTILE-BYTES"));
});

test("usage errors exit 2", () => {
  const result = cli({ pathVar: controlledPath(), args: ["--frobnicate"] });
  assert.equal(result.status, 2, result.stdout + result.stderr);
});

// ---------------------------------------------------------------------------------------------
// The agy column, end to end (E1.7 closes E1.3's deferred assertion). Both dimensions matter: what
// the row says, and whether it may influence the exit code — which only a passed gate permits.

function openGateFile() {
  const dir = mkdtempSync(path.join(tmpdir(), "preflight-gate-"));
  const file = path.join(dir, "gate-status.json");
  const names = ["headless_invocation", "read_only_write_denied", "timeout_kill",
    "failure_signature", "quota_signature"];
  writeFileSync(file, JSON.stringify({
    schema: 1, status: "passed", agy_version: "1.1.2", recorded_at: "2026-07-28T00:00:00Z",
    checks: Object.fromEntries(names.map((n) => [n, { state: "passed", note: "simulated" }])),
  }));
  return file;
}

const AGY_FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-agy");
const codexOk = () => path.join(FIXTURES, "preflight-ok.mjs");

test("agy matrix: healthy, signed-out and absent — under a SHUT gate, all stay pending", () => {
  for (const [label, agy] of [
    ["healthy", path.join(AGY_FIXTURES, "responder.mjs")],
    ["signed out", path.join(AGY_FIXTURES, "auth-error.mjs")],
    ["absent", "/nonexistent/definitely-not-installed-agy"],
  ]) {
    const result = cli({ pathVar: controlledPath({ includeNode: true }), seam: codexOk(), agy });
    assert.equal(result.status, 0, `${label}: a shut gate must never fail the exit code
${result.stdout}`);
    assert.match(result.stdout, /agy\s+pending/, `${label}: ${result.stdout}`);
    assert.match(result.stdout, /contract gate not passed/, label);
  }
});

test("agy matrix under an OPEN gate: the row reports truthfully and contributes to the exit code", () => {
  const gate = openGateFile();

  const healthy = cli({
    pathVar: controlledPath({ includeNode: true }), seam: codexOk(),
    agy: path.join(AGY_FIXTURES, "responder.mjs"), gate, args: ["--json"],
  });
  const healthyRows = JSON.parse(healthy.stdout).engines;
  const healthyAgy = healthyRows.find((row) => row.engine === "agy");
  assert.equal(healthyAgy.available, true, healthy.stdout);
  assert.equal(healthyAgy.auth, "unknown", "agy exposes no auth mode");
  assert.deepEqual(healthyAgy.models.slugs, ["gemini-a", "gemini-b"]);
  assert.equal(healthy.status, 0);

  const signedOut = cli({
    pathVar: controlledPath({ includeNode: true }), seam: codexOk(),
    agy: path.join(AGY_FIXTURES, "auth-error.mjs"), gate, args: ["--json"],
  });
  const signedOutAgy = JSON.parse(signedOut.stdout).engines.find((row) => row.engine === "agy");
  assert.equal(signedOutAgy.auth, "not-authenticated", "the frozen enum, not a new word");
  assert.equal(signedOutAgy.models.status, "missing");
  assert.equal(signedOut.status, 1, "an open gate lets an unavailable agy fail the exit code");

  // The third leg of the matrix: absent under an OPEN gate is a genuine failure, not pending.
  const absent = cli({
    pathVar: controlledPath({ includeNode: true }), seam: codexOk(),
    agy: "/nonexistent/definitely-not-installed-agy", gate, args: ["--json"],
  });
  const absentAgy = JSON.parse(absent.stdout).engines.find((row) => row.engine === "agy");
  assert.equal(absentAgy.available, false, absent.stdout);
  assert.match(absentAgy.detail, /not found on PATH/);
  assert.equal(absent.status, 1, "under an open gate, a missing agy fails the preflight");
});
