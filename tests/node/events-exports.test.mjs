// SPDX-License-Identifier: ISC
// Every export of scripts/lib/events.mjs is reachable from production, or says why it is retained (vibe-301).
//
// **Why this exists.** Retiring the agy lane (#300, ADR-0002) deleted the two consumers M6 had consolidated a
// quota/auth vocabulary for, and left that vocabulary exported and green under its own tests with nothing calling it.
// A later change published two more exports nothing was meant to consume. Neither was caught, because no check asked
// the question: does anything outside the tests use this? This file asks it for `events.mjs`.
//
// **The contract.** An export passes when EITHER
//   * a production module — any `.mjs` under `scripts/`, `bin/` or `hooks/`, other than `events.mjs` itself — imports
//     it by name, with the specifier RESOLVED to `events.mjs` rather than string-matched; OR
//   * the line directly above its `export` line is `// export-retained: <reason>`, stating why an export with no
//     production importer is kept (for example, a table production reaches only through a function in this module).
//
// **Threat model — a declared boundary.** This guards against honest drift: an export left behind when its consumer
// goes, in a codebase that imports with ordinary syntax. It does not try to out-parse source contrived to read one way
// to V8 and another way to a lexer. It meets that boundary by REFUSING, never by guessing: where reading a spelling
// correctly would take a full parser, the file is refused and the suite fails, so the spelling gets rewritten plainly.
// Refused: a `/` whose meaning depends on statement context (after a line break, an `if`/`while`/`for`/`with` head's
// `)`, `}`, `.`, `of`, `++` or `--`);
// any non-ASCII character outside a string, template, regex or comment; an escape outside those literals; anything
// unterminated. A valid module that reads differently to `lex()` than to V8 WITHOUT tripping a refusal is outside
// the boundary — the contract is ordinary syntax, and the refusals are how unusual syntax announces itself.
//
// **Fail closed where reachability by name cannot be decided.** Each of these fails the suite: a default or namespace
// import of `events.mjs`; a re-export of it in any spelling (`export *`, `export * as ns`, `export { … } from`); a
// dynamic `import()` of it by string literal; an escaped imported name in an import of it; an escaped specifier, or a
// specifier spelled as a URL (`file:`, `%`, `?`, `#`), wherever it points; an import declaration the parser cannot
// read; a production script that is not `.mjs`. The module's exports are also read two ways — parsed from source and taken from the loaded module — and must
// agree, so an unfamiliar declaration form cannot slip an export past the check.
//
// **Stated limits.** `import(expr)` with a computed argument names no target statically. The scope is this one
// module: the question is worth asking of others, but asking it here does not answer it there.

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
// JavaScript that is not an ES module file. Scripts admit grammar a module lexer does not model (HTML-like comments).
const NON_MODULE_SCRIPT = /\.(?:js|cjs|jsx|ts|mts|cts|tsx)$/;

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

function productionTree() {
  const walk = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? walk(full) : [full];
  });
  return PRODUCTION_ROOTS.flatMap((root) => walk(path.join(REPO_ROOT, root)));
}

const productionModules = () => productionTree().filter((file) => file.endsWith(".mjs") && file !== TARGET);

/** Production files that are JavaScript but not `.mjs`: by extension, or extensionless with a `node` `#!` line. */
function productionNonModuleScripts() {
  return productionTree().filter((file) => {
    if (NON_MODULE_SCRIPT.test(file)) return true;
    if (path.extname(file) !== "") return false;
    return /^#![^\n]*\bnode\b/.test(readFileSync(file, "utf8").slice(0, 200));
  }).map((file) => path.relative(REPO_ROOT, file));
}

// ---- the lexer ---------------------------------------------------------------------------------------------------

class LexRefusal extends Error {}

const LINE_TERMINATOR = /[\n\r\u2028\u2029]/;
const SPACE = /[\t\v\f ]/;
const WORD = /[A-Za-z0-9_$]/;
// Words after which an expression begins, so a `/` opens a regex. After any other word, `/` divides.
const EXPRESSION_KEYWORDS = new Set([
  "return", "typeof", "instanceof", "in", "new", "delete", "void", "throw", "case", "do", "else", "yield", "await",
]);

