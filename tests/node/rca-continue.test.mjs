// SPDX-License-Identifier: ISC
// RCA and thread-resume, executed FROM THE ARTIFACTS (E1.5 / vibe-15).
//
// Same discipline as delegate-dispatch.test.mjs: the subjects under test are the tagged canonical
// blocks in commands/bug-analyze.md and commands/continue.md — extracted, instantiated via env
// (values are data), and executed. RED while the artifacts (or their blocks) do not exist.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createRecord, jobsDir, newRecord, readRecord } from "../../scripts/lib/jobs.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const BUG_ANALYZE = path.join(REPO_ROOT, "commands", "bug-analyze.md");
const CONTINUE = path.join(REPO_ROOT, "commands", "continue.md");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex");

function extractBlock(file, tag) {
  const text = readFileSync(file, "utf8");
  assert.ok(text.includes(tag), `${path.basename(file)} lacks the ${tag} block`);
  const fenced = text.split(tag, 2)[1].split("```");
  assert.ok(fenced.length >= 3, `${tag}: no fenced block follows the tag`);
  return fenced[1].replace(/^bash\n/, "");
}

function run(block, { cwd, env = {} }) {
  return spawnSync("bash", ["-c", block], {
    cwd, encoding: "utf8", timeout: 60_000,
    env: { ...process.env, CLAUDE_PLUGIN_ROOT: REPO_ROOT, ...env },
  });
}

function seededRepo() {
  const dir = mkdtempSync(path.join(tmpdir(), "rca-seed-"));
  mkdirSync(path.join(dir, "src"), { recursive: true });
  writeFileSync(path.join(dir, "src", "adder.js"),
    "export function addTwo(n) { return n + 2; } // bug: addTwo should add one\n");
  writeFileSync(path.join(dir, "src", "weird name.js"),
    "// also mentions addTwo in a spaced filename\n");
  writeFileSync(path.join(dir, "README.md"), "unrelated\n");
  return dir;
}

const TERMINAL = new Set(["completed", "failed", "timed_out", "cancelled"]);
async function waitTerminal(ws, jobId, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const record = await readRecord(ws, jobId).catch(() => null);
    if (record && TERMINAL.has(record.status)) return record;
    if (Date.now() > deadline) throw new Error(`job ${jobId} never terminal`);
    await new Promise((r) => setTimeout(r, 50));
  }
}

test("recon: fixed-string sweep shortlists the defective file; hostile terms and spaced names are inert", () => {
  const repo = seededRepo();
  const recon = extractBlock(BUG_ANALYZE, "<!-- canonical-recon -->");
  const result = run(recon, {
    cwd: repo,
    env: { BUGA_TERMS: "addTwo\n$(touch pwned3)\n--dash-leading\nno such term anywhere" },
  });
  assert.equal(result.status, 0, result.stderr);
  const listed = result.stdout.split("\n").filter(Boolean);
  assert.ok(listed.includes("src/adder.js"),
    "recon paths are ./-normalized so they match prompt FILE: headers and engine mentions "
    + `exactly — got: ${result.stdout}`);
  assert.ok(listed.some((l) => l.includes("src/weird name.js")), "spaced filenames must survive");
  assert.ok(!listed.some((l) => l.includes("README.md")));
  assert.ok(!readdirSync(repo).includes("pwned3"), "hostile terms must never execute");
  assert.ok(listed.length <= 5, "the shortlist cap bounds the sweep");
});

