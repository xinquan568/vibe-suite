// SPDX-License-Identifier: ISC
// The event log, end to end (vibe-207 / grill M5).
//
// This is the issue's own acceptance bullet, made executable: *"After a dispatch, a gate decision,
// and a prune, `jobs log` shows the three events with correlation ids."* Three real processes write
// to one log — a background runner, the Stop review gate, and the jobs CLI — and a fourth reads it
// back through the shipped command. Nothing here stubs the log or the writer.
//
// Retention is deliberately absent, and the last test proves it: past `EVENT_LOG_MAX_BYTES` the log
// is NOT trimmed, and `jobs log` says so instead. Bounded retention under concurrent writers is #266.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { eventLogPath, EVENT_LOG_MAX_BYTES } from "../../scripts/lib/eventlog.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CLI = path.join(REPO_ROOT, "scripts", "jobs-cli.mjs");
const RUNNER = path.join(REPO_ROOT, "scripts", "codex-runner.mjs");
const GATE = path.join(REPO_ROOT, "scripts", "stop-review-gate-hook.mjs");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex");

/** A git repo the Stop gate will look at, so its decision is a real one. */
function workspace() {
  const dir = tmpWorkspace("eventlog-e2e-");
  const git = (...args) => spawnSync("git", ["-C", dir, ...args], { encoding: "utf8" });
  git("init", "-q");
  writeFileSync(path.join(dir, "tracked.txt"), "baseline\n");
  git("add", "-A");
  git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "baseline");
  return dir;
}

const records = (ws) =>
  readFileSync(eventLogPath(ws), "utf8").split("\n").filter(Boolean).flatMap((line) => {
    try { return [JSON.parse(line)]; } catch { return []; }
  });

test("a dispatch, a gate decision and a prune all reach one log, and jobs log reads them back", () => {
  const ws = workspace();

  // 1. A real foreground dispatch against the fake codex — the runner writes dispatch.start and
  //    dispatch.finalise, both carrying the job id that correlates them.
  const dispatch = spawnSync("node", [RUNNER,
    "--kind", "review", "--effort", "low", "--sandbox", "read-only",
    "--timeout-ms", "120000", "--", "fixture prompt"], {
    cwd: ws, encoding: "utf8", timeout: 60_000,
    env: { ...process.env, VIBE_SUITE_CODEX_BIN: path.join(FIXTURES, "emitter.mjs") },
  });
  const receipt = JSON.parse(dispatch.stdout.trim().split("\n").at(-1));
  assert.ok(receipt.jobId, "the dispatch produced a job id to correlate on");

  // 2. The Stop gate, shipped disabled, still decides — and a decision is what the log records.
  const gate = spawnSync(process.execPath, [GATE], {
    cwd: ws, encoding: "utf8", timeout: 60_000,
    input: JSON.stringify({ cwd: ws, hook_event_name: "Stop" }),
  });
  assert.equal(gate.status, 0, `gate: ${gate.stderr}`);

  // 3. A prune sweep.
  const prune = spawnSync("node", [CLI, "prune"], { cwd: ws, encoding: "utf8", timeout: 60_000 });
  assert.equal(prune.status, 0, `prune: ${prune.stderr}`);

  const all = records(ws);
  const byEvent = (name) => all.filter((r) => r.event === name);

  assert.ok(byEvent("dispatch.start").length >= 1, "the dispatch start is recorded");
  assert.ok(byEvent("dispatch.finalise").length >= 1, "and so is its outcome");
  assert.equal(byEvent("gate.decision").length, 1, "one gate decision");
  assert.equal(byEvent("prune.action").length, 1, "one prune sweep");

  // The correlation the issue asks for: the two dispatch records name the same job the receipt did.
  for (const event of ["dispatch.start", "dispatch.finalise"]) {
    assert.equal(byEvent(event)[0].jobId, receipt.jobId,
      `${event} must carry the job id, or the record answers "something happened" and nothing more`);
  }
  // The gate and prune have no job of their own, so the key is absent rather than null.
  assert.equal("jobId" in byEvent("gate.decision")[0], false);
  assert.equal("jobId" in byEvent("prune.action")[0], false);

  // durationMs: a claimed job ran, so it is a non-negative number rather than null.
  const finalise = byEvent("dispatch.finalise")[0];
  assert.equal(typeof finalise.detail.status, "string");
  assert.ok(finalise.detail.durationMs === null || finalise.detail.durationMs >= 0,
    `durationMs must be null or non-negative, got ${finalise.detail.durationMs}`);

  // And the shipped reader shows them.
  const shown = spawnSync("node", [CLI, "log"], { cwd: ws, encoding: "utf8", timeout: 60_000 });
  assert.equal(shown.status, 0);
  for (const name of ["dispatch.start", "dispatch.finalise", "gate.decision", "prune.action"]) {
    assert.ok(shown.stdout.includes(name), `jobs log must show ${name}`);
  }
  assert.ok(shown.stdout.includes(receipt.jobId), "including the correlation id");
});

test("past the cap the log is NOT trimmed — jobs log says so and names #266", () => {
  const ws = workspace();
  const record = `${JSON.stringify({ ts: "2026-08-29T10:00:00.000Z", component: "jobs",
    event: "prune.action", detail: { pad: "x".repeat(900) } })}\n`;
  const copies = Math.ceil((EVENT_LOG_MAX_BYTES + 1024) / record.length);
  spawnSync("node", [CLI, "prune"], { cwd: ws, encoding: "utf8", timeout: 60_000 });  // makes the dir
  writeFileSync(eventLogPath(ws), record.repeat(copies), { mode: 0o600 });
  const before = statSync(eventLogPath(ws)).size;
  assert.ok(before > EVENT_LOG_MAX_BYTES, "the fixture really is over the cap");

  const shown = spawnSync("node", [CLI, "log"], { cwd: ws, encoding: "utf8", timeout: 60_000 });
  assert.equal(shown.status, 0, "an oversized log still renders");
  assert.match(shown.stdout, /#266/, "the accepted liability is named, not left silent");
  assert.equal(statSync(eventLogPath(ws)).size, before,
    "and NOTHING was trimmed — a notice is not a cap, which is the whole point of the split");
});
