// SPDX-License-Identifier: ISC
// The opt-in Stop-review gate (E1.6 / vibe-16), driven as the harness drives it: harness-shaped
// JSON on stdin, decision on stdout, exit 0 always.
//
// The acceptance cases are here — disabled by default, enabled blocks a seeded bad diff, codex
// absent fails open — plus the two properties that make those cases mean something: the seeded
// defect lives in an UNTRACKED file and the fixture blocks only if that file's CONTENT reached it,
// and the verdict is read structurally (last assistant message, first non-empty line) so neither
// the diff nor a non-assistant event can spoof it.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { jobsDir } from "../../scripts/lib/jobs.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOK = path.join(REPO_ROOT, "scripts", "stop-review-gate-hook.mjs");
const STORE = path.join(REPO_ROOT, "scripts", "lib", "store.py");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex");

const MARKER = "SEEDED-DEFECT-MARKER";

function repo({ enabled = false, failPolicy = null, gateModel = null, projectModel = null } = {}) {
  const dir = mkdtempSync(path.join(tmpdir(), "stop-gate-"));
  const git = (...args) => spawnSync("git", ["-C", dir, ...args], { encoding: "utf8" });
  git("init", "-q");
  writeFileSync(path.join(dir, "tracked.txt"), "baseline\n");
  git("add", "-A");
  git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "baseline");
  if (projectModel) {
    // `.vibe-suite.md` is YAML FRONTMATTER (config.py's grammar), not a fenced block.
    writeFileSync(path.join(dir, ".vibe-suite.md"),
      `---\nmodel_overrides:\n  codex: ${projectModel}\n---\n\n# project config\n`);
  }
  const setKey = (key, value) => {
    const py = `import sys; sys.path.insert(0, ${JSON.stringify(path.dirname(STORE))}); ` +
      `import store; store.Store(${JSON.stringify(dir)}).set(${JSON.stringify(key)}, ${value})`;
    const r = spawnSync("python3", ["-c", py], { encoding: "utf8" });
    assert.equal(r.status, 0, r.stderr);
  };
  if (enabled) setKey("gate.stop_review_gate", "True");
  if (failPolicy) setKey("gate.fail_policy", JSON.stringify(failPolicy));
  if (gateModel) setKey("gate.model", JSON.stringify(gateModel));
  return dir;
}

/** The seeded defect: a NEW (untracked) file, which `git diff HEAD` alone would never show. */
function seedDefect(dir, name = "new-defect.js") {
  writeFileSync(path.join(dir, name), `// ${MARKER}: an off-by-one nobody reviewed\n`);
}

function runHook(dir, { fixture = null, input = {}, probe = null, env = {} } = {}) {
  return spawnSync(process.execPath, [HOOK], {
    cwd: dir, encoding: "utf8", timeout: 60_000,
    input: JSON.stringify({ cwd: dir, hook_event_name: "Stop", ...input }),
    env: {
      ...process.env,
      ...(fixture ? { VIBE_SUITE_CODEX_BIN: path.join(FIXTURES, fixture) } : {}),
      ...(probe ? { VIBE_TEST_PROBE: probe } : {}),
      ...env,
    },
  });
}

const decisionOf = (result) => (result.stdout.trim() ? JSON.parse(result.stdout.trim()) : null);
const jobCount = (dir) => {
  try {
    return readdirSync(jobsDir(dir)).filter((n) => /^job_[0-9a-f]{20}\.json$/.test(n)).length;
  } catch {
    return 0;
  }
};

test("disabled by default on a fresh install: allows, and dispatches nothing at all", () => {
  const dir = repo();
  seedDefect(dir);
  const result = runHook(dir, { fixture: "gate-marker.mjs" });
  assert.equal(result.status, 0);
  assert.equal(decisionOf(result), null, "no decision means allow");
  assert.equal(jobCount(dir), 0, "a disabled gate must not create a job record — nothing ran");
});

test("enabled: a seeded defect in an UNTRACKED file blocks — and only because its content was sent", () => {
  const dir = repo({ enabled: true });
  seedDefect(dir);
  const probe = path.join(mkdtempSync(path.join(tmpdir(), "gate-probe-")), "probe.json");
  const result = runHook(dir, { fixture: "gate-marker.mjs", probe });

  const decision = decisionOf(result);
  assert.ok(decision, `expected a block decision, got: ${result.stdout}${result.stderr}`);
  assert.equal(decision.decision, "block");
  assert.ok(decision.reason.includes("seeded defect"), decision.reason);
  // The fixture allows unless the marker reached it: blocking IS the content-delivery proof.
  const sent = JSON.parse(readFileSync(probe, "utf8")).argv.at(-1);
  assert.ok(sent.includes(MARKER), "the untracked file's content must reach the reviewer");
  assert.ok(sent.includes("new-defect.js"));
});

