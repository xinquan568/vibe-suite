// SPDX-License-Identifier: ISC
// Deadline-bounded subprocess control for the job engine (E1.1 / vibe-11).
//
// This module runs a child and reports what happened to it. It deliberately does **not** decide
// whether the run succeeded — that judgement belongs to `events.mjs`, which reads the event stream,
// because `codex exec`'s exit code is not a reliable success signal. Keeping the two apart is what
// stops "the process ended" from silently becoming "the work succeeded".
//
// stdin is `"ignore"`, which Node binds to /dev/null. That is load-bearing: with an inherited stdin,
// codex prints "Reading additional input from stdin..." and blocks forever in a non-interactive
// session.
//
// Termination escalates and is **group-wide**. SIGTERM asks; a child that traps it would otherwise
// outlive its deadline, so SIGKILL follows and cannot be refused. Both go to the process *group*
// where one exists, because killing only the direct child would orphan whatever it spawned.

import { spawn } from "node:child_process";

export const DEFAULT_GRACE_MS = 2000;
export const DEFAULT_HEARTBEAT_MS = 30_000;
export const DEFAULT_TIMEOUT_MS = 600_000;      // 10 minutes; documented in the runner's --help

/** The heartbeat interval, overridable so tests need not spend 30 s observing one beat. */
export function heartbeatInterval(env = process.env) {
  const raw = Number(env.VIBE_SUITE_HEARTBEAT_MS);
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_HEARTBEAT_MS;
}

/**
 * Signal a process group, falling back to the process itself.
 *
 * A negative pid targets the group. The worker is spawned `detached`, so it leads a group containing
 * the Codex process it spawned; signalling only the worker would leave that grandchild orphaned.
 */
export function signalGroup(pid, signal) {
  try {
    process.kill(-pid, signal);
    return true;
  } catch (error) {
    if (error.code === "ESRCH") return false;
    try {
      process.kill(pid, signal);                 // not a group leader — signal it directly
      return true;
    } catch {
      return false;
    }
  }
}

/** How long the detached mode polls for the process group to disappear after SIGKILL. */
export const GROUP_REAP_DEADLINE_MS = 5000;
const GROUP_REAP_POLL_MS = 50;

/**
 * Run `command args…` under a deadline.
 *
 * Resolves `{ exitCode, signal, stdout, stderr, timedOut, killedHard, groupReaped }`. Never
 * rejects for a non-zero exit — that is data, not an exception.
 *
 * `timeoutMs` must be a finite positive number. A deadline-bounded runner that silently accepts
 * "no deadline" is the defect this throw exists to prevent: the guard is enforced where the value is
 * relied upon, not only where it is set.
 *
 * **`detached: true` (E1.3 / vibe-13) makes the deadline group-wide.** The default mode signals
 * only the direct child, so a child that spawns descendants into its group can leave them running
 * past the deadline — fine for callers that manage their own workers (the runner detaches its
 * workers itself), wrong for a probe calling an arbitrary external CLI. Detached mode spawns the
 * child as a group leader, escalates through `signalGroup`, and resolves only after polling the
 * group gone; `groupReaped` reports the confirmation (`null` in default mode — a non-detached
 * child leads no group, and claiming one was reaped would be a lie).
 */
export function runWithDeadline({
  command,
  args = [],
  cwd = process.cwd(),
  env = process.env,
  timeoutMs,
  graceMs = DEFAULT_GRACE_MS,
  onHeartbeat = null,
  heartbeatMs = DEFAULT_HEARTBEAT_MS,
  onSpawned = null,
  detached = false,
}) {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return Promise.reject(new RangeError(
      `runWithDeadline: timeoutMs must be a finite positive number, got ${timeoutMs}`));
  }

  return new Promise((resolve, reject) => {
    let child;
    try {
      child = spawn(command, args, { cwd, env, stdio: ["ignore", "pipe", "pipe"], detached });
    } catch (error) {
      reject(error);
      return;
    }

    if (onSpawned) onSpawned(child);

    const stdout = [];
    const stderr = [];
    let timedOut = false;
    let killedHard = false;
    let settled = false;

    child.stdout.on("data", (chunk) => { stdout.push(chunk); });
    child.stderr.on("data", (chunk) => { stderr.push(chunk); });

    const beat = onHeartbeat ? setInterval(() => { onHeartbeat(); }, heartbeatMs) : null;

    // In detached mode the child leads its own group, so signalling `-pid` is safe and reaches
    // descendants; in default mode `signalGroup` must NOT be used — the child shares the caller's
    // group, and `-pid` would target the caller itself on the ESRCH fallback path.
    const terminate = (signal) => {
      if (detached) signalGroup(child.pid, signal);
      else child.kill(signal);
    };

    let killTimer = null;
    const deadline = setTimeout(() => {
      timedOut = true;
      terminate("SIGTERM");
      killTimer = setTimeout(() => {
        killedHard = true;
        terminate("SIGKILL");
      }, graceMs);
    }, timeoutMs);

    const cleanup = () => {
      clearTimeout(deadline);
      if (killTimer) clearTimeout(killTimer);
      if (beat) clearInterval(beat);
    };

    child.on("error", (error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    });

    // Detached only: confirm the whole group is gone, escalating once more if the direct child's
    // exit left descendants behind. A timer expiring proves nothing (the E1.1 rule) — only the
    // group actually disappearing counts. Escalating here IS a hard kill and is reported as one.
    const confirmGroupReaped = () => new Promise((done) => {
      if (!signalGroup(child.pid, 0)) { done(true); return; }
      signalGroup(child.pid, "SIGTERM");
      signalGroup(child.pid, "SIGKILL");
      killedHard = true;
      const reapDeadline = Date.now() + GROUP_REAP_DEADLINE_MS;
      const poll = setInterval(() => {
        if (!signalGroup(child.pid, 0)) { clearInterval(poll); done(true); }
        else if (Date.now() > reapDeadline) { clearInterval(poll); done(false); }
      }, GROUP_REAP_POLL_MS);
    });

    child.on("close", (code, signal) => {
      if (settled) return;
      settled = true;
      cleanup();
      const finish = (groupReaped) => resolve({
        exitCode: code,
        signal,
        stdout: Buffer.concat(stdout).toString("utf8"),
        stderr: Buffer.concat(stderr).toString("utf8"),
        timedOut,
        killedHard,
        groupReaped,
      });
      if (!detached) { finish(null); return; }
      confirmGroupReaped().then(finish);
    });
  });
}
