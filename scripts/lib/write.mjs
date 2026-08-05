// SPDX-License-Identifier: ISC
//
// The audited write primitive for the Node surface (vibe-103), the counterpart to
// `scripts/lib/bridge.py` on the Python side. Independently implemented from that module's
// *invariants*, not ported from its code (D7).
//
// **What this closes.** A symlink observed at a destination is refused rather than followed
// (`lstat`, never `exists` — a dangling symlink reports `false` from `exists` and gets followed,
// which was the single most repeated defect #94 catalogued). Ownership is proven by a stamp, never
// inferred from a name. Modes are set at creation and then made exact before publication, so no
// window exists in which a private file is readable. Replacing a file and publishing a new one are
// different operations with different failure modes, and conflating them loses "whoever appeared
// concurrently wins".
//
// **What this does NOT close, stated plainly.** Node exposes no `openat`/dir-fd-relative pathname
// parameter, so every operation here is path-based. Between the moment this module observes a path
// and the moment it mutates it, the *directory components and the final component alike* can be
// substituted — for `rename`, `unlink`, and `link` equally. The guarantee is therefore "refuses the
// state it observed", not "proves nothing was substituted afterwards".
//
// What makes that unexploitable across users is containment plus permissions, and the three trusted
// roots do not share one invariant:
//   - `<workspace>/.vibe-suite-state/**` — private state; `0700`, re-tightened by `secureDirAt` on
//     every run, so no other uid can create or swap entries inside it.
//   - owned temp roots — `0700` from `mkdtemp`, carrying the marker `isOwnedTempRoot` validates.
//   - the plugin checkout (the gate record's parent) — NOT private state. Its only invariant is
//     that a trusted install is not group- or world-writable. That is an installation property this
//     module does not create; it is disclosed rather than absorbed into the `0700` claim.
// A same-uid attacker is out of scope here exactly as it is for `bridge.py`.
//
// **Durability cost.** A transaction may sync a scratch file and its directory for the CAS and
// again for the canonical publication. Directory syncs are issued once per publication, never for a
// scratch about to be unlinked.
//
// **Nothing here prevents a future edit from calling `fs` directly.** That is the AST lint of
// issue #103's requirement 7, which is NOT delivered by this module and remains open.

import { randomBytes } from "node:crypto";
import { constants, promises as fs } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

export class WriteError extends Error {
  constructor(message) {
    super(message);
    this.name = "WriteError";
  }
}

/** The stamp that proves this suite wrote a file. A path is not ownership; a name is not ownership. */
export const STAMP_KEY = "_vibe-suite_owned";
export const STAMP_SCHEMA = 1;
const TEMP_ROOT_KIND = "temp-root";
const MARKER_NAME = ".vibe-suite-owned.json";

/** `mkdtemp` gives 0700; state directories are held there too. */
const PRIVATE_DIR_MODE = 0o700;
/** Records, prompts and latches are private: they can hold raw model output. */
export const PRIVATE_FILE_MODE = 0o600;
const DEFAULT_FILE_MODE = 0o644;

const SCRATCH_ATTEMPTS = 64;
const OPEN_WRITE = constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW;

/** Realpaths of temp roots this process made. A cache for speed — never the authority. */
const ownedTempCache = new Set();

/**
 * The node kind at `p`, by `lstat`. A broken symlink is a symlink, not `absent`: reporting it
 * absent is how a caller ends up following it.
 */
export async function classify(p) {
  let info;
  try {
    info = await fs.lstat(p);
  } catch (error) {
    if (error.code === "ENOENT") return "absent";
    throw error;
  }
  if (info.isSymbolicLink()) return "symlink";
  if (info.isDirectory()) return "dir";
  if (info.isFile()) return "file";
  return "other";
}

/**
 * A containment root must not be the escape it is meant to contain. When the root is itself a
 * symlink, every "is this inside?" comparison resolves through it and passes.
 */
export async function assertRoot(root) {
  const kind = await classify(root);
  if (kind === "symlink") throw new WriteError(`${root}: containment root is a symlink`);
  if (kind !== "dir") throw new WriteError(`${root}: containment root is not a directory (${kind})`);
}