test("wait mode: one read-only dispatch; the assembled report promotes only recon-supported findings", async () => {
  const repo = seededRepo();
  const probe = path.join(mkdtempSync(path.join(tmpdir(), "rca-probe-")), "probe.json");
  const promptFile = path.join(mkdtempSync(path.join(tmpdir(), "rca-prompt-")), "prompt.md");
  writeFileSync(promptFile, [
    "Bug: addTwo returns n+2 instead of n+1.",
    "FILE: src/adder.js", "evidence: return n + 2",
    "FILE: src/weird name.js", "evidence: mentions addTwo",
  ].join("\n") + "\n");

  const dispatch = extractBlock(BUG_ANALYZE, "<!-- canonical-dispatch -->");
  const result = run(dispatch, {
    cwd: repo,
    env: {
      VIBE_SUITE_CODEX_BIN: path.join(FIXTURES, "rca-analyst.mjs"),
      VIBE_TEST_PROBE: probe, BUGA_PROMPT_FILE: promptFile,
    },
  });
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  const receipt = JSON.parse(result.stdout.trim().split("\n").at(-1));
  assert.equal(receipt.status, "completed");
  const argv = JSON.parse(readFileSync(probe, "utf8")).argv;
  assert.ok(argv.includes("-s") && argv[argv.indexOf("-s") + 1] === "read-only",
    "analysis is read-only, always");

  const record = await readRecord(repo, receipt.jobId);
  const shortlistFile = path.join(repo, "shortlist.txt");
  const resultFile = path.join(repo, "engine.txt");
  writeFileSync(shortlistFile, "src/adder.js\nsrc/weird name.js\n");
  writeFileSync(resultFile, record.rawOutput);

  const report = run(extractBlock(BUG_ANALYZE, "<!-- canonical-report -->"), {
    cwd: repo, env: { REPORT_SHORTLIST_FILE: shortlistFile, REPORT_RESULT_FILE: resultFile },
  });
  assert.equal(report.status, 0, report.stderr);
  const findings = report.stdout.split("## Engine analysis")[0];
  assert.ok(findings.includes("src/adder.js"),
    "the defective file must appear in the findings section, not merely somewhere");
  assert.ok(!findings.includes("/tmp/not-in-shortlist.js"),
    "an engine claim without recon support must not be promoted");
  assert.ok(report.stdout.includes("/tmp/not-in-shortlist.js"),
    "...but it stays visible inside the fenced engine text");
});

test("background mode: running receipt, real jobs-result retrieval, findings identical to wait mode", async () => {
  const repo = seededRepo();
  const side = mkdtempSync(path.join(tmpdir(), "rca-bg-"));            // outside the workspace,
  const promptFile = path.join(side, "prompt.md");                     // as the artifact mandates
  const shortlistFile = path.join(side, "shortlist.txt");              // saved at dispatch time
  writeFileSync(promptFile, "Bug: addTwo.\nFILE: src/adder.js\nevidence: return n + 2\n");
  writeFileSync(shortlistFile, "src/adder.js\n");

  const dispatch = extractBlock(BUG_ANALYZE, "<!-- canonical-dispatch -->");
  const env = {
    VIBE_SUITE_CODEX_BIN: path.join(FIXTURES, "rca-analyst.mjs"),
    BUGA_PROMPT_FILE: promptFile,
  };
  const findingsOf = (resultFilePath) => {
    const report = run(extractBlock(BUG_ANALYZE, "<!-- canonical-report -->"), {
      cwd: repo,
      env: { REPORT_SHORTLIST_FILE: shortlistFile, REPORT_RESULT_FILE: resultFilePath },
    });
    assert.equal(report.status, 0, report.stderr);
    return report.stdout.split("## Engine analysis")[0];
  };

  // Wait mode: the baseline findings.
  const wait = run(dispatch, { cwd: repo, env });
  assert.equal(wait.status, 0, wait.stderr);
  const waitReceipt = JSON.parse(wait.stdout.trim().split("\n").at(-1));
  const waitResultFile = path.join(side, "wait-engine.txt");
  writeFileSync(waitResultFile, waitReceipt.rawOutput);
  const waitFindings = findingsOf(waitResultFile);
  assert.ok(waitFindings.includes("src/adder.js"));

  // Background: receipt, then retrieval through the REAL /vibe-suite:jobs result path.
  const bg = run(dispatch, { cwd: repo, env: { ...env, BUGA_BACKGROUND: "1" } });
  assert.equal(bg.status, 0, bg.stderr);
  const receipt = JSON.parse(bg.stdout.trim().split("\n").at(-1));
  assert.equal(receipt.status, "running", "background returns a launch receipt");
  assert.deepEqual(Object.keys(receipt), ["jobId", "status", "threadId", "rawOutput", "verdictState"]);
  await waitTerminal(repo, receipt.jobId);

  const retrieved = spawnSync("node", [path.join(REPO_ROOT, "scripts", "jobs-cli.mjs"),
    "result", receipt.jobId], { cwd: repo, encoding: "utf8", timeout: 30_000 });
  assert.equal(retrieved.status, 0, retrieved.stderr);
  const line = JSON.parse(retrieved.stdout.trim());
  assert.equal(line.status, "completed");

  const bgResultFile = path.join(side, "bg-engine.txt");
  writeFileSync(bgResultFile, line.rawOutput);
  assert.equal(findingsOf(bgResultFile), waitFindings,
    "retrieval-time assembly must produce EXACTLY the wait-mode findings");
});

