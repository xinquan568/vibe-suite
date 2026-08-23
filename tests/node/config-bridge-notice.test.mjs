// SPDX-License-Identifier: ISC
// vibe-186 / grill S2 (B3): a `sandbox` raised above read-only by `.vibe-suite.md` is NOTICED on
// dispatch. The one reader (`scripts/lib/config.py`) emits the line on stderr with exit 0;
// `scripts/lib/config-bridge.mjs` forwards the reader's stderr to the dispatcher's, so every Node
// consumer of `loadConfig` — `codex-runner.mjs` first of all — shows it, while the JSON contract on
// stdout is untouched. The runner-level case drives the real `codex-runner.mjs` against the
// fake-codex fixture, exactly as `jobs-cli.test.mjs` does.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
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
  const dir = mkdtempSync(path.join(tmpdir(), "config-bridge-notice-"));
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