test("untracked collection: spaced names included, symlinks and outside targets excluded, caps disclosed", () => {
  const dir = repo({ enabled: true });
  writeFileSync(path.join(dir, "spaced name.txt"), "SPACED-CONTENT-PRESENT\n");
  const outside = mkdtempSync(path.join(tmpdir(), "gate-outside-"));
  writeFileSync(path.join(outside, "secret.txt"), "OUTSIDE-SECRET-MUST-NOT-LEAK\n");
  symlinkSync(path.join(outside, "secret.txt"), path.join(dir, "link-to-secret.txt"));
  writeFileSync(path.join(dir, "huge.txt"), "H".repeat(25_000));

  const probe = path.join(mkdtempSync(path.join(tmpdir(), "gate-probe-")), "probe.json");
  const result = runHook(dir, { fixture: "gate-allower.mjs", probe });
  assert.equal(result.status, 0);
  const sent = JSON.parse(readFileSync(probe, "utf8")).argv.at(-1);
  assert.ok(sent.includes("SPACED-CONTENT-PRESENT"), "spaced filenames must be collected");
  assert.ok(!sent.includes("OUTSIDE-SECRET-MUST-NOT-LEAK"),
    "a symlink must never smuggle outside content into the prompt");
  assert.ok(sent.includes("truncated at the per-file cap"), "truncation must be disclosed");
});

test("codex absent: fails OPEN by default, and CLOSED when the policy says so", () => {
  const open = repo({ enabled: true });
  seedDefect(open);
  const openResult = runHook(open, { env: { VIBE_SUITE_CODEX_BIN: "/nonexistent/codex" } });
  assert.equal(openResult.status, 0);
  assert.equal(decisionOf(openResult), null, "fail-open allows the stop");
  assert.ok(openResult.stderr.includes("failing open"), openResult.stderr);

  const closed = repo({ enabled: true, failPolicy: "closed" });
  seedDefect(closed);
  const closedResult = runHook(closed, { env: { VIBE_SUITE_CODEX_BIN: "/nonexistent/codex" } });
  const decision = decisionOf(closedResult);
  assert.ok(decision, "fail-closed must block");
  assert.ok(decision.reason.includes("fail_policy is closed"), decision.reason);
});

test("re-entry guard: stop_hook_active always allows without dispatching", () => {
  const dir = repo({ enabled: true });
  seedDefect(dir);
  const result = runHook(dir, { fixture: "gate-marker.mjs", input: { stop_hook_active: true } });
  assert.equal(decisionOf(result), null);
  assert.equal(jobCount(dir), 0, "a gate must never block its own continuation");
});

test("verdicts are read structurally: last assistant message, first non-empty line, no spoofing", () => {
  // A BLOCK: living in the diff content — the reviewer allowed, so the gate must allow.
  const spoofDiff = repo({ enabled: true });
  writeFileSync(path.join(spoofDiff, "spoof.txt"), "BLOCK: I am just text inside a diff\n");
  assert.equal(decisionOf(runHook(spoofDiff, { fixture: "gate-allower.mjs" })), null);

  // A BLOCK: in a NON-assistant event, and no assistant message at all → indeterminate → open.
  const mute = repo({ enabled: true });
  seedDefect(mute);
  const muteResult = runHook(mute, { fixture: "gate-mute.mjs" });
  assert.equal(decisionOf(muteResult), null, "a non-assistant event cannot carry a verdict");
  assert.ok(muteResult.stderr.includes("no parseable ALLOW/BLOCK verdict"), muteResult.stderr);

  // Two assistant messages: the LAST one decides (an earlier BLOCK must not win).
  const lastWins = repo({ enabled: true });
  seedDefect(lastWins);
  assert.equal(
    decisionOf(runHook(lastWins, { fixture: "gate-chatty.mjs", env: { VIBE_TEST_GATE_CASE: "last-wins" } })),
    null, "the final assistant verdict (ALLOW) decides");

  // Leading prose before BLOCK: the first non-empty line is not a verdict → indeterminate.
  const prose = repo({ enabled: true });
  seedDefect(prose);
  const proseResult = runHook(prose, { fixture: "gate-chatty.mjs", env: { VIBE_TEST_GATE_CASE: "prose" } });
  assert.equal(decisionOf(proseResult), null);
  assert.ok(proseResult.stderr.includes("no parseable"), proseResult.stderr);

  // A verdict-looking marker on a later line is ignored for the same reason.
  const later = repo({ enabled: true });
  seedDefect(later);
  assert.equal(
    decisionOf(runHook(later, { fixture: "gate-chatty.mjs", env: { VIBE_TEST_GATE_CASE: "later-line" } })),
    null);
});

