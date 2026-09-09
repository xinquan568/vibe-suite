// SPDX-License-Identifier: ISC
// M8 / vibe-221: the runners' `model` comes from ONE executable statement of the engine ladder — the Python seam
// (`scripts/lib/engine_resolution.py` behind `config_cli.py resolve-engine`). `config-bridge.mjs resolveModel`
// spawns it; `resolveDefaults` no longer has a model rule; no Node file reads `model_overrides` itself. A second
// statement of the rule in JavaScript is the defect class this issue removed, so the source guard below fails on
// its return.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { chmodSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { ConfigBridgeError, loadConfig, resolveDefaults, resolveModel } from "../../scripts/lib/config-bridge.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function workspace(frontmatter) {
  const dir = tmpWorkspace("engine-resolution-bridge-");
  if (frontmatter !== null) writeFileSync(path.join(dir, ".vibe-suite.md"), `---\n${frontmatter}---\n`);
  return dir;
}
const OVERRIDES = "model_overrides:\n  codex: project-codex\n  agy: project-agy\n";

test("the user's model wins over the project override, through the seam", () => {
  assert.equal(resolveModel(workspace(OVERRIDES), { engine: "codex", model: "user-model" }), "user-model");
});

test("each lane reads its own override — codex gets codex's, agy gets agy's", () => {
  const dir = workspace(OVERRIDES);
  assert.equal(resolveModel(dir, { engine: "codex" }), "project-codex");
  assert.equal(resolveModel(dir, { engine: "agy" }), "project-agy");
});

test("nothing configured → null (DEFER: no model flag; P9)", () => {
  assert.equal(resolveModel(workspace(null), { engine: "codex" }), null);
  assert.equal(resolveModel(workspace("sandbox: read-only\n"), { engine: "agy" }), null);
});

test("noModel short-circuits to null WITHOUT spawning the seam", () => {
  // A python that cannot run: if the bridge spawned it, this would throw, not return null.
  assert.equal(resolveModel(workspace(OVERRIDES), { engine: "codex", noModel: true, python: "/nonexistent/python3" }), null);
});

test("a bad engine, or a broken project file, is a ConfigBridgeError — fail-closed like loadConfig", () => {
  assert.throws(() => resolveModel(workspace(null), { engine: "bogus" }), ConfigBridgeError);
  assert.throws(() => resolveModel(workspace(null), {}), ConfigBridgeError, "an engine is required");
  const broken = tmpWorkspace("engine-resolution-broken-");
  writeFileSync(path.join(broken, ".vibe-suite.md"), "---\nengine: codex\n");
  assert.throws(() => resolveModel(broken, { engine: "codex" }), ConfigBridgeError);
});

// The direct-runner pin ordinary override forwarding never had: the real codex-runner, a project override, the
// fake-codex emitter — the job record carries the override; `--no-model` carries null. (Green at base too — the
// old resolveDefaults forwarded the override — so this is a guard on the delegation, not RED evidence.)
test("codex-runner forwards the project's codex override through the seam, and --no-model bypasses it", async () => {
  const { readRecord } = await import("../../scripts/lib/jobs.mjs");
  const RUNNER = path.join(REPO_ROOT, "scripts", "codex-runner.mjs");
  const EMITTER = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex", "emitter.mjs");
  const dispatch = async (extra) => {
    const ws = workspace(OVERRIDES);
    const result = spawnSync(process.execPath, [RUNNER,
      "--kind", "review", "--effort", "low", "--sandbox", "read-only", "--timeout-ms", "120000",
      "--background", ...extra, "--", "fixture prompt",
    ], { cwd: ws, encoding: "utf8", timeout: 30_000, env: { ...process.env, VIBE_SUITE_CODEX_BIN: EMITTER } });
    assert.equal(result.status, 0, `runner failed: ${result.stdout}\n${result.stderr}`);
    const receipt = JSON.parse(result.stdout.trim().split("\n").at(-1));
    const deadline = Date.now() + 20_000;
    for (;;) {
      const record = await readRecord(ws, receipt.jobId).catch(() => null);
      if (record && ["completed", "failed", "timed_out", "cancelled"].includes(record.status)) return record;
      if (Date.now() > deadline) throw new Error("fixture job never reached a terminal status");
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
  };
  assert.equal((await dispatch([])).model, "project-codex");
  assert.equal((await dispatch(["--no-model"])).model, null);
  assert.equal((await dispatch(["--model", "explicit-model"])).model, "explicit-model");
});

// A controlled "interpreter": the seam's failure paths are exercised by substituting python3 with a shell
// script that misbehaves in exactly one way, so each protection is the only thing standing between the
// bridge and a wrong model.
function fakePython(body) {
  const bin = tmpWorkspace("engine-resolution-fakepy-");
  const fake = path.join(bin, "python3");
  writeFileSync(fake, `#!/bin/sh\n${body}\n`);
  chmodSync(fake, 0o755);
  return fake;
}

test("a seam that never returns is a ConfigBridgeError within the bound — the spawn is timed, not trusted", () => {
  const started = Date.now();
  assert.throws(() => resolveModel(workspace(null), { engine: "codex", python: fakePython("sleep 30"), timeoutMs: 300 }),
    ConfigBridgeError, "a timed-out seam is an error, never a silent null");
  assert.ok(Date.now() - started < 10_000, `the spawn must be bounded — took ${Date.now() - started}ms`);
});

test("a seam that prints non-JSON is a ConfigBridgeError", () => {
  assert.throws(() => resolveModel(workspace(null), { engine: "codex", python: fakePython("echo not-json") }),
    /did not emit JSON/);
});

test("a seam whose JSON carries no model key is a ConfigBridgeError — never read as null", () => {
  assert.throws(() => resolveModel(workspace(null), { engine: "codex", python: fakePython("echo '{\"engine\": \"codex\"}'") }),
    /without a model key/);
  assert.throws(() => resolveModel(workspace(null), { engine: "codex", python: fakePython("echo '[1]'") }), /without a model key/);
});

test("resolveDefaults resolves sandbox and effort only — the model rule left with the seam", () => {
  const out = resolveDefaults(loadConfig(workspace(OVERRIDES)), { sandbox: "read-only" });
  assert.deepEqual(Object.keys(out).sort(), ["effort", "sandbox"]);
});

test("source guard: no Node file states the model rule itself", () => {
  for (const rel of ["scripts/lib/config-bridge.mjs", "scripts/codex-runner.mjs", "scripts/agy-runner.mjs"]) {
    const text = readFileSync(path.join(REPO_ROOT, rel), "utf8");
    assert.ok(!text.includes("model_overrides"), `${rel} reads model_overrides itself — a second statement of the rule`);
  }
});