const ambiguousSlash = (after) => new LexRefusal(`cannot decide whether \`/\` after ${after} is a regex or a division`);

/** Whether the `)` ending `tokens` closes the head of `if`, `while`, `for` (including `for await`) or `with`. An
 * unmatched `)` counts as a statement head: that is the answer that refuses. */
function closesStatementHead(tokens) {
  let depth = 0;
  for (let k = tokens.length - 1; k >= 0; k -= 1) {
    const t = tokens[k];
    if (t.type !== "punct") continue;
    if (t.value === ")") depth += 1;
    else if (t.value === "(" && --depth === 0) {
      let head = tokens[k - 1];
      if (head?.type === "word" && head.value === "await" && tokens[k - 2]?.type === "word" && tokens[k - 2].value === "for") {
        head = tokens[k - 2];
      }
      return head?.type === "word" && ["if", "while", "for", "with"].includes(head.value);
    }
  }
  return true;
}

/** Whether a `/` (not `//` or `/*`) opens a regex, given the tokens before it. Throws where that needs a parser. */
function slashOpensRegex(tokens, afterLineBreak) {
  const last = tokens[tokens.length - 1];
  if (last === undefined) return true;
  if (afterLineBreak) throw ambiguousSlash("a line break");         // ASI: `let x\n/re/` versus `a\n/ b`
  if (last.type === "word") {
    const before = tokens[tokens.length - 2];
    const spread = tokens[tokens.length - 3]?.type === "punct" && tokens[tokens.length - 3].value === ".";
    if (before?.type === "punct" && before.value === "." && !spread) return false;   // `o.return / 2` — a property name
    if (last.value === "of") throw ambiguousSlash("`of`");           // `for (x of /re/)` versus a variable named `of`
    return EXPRESSION_KEYWORDS.has(last.value);
  }
  if (last.type !== "punct") return false;                           // after a string, template or regex, `/` divides
  if (last.value === ")") {
    // `)` ends an expression — `Date.now() / 1000`, `(a + b) / 2` — unless it closes a statement head, after which a
    // statement (and so a regex) may begin: `if (x) /re/.test(s)`. Only that case needs a parser, so only it refuses.
    if (closesStatementHead(tokens)) throw ambiguousSlash("`)` closing an `if`, `while`, `for` or `with` head");
    return false;
  }
  if (["}", "."].includes(last.value)) throw ambiguousSlash(`\`${last.value}\``);   // a block or an object; `1. / 2`
  if (last.value === "]") return false;
  const before = tokens[tokens.length - 2];
  if ((last.value === "+" || last.value === "-") && before?.type === "punct" && before.value === last.value) {
    throw ambiguousSlash(`\`${last.value.repeat(2)}\``);             // `a++ / b` versus `a + +/re/`
  }
  return true;
}

/**
 * Tokens of `source`: ASCII words, punctuation, and strings with their value and whether they held an escape.
 * Comments are dropped; template text is dropped but every `${ … }` is lexed as code. Anything the lexer cannot
 * decide throws a LexRefusal.
 */