/** `target` must resolve inside `root`. The nearest existing ancestor is what gets resolved. */
export async function assertInside(root, target) {
  // Both sides must be resolved before they are compared. Comparing a lexical target against a
  // resolved root fails wherever the temp directory is itself a symlink (`/var` -> `/private/var`
  // on macOS), and `path.resolve` has already normalised any `..` away, so the lexical pre-check
  // that used to sit here rejected legitimate paths without catching anything the walk misses.
  const resolvedRoot = await fs.realpath(root);
  let probe = path.resolve(target);
  while (true) {
    const kind = await classify(probe);
    // Containment asks where the entry *is*, so a symlink is resolved no further than its own
    // parent. Resolving through it would report the link's target as the location and answer
    // "outside" for a link that sits perfectly well inside the root — and the caller would never
    // learn it was a link at all, which is the thing that actually has to be refused.
    if (kind !== "absent" && kind !== "symlink") break;
    const parent = path.dirname(probe);
    if (parent === probe) throw new WriteError(`${target}: no existing ancestor`);
    probe = parent;
  }
  const resolvedProbe = await fs.realpath(probe);
  const rel = path.relative(resolvedRoot, resolvedProbe);
  if (rel !== "" && (rel.startsWith("..") || path.isAbsolute(rel))) {
    throw new WriteError(`${target}: resolves outside ${root}`);
  }
}

/**
 * An exclusive scratch file, created at `mode`.
 *
 * Returns the handle **and its path**: a `FileHandle` carries no pathname, and `link`, `rename` and
 * `unlink` all need one. The name is unpredictable because a fixed `.tmp` path is a path the user
 * may own, and `O_EXCL | O_NOFOLLOW` means an existing entry is a refusal rather than a target.
 */
export async function scratch(dir, name, mode) {
  let lastError;
  for (let attempt = 0; attempt < SCRATCH_ATTEMPTS; attempt += 1) {
    const candidate = path.join(dir, `.${name}.${randomBytes(6).toString("hex")}.vibe-tmp`);
    try {
      const handle = await fs.open(candidate, OPEN_WRITE, mode);
      return { handle, path: candidate };
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      lastError = error;
    }
  }
  throw new WriteError(`${dir}: no free scratch name after ${SCRATCH_ATTEMPTS} attempts`, {
    cause: lastError,
  });
}

/**
 * Write `content` into a scratch file at the exact mode, then hand back its path.
 *
 * `open`'s mode argument is filtered by the process umask, so passing 0600 does not mean the file
 * *is* 0600. The file is still created restrictively — `chmod` only ever loosens what umask
 * tightened, and it happens before publication, so there is no window in which the published file
 * is more permissive than asked.
 */
async function stage(dir, name, content, mode) {
  const { handle, path: staged } = await scratch(dir, name, mode);
  try {
    await handle.writeFile(content, "utf8");
    await handle.chmod(mode);
    await handle.sync();
    return staged;
  } finally {
    await handle.close();
  }
}

async function syncDir(dir) {
  const handle = await fs.open(dir, constants.O_RDONLY);
  try {
    await handle.sync();
  } finally {
    await handle.close();
  }
}

/**
 * Replace `dest` atomically.
 *
 * An explicit `mode` always wins. Only its absence preserves an existing file's mode — preserving
 * by default would leave a record that is already 0644 at 0644 forever, which is how a privacy
 * fix becomes a no-op on exactly the installations that need it.
 */
export async function writeAtomic(root, dest, content, { mode } = {}) {
  await assertRoot(root);
  await assertInside(root, dest);
  const kind = await classify(dest);
  if (kind === "symlink") {
    throw new WriteError(`${dest}: is a symlink — refusing to convert a link into a file`);
  }
  if (kind === "dir" || kind === "other") throw new WriteError(`${dest}: is a ${kind}`);

  let effective = mode;
  if (effective === undefined) {
    effective = kind === "file" ? (await fs.stat(dest)).mode & 0o777 : DEFAULT_FILE_MODE;
  }
  const dir = path.dirname(dest);
  const staged = await stage(dir, path.basename(dest), content, effective);
  try {
    await fs.rename(staged, dest);
  } catch (error) {
    await fs.unlink(staged).catch(() => {});
    throw error;
  }
  await syncDir(dir);
}

/**
 * Publish `dest` only if nothing is there — the create-only counterpart to `writeAtomic`.
 *
 * `false` means someone else won the race. A symlink or non-file already at `dest` is an *error*,
 * not a loss: "something else is there" and "someone else got there first" are different answers,
 * and returning `false` for both would let a caller learn "it exists" by having clobbered it.
 */
export async function publishNew(root, dest, content, { mode = DEFAULT_FILE_MODE } = {}) {
  await assertRoot(root);
  await assertInside(root, dest);
  const kind = await classify(dest);
  if (kind === "symlink" || kind === "dir" || kind === "other") {
    throw new WriteError(`${dest}: is a ${kind} — refusing to publish over it`);
  }
  const dir = path.dirname(dest);
  const staged = await stage(dir, path.basename(dest), content, mode);
  try {
    await fs.link(staged, dest);
  } catch (error) {
    if (error.code === "EEXIST") return false;
    throw error;
  } finally {
    await fs.unlink(staged).catch(() => {});
  }
  await syncDir(dir);
  return true;
}

