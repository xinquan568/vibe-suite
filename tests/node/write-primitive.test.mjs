// SPDX-License-Identifier: ISC
// The audited Node write primitive, and the destructive defect it exists to close (vibe-103).
//
// The live repro drives the SESSION HOOK, not the library function: the defect's severity comes
// from being reachable with no command run, so a test that called `reapOrphanTemps` directly would
// prove something weaker than what was reported.

import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import {
  chmodSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, statSync, symlinkSync,
  utimesSync, writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  classify, ensureDirAt, isOwnedTempRoot, makeOwnedTempDir, publishNew, removeOwnedTree, scratch,
  openSinkAt, secureDirAt, unlinkOwned, writeAtomic, PRIVATE_FILE_MODE, STAMP_KEY,
} from "../../scripts/lib/write.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOK = path.join(REPO_ROOT, "scripts", "session-lifecycle-hook.mjs");
const SIX_HOURS_AGO = () => new Date(Date.now() - 7 * 60 * 60 * 1000);

const mode = (p) => statSync(p).mode & 0o777;
const scratchDir = () => mkdtempSync(path.join(tmpdir(), "write-prim-"));

// --------------------------------------------------------------------- the live destructive defect

for (const event of ["start", "end"]) {
  test(`SessionEvent ${event}: an outside file behind a symlinked jobs dir is NOT deleted`, () => {
    // The issue's repro verbatim: <workspace>/.vibe-suite-state/jobs is a symlink to a directory
    // the user owns, holding a file whose NAME matches the reaper's pattern and whose age is past
    // the bound. Before vibe-103 the hook unlinked it.
    const ws = mkdtempSync(path.join(tmpdir(), "repro-ws-"));
    const outside = mkdtempSync(path.join(tmpdir(), "repro-outside-"));
    const victim = path.join(outside, "notes.tmp.archive");
    writeFileSync(victim, "the user's own notes\n", "utf8");
    utimesSync(victim, SIX_HOURS_AGO(), SIX_HOURS_AGO());

    mkdirSync(path.join(ws, ".vibe-suite-state"), { recursive: true });
    symlinkSync(outside, path.join(ws, ".vibe-suite-state", "jobs"));

    const result = spawnSync(process.execPath, [HOOK, "--event", event],
      { cwd: ws, encoding: "utf8", timeout: 30_000 });

    assert.equal(result.status, 0, "the hook must stay non-fatal");
    assert.ok(readdirSync(outside).includes("notes.tmp.archive"),
      "a file outside the workspace was deleted through a symlinked jobs directory");
    assert.equal(readFileSync(victim, "utf8"), "the user's own notes\n");
  });
}

// --------------------------------------------------------------------- ownership, not name shape

test("unlinkOwned collects a stamped file and leaves an unstamped one that matches by name", async () => {
  const root = scratchDir();
  const stamped = path.join(root, "job_a.tmp.1.aaa");
  const bare = path.join(root, "job_b.tmp.1.bbb");
  writeFileSync(stamped, JSON.stringify({ [STAMP_KEY]: { kind: "job-scratch", schema: 1 } }));
  writeFileSync(bare, "{}");

  assert.equal(await unlinkOwned(root, "job_a.tmp.1.aaa", ["job-scratch"]), true);
  assert.equal(await unlinkOwned(root, "job_b.tmp.1.bbb", ["job-scratch"]), false,
    "a name pattern is not ownership — an unstamped file must survive");
  assert.ok(readdirSync(root).includes("job_b.tmp.1.bbb"));
});

test("unlinkOwned refuses a symlink whose target carries a valid stamp", async () => {
  const root = scratchDir();
  const elsewhere = path.join(scratchDir(), "real.json");
  writeFileSync(elsewhere, JSON.stringify({ [STAMP_KEY]: { kind: "job-scratch", schema: 1 } }));
  symlinkSync(elsewhere, path.join(root, "link.tmp.1.ccc"));

  assert.equal(await unlinkOwned(root, "link.tmp.1.ccc", ["job-scratch"]), false);
  assert.equal(classify(path.join(root, "link.tmp.1.ccc")) instanceof Promise, true);
  assert.ok(lstatSync(elsewhere).isFile(), "the symlink's target must be untouched");
});

// --------------------------------------------------------------------- modes

test("scratch sets the mode AT CREATION, before anything can read the file", async () => {
  const root = scratchDir();
  const { handle, path: staged } = await scratch(root, "record", PRIVATE_FILE_MODE);
  try {
    const info = await handle.stat();
    assert.equal(info.mode & 0o777, PRIVATE_FILE_MODE,
      "creating at the default and chmod-ing after leaves a window — the window is the leak");
  } finally {
    await handle.close();
  }
  assert.equal(mode(staged), PRIVATE_FILE_MODE);
});

