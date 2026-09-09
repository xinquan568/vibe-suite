// SPDX-License-Identifier: ISC
// End-to-end subprocess tests for the /vibe-suite:preflight CLI (E1.3 / vibe-13).
//
// The acceptance's present/absent matrix is exercised with REAL PATH manipulation — present is an
// executable named `codex` in a temp bin dir on a controlled PATH (no seam), absent is the same
// controlled PATH without it — so a discovery defect that only the seam papers over fails here.
// Seam-based variants (VIBE_SUITE_CODEX_BIN) cover auth and hostile-output behavior.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawn, spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CLI = path.join(REPO_ROOT, "scripts", "preflight-cli.mjs");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex");

function tempDir(prefix) {
  return tmpWorkspace(prefix);
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
function controlledPath({ codexFixture = null, includeNode = codexFixture !== null,
                          healthyRuntimes = true } = {}) {
  const entries = [];
  // vibe-209: preflight now probes python3/node/git and those rows COUNT toward the exit code, so a
  // PATH with none of them present is a machine missing its runtimes — and every engine-focused test
  // below would fail for a reason it is not about. Seeding healthy fakes keeps each test testing
  // what it means to: the engine cases get a working machine, and the runtime cases
  // (`runtimePath`) build their own PATH to say otherwise.
  if (healthyRuntimes) {
    const rt = tempDir("preflight-healthy-rt-");
    fakeRuntime(rt, "python3", "Python 3.14.6");
    fakeRuntime(rt, "node", "v24.12.0");
    fakeRuntime(rt, "git", "git version 2.43.0");
    entries.push(rt);
  }
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
  const dir = tmpWorkspace("preflight-gate-");
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

// === vibe-209 (grill P4) — runtime rows =============================================================
//
// The matrix probed AI engines only, so a missing `python3`, `node` or `git` first announced itself
// as a stack trace mid-run. These rows put the three runtimes in front of that.
//
// **The rows are NOT engines.** They carry `runtime` rather than `engine`, and `auth: null` rather
// than `auth: "unknown"` — the schema already distinguishes "a probe failed to learn something
// knowable" (`"unknown"`) from "there is nothing here to learn" (`null`), and git has no auth mode.
// That distinction is what lets `exitCodeFor` stay exactly as it was: its last rule is
// `row.engine !== "agy" && row.auth === "unknown"`, a hard-coded exception BY NAME, and a runtime row
// reporting `"unknown"` would fail preflight on a healthy machine. R-AUTH below pins that reasoning.

const fakeRuntime = (dir, name, output) => {
  const p = path.join(dir, name);
  const real = name === "node" ? process.execPath : `/usr/bin/${name}`;
  writeFileSync(p, `#!/bin/sh\n`
    + `if [ "$1" = "--version" ]; then printf '%s\\n' ${JSON.stringify(output)}; exit 0; fi\n`
    + `exec ${JSON.stringify(real)} "$@"\n`);
  chmodSync(p, 0o755);
};

/** A PATH holding fake runtime binaries. `undefined` version ⇒ the binary is absent. */
function runtimePath({ python3, node: nodeVer, git, includeNodeDir = false } = {}) {
  const bin = tempDir("preflight-rt-");
  const put = (name, out) => {
    if (out === undefined) return;
    fakeRuntime(bin, name, out);
  };
  put("python3", python3);
  put("node", nodeVer);
  put("git", git);
  const entries = [bin];
  if (includeNodeDir) entries.push(path.dirname(process.execPath));
  return entries.join(path.delimiter);
}

const HEALTHY = { python3: "Python 3.14.6", node: "v24.12.0", git: "git version 2.43.0" };

/** The runtimes array from `--json`, or [] when the key is absent. */
function runtimesOf(result) {
  const payload = JSON.parse(result.stdout);
  return payload.runtimes ?? [];
}
const runtimeRow = (result, name) => runtimesOf(result).find((r) => r.runtime === name);

// --- present, absent, and the exit code each produces ---------------------------------------------

test("R1 acceptance: preflight on a PATH without python3 reports the row and exits non-zero (vibe-209)", () => {
  const result = cli({
    pathVar: runtimePath({ ...HEALTHY, python3: undefined }),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  const row = runtimeRow(result, "python3");
  assert.ok(row, `a python3 row must exist: ${result.stdout}${result.stderr}`);
  assert.equal(row.available, false, "absent means unavailable");
  assert.equal(result.status, 1,
    "and it must COUNT — exitCodeFor's existing `available !== true` rule is what fails it");
});

test("R2: preflight reports an absent node — via an absolute launcher, deliberately (vibe-209)", () => {
  // `cli()` spawns `process.execPath`, an ABSOLUTE path to node, so the CLI itself still runs on a
  // PATH with no `node` on it. That is intentional and is why this row is observable at all: in real
  // use `commands/preflight.md` launches `node …/preflight-cli.mjs`, so an absent node yields NO
  // preflight output whatsoever. Doctor — which is Python-hosted — is the diagnostic for that case,
  // exactly as preflight is the diagnostic for an absent python3. Neither tool can report the
  // absence of its own host; between them the pair is complete. Do not read this test as proof that
  // preflight survives a missing node.
  const result = cli({
    pathVar: runtimePath({ ...HEALTHY, node: undefined }),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  assert.equal(runtimeRow(result, "node")?.available, false);
  assert.equal(result.status, 1);
});

test("R3: preflight reports an absent git (vibe-209)", () => {
  const result = cli({
    pathVar: runtimePath({ ...HEALTHY, git: undefined }),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  assert.equal(runtimeRow(result, "git")?.available, false);
  assert.equal(result.status, 1);
});

test("R4: a healthy git row carries auth null, and does not fail the exit code (vibe-209)", () => {
  const result = cli({
    pathVar: runtimePath(HEALTHY),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  const row = runtimeRow(result, "git");
  assert.ok(row, "a git row must exist");
  assert.equal(row.available, true);
  assert.equal(row.auth, null,
    "null means 'nothing here to learn'. `\"unknown\"` means 'failed to learn something knowable', " +
    "and exitCodeFor fails that for every row not literally named \"agy\" — see R-AUTH.");
  assert.equal(result.status, 0, "three healthy runtimes and a healthy codex is a clean preflight");
});

test("R-AUTH: a runtime row reporting auth 'unknown' WOULD fail the exit code (vibe-209)", async () => {
  // Not a test of shipped behaviour — a test of the reason D-1 chose `null`. `exitCodeFor` ends with
  // `row.engine !== "agy" && row.auth === "unknown"`, an exception hard-coded to ONE engine name. A
  // runtime row is not named there, so `"unknown"` would fail preflight on a perfectly healthy
  // machine. If someone later "tidies" `null` into `"unknown"`, this goes red and says why.
  // From the LIBRARY, not the CLI. `preflight-cli.mjs` calls main() at module scope, so
  // importing it runs a REAL preflight against this machine — printing a matrix, probing the
  // real codex and agy, and setting process.exitCode. That is what made this suite take 110s
  // and fail at file level while every subtest passed. The exit rule lives in the library so a
  // test can read it without dispatching anything.
  const { exitCodeFor } = await import("../../scripts/lib/preflight.mjs");
  const healthy = { runtime: "git", available: true, version: "git version 2.43.0", auth: null };
  assert.equal(exitCodeFor([healthy]), 0, "auth null passes");
  assert.equal(exitCodeFor([{ ...healthy, auth: "unknown" }]), 1,
    "and 'unknown' does not — which is why the rows report null");
});

// --- version floors ------------------------------------------------------------------------------

test("R6: python3 below the 3.11 floor is unavailable, with the floor named (vibe-209)", () => {
  const result = cli({
    pathVar: runtimePath({ ...HEALTHY, python3: "Python 3.9.18" }),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  const row = runtimeRow(result, "python3");
  assert.equal(row.available, false, "below the floor is not available");
  assert.match(row.detail, /3\.11/, `the floor must be named so the operator knows what to install: ${row.detail}`);
  assert.equal(result.status, 1);
});

test("R7: node below the 18 floor is unavailable, with the floor named (vibe-209)", () => {
  const result = cli({
    pathVar: runtimePath({ ...HEALTHY, node: "v16.20.2" }),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  const row = runtimeRow(result, "node");
  assert.equal(row.available, false);
  assert.match(row.detail, /18/, `the floor must be named: ${row.detail}`);
  assert.equal(result.status, 1);
});

test("R-FLOOR: the floors themselves PASS — 3.11.0 and v18.0.0 are not off-by-one (vibe-209)", () => {
  // The likeliest defect in a version comparison is the boundary, and a `>` where `>=` belongs
  // rejects exactly the version the documentation tells people to install.
  const result = cli({
    pathVar: runtimePath({ python3: "Python 3.11.0", node: "v18.0.0", git: HEALTHY.git }),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  assert.equal(runtimeRow(result, "python3").available, true, "3.11.0 meets the 3.11 floor");
  assert.equal(runtimeRow(result, "node").available, true, "v18.0.0 meets the 18 floor");
  assert.equal(result.status, 0);
});

test("R-MINOR: 3.9 is below 3.11 — components compare numerically, not as decimals (vibe-209)", () => {
  // `parseFloat("3.9") > parseFloat("3.11")` is TRUE, so a decimal comparison accepts 3.9 as
  // meeting a 3.11 floor. Only a per-component comparison gets this right.
  const result = cli({
    pathVar: runtimePath({ ...HEALTHY, python3: "Python 3.9.99" }),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  assert.equal(runtimeRow(result, "python3").available, false,
    "3.9.99 is BELOW 3.11 — a float comparison would call it 3.99 and pass it");
});

test("R8: an unreadable version is 'unknown', which the existing rule already fails (vibe-209)", () => {
  const result = cli({
    pathVar: runtimePath({ ...HEALTHY, python3: "not a version at all" }),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  assert.equal(runtimeRow(result, "python3").version, "unknown");
  assert.equal(result.status, 1, "exitCodeFor's `version === \"unknown\"` rule, unchanged");
});

test("R-HOSTILE: a runtime's version output is bounded and control-free (vibe-209)", () => {
  // The row carries whatever the binary printed. An unbounded or unsanitised token would put
  // arbitrary bytes from a program on PATH into a JSON document an operator reads.
  const hostile = "v18.0.0 \u001b[31mRED\u001b[0m \u0007" + "A".repeat(4000);
  const result = cli({
    pathVar: runtimePath({ ...HEALTHY, node: hostile }),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  const { version } = runtimeRow(result, "node");
  // The BANNER, exactly — not "something short and clean". The anchored pattern is the bound, so
  // asserting a length ceiling would pass for any implementation that happened to truncate; this
  // fails unless the reported token is the runtime's own version line and nothing else.
  assert.equal(version, "v18.0.0",
    `only the anchored banner may be reported, got ${JSON.stringify(version)}`);
  assert.ok(!/[\u0000-\u001f]/.test(version), "and no control character can be in it");
  assert.ok(!result.stdout.includes("\u0007"), "nor reach the document by another route");
});

/** A PATH whose named binary runs `script` verbatim — for outputs a version string cannot express. */
function rawRuntimePath(name, script, others = HEALTHY) {
  const bin = tempDir("preflight-raw-");
  for (const [other, out] of Object.entries(others)) {
    if (other !== name) fakeRuntime(bin, other, out);
  }
  const p = path.join(bin, name);
  writeFileSync(p, script);
  chmodSync(p, 0o755);
  return bin;
}

test("R-REAP: an unreaped probe group is a failure, not a version (vibe-209)", async () => {
  // Injected rather than raced. `runWithDeadline` confirms a group's disappearance and reports it
  // through `groupReaped`; a probe whose descendants may still be running has not been bounded, so
  // its output is not evidence. Producing a genuinely unreaped group on demand is not something a
  // test can do reliably — the effect seam is, and the branch is what matters.
  const { probeRuntime } = await import("../../scripts/lib/preflight.mjs");
  const outcome = {
    exitCode: 0, stdout: "Python 3.14.6\n", stderr: "", timedOut: false,
    spawnFailed: false, groupReaped: false,
  };
  const row = await probeRuntime("python3", { run: async () => outcome });
  assert.equal(row.available, false,
    "an unconfirmed reap must fail closed — a timer that merely expired proves nothing");
  assert.match(row.detail, /reaped/, `the reason must say so: ${row.detail}`);

  const confirmed = await probeRuntime("python3",
    { run: async () => ({ ...outcome, groupReaped: true }) });
  assert.equal(confirmed.available, true, "and the same output WITH confirmation is fine");
});

// vibe-283: readiness for a shell fixture that publishes a pid.
//
// Synchronous BY DESIGN. `runWithDeadline` invokes `onSpawned` at `scripts/lib/process.mjs:160` and
// creates its deadline timer at `:183`; the callback's return value is discarded, so a promise would
// not be awaited and only synchronous work can delay arming. Blocking this loop is safe here: the
// fixture is a separate OS process and keeps running while we wait.
//
// The sleep uses `Atomics.wait` rather than a spin so it does not compete for CPU with the very
// fixture it is waiting for — the original defect only appeared when CPU was scarce.
const READY_BUDGET_MS = 10_000;

function readPublishedPidSync(target, budgetMs, stepMs = 10) {
  const sleeper = new Int32Array(new SharedArrayBuffer(4));
  const deadline = Date.now() + budgetMs;
  for (;;) {
    // Existence is not readiness: `printf '%s' "$!" > file` creates and truncates the target before
    // it writes, so the contents must parse to a positive integer before we call the fixture ready.
    if (existsSync(target)) {
      let raw = "";
      try { raw = readFileSync(target, "utf8").trim(); } catch { raw = ""; }
      if (/^[0-9]+$/.test(raw)) {
        const pid = Number(raw);
        if (Number.isInteger(pid) && pid > 0) return pid;
      }
    }
    const remaining = deadline - Date.now();
    if (remaining <= 0) return null;
    Atomics.wait(sleeper, 0, 0, Math.min(stepMs, remaining));
  }
}

test("R-DESCENDANT: only a GROUP-wide deadline reaps a probe's descendant (vibe-209)", async () => {
  // What `detached: true` is FOR, measured in both directions rather than asserted in one.
  //
  // An earlier version of this test called `probeRuntime` and checked the descendant was gone. It
  // passed — and it ALSO passed with `detached: true` removed, so it certified nothing. The
  // discriminating measurement is the one below: the same fixture, through the same
  // `runWithDeadline`, differs only in `detached`, and the descendant survives exactly when the
  // deadline is not group-wide.
  //
  // `probeRuntime`'s use of the detached form is covered separately and behaviourally: without it
  // `groupReaped` is `null`, which fails the guard R-REAP pins and turns every healthy-runtime row
  // unavailable.
  const { runWithDeadline } = await import("../../scripts/lib/process.mjs");

  const spawnHangingParentWithChild = () => {
    const bin = tempDir("preflight-desc-");
    const pidFile = path.join(bin, "descendant.pid");
    const fake = path.join(bin, "python3");
    // A backgrounded grandchild that would outlive its parent, then a parent that hangs past the
    // deadline. Only signalling the whole group reaches the grandchild.
    // Published atomically: `> dest` would create and truncate `dest` before `printf` writes, so a
    // reader can observe it empty. A rename within one directory cannot be observed half-done.
    const tmp = JSON.stringify(`${pidFile}.tmp`);
    const dest = JSON.stringify(pidFile);
    writeFileSync(fake,
      `#!/bin/sh\nsh -c 'sleep 30' &\nprintf '%s' "$!" > ${tmp}\nmv ${tmp} ${dest}\nsleep 30\n`);
    chmodSync(fake, 0o755);
    return { fake, pidFile };
  };

  const observe = async (detached) => {
    const { fake, pidFile } = spawnHangingParentWithChild();
    let ready = null;
    const outcome = await runWithDeadline({
      command: fake, args: ["--version"], env: process.env, timeoutMs: 1000, detached,
      // vibe-283: the deadline must not start until the fixture has published. Before this gate the
      // 1s deadline raced the fixture's startup, and a starved fixture reported as a reaping failure.
      onSpawned: () => { ready = readPublishedPidSync(pidFile, READY_BUDGET_MS); },
    });
    await new Promise((resolve) => { setTimeout(resolve, 600); });
    assert.ok(ready !== null,
      "fixture setup: the descendant's pid must be published before the deadline is armed. A failure "
      + "here is a readiness failure, not a reaping regression (vibe-283).");
    const pid = ready;
    assert.ok(Number.isInteger(pid) && pid > 0, `a descendant pid was recorded: ${pid}`);
    let alive = true;
    try { process.kill(pid, 0); } catch { alive = false; }
    if (alive) { try { process.kill(pid, "SIGKILL"); } catch { /* already gone */ } }
    return { alive, groupReaped: outcome.groupReaped };
  };

  const grouped = await observe(true);
  assert.equal(grouped.groupReaped, true, "the detached form confirms the group is gone");
  assert.equal(grouped.alive, false,
    "and the descendant dies with it — this is the whole purpose of the detached deadline");

  const ungrouped = await observe(false);
  assert.notEqual(ungrouped.groupReaped, true,
    "the plain form cannot confirm a group it never made");
  assert.equal(ungrouped.alive, true,
    "and the descendant SURVIVES — which is the failure the runtime probe must not have. If this "
    + "assertion ever fails, the measurement no longer discriminates and the test above proves "
    + "nothing.");
});

// --- vibe-283: fixture readiness must be established BEFORE the deadline is armed ---------------
//
// `R-DESCENDANT` above measures reaping, but its precondition — that the fixture had published its
// descendant's pid — raced the deadline. `runWithDeadline` calls `onSpawned` at `process.mjs:160`
// and only then creates its timer at `:183`, so the clock runs from spawn whether or not the child
// has been scheduled. Under load the fixture lost that race and the suite reported a reaping
// failure that had not happened.
//
// Readiness is a PUBLISHED VALID PID, never a merely-created path: `printf '%s' "$!" > file`
// creates and truncates its target BEFORE `printf` runs, so gating on existence alone would arm the
// deadline over an empty file and move the race to the pid-parse assertion instead of removing it.

/** A fixture that spawns its descendant immediately but publishes the pid only after `delay`. */
const slowPublishFixture = (pidFile, delay) => {
  const tmp = JSON.stringify(`${pidFile}.tmp`);
  const dest = JSON.stringify(pidFile);
  return `#!/bin/sh\nsh -c 'sleep 30' &\nsleep ${delay}\nprintf '%s' "$!" > ${tmp}\nmv ${tmp} ${dest}\nsleep 30\n`;
};

test("R-READY-TIMEOUT: readiness times out rather than reporting a pid that was never published (vibe-283)", () => {
  const target = path.join(tempDir("ready-timeout-"), "never.pid");
  const started = Date.now();
  const pid = readPublishedPidSync(target, 300);
  const elapsed = Date.now() - started;
  assert.equal(pid, null, "a path that never appears is never ready");
  assert.ok(elapsed >= 250, `it must actually wait out its budget, waited ${elapsed}ms`);
  assert.ok(elapsed < 5000, `and must not hang past it, waited ${elapsed}ms`);
});

test("R-READY-EMPTY: an existing but EMPTY pid file is not readiness (vibe-283)", () => {
  // The mutant this kills: a helper gating on existSync alone. The shell creates the redirect
  // target before writing it, so existence-only readiness re-opens the vibe-283 race silently.
  const target = path.join(tempDir("ready-empty-"), "empty.pid");
  writeFileSync(target, "");
  assert.ok(existsSync(target), "precondition: the path exists");
  assert.equal(readPublishedPidSync(target, 300), null,
    "an existing but empty file is not a published pid");
  writeFileSync(target, "not-a-pid");
  assert.equal(readPublishedPidSync(target, 300), null,
    "and neither is a file whose contents do not parse to a positive integer");
});

test("R-READY-WAITS: readiness returns the published pid, and not before it is published (vibe-283)", () => {
  const target = path.join(tempDir("ready-waits-"), "late.pid");
  const tmp = `${target}.tmp`;
  const publisher = spawn("/bin/sh",
    ["-c", `sleep 0.5; printf '%s' 4242 > ${JSON.stringify(tmp)}; mv ${JSON.stringify(tmp)} ${JSON.stringify(target)}`],
    { stdio: "ignore" });
  const started = Date.now();
  const pid = readPublishedPidSync(target, READY_BUDGET_MS);
  const elapsed = Date.now() - started;
  publisher.kill();
  assert.equal(pid, 4242, "the published pid is returned");
  assert.ok(elapsed >= 400, `and not before it was published, returned after ${elapsed}ms`);
});

test("R-DESCENDANT-SLOWSTART: a slow-publishing fixture still measures reaping, not startup (vibe-283)", async () => {
  // The regression for the flake itself, made DETERMINISTIC: the delay is a property of the fixture
  // rather than of machine load, so this fails on any machine — not only a contended one — when the
  // readiness gate is removed. A 1.5s publish against a 1s deadline loses every time.
  const { runWithDeadline } = await import("../../scripts/lib/process.mjs");
  const bin = tempDir("preflight-slowstart-");
  const pidFile = path.join(bin, "descendant.pid");
  const fake = path.join(bin, "python3");
  writeFileSync(fake, slowPublishFixture(pidFile, "1.5"));
  chmodSync(fake, 0o755);

  let ready = null;
  const outcome = await runWithDeadline({
    command: fake, args: ["--version"], env: process.env, timeoutMs: 1000, detached: true,
    onSpawned: () => { ready = readPublishedPidSync(pidFile, READY_BUDGET_MS); },
  });

  assert.ok(ready !== null,
    "the readiness gate must complete before the deadline is armed. Without it the fixture's 1.5s "
    + "publish loses to the 1s deadline on EVERY machine — which is the vibe-283 flake, made "
    + "deterministic. A failure here means the gate is gone, not that reaping regressed.");
  assert.equal(outcome.groupReaped, true, "the detached form still confirms the group is gone");
  let alive = true;
  try { process.kill(ready, 0); } catch { alive = false; }
  if (alive) { try { process.kill(ready, "SIGKILL"); } catch { /* already gone */ } }
  assert.equal(alive, false,
    "and the descendant still dies with the group — the property R-DESCENDANT exists to measure");
});

test("R-BOUNDS: an implausible version component is REJECTED, not truncated (vibe-209)", () => {
  // The mutation that earned this test survived a 38-row ledger: the doctor side had a bounds test
  // and preflight did not, so `\d{1,4}` without the lookahead would have shipped here.
  //
  // Truncation is worse than a parse failure. `Python 3.12345` matched as 3.1234 — a version that
  // was never printed, handed to the floor comparison as if it had been read. A four-digit ceiling
  // is a plausibility check, not a formatter.
  const result = cli({
    pathVar: rawRuntimePath("python3", "#!/bin/sh\nprintf 'Python 3.12345\\n'\n"),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  const row = runtimeRow(result, "python3");
  assert.equal(row.available, false,
    "an implausible component means the output is not the banner it resembles");
  assert.ok(!/3\.1234\b/.test(JSON.stringify(row)),
    `a truncated component must never be reported as the version: ${JSON.stringify(row)}`);
  assert.equal(result.status, 1);
});

test("R-EXIT: a runtime that FAILS is unavailable, whatever it printed on the way (vibe-209)", () => {
  // Reporting a runtime available because a failing invocation happened to mention a version is the
  // same class of defect as reading a verdict out of a raw stream instead of an assistant message.
  const result = cli({
    pathVar: rawRuntimePath("python3", "#!/bin/sh\nprintf 'Python 3.11.9\\n'\nexit 1\n"),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  const row = runtimeRow(result, "python3");
  assert.equal(row.available, false, "a non-zero --version is a failed probe, not a version");
  assert.match(row.detail, /exited 1/, `the exit status must be reported: ${row.detail}`);
  assert.equal(result.status, 1);
});

test("R-BANNER: a wrapper's own version cannot be mistaken for the runtime's (vibe-209)", () => {
  // The defect this kills, measured before it was fixed: `wrapper 9.0 warning; Python 3.9.18` parsed
  // as 9.0, cleared the 3.11 floor, and reported available — while the real interpreter was 3.9.18.
  // Preflight called a machine healthy that was not, which is the exact failure it exists to catch.
  const result = cli({
    pathVar: rawRuntimePath("python3",
      "#!/bin/sh\nprintf 'wrapper 9.0 warning; Python 3.9.18\\n'\n"),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  const row = runtimeRow(result, "python3");
  assert.equal(row.available, false,
    "only the runtime's own anchored banner counts; a leading dotted number is not a version");
  assert.ok(!/9\.0/.test(row.version), `the wrapper's number must not be reported: ${row.version}`);
  assert.equal(result.status, 1);
});

test("R-ANCHOR: the real banner is still read when a wrapper prints ABOVE it (vibe-209)", () => {
  // The anchor is per LINE, not per output — a wrapper that warns on its own line must not stop the
  // real banner from being found, or the fix would trade a false green for a false red.
  const result = cli({
    pathVar: rawRuntimePath("python3",
      "#!/bin/sh\nprintf 'wrapper: using pyenv shim\\nPython 3.14.6\\n'\n"),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  const row = runtimeRow(result, "python3");
  assert.equal(row.available, true, "the banner is on its own line and must be found");
  assert.equal(row.version, "Python 3.14.6",
    "and the REPORTED token is the banner, not the wrapper's first line");
});

// --- the JSON envelope ---------------------------------------------------------------------------

test("R10: --json carries a runtimes array in fixed order (vibe-209)", () => {
  const result = cli({
    pathVar: runtimePath(HEALTHY),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  assert.deepEqual(runtimesOf(result).map((r) => r.runtime), ["python3", "node", "git"]);
});

test("R9: `engines` is untouched — same rows, same order, same positions (vibe-209)", () => {
  // D-2 exists because of this: `preflight-cli.test.mjs` asserts the engines array EXACTLY and reads
  // `engines[1]` POSITIONALLY. Appending runtime rows to it would break a published contract and two
  // tests that are not defects. The runtimes live in a sibling key precisely so this stays true.
  const result = cli({
    pathVar: runtimePath(HEALTHY),
    seam: path.join(FIXTURES, "preflight-ok.mjs"), args: ["--json"],
  });
  const payload = JSON.parse(result.stdout);
  assert.deepEqual(payload.engines.map((r) => r.engine), ["codex", "agy"],
    "the engines array keeps its exact contents and order");
  assert.equal(payload.engines[1].engine, "agy", "and its positional reading");
  for (const row of payload.engines) {
    assert.ok(!("runtime" in row), "no runtime row may leak into engines");
  }
});

test("R-TEXT: the human matrix shows the runtimes too (vibe-209)", () => {
  const result = cli({
    pathVar: runtimePath({ ...HEALTHY, git: undefined }),
    seam: path.join(FIXTURES, "preflight-ok.mjs"),
  });
  assert.match(result.stdout, /python3/, "the text matrix must list the runtimes");
  assert.match(result.stdout, /\bgit\b/, "including the one that is missing");
});