function lex(source) {
  const tokens = [];
  const braces = [];                                                 // "block" | "substitution", innermost last
  let lineBreak = false;                                             // a LineTerminator since the last token
  const emit = (token) => { tokens.push(token); lineBreak = false; };
  let i = source.startsWith("#!") ? source.search(LINE_TERMINATOR) : 0;
  if (i === -1) return tokens;

  // Scan template text from `i` up to its closing backtick, or up to a `${` that hands back to the main loop.
  const templateText = () => {
    while (i < source.length) {
      const c = source[i];
      if (c === "\\") { i += 2; continue; }
      if (c === "`") { i += 1; emit({ type: "template", value: "" }); return; }
      if (c === "$" && source[i + 1] === "{") {
        i += 2;
        braces.push("substitution");
        emit({ type: "punct", value: "${" });
        return;
      }
      i += 1;
    }
    throw new LexRefusal("unterminated template literal");
  };

  while (i < source.length) {
    const c = source[i];
    if (LINE_TERMINATOR.test(c)) { lineBreak = true; i += 1; continue; }
    if (SPACE.test(c)) { i += 1; continue; }

    if (c === "/" && source[i + 1] === "/") {
      while (i < source.length && !LINE_TERMINATOR.test(source[i])) i += 1;
      continue;
    }
    if (c === "/" && source[i + 1] === "*") {
      const end = source.indexOf("*/", i + 2);
      if (end === -1) throw new LexRefusal("unterminated block comment");
      if (LINE_TERMINATOR.test(source.slice(i, end))) lineBreak = true;
      i = end + 2;
      continue;
    }

    if (c === '"' || c === "'") {
      let j = i + 1;
      let value = "";
      let escaped = false;
      while (j < source.length && source[j] !== c) {
        if (source[j] === "\\") { escaped = true; j += 2; continue; }
        if (source[j] === "\n" || source[j] === "\r") throw new LexRefusal("unterminated string");
        value += source[j];
        j += 1;
      }
      if (j >= source.length) throw new LexRefusal("unterminated string");
      emit({ type: "string", value, escaped });
      i = j + 1;
      continue;
    }

    if (c === "`") { i += 1; templateText(); continue; }
    if (c === "{") { braces.push("block"); emit({ type: "punct", value: "{" }); i += 1; continue; }
    if (c === "}") {
      i += 1;
      if (braces.pop() === "substitution") { templateText(); continue; }
      emit({ type: "punct", value: "}" });
      continue;
    }

    if (c === "/") {
      if (!slashOpensRegex(tokens, lineBreak)) { emit({ type: "punct", value: "/" }); i += 1; continue; }
      let j = i + 1;
      let inClass = false;
      for (;;) {
        if (j >= source.length || LINE_TERMINATOR.test(source[j])) throw new LexRefusal("unterminated regex literal");
        const ch = source[j];
        if (ch === "\\") {
          if (j + 1 >= source.length || LINE_TERMINATOR.test(source[j + 1])) throw new LexRefusal("unterminated regex literal");
          j += 2;
          continue;
        }
        if (ch === "[") inClass = true;
        else if (ch === "]") inClass = false;
        else if (ch === "/" && !inClass) break;
        j += 1;
      }
      j += 1;
      while (j < source.length && WORD.test(source[j])) j += 1;
      emit({ type: "regex", value: "" });
      i = j;
      continue;
    }

    if (c === "\\") throw new LexRefusal("an escape outside a string, template or regex");
    if (c.charCodeAt(0) > 0x7e) throw new LexRefusal("a non-ASCII character outside a string, template, regex or comment");

    if (WORD.test(c)) {
      let j = i;
      while (j < source.length && WORD.test(source[j])) j += 1;
      emit({ type: "word", value: source.slice(i, j) });
      i = j;
      continue;
    }

    emit({ type: "punct", value: c });
    i += 1;
  }
  if (braces.includes("substitution")) throw new LexRefusal("unterminated template substitution");
  return tokens;
}

// ---- what a file does with events.mjs ----------------------------------------------------------------------------

const is = (token, type, value) => token !== undefined && token.type === type && (value === undefined || token.value === value);

/**
 * What one source file does with `events.mjs`: the names it imports, and every use that hides which names it uses.
 * `file` is the path the source is read as; specifiers resolve against its URL.
 */