test("an explicit mode wins over preservation, so an existing 0644 record becomes 0600", async () => {
  const root = scratchDir();
  const dest = path.join(root, "record.json");
  writeFileSync(dest, "{}", { mode: 0o644 });
  chmodSync(dest, 0o644);

  await writeAtomic(root, dest, JSON.stringify({ updated: true }), { mode: PRIVATE_FILE_MODE });
  assert.equal(mode(dest), PRIVATE_FILE_MODE,
    "preserve-by-default would leave an already-0644 record at 0644 forever");
});

test("absent an explicit mode, an existing file's mode is preserved", async () => {
  const root = scratchDir();
  const dest = path.join(root, "doc.md");
  writeFileSync(dest, "one", { mode: 0o640 });
  chmodSync(dest, 0o640);
  await writeAtomic(root, dest, "two");
  assert.equal(mode(dest), 0o640);
});

for (const umask of [0o077, 0o000]) {
  test(`the exact mode lands under umask ${umask.toString(8).padStart(3, "0")}`, async () => {
    const previous = process.umask(umask);
    try {
      const root = scratchDir();
      const dest = path.join(root, "record.json");
      await writeAtomic(root, dest, "{}", { mode: PRIVATE_FILE_MODE });
      assert.equal(mode(dest), PRIVATE_FILE_MODE, "open()'s mode is umask-filtered; chmod is not");
    } finally {
      process.umask(previous);
    }
  });
}

// --------------------------------------------------------------------- symlink refusal

test("writeAtomic refuses a symlinked destination rather than converting it", async () => {
  const root = scratchDir();
  const outside = path.join(scratchDir(), "target.txt");
  writeFileSync(outside, "theirs");
  symlinkSync(outside, path.join(root, "dest.json"));

  await assert.rejects(() => writeAtomic(root, path.join(root, "dest.json"), "ours"),
    /is a symlink/);
  assert.equal(readFileSync(outside, "utf8"), "theirs");
});

test("writeAtomic refuses a DANGLING symlink, which exists() would report absent", async () => {
  const root = scratchDir();
  symlinkSync(path.join(root, "nowhere"), path.join(root, "dangling.json"));
  await assert.rejects(() => writeAtomic(root, path.join(root, "dangling.json"), "x"),
    /is a symlink/);
});

test("assertRoot refuses a containment root that is itself a symlink", async () => {
  const real = scratchDir();
  const linkRoot = path.join(scratchDir(), "root-link");
  symlinkSync(real, linkRoot);
  await assert.rejects(() => writeAtomic(linkRoot, path.join(linkRoot, "f.json"), "x"),
    /containment root is a symlink/);
});

// --------------------------------------------------------------------- create-only vs replace

test("publishNew loses the race with false, but ERRORS on a pre-existing symlink", async () => {
  const root = scratchDir();
  assert.equal(await publishNew(root, path.join(root, "a.json"), "{}"), true);
  assert.equal(await publishNew(root, path.join(root, "a.json"), "{}"), false,
    "whoever appeared concurrently wins — never an overwrite");

  symlinkSync(path.join(root, "a.json"), path.join(root, "b.json"));
  await assert.rejects(() => publishNew(root, path.join(root, "b.json"), "{}"), /is a symlink/,
    "'something else is there' and 'someone won the race' are different answers");
});

// --------------------------------------------------------------------- directories

test("secureDirAt tightens an ALREADY-EXISTING 0755 directory, which a creation mode cannot", async () => {
  const root = scratchDir();
  const state = path.join(root, ".vibe-suite-state");
  mkdirSync(state, { mode: 0o755 });
  chmodSync(state, 0o755);
  await secureDirAt(root, ".vibe-suite-state");
  assert.equal(mode(state), 0o700);
});

test("ensureDirAt refuses a symlinked path component", async () => {
  const root = scratchDir();
  symlinkSync(scratchDir(), path.join(root, "state"));
  // Either diagnostic is a refusal: containment catches it as an escape when the link points out
  // of the root, the component check catches it when it does not. What must never happen is a
  // directory created through the link.
  await assert.rejects(() => ensureDirAt(root, path.join("state", "jobs")),
    /path component is a symlink|resolves outside|escapes/);
  assert.equal(readdirSync(root).length, 1, "nothing was created through the symlink");
});

// --------------------------------------------------------------------- cross-process temp roots

