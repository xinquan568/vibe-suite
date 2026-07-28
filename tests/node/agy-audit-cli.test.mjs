// SPDX-License-Identifier: ISC
// The audit lane as observable process behaviour (E1.7 / vibe-17).
//
// The round-1 fallback existed only as returned objects, so its exit codes and manual signal were
// claims. These drive the real CLI in a subprocess with controlled binaries and an injected gate
// record, and assert what a caller can actually see: exit code, stdout, stderr, and how many job
// records were created.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { jobsDir } from "../../scripts/lib/jobs.mjs";
import { MANDATORY_CHECKS } from "../../scripts/lib/agy-gate.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CLI = path.join(REPO_ROOT, "scripts", "agy-audit-cli.mjs");
const AGY_FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-agy");
const CODEX_FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex");
const MISSING = "/nonexistent/definitely-not-installed";

function openGate() {
  const file = path.join(mkdtempSync(path.join(tmpdir(), "audit-gate-")), "gate-status.json");
  writeFileSync(file, JSON.stringify({
    schema: 1, status: "passed", agy_version: "1.1.2", recorded_at: "2026-07-28T00:00:00Z",
    checks: Object.fromEntries(MANDATORY_CHECKS.map((n) => [n, { state: "passed", note: "simulated" }])),
  }));
  return file;
}

function run({ agy = MISSING, codex = MISSING, gate = null } = {}) {
  const cwd = mkdtempSync(path.join(tmpdir(), "audit-ws-"));
  const result = spawnSync(process.execPath, [CLI, "--", "audit this repository"], {
    cwd, encoding: "utf8", timeout: 90_000,
    env: {
      ...process.env,
      // Both engines are ALWAYS pinned: "no test invokes the real CLI" has to be enforced, not hoped.
      VIBE_SUITE_AGY_BIN: agy,
      VIBE_SUITE_CODEX_BIN: codex,
      ...(gate ? { VIBE_SUITE_AGY_GATE_FILE: gate } : {}),
    },
  });
  const records = (() => {
    try {
      return readdirSync(jobsDir(cwd)).filter((n) => /^job_[0-9a-f]{20}\.json$/.test(n)).length;
    } catch { return 0; }
  })();
  return { ...result, cwd, records };
}

test("gated shut: exit 2, nothing dispatched, no records", () => {
  const result = run({ agy: path.join(AGY_FIXTURES, "responder.mjs") });   // production record
  assert.equal(result.status, 2, `${result.stdout}${result.stderr}`);
  assert.match(result.stderr, /gated shut/);
  assert.match(result.stderr, /agy-flip-checklist/);
  assert.equal(result.stdout.trim(), "", "stdout carries results only");
  assert.equal(result.records, 0);
});

test("agy answers: one result on stdout, no header, exit 0", () => {
  const result = run({
    gate: openGate(),
    agy: path.join(AGY_FIXTURES, "responder.mjs"),
    codex: path.join(CODEX_FIXTURES, "emitter.mjs"),
  });
  assert.equal(result.status, 0, `${result.stdout}${result.stderr}`);
  const lines = result.stdout.trim().split("\n").filter(Boolean);
  assert.equal(lines.length, 1, "exactly one caller-facing result");
  assert.equal(JSON.parse(lines[0]).status, "completed");
  assert.ok(!/unreachable/.test(result.stderr), "nothing was unreachable");
  assert.equal(result.records, 1, "only agy ran");
});

test("agy unreachable: header on stderr, codex's result on stdout, TWO records, exit 0", () => {
  const result = run({
    gate: openGate(),
    agy: path.join(AGY_FIXTURES, "auth-error.mjs"),          // completes, but unauthenticated
    codex: path.join(CODEX_FIXTURES, "emitter.mjs"),
  });
  assert.equal(result.status, 0, `${result.stdout}${result.stderr}`);
  assert.match(result.stderr, /agy is unreachable \((unauthenticated|failed)\)/);
  assert.match(result.stderr, /preflight/, "the header carries a remedy");
  const lines = result.stdout.trim().split("\n").filter(Boolean);
  assert.equal(lines.length, 1, "the caller gets exactly one result — codex's");
  assert.equal(JSON.parse(lines[0]).status, "completed");
  assert.equal(result.records, 2, "the failed agy job and the codex job are both recorded");
});

test("both unreachable: the manual signal on stdout and exit 3", () => {
  const result = run({ gate: openGate(), agy: MISSING, codex: MISSING });
  assert.equal(result.status, 3, `${result.stdout}${result.stderr}`);
  const signal = JSON.parse(result.stdout.trim());
  assert.equal(signal.fallback, "manual");
  assert.equal(typeof signal.reason, "string");
  assert.match(result.stderr, /no engine could run this analysis/);
});

test("a malformed invocation is a usage error, distinct from the manual path", () => {
  const cwd = mkdtempSync(path.join(tmpdir(), "audit-usage-"));
  const result = spawnSync(process.execPath, [CLI], { cwd, encoding: "utf8", timeout: 30_000 });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /prompt is required/);
});