function usesOf(file, source) {
  const names = [];
  const undecidable = [];
  let tokens;
  try {
    tokens = lex(source);
  } catch (err) {
    if (!(err instanceof LexRefusal)) throw err;
    return { names, undecidable: [`the lexer refused the file: ${err.message}`] };
  }
  // Whether a specifier token names `events.mjs`. A specifier that is escaped or spelled as a URL is judged by
  // neither its text nor a guess at its decoding: it is undecidable wherever it points.
  const judge = (token, what) => {
    if (token.escaped) { undecidable.push(`${what} with an escaped specifier`); return false; }
    const spec = token.value;
    if (!(spec.startsWith(".") || spec.startsWith("/") || /^[A-Za-z][A-Za-z0-9+.-]*:/.test(spec))) return false;  // bare
    if (spec.startsWith("node:")) return false;
    if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(spec) || /[%?#]/.test(spec)) {
      undecidable.push(`${what} with a specifier spelled as a URL`);
      return false;
    }
    return fileURLToPath(new URL(spec, pathToFileURL(file))) === TARGET;
  };

  for (let i = 0; i < tokens.length; i += 1) {
    const token = tokens[i];
    if (is(tokens[i - 1], "punct", ".")) continue;                  // `x.import`, `x.export` are property names

    if (is(token, "word", "import")) {
      const next = tokens[i + 1];
      if (is(next, "punct", ".") || is(next, "punct", ":")) continue;   // `import.meta`; `{ import: … }`
      if (is(next, "punct", "(")) {                                  // dynamic import()
        if (is(tokens[i + 2], "string") && judge(tokens[i + 2], "dynamic import")) undecidable.push("dynamic import");
        continue;
      }
      if (is(next, "string")) { judge(next, "side-effect import"); i += 1; continue; }   // `import "…"` uses no names

      // import <clause> from "<specifier>" — the clause is words, strings, `*`, `,` and at most one `{ … }`, and its
      // `from` is the first one outside the braces that a string follows.
      let j = i + 1;
      let depth = 0;
      while (j < tokens.length && !(depth === 0 && is(tokens[j], "word", "from") && is(tokens[j + 1], "string"))) {
        const t = tokens[j];
        if (is(t, "punct", "{")) depth += 1;
        else if (is(t, "punct", "}")) depth -= 1;
        else if (!(is(t, "word") || is(t, "string") || is(t, "punct", "*") || is(t, "punct", ","))) break;
        j += 1;
      }
      if (!is(tokens[j], "word", "from")) { undecidable.push("an import declaration the parser could not read"); continue; }
      const clause = tokens.slice(i + 1, j);
      i = j + 1;
      if (!judge(tokens[j + 1], "import")) continue;
      if (is(clause[0], "word")) undecidable.push("default import");       // `import d …`; `* as ns` starts with `*`
      if (clause.some((t) => is(t, "punct", "*"))) undecidable.push("namespace import");
      const open = clause.findIndex((t) => is(t, "punct", "{"));
      if (open !== -1) {
        const inner = clause.slice(open + 1, clause.findIndex((t) => is(t, "punct", "}")));
        let expectName = true;
        for (const t of inner) {
          if (is(t, "punct", ",")) { expectName = true; continue; }
          if (!expectName) continue;
          expectName = false;
          if (t.escaped) undecidable.push("an escaped imported name");   // `"v…"`: its text is not its name
          else if (t.value === "default") undecidable.push("default import");
          else names.push(t.value);
        }
      }
      continue;
    }

    if (is(token, "word", "export")) {
      let j = i + 1;
      if (is(tokens[j], "punct", "*")) {
        j += 1;
        if (is(tokens[j], "word", "as")) j += 2;                     // `export * as ns` — `ns` a word or a string
      } else if (is(tokens[j], "punct", "{")) {
        while (j < tokens.length && !is(tokens[j], "punct", "}")) j += 1;
        j += 1;
      } else {
        continue;                                                    // `export const …` and friends: declarations
      }
      i = j - 1;                                                     // the clause's words are names, never keywords
      if (is(tokens[j], "word", "from") && is(tokens[j + 1], "string")) {
        i = j + 1;
        if (judge(tokens[j + 1], "re-export")) undecidable.push("re-export");
      }
    }
  }
  return { names, undecidable };
}

/** What production does with `events.mjs`, across every production module. */
function productionUse() {
  const imported = new Set();
  const undecidable = [];
  for (const file of productionModules()) {
    const { names, undecidable: hidden } = usesOf(file, readFileSync(file, "utf8"));
    for (const name of names) imported.add(name);
    for (const what of hidden) undecidable.push(`${path.relative(REPO_ROOT, file)}: ${what}`);
  }
  return { imported, undecidable };
}

test("every export of events.mjs is imported by a production module or marked export-retained", () => {
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
    "reachability by name is undecidable here — import names explicitly, in plain syntax, from a plain relative specifier");
});

