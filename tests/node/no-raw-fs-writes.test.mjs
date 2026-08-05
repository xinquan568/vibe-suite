// SPDX-License-Identifier: ISC
// Probes for the Node write-discipline checker (vibe-153, requirement 7 of #103).
//
// The checker is sound in one direction — nothing ambiguous resolves toward `clean` — so the
// assertions split three ways:
//
//   * DIRTY_MUTATORS: a resolved mutator call must verdict EXACTLY `raw-fs-write`. Asserting
//     merely "not clean" would let a checker that lost a mutator into the generic refusal
//     bucket pass while its mutator table silently shrank.
//   * REFUSALS: one cell per unsupported-construct class the issue enumerates, plus the
//     survivors that broke the two designs #103 rejected (Worker eval, data: re-export,
//     indirect Function, process.binding, getBuiltinModule, createRequire…). Each must
//     verdict `refused`.
//   * CLEAN: the accepted dialect must actually admit ordinary modules, or the checker is
//     unusable however sound it is.

import { strict as assert } from "node:assert";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { inspect, MUTATORS, HANDLE_MUTATORS, KNOWN, PRIMITIVE } from "./no-raw-fs-writes.mjs";
import { writeFileSync } from "node:fs";

const DIR = mkdtempSync(path.join(tmpdir(), "rawfs-probe-"));
const probe = (name, source) => {
  const file = path.join(DIR, `${name}.mjs`);
  writeFileSync(file, source, "utf8");
  return inspect(file).verdict;
};

// --- resolved mutators: exactly `raw-fs-write` -------------------------------

test("every promise-API mutator is a raw write", () => {
  for (const name of MUTATORS) {
    if (name.endsWith("Sync")) continue;
    // open is a mutator only by flag; its own cells cover both directions.
    const src = name === "open"
      ? 'import { open } from "node:fs/promises";\nconst h = await open("p", "w");\n'
      : `import { ${name} } from "node:fs/promises";\nawait ${name}("p");\n`;
    assert.equal(probe(`promise_${name}`, src), "raw-fs-write", name);
  }
});

test("every sync mutator is a raw write", () => {
  for (const name of MUTATORS) {
    if (!name.endsWith("Sync")) continue;
    const src = name === "openSync"
      ? 'import { openSync } from "node:fs";\nconst h = openSync("p", "w");\n'
      : `import { ${name} } from "node:fs";\n${name}("p");\n`;
    assert.equal(probe(`sync_${name}`, src), "raw-fs-write", name);
  }
});

test("namespace member mutators are raw writes", () => {
  for (const name of MUTATORS) {
    if (name === "open" || name === "openSync") continue;   // flag-dependent; own cells
    const src = `import * as fs from "node:fs";\nfs.${name}("p");\n`;
    assert.equal(probe(`ns_${name}`, src), "raw-fs-write", name);
  }
});

test("default-import member mutators are raw writes", () => {
  const src = 'import fs from "node:fs";\nfs.writeFileSync("p", "x");\n';
  assert.equal(probe("default_member", src), "raw-fs-write");
});

test("every FileHandle mutator is a raw write", () => {
  for (const name of HANDLE_MUTATORS) {
    const src = 'import { open } from "node:fs/promises";\n'
      + 'const h = await open("p", "r");\n'
      + `await h.${name}("x");\n`;
    assert.equal(probe(`handle_${name}`, src), "raw-fs-write", name);
  }
});

test("open with a write-capable flag is a raw write", () => {
  for (const flag of ['"w"', '"a"', '"r+"', '"w+"', '"ax"']) {
    const src = `import { open } from "node:fs/promises";\nconst h = await open("p", ${flag});\n`;
    assert.equal(probe(`openflag_${flag.replace(/\W/g, "")}`, src), "raw-fs-write", flag);
  }
});

// --- refusal classes: exactly `refused` --------------------------------------

