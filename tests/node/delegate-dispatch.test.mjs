// SPDX-License-Identifier: ISC
// Delegation dispatch + verification, executed FROM THE ARTIFACT (E1.4 / vibe-14).
//
// The subject under test is `commands/delegate.md`'s own recipe: this file extracts the tagged
// canonical blocks from the artifact, instantiates their placeholders, and executes the extracted
// text. It is RED while the artifact (or its blocks) does not exist, and the recipe cannot drift
// from what tests prove — there is no second copy of it here.
//
// The delegate-writer fixture records its cwd (proving the engine ran in the scratch repo, not
// this repo) and creates a real workspace change, so the verify block has an implementation
// outcome to see.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { readRecord } from "../../scripts/lib/jobs.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const ARTIFACT = path.join(REPO_ROOT, "commands", "delegate.md");
const WRITER = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex", "delegate-writer.mjs");

const HOSTILE_PLAN = [
  "Create IMPLEMENTED.txt in the workspace.",
  "hostile bytes that must stay data: $(touch pwned) `touch pwned` \"; touch pwned; \" 'x'",
].join("\n");

function extractBlock(text, tag) {
  assert.ok(text.includes(tag), `commands/delegate.md lacks the ${tag} block`);
  const after = text.split(tag, 2)[1];
  const fenced = after.split("```");
  assert.ok(fenced.length >= 3, `${tag}: no fenced block follows the tag`);
  return fenced[1].replace(/^bash\n/, "");
}

// A repo-resident test script is COMMITTED at the baseline (that is what "resident" means): the
// verify block may execute it only while the engine's run left it untouched. `withTests: false`
// gives a baseline without one, for the engine-created-script case.
function scratchRepo({ withTests = true } = {}) {
  const dir = mkdtempSync(path.join(tmpdir(), "delegate-scratch-"));
  const git = (...args) => {
    const r = spawnSync("git", ["-C", dir, ...args], { encoding: "utf8" });
    assert.equal(r.status, 0, r.stderr);
  };
  git("init", "-q");
  if (withTests) {
    writeFileSync(path.join(dir, "run-tests.sh"), "#!/bin/sh\necho ok > TESTS-RAN\nexit 0\n");
    chmodSync(path.join(dir, "run-tests.sh"), 0o755);
    git("add", "run-tests.sh");
  }
  git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "baseline");
  return dir;
}

