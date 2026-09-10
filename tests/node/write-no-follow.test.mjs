// SPDX-License-Identifier: ISC
// `readNoFollow` under concurrent root disappearance and replacement (vibe-261, Step-9 findings
// 4, 6, 7 and 8).
//
// These live in their OWN file because they patch `fs.lstat` for the whole process: `node --test`
// gives each file its own process, so the mock cannot leak into the store's other suites. The
// orderings are races -- a directory observed, then gone or swapped -- which a fixture on a real
// filesystem cannot stage deterministically. `scripts/lib/write.mjs` imports `promises as fs` from
// `node:fs`, an ordinary patchable object, so no seam inside the module is needed to reach them.
//
// The mock is PATH-SPECIFIC, and that is load-bearing (finding 8). An earlier version failed every
// `lstat` after the first, including surviving ancestors -- so `assertInside`'s walk ran out of
// ancestors and threw "no existing ancestor" instead of the "resolves outside" this is meant to
// pin. It passed while testing the wrong branch, and a mutant translating only the other message
// would have passed with it. Here only the root and paths beneath it vanish; every ancestor above
// keeps answering truthfully, so the walk stops at the surviving parent and produces the real
// containment failure. The preconditions are asserted rather than assumed, so an extra `lstat`
// added upstream cannot silently shift the mock onto a different call and quietly stop testing.

import { strict as assert } from "node:assert";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { readNoFollow } from "../../scripts/lib/write.mjs";

function jobsRoot() {
  const root = path.join(mkdtempSync(path.join(os.tmpdir(), "no-follow-")), "jobs");
  mkdirSync(root);
  writeFileSync(path.join(root, "job.v1.json"), "{}\n", "utf8");
  return root;
}

const isAtOrUnder = (p, root) => p === root || p.startsWith(root + path.sep);

/**
 * Let the root be observed truthfully `graceCalls` times, then make it -- and only it and its
 * contents -- report `code`. Ancestors above the root keep answering for real.
 */
async function withRootFailing(root, { graceCalls, code }, body) {
  const realLstat = fs.lstat;
  const seen = { root: 0, other: 0 };
  fs.lstat = async (p, ...rest) => {
    const target = String(p);
    if (!isAtOrUnder(target, root)) { seen.other += 1; return realLstat(target, ...rest); }
    seen.root += 1;
    if (seen.root <= graceCalls) return realLstat(target, ...rest);
    const err = new Error(`${code}: injected for ${target}`);
    err.code = code;
    throw err;
  };
  try {
    return await body(seen);
  } finally {
    fs.lstat = realLstat;
  }
}

test("vibe-261: a root vanishing mid-walk reports absence, via the surviving-parent path", async () => {
  // The exact ordering finding 6 named: `classify(root)` sees a directory and `realpath(root)`
  // succeeds, THEN the root goes. `assertInside` climbs past it to the surviving parent, whose
  // relative path points outside -- historically "resolves outside", a WriteError with no `code`,
  // which callers' benign absence branches never saw.
  const root = jobsRoot();
  await withRootFailing(root, { graceCalls: 1, code: "ENOENT" }, async (seen) => {
    await assert.rejects(() => readNoFollow(root, "job.v1.json"), (error) => {
      assert.equal(error.code, "ENOENT", `a vanished root is absence, got: ${error.message}`);
      return true;
    });
    // Anti-drift: the first observation must have been the real directory, and the walk must have
    // consulted an ancestor ABOVE the root. If either stops holding, this test is no longer
    // exercising the surviving-parent path and must fail rather than pass quietly.
    assert.ok(seen.root > 1, "the root was observed again after its initial classification");
    assert.ok(seen.other > 0, "the walk reached a surviving ancestor above the root");
  });
});

test("vibe-261: a root absent from the outset reports absence", async () => {
  const root = jobsRoot();
  await withRootFailing(root, { graceCalls: 0, code: "ENOENT" }, async () => {
    await assert.rejects(() => readNoFollow(root, "job.v1.json"), (error) => {
      assert.equal(error.code, "ENOENT");
      return true;
    });
  });
});

test("vibe-261: a root REPLACED by a symlink is refused, never reported as absence", async () => {
  // Finding 7. `realpath` on a dangling link throws ENOENT, so rethrowing the original error
  // unexamined would report a symlinked root as absence -- laundering a refusal into a benign
  // branch. The re-observation must decide all three ways, not merely "absent or not".
  const root = jobsRoot();
  const realLstat = fs.lstat;
  let calls = 0;
  fs.lstat = async (p, ...rest) => {
    const target = String(p);
    if (!isAtOrUnder(target, root)) return realLstat(target, ...rest);
    calls += 1;
    if (calls === 1) return realLstat(target, ...rest);          // still the real directory
    if (target === root) return { isSymbolicLink: () => true, isDirectory: () => false, isFile: () => false };
    const gone = new Error(`ENOENT: injected for ${target}`);
    gone.code = "ENOENT";
    throw gone;
  };
  try {
    await assert.rejects(() => readNoFollow(root, "job.v1.json"), (error) => {
      assert.notEqual(error.code, "ENOENT", "a symlinked root is a refusal, not absence");
      assert.match(error.message, /not a directory \(symlink\)/);
      return true;
    });
  } finally {
    fs.lstat = realLstat;
  }
});

test("vibe-261: a genuine escape is still refused, and is NOT reported as absence", async () => {
  // Nothing is mocked: the root is a real directory throughout, so the refusal must survive with
  // no `code` attached. This is what proves the translation never launders a real failure.
  const root = jobsRoot();
  const outside = path.join(path.dirname(root), "elsewhere.json");
  writeFileSync(outside, "{}\n", "utf8");
  await assert.rejects(() => readNoFollow(root, outside), (error) => {
    assert.equal(error.code, undefined, "an escape is not absence");
    assert.match(error.message, /resolves outside/);
    return true;
  });
});