test("production JavaScript under scripts/, bin/ and hooks/ is .mjs, the grammar this check reads", () => {
  assert.deepEqual(productionNonModuleScripts(), [],
    "a script admits grammar the module lexer does not model — write it as .mjs");
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

// Every row is read as a module in scripts/, so "./lib/events.mjs" is the target and "./lib/jobs.mjs" is not. Rows come
// in three groups: the ESM forms that reach another module's names, enumerated from the grammar; the lookalikes a
// scanner can mistake for use; and the spellings the lexer must refuse rather than guess — beside controls showing the
// same text is read correctly when written plainly.
const EVENTS = '"./lib/events.mjs"';
const REFUSED = (why) => [`the lexer refused the file: ${why}`];
const AMBIGUOUS_SLASH = (after) => REFUSED(`cannot decide whether \`/\` after ${after} is a regex or a division`);
const HEAD = "`)` closing an `if`, `while`, `for` or `with` head";
const URL_SPELLED = (what) => [`${what} with a specifier spelled as a URL`];
const GRAMMAR = [
  // -- the grammar
  ["named, single-line", `import { VERDICT_RE, verdictLineOf as v } from ${EVENTS};`, ["VERDICT_RE", "verdictLineOf"], []],
  ["named, multi-line", `import {\n  VERDICT_RE,\n  classifyFailure,\n} from ${EVENTS};`, ["VERDICT_RE", "classifyFailure"], []],
  ["named, a string as the imported name", `import { "VERDICT_RE" as V } from ${EVENTS};`, ["VERDICT_RE"], []],
  ["named, aliased to `from`", `import { classifyFailure as from } from ${EVENTS};`, ["classifyFailure"], []],
  ["named, from another module", 'import { VERDICT_RE } from "./lib/jobs.mjs";', [], []],
  ["named, with import attributes", `import { VERDICT_RE } from ${EVENTS} with { type: "javascript" };`, ["VERDICT_RE"], []],
  ["default", `import events from ${EVENTS};`, [], ["default import"]],
  ["default, named `from`", `import from from ${EVENTS};`, [], ["default import"]],
  ["default, spelled inside the braces", `import { default as events } from ${EVENTS};`, [], ["default import"]],
  ["default and named", `import events, { VERDICT_RE } from ${EVENTS};`, ["VERDICT_RE"], ["default import"]],
  ["namespace", `import * as events from ${EVENTS};`, [], ["namespace import"]],
  ["default and namespace", `import events, * as all from ${EVENTS};`, [], ["default import", "namespace import"]],
  ["side-effect", `import ${EVENTS};`, [], []],
  ["export * from", `export * from ${EVENTS};`, [], ["re-export"]],
  ["export * as ns from", `export * as events from ${EVENTS};`, [], ["re-export"]],
  ["export * as \"ns\" from", `export * as "events" from ${EVENTS};`, [], ["re-export"]],
  ["export { … } from", `export { VERDICT_RE } from ${EVENTS};`, [], ["re-export"]],
  ["export { … } from, multi-line", `export {\n  VERDICT_RE,\n} from ${EVENTS};`, [], ["re-export"]],
  ["export { default } from", `export { default } from ${EVENTS};`, [], ["re-export"]],
  ["export { x as from } from", `export { classifyFailure as from } from ${EVENTS};`, [], ["re-export"]],
  ["export { x as import } from", `export { classifyFailure as import } from ${EVENTS};`, [], ["re-export"]],
  ["a local export list is not a re-export", "const VERDICT_RE = 1;\nexport { VERDICT_RE };", [], []],
  ["dynamic import of a literal", `const m = await import(${EVENTS});`, [], ["dynamic import"]],
  ["dynamic import of another module", 'const m = await import("./lib/jobs.mjs");', [], []],
  ["import.meta is not an import", "const here = import.meta.url;", [], []],
  ["an object key named import is not an import", "const o = { import: 1 };", [], []],
  ["a `node:` specifier is never the target", 'import { readFileSync } from "node:fs";', [], []],
  ["a #! line before the import", `#!/usr/bin/env node\nimport { VERDICT_RE } from ${EVENTS};`, ["VERDICT_RE"], []],
  ["escaped specifier: static import", 'import { VERDICT_RE } from "./lib/events\\x2emjs";', [], ["import with an escaped specifier"]],
  ["escaped specifier: re-export", 'export * from "./lib/events\\x2emjs";', [], ["re-export with an escaped specifier"]],
  ["escaped specifier: dynamic import", 'const m = await import("./lib/events\\x2emjs");', [], ["dynamic import with an escaped specifier"]],
  ["escaped imported name: an ordinary name", `import { "\\u0076erdictLineOf" as v } from ${EVENTS};`, [], ["an escaped imported name"]],
  ["escaped imported name: default", `import { "\\x64efault" as d } from ${EVENTS};`, [], ["an escaped imported name"]],
  ["escaped imported name: a name that is not an export", `import { "VERDICT_RE\\n" as v } from ${EVENTS};`, [], ["an escaped imported name"]],
  ["URL specifier: percent-encoded", 'export * as ns from "./lib/%65vents.mjs";', [], URL_SPELLED("re-export")],
  ["URL specifier: a query", 'export * as ns from "./lib/events.mjs?probe";', [], URL_SPELLED("re-export")],
  ["URL specifier: a fragment", 'const x = import("./lib/events.mjs#probe");', [], URL_SPELLED("dynamic import")],
  ["URL specifier: file:", `import { VERDICT_RE } from "${pathToFileURL(TARGET).href}";`, [], URL_SPELLED("import")],
  ["control: a plain relative specifier resolves", 'export * as ns from "../scripts/lib/events.mjs";', [], ["re-export"]],
  // -- lookalikes
  ["lookalike: a line comment", `// import { VERDICT_RE } from ${EVENTS};`, [], []],
  ["lookalike: a block comment", `/* import { VERDICT_RE } from ${EVENTS}; */`, [], []],
  ["lookalike: a string", `const s = 'import { VERDICT_RE } from ${EVENTS}';`, [], []],
  ["lookalike: a template", `const s = \`import { VERDICT_RE } from ${EVENTS}\`;`, [], []],
  ["a template substitution is code", `const s = \`\${await import(${EVENTS})}\`;`, [], ["dynamic import"]],
  ["a `}` in a comment inside a substitution does not close it", `const s = \`\${1 // }\n + import(${EVENTS})}\`;`, [], ["dynamic import"]],
  ["control: the same substitution without the `}`", `const s = \`\${1 // x\n + import(${EVENTS})}\`;`, [], ["dynamic import"]],
  ["a `}` in a string inside a substitution does not close it", `const s = \`\${"}"}\`;\nexport * from ${EVENTS};`, [], ["re-export"]],
  ["a regex holding a quote does not open a string", `const q = /["']/;\nimport { VERDICT_RE } from ${EVENTS};`, ["VERDICT_RE"], []],
  ["a keyword as a property name divides", `const o = { return: 1 }; o.return / [import(${EVENTS})] / 2;`, [], ["dynamic import"]],
  ["a keyword after a spread is still a keyword", `const kind = [...typeof /["']/];\nimport { VERDICT_RE } from ${EVENTS};`, ["VERDICT_RE"], []],
  ["non-ASCII inside a comment or a string is text", `// caf\u00e9\nconst s = "\u{10400}";\nimport { VERDICT_RE } from ${EVENTS};`, ["VERDICT_RE"], []],
  ["a CR ends a line comment", `// note\rexport * as ns from ${EVENTS};`, [], ["re-export"]],
  ["a U+2028 ends a line comment", `// note\u2028export * as ns from ${EVENTS};`, [], ["re-export"]],
  ["control: an LF ends a line comment", `// note\nexport * as ns from ${EVENTS};`, [], ["re-export"]],
  // -- refuse rather than guess
  ["refused: `/` after a line break (statement end)", `debugger\n/[import { VERDICT_RE } from ${EVENTS};]/;`, [], AMBIGUOUS_SLASH("a line break")],
  ["refused: `/` after a line break (a declaration)", `let x\n/[import { VERDICT_RE } from ${EVENTS};]/;`, [], AMBIGUOUS_SLASH("a line break")],
  ["refused: `/` after a line break (an import)", `import "node:fs"\n/[import { VERDICT_RE } from ${EVENTS};]/;`, [], AMBIGUOUS_SLASH("a line break")],
  ["refused: `/` after a block comment spanning lines", `let x /*\n*/ /[import { VERDICT_RE } from ${EVENTS};]/;`, [], AMBIGUOUS_SLASH("a line break")],
  ["refused: `/` after an `if` head's `)`", `if (true) /[import { VERDICT_RE } from ${EVENTS};]/.test("");`, [], AMBIGUOUS_SLASH(HEAD)],
  ["refused: `/` after a `while` head's `)`", "while (x) /re/.test(s);", [], AMBIGUOUS_SLASH(HEAD)],
  ["refused: `/` after a `for await` head's `)`", "for await (const x of xs) /re/.test(x);", [], AMBIGUOUS_SLASH(HEAD)],
  ["control: `/` after a call's `)` divides", `const seconds = Date.now() / 1000;\nimport { VERDICT_RE } from ${EVENTS};`, ["VERDICT_RE"], []],
  ["control: `/` after a grouping `)` divides", `const half = (1 + 2) / 2;\nimport { VERDICT_RE } from ${EVENTS};`, ["VERDICT_RE"], []],
  ["control: a division after `)` does not hide a later import", `const q = f(x) / [import(${EVENTS})] / 2;`, [], ["dynamic import"]],
  ["control: `)` then an operator other than `/`", `const q = (1 + 2) * 3;\nimport { VERDICT_RE } from ${EVENTS};`, ["VERDICT_RE"], []],
  ["refused: `/` after `}`", 'function f() {} /re/.test("");', [], AMBIGUOUS_SLASH("`}`")],
  ["refused: `/` after `.` (a number ending in a dot)", `const x = 1. / [import(${EVENTS})] / 2;`, [], AMBIGUOUS_SLASH("`.`")],
  ["control: `/` after `]` divides", `const q = [4][0] / 2;\nimport { VERDICT_RE } from ${EVENTS};`, ["VERDICT_RE"], []],
  ["refused: `/` after `of`", 'for (const x of /a/g.exec("a")) {}', [], AMBIGUOUS_SLASH("`of`")],
  ["refused: `/` after `++`", "let a = 1; a++ / 2;", [], AMBIGUOUS_SLASH("`++`")],
  ["control: `/` after a keyword opens a regex", `const f = () => { return /["']/; };\nimport { VERDICT_RE } from ${EVENTS};`, ["VERDICT_RE"], []],
  ["refused: non-ASCII in an identifier", `export * as \u{10400} from ${EVENTS};`, [], REFUSED("a non-ASCII character outside a string, template, regex or comment")],
  ["refused: non-ASCII whitespace", `const a = 1;\u00a0/[import { VERDICT_RE } from ${EVENTS};]/;`, [], REFUSED("a non-ASCII character outside a string, template, regex or comment")],
  ["refused: an unterminated string", 'const s = "unterminated;\n', [], REFUSED("unterminated string")],
  ["refused: an unterminated template", "const s = `never closed\n", [], REFUSED("unterminated template literal")],
  ["refused: an unterminated substitution", "const s = `${1\n", [], REFUSED("unterminated template substitution")],
  ["refused: an unterminated block comment", "/* never closed\n", [], REFUSED("unterminated block comment")],
  ["refused: an unterminated regex", "const r = /never closed\n;", [], REFUSED("unterminated regex literal")],
  ["refused: an escape outside a literal", `import { \\u0056ERDICT_RE } from ${EVENTS};`, [], REFUSED("an escape outside a string, template or regex")],
];

for (const [label, source, names, undecidable] of GRAMMAR) {
  test(`usesOf: ${label}`, () => {
    assert.deepEqual(usesOf(path.join(REPO_ROOT, "scripts", "probe.mjs"), source), { names, undecidable });
  });
}
