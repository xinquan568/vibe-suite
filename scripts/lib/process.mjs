// SPDX-License-Identifier: ISC
// Deadline-bounded subprocess control for the job engine (E1.1 / vibe-11).
//
// This module runs a child and reports what happened to it. It deliberately does **not** decide
// whether the run succeeded — that judgement belongs to `events.mjs`, which reads the event stream,
// because the exit code is not a reliable success signal for `codex exec`. Keeping the two apart is
// what stops "the process ended" from silently becoming "the work succeeded".
//
// stdin is `"ignore"`, which Node binds to /dev/null. That is load-bearing, not tidiness: with an
// inherited stdin, codex prints "Reading additional input from stdin..." and blocks forever in a
// non-interactive session.
//
// Termination escalates. SIGTERM asks; a child that traps or ignores it would otherwise outlive its
// deadline, so SIGKILL follows after a grace period and cannot be refused.

import { spawn } from "node:child_process";

export const DEFAULT_GRACE_MS = 2000;
export const DEFAULT_HEARTBEAT_MS = 30_000;

/** The heartbeat interval, overridable so tests need not spend 30 s observing one beat. */
export function heartbeatInterval(env = process.env) {
  const raw = Number(env.VIBE_SUITE_HEARTBEAT_MS);
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_HEARTBEAT_MS;
}

/**
 * Run `command args…` under a deadline.
 *
 * Resolves `{ exitCode, signal, stdout, stderr, timedOut, killedHard }`. Never rejects for a
 * non-zero exit — that is data, not an exception.
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
}) {
  return new Promise((resolve, reject) => {
    let child;
    try {
      child = spawn(command, args, { cwd, env, stdio: ["ignore", "pipe", "pipe"] });
    } catch (error) {
      reject(error);
      return;
    }

    const stdout = [];
    const stderr = [];
    let timedOut = false;
    let killedHard = false;
    let settled = false;

    child.stdout.on("data", (chunk) => stdout.push(chunk));
    child.stderr.on("data", (chunk) => stderr.push(chunk));

    const beat = onHeartbeat ? setInterval(() => onHeartbeat(), heartbeatMs) : null;

    let killTimer = null;
    const deadline = Number.isFinite(timeoutMs) && timeoutMs > 0
      ? setTimeout(() => {
          timedOut = true;
          child.kill("SIGTERM");
          // The child may ignore SIGTERM. SIGKILL cannot be ignored, so the deadline holds.
          killTimer = setTimeout(() => {
            killedHard = true;
            child.kill("SIGKILL");
          }, graceMs);
        }, timeoutMs)
      : null;

    const cleanup = () => {
      if (deadline) clearTimeout(deadline);
      if (killTimer) clearTimeout(killTimer);
      if (beat) clearInterval(beat);
    };

    const finish = (result) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(result);
    };

    child.on("error", (error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    });

    child.on("close", (code, signal) => {
      finish({
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
