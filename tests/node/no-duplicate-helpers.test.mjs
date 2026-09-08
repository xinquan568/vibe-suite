// SPDX-License-Identifier: ISC
// M6 (vibe-218) acceptance: no duplicate UsageError / main-tail / quota table / cap / timeout remains
// under scripts/. A grep-shaped assertion: the ONE home of each helper is named, everything else is a
// duplicate. The two hooks' fail-open tails are asserted present by name — they are a contract, not a copy.
import { strict as assert } from "node:assert";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCRIPTS = path.resolve(HERE, "..", "..", "scripts");

function sources() {
  const out = [];
  for (const dir of [SCRIPTS, path.join(SCRIPTS, "lib")]) {
    for (const name of readdirSync(dir)) {
      if (!name.endsWith(".mjs")) continue;
      const rel = path.relative(SCRIPTS, path.join(dir, name)).split(path.sep).join("/");
      out.push([rel, readFileSync(path.join(dir, name), "utf8")]);
    }
  }
  return out;
}

function homes(pattern, files) {
  return files.filter(([, text]) => pattern.test(text)).map(([rel]) => rel).sort();
}

test("class UsageError is defined once, in lib/cli.mjs", () => {
  assert.deepEqual(homes(/^\s*(export\s+)?class UsageError\b/m, sources()), ["lib/cli.mjs"]);
});

const HOOKS = ["stop-review-gate-hook.mjs", "session-lifecycle-hook.mjs"];

test("the CLI tail main().then((code) …) exists in no CLI — runMain is the one tail; the two hooks keep their fail-open tails", () => {
  const files = sources();
  const clis = files.filter(([rel]) => !HOOKS.includes(rel));
  assert.deepEqual(homes(/^\s*main\(\)\s*\.then\(\s*\(code\)/m, clis), []);
  assert.deepEqual(homes(/^main\(\)\.then\(async/m, files), ["stop-review-gate-hook.mjs"]);
  assert.deepEqual(homes(/^main\(\)\.catch\(/m, files), ["session-lifecycle-hook.mjs"]);
});

test("the quota/auth vocabularies are defined once, in lib/events.mjs, and no consumer keeps a literal predicate", () => {
  const files = sources();
  for (const name of ["QUOTA_CODES", "QUOTA_PHRASES", "QUOTA_TEXT_MARKERS", "AUTH_TEXT_MARKERS", "AUTH_SIGNATURE_MARKERS"]) {
    assert.deepEqual(homes(new RegExp(`^\\s*(export\\s+)?const ${name}\\b`, "m"), files), ["lib/events.mjs"], name);
  }
  const text = Object.fromEntries(files);
  for (const literal of ['includes("quota")', 'includes("resource exhausted")', 'includes("rate limit")', 'includes("authentication required")', 'includes("please sign in")']) {
    assert.ok(!text["agy-runner.mjs"].includes(literal), `agy-runner still carries ${literal}`);
  }
  for (const literal of ['includes("quota")', 'includes("auth")']) {
    assert.ok(!text["lib/agy-fallback.mjs"].includes(literal), `agy-fallback still carries ${literal}`);
  }
  assert.match(text["agy-runner.mjs"], /from "\.\/lib\/events\.mjs"/);
  assert.match(text["lib/agy-fallback.mjs"], /from "\.\/events\.mjs"/);
  assert.ok(!/\bconst QUOTA_/.test(text["codex-runner.mjs"]), "codex-runner still defines a QUOTA_ table");
});

test("the 96,000-byte cap and DEFAULT_TIMEOUT_MS are defined once, in lib/process.mjs", () => {
  assert.deepEqual(homes(/\b96_000\b|\b96000\b/, sources()), ["lib/process.mjs"]);
  assert.deepEqual(homes(/^\s*(export\s+)?const DEFAULT_TIMEOUT_MS\s*=/m, sources()), ["lib/process.mjs"]);
});
