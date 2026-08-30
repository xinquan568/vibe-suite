// SPDX-License-Identifier: ISC
// vibe-186 / grill S2 (B3): a `sandbox` raised above read-only by `.vibe-suite.md` is NOTICED on
// dispatch. The one reader (`scripts/lib/config.py`) emits the line on stderr with exit 0;
// `scripts/lib/config-bridge.mjs` forwards the reader's stderr to the dispatcher's, so every Node
// consumer of `loadConfig` — `codex-runner.mjs` first of all — shows it, while the JSON contract on
// stdout is untouched. The runner-level case drives the real `codex-runner.mjs` against the
// fake-codex fixture, exactly as `jobs-cli.test.mjs` does.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { chmodSync, writeFileSync } from "node:fs";

import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { readRecord } from "../../scripts/lib/jobs.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const BRIDGE = path.join(REPO_ROOT, "scripts", "lib", "config-bridge.mjs");
const RUNNER = path.join(REPO_ROOT, "scripts", "codex-runner.mjs");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex");
const NOTICE = "notice: sandbox 'workspace-write' in .vibe-suite.md raises every codex dispatch from this workspace above read-only";

function workspace(frontmatter) {
  const dir = tmpWorkspace("config-bridge-notice-");
  if (frontmatter !== null) writeFileSync(path.join(dir, ".vibe-suite.md"), `---\n${frontmatter}---\n`);
  return dir;
}

// Load through the bridge in a CHILD process so the forwarded stderr is observable as bytes.
function loadViaBridge(dir) {
  const script = `import { loadConfig, resolveDefaults } from ${JSON.stringify(BRIDGE)};
const config = loadConfig(${JSON.stringify(dir)});
process.stdout.write(JSON.stringify({ sandbox: config.sandbox, resolved: resolveDefaults(config).sandbox, overridden: resolveDefaults(config, { sandbox: "read-only" }).sandbox }));`;
  return spawnSync(process.execPath, ["--input-type=module", "-e", script], { encoding: "utf8", timeout: 30_000 });
}

test("the bridge forwards the reader's notice to stderr and keeps the JSON contract", () => {
  const r = loadViaBridge(workspace("sandbox: workspace-write\n"));
  assert.equal(r.status, 0, r.stderr);
  assert.ok(r.stderr.includes(`config: ${NOTICE}`), `stderr was: ${JSON.stringify(r.stderr)}`);
  const out = JSON.parse(r.stdout);
  assert.equal(out.sandbox, "workspace-write", "the level is honoured — a notice, not a refusal");
  assert.equal(out.resolved, "workspace-write");
  assert.equal(out.overridden, "read-only", "an explicit --sandbox still wins (user > file > default)");
});

test("read-only (or no file) produces no notice", () => {
  for (const dir of [workspace("sandbox: read-only\n"), workspace(null)]) {
    const r = loadViaBridge(dir);
    assert.equal(r.status, 0, r.stderr);
    assert.ok(!r.stderr.includes("notice:"), `unexpected notice: ${r.stderr}`);
    assert.equal(JSON.parse(r.stdout).resolved, "read-only");
  }
});

test("a dispatch through codex-runner prints the notice when the project file raised the sandbox", async () => {
  const ws = workspace("sandbox: workspace-write\n");
  const result = spawnSync(process.execPath, [RUNNER,
    "--kind", "review", "--effort", "low", "--sandbox", "read-only",
    "--timeout-ms", "120000", "--background", "--", "fixture prompt",
  ], {
    cwd: ws, encoding: "utf8", timeout: 30_000,
    env: { ...process.env, VIBE_SUITE_CODEX_BIN: path.join(FIXTURES, "emitter.mjs") },
  });
  assert.equal(result.status, 0, `runner failed: ${result.stdout}\n${result.stderr}`);
  assert.ok(result.stderr.includes(NOTICE), `dispatch stderr was: ${JSON.stringify(result.stderr)}`);
  const receipt = JSON.parse(result.stdout.trim().split("\n").at(-1));
  assert.equal(receipt.status, "running", "the launch receipt is unchanged by the notice");
  // Let the detached job finish against the fixture so nothing outlives the test.
  const deadline = Date.now() + 20_000;
  for (;;) {
    const record = await readRecord(ws, receipt.jobId).catch(() => null);
    if (record && ["completed", "failed", "timed_out", "cancelled"].includes(record.status)) break;
    if (Date.now() > deadline) throw new Error("fixture job never reached a terminal status");
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
});

// --- vibe-209 ------------------------------------------------------------------------------------

test("C1 CHARACTERISATION (green before this change): a misspelled known key warns once on dispatch", async () => {
  // **This test is not RED and proves nothing about vibe-209.** The issue's second acceptance
  // criterion — "a misspelled known key in .vibe-suite.md produces one stderr warning on dispatch" —
  // was ALREADY met before this change. The grill report described `config.load()` discarding
  // warnings on the dispatch path, which was true at its baseline `090b511`; vibe-186 then made
  // `config.py:main()` print every warning to stderr and `config-bridge.mjs` forward them.
  //
  // It is added as a REGRESSION GUARD, and labelled so nobody later mistakes a green test for
  // evidence that this issue did the work. The sibling cases above cover the sandbox-raised and
  // store-only notices; an unknown key is the shape the criterion actually names, and had none.
  const { loadConfig } = await import(BRIDGE);
  const root = tmpWorkspace("config-c1-");
  writeFileSync(path.join(root, ".vibe-suite.md"), "---\nsandbax: read-only\n---\n");

  const seen = [];
  const real = process.stderr.write.bind(process.stderr);
  process.stderr.write = (chunk, ...rest) => { seen.push(String(chunk)); return real(chunk, ...rest); };
  let resolved;
  try {
    resolved = loadConfig(root);
  } finally {
    process.stderr.write = real;
  }

  const warnings = seen.join("").split("\n").filter((line) => line.includes("config:"));
  assert.equal(warnings.length, 1, `exactly one warning, got ${JSON.stringify(warnings)}`);
  assert.match(warnings[0], /unknown key 'sandbax'/, "it names the key the operator misspelled");
  assert.ok(resolved && typeof resolved === "object", "and the load still succeeds — warn, never crash");
});

test("R15: the python3 spawn is bounded at exactly 30_000 ms, and the bound is real (vibe-209)", async () => {
  // Two assertions, because they fail for different reasons. The VALUE is what the issue specifies —
  // a test that only forces a timeout cannot tell 30 s from 10 min, so any bound at all would pass
  // it. The BEHAVIOUR is that the bound is actually wired into the spawn rather than merely declared.
  const { CONFIG_TIMEOUT_MS, loadConfig: load } = await import(BRIDGE);
  assert.equal(CONFIG_TIMEOUT_MS, 30_000, "the issue names this value; a different one is a defect");

  // A `python3` that never returns. The bridge must give up rather than hang the dispatch forever.
  const root = tmpWorkspace("config-slow-");
  const bin = tmpWorkspace("config-slowbin-");
  const fake = path.join(bin, "python3");
  writeFileSync(fake, "#!/bin/sh\nsleep 30\n");
  chmodSync(fake, 0o755);

  const started = Date.now();
  assert.throws(() => load(root, { python: fake, timeoutMs: 300 }),
    /cannot run|exited/, "a timed-out interpreter is an error, never a silent empty config");
  assert.ok(Date.now() - started < 10_000,
    `the spawn must be bounded — took ${Date.now() - started}ms with no bound in sight`);
});
