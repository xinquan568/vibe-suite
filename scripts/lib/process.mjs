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

/**
 * Run `command args…` under a deadline.
 *
 * Resolves `{ exitCode, signal, stdout, stderr, timedOut, killedHard }`. Never rejects for a
 * non-zero exit — that is data, not an exception.
 *
 * `timeoutMs` must be a finite positive number. A deadline-bounded runner that silently accepts
 * "no deadline" is the defect this throw exists to prevent: the guard is enforced where the value is
 * relied upon, not only where it is set.
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
}) {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return Promise.reject(new RangeError(
      `runWithDeadline: timeoutMs must be a finite positive number, got ${timeoutMs}`));
  }

  return new Promise((resolve, reject) => {
    let child;
    try {
      child = spawn(command, args, { cwd, env, stdio: ["ignore", "pipe", "pipe"] });
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

    let killTimer = null;
    const deadline = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
      killTimer = setTimeout(() => {
        killedHard = true;
        child.kill("SIGKILL");
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

    child.on("close", (code, signal) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve({
        exitCode: code,
        signal,
        stdout: Buffer.concat(stdout).toString("utf8"),
        stderr: Buffer.concat(stderr).toString("utf8"),
        timedOut,
        killedHard,
      });
    });
  });
}