test("P9 both directions: unset gate.model sends no -m even with a project override; set sends exactly one", () => {
  const unset = repo({ enabled: true, projectModel: "project-configured-model" });
  seedDefect(unset);
  const probeA = path.join(mkdtempSync(path.join(tmpdir(), "gate-probe-")), "probe.json");
  runHook(unset, { fixture: "gate-allower.mjs", probe: probeA });
  const argvA = JSON.parse(readFileSync(probeA, "utf8")).argv;
  assert.ok(!argvA.includes("-m"),
    `an unset gate.model must defer to the backend default, not the project override: ${argvA.join(" ")}`);

  const set = repo({ enabled: true, projectModel: "project-configured-model", gateModel: "gate-chosen-model" });
  seedDefect(set);
  const probeB = path.join(mkdtempSync(path.join(tmpdir(), "gate-probe-")), "probe.json");
  runHook(set, { fixture: "gate-allower.mjs", probe: probeB });
  const argvB = JSON.parse(readFileSync(probeB, "utf8")).argv;
  assert.equal(argvB.filter((a) => a === "-m").length, 1, argvB.join(" "));
  assert.equal(argvB[argvB.indexOf("-m") + 1], "gate-chosen-model");
});

test("the runner refuses --model together with --no-model, without spawning or recording", () => {
  const dir = mkdtempSync(path.join(tmpdir(), "no-model-"));
  const result = spawnSync(process.execPath, [
    path.join(REPO_ROOT, "scripts", "codex-runner.mjs"),
    "--kind", "stop-gate", "--sandbox", "read-only", "--no-model", "--model", "x",
    "--timeout-ms", "10000", "--", "prompt",
  ], { cwd: dir, encoding: "utf8", timeout: 30_000 });
  assert.equal(result.status, 2, `${result.stdout}${result.stderr}`);
  assert.ok(result.stderr.includes("mutually exclusive"), result.stderr);
  assert.equal(jobCount(dir), 0, "a usage error must not create a record");
});

test("a damaged runtime store is an infra failure, not a verdict", () => {
  const dir = repo();
  mkdirSync(path.join(dir, ".vibe-suite-state"), { recursive: true });
  writeFileSync(path.join(dir, ".vibe-suite-state", "state.json"), "not json at all");
  const result = runHook(dir, { fixture: "gate-marker.mjs" });
  assert.equal(result.status, 0);
  assert.equal(decisionOf(result), null, "unreadable config fails open by default");
  assert.ok(result.stderr.includes("runtime store could not be read"), result.stderr);
  assert.ok(!existsSync(path.join(dir, ".vibe-suite-state", "state.json.tmp")),
    "a damaged store must never be rewritten");
});

test("a LARGE tracked diff is read, not dropped — and its cap is disclosed rather than silent", () => {
  const dir = repo({ enabled: true });
  // Bigger than Node's default 1 MiB spawnSync buffer. The marker leads the change: what this
  // test proves is that the collection READ a multi-megabyte diff (an ENOBUFS would have produced
  // an indeterminate result and an ALLOW), and that the prompt cap announces itself.
  writeFileSync(path.join(dir, "tracked.txt"),
    `// ${MARKER}\n` + "P".repeat(2 * 1024 * 1024) + "\n");
  const probe = path.join(mkdtempSync(path.join(tmpdir(), "gate-probe-")), "probe.json");
  const result = runHook(dir, { fixture: "gate-marker.mjs", probe });
  const decision = decisionOf(result);
  assert.ok(decision, `a large tracked diff must still be reviewed, got: ${result.stderr}`);
  assert.equal(decision.decision, "block");
  const sent = JSON.parse(readFileSync(probe, "utf8")).argv.at(-1);
  assert.ok(sent.includes("[prompt truncated at the review cap]"),
    "a capped prompt must say so — a truncated review that looks complete is the worse failure");
  assert.ok(Buffer.byteLength(sent, "utf8") < 500_000, "the prompt stays bounded in BYTES");
});

