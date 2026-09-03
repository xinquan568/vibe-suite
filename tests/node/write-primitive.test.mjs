// SPDX-License-Identifier: ISC
// The audited Node write primitive, and the destructive defect it exists to close (vibe-103).
//
// The live repro drives the SESSION HOOK, not the library function: the defect's severity comes
// from being reachable with no command run, so a test that called `reapOrphanTemps` directly would
// prove something weaker than what was reported.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawn, spawnSync } from "node:child_process";
import { chmodSync, closeSync, constants as fsConstants, existsSync, linkSync, lstatSync, mkdirSync, openSync, readdirSync, readFileSync, renameSync, statSync, symlinkSync, unlinkSync, utimesSync, writeFileSync, writeSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  appendLineAt, classify, ensureDirAt, isOwnedTempRoot, judgeGenerationsAt, makeOwnedTempDir, publishNew,
  removeOwnedTree, retireGenerationsAt, rotateLogAt, scratch, openSinkAt, secureDirAt, unlinkOwned, writeAtomic,
  EVENT_LINE_MAX, PRIVATE_FILE_MODE, STAMP_KEY,
} from "../../scripts/lib/write.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOK = path.join(REPO_ROOT, "scripts", "session-lifecycle-hook.mjs");
const SIX_HOURS_AGO = () => new Date(Date.now() - 7 * 60 * 60 * 1000);

const mode = (p) => statSync(p).mode & 0o777;
const scratchDir = () => tmpWorkspace("write-prim-");

// --------------------------------------------------------------------- the live destructive defect

