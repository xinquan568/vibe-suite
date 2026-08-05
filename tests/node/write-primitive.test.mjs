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
  secureDirAt, unlinkOwned, writeAtomic, PRIVATE_FILE_MODE, STAMP_KEY,
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

test("removeOwnedTree refuses a root it does not own", async () => {
  const bare = mkdtempSync(path.join(tmpdir(), "vibe-unowned-"));
  await assert.rejects(() => removeOwnedTree(bare), /not an owned temp root/);
  assert.ok(lstatSync(bare).isDirectory());
});