const REFUSALS = {
  dynamicImport: 'const fs = await import("node:fs");\nfs.writeFileSync("p", "x");\n',
  createRequire: 'import { createRequire } from "node:module";\n'
    + 'const r = createRequire(import.meta.url);\nr("fs").writeFileSync("p", "x");\n',
  processBinding: 'process.binding("fs");\n',
  getBuiltinModule: 'const fs = process.getBuiltinModule("fs");\nfs.writeFileSync("p", "x");\n',
  evalCall: 'eval(String.raw`x`);\n',
  functionCtor: 'const f = new Function("return process")();\n',
  indirectFunction: 'const F = (() => {}).constructor;\nF("return 1")();\n',
  workerEval: 'import { Worker } from "node:worker_threads";\n'
    + 'new Worker(SRC, { eval: true });\n',
  dataModule: 'export { writeFileSync } from "data:text/javascript,export const writeFileSync=0";\n',
  bareSpecifier: 'import x from "some-package";\n',
  nonLiteralSpecifier: 'const s = "node:fs";\nawait import(s);\n',
  reExportFs: 'export { writeFile } from "node:fs/promises";\n',
  reExportStar: 'export * from "node:fs";\n',
  aliasBinding: 'import fs from "node:fs";\nconst w = fs.writeFileSync;\nw("p", "x");\n',
  computedAccess: 'import fs from "node:fs";\nfs["write" + "FileSync"]("p", "x");\n',
  classField: 'import fs from "node:fs";\nclass C { w = fs.writeFileSync; }\n',
  globalThisReach: 'globalThis.process.binding("fs");\n',
  argumentPassing: 'import { writeFile } from "node:fs/promises";\nrun(writeFile);\n',
  returnCapability: 'import fs from "node:fs";\nexport function get() { return fs; }\n',
  exportCapability: 'import fs from "node:fs";\nexport { fs };\n',
  destructureNamespace: 'import * as fs from "node:fs";\nconst { writeFileSync } = fs;\n',
  unknownMember: 'import fs from "node:fs";\nfs.someFutureApi("p");\n',
  unresolvableOpenFlag: 'import { open } from "node:fs/promises";\n'
    + 'const f = flagFromConfig();\nconst h = await open("p", f);\n',
  openThenChain: 'import { open } from "node:fs/promises";\n'
    + 'await open("p", "r").then((h) => h.chmod(0o600));\n',
  openReturned: 'import { open } from "node:fs/promises";\n'
    + 'export function get() { return open("p", "r"); }\n',
  openPassed: 'import { open } from "node:fs/promises";\nuse(open("p", "r"));\n',
  openCallbackForm: 'import { open } from "node:fs";\nopen("p", "r", (e, fd) => {});\n',
  handleAliased: 'import { open } from "node:fs/promises";\n'
    + 'const h = await open("p", "r");\nconst g = h;\n',
  handleUnknownMember: 'import { open } from "node:fs/promises";\n'
    + 'const h = await open("p", "r");\nawait h.futureThing();\n',
  bareCapabilityMention: 'import fs from "node:fs";\nconsole.log(fs);\n',
};

test("every unsupported construct refuses", () => {
  for (const [name, src] of Object.entries(REFUSALS)) {
    assert.equal(probe(`refuse_${name}`, src), "refused", name);
  }
});

// --- the accepted dialect must admit ordinary modules ------------------------

const CLEAN = {
  noFs: 'import path from "node:path";\nexport const j = (a, b) => path.join(a, b);\n',
  readersNamed: 'import { readFile, readdir } from "node:fs/promises";\n'
    + 'export async function load(p) {\n  const files = await readdir(p);\n'
    + '  return readFile(files[0], "utf8");\n}\n',
  readersNamespace: 'import * as fs from "node:fs";\n'
    + 'export const there = (p) => fs.existsSync(p);\n',
  readOnlyHandle: 'import { open } from "node:fs/promises";\n'
    + 'export async function head(p) {\n  const h = await open(p, "r");\n'
    + '  const out = await h.read();\n  await h.close();\n  return out;\n}\n',
  relativeImport: 'import { publish } from "../lib/write.mjs";\n'
    + 'export const go = (p, d) => publish(p, d);\n',
  templatesAndRegex: 'const re = /a\\/b/g;\nexport const t = (x) => `v:${x.replace(re, "-")}`;\n',
};

test("the accepted dialect admits ordinary modules", () => {
  for (const [name, src] of Object.entries(CLEAN)) {
    assert.equal(probe(`clean_${name}`, src), "clean", name);
  }
});

// --- constants ---------------------------------------------------------------

test("KNOWN is empty and stays empty", () => {
  assert.equal(KNOWN.size, 0,
    "an entry in KNOWN is a new claim that some site cannot route through the primitive");
});

test("the primitive is the audited write module", () => {
  assert.equal(PRIMITIVE, "scripts/lib/write.mjs");
});

test("the mutator floor covers the issue's named set", () => {
  for (const name of ["writeFile", "appendFile", "mkdir", "mkdtemp", "rename", "link",
                      "symlink", "unlink", "rm", "rmdir", "chmod", "chown", "copyFile",
                      "cp", "truncate", "ftruncate", "utimes", "write", "writev",
                      "createWriteStream", "open"]) {
    assert.ok(MUTATORS.has(name), `mutator floor lacks ${name}`);
    assert.ok(MUTATORS.has(`${name}Sync`) || name === "createWriteStream",
      `mutator floor lacks ${name}Sync`);
  }
});
