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

test("the quota tables are defined once, in lib/events.mjs, and no consumer keeps a literal predicate", () => {
  const files = sources();
  for (const name of ["QUOTA_CODES", "QUOTA_PHRASES"]) {
    assert.deepEqual(homes(new RegExp(`^\\s*(export\\s+)?const ${name}\\b`, "m"), files), ["lib/events.mjs"], name);
  }
  const text = Object.fromEntries(files);
  // vibe-298: the two consumers this used to police — agy-runner and agy-fallback — were deleted
  // with their lane (ADR-0002). The M6 property is unchanged and still worth checking: the tables
  // have ONE home, and no surviving consumer re-implements the predicate as a literal.
  // vibe-301: the three plain-text marker tables (QUOTA_TEXT_MARKERS, AUTH_TEXT_MARKERS,
  // AUTH_SIGNATURE_MARKERS) were deleted with mentionsAny and mentionsQuota once nothing consumed them,
  // so the two tables classifyFailure reads are all that remains to police. The lane, markers included,
  // is preserved at tag retired/agy-lane.
  assert.ok(!/\bconst QUOTA_/.test(text["codex-runner.mjs"]), "codex-runner still defines a QUOTA_ table");
});

test("the last-stdout-line JSON parser is defined once, in lib/cli.mjs, and the Stop hook calls it", () => {
  // Step 9 R2: the hook imported parseLastJsonLine and kept its own copy of the parser beside it.
  const files = sources();
  assert.deepEqual(homes(/\.trim\(\)\.split\("\\n"\)\.filter\(Boolean\)\.at\(-1\)/, files), ["lib/cli.mjs"]);
  const hook = Object.fromEntries(files)["stop-review-gate-hook.mjs"];
  assert.match(hook, /^import \{ parseLastJsonLine \} from "\.\/lib\/cli\.mjs";$/m);
  assert.match(hook, /const result = parseLastJsonLine\(dispatched\.stdout\);/);
});

test("the 96,000-byte cap and DEFAULT_TIMEOUT_MS are defined once, in lib/process.mjs", () => {
  assert.deepEqual(homes(/\b96_000\b|\b96000\b/, sources()), ["lib/process.mjs"]);
  assert.deepEqual(homes(/^\s*(export\s+)?const DEFAULT_TIMEOUT_MS\s*=/m, sources()), ["lib/process.mjs"]);
});

test("the ANSI CSI strip has one home for the transport/sanitiser pair — lib/reason-frame.mjs — and the transport imports it (vibe-310)", () => {
  // Scoped to the PAIR by the owner's decision (2026-09-16): the transport (lib/jobs.mjs) strips before
  // bounding with the same step the gate's sanitiser runs first, so one definition serves both and
  // "what counts as ANSI" is a single answer for them. lib/render.mjs (stripControls) and
  // lib/preflight.mjs (boundToken) carry their own copies of the CSI step inside different chains;
  // they are pre-existing and are #321's business, so they are deliberately NOT read here.
  const text = Object.fromEntries(sources());
  const pair = { "lib/reason-frame.mjs": text["lib/reason-frame.mjs"], "lib/jobs.mjs": text["lib/jobs.mjs"] };
  const CSI_SOURCE = /\\x1b\\\[\[0-9;\?\]\*\[ -\/\]\*\[@-~\]/g;
  const occurrences = Object.fromEntries(Object.entries(pair).map(([rel, src]) => [rel, (src.match(CSI_SOURCE) ?? []).length]));
  // OCCURRENCES, not files: an inline copy kept beside the shared constant is one file and two homes.
  assert.deepEqual(occurrences, { "lib/reason-frame.mjs": 1, "lib/jobs.mjs": 0 }, "the pattern source appears once across the pair");
  assert.equal((pair["lib/reason-frame.mjs"].match(/^\s*export function stripAnsi\b/mg) ?? []).length, 1, "stripAnsi is exported once");
  // The sanitiser DELEGATES its first step: stripAnsi(reason) comes before any .replace( in its body.
  const sanitiser = /export function sanitiseReason\([^)]*\)\s*\{([\s\S]*?)^\}/m.exec(pair["lib/reason-frame.mjs"]);
  assert.ok(sanitiser, "sanitiseReason is present");
  const body = sanitiser[1];
  assert.ok(body.indexOf("stripAnsi(reason)") !== -1 && body.indexOf("stripAnsi(reason)") < body.indexOf(".replace("),
    "sanitiseReason's chain starts with stripAnsi(reason)");
  assert.match(pair["lib/jobs.mjs"], /^import \{[^}]*\bstripAnsi\b[^}]*\} from "\.\/reason-frame\.mjs";$/m,
    "the transport imports the one strip rather than keeping a copy");
  assert.match(pair["lib/jobs.mjs"], /stripAnsi\(line\.slice\(cut\)\)/, "and calls it on the reason, before bounding");
});