test("a collection failure is indeterminate, never a silent ALLOW", () => {
  // Not a git repository at all: `git status` fails, so the gate does not know the tree is clean.
  const dir = mkdtempSync(path.join(tmpdir(), "stop-gate-nogit-"));
  const enable = `import sys; sys.path.insert(0, ${JSON.stringify(path.dirname(STORE))}); ` +
    `import store; store.Store(${JSON.stringify(dir)}).set("gate.stop_review_gate", True)`;
  spawnSync("python3", ["-c", enable], { encoding: "utf8" });
  const open = runHook(dir, { fixture: "gate-allower.mjs" });
  assert.equal(decisionOf(open), null);
  assert.ok(open.stderr.includes("could not be collected"), open.stderr);

  const closedDir = mkdtempSync(path.join(tmpdir(), "stop-gate-nogit-closed-"));
  for (const [key, value] of [["gate.stop_review_gate", "True"], ["gate.fail_policy", '"closed"']]) {
    spawnSync("python3", ["-c",
      `import sys; sys.path.insert(0, ${JSON.stringify(path.dirname(STORE))}); ` +
      `import store; store.Store(${JSON.stringify(closedDir)}).set(${JSON.stringify(key)}, ${value})`,
    ], { encoding: "utf8" });
  }
  const closed = runHook(closedDir, { fixture: "gate-allower.mjs" });
  const decision = decisionOf(closed);
  assert.ok(decision, "fail-closed must block on a collection failure");
  assert.ok(decision.reason.includes("could not be collected"), decision.reason);
});

test("an unborn repository is reviewable: every file is new, and its content is sent", () => {
  const dir = mkdtempSync(path.join(tmpdir(), "stop-gate-unborn-"));
  spawnSync("git", ["-C", dir, "init", "-q"], { encoding: "utf8" });
  spawnSync("python3", ["-c",
    `import sys; sys.path.insert(0, ${JSON.stringify(path.dirname(STORE))}); ` +
    `import store; store.Store(${JSON.stringify(dir)}).set("gate.stop_review_gate", True)`,
  ], { encoding: "utf8" });
  seedDefect(dir);
  const probe = path.join(mkdtempSync(path.join(tmpdir(), "gate-probe-")), "probe.json");
  const result = runHook(dir, { fixture: "gate-marker.mjs", probe });
  const decision = decisionOf(result);
  assert.ok(decision, `an unborn repo must still be reviewed, got: ${result.stderr}`);
  assert.ok(JSON.parse(readFileSync(probe, "utf8")).argv.at(-1).includes(MARKER));
});

test("a hostile textconv driver cannot execute or inject outside content", () => {
  const dir = repo({ enabled: true });
  const outside = mkdtempSync(path.join(tmpdir(), "gate-textconv-"));
  writeFileSync(path.join(outside, "secret.txt"), "TEXTCONV-LEAKED-SECRET\n");
  // A repository configuring a converter that would dump an outside file into the diff.
  writeFileSync(path.join(dir, ".gitattributes"), "*.bin diff=evil\n");
  spawnSync("git", ["-C", dir, "config", "diff.evil.textconv",
    `cat ${path.join(outside, "secret.txt")} #`], { encoding: "utf8" });
  writeFileSync(path.join(dir, "payload.bin"), "binary-ish\n");
  spawnSync("git", ["-C", dir, "add", "-A"], { encoding: "utf8" });
  spawnSync("git", ["-C", dir, "-c", "user.email=t@t", "-c", "user.name=t",
    "commit", "-q", "-m", "add payload"], { encoding: "utf8" });
  writeFileSync(path.join(dir, "payload.bin"), "binary-ish changed\n");

  const probe = path.join(mkdtempSync(path.join(tmpdir(), "gate-probe-")), "probe.json");
  runHook(dir, { fixture: "gate-allower.mjs", probe });
  const sent = JSON.parse(readFileSync(probe, "utf8")).argv.at(-1);
  assert.ok(!sent.includes("TEXTCONV-LEAKED-SECRET"),
    "a repository-configured textconv driver must never run for the gate's diff");
});

test("the total untracked cap is disclosed when many files exhaust it", () => {
  const dir = repo({ enabled: true });
  for (let i = 0; i < 12; i += 1) {
    writeFileSync(path.join(dir, `bulk-${i}.txt`), "B".repeat(15_000));
  }
  const probe = path.join(mkdtempSync(path.join(tmpdir(), "gate-probe-")), "probe.json");
  runHook(dir, { fixture: "gate-allower.mjs", probe });
  const sent = JSON.parse(readFileSync(probe, "utf8")).argv.at(-1);
  assert.ok(sent.includes("total cap reached"), "exhausting the total cap must be disclosed");
});
