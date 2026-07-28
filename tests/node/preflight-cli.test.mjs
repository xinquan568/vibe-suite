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

function cli({ pathVar, seam = null, home = freshHome(), args = [] }) {
  const env = {
    HOME: home, CODEX_HOME: home, PATH: pathVar,
  };
  if (seam) env.VIBE_SUITE_CODEX_BIN = seam;
  return spawnSync(process.execPath, [CLI, ...args], {
    cwd: tempDir("preflight-cwd-"), env, encoding: "utf8", timeout: 60_000,
  });
}

test("PRESENT via PATH: an executable named codex on a controlled PATH yields the available matrix, exit 0", () => {
  const result = cli({ pathVar: controlledPath({ codexFixture: path.join(FIXTURES, "preflight-ok.mjs") }) });
  assert.equal(result.status, 0, `stdout: ${result.stdout}\nstderr: ${result.stderr}`);
  for (const expected of ["codex", "available", "chatgpt", "codex-cli 0.0.7", "discovered-model-a",
    "agy", "probe pending"]) {
    assert.ok(result.stdout.includes(expected), `missing '${expected}' in:\n${result.stdout}`);
  }
});

test("ABSENT via PATH: a controlled PATH with no codex yields the absent matrix, exit 1", () => {
  const result = cli({ pathVar: controlledPath() });
  assert.equal(result.status, 1, `stdout: ${result.stdout}\nstderr: ${result.stderr}`);
  assert.ok(result.stdout.includes("not found"), result.stdout);
  assert.ok(result.stdout.includes("probe pending"), "the agy column must render regardless");
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
  }
  assert.equal(payload.engines[1].available, null);
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
