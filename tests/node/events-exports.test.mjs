// SPDX-License-Identifier: ISC
// Every export of scripts/lib/events.mjs is reachable from production, or says why it is retained (vibe-301).
//
// **Why this exists.** Retiring the agy lane (#300, ADR-0002) deleted the two consumers M6 had consolidated a
// quota/auth vocabulary for, and left that vocabulary exported and green under its own tests with nothing calling it.
// A later change published two more exports nothing was meant to consume. Neither was caught, because no check asked
// the question: does anything outside the tests use this? This file asks it for `events.mjs`.
//
// **The contract.** An export passes when EITHER
//   * a production file — any `.mjs`/`.js` under `scripts/`, `bin/` or `hooks/`, other than `events.mjs` itself —
//     imports it by name, with the import path RESOLVED to `events.mjs` rather than string-matched; OR
//   * the line directly above its `export` line is `// export-retained: <reason>`, stating why an export with no
//     production importer is kept (for example, a table production reaches only through a function in this module).
//
// **Fail closed where reachability by name cannot be decided.** A namespace import (`import * as x`) or a re-export
// (`export … from`) of `events.mjs` hides which names are used, so either one fails this suite rather than passing it.
// The module's exports are read two ways — parsed from source and taken from the loaded module — and must agree, so a
// declaration form the parser does not understand cannot slip an export past the check.
//
// **Stated limits.** A dynamic `import()` of `events.mjs` is not detected (none exists). The scope is this one module:
// the question is worth asking of others, but asking it here does not answer it there.

import { strict as assert } from "node:assert";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const TARGET = path.join(REPO_ROOT, "scripts", "lib", "events.mjs");
const PRODUCTION_ROOTS = ["scripts", "bin", "hooks"];
const RETAINED = /^\s*\/\/\s*export-retained:\s*\S/;
const DECLARATION = /^export\s+(?:async\s+function\*?|function\*?|const|let|var|class)\s+([A-Za-z_$][\w$]*)/;

/** Names declared by `export <declaration>` lines, each with whether the line above carries the retained marker. */
function declaredExports(source) {
  const lines = source.split("\n");
  const out = [];
  for (const [index, line] of lines.entries()) {
    const match = DECLARATION.exec(line);
    if (match) out.push({ name: match[1], retained: index > 0 && RETAINED.test(lines[index - 1]) });
  }
  return out;
}

function productionFiles() {
  const walk = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(full);
    return /\.(mjs|js)$/.test(entry.name) ? [full] : [];
  });
  return PRODUCTION_ROOTS.flatMap((root) => walk(path.join(REPO_ROOT, root))).filter((file) => file !== TARGET);
}

const pointsAtTarget = (file, specifier) => specifier.startsWith(".") && path.resolve(path.dirname(file), specifier) === TARGET;

/** What production does with `events.mjs`: the names it imports, and any use that hides which names it uses. */
function productionUse() {
  const imported = new Set();
  const undecidable = [];
  for (const file of productionFiles()) {
    const text = readFileSync(file, "utf8");
    const rel = path.relative(REPO_ROOT, file);
    for (const m of text.matchAll(/import\s+(?:[A-Za-z_$][\w$]*\s*,\s*)?\{([^}]*)\}\s*from\s*["']([^"']+)["']/g)) {
      if (!pointsAtTarget(file, m[2])) continue;
      for (const part of m[1].split(",")) {
        const name = part.trim().split(/\s+as\s+/)[0];
        if (name) imported.add(name);
      }
    }
    for (const m of text.matchAll(/import\s+\*\s+as\s+[A-Za-z_$][\w$]*\s+from\s*["']([^"']+)["']/g)) {
      if (pointsAtTarget(file, m[1])) undecidable.push(`${rel}: namespace import`);
    }
    for (const m of text.matchAll(/export\s+(?:\*|\{[^}]*\})\s*from\s*["']([^"']+)["']/g)) {
      if (pointsAtTarget(file, m[1])) undecidable.push(`${rel}: re-export`);
    }
  }
  return { imported, undecidable };
}

test("every export of events.mjs is imported by a production file or marked export-retained", () => {
  const declared = declaredExports(readFileSync(TARGET, "utf8"));
  const { imported } = productionUse();
  const orphans = declared.filter((e) => !imported.has(e.name) && !e.retained).map((e) => e.name);
  assert.deepEqual(orphans, [],
    `exports with no production importer and no \`// export-retained: <reason>\` line above them: ${orphans.join(", ")}`);
});

test("an export-retained marker is not left on an export that production already imports", () => {
  const declared = declaredExports(readFileSync(TARGET, "utf8"));
  const { imported } = productionUse();
  const stale = declared.filter((e) => e.retained && imported.has(e.name)).map((e) => e.name);
  assert.deepEqual(stale, [], `a retained marker explains nothing on an imported export: ${stale.join(", ")}`);
});

test("production never uses events.mjs in a way that hides which names it uses", () => {
  assert.deepEqual(productionUse().undecidable, [],
    "a namespace import or re-export makes reachability by name undecidable — import names explicitly");
});

test("the exports parsed from source are exactly the module's runtime exports", async () => {
  const parsed = declaredExports(readFileSync(TARGET, "utf8")).map((e) => e.name).sort();
  const runtime = Object.keys(await import(pathToFileURL(TARGET).href)).sort();
  assert.deepEqual(parsed, runtime, "an export form the parser does not recognise would escape the reachability check");
});

test("declaredExports: the marker counts only on the line directly above the export, and only with a reason", () => {
  const source = [
    "// export-retained: production reaches this through classify()",
    "export const KEPT = 1;",
    "// export-retained: a blank line separates this from its export",
    "",
    "export const DETACHED = 2;",
    "// export-retained:",
    "export const NO_REASON = 3;",
    "export function PLAIN() {}",
    "export async function ASYNC() {}",
  ].join("\n");
  assert.deepEqual(declaredExports(source), [
    { name: "KEPT", retained: true },
    { name: "DETACHED", retained: false },
    { name: "NO_REASON", retained: false },
    { name: "PLAIN", retained: false },
    { name: "ASYNC", retained: false },
  ]);
});