test("report fence outgrows tilde runs in engine text and strips terminal controls", () => {
  const repo = seededRepo();
  const side = mkdtempSync(path.join(tmpdir(), "rca-fence-"));
  const shortlistFile = path.join(side, "short.txt");
  const resultFile = path.join(side, "hostile.txt");
  writeFileSync(shortlistFile, "src/adder.js\n");
  writeFileSync(resultFile, "src/adder.js ok\n~~~~\nESCAPE-ATTEMPT\n~~~~\n\x1b[31mansi\r junk\n");

  const report = run(extractBlock(BUG_ANALYZE, "<!-- canonical-report -->"), {
    cwd: repo, env: { REPORT_SHORTLIST_FILE: shortlistFile, REPORT_RESULT_FILE: resultFile },
  });
  assert.equal(report.status, 0, report.stderr);
  const fence = "~".repeat(5);
  const parts = report.stdout.split(fence);
  assert.equal(parts.length, 3, `expected one opening and one closing 5-tilde fence:\n${report.stdout}`);
  assert.ok(parts[1].includes("ESCAPE-ATTEMPT") && parts[1].includes("~~~~"),
    "the hostile runs stay INSIDE the longer fence");
  assert.equal(parts[2].trim(), "", "nothing renders after the closing fence");
  assert.ok(!report.stdout.includes("\x1b") && !report.stdout.includes("\r"),
    "terminal controls are stripped, not displayed");
});

test("continue: resumes the prior thread with full inheritance and no re-specified flags", async () => {
  const ws = mkdtempSync(path.join(tmpdir(), "continue-ws-"));
  // Prior job: a real runner dispatch against the emitter, whose record captures the thread id.
  const first = spawnSync("node", [path.join(REPO_ROOT, "scripts", "codex-runner.mjs"),
    "--kind", "review", "--effort", "low", "--sandbox", "read-only",
    "--model", "sentinel-model-for-tests",
    "--timeout-ms", "30000", "--", "first question"], {
    cwd: ws, encoding: "utf8", timeout: 30_000,
    env: { ...process.env, VIBE_SUITE_CODEX_BIN: path.join(FIXTURES, "emitter.mjs") },
  });
  assert.equal(first.status, 0, first.stderr);
  const prior = JSON.parse(first.stdout.trim().split("\n").at(-1));
  assert.equal(prior.threadId, "thread_fixture_0001");

  const probe = path.join(mkdtempSync(path.join(tmpdir(), "continue-probe-")), "probe.json");
  const promptFile = path.join(mkdtempSync(path.join(tmpdir(), "continue-prompt-")), "follow-up.md");
  writeFileSync(promptFile, "follow-up question\n");

  const dispatch = extractBlock(CONTINUE, "<!-- canonical-dispatch -->");
  for (const flag of ["--sandbox", "--effort", "--model", "--kind"]) {
    assert.ok(!dispatch.includes(flag),
      `continue must not re-specify ${flag} — inheritance is the contract`);
  }
  const result = run(dispatch, {
    cwd: ws,
    env: {
      VIBE_SUITE_CODEX_BIN: path.join(FIXTURES, "emitter.mjs"),
      VIBE_TEST_PROBE: probe,
      CONTINUE_JOB_ID: prior.jobId, CONTINUE_PROMPT_FILE: promptFile,
    },
  });
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  const resumed = JSON.parse(result.stdout.trim().split("\n").at(-1));
  assert.equal(resumed.status, "completed");
  assert.notEqual(resumed.jobId, prior.jobId);

  const argv = JSON.parse(readFileSync(probe, "utf8")).argv;
  assert.deepEqual(argv.slice(0, 3), ["exec", "resume", "thread_fixture_0001"],
    "the resume must target the prior record's thread");
  assert.ok(!argv.includes("-s"), "codex exec resume takes no sandbox flag — inherited state only");
  assert.ok(argv.includes("-m") && argv[argv.indexOf("-m") + 1] === "sentinel-model-for-tests",
    "a non-null prior model must reach the resumed engine call — null==null would hide a break");

  const priorRecord = await readRecord(ws, prior.jobId);
  const newRecord2 = await readRecord(ws, resumed.jobId);
  for (const key of ["kind", "sandbox", "effort", "model"]) {
    assert.equal(newRecord2[key], priorRecord[key], `inherited field diverged: ${key}`);
  }
});

