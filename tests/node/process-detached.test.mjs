// SPDX-License-Identifier: ISC
// runWithDeadline's opt-in detached-group mode (E1.3 / vibe-13).
//
// The default mode signals only the direct child (`child.kill`), so a child that spawns
// descendants into its group can leave them running past the deadline. Preflight probes call an
// external CLI that does exactly that, so they need a mode where the child is spawned detached
// (leading its own group), escalation goes through `signalGroup`, and the promise does not resolve
// until the WHOLE group is confirmed gone. The hanger fixture ignores SIGTERM at every level and
// spawns a same-group descendant — precisely the tree the default mode cannot reap.

import { strict as assert } from "node:assert";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { runWithDeadline } from "../../scripts/lib/process.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const HANGER = path.join(REPO_ROOT, "tests", "fixtures", "hanger.mjs");

test("detached mode reaps a SIGTERM-immune descendant tree by deadline", async () => {
  let pid = null;
  const result = await runWithDeadline({
    command: process.execPath,
    args: [HANGER],
    timeoutMs: 800,
    graceMs: 200,
    detached: true,
    onSpawned: (child) => { pid = child.pid; },
  });
  assert.equal(result.timedOut, true);
  assert.equal(result.killedHard, true, "SIGTERM immunity must force the SIGKILL escalation");
  assert.equal(result.groupReaped, true, "the resolve contract is: group confirmed gone");
  assert.ok(pid, "onSpawned must still fire in detached mode");
  // The definitive check: the entire process group — parent AND descendant — is dead.
  assert.throws(() => process.kill(-pid, 0), { code: "ESRCH" },
    "the process group must not survive the deadline");
});

test("default mode is unchanged: no groupReaped claim is made for non-detached children", async () => {
  const result = await runWithDeadline({
    command: process.execPath,
    args: ["-e", "process.exit(0)"],
    timeoutMs: 5000,
  });
  assert.equal(result.exitCode, 0);
  assert.equal(result.timedOut, false);
  assert.equal(result.groupReaped, null,
    "a non-detached child leads no group; claiming a group was reaped would be a lie");
});

test("a detached child that exits cleanly reports its group reaped without any signal", async () => {
  const result = await runWithDeadline({
    command: process.execPath,
    args: ["-e", "process.exit(0)"],
    timeoutMs: 5000,
    detached: true,
  });
  assert.equal(result.exitCode, 0);
  assert.equal(result.timedOut, false);
  assert.equal(result.killedHard, false);
  assert.equal(result.groupReaped, true);
});