test("a parent-created owned temp root is recognised by a SPAWNED CHILD", async () => {
  const owned = await makeOwnedTempDir("vibe-cross");
  const bare = mkdtempSync(path.join(tmpdir(), "vibe-bare-"));
  const probe = `
    import { isOwnedTempRoot } from ${JSON.stringify(path.join(REPO_ROOT, "scripts/lib/write.mjs"))};
    const [owned, bare] = process.argv.slice(2);
    console.log(JSON.stringify({
      owned: await isOwnedTempRoot(owned), bare: await isOwnedTempRoot(bare),
    }));`;
  const script = path.join(owned, "probe.mjs");
  writeFileSync(script, probe, "utf8");

  const out = spawnSync(process.execPath, [script, owned, bare],
    { encoding: "utf8", timeout: 30_000 });
  const seen = JSON.parse(out.stdout.trim());
  assert.equal(seen.owned, true, "an in-process registry cannot answer in a child; the marker can");
  assert.equal(seen.bare, false, "a bare mkdtemp directory carries no ownership");

  chmodSync(owned, 0o755);
  assert.equal(await isOwnedTempRoot(owned), false, "a loosened root is no longer private");
  chmodSync(owned, 0o700);
  await removeOwnedTree(owned);
});

// ------------------------------------------------------- intermediate components and containment

test("an INTERMEDIATE symlink cannot be published through — no race required", async () => {
  // The escape a review found: with `root/link -> outside` and `outside/new.json` absent, walking
  // past the link to the root answered "inside", and the final classify saw "absent" because lstat
  // followed the link. Both writers then published into `outside`.
  const root = scratchDir();
  const outside = scratchDir();
  symlinkSync(outside, path.join(root, "link"));
  const dest = path.join(root, "link", "new.json");

  await assert.rejects(() => writeAtomic(root, dest, "ours"), /intermediate path component/);
  await assert.rejects(() => publishNew(root, dest, "ours"), /intermediate path component/);
  assert.deepEqual(readdirSync(outside), [], "nothing may be published through the link");
});

test("secureDirAt cannot chmod outside its root", async () => {
  const root = scratchDir();
  const outside = scratchDir();
  mkdirSync(path.join(outside, "victim"), { mode: 0o755 });
  chmodSync(path.join(outside, "victim"), 0o755);

  await assert.rejects(
    () => secureDirAt(root, path.join("..", path.basename(outside), "victim")),
    /escapes|resolves outside|intermediate/);
  assert.equal(mode(path.join(outside, "victim")), 0o755, "an outside directory must be untouched");
});

test("a stage that fails AFTER creating its scratch leaves nothing behind", async () => {
  const root = scratchDir();
  // Content `writeFile` rejects, so the failure happens with the scratch already on disk — the
  // earlier version of this cell was refused before staging and proved nothing about cleanup.
  await assert.rejects(() => writeAtomic(root, path.join(root, "dest.json"), Symbol("nope")));
  assert.deepEqual(readdirSync(root).filter((n) => n.endsWith(".vibe-tmp")), [],
    "a scratch nobody will publish is a private file left behind");
});

test("'..' is refused on the LITERAL path, before any normalisation", async () => {
  // The escape a review found after the first fix: `path.resolve`/`relative`/`join` all collapse
  // `link/..` lexically, while the kernel follows the link first — so a containment check on the
  // collapsed path and a write through the original disagree, and the write wins.
  const root = scratchDir();
  const outside = scratchDir();
  mkdirSync(path.join(outside, "child"));
  symlinkSync(path.join(outside, "child"), path.join(root, "link"));

  for (const raw of [`${root}/link/../new.json`, `${root}/link/../../new.json`,
    `${root}/../escape.json`]) {
    await assert.rejects(() => writeAtomic(root, raw, "pwned"), /not a usable path component/);
    await assert.rejects(() => publishNew(root, raw, "pwned"), /not a usable path component/);
  }
  assert.deepEqual(readdirSync(outside).filter((n) => n !== "child"), [],
    "nothing may be written outside through a normalisation disagreement");
});

test("a symlinked root passed with a trailing separator is still refused", async () => {
  // lstat("/path/") follows the trailing-slash symlink and reports a directory, so the root check
  // has to normalise before it looks.
  const real = scratchDir();
  const linkRoot = path.join(scratchDir(), "root-link");
  symlinkSync(real, linkRoot);
  await assert.rejects(() => writeAtomic(`${linkRoot}/`, path.join(real, "f.json"), "x"),
    /containment root is a symlink/);
});