test("the artifact's canonical dispatch runs the plan at workspace-write in the scratch repo, argv-safe", async () => {
  const artifact = readFileSync(ARTIFACT, "utf8");
  const dispatchTemplate = extractBlock(artifact, "<!-- canonical-dispatch -->");
  for (const marker of ["--kind delegate", "--sandbox", '"$(cat']) {
    assert.ok(dispatchTemplate.includes(marker), `canonical dispatch lacks: ${marker}`);
  }

  const scratch = scratchRepo();
  const promptFile = path.join(mkdtempSync(path.join(tmpdir(), "delegate-prompt-")), "prompt.md");
  writeFileSync(promptFile,
    "Provenance: unknown — supplied by the operator\n\n" + HOSTILE_PLAN + "\n");
  const probe = path.join(mkdtempSync(path.join(tmpdir(), "delegate-probe-")), "probe.json");

  // The template is env-parameterized — resolved values travel as DATA in the environment, never
  // by textual substitution. Executing it verbatim with only env set is the whole instantiation.
  const result = spawnSync("bash", ["-c", dispatchTemplate], {
    cwd: scratch, encoding: "utf8", timeout: 60_000,
    env: {
      ...process.env,
      CLAUDE_PLUGIN_ROOT: REPO_ROOT,
      VIBE_SUITE_CODEX_BIN: WRITER,
      VIBE_TEST_PROBE: probe,
      DELEGATE_PROMPT_FILE: promptFile,
    },
  });
  assert.equal(result.status, 0, `dispatch failed:\n${result.stdout}\n${result.stderr}`);

  const receipt = JSON.parse(result.stdout.trim().split("\n").at(-1));
  assert.equal(receipt.status, "completed");

  // The engine ran IN THE SCRATCH REPO, at workspace-write, with the prompt intact as one token.
  const recorded = JSON.parse(readFileSync(probe, "utf8"));
  assert.equal(realpathSync(recorded.cwd), realpathSync(scratch),
    "the engine must run in the delegated workspace");
  const argv = recorded.argv;
  assert.ok(argv.includes("-s") && argv[argv.indexOf("-s") + 1] === "workspace-write", argv.join(" "));
  const promptToken = argv.at(-1);
  assert.ok(promptToken.includes("Provenance: unknown — supplied by the operator"));
  assert.ok(promptToken.includes("$(touch pwned)") && promptToken.includes("`touch pwned`"),
    "metacharacters must arrive as literal prompt data");
  assert.ok(!existsSync(path.join(scratch, "pwned")),
    "plan metacharacters must never execute on the host");

  const record = await readRecord(scratch, receipt.jobId);
  assert.equal(record.sandbox, "workspace-write");

  // The fixture implemented something; now the artifact's own verify block must see it.
  assert.ok(existsSync(path.join(scratch, "IMPLEMENTED.txt")));
  const verifyBlock = extractBlock(artifact, "<!-- canonical-verify -->");
  const verify = spawnSync("bash", ["-c", verifyBlock], { cwd: scratch, encoding: "utf8", timeout: 30_000 });
  assert.equal(verify.status, 0, `verify block failed:\n${verify.stdout}\n${verify.stderr}`);
  assert.ok(verify.stdout.includes("IMPLEMENTED.txt"),
    "verification must surface the implementation's workspace change");
  assert.ok(existsSync(path.join(scratch, "TESTS-RAN")),
    "verification must run the target project's tests when present");

  // Trust boundary (grill S3): a repo-resident test script the run TOUCHED is not executed
  // unconfirmed. (a) modified tracked script: the block refuses (exit 3), executes nothing, and
  // names the script, the diff and the confirmation flag.
  rmSync(path.join(scratch, "TESTS-RAN"));
  writeFileSync(path.join(scratch, "run-tests.sh"), "#!/bin/sh\n# touched by the engine\necho ok > TESTS-RAN\nexit 0\n");
  const refused = spawnSync("bash", ["-c", verifyBlock], { cwd: scratch, encoding: "utf8", timeout: 30_000 });
  assert.equal(refused.status, 3, `a changed run-tests.sh must refuse verification:\n${refused.stdout}\n${refused.stderr}`);
  assert.ok(!existsSync(path.join(scratch, "TESTS-RAN")), "the changed script must not have run");
  assert.ok(refused.stdout.includes("verify: refusing to execute repo-resident test scripts"),
    "the refusal marker line — how a refusal is told from a target's own exit status");
  assert.ok(refused.stdout.includes(" M run-tests.sh"), "the porcelain line names the script");
  assert.ok(refused.stdout.includes("+# touched by the engine"), "the diff is shown");
  assert.ok(refused.stdout.includes("DELEGATE_VERIFY_CONFIRMED"), "the confirmation flag is named");
  // (b) after the operator's explicit yes the SAME block runs, carrying the flag as data
  const confirmed = spawnSync("bash", ["-c", verifyBlock], {
    cwd: scratch, encoding: "utf8", timeout: 30_000, env: { ...process.env, DELEGATE_VERIFY_CONFIRMED: "1" },
  });
  assert.equal(confirmed.status, 0, `confirmed verification must run:\n${confirmed.stdout}\n${confirmed.stderr}`);
  assert.ok(existsSync(path.join(scratch, "TESTS-RAN")), "the confirmed script ran");
  // (c) a script the engine CREATED — untracked, invisible to git diff — refuses too
  const fresh = scratchRepo({ withTests: false });
  writeFileSync(path.join(fresh, "run-tests.sh"), "#!/bin/sh\necho ok > TESTS-RAN\nexit 0\n");
  chmodSync(path.join(fresh, "run-tests.sh"), 0o755);
  const created = spawnSync("bash", ["-c", verifyBlock], { cwd: fresh, encoding: "utf8", timeout: 30_000 });
  assert.equal(created.status, 3, `an engine-created run-tests.sh must refuse verification:\n${created.stdout}`);
  assert.ok(!existsSync(path.join(fresh, "TESTS-RAN")), "the created script must not have run");
  assert.ok(created.stdout.includes("?? run-tests.sh"), "the untracked script is named by porcelain");
  assert.ok(created.stdout.includes("+echo ok > TESTS-RAN"),
    "the created file's CONTENT is shown as an addition diff (git diff alone shows nothing for it)");
  // (d) an engine-created package.json whose test script would run: the npm branch IS eligible
  // here (node_modules present, no run-tests.sh), so without the guard `npm test` would execute
  // `touch PWNED` — the refusal is what prevents it, and the created content is shown
  const pkg = scratchRepo({ withTests: false });
  mkdirSync(path.join(pkg, "node_modules"));
  writeFileSync(path.join(pkg, "package.json"), JSON.stringify({ scripts: { test: "touch PWNED" } }) + "\n");
  const pkgRefused = spawnSync("bash", ["-c", verifyBlock], { cwd: pkg, encoding: "utf8", timeout: 60_000 });
  assert.equal(pkgRefused.status, 3, `a created package.json must refuse verification:\n${pkgRefused.stdout}\n${pkgRefused.stderr}`);
  assert.ok(!existsSync(path.join(pkg, "PWNED")), "the created test script must not have run");
  assert.ok(pkgRefused.stdout.includes("?? package.json"));
  assert.ok(pkgRefused.stdout.includes("touch PWNED"), "the created package.json's content is shown");

  // (e) a STAGED modification (git add after the engine edited it): a plain `git diff` shows
  // nothing, so the staged diff must be what the operator sees — refused, shown, not run
  const staged = scratchRepo();
  writeFileSync(path.join(staged, "run-tests.sh"), "#!/bin/sh\n# staged by the engine\necho ok > TESTS-RAN\nexit 0\n");
  assert.equal(spawnSync("git", ["-C", staged, "add", "run-tests.sh"], { encoding: "utf8" }).status, 0);
  const stagedRefused = spawnSync("bash", ["-c", verifyBlock], { cwd: staged, encoding: "utf8", timeout: 30_000 });
  assert.equal(stagedRefused.status, 3, `a staged-modified run-tests.sh must refuse verification:\n${stagedRefused.stdout}`);
  assert.ok(!existsSync(path.join(staged, "TESTS-RAN")), "the staged-modified script must not have run");
  assert.ok(stagedRefused.stdout.includes("M  run-tests.sh"), "porcelain names the staged change");
  assert.ok(stagedRefused.stdout.includes("+# staged by the engine"), "the STAGED diff is shown");
  // (f) a STAGED NEW script (created by the engine, then git add): `git ls-files` now calls it
  // tracked, so the no-index path does not apply — `git diff --cached` must show it whole
  const stagedNew = scratchRepo({ withTests: false });
  writeFileSync(path.join(stagedNew, "run-tests.sh"), "#!/bin/sh\necho ok > TESTS-RAN\nexit 0\n");
  chmodSync(path.join(stagedNew, "run-tests.sh"), 0o755);
  assert.equal(spawnSync("git", ["-C", stagedNew, "add", "run-tests.sh"], { encoding: "utf8" }).status, 0);
  const stagedNewRefused = spawnSync("bash", ["-c", verifyBlock], { cwd: stagedNew, encoding: "utf8", timeout: 30_000 });
  assert.equal(stagedNewRefused.status, 3, `a staged-new run-tests.sh must refuse verification:\n${stagedNewRefused.stdout}`);
  assert.ok(!existsSync(path.join(stagedNew, "TESTS-RAN")), "the staged-new script must not have run");
  assert.ok(stagedNewRefused.stdout.includes("A  run-tests.sh"), "porcelain names the staged addition");
  assert.ok(stagedNewRefused.stdout.includes("+echo ok > TESTS-RAN"), "the staged-new file's CONTENT is shown");

  // Faithful failure: a failing target test fails the verify block — reported, never absorbed.
  // (confirmed, so the script actually executes and its own failure is what fails the block)
  writeFileSync(path.join(scratch, "run-tests.sh"), "#!/bin/sh\nexit 1\n");
  chmodSync(path.join(scratch, "run-tests.sh"), 0o755);
  const failing = spawnSync("bash", ["-c", verifyBlock], {
    cwd: scratch, encoding: "utf8", timeout: 30_000, env: { ...process.env, DELEGATE_VERIFY_CONFIRMED: "1" },
  });
  assert.notEqual(failing.status, 0, "a failing target test must fail verification");
  assert.ok(!failing.stdout.includes("verify: refusing"), "...by its own failure, not by the refusal");
  // A target script that itself exits 3 is NOT mistaken for a refusal: the status is the same,
  // the marker line is what tells them apart.
  writeFileSync(path.join(scratch, "run-tests.sh"), "#!/bin/sh\nexit 3\n");
  chmodSync(path.join(scratch, "run-tests.sh"), 0o755);
  const exits3 = spawnSync("bash", ["-c", verifyBlock], {
    cwd: scratch, encoding: "utf8", timeout: 30_000, env: { ...process.env, DELEGATE_VERIFY_CONFIRMED: "1" },
  });
  assert.equal(exits3.status, 3, "the target's own exit 3 propagates");
  assert.ok(!exits3.stdout.includes("verify: refusing"), "no refusal marker: this is the target's failure");

  // Faithful failure, git dimension: a broken inspection (not a git repo at all) must also fail
  // the block — no later success may mask an earlier failed command (set -euo pipefail).
  const notARepo = mkdtempSync(path.join(tmpdir(), "delegate-notrepo-"));
  const brokenGit = spawnSync("bash", ["-c", verifyBlock], { cwd: notARepo, encoding: "utf8", timeout: 30_000 });
  assert.notEqual(brokenGit.status, 0, "failed git inspection must fail verification");
});

