// SPDX-License-Identifier: ISC
// Probes for the top-level-await checker (E1.1 / vibe-11).
//
// The checker is sound in one direction: no false negatives, false positives allowed and visible.
// So `clean` is the assertion that matters — every DIRTY case must NOT be clean, and every CLEAN
// case must be clean (a false positive there would be a usability bug, not an unsoundness).
//
// Both round-1 false negatives are pinned here permanently.

import { tmpWorkspace } from "./_tmp.mjs";
import { strict as assert } from "node:assert";
import { writeFileSync } from "node:fs";

import path from "node:path";
import test from "node:test";

import { inspect } from "./no-top-level-await.mjs";

const DIR = tmpWorkspace("tla-probe-");
const probe = (name, source) => {
  const file = path.join(DIR, `${name}.mjs`);
  writeFileSync(file, source, "utf8");
  return inspect(file).verdict;
};

// --- must NOT be reported clean (unsoundness would live here) ---------------

const DIRTY = {
  plain: 'const x = await work();\n',
  exported: 'export const x = await work();\n',
  exportDefault: 'export default await work();\n',
  // Round-1 false negative #1: a semicolonless import let the old regex swallow the next statement.
  semicolonlessImport: 'import { x } from "./x.mjs"\nawait x();\n',
  // Round-1 false negative #2: `await` before a newline parsed as an identifier under new Function.
  newlineAwait: 'const y = await\n  Promise.resolve(1);\n',
  templateSubstitution: 'const s = `${await work()}`;\nexport default s;\n',
  nestedTemplate: 'const s = `a${`b${await work()}`}c`;\n',
  insideBlock: 'if (globalThis.x) { await work(); }\n',
  insideObjectLiteral: 'const o = { k: await work() };\n',
  // A call followed by an ASI-separated block is NOT a method body; the old rule would have been
  // fooled. Ambiguity resolves toward reporting.
  callThenBlock: 'foo()\n{ await work(); }\n',
  conciseArrowThenAwait: 'const f = x => x\nawait work();\n',
  // A contextual keyword across a statement boundary is not a method header: `async` alone is an
  // expression statement, then a call, then a block. The Step-8 review found this false negative.
  contextualKeywordAcrossStatementBoundary:
    'const async = 0, foo = () => {};\nasync\nfoo()\n{ await work(); }\n',
  // A bare CR is a LineTerminator too; treating it as ordinary whitespace preserved false adjacency.
  contextualKeywordAcrossCarriageReturn:
    'const async = 0, foo = () => {};\rasync/*\r*/foo()\r{ await work(); }\r',
  // A multi-line block comment between a contextual keyword and the name is still a statement break.
  contextualKeywordAcrossBlockComment:
    'const async = 0, foo = () => {};\nasync/*\n*/foo()\n{ await work(); }\n',
};

for (const [name, source] of Object.entries(DIRTY)) {
  test(`reports or refuses: ${name}`, () => {
    const verdict = probe(name, source);
    assert.notEqual(verdict, "clean",
      `${name} contains top-level await but the checker said clean — a false negative`);
  });
}

// --- must be clean (ordinary shapes; OTHER frames are accepted) -------------

const CLEAN = {
  namedImports: 'import { a, b } from "node:fs";\nexport default a;\n',
  objectLiteral: 'const o = { a: 1, b: { c: 2 } };\nexport default o;\n',
  destructuring: 'const { a = 1, b: { c } = {} } = globalThis.z;\nexport default c;\n',
  objectSpread: 'const o = { ...globalThis.z, k: 1 };\nexport default o;\n',
  nestedAsync: 'import fs from "node:fs";\nexport async function go() { await fs.promises.readFile("x"); }\n',
  objectMethod: 'const o = { async m() { await work(); } };\nexport default o;\n',
  classMethod: 'class C { async m() { await work(); } }\nexport default C;\n',
  cleanConciseArrow: 'const f = (x) => x * 2;\nexport default f;\n',
  division: 'const r = (1 + 2) / 3;\nexport default r;\n',
  regexLiteral: 'const r = /ab[/]c/g;\nexport default r.source;\n',
  awaitInStringAndComment: '// await work()\nconst s = "await work()";\nexport default s;\n',
  templateNoAwait: 'const s = `a${1 + 2}b`;\nexport default s;\n',
  mainInvocation: 'async function main() { await work(); }\nmain();\n',
  // `function` cannot stand alone as an expression statement, so a newline before the name is
  // unambiguous — unlike the contextual keywords above.
  asyncFunctionNewlineName: 'async function\nfoo() { await work(); }\nfoo();\n',
  crlfLineEndings: 'import { a } from "node:fs";\r\nasync function go() { await a(); }\r\ngo();\r\n',
};

for (const [name, source] of Object.entries(CLEAN)) {
  test(`clean: ${name}`, () => {
    assert.equal(probe(name, source), "clean", `${name} should be clean`);
  });
}

test("a concise arrow containing await is refused, not silently accepted", () => {
  assert.equal(probe("conciseAwait", 'const f = () => await work();\n'), "refused");
});

test("refusal is never clean — an unterminated construct fails closed", () => {
  assert.equal(probe("unterminated", 'const s = "oops\n'), "refused");
});