test("removeOwnedTree refuses a root it does not own", async () => {
  const bare = mkdtempSync(path.join(tmpdir(), "vibe-unowned-"));
  await assert.rejects(() => removeOwnedTree(bare), /not an owned temp root/);
  assert.ok(lstatSync(bare).isDirectory());
});

// ------------------------------------------------------------- the routed callers, not the library

test("a record published by createRecord is 0600, and the state dir is 0700", async () => {
  const { createRecord, jobsDir, newRecord, recordPath } = await import("../../scripts/lib/jobs.mjs");
  const ws = mkdtempSync(path.join(tmpdir(), "routed-record-"));
  const record = newRecord({
    jobId: "job_00000000000000000000", kind: "review", sandbox: "read-only", effort: "low",
    model: null, background: false, timeoutMs: 1000, claimDigest: null,
  });
  await createRecord(ws, record);

  assert.equal(mode(recordPath(ws, "job_00000000000000000000")), PRIVATE_FILE_MODE,
    "job records can hold raw model output");
  assert.equal(mode(jobsDir(ws)), 0o700);
  assert.equal(mode(path.join(ws, ".vibe-suite-state")), 0o700);
});

test("an ALREADY-0644 canonical record becomes 0600 when the store updates it", async () => {
  const { createRecord, newRecord, recordPath, updateRecord } =
    await import("../../scripts/lib/jobs.mjs");
  const ws = mkdtempSync(path.join(tmpdir(), "routed-upgrade-"));
  await createRecord(ws, newRecord({
    jobId: "job_11111111111111111111", kind: "review", sandbox: "read-only", effort: "low",
    model: null, background: false, timeoutMs: 1000, claimDigest: null,
  }));
  // The state an installation upgraded from before vibe-103 is actually in.
  chmodSync(recordPath(ws, "job_11111111111111111111"), 0o644);

  await updateRecord(ws, "job_11111111111111111111", { threadId: "t-1" });
  assert.equal(mode(recordPath(ws, "job_11111111111111111111")), PRIVATE_FILE_MODE,
    "preserve-by-default would leave it 0644 forever — the mode override is what fixes upgrades");
});

test("an existing 0755 state directory is tightened on the next store use", async () => {
  const { createRecord, newRecord } = await import("../../scripts/lib/jobs.mjs");
  const ws = mkdtempSync(path.join(tmpdir(), "routed-tighten-"));
  mkdirSync(path.join(ws, ".vibe-suite-state", "jobs"), { recursive: true, mode: 0o755 });
  chmodSync(path.join(ws, ".vibe-suite-state"), 0o755);
  chmodSync(path.join(ws, ".vibe-suite-state", "jobs"), 0o755);

  await createRecord(ws, newRecord({
    jobId: "job_22222222222222222222", kind: "review", sandbox: "read-only", effort: "low",
    model: null, background: false, timeoutMs: 1000, claimDigest: null,
  }));
  assert.equal(mode(path.join(ws, ".vibe-suite-state")), 0o700);
  assert.equal(mode(path.join(ws, ".vibe-suite-state", "jobs")), 0o700);
});

test("the reaper trusts the WORKSPACE, not the last path component", async () => {
  // `.vibe-suite-state` is a symlink whose `jobs` child is a real directory outside the workspace:
  // asserting only the final component accepted it, and a stamped file there was deleted.
  const { reapOrphanTemps } = await import("../../scripts/lib/jobs.mjs");
  const ws = mkdtempSync(path.join(tmpdir(), "reaper-anchor-"));
  const outside = scratchDir();
  mkdirSync(path.join(outside, "jobs"));
  const bait = path.join(outside, "jobs", "job_x.tmp.1.aaa");
  writeFileSync(bait, JSON.stringify({ [STAMP_KEY]: { kind: "job-scratch", schema: 1 } }));
  utimesSync(bait, SIX_HOURS_AGO(), SIX_HOURS_AGO());
  symlinkSync(outside, path.join(ws, ".vibe-suite-state"));

  assert.equal(await reapOrphanTemps(ws), 0);
  assert.ok(readdirSync(path.join(outside, "jobs")).includes("job_x.tmp.1.aaa"),
    "a stamp is copyable; the containment chain is what says the directory is ours");
});

for (const umask of [0o077, 0o000]) {
  test(`preservation is exact under umask ${umask.toString(8).padStart(3, "0")}`, async () => {
    const previous = process.umask(umask);
    try {
      const root = scratchDir();
      const dest = path.join(root, "doc.md");
      writeFileSync(dest, "one");
      chmodSync(dest, 0o640);
      await writeAtomic(root, dest, "two");              // no explicit mode: preserve
      assert.equal(mode(dest), 0o640, "preservation must survive the process umask too");
    } finally {
      process.umask(previous);
    }
  });
}

