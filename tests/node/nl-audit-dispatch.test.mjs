// SPDX-License-Identifier: ISC
// Command-level dispatch contract for /vibe-suite:nl-audit.
//
// vibe-298: this file used to be the end-to-end harness for the agy -> codex -> manual fallback
// chain — a PATH-shimmed matrix over `agy-audit-cli.mjs`, `agy-fallback.mjs` and the fake-agy
// fixtures. That lane was retired (ADR-0002) and its subjects were deleted with it, so the tests
// that drove them went too: they exercised code that no longer exists, and keeping them would have
// meant keeping the code.
//
// What survives is the property that never belonged to the lane: the command artifact must name the
// dispatch it actually uses, and must bind the degradation contract. That is asserted below, and it
// is asserted POSITIVELY — the previous form required the retired dispatcher to be named, which is
// now the inverse of the contract.

import { strict as assert } from "node:assert";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const COMMAND = path.join(REPO_ROOT, "commands", "nl-audit.md");

test("the command binds the dispatch paths and the degradation contract", () => {
  const text = readFileSync(COMMAND, "utf8");
  assert.match(text, /scripts\/codex-runner\.mjs/, "the codex lane's dispatch must be named");
  assert.doesNotMatch(text, /agy/i, "no retired lane may be named in the dispatch contract");
  assert.match(text, /commands\/shared\/fallback\.md/, "the degradation contract must be bound");
});