test("override branch: env-carried effort/model values are data — even hostile ones", async () => {
  const artifact = readFileSync(ARTIFACT, "utf8");
  const dispatchTemplate = extractBlock(artifact, "<!-- canonical-dispatch -->");
  const scratch = scratchRepo();
  const promptFile = path.join(mkdtempSync(path.join(tmpdir(), "delegate-prompt-")), "prompt.md");
  writeFileSync(promptFile, "Provenance: authored by Claude (this session)\n\ntrivial task\n");
  const probe = path.join(mkdtempSync(path.join(tmpdir(), "delegate-probe-")), "probe.json");

  const hostileModel = "x; touch pwned2 `touch pwned2`";
  const result = spawnSync("bash", ["-c", dispatchTemplate], {
    cwd: scratch, encoding: "utf8", timeout: 60_000,
    env: {
      ...process.env,
      CLAUDE_PLUGIN_ROOT: REPO_ROOT,
      VIBE_SUITE_CODEX_BIN: WRITER,
      VIBE_TEST_PROBE: probe,
      DELEGATE_PROMPT_FILE: promptFile,
      DELEGATE_EFFORT: "low",
      DELEGATE_MODEL: hostileModel,
    },
  });
  assert.equal(result.status, 0, `override dispatch failed:\n${result.stdout}\n${result.stderr}`);
  const recorded = JSON.parse(readFileSync(probe, "utf8"));
  const argv = recorded.argv;
  assert.ok(argv.includes("-m") && argv[argv.indexOf("-m") + 1] === hostileModel,
    "the model override must arrive as ONE literal argv token");
  assert.ok(!existsSync(path.join(scratch, "pwned2")),
    "a hostile override value must never execute on the host");
});