test("the latch signal is written 0600, and only inside an owned root", async () => {
  const { spawnSync: spawn } = await import("node:child_process");
  const owned = await makeOwnedTempDir("vibe-latch-mode");
  const bare = mkdtempSync(path.join(tmpdir(), "vibe-latch-bare-"));
  const runner = path.join(REPO_ROOT, "scripts", "codex-runner.mjs");

  for (const [dir, shouldWrite] of [[owned, true], [bare, false]]) {
    spawn(process.execPath, [runner, "--kind", "review", "--effort", "low", "--sandbox",
      "read-only", "--timeout-ms", "3000", "--", "probe"], {
      cwd: mkdtempSync(path.join(tmpdir(), "latch-ws-")),
      env: { ...process.env, VIBE_SUITE_TEST_LATCH_DIR: dir,
        VIBE_SUITE_CODEX_BIN: path.join(REPO_ROOT, "tests/fixtures/fake-codex/emitter.mjs") },
      encoding: "utf8", timeout: 30_000,
    });
    const signals = readdirSync(dir).filter((n) => n.endsWith(".signal"));
    if (shouldWrite) {
      assert.ok(signals.length > 0, "an owned root must receive the latch signal");
      assert.equal(mode(path.join(dir, signals[0])), PRIVATE_FILE_MODE);
    } else {
      assert.deepEqual(signals, [],
        "an env-supplied path that is not an owned root is not a permitted destination");
    }
  }
  await removeOwnedTree(owned);
});

test("the gate record refuses an out-of-root and a symlinked destination", async () => {
  const { spawnSync: spawn } = await import("node:child_process");
  const probe = path.join(REPO_ROOT, "scripts", "agy-contract-probe.mjs");
  const outside = mkdtempSync(path.join(tmpdir(), "gate-out-"));
  const target = path.join(outside, "gate-status.json");

  const run = (file) => spawn(process.execPath, [probe, "--write-record"], {
    env: { ...process.env, VIBE_SUITE_AGY_GATE_FILE: file,
      VIBE_SUITE_AGY_BIN: path.join(REPO_ROOT, "tests/fixtures/fake-codex/emitter.mjs") },
    encoding: "utf8", timeout: 60_000,
  });

  run(target);
  assert.ok(!readdirSync(outside).includes("gate-status.json"),
    "an out-of-root gate destination must be refused, not written");

  const owned = await makeOwnedTempDir("gate-owned");
  const linked = path.join(owned, "link.json");
  symlinkSync(target, linked);
  run(linked);
  assert.ok(!readdirSync(outside).includes("gate-status.json"),
    "a symlinked gate destination must not be followed");

  // The positive control. Without it the two assertions above pass just as well when the probe
  // never wrote anything at all — an absence-only test reports safety it did not establish.
  run(path.join(owned, "gate-status.json"));
  assert.ok(readdirSync(owned).includes("gate-status.json"),
    "a permitted destination inside an owned root must still be written");
  await removeOwnedTree(owned).catch(() => {});
});

test("openSinkAt creates an exclusive 0600 append sink a child can inherit, and refuses an existing file, a symlink and an out-of-root path (vibe-182)", async () => {
  const root = scratchDir();
  const dest = path.join(root, "job.log");
  const sink = await openSinkAt(root, dest);
  try {
    assert.equal(mode(dest), PRIVATE_FILE_MODE, "the sink is private from creation, umask notwithstanding");
    // A child whose stderr IS the sink's descriptor writes straight into the file — the whole point.
    const child = spawnSync(process.execPath, ["-e", "process.stderr.write('from the child\\n')"],
      { stdio: ["ignore", "ignore", sink.fd] });
    assert.equal(child.status, 0);
  } finally {
    await sink.close();
  }
  assert.equal(readFileSync(dest, "utf8"), "from the child\n", "the child's stderr landed in the sink");
  await assert.rejects(openSinkAt(root, dest), /already exists/,
    "a sink is created once — never reopened over an existing file");
  const link = path.join(root, "link.log");
  symlinkSync(path.join(root, "elsewhere.log"), link);
  await assert.rejects(openSinkAt(root, link), /symlink/, "a (dangling) symlink is refused, not followed");
  await assert.rejects(openSinkAt(root, path.join(tmpdir(), "vibe-182-outside.log")), /outside/,
    "containment holds for sinks as for every other write");
});