/** Create `rel` under `root` at an explicit mode, refusing a symlinked component it observes. */
export async function ensureDirAt(root, rel, mode = PRIVATE_DIR_MODE) {
  await assertRoot(root);
  const target = path.resolve(root, rel);
  await assertInside(root, target);
  const parts = path.relative(root, target).split(path.sep).filter(Boolean);
  let current = root;
  for (const part of parts) {
    if (part === "..") throw new WriteError(`${rel}: '..' is not a path component here`);
    current = path.join(current, part);
    const kind = await classify(current);
    if (kind === "symlink") throw new WriteError(`${current}: path component is a symlink`);
    if (kind === "absent") {
      await fs.mkdir(current, { mode });
    } else if (kind !== "dir") {
      throw new WriteError(`${current}: path component is a ${kind}`);
    }
  }
  return current;
}

/**
 * Tighten an existing directory through its descriptor.
 *
 * A creation mode cannot fix a directory that already exists at 0755 — and on an installation
 * upgraded from before this module, that is exactly the state the state directory is in.
 */
export async function secureDirAt(root, rel, mode = PRIVATE_DIR_MODE) {
  const target = path.resolve(root, rel);
  if (await classify(target) !== "dir") throw new WriteError(`${target}: not a directory`);
  const handle = await fs.open(target, constants.O_RDONLY);
  try {
    await handle.chmod(mode);
  } finally {
    await handle.close();
  }
}

/**
 * A private temp root, marked on disk so **any** process can recognise it.
 *
 * An in-process registry cannot answer for a root the parent created and a spawned child received,
 * and that is a shape the test suite genuinely uses. Ownership is proven from disk, the same way a
 * job scratch proves it — a registration another process cannot see is no more ownership than a
 * filename is.
 */
export async function makeOwnedTempDir(prefix) {
  const root = await fs.mkdtemp(path.join(await fs.realpath(tmpdir()), `${prefix}-`));
  const marker = JSON.stringify({ [STAMP_KEY]: { kind: TEMP_ROOT_KIND, schema: STAMP_SCHEMA } });
  await writeAtomic(root, path.join(root, MARKER_NAME), `${marker}\n`, { mode: PRIVATE_FILE_MODE });
  ownedTempCache.add(await fs.realpath(root));
  return root;
}

/** The cross-process ownership oracle for temp roots: real dir, 0700, our uid, valid marker. */
export async function isOwnedTempRoot(p) {
  if (typeof process.getuid !== "function") return false;
  let info;
  try {
    info = await fs.lstat(p);
  } catch {
    return false;
  }
  if (!info.isDirectory() || info.isSymbolicLink()) return false;
  if ((info.mode & 0o777) !== PRIVATE_DIR_MODE) return false;
  if (info.uid !== process.getuid()) return false;
  let handle;
  try {
    handle = await fs.open(path.join(p, MARKER_NAME), constants.O_RDONLY | constants.O_NOFOLLOW);
    const stamp = JSON.parse(await handle.readFile("utf8"))?.[STAMP_KEY];
    return stamp?.kind === TEMP_ROOT_KIND && stamp?.schema === STAMP_SCHEMA;
  } catch {
    return false;
  } finally {
    await handle?.close();
  }
}

/** Remove a temp root this suite owns. Symlinks are unlinked as links, never descended through. */
export async function removeOwnedTree(root) {
  if (!(await isOwnedTempRoot(root))) {
    throw new WriteError(`${root}: not an owned temp root — refusing to remove it`);
  }
  const marker = path.join(root, MARKER_NAME);
  await removeInside(root, marker);
  await fs.unlink(marker).catch(() => {});
  await fs.rmdir(root);
  ownedTempCache.delete(path.resolve(root));
}

async function removeInside(dir, keep) {
  for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (full === keep) continue;
    if (entry.isDirectory() && !entry.isSymbolicLink()) {
      await removeInside(full, keep);
      await fs.rmdir(full);
    } else {
      await fs.unlink(full);
    }
  }
}

/**
 * Delete `rel` under `root` only when this suite wrote it.
 *
 * The stamp is read **through the open handle**, so what is deleted is what was inspected as far as
 * a path-based API allows. Anything unparseable, unstamped, non-regular or symlinked survives:
 * failing to collect our own temp is a leak, and deleting someone else's file is a defect, and the
 * two are not the same size.
 */
export async function unlinkOwned(root, rel, kinds) {
  await assertRoot(root);
  const target = path.resolve(root, rel);
  await assertInside(root, target);
  if (await classify(target) !== "file") return false;

  let handle;
  try {
    handle = await fs.open(target, constants.O_RDONLY | constants.O_NOFOLLOW);
    const stamp = JSON.parse(await handle.readFile("utf8"))?.[STAMP_KEY];
    if (stamp?.schema !== STAMP_SCHEMA || !kinds.includes(stamp?.kind)) return false;
  } catch {
    return false;
  } finally {
    await handle?.close();
  }
  await fs.unlink(target);
  return true;
}
