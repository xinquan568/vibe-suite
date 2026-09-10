// SPDX-License-Identifier: ISC
// `readNoFollow` under concurrent root disappearance (vibe-261, Step-9 findings 4 and 6).
//
// These live in their OWN file because they patch `fs.lstat` for the whole process: `node --test`
// gives each file its own process, so the mock cannot leak into the store's other suites. The
// orderings below are races -- a directory observed, then gone -- and a race is exactly what a
// fixture on a real filesystem cannot stage deterministically. `scripts/lib/write.mjs` imports
// `promises as fs` from `node:fs`, an ordinary patchable object, so no seam inside the module is
// needed to reach them.
//
// What is being pinned: every ordering of a vanished containment root reports ABSENCE (`ENOENT`),
// because every caller's benign "the slot is simply not there" branch keys on `code`. A root that
// is still present when the walk fails is a genuine escape and stays refused.

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

/** Run `body` with `fs.lstat` real for the first `realCalls` calls, then reporting ENOENT. */
async function withRootVanishingAfter(realCalls, body) {
  const realLstat = fs.lstat;
  let seen = 0;
  fs.lstat = async (p, ...rest) => {
    seen += 1;
    if (seen <= realCalls) return realLstat(p, ...rest);
    const gone = new Error(`ENOENT: no such file or directory, lstat '${p}'`);
    gone.code = "ENOENT";
    throw gone;
  };
  try {
    return await body();
  } finally {
    fs.lstat = realLstat;
  }
}

test("vibe-261: a root that vanishes after its classification reports absence", async () => {
  // The ordering finding 6 names: `classify` sees a directory, `realpath(root)` still succeeds, and
  // the containment walk then climbs past the vanished directory to a surviving ancestor -- which
  // used to surface as "resolves outside", a WriteError carrying NO code, so callers' benign
  // absence branches never saw it and a disappearance was reported as an entry needing repair.
  const root = jobsRoot();
  await withRootVanishingAfter(1, async () => {
    await assert.rejects(() => readNoFollow(root, "job.v1.json"), (error) => {
      assert.equal(error.code, "ENOENT", `a vanished root is absence, got: ${error.message}`);
      return true;
    });
  });
});

test("vibe-261: a root absent from the outset reports absence too", async () => {
  const root = jobsRoot();
  await withRootVanishingAfter(0, async () => {
    await assert.rejects(() => readNoFollow(root, "job.v1.json"), (error) => {
      assert.equal(error.code, "ENOENT");
      return true;
    });
  });
});

test("vibe-261: a genuine escape is still refused, and is NOT reported as absence", async () => {
  // The other side of the same catch: it must translate a DISAPPEARANCE, never launder a real
  // containment failure. Nothing is mocked here -- the root is present throughout, so the refusal
  // must survive with no `code` attached.
  const root = jobsRoot();
  const outside = path.join(path.dirname(root), "elsewhere.json");
  writeFileSync(outside, "{}\n", "utf8");
  await assert.rejects(() => readNoFollow(root, outside), (error) => {
    assert.equal(error.code, undefined, "an escape is not absence");
    assert.match(error.message, /resolves outside/);
    return true;
  });
});
