#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Top-level-await detector for shipped .mjs modules (E1.1 / vibe-11, cc-suite W7 class).
//
// `node --check` ACCEPTS top-level await in an .mjs file — verified, not assumed — so it cannot serve
// as the oracle for the acceptance criterion. A token grep is no better: it cannot tell a top-level
// `await` from one inside an async function, which every module here legitimately contains.
//
// So the check uses Node's own parser. The module is reduced to a form `new Function` accepts —
// `import` statements dropped, `export` prefixes stripped, `export default X` rewritten to a binding
// — and then parsed as an ordinary (non-async) function body. A top-level `await` raises "await is
// only valid in async functions"; a nested one parses cleanly.
//
// It fails CLOSED: any unexpected parse error is reported as a failure rather than waved through, so
// a module this transform cannot handle can never be mistaken for a clean one.

import { readFileSync } from "node:fs";

function reduceToFunctionBody(source) {
  return source
    // A shebang is legal in an .mjs entry point but not inside a function body.
    .replace(/^#![^\n]*\n/, "\n")
    // `import.meta` is module-only syntax. Substituting an identifier keeps the surrounding code
    // parseable without touching any `await`, which is the only thing being detected.
    .replace(/\bimport\.meta\b/g, "__import_meta__")
    .replace(/^\s*import\s+[^;]*;?\s*$/gm, "")
    .replace(/^\s*export\s+default\s+/gm, "const __default__ = ")
    .replace(/^\s*export\s+\{[^}]*\}\s*;?\s*$/gm, "")
    .replace(/^\s*export\s+/gm, "");
}

function inspect(file) {
  const body = reduceToFunctionBody(readFileSync(file, "utf8"));
  try {
    new Function(body);
    return { file, verdict: "clean" };
  } catch (error) {
    if (/await is only valid|await is only allowed/.test(error.message)) {
      return { file, verdict: "top-level-await" };
    }
    return { file, verdict: "unparseable", detail: error.message };
  }
}

function main() {
  const files = process.argv.slice(2);
  if (files.length === 0) {
    process.stderr.write("no-top-level-await: no files given\n");
    process.exit(2);
  }
  const bad = files.map(inspect).filter((r) => r.verdict !== "clean");
  for (const result of bad) {
    process.stderr.write(`${result.file}: ${result.verdict}${result.detail ? ` — ${result.detail}` : ""}\n`);
  }
  if (bad.length > 0) process.exit(1);
  process.stdout.write(`ok: no top-level await in ${files.length} shipped module(s)\n`);
}

main();