for (const event of ["start", "end"]) {
  test(`SessionEvent ${event}: an outside file behind a symlinked jobs dir is NOT deleted`, () => {
    // The issue's repro verbatim: <workspace>/.vibe-suite-state/jobs is a symlink to a directory
    // the user owns, holding a file whose NAME matches the reaper's pattern and whose age is past
    // the bound. Before vibe-103 the hook unlinked it.
    const ws = tmpWorkspace("repro-ws-");
    const outside = tmpWorkspace("repro-outside-");
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
  const bare = tmpWorkspace("vibe-bare-");
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
  const bare = tmpWorkspace("vibe-unowned-");
  await assert.rejects(() => removeOwnedTree(bare), /not an owned temp root/);
  assert.ok(lstatSync(bare).isDirectory());
});

// ------------------------------------------------------------- the routed callers, not the library

test("a record published by createRecord is 0600, and the state dir is 0700", async () => {
  const { createRecord, jobsDir, newRecord, recordPath } = await import("../../scripts/lib/jobs.mjs");
  const ws = tmpWorkspace("routed-record-");
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
  const ws = tmpWorkspace("routed-upgrade-");
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
  const ws = tmpWorkspace("routed-tighten-");
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
  const ws = tmpWorkspace("reaper-anchor-");
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
  const bare = tmpWorkspace("vibe-latch-bare-");
  const runner = path.join(REPO_ROOT, "scripts", "codex-runner.mjs");

  for (const [dir, shouldWrite] of [[owned, true], [bare, false]]) {
    spawn(process.execPath, [runner, "--kind", "review", "--effort", "low", "--sandbox",
      "read-only", "--timeout-ms", "3000", "--", "probe"], {
      cwd: tmpWorkspace("latch-ws-"),
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
  const outside = tmpWorkspace("gate-out-");
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

test("readOwned reads a stamped regular file of ours and nothing else — not through a symlink, not a directory, not another kind", async () => {
  const { readOwned, STAMP_KEY } = await import("../../scripts/lib/write.mjs");
  const { mkdirSync, symlinkSync, writeFileSync } = await import("node:fs");
  const path = (await import("node:path")).default;
  const { tmpWorkspace } = await import("./_tmp.mjs");
  const root = tmpWorkspace("write-readowned-");
  const good = JSON.stringify({ [STAMP_KEY]: { kind: "probe", schema: 1 }, jobId: "x" });
  writeFileSync(path.join(root, "good.json"), good);
  writeFileSync(path.join(root, "unstamped.json"), "{}");
  writeFileSync(path.join(root, "garbage.json"), "not json");
  writeFileSync(path.join(root, "wrongkind.json"), JSON.stringify({ [STAMP_KEY]: { kind: "other", schema: 1 } }));
  writeFileSync(path.join(root, "wrongschema.json"), JSON.stringify({ [STAMP_KEY]: { kind: "probe", schema: 2 } }));
  mkdirSync(path.join(root, "dir.json"));
  const outside = tmpWorkspace("write-readowned-outside-");
  writeFileSync(path.join(outside, "target.json"), good);
  symlinkSync(path.join(outside, "target.json"), path.join(root, "link.json"));   // a symlink to a VALID file of ours

  assert.deepEqual(await readOwned(root, "good.json", ["probe"]), JSON.parse(good));
  for (const name of ["unstamped.json", "garbage.json", "wrongkind.json", "wrongschema.json", "dir.json", "link.json", "absent.json"]) {
    assert.equal(await readOwned(root, name, ["probe"]), null, name);
  }
  await assert.rejects(() => readOwned(root, "../escape.json", ["probe"]), /'\.\.' is not a usable path component|resolves outside/);
});

test("publishDirAt renames a staged directory of ours into an ABSENT destination, and refuses everything else", async () => {
  const { publishDirAt, STAMP_KEY } = await import("../../scripts/lib/write.mjs");
  const { mkdirSync, symlinkSync, writeFileSync, existsSync, lstatSync, readdirSync } = await import("node:fs");
  const path = (await import("node:path")).default;
  const { tmpWorkspace } = await import("./_tmp.mjs");
  const root = tmpWorkspace("write-publishdir-");
  const opts = { stampName: ".stamp", kinds: ["probe"] };
  const stamp = JSON.stringify({ [STAMP_KEY]: { kind: "probe", schema: 1 } });
  const stage = (name, { stamped = true } = {}) => {
    mkdirSync(path.join(root, name), { mode: 0o700 });
    if (stamped) writeFileSync(path.join(root, name, ".stamp"), stamp);
  };
  stage("s1");
  assert.equal(await publishDirAt(root, "s1", "dest", opts), true);
  assert.ok(lstatSync(path.join(root, "dest")).isDirectory() && !existsSync(path.join(root, "s1")));
  assert.deepEqual(readdirSync(path.join(root, "dest")), [".stamp"], "the provenance arrived with the directory");
  stage("s2");
  assert.equal(await publishDirAt(root, "s2", "dest", opts), false, "an existing directory is never replaced");
  assert.ok(existsSync(path.join(root, "s2")), "the staged directory is left for the caller to withdraw");
  writeFileSync(path.join(root, "file"), "x");
  assert.equal(await publishDirAt(root, "s2", "file", opts), false, "an existing file is never replaced");
  stage("unstamped", { stamped: false });
  assert.equal(await publishDirAt(root, "unstamped", "dest2", opts), false, "no provenance, no publication");
  assert.ok(!existsSync(path.join(root, "dest2")));
  const outside = tmpWorkspace("write-publishdir-outside-");
  writeFileSync(path.join(outside, ".stamp"), stamp);
  symlinkSync(outside, path.join(root, "linked"));
  assert.equal(await publishDirAt(root, "linked", "dest3", opts), false, "a symlinked staging directory is refused");
  assert.ok(!existsSync(path.join(root, "dest3")) && existsSync(path.join(outside, ".stamp")));
});

test("removeOwnedDirAt removes only a directory holding exactly our stamp — foreign, non-empty, symlinked and absent answer differently", async () => {
  const { removeOwnedDirAt, STAMP_KEY } = await import("../../scripts/lib/write.mjs");
  const { mkdirSync, symlinkSync, writeFileSync, existsSync } = await import("node:fs");
  const path = (await import("node:path")).default;
  const { tmpWorkspace } = await import("./_tmp.mjs");
  const root = tmpWorkspace("write-rmowned-");
  const opts = { stampName: ".stamp", kinds: ["probe"] };
  const stamp = JSON.stringify({ [STAMP_KEY]: { kind: "probe", schema: 1 } });
  mkdirSync(path.join(root, "ours"), { mode: 0o700 }); writeFileSync(path.join(root, "ours", ".stamp"), stamp);
  mkdirSync(path.join(root, "empty"), { mode: 0o700 });
  mkdirSync(path.join(root, "extra"), { mode: 0o700 }); writeFileSync(path.join(root, "extra", ".stamp"), stamp); writeFileSync(path.join(root, "extra", "more"), "x");
  mkdirSync(path.join(root, "wrong"), { mode: 0o700 }); writeFileSync(path.join(root, "wrong", ".stamp"), JSON.stringify({ [STAMP_KEY]: { kind: "other", schema: 1 } }));
  writeFileSync(path.join(root, "file"), "x");
  const outside = tmpWorkspace("write-rmowned-outside-"); writeFileSync(path.join(outside, ".stamp"), stamp);
  symlinkSync(outside, path.join(root, "link"));

  assert.equal(await removeOwnedDirAt(root, "ours", opts), "removed");
  assert.ok(!existsSync(path.join(root, "ours")));
  assert.equal(await removeOwnedDirAt(root, "ours", opts), "absent");
  assert.equal(await removeOwnedDirAt(root, "empty", opts), "refused", "no provenance");
  assert.equal(await removeOwnedDirAt(root, "extra", opts), "refused", "anything besides the stamp");
  assert.ok(existsSync(path.join(root, "extra", ".stamp")) && existsSync(path.join(root, "extra", "more")), "nothing inside was touched");
  assert.equal(await removeOwnedDirAt(root, "wrong", opts), "refused");
  assert.equal(await removeOwnedDirAt(root, "file", opts), "refused");
  assert.equal(await removeOwnedDirAt(root, "link", opts), "refused", "a symlink is refused, not followed");
  assert.ok(existsSync(path.join(outside, ".stamp")), "the target survives");
  await assert.rejects(() => removeOwnedDirAt(root, "../escape", opts), /'\.\.' is not a usable path component|resolves outside/);
});

test("unlinkOwned applies the caller's identity predicate at the mutation, not beside it", async () => {
  const { unlinkOwned, STAMP_KEY } = await import("../../scripts/lib/write.mjs");
  const { writeFileSync, existsSync } = await import("node:fs");
  const path = (await import("node:path")).default;
  const { tmpWorkspace } = await import("./_tmp.mjs");
  const root = tmpWorkspace("write-predicate-");
  const doc = (id) => JSON.stringify({ [STAMP_KEY]: { kind: "probe", schema: 1 }, id }) + "\n";
  writeFileSync(path.join(root, "a.json"), doc("A"));
  writeFileSync(path.join(root, "b.json"), doc("B"));

  const isA = (parsed) => parsed.id === "A";
  assert.equal(await unlinkOwned(root, "b.json", ["probe"], { predicate: isA }), false,
    "the stamp matches, the identity does not: refused");
  assert.ok(existsSync(path.join(root, "b.json")), "and the file is still there");
  assert.equal(await unlinkOwned(root, "a.json", ["probe"], { predicate: isA }), true);
  assert.ok(!existsSync(path.join(root, "a.json")));
  assert.equal(await unlinkOwned(root, "b.json", ["probe"]), true, "no predicate: the kind decides, as before");
});

test("removeOwnedDirAt with vacateAs takes the path first, and refuses before moving anything it cannot remove", async () => {
  const { removeOwnedDirAt, classify, STAMP_KEY } = await import("../../scripts/lib/write.mjs");
  const { mkdirSync, writeFileSync, existsSync } = await import("node:fs");
  const path = (await import("node:path")).default;
  const { tmpWorkspace } = await import("./_tmp.mjs");
  const root = tmpWorkspace("write-vacate-");
  const opts = { stampName: ".stamp", kinds: ["probe"] };
  const stamp = JSON.stringify({ [STAMP_KEY]: { kind: "probe", schema: 1 } });
  mkdirSync(path.join(root, "ours"), { mode: 0o700 }); writeFileSync(path.join(root, "ours", ".stamp"), stamp);
  mkdirSync(path.join(root, "extra"), { mode: 0o700 });
  writeFileSync(path.join(root, "extra", ".stamp"), stamp); writeFileSync(path.join(root, "extra", "more"), "x");

  const seen = [];
  assert.equal(await removeOwnedDirAt(root, "ours", {
    ...opts, vacateAs: ".staged", onVacated: async () => seen.push(await classify(path.join(root, "ours"))),
  }), "removed");
  assert.deepEqual(seen, ["absent"], "a peer arriving mid-removal sees an absent path, never a stripped directory");
  assert.ok(!existsSync(path.join(root, ".staged")), "and the remains are gone too");

  assert.equal(await removeOwnedDirAt(root, "extra", { ...opts, vacateAs: ".staged2" }), "refused");
  assert.ok(existsSync(path.join(root, "extra", "more")), "a directory holding more than the stamp is refused WHERE IT STANDS");
  assert.ok(!existsSync(path.join(root, ".staged2")));

  mkdirSync(path.join(root, "taken"), { mode: 0o700 });
  mkdirSync(path.join(root, "ours2"), { mode: 0o700 }); writeFileSync(path.join(root, "ours2", ".stamp"), stamp);
  assert.equal(await removeOwnedDirAt(root, "ours2", { ...opts, vacateAs: "taken" }), "refused",
    "an occupied staging name is refused, never replaced");
  assert.ok(existsSync(path.join(root, "ours2", ".stamp")));
});

test("removeEmptyDirAt removes an empty directory and nothing else", async () => {
  const { removeEmptyDirAt } = await import("../../scripts/lib/write.mjs");
  const { mkdirSync, writeFileSync, existsSync, symlinkSync } = await import("node:fs");
  const path = (await import("node:path")).default;
  const { tmpWorkspace } = await import("./_tmp.mjs");
  const root = tmpWorkspace("write-rmempty-");
  mkdirSync(path.join(root, "empty"), { mode: 0o700 });
  mkdirSync(path.join(root, "full"), { mode: 0o700 }); writeFileSync(path.join(root, "full", "x"), "x");
  writeFileSync(path.join(root, "file"), "x");
  const outside = tmpWorkspace("write-rmempty-outside-");
  symlinkSync(outside, path.join(root, "link"));

  assert.equal(await removeEmptyDirAt(root, "empty"), "removed");
  assert.equal(await removeEmptyDirAt(root, "empty"), "absent");
  assert.equal(await removeEmptyDirAt(root, "full"), "refused", "rmdir cannot destroy data");
  assert.ok(existsSync(path.join(root, "full", "x")));
  assert.equal(await removeEmptyDirAt(root, "file"), "refused");
  assert.equal(await removeEmptyDirAt(root, "link"), "refused", "a symlink is not a directory here");
  assert.ok(existsSync(outside), "the target survives");
  await assert.rejects(() => removeEmptyDirAt(root, "../escape"), /'\.\.' is not a usable path component|resolves outside/);
});

test("unlinkOwned answers false when the file it judged is gone by the time it unlinks", async () => {
  // Review finding 2: the final `fs.unlink` sat outside the primitive's catch, so a peer that
  // removed the same file in the window made the call THROW. `removeOwnedDirAt` calls this
  // primitive without a catch of its own, so a second prune sweeping the same aged staging
  // directory aborted the whole sweep instead of treating a lost race as a lost race.
  const root = tmpWorkspace("write-race-");
  const target = path.join(root, "x.json");
  const doc = JSON.stringify({ [STAMP_KEY]: { kind: "probe", schema: 1 }, id: "A" }) + "\n";
  writeFileSync(target, doc, "utf8");
  // The predicate runs on the document read through the handle, immediately before the unlink —
  // which is exactly the window a peer occupies.
  const { existsSync, unlinkSync } = await import("node:fs");
  const peerRemovesItFirst = () => { unlinkSync(target); return true; };
  assert.equal(await unlinkOwned(root, "x.json", ["probe"], { predicate: peerRemovesItFirst }), false,
    "a lost race is false, never a throw");
  assert.ok(!existsSync(target));
});

test("removeOwnedDirAt reports a peer that finished in the validation window as absent, not as a failure",
  async () => {
    const { removeOwnedDirAt } = await import("../../scripts/lib/write.mjs");
    const root = scratchDir();
    const opts = { stampName: ".stamp", kinds: ["probe"] };
    const stamp = JSON.stringify({ [STAMP_KEY]: { kind: "probe", schema: 1 } });
    const { rmSync } = await import("node:fs");
    mkdirSync(path.join(root, "ours"), { mode: 0o700 });
    writeFileSync(path.join(root, "ours", ".stamp"), stamp);
    assert.equal(await removeOwnedDirAt(root, "ours", {
      ...opts, onValidated: () => rmSync(path.join(root, "ours"), { recursive: true }),
    }), "absent", "a peer that removed the whole directory is a lost race, not a refusal");

    mkdirSync(path.join(root, "ours2"), { mode: 0o700 });
    writeFileSync(path.join(root, "ours2", ".stamp"), stamp);
    const { unlinkSync, existsSync } = await import("node:fs");
    assert.equal(await removeOwnedDirAt(root, "ours2", {
      ...opts, onValidated: () => unlinkSync(path.join(root, "ours2", ".stamp")),
    }), "refused", "a peer that removed only the stamp leaves an empty directory for the caller's fallback");
    assert.ok(existsSync(path.join(root, "ours2")));
  });

test("publishDirAt answers false when the destination appears after it was checked", async () => {
  // The catch arm at the rename: `dest` was absent when this call looked, and something landed
  // there before the rename. It is a lost race, not a failure, and nothing at the destination is
  // replaced.
  const { publishDirAt, STAMP_KEY } = await import("../../scripts/lib/write.mjs");
  const { mkdirSync, writeFileSync, readFileSync, existsSync } = await import("node:fs");
  const root = scratchDir();
  const opts = { stampName: ".stamp", kinds: ["probe"] };
  const stamp = JSON.stringify({ [STAMP_KEY]: { kind: "probe", schema: 1 } });
  mkdirSync(path.join(root, "staged"), { mode: 0o700 });
  writeFileSync(path.join(root, "staged", ".stamp"), stamp);

  assert.equal(await publishDirAt(root, "staged", "dest", {
    ...opts, onChecked: () => writeFileSync(path.join(root, "dest"), "someone else's\n"),
  }), false, "a destination that appeared in the window is a lost race");
  assert.equal(readFileSync(path.join(root, "dest"), "utf8"), "someone else's\n",
    "and what landed there is untouched");
  assert.ok(existsSync(path.join(root, "staged", ".stamp")), "the staged directory is left for its caller");
});

test("removeEmptyDirAt answers absent when the directory is gone by the time it calls rmdir", async () => {
  const { removeEmptyDirAt } = await import("../../scripts/lib/write.mjs");
  const { mkdirSync, rmdirSync, writeFileSync, existsSync } = await import("node:fs");
  const root = scratchDir();
  mkdirSync(path.join(root, "empty"), { mode: 0o700 });
  assert.equal(await removeEmptyDirAt(root, "empty", {
    onChecked: () => rmdirSync(path.join(root, "empty")),
  }), "absent", "a peer that removed it first is a lost race, not a refusal");

  mkdirSync(path.join(root, "fills"), { mode: 0o700 });
  assert.equal(await removeEmptyDirAt(root, "fills", {
    onChecked: () => writeFileSync(path.join(root, "fills", "x"), "x"),
  }), "refused", "a directory that gained an entry in the window is refused, and keeps it");
  assert.ok(existsSync(path.join(root, "fills", "x")));
});

test("removeOwnedDirAt answers absent when the directory vanishes before it is vacated", async () => {
  // The catch arm on the vacating rename: the source is gone. `absent` — not `refused`, which would
  // report a leftover for an object a peer has already dealt with.
  const { removeOwnedDirAt, STAMP_KEY } = await import("../../scripts/lib/write.mjs");
  const { mkdirSync, writeFileSync, rmSync, existsSync } = await import("node:fs");
  const root = scratchDir();
  const opts = { stampName: ".stamp", kinds: ["probe"] };
  const stamp = JSON.stringify({ [STAMP_KEY]: { kind: "probe", schema: 1 } });
  mkdirSync(path.join(root, "ours"), { mode: 0o700 });
  writeFileSync(path.join(root, "ours", ".stamp"), stamp);

  assert.equal(await removeOwnedDirAt(root, "ours", {
    ...opts, vacateAs: ".staged",
    onValidated: () => rmSync(path.join(root, "ours"), { recursive: true }),
  }), "absent");
  assert.equal(existsSync(path.join(root, ".staged")), false, "nothing was staged");
});


// ------------------------------------------------------- appendLineAt: the shared-log append (vibe-207)
//
// `openSinkAt` is `O_EXCL` — "a sink is created once, never reopened" — which is right for one
// child's stderr and wrong for a log every process must reopen. `appendLineAt` keeps the exclusive
// CREATE (so the chmod is provably the creator's) and makes only the REOPEN permissive, validating
// the DESCRIPTOR rather than the path.
//
// Two clauses are implemented and deliberately NOT tested here, because an unprivileged test cannot
// reach them honestly:
//   * `st.uid !== process.getuid()` — creating a file owned by another uid needs privilege.
//   * a short `write()` — the kernel decides; forcing one on a regular file is not reachable from
//     the test process. The check exists because a short write on an append log tears a record.
// Writing tests that appear to cover these would be worse than the declared gap: they would pass
// with the clause removed.

test("appendLineAt creates the log 0600 and appends a terminated line (vibe-207)", async () => {
  const root = scratchDir();
  await appendLineAt(root, "events.log", '{"event":"first"}');
  const dest = path.join(root, "events.log");
  assert.equal(mode(dest), 0o600, "a created log is private from the first byte");
  assert.equal(readFileSync(dest, "utf8"), '{"event":"first"}\n', "the line is terminated");

  await appendLineAt(root, "events.log", '{"event":"second"}');
  assert.equal(readFileSync(dest, "utf8"), '{"event":"first"}\n{"event":"second"}\n',
    "the second call REOPENS and appends — this is what openSinkAt cannot do");
});

test("appendLineAt refuses a record with an embedded newline (vibe-207)", async () => {
  const root = scratchDir();
  await assert.rejects(appendLineAt(root, "events.log", 'a\nb'), /newline/,
    "a record is one line by construction; splitting it silently would interleave under concurrency");
  assert.equal(existsSync(path.join(root, "events.log")), false, "nothing is created for a refused record");
});

test("appendLineAt refuses a record over EVENT_LINE_MAX, whole (vibe-207)", async () => {
  const root = scratchDir();
  assert.equal(typeof EVENT_LINE_MAX, "number", "the bound is exported so callers can fit their records");
  await assert.rejects(appendLineAt(root, "events.log", "x".repeat(EVENT_LINE_MAX)), /EVENT_LINE_MAX/,
    "refused rather than split — a split record is two malformed lines, not one long one");
});

test("appendLineAt refuses a symlink on BOTH the create and the reopen path (vibe-207)", async () => {
  const root = scratchDir();
  symlinkSync(path.join(tmpdir(), "vibe-207-nowhere.log"), path.join(root, "events.log"));
  await assert.rejects(appendLineAt(root, "events.log", "{}"), /symlink|ELOOP/,
    "a dangling symlink fails O_EXCL with EEXIST and then O_NOFOLLOW on the reopen");

  const real = scratchDir();
  writeFileSync(path.join(real, "target.log"), "", { mode: 0o600 });
  const root2 = scratchDir();
  symlinkSync(path.join(real, "target.log"), path.join(root2, "events.log"));
  await assert.rejects(appendLineAt(root2, "events.log", "{}"), /symlink|ELOOP/,
    "a symlink to a real private file is still refused — the link is what would be written through");
});

test("appendLineAt refuses a directory at the log path (vibe-207)", async () => {
  const root = scratchDir();
  mkdirSync(path.join(root, "events.log"));
  await assert.rejects(appendLineAt(root, "events.log", "{}"), /directory|EISDIR|not a regular file/,
    "a directory is what an emitter's degrade test plants; it must refuse, not throw something unhandled");
});

test("appendLineAt refuses a hard-linked log — the substitution O_NOFOLLOW cannot see (vibe-207)", async () => {
  const root = scratchDir();
  const dest = path.join(root, "events.log");
  writeFileSync(dest, "", { mode: 0o600 });
  linkSync(dest, path.join(root, "events.log.alias"));
  assert.equal(lstatSync(dest).nlink, 2, "the fixture really is hard-linked");
  await assert.rejects(appendLineAt(root, "events.log", "{}"), /link|nlink/,
    "a second name for the inode means someone else can read every record we write");
});

test("appendLineAt refuses a group- or world-readable log, and does not repair it (vibe-207)", async () => {
  const root = scratchDir();
  const dest = path.join(root, "events.log");
  writeFileSync(dest, "keep\n", { mode: 0o640 });
  await assert.rejects(appendLineAt(root, "events.log", "{}"), /mode|0600|private/,
    "0600 is enforced on the reopen path, which is where the issue's requirement would otherwise be lost");
  assert.equal(mode(dest), 0o640, "REFUSE, NEVER REPAIR — chmodding a file we did not create is a mutation we cannot justify");
  assert.equal(readFileSync(dest, "utf8"), "keep\n", "and nothing was appended to it");
});

test("appendLineAt refuses a path outside the root (vibe-207)", async () => {
  const root = scratchDir();
  await assert.rejects(appendLineAt(root, path.join("..", "escape.log"), "{}"), /outside/,
    "containment is checked before anything is opened");
});

test("appendLineAt never re-chmods a log it did not create (vibe-207)", async () => {
  const root = scratchDir();
  const dest = path.join(root, "events.log");
  await appendLineAt(root, "events.log", "{}");
  chmodSync(dest, 0o400);                     // still private, but not writable by us
  await assert.rejects(appendLineAt(root, "events.log", "{}"), /EACCES|permission/i,
    "an unwritable private log is refused rather than chmodded back open");
  assert.equal(mode(dest), 0o400, "the mode we found is the mode we leave");
});

// --- vibe-207 step 9: the branches the Step-8 review found undeclared ------------------------------

test("appendLineAt refuses a FIFO WITHOUT blocking — the whole point of O_NONBLOCK (vibe-207)", async () => {
  const root = scratchDir();
  const fifo = path.join(root, "events.log");
  const made = spawnSync("mkfifo", [fifo], { encoding: "utf8" });
  if (made.status !== 0) return;                       // no mkfifo on this platform: skip, do not fake

  // The assertion that matters is that this RETURNS. An O_WRONLY open of a FIFO with no reader blocks
  // forever without O_NONBLOCK, and an emitter that hangs has broken the promise that observability
  // never affects what it observes — worse than one that loses a record.
  const started = Date.now();
  await assert.rejects(appendLineAt(root, "events.log", "{}"), /FIFO|regular file|ENXIO/,
    "a FIFO with no reader is refused");
  assert.ok(Date.now() - started < 5_000,
    `the open took ${Date.now() - started}ms — without O_NONBLOCK it would never return at all`);
});

test("appendLineAt refuses a non-regular file it CAN open — the isFile() branch (vibe-207)", async () => {
  const root = scratchDir();
  const fifo = path.join(root, "events.log");
  const made = spawnSync("mkfifo", [fifo], { encoding: "utf8" });
  if (made.status !== 0) return;                       // no mkfifo here: skip, do not fake

  // A reader on the other end makes the O_NONBLOCK open SUCCEED, so the refusal must come from the
  // descriptor `fstat` rather than from the open. That is the `isFile()` branch, which the directory
  // fixture never reaches — it fails at the open.
  //
  // THIS PROCESS is the reader, opened O_RDONLY|O_NONBLOCK so the open returns at once and the fd is
  // held for the whole assertion. Two earlier attempts were not coordination at all: a timed sleep,
  // and then a probe that opened the FIFO for writing — which sent EOF when it exited, so `cat`
  // finished and there was no reader left by the time the assertion ran.
  const reader = openSync(fifo, fsConstants.O_RDONLY | fsConstants.O_NONBLOCK);
  try {
    await assert.rejects(appendLineAt(root, "events.log", "{}"),
      /not a regular file/,
      "the refusal must be the fstat one — matching the ENXIO text too would let this pass on the " +
      "no-reader path the previous test already covers");
  } finally {
    closeSync(reader);
  }
});

test("appendLineAt chmods what it creates, restoring bits a RESTRICTIVE umask removed (vibe-207)", async () => {
  // A permissive umask proves nothing: open(path, flags, mode) creates with mode & ~umask, so a
  // umask of 0 still yields 0600 and the chmod is invisible. A umask can only REMOVE bits — so the
  // discriminating fixture is a restrictive one, where the create yields 0400 and only the chmod
  // brings the owner-write bit back.
  //
  // My first version of this test used umask 0 and passed with the chmod deleted. Mutation caught
  // it, which is the reason the mutation was run.
  const root = scratchDir();
  const previous = process.umask(0o277);               // strips group/other AND owner-write
  try {
    await appendLineAt(root, "events.log", "{}");
    assert.equal(mode(path.join(root, "events.log")), 0o600,
      "without the chmod on the created descriptor this is 0400 — created read-only, and the next " +
      "append would fail EACCES on a log this process just made");
  } finally {
    process.umask(previous);
  }
});

// ------------------------------------------------- vibe-266: rotation and retention, the primitives
//
// Every mutation retention needs lives here: `appendLineAt` learns to observe the live file's size
// through its own descriptor before writing; `rotateLogAt` moves a judged inode to a fresh name;
// `judgeGenerationsAt` is the one recogniser the sweep and the reader share; `retireGenerationsAt`
// unlinks what it found eligible. The interleavings that defeated six designs are forced through
// seams, never raced. The uid clause of the recogniser and of `rotateLogAt`'s shape check, and
// `rotateLogAt`'s final-`rename` `ENOENT`, are DECLARED untestable here — the first because an
// unprivileged test cannot make a file another uid owns (as `appendLineAt`'s uid clause is declared
// above), the second because the comparison→rename gap deliberately has no seam.

const SHAPE = /^events\.log\.\d{8}T\d{6}Z\.[0-9a-f]{32}$/;
const genName = (stamp = "20260903T120000Z") => `events.log.${stamp}.${randomBytes(16).toString("hex")}`;
const HOUR = 60 * 60 * 1000;
const setAge = (p, ageMs, now) => { const t = new Date(now - ageMs); utimesSync(p, t, t); };
const rec = (n) => JSON.stringify({ event: "e", n });
/** Presence by lstat — `existsSync` follows symlinks and reports a dangling link as absent. */
const present = (p) => { try { lstatSync(p); return true; } catch { return false; } };

test("appendLineAt with maxBytes appends below the threshold and reports the inode and size it observed (vibe-266)", async () => {
  const root = scratchDir();
  const r1 = await appendLineAt(root, "events.log", rec(1), { maxBytes: 10_000 });
  assert.equal(r1.outcome, "appended");
  assert.equal(r1.ino, statSync(path.join(root, "events.log")).ino, "the creator's own fstat, through the handle it wrote through");
  assert.equal(r1.size, statSync(path.join(root, "events.log")).size);
  const r2 = await appendLineAt(root, "events.log", rec(2), { maxBytes: 10_000 });
  assert.equal(r2.outcome, "appended");
  assert.equal(r2.ino, r1.ino, "the reopen observed the same inode");
});

test("appendLineAt with maxBytes returns full and writes NOTHING when the live file is at the threshold (vibe-266)", async () => {
  const root = scratchDir();
  const dest = path.join(root, "events.log");
  await appendLineAt(root, "events.log", "x".repeat(200));
  const before = readFileSync(dest);
  const r = await appendLineAt(root, "events.log", rec(1), { maxBytes: 100 });
  assert.equal(r.outcome, "full");
  assert.equal(r.ino, statSync(dest).ino, "the caller learns which inode it judged");
  assert.equal(r.size, before.length);
  assert.deepEqual(readFileSync(dest), before, "an observer of a full file never writes into it (O2-i)");
});

test("appendLineAt without maxBytes behaves exactly as before, and its result carries the inode (vibe-266)", async () => {
  const root = scratchDir();
  await appendLineAt(root, "events.log", "x".repeat(3000));
  const r = await appendLineAt(root, "events.log", rec(1));
  assert.equal(r.outcome, "appended", "no threshold, no refusal — the vibe-207 contract is unchanged");
  assert.equal(readFileSync(path.join(root, "events.log"), "utf8").split("\n").filter(Boolean).length, 2);
});

test("a rename between the EEXIST and the reopen is retried once and the record lands (vibe-266)", async () => {
  const root = scratchDir();
  const dest = path.join(root, "events.log");
  await appendLineAt(root, "events.log", rec(0));                                  // the live exists: the next call's create sees EEXIST
  const calls = [];
  const r = await appendLineAt(root, "events.log", rec(1), {
    onBeforeReopen: (attempt) => { calls.push(attempt); if (attempt === 1) renameSync(dest, `${dest}.rotated`); },
  });
  assert.equal(r.outcome, "appended");
  assert.deepEqual(calls, [1], "the retry's create succeeded — no second reopen");
  assert.equal(readFileSync(dest, "utf8"), `${rec(1)}\n`, "the record is in the fresh live file");
  assert.equal(readFileSync(`${dest}.rotated`, "utf8"), `${rec(0)}\n`, "and the rotated file holds only the old record");
});

test("two renames-away exhaust the single retry and the ENOENT is thrown, as before (vibe-266)", async () => {
  // The exhaustion needs a live file to REAPPEAR between the retry's create and its reopen, which
  // no single seam before the reopen can arrange; `onBeforeCreate` is the additive seam for it.
  const root = scratchDir();
  const dest = path.join(root, "events.log");
  await appendLineAt(root, "events.log", rec(0));
  const trail = [];
  await assert.rejects(appendLineAt(root, "events.log", rec(1), {
    onBeforeCreate: (attempt) => { trail.push(`create${attempt}`); if (attempt === 2) writeFileSync(dest, "", { mode: 0o600 }); },
    onBeforeReopen: (attempt) => { trail.push(`reopen${attempt}`); renameSync(dest, `${dest}.moved${attempt}`); },
  }), /ENOENT/, "a second ENOENT is not retried: the record is dropped by the caller's catch, not looped on");
  assert.deepEqual(trail, ["create1", "reopen1", "create2", "reopen2"]);
});

test("rotateLogAt moves the judged inode to a fresh name, preserving content and mtime, and a fresh live can follow (vibe-266)", async () => {
  const root = scratchDir();
  const dest = path.join(root, "events.log");
  await appendLineAt(root, "events.log", rec(1));
  const now = Date.now(); setAge(dest, 3 * HOUR, now);
  const before = statSync(dest);
  const name = genName();
  assert.equal(await rotateLogAt(root, "events.log", { generationRel: name, expectedIno: before.ino }), "rotated");
  const gen = statSync(path.join(root, name));
  assert.equal(gen.ino, before.ino, "the same inode under a new name");
  assert.equal(gen.mtimeMs, before.mtimeMs, "rename does not touch mtime — content age survives rotation");
  assert.equal(readFileSync(path.join(root, name), "utf8"), `${rec(1)}\n`);
  assert.equal(existsSync(dest), false);
  const r = await appendLineAt(root, "events.log", rec(2), { maxBytes: 100 });
  assert.equal(r.outcome, "appended", "the next appender creates a fresh live");
  assert.notEqual(r.ino, before.ino);
});

test("rotateLogAt refuses to rename onto a name that exists — 'exists', nothing moved (vibe-266)", async () => {
  const root = scratchDir();
  await appendLineAt(root, "events.log", rec(1));
  const taken = genName();
  writeFileSync(path.join(root, taken), "occupied\n", { mode: 0o600 });
  const ino = statSync(path.join(root, "events.log")).ino;
  assert.equal(await rotateLogAt(root, "events.log", { generationRel: taken, expectedIno: ino }), "exists");
  assert.equal(readFileSync(path.join(root, taken), "utf8"), "occupied\n", "the occupant is untouched");
  assert.equal(statSync(path.join(root, "events.log")).ino, ino, "the live file is untouched");
});

test("rotateLogAt returns moved and renames nothing when the seam replaces the live before the observation (vibe-266)", async () => {
  const root = scratchDir();
  const dest = path.join(root, "events.log");
  await appendLineAt(root, "events.log", rec(1));
  const judged = statSync(dest).ino;
  const name = genName();
  const outcome = await rotateLogAt(root, "events.log", {
    generationRel: name, expectedIno: judged,
    onChecked: () => { renameSync(dest, path.join(root, genName())); writeFileSync(dest, `${rec(2)}\n`, { mode: 0o600 }); },
  });
  assert.equal(outcome, "moved", "the pathname denotes a replacement inode: the stale rotator moves nothing");
  assert.equal(existsSync(path.join(root, name)), false);
  assert.equal(readFileSync(dest, "utf8"), `${rec(2)}\n`, "the replacement live is exactly where it was");
});

test("rotateLogAt returns absent when the live file is removed inside the seam — the pre-comparison lstat site (vibe-266)", async () => {
  const root = scratchDir();
  const dest = path.join(root, "events.log");
  await appendLineAt(root, "events.log", rec(1));
  const ino = statSync(dest).ino;
  assert.equal(await rotateLogAt(root, "events.log", {
    generationRel: genName(), expectedIno: ino, onChecked: () => renameSync(dest, path.join(root, genName())),
  }), "absent");
  assert.equal(await rotateLogAt(root, "events.log", { generationRel: genName(), expectedIno: ino }), "absent", "and when it was never there");
});

test("rotateLogAt refuses a live path that is not the writer's shape: a symlink, a directory, a hard-linked file, a 0644 file (vibe-266)", async () => {
  const cases = {
    symlink: (root) => symlinkSync(path.join(tmpdir(), "vibe-266-nowhere"), path.join(root, "events.log")),
    directory: (root) => mkdirSync(path.join(root, "events.log")),
    "hard link": (root) => { writeFileSync(path.join(root, "events.log"), "x\n", { mode: 0o600 }); linkSync(path.join(root, "events.log"), path.join(root, "alias")); },
    "0644": (root) => { writeFileSync(path.join(root, "events.log"), "x\n", { mode: 0o600 }); chmodSync(path.join(root, "events.log"), 0o644); },
  };
  for (const [label, arrange] of Object.entries(cases)) {
    const root = scratchDir();
    arrange(root);
    const ino = lstatSync(path.join(root, "events.log")).ino;
    assert.equal(await rotateLogAt(root, "events.log", { generationRel: genName(), expectedIno: ino }), "refused", label);
    assert.equal(present(path.join(root, "events.log")), true, `${label}: nothing moved`);   // lstat: a dangling symlink is still THERE
  }
});

test("rotateLogAt requires the inode the caller judged (vibe-266)", async () => {
  const root = scratchDir();
  await assert.rejects(rotateLogAt(root, "events.log", { generationRel: genName() }), /expectedIno/);
});

test("judgeGenerationsAt and retireGenerationsAt: past the eligibility delay retired, inside it kept — with an injected clock (vibe-266)", async () => {
  const root = scratchDir();
  const now = Date.now();
  const old = genName("20260801T000000Z"); writeFileSync(path.join(root, old), "old\n", { mode: 0o600 }); setAge(path.join(root, old), 10 * HOUR, now);
  const young = genName("20260903T000000Z"); writeFileSync(path.join(root, young), "young\n", { mode: 0o600 }); setAge(path.join(root, young), 1 * HOUR, now);
  const judged = await judgeGenerationsAt(root, ".", { shape: SHAPE, olderThanMs: 5 * HOUR, now });
  assert.deepEqual(judged, { eligible: [old], kept: 1, refused: [] });
  const swept = await retireGenerationsAt(root, ".", { shape: SHAPE, olderThanMs: 5 * HOUR, now });
  assert.deepEqual(swept, { retired: [old], kept: 1, refused: [] });
  assert.equal(existsSync(path.join(root, old)), false);
  assert.equal(existsSync(path.join(root, young)), true);
});

test("the eligibility boundary is exact to the millisecond of the injected clock, not the host filesystem's precision (vibe-266)", async () => {
  const root = scratchDir();
  const now = Date.now();
  const g = genName(); writeFileSync(path.join(root, g), "g\n", { mode: 0o600 }); setAge(path.join(root, g), 10_000, now);
  const age = now - statSync(path.join(root, g)).mtimeMs;              // whatever the filesystem stored
  assert.equal((await judgeGenerationsAt(root, ".", { shape: SHAPE, olderThanMs: age + 1, now })).kept, 1, "one ms inside: kept");
  assert.deepEqual((await judgeGenerationsAt(root, ".", { shape: SHAPE, olderThanMs: age - 1, now })).eligible, [g], "one ms past: eligible");
});

test("the live file is never a candidate, however old (vibe-266)", async () => {
  const root = scratchDir();
  const now = Date.now();
  writeFileSync(path.join(root, "events.log"), "ancient\n", { mode: 0o600 }); setAge(path.join(root, "events.log"), 400 * 24 * HOUR, now);
  const swept = await retireGenerationsAt(root, ".", { shape: SHAPE, olderThanMs: HOUR, now });
  assert.deepEqual(swept, { retired: [], kept: 0, refused: [] }, "fails the name clause: not kept, not eligible, not refused");
  assert.equal(existsSync(path.join(root, "events.log")), true);
});

test("the sibling recogniser: five near-miss negatives, each failing exactly ONE clause, plus two non-isolating defences (vibe-266)", async () => {
  const now = Date.now();
  const aged = (root, name, mode = 0o600) => { const p = path.join(root, name); writeFileSync(p, "aged\n", { mode }); chmodSync(p, mode); setAge(p, 10 * HOUR, now); return p; };
  const judge = (root) => judgeGenerationsAt(root, ".", { shape: SHAPE, olderThanMs: HOUR, now });

  // clause 1 — the name: 31 hex digits, everything else valid. Not a candidate at all.
  { const root = scratchDir(); const p = aged(root, genName().slice(0, -1));
    assert.deepEqual(await judge(root), { eligible: [], kept: 0, refused: [] }); assert.ok(existsSync(p)); }
  // clause 2 — a regular file: a FIFO with one link and mode 0600 fails only this clause.
  { const root = scratchDir(); const name = genName(); const fifo = path.join(root, name);
    if (spawnSync("mkfifo", [fifo]).status === 0) {
      chmodSync(fifo, 0o600); setAge(fifo, 10 * HOUR, now);
      const j = await judge(root); assert.deepEqual(j.refused, [name]); assert.deepEqual(j.eligible, []); assert.ok(existsSync(fifo));
    } }                                                                 // no mkfifo: skipped, not faked
  // clause 3 — one link: a second name that does NOT match the shape, so only one candidate exists and it fails nlink alone.
  { const root = scratchDir(); const name = genName(); const p = aged(root, name); linkSync(p, path.join(root, "alias.txt"));
    const j = await judge(root); assert.deepEqual(j.refused, [name]); assert.ok(existsSync(p)); assert.ok(existsSync(path.join(root, "alias.txt"))); }
  // clause 4 — our uid: DECLARED untestable unprivileged (see the header comment of this section).
  // clause 5 — private mode: 0644, everything else valid.
  { const root = scratchDir(); const name = genName(); const p = aged(root, name, 0o644);
    const j = await judge(root); assert.deepEqual(j.refused, [name]); assert.ok(existsSync(p)); }
  // clause 6 — the age: inside the delay, everything else valid.
  { const root = scratchDir(); const name = genName(); const p = path.join(root, name); writeFileSync(p, "fresh\n", { mode: 0o600 }); setAge(p, 10 * 60_000, now);
    assert.deepEqual(await judge(root), { eligible: [], kept: 1, refused: [] }); assert.ok(existsSync(p)); }
  // Non-isolating defences: a symlink and a directory with valid names fail the regular-file clause (and more); neither is unlinked or followed.
  { const root = scratchDir(); const target = path.join(scratchDir(), "target"); writeFileSync(target, "target\n", { mode: 0o600 }); setAge(target, 10 * HOUR, now);
    const name = genName(); symlinkSync(target, path.join(root, name));
    const j = await judge(root); assert.deepEqual(j.refused, [name]);
    await retireGenerationsAt(root, ".", { shape: SHAPE, olderThanMs: HOUR, now });
    assert.ok(existsSync(path.join(root, name)) && existsSync(target), "not unlinked, not followed"); }
  { const root = scratchDir(); const name = genName(); mkdirSync(path.join(root, name)); setAge(path.join(root, name), 10 * HOUR, now);
    const j = await judge(root); assert.deepEqual(j.refused, [name]); assert.ok(existsSync(path.join(root, name))); }
});

test("mtime is the retention clock, not the timestamp in the name — design 5's failure (vibe-266)", async () => {
  const root = scratchDir();
  const now = Date.now();
  const oldName = genName("20200101T000000Z"); writeFileSync(path.join(root, oldName), "fresh content\n", { mode: 0o600 }); setAge(path.join(root, oldName), 60_000, now);
  const newName = genName("20990101T000000Z"); writeFileSync(path.join(root, newName), "old content\n", { mode: 0o600 }); setAge(path.join(root, newName), 10 * HOUR, now);
  const j = await judgeGenerationsAt(root, ".", { shape: SHAPE, olderThanMs: HOUR, now });
  assert.deepEqual(j.eligible, [newName], "the name says 2099, the content is ten hours old: eligible");
  assert.equal(j.kept, 1, "the name says 2020, the content is a minute old: kept");
});

test("a peer that unlinks the qualified generation first is a lost race, skipped — designs 1, 2 and 6 (vibe-266)", async () => {
  const root = scratchDir();
  const now = Date.now();
  const g = genName(); writeFileSync(path.join(root, g), "g\n", { mode: 0o600 }); setAge(path.join(root, g), 10 * HOUR, now);
  let newer;
  const swept = await retireGenerationsAt(root, ".", {
    shape: SHAPE, olderThanMs: HOUR, now,
    onQualified: (name) => { unlinkSyncSafe(path.join(root, name)); newer = genName(); writeFileSync(path.join(root, newer), "newer\n", { mode: 0o600 }); },
  });
  assert.deepEqual(swept.retired, [], "the peer got there first: ENOENT, not a throw, not a retired row");
  assert.deepEqual(swept.refused, []);
  assert.ok(existsSync(path.join(root, newer)), "a generation created inside the window is untouched — its name was never qualified");
});

test("a straggler write through a pre-rotation descriptor BEFORE qualification refreshes mtime and protects the generation (vibe-266)", async () => {
  const root = scratchDir();
  const dest = path.join(root, "events.log");
  const now = Date.now();
  await appendLineAt(root, "events.log", rec(1)); setAge(dest, 10 * HOUR, now);
  const fd = openSync(dest, "a");
  try {
    const name = genName();
    assert.equal(await rotateLogAt(root, "events.log", { generationRel: name, expectedIno: statSync(dest).ino }), "rotated");
    writeSync(fd, `${rec(2)}\n`);                                                // lands in the rotated inode
    const j = await judgeGenerationsAt(root, ".", { shape: SHAPE, olderThanMs: HOUR, now: Date.now() });
    assert.equal(j.kept, 1, "the straggler's write moved mtime to now: inside the floor");
    assert.deepEqual(j.eligible, []);
  } finally { closeSync(fd); }
});

test("a name listed by readdir but gone before its lstat is skipped — neither kept nor eligible nor refused (vibe-266)", async () => {
  const root = scratchDir();
  const now = Date.now();
  const g = genName(); writeFileSync(path.join(root, g), "g\n", { mode: 0o600 }); setAge(path.join(root, g), 10 * HOUR, now);
  const j = await judgeGenerationsAt(root, ".", {
    shape: SHAPE, olderThanMs: HOUR, now, onListed: (names) => { assert.ok(names.includes(g)); unlinkSyncSafe(path.join(root, g)); },
  });
  assert.deepEqual(j, { eligible: [], kept: 0, refused: [] });
});

test("judgeGenerationsAt and retireGenerationsAt on a non-directory or an unreadable directory answer empty, never throw (vibe-266)", async () => {
  const root = scratchDir();
  writeFileSync(path.join(root, "notadir"), "x\n", { mode: 0o600 });
  assert.deepEqual(await judgeGenerationsAt(root, "notadir", { shape: SHAPE, olderThanMs: HOUR }), { eligible: [], kept: 0, refused: [] });
  assert.deepEqual(await retireGenerationsAt(root, "notadir", { shape: SHAPE, olderThanMs: HOUR }), { retired: [], kept: 0, refused: [] });
  if (typeof process.getuid === "function" && process.getuid() !== 0) {   // root reads anything: skip honestly
    mkdirSync(path.join(root, "sealed"), { mode: 0o700 });
    writeFileSync(path.join(root, "sealed", genName()), "g\n", { mode: 0o600 });
    chmodSync(path.join(root, "sealed"), 0o000);
    try {
      assert.deepEqual(await judgeGenerationsAt(root, "sealed", { shape: SHAPE, olderThanMs: HOUR }), { eligible: [], kept: 0, refused: [] });
    } finally { chmodSync(path.join(root, "sealed"), 0o700); }
  }
});

/** unlink that tolerates a missing file — the peer in a race may already have won. */
function unlinkSyncSafe(p) { try { unlinkSync(p); } catch (error) { if (error.code !== "ENOENT") throw error; } }
