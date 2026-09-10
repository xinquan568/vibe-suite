// SPDX-License-Identifier: ISC
// Dispatch contract for /vibe-suite:nl-audit — the executable codex lane, plus the command artifact.
//
// vibe-298: this file also held the end-to-end harness for the retired agy -> codex -> manual
// fallback chain. That lane is gone (ADR-0002) and its subjects were deleted with it, so those cases
// went too. What did NOT go is the codex lane's own subprocess test: its subject is the surviving
// `codex-runner.mjs`, and it is exercised through a controlled PATH with no binary override, so it
// detects broken executable discovery that a filename assertion cannot see.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { spawnSync } from "node:child_process";
import { chmodSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CODEX_RUNNER = path.join(REPO_ROOT, "scripts", "codex-runner.mjs");
const COMMAND = path.join(REPO_ROOT, "commands", "nl-audit.md");
const FAKE_CODEX = path.join(REPO_ROOT, "tests", "fixtures", "fake-codex", "emitter.mjs");

/**
 * `python3` is not an engine and is not part of the fixture: `codex-runner.mjs` reads project
 * configuration through `scripts/lib/config-bridge.mjs`, which shells out to the suite's config
 * reader. With a one-directory PATH the runner cannot find an interpreter and fails before it ever
 * looks for an engine — which would make every case below pass or fail for a reason that has nothing
 * to do with engine discovery. It is a passthrough to the real interpreter and leaves no engine
 * reachable.
 */
const REAL_PYTHON3 = (() => {
  const found = spawnSync("sh", ["-c", "command -v python3"], { encoding: "utf8" });
  const resolved = (found.stdout || "").trim();
  assert.ok(resolved, "python3 must be on PATH to build the shim directory");
  return resolved;
})();

function shimPath(shims) {
  const dir = tmpWorkspace("nl-audit-path-");
  const write = (name, line) => {
    const file = path.join(dir, name);
    writeFileSync(file, `#!/bin/sh\n${line}\n`);
    chmodSync(file, 0o755);
  };
  for (const [name, target] of Object.entries(shims)) {
    write(name, `exec ${JSON.stringify(process.execPath)} ${JSON.stringify(target)} "$@"`);
  }
  write("python3", `exec ${JSON.stringify(REAL_PYTHON3)} "$@"`);
  return dir;
}

/** Run a script with PATH holding only the given shims, and the binary override deleted. */
function runOnPath(script, args, { shims = {} } = {}) {
  const cwd = tmpWorkspace("nl-audit-ws-");
  const env = { ...process.env, PATH: shimPath(shims) };
  delete env.VIBE_SUITE_CODEX_BIN;
  const result = spawnSync(process.execPath, [script, ...args], {
    cwd, encoding: "utf8", timeout: 90_000, env,
  });
  return { ...result, cwd, env };
}

const PROMPT = ["--", "audit this repository"];

// --- the mechanism itself -----------------------------------------------------------------------

test("the harness really does use PATH: no binary override survives into the child", () => {
  const { env } = runOnPath(CODEX_RUNNER, ["--sandbox", "read-only", "--kind", "audit", ...PROMPT],
    { shims: { codex: FAKE_CODEX } });
  assert.equal(env.VIBE_SUITE_CODEX_BIN, undefined);
  assert.equal(env.PATH.split(path.delimiter).length, 1, "PATH must hold exactly the shim dir");
});

test("an absent engine is genuinely absent: no real binary is reachable on the shim PATH", () => {
  // Without this, a case expecting "codex is missing" could silently find the developer's real
  // installation and pass for the wrong reason. PATH is replaced rather than prepended so this holds.
  const dir = shimPath({});
  const found = spawnSync("sh", ["-c", "command -v codex"],
    { encoding: "utf8", env: { ...process.env, PATH: dir } });
  assert.equal((found.stdout || "").trim(), "", "codex must not be reachable");
});

// --- the codex lane, end to end -----------------------------------------------------------------

test("the codex lane answers directly, discovered through PATH with no override", () => {
  const result = runOnPath(CODEX_RUNNER, ["--sandbox", "read-only", "--kind", "audit", ...PROMPT],
    { shims: { codex: FAKE_CODEX } });
  assert.equal(result.status, 0, `${result.stdout}${result.stderr}`);
  const line = result.stdout.trim().split("\n").filter(Boolean).at(-1);
  assert.equal(JSON.parse(line).status, "completed",
    "the audit lane must reach codex through real executable discovery");
});

// --- the command artifact's half of "command-level" ----------------------------------------------

test("the command binds the dispatch paths and the degradation contract", () => {
  const text = readFileSync(COMMAND, "utf8");
  assert.match(text, /scripts\/codex-runner\.mjs/, "the codex lane's dispatch must be named");
  // vibe-298: this used to REQUIRE the retired lane's dispatcher to be named. That is now the
  // inverse of the contract — a command naming a deleted script is a stale self-description.
  assert.doesNotMatch(text, /agy/i, "no retired lane may be named in the dispatch contract");
  assert.match(text, /commands\/shared\/fallback\.md/, "the degradation contract must be bound");
});
