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
import { chmodSync, existsSync, mkdtempSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
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

function scratchRepo() {
  const dir = mkdtempSync(path.join(tmpdir(), "delegate-scratch-"));
  const git = (...args) => {
    const r = spawnSync("git", ["-C", dir, ...args], { encoding: "utf8" });
    assert.equal(r.status, 0, r.stderr);
  };
  git("init", "-q");
  git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "baseline");
  writeFileSync(path.join(dir, "run-tests.sh"), "#!/bin/sh\necho ok > TESTS-RAN\nexit 0\n");
  chmodSync(path.join(dir, "run-tests.sh"), 0o755);
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

  // Instantiate the template exactly as the command instructs: resolved sandbox, prompt file,
  // optional flags omitted. ${CLAUDE_PLUGIN_ROOT} expands in the shell from the environment.
  const command = dispatchTemplate
    .replace(/\[--effort <flag>\]\s*/g, "")
    .replace(/\[--model <flag>\]\s*/g, "")
    .replace(/\[--background\]\s*/g, "")
    .replace("<resolved>", "workspace-write")
    .replace("<prompt-file>", promptFile);

  const result = spawnSync("bash", ["-c", command], {
    cwd: scratch, encoding: "utf8", timeout: 60_000,
    env: {
      ...process.env,
      CLAUDE_PLUGIN_ROOT: REPO_ROOT,
      VIBE_SUITE_CODEX_BIN: WRITER,
      VIBE_TEST_PROBE: probe,
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

  // Faithful failure: a failing target test fails the verify block — reported, never absorbed.
  writeFileSync(path.join(scratch, "run-tests.sh"), "#!/bin/sh\nexit 1\n");
  chmodSync(path.join(scratch, "run-tests.sh"), 0o755);
  const failing = spawnSync("bash", ["-c", verifyBlock], { cwd: scratch, encoding: "utf8", timeout: 30_000 });
  assert.notEqual(failing.status, 0, "a failing target test must fail verification");
});
