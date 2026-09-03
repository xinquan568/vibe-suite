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
/**
 * vibe-207: the largest record `appendLineAt` will write, in UTF-8 bytes.
 *
 * A POLICY bound, not an atomicity threshold — `PIPE_BUF` governs pipes, and a regular-file
 * `write()` may return short regardless of size. It is sized from the suite's own field caps
 * (`REASON_CAP` 500, `STDERR_TAIL_BYTES` 8192 truncated well below it by callers) against JSON
 * escaping's 6x worst case, so a record that fits its fields fits this.
 */
export const EVENT_LINE_MAX = 4096;

// vibe-182: a long-lived sink (a child's stderr) appends; everything else about its creation is the
// same — exclusive, never through a symlink, private from the first byte.
const OPEN_SINK = OPEN_WRITE | constants.O_APPEND;

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
  // `path.resolve` first: `lstat("/var/")` follows the trailing-slash symlink and reports a
  // directory, so a root passed with a trailing separator escaped this check entirely.
  const kind = await classify(path.resolve(root));
  if (kind === "symlink") throw new WriteError(`${root}: containment root is a symlink`);
  if (kind !== "dir") throw new WriteError(`${root}: containment root is not a directory (${kind})`);
}

/** `target` must resolve inside `root`. The nearest existing ancestor is what gets resolved. */
export async function assertInside(root, target) {
  // Both sides must be resolved before they are compared. Comparing a lexical target against a
  // resolved root fails wherever the temp directory is itself a symlink (`/var` -> `/private/var`
  // on macOS), and `path.resolve` has already normalised any `..` away.
  //
  // **The final component and the intermediate ones are treated differently, and conflating them
  // is an escape with no race in it.** The final component may be a symlink — the caller's own
  // `classify` refuses it, and stopping here is what lets it report "this is a link" instead of
  // "this is outside". An *intermediate* symlink is refused right here: an earlier revision walked
  // past it to the root, so `/root/link/new.json` with `link -> /outside` resolved to `/root`,
  // answered "inside", and then published through the link into `/outside`.
  const resolvedRoot = await fs.realpath(root);

  // **`..` is refused on the ORIGINAL path, before normalisation.** `path.resolve` collapses
  // `link/../new.json` to `new.json` lexically, but the kernel resolves it by following `link`
  // first — so a containment check on the collapsed path and a write through the original one
  // disagree, and the write wins. Refusing the component removes the disagreement instead of
  // trying to model it.
  // The check reads the LITERAL string. `path.relative` and `path.join` both normalise, so running
  // either one first re-collapses the very component being looked for — which is how the first
  // attempt at this guard passed its own test while the escape still worked.
  if (String(target).split(path.sep).includes("..")) {
    throw new WriteError(`${target}: '..' is not a usable path component here`);
  }

  const target_ = path.resolve(target);
  let probe = target_;
  while (true) {
    const kind = await classify(probe);
    if (kind === "symlink" && probe !== target_) {
      throw new WriteError(`${probe}: intermediate path component is a symlink`);
    }
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
    try {
      await handle.writeFile(content, "utf8");
      await handle.chmod(mode);
      await handle.sync();
    } finally {
      await handle.close();
    }
  } catch (error) {
    // Every failing path, including a rejecting `close()` — which an earlier revision let through
    // because the success flag was set before the close ran, leaving an unreachable private file.
    await fs.unlink(staged).catch(() => {});
    throw error;
  }
  return staged;
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

/**
 * Open a private, append-only sink at `dest` for a process's lifetime — the one primitive that hands
 * back an OPEN DESCRIPTOR rather than writing content (vibe-182 / grill H7).
 *
 * `writeAtomic`/`publishNew` write whole files and close them; a child's stderr needs a descriptor
 * that stays open for as long as the child lives, so it is created here — inside `root`, exclusive
 * (`O_EXCL`: a sink is created once, never reopened over an existing file), `O_NOFOLLOW`, `O_APPEND`,
 * at `mode` and then `chmod`ed to it so the umask cannot loosen it. The caller owns the handle:
 * typically it passes `handle.fd` as a `spawn` stdio slot and closes its own copy afterwards — the
 * child holds its own descriptor. Nothing here writes content.
 */
export async function openSinkAt(root, dest, { mode = PRIVATE_FILE_MODE } = {}) {
  await assertRoot(root);
  await assertInside(root, dest);
  const kind = await classify(dest);
  if (kind === "symlink") throw new WriteError(`${dest}: is a symlink — refusing to open a sink over it`);
  if (kind !== "absent") throw new WriteError(`${dest}: already exists — a sink is created once, never reopened`);
  const handle = await fs.open(dest, OPEN_SINK, mode);
  try {
    await handle.chmod(mode);
  } catch (error) {
    await handle.close().catch(() => {});
    await fs.unlink(dest).catch(() => {});
    throw error;
  }
  return handle;
}

/**
 * Append ONE line to a shared, reopenable log inside `root` (vibe-207), observing its size first (vibe-266).
 *
 * `openSinkAt` is `O_EXCL` — "a sink is created once, never reopened" — which is exactly right for
 * one child's stderr and exactly wrong for a log that every process in the workspace must reopen.
 * This is the reopenable counterpart, and it gives up that exclusivity ONLY on the reopen:
 *
 *   * The CREATE stays `O_EXCL`, so a successful create is self-identifying and the `chmod` that
 *     follows it is provably ours. A pre-open `classify()` could not tell us that: between the
 *     classify and the open the path can change, and then "did this call create it?" is a guess.
 *   * The REOPEN validates the **descriptor**, never the path — `fstat` on the handle we are about
 *     to write through, so the object judged and the object mutated are the same object. That is
 *     the property four earlier designs of the surrounding feature failed to hold, each by deciding
 *     about an inode and then mutating a pathname.
 *   * `O_NONBLOCK` is on the reopen because a FIFO at the path would otherwise block an `O_WRONLY`
 *     open forever, and an emitter that hangs has broken the one promise observability owes: never
 *     to affect the operation it observes. On a regular file the flag is a no-op.
 *
 * **Refuse, never repair.** A file that fails any clause is not chmodded, not truncated and not
 * appended to. Tightening the mode of a file we did not create is a mutation we cannot justify, and
 * appending to a group-readable log would publish whatever the caller is recording.
 *
 * One `write()` of one buffer, with `bytesWritten` checked: `O_APPEND` makes the seek-and-write
 * atomic per call, so a record that needs two calls can interleave with another appender's. A short
 * write is therefore NOT retried — a retry would splice this record around someone else's — it
 * raises, and the reader drops the torn line.
 *
 * `line` must not contain a newline: a record is one line by construction, and splitting it here
 * would silently produce two malformed ones.
 *
 * **vibe-266 — the size is observed through the handle before anything is written, on BOTH paths.**
 * With `maxBytes` set, a descriptor that observes the file at or above the threshold writes NOTHING
 * and reports `full` with the inode it observed; only a descriptor that observed the file below the
 * threshold ever writes. Under `O_APPEND` a file's size never decreases, so a writer that observed
 * "below" observed the inode before the write that crossed the threshold — which is what lets a
 * retention sweep reason about who can still write into a rotated generation (the frozen analysis's
 * obligation O2-i). The creator observes too: an exclusive create proves the inode was empty, and the
 * `fstat` makes that observation explicit and returns the inode, so every writer's interval is the
 * same shape — its own `fstat` on the handle it writes through, then its `write`.
 *
 * **vibe-266 — one retry across the `EEXIST`→`ENOENT` gap.** (`onBeforeCreate` and `onBeforeReopen` are
 * test seams at the two windows of that retry.) The create fails `EEXIST` because the
 * live file exists; a rotator renames it away; the reopen finds nothing. That interleaving was
 * unreachable before rotation existed and would have dropped the record silently. One more attempt
 * — a fresh exclusive create — is made; a second `ENOENT` is thrown as before.
 *
 * Returns `{ outcome: "appended" | "full", ino, size }`. Without `maxBytes` the outcome is always
 * `appended`, exactly as before; `ino` and `size` are the values observed through the handle.
 */
export async function appendLineAt(root, rel, line, {
  mode = PRIVATE_FILE_MODE, maxBytes = null, onBeforeCreate = null, onBeforeReopen = null,
} = {}) {
  await assertRoot(root);
  const dest = path.resolve(root, rel);
  await assertInside(root, dest);
  if (typeof line !== "string" || line.includes("\n")) {
    throw new WriteError(`${dest}: a record is one line — an embedded newline is refused`);
  }
  const buf = Buffer.from(`${line}\n`, "utf8");
  if (buf.length > EVENT_LINE_MAX) {
    throw new WriteError(
      `${dest}: record is ${buf.length} bytes, over EVENT_LINE_MAX (${EVENT_LINE_MAX}) — refused whole`);
  }

  let handle = null;
  let info = null;
  for (let attempt = 1; ; attempt += 1) {
    if (onBeforeCreate) await onBeforeCreate(attempt);   // test seam: before each exclusive-create attempt
    try {
      handle = await fs.open(dest, OPEN_SINK, mode);   // O_CREAT|O_EXCL|O_NOFOLLOW|O_WRONLY|O_APPEND
      await handle.chmod(mode);                        // we created it, so the umask cannot loosen it
      info = await handle.stat();                      // vibe-266: the creator's own observation — size 0, and the inode
      break;
    } catch (error) {
      if (error.code !== "EEXIST") {
        await handle?.close().catch(() => {});
        throw error;
      }
    }
    // vibe-266: a documented test seam at the one window rotation opens in this call — the live file
    // exists at the EEXIST and may be renamed away before the reopen.
    if (onBeforeReopen) await onBeforeReopen(attempt);
    try {
      ({ handle, info } = await reopenForAppend(dest, mode));
      break;
    } catch (error) {
      if (error.code === "ENOENT" && attempt < 2) continue;   // renamed away between the EEXIST and the reopen: once more
      throw error;
    }
  }

  try {
    if (maxBytes !== null && info.size >= maxBytes) {
      // Observed at or above the threshold through the handle we would have written through:
      // nothing is written, and the caller learns which inode it judged.
      return { outcome: "full", ino: info.ino, size: info.size };
    }
    const { bytesWritten } = await handle.write(buf);
    if (bytesWritten !== buf.length) {
      throw new WriteError(
        `${dest}: short write (${bytesWritten}/${buf.length}) — the record is torn and is not retried`);
    }
    return { outcome: "appended", ino: info.ino, size: info.size + buf.length };
  } finally {
    await handle.close().catch(() => {});
  }
}

/** The reopen half of `appendLineAt`: open without following, then judge the descriptor. */
async function reopenForAppend(dest, mode) {
  const flags = constants.O_WRONLY | constants.O_APPEND | constants.O_NOFOLLOW | constants.O_NONBLOCK;
  let handle;
  try {
    handle = await fs.open(dest, flags);
  } catch (error) {
    // ELOOP: a symlink at the final component. EISDIR / ENXIO: a directory or an unread FIFO.
    if (error.code === "ELOOP") throw new WriteError(`${dest}: is a symlink — refusing to append through it`);
    if (error.code === "EISDIR") throw new WriteError(`${dest}: is a directory, not a regular file`);
    if (error.code === "ENXIO") throw new WriteError(`${dest}: is a FIFO with no reader — refusing to append`);
    throw error;
  }
  try {
    const info = await handle.stat();
    if (!info.isFile()) throw new WriteError(`${dest}: not a regular file — refusing to append`);
    if (info.nlink !== 1) throw new WriteError(
      `${dest}: has ${info.nlink} links — another name for this inode can read every record`);
    if (typeof process.getuid === "function" && info.uid !== process.getuid()) {
      throw new WriteError(`${dest}: owned by uid ${info.uid} — refusing to append`);
    }
    if ((info.mode & 0o077) !== 0) throw new WriteError(
      `${dest}: mode ${(info.mode & 0o777).toString(8)} is not private (${mode.toString(8)} required) — refused, not repaired`);
    return { handle, info };
  } catch (error) {
    await handle.close().catch(() => {});
    throw error;
  }
}

/** The writer's exact shape, judged from an `lstat` (never followed): a regular file with one name, ours, private. */
function isWriterShape(info) {
  if (!info.isFile()) return false;                                            // a symlink, directory or FIFO fails here
  if (info.nlink !== 1) return false;
  if (typeof process.getuid === "function" && info.uid !== process.getuid()) return false;
  return (info.mode & 0o077) === 0;
}

/**
 * Rotate a live log: move the inode at `rel` to the fresh name `generationRel` (vibe-266).
 *
 * `"rotated"` | `"moved"` | `"absent"` | `"exists"` | `"refused"`. Nothing here destroys content: a
 * `rename` onto an absent name moves the inode, keeps its `mtime`, and leaves every descriptor already
 * open on it writing into the renamed file.
 *
 * **The order of the checks is the safety argument, so it is fixed and commented step by step.**
 *
 *   1. The destination must be ABSENT, checked first (obligation O1). A generation name is a fresh
 *      CSPRNG value that no other actor derives, so this is a guard against a repeated draw, not a
 *      reservation — reserving the name is what let two earlier designs hand the sweep an aged, empty,
 *      qualifiable placeholder to unlink while the rename was in flight. `"exists"` means the caller
 *      drew a value that is in use; the record is refused rather than the file replaced.
 *   2. The test seam sits HERE, before the observation that authorises the rename — never after it.
 *   3. The live file is observed by `lstat` (never followed), judged to be the writer's exact shape,
 *      and its inode compared with `expectedIno` — the inode the caller judged oversized through its
 *      own descriptor. A different inode means a peer rotated and an appender created a replacement:
 *      `"moved"`, and nothing is renamed. Moving a replacement that never crossed the threshold is the
 *      interleaving that defeated the single-term temporal argument in review; it is refused here.
 *   4. `rename` is the NEXT syscall after the comparison. Nothing is awaited between them, so the
 *      rotator's interval — from the observation that authorises the rename to the rename — is one
 *      syscall gap. A replacement created inside that gap is the declared temporal residue (the
 *      frozen analysis's non-guarantee (a)); this primitive does not claim to detect it, and a seam
 *      in that gap would recreate the very non-adjacency step 2 exists to avoid.
 *
 * `expectedIno` is required: a caller without an observed inode has no business rotating.
 */
export async function rotateLogAt(root, rel, { generationRel, expectedIno, onChecked = null } = {}) {
  if (typeof expectedIno !== "number") {
    throw new WriteError(`${rel}: rotateLogAt needs the inode the caller judged (expectedIno)`);
  }
  await assertRoot(root);
  const dest = path.resolve(root, rel);
  const target = path.resolve(root, generationRel);
  await assertInside(root, dest);
  await assertInside(root, target);
  if ((await classify(target)) !== "absent") return "exists";              // 1. O1: never onto a name in use
  if (onChecked) await onChecked();                                          // 2. the seam, BEFORE the observation
  let info;
  try {
    info = await fs.lstat(dest);                                             // 3. the authoritative observation
  } catch (error) {
    if (error.code === "ENOENT") return "absent";
    throw error;
  }
  if (!isWriterShape(info)) return "refused";
  if (info.ino !== expectedIno) return "moved";
  try {
    await fs.rename(dest, target);                                           // 4. the next syscall — no await between
  } catch (error) {
    if (error.code === "ENOENT") return "absent";                            // reachable only inside the gap above; declared, not tested
    throw error;
  }
  return "rotated";
}

/**
 * Judge the generations under `dirRel` (vibe-266) — READ-ONLY, the one recogniser both the sweep
 * and the reader use, so "eligible to retire" and "counts toward the cap" are the same set.
 *
 * `{ eligible, kept, refused }`: `eligible` names whose content age exceeds `olderThanMs`; `kept` the
 * count of generations of ours still inside it; `refused` names that match the shape but are not the
 * writer's (a symlink, a directory, a FIFO, a hard-linked or non-private file — reported, never counted,
 * never touched). Six clauses, in order: the name shape (which the live file fails, so it is never a
 * candidate), a regular file by `lstat` (never followed), one link, our uid, no group/other bits, and
 * the age — `mtime`, which every write refreshes and `rename` preserves, against `now`. The caller
 * supplies `now` so the boundary is testable without sleeping.
 *
 * Every failure to read is an empty judgment, never a throw: a directory that is not there, a listing
 * that fails, a name that vanishes between the listing and its `lstat` (`onListed` is the seam for
 * that window) all yield less, not an error.
 */
export async function judgeGenerationsAt(root, dirRel, { shape, olderThanMs, now = Date.now(), onListed = null } = {}) {
  const empty = { eligible: [], kept: 0, refused: [] };
  await assertRoot(root);
  const dir = path.resolve(root, dirRel);
  await assertInside(root, dir);
  if ((await classify(dir)) !== "dir") return empty;
  let names;
  try {
    names = await fs.readdir(dir);
  } catch {
    return empty;
  }
  if (onListed) await onListed(names);
  const eligible = [];
  const refused = [];
  let kept = 0;
  for (const name of names) {
    if (!shape.test(name)) continue;                                         // clause 1 — the live file exits here
    let info;
    try {
      info = await fs.lstat(path.join(dir, name));
    } catch (error) {
      if (error.code === "ENOENT") continue;                                 // listed, then gone: neither kept nor eligible
      refused.push(name);
      continue;
    }
    if (!isWriterShape(info)) { refused.push(name); continue; }             // clauses 2–5
    if (now - info.mtimeMs <= olderThanMs) { kept += 1; continue; }          // clause 6 — inside the floor
    eligible.push(name);
  }
  return { eligible, kept, refused };
}

/**
 * Retire the generations `judgeGenerationsAt` found eligible (vibe-266): `{ retired, kept, refused }`.
 *
 * The unlink is by name after a judgment by `lstat` — the one path-addressed mutation this module adds
 * after an inode judgment, and it is safe exactly to the extent the frozen analysis states: no
 * in-protocol operation rebinds a generation name (O1, up to a repeated fresh draw), and a write can
 * land in a retired inode only from a descriptor whose interval exceeded the declared bound (O2).
 * `onQualified` is the seam between the judgment and the unlink. A peer that unlinked first is a lost
 * race (`ENOENT`, skipped); anything else that stops an unlink is reported in `refused`, never thrown.
 */
export async function retireGenerationsAt(root, dirRel, { shape, olderThanMs, now = Date.now(), onQualified = null } = {}) {
  const judged = await judgeGenerationsAt(root, dirRel, { shape, olderThanMs, now });
  const dir = path.resolve(root, dirRel);
  const retired = [];
  const refused = [...judged.refused];
  for (const name of judged.eligible) {
    if (onQualified) await onQualified(name);
    try {
      await fs.unlink(path.join(dir, name));
      retired.push(name);
    } catch (error) {
      if (error.code === "ENOENT") continue;                                 // a peer retired it first
      refused.push(name);
    }
  }
  return { retired, kept: judged.kept, refused };
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
  // Containment first: without it, a `..` or absolute `rel` chmods a directory outside the root,
  // which is the same class of hole `assertRoot` exists to close one level up.
  await assertRoot(root);
  const target = path.resolve(root, rel);
  await assertInside(root, target);
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
 * Read a stamped file of ours (vibe-204): parsed JSON, or `null`. Opened `O_NOFOLLOW` and checked
 * to be a regular file THROUGH THE HANDLE, so a symlink at the path — even one whose target is a
 * perfectly valid file of ours — is `null`, as is a directory, an unparseable file, or a file
 * whose stamp is missing, of another schema, or of a kind not in `kinds`. This is the read-side
 * twin of `unlinkOwned`: a name is not authority, and neither is what a name points at.
 */
export async function readOwned(root, rel, kinds) {
  await assertRoot(root);
  const target = path.resolve(root, rel);
  await assertInside(root, target);
  let handle;
  try {
    handle = await fs.open(target, constants.O_RDONLY | constants.O_NOFOLLOW);
    const info = await handle.stat();
    if (!info.isFile()) return null;
    const parsed = JSON.parse(await handle.readFile("utf8"));
    const stamp = parsed?.[STAMP_KEY];
    if (stamp?.schema !== STAMP_SCHEMA || !kinds.includes(stamp?.kind)) return null;
    return parsed;
  } catch {
    return null;
  } finally {
    await handle?.close();
  }
}

/**
 * Publish a staged directory of ours at `dest` in one atomic step (vibe-204: the prune tombstone).
 * The staged directory must be a real directory carrying our stamp file `stampName` (proven by
 * `readOwned`), and `dest` must be absent — a file or a directory there, ours or not, is refused
 * (`false`), never replaced. `rename(2)` of a directory is atomic, so the tombstone becomes visible
 * WITH its provenance already inside; there is no state in which an unprovenanced directory of ours
 * exists at the destination.
 */
export async function publishDirAt(root, stagedRel, destRel, { stampName, kinds, onChecked = null }) {
  await assertRoot(root);
  const staged = path.resolve(root, stagedRel);
  const dest = path.resolve(root, destRel);
  await assertInside(root, staged);
  await assertInside(root, dest);
  if (await classify(staged) !== "dir") return false;
  if (await readOwned(staged, stampName, kinds) === null) return false;
  if (await classify(dest) !== "absent") return false;
  // A documented test seam at the window this call cannot close: the destination was absent when it
  // was checked, and the rename below is what finds out whether it still is.
  if (onChecked) await onChecked();
  try {
    await fs.rename(staged, dest);
  } catch (error) {
    if (["EEXIST", "ENOTEMPTY", "ENOTDIR", "EISDIR"].includes(error.code)) return false;
    throw error;
  }
  return true;
}

/**
 * Remove a directory of ours (vibe-204: an expired tombstone, a stale staging directory):
 * `removed`, `absent`, or `refused`. Provenance is the stamp file inside it, read without
 * following; the directory must hold that file and NOTHING else (nothing here descends), the stamp
 * is unlinked through `unlinkOwned`, and `rmdir` does the rest. A directory without our stamp — or
 * with anything else in it — is not ours to remove and is refused.
 */
/** Does `dir` hold exactly `name` and nothing else? `false` if it cannot be read at all. */
async function holdsOnly(dir, name) {
  try {
    const entries = await fs.readdir(dir);
    return entries.length === 1 && entries[0] === name;
  } catch {
    return false;
  }
}

export async function removeOwnedDirAt(root, rel, {
  stampName, kinds, vacateAs = null, onVacated = null, onValidated = null, onStampJudged = null,
}) {
  await assertRoot(root);
  let target = path.resolve(root, rel);
  await assertInside(root, target);
  const kind = await classify(target);
  if (kind === "absent") return "absent";
  if (kind !== "dir") return "refused";
  if (await readOwned(target, stampName, kinds) === null) return "refused";
  if (!(await holdsOnly(target, stampName))) return "refused";     // decided before anything moves
  // A documented test seam at the one window this call cannot close by construction: the directory
  // has been validated and nothing has been touched yet. Two callers sweeping the same directory
  // both stand here, and what happens next is what the outcomes below have to describe honestly.
  if (onValidated) await onValidated();
  // vibe-204 round 6: `vacateAs` takes the directory OUT of the caller's namespace, in one atomic
  // `rename`, before anything inside it is touched. Removing in place published two intermediate
  // states to concurrent peers — "our stamp is gone but the directory is still here" — and a peer
  // that met one of them could only report a directory it was unable to prove. With the path
  // vacated first, the states a peer can observe at `rel` are the two it can act on: the directory
  // whole, or nothing. The remains carry their provenance to a name the caller sweeps. Only a
  // directory that holds exactly our stamp is ever moved: a directory carrying anything else is
  // refused where it stands.
  if (vacateAs !== null) {
    const staged = path.resolve(root, vacateAs);
    await assertInside(root, staged);
    if (await classify(staged) !== "absent") return "refused";
    try {
      await fs.rename(target, staged);
    } catch (error) {
      if (error.code === "ENOENT") return "absent";              // a peer took it first: a lost race
      return "refused";
    }
    target = staged;
    if (onVacated) await onVacated();
  }
  if (!(await holdsOnly(target, stampName))) {
    return (await classify(target)) === "absent" ? "absent" : "refused";
  }
  // The second seam sits INSIDE the unlink, between the stamp being read through its handle and the
  // `unlink` on the next line — the one window `holdsOnly` above cannot cover, because two callers
  // can both pass that check and both open the stamp before either removes it.
  if (!(await unlinkOwned(target, stampName, kinds,
        { predicate: onStampJudged === null ? null : async () => { await onStampJudged(); return true; } }))) {
    return (await classify(target)) === "absent" ? "absent" : "refused";
  }
  try {
    await fs.rmdir(target);
  } catch (error) {
    return error.code === "ENOENT" ? "absent" : "refused";
  }
  return "removed";
}

/**
 * Remove an EMPTY directory (vibe-204 round 6): `removed`, `absent`, or `refused`.
 *
 * The narrow twin of `removeOwnedDirAt`, for the two states a crash can strand where provenance
 * either does not exist yet or no longer does: a staging directory created before its stamp was
 * published, and the tail of a removal whose stamp is already gone. `rmdir(2)` is the whole
 * operation — it refuses a directory that holds anything at all, so it cannot destroy data, and
 * nothing here descends, reads, or follows. The caller decides which paths are eligible; this
 * primitive proves only "empty".
 */
export async function removeEmptyDirAt(root, rel, { onChecked = null } = {}) {
  await assertRoot(root);
  const target = path.resolve(root, rel);
  await assertInside(root, target);
  const kind = await classify(target);
  if (kind === "absent") return "absent";
  if (kind !== "dir") return "refused";
  // The same window, and the same reason for naming it: `rmdir` below is what learns whether the
  // directory classified a moment ago is still there.
  if (onChecked) await onChecked();
  try {
    await fs.rmdir(target);
  } catch (error) {
    if (error.code === "ENOENT") return "absent";
    return "refused";
  }
  return "removed";
}

/**
 * Delete `rel` under `root` only when this suite wrote it.
 *
 * The stamp is read **through the open handle**, so what is deleted is what was inspected as far as
 * a path-based API allows. Anything unparseable, unstamped, non-regular or symlinked survives:
 * failing to collect our own temp is a leak, and deleting someone else's file is a defect, and the
 * two are not the same size.
 */
export async function unlinkOwned(root, rel, kinds, { predicate = null } = {}) {
  await assertRoot(root);
  const target = path.resolve(root, rel);
  await assertInside(root, target);
  if (await classify(target) !== "file") return false;

  let handle;
  try {
    handle = await fs.open(target, constants.O_RDONLY | constants.O_NOFOLLOW);
    const parsed = JSON.parse(await handle.readFile("utf8"));
    const stamp = parsed?.[STAMP_KEY];
    if (stamp?.schema !== STAMP_SCHEMA || !kinds.includes(stamp?.kind)) return false;
    // vibe-204 round 6: the caller's identity predicate is applied HERE, on the document read
    // through this handle, and the unlink is the next thing that happens. A caller that checked
    // identity in an earlier call and then asked for an unqualified delete was deciding on one
    // observation and mutating a different one — which is how a record published in the gap could
    // be deleted on its stamp kind alone. What a path-based API can promise is that the object
    // deleted is the object judged as far as it was observed; that promise has to live in the
    // deleting call, not beside it.
    if (predicate !== null && !(await predicate(parsed))) return false;
  } catch {
    return false;
  } finally {
    await handle?.close();
  }
  try {
    await fs.unlink(target);
  } catch (error) {
    // A peer that removed the same file between this call's read and its unlink has done what this
    // call was about to do. `false` already means "absent or not ours"; a lost race belongs on that
    // side of the line, not thrown at a caller that is sweeping. Everything else still raises — a
    // permission failure is not a race.
    if (error.code === "ENOENT") return false;
    throw error;
  }
  return true;
}
