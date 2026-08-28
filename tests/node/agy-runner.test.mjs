// SPDX-License-Identifier: ISC
// The agy runner (E1.7 / vibe-17), driven as a subprocess against the fake-agy fixtures.
//
// Two families of property: the gate must hold shut (no dispatch, no record) until it is opened
// deliberately, and — once opened — the runner must mirror E1.1's contract while respecting what
// agy's own behaviour forces (exit codes lie, OAuth blocks past stdin, no thread id exists).

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";

import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { jobsDir, readRecord } from "../../scripts/lib/jobs.mjs";
import { MANDATORY_CHECKS } from "../../scripts/lib/agy-gate.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const RUNNER = path.join(REPO_ROOT, "scripts", "agy-runner.mjs");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-agy");

/** A simulated GRADUATED gate, injected through the documented seam. Production stays not_passed. */
function passedGateFile() {
  const dir = tmpWorkspace("agy-gate-open-");
  const file = path.join(dir, "gate-status.json");
  writeFileSync(file, JSON.stringify({
    schema: 1, status: "passed", agy_version: "1.1.2", recorded_at: "2026-07-28T00:00:00Z",
    checks: Object.fromEntries(MANDATORY_CHECKS.map((n) => [n, { state: "passed", note: "" }])),
  }));
  return file;
}

function run(args, { cwd, fixture = "responder.mjs", gate = null, probe = null, env = {} } = {}) {
  return spawnSync(process.execPath, [RUNNER, ...args], {
    cwd, encoding: "utf8", timeout: 60_000,
    env: {
      ...process.env,
      VIBE_SUITE_AGY_BIN: path.join(FIXTURES, fixture),
      ...(gate ? { VIBE_SUITE_AGY_GATE_FILE: gate } : {}),
      ...(probe ? { VIBE_TEST_PROBE: probe } : {}),
      ...env,
    },
  });
}

const ws = () => tmpWorkspace("agy-ws-");
const jobCount = (dir) => {
  try {
    return readdirSync(jobsDir(dir), { withFileTypes: true })
      .filter((e) => e.isFile() && /^job_[0-9a-f]{20}\.json$/.test(e.name)).length;
  } catch { return 0; }
};
const base = (...extra) => ["--kind", "audit", "--timeout-ms", "20000", ...extra, "--", "analyse this"];

test("pre-gate: the committed gate is shut, so nothing dispatches and no record is created", () => {
  const dir = ws();
  const result = run(base(), { cwd: dir });                     // no gate override: production record
  assert.equal(result.status, 2, `${result.stdout}${result.stderr}`);
  assert.match(result.stderr, /gated shut/);
  assert.match(result.stderr, /agy-flip-checklist/, "the refusal points at the checklist");
  assert.equal(jobCount(dir), 0, "a refused lane must not leave a job record behind");
});

test("with the gate simulated open: a record, the five-key line, and threadId null", async () => {
  const dir = ws();
  const probe = path.join(tmpWorkspace("agy-probe-"), "probe.json");
  const result = run(base(), { cwd: dir, gate: passedGateFile(), probe });
  assert.equal(result.status, 0, `${result.stdout}${result.stderr}`);
  const line = JSON.parse(result.stdout.trim().split("\n").at(-1));
  assert.deepEqual(Object.keys(line), ["jobId", "status", "threadId", "rawOutput", "verdictState"]);
  assert.equal(line.status, "completed");
  assert.equal(line.threadId, null, "agy v1 exposes no thread id — inventing one would be a lie");
  const argv = JSON.parse(readFileSync(probe, "utf8")).argv;
  assert.ok(argv.includes("--sandbox") && argv.includes("--print"), argv.join(" "));
  const record = await readRecord(dir, line.jobId);
  assert.equal(record.sandbox, "read-only");
});

test("model resolution: explicit wins, agy's override applies, otherwise omitted, --no-model forces omission", () => {
  const gate = passedGateFile();
  const withOverride = () => {
    const dir = ws();
    writeFileSync(path.join(dir, ".vibe-suite.md"),
      "---\nmodel_overrides:\n  agy: project-agy-model\n---\n\n# config\n");
    return dir;
  };
  const argvOf = (dir, extra) => {
    const probe = path.join(tmpWorkspace("agy-probe-"), "probe.json");
    const r = run(base(...extra), { cwd: dir, gate, probe });
    assert.equal(r.status, 0, `${r.stdout}${r.stderr}`);
    return JSON.parse(readFileSync(probe, "utf8")).argv;
  };

  const explicit = argvOf(withOverride(), ["--model", "explicit-model"]);
  assert.equal(explicit[explicit.indexOf("--model") + 1], "explicit-model");

  const configured = argvOf(withOverride(), []);
  assert.equal(configured[configured.indexOf("--model") + 1], "project-agy-model",
    "the agy-specific override applies when the caller chose nothing");

  const none = argvOf(ws(), []);
  assert.ok(!none.includes("--model"), `no override, no flag (P9): ${none.join(" ")}`);

  const deferred = argvOf(withOverride(), ["--no-model"]);
  assert.ok(!deferred.includes("--model"),
    "--no-model must reach past the project override to the backend default");
});