test("continue usage errors: invalid job id and thread-less records refuse without a new record", async () => {
  const ws = mkdtempSync(path.join(tmpdir(), "continue-err-"));
  const promptFile = path.join(mkdtempSync(path.join(tmpdir(), "continue-errp-")), "p.md");
  writeFileSync(promptFile, "follow-up\n");
  const dispatch = extractBlock(CONTINUE, "<!-- canonical-dispatch -->");

  const missing = run(dispatch, {
    cwd: ws,
    env: { CONTINUE_JOB_ID: "job_ffffffffffffffffffff", CONTINUE_PROMPT_FILE: promptFile },
  });
  assert.notEqual(missing.status, 0, "a nonexistent job must refuse");

  await createRecord(ws, {
    ...newRecord({ jobId: "job_abababababababababab", kind: "review", sandbox: "read-only",
      effort: "low", model: null, background: false, timeoutMs: 1000, claimDigest: null }),
    status: "completed", threadId: null,
  });
  const noThread = run(dispatch, {
    cwd: ws,
    env: { CONTINUE_JOB_ID: "job_abababababababababab", CONTINUE_PROMPT_FILE: promptFile },
  });
  assert.notEqual(noThread.status, 0);
  assert.ok((noThread.stdout + noThread.stderr).includes("no thread id"), noThread.stderr);
  assert.equal(readdirSync(jobsDir(ws)).filter((n) => /^job_[0-9a-f]{20}\.json$/.test(n)).length, 1,
    "a refused resume must not create a new record");
});

test("continue danger prior: an inherited dangerous sandbox refuses without fresh confirmation", async () => {
  const ws = mkdtempSync(path.join(tmpdir(), "continue-danger-"));
  await createRecord(ws, {
    ...newRecord({ jobId: "job_cdcdcdcdcdcdcdcdcdcd", kind: "delegate",
      sandbox: "danger-full-access", effort: "low", model: null, background: false,
      timeoutMs: 1000, claimDigest: null }),
    status: "completed", threadId: "thread_danger_0001",
  });
  const promptFile = path.join(mkdtempSync(path.join(tmpdir(), "continue-dp-")), "p.md");
  writeFileSync(promptFile, "follow-up\n");
  const dispatch = extractBlock(CONTINUE, "<!-- canonical-dispatch -->");

  const refused = run(dispatch, {
    cwd: ws,
    env: { CONTINUE_JOB_ID: "job_cdcdcdcdcdcdcdcdcdcd", CONTINUE_PROMPT_FILE: promptFile },
  });
  assert.notEqual(refused.status, 0,
    "inheriting a confirmed sandbox is not inheriting the confirmation");
  assert.equal(readdirSync(jobsDir(ws)).filter((n) => /^job_[0-9a-f]{20}\.json$/.test(n)).length, 1);
});