test("--model together with --no-model is a usage error, with nothing created", () => {
  const dir = ws();
  const result = run(base("--model", "x", "--no-model"), { cwd: dir, gate: passedGateFile() });
  assert.equal(result.status, 2, result.stderr);
  assert.match(result.stderr, /mutually exclusive/);
  assert.equal(jobCount(dir), 0);
});

test("exit 0 with an authentication error is a FAILURE, not a result", async () => {
  const dir = ws();
  const result = run(base(), { cwd: dir, gate: passedGateFile(), fixture: "auth-error.mjs" });
  assert.equal(result.status, 1, `${result.stdout}${result.stderr}`);
  const line = JSON.parse(result.stdout.trim().split("\n").at(-1));
  assert.equal(line.status, "failed");
  const record = await readRecord(dir, line.jobId);
  assert.equal(record.error, "unauthenticated",
    "the exit code said success; the output said sign in — the output decides");
});

test("a quota response is classified as such", async () => {
  const dir = ws();
  const result = run(base(), { cwd: dir, gate: passedGateFile(), fixture: "quota.mjs" });
  const line = JSON.parse(result.stdout.trim().split("\n").at(-1));
  assert.equal(line.status, "failed");
  assert.equal((await readRecord(dir, line.jobId)).error, "quota");
});

test("an OAuth-blocking agy is killed by the deadline: stdin at /dev/null does not save you", async () => {
  const dir = ws();
  const result = run(["--kind", "audit", "--timeout-ms", "3000", "--", "analyse"],
    { cwd: dir, gate: passedGateFile(), fixture: "auth-blocker.mjs" });
  assert.equal(result.status, 1, `${result.stdout}${result.stderr}`);
  const line = JSON.parse(result.stdout.trim().split("\n").at(-1));
  assert.equal(line.status, "timed_out", "only a detached group kill bounds a blocking OAuth prompt");
  // vibe-182: the signal that ended agy is on the record — a falsifiable assertion (a lane that
  // forgot to finalise `signal` would leave newRecord's null here).
  const record = await readRecord(dir, line.jobId);
  assert.ok(record.signal === "SIGTERM" || record.signal === "SIGKILL", `the ending signal is recorded: ${record.signal}`);
});

test("an oversized prompt fails CLOSED — no truncation, no dispatch, no record", () => {
  const dir = ws();
  const probe = path.join(tmpWorkspace("agy-probe-"), "probe.json");
  // Multibyte, so the cap is proven to be bytes rather than characters.
  const huge = "é".repeat(60_000);                    // 120 000 bytes
  const result = run(["--kind", "audit", "--timeout-ms", "20000", "--", huge],
    { cwd: dir, gate: passedGateFile(), probe });
  assert.equal(result.status, 2, `${result.stdout}${result.stderr}`);
  assert.match(result.stderr, /exceeds .* bytes/);
  assert.match(result.stderr, /silently change the scope/);
  assert.equal(jobCount(dir), 0, "a refused prompt must leave no record");
});

test("an unconfirmed process-group reap is terminal, not a completed job", async () => {
  // The classifier is unit-reachable, and this is the one property a fixture cannot fake: the
  // runner must refuse to call a job completed when its group may still be alive.
  const { classifyOutput } = await import("../../scripts/agy-runner.mjs");
  assert.deepEqual(classifyOutput({ stdout: "analysis\n", groupReaped: false }),
    { status: "failed", reason: "reap-failed" });
  assert.equal(classifyOutput({ stdout: "analysis\n", groupReaped: true }).status, "completed");
  // A MISSING confirmation is not a confirmation. Round 2 blessed this case as completed, which let
  // any caller that forgot to report a reap look successful.
  assert.deepEqual(classifyOutput({ stdout: "analysis\n" }),
    { status: "failed", reason: "reap-failed" });
  assert.deepEqual(classifyOutput({ stdout: "analysis\n", groupReaped: null }),
    { status: "failed", reason: "reap-failed" });
  // And confirmation is checked BEFORE the more specific-sounding reasons, which would mask it.
  assert.deepEqual(classifyOutput({ timedOut: true, groupReaped: false }),
    { status: "failed", reason: "reap-failed" });
  assert.deepEqual(classifyOutput({ stdout: "Please sign in\n", groupReaped: false }),
    { status: "failed", reason: "reap-failed" });
});

test("the engine's stderr is persisted on the record as stderrTail; a natural exit records no signal (vibe-182)", async () => {
  const dir = ws();
  const result = run(base(), { cwd: dir, gate: passedGateFile(), fixture: "auth-error.mjs" });
  const line = JSON.parse(result.stdout.trim().split("\n").at(-1));
  const record = await readRecord(dir, line.jobId);
  assert.match(record.stderrTail ?? "", /Please sign in/, "the stderr that explained the failure is on the record");
  assert.equal(record.signal, null, "exit 0 — no signal");
  assert.equal(record.malformedLines, null, "agy has no event stream; the count stays null");
});
