#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Write-discipline checker for the Node surface (vibe-153, requirement 7 of #103).
//
// `scripts/lib/write.mjs` is the audited primitive; every shipped mutation routes through it.
// This checker is what keeps that true after the next edit. Two designs were rejected on #103
// before this one: a tokenizer with an ENUMERATED refusal list ("a finite list of known
// evasions does not make a tokenizer fail-closed"), and a runtime capability tripwire (broken
// by `require("fs").promises`, `process.getBuiltinModule`, pre-registration caches, forged
// `parentURL`, `process.binding` — and coverage-bounded besides). Both failed the same way: a
// blacklist cannot carry an invariant.
//
// **So the acceptance set is closed and the judgment is whole-module.** A module is `clean`
// only when every construct it uses belongs to the accepted dialect below. Anything else is
// `refused` — not because it was listed, but because it is not in the set. `eval`, the
// `Function` constructor, `Worker`, `process.binding`, a `data:` import, a bare package
// specifier, a computed member access: none are dialect productions, so none can reach
// `clean`. Nothing ambiguous resolves toward `clean`; false positives are visible and are
// fixed by rewriting the construct.
//
// The accepted dialect:
//
//   * IMPORTS. Static `import` declarations only, specifier a string literal that is one of
//     the four fs spellings, another `node:` builtin, or a relative path. `export … from`
//     naming an fs specifier is refused (a re-export launders capability); so is any other
//     provenance.
//   * CAPABILITY. An fs import binds a capability name (named / namespace / default form).
//     A capability name may be used in exactly two ways: called directly, or one plain
//     member access then called. Every other appearance — argument, return, re-assignment,
//     export, object or class field, destructuring target, computed access, bare mention —
//     is refused, so propagation and escape cannot survive.
//   * CLASSIFICATION. A resolved call's name is a MUTATOR (`raw-fs-write`) or a READER
//     (accepted). A name in NEITHER table is refused — the inversion that keeps unknown and
//     future members from passing.
//   * OPEN + HANDLES. `open`/`openSync` is a mutator unless its flag argument is a read-only
//     string literal. Its result may be consumed exactly one way: an assignment to a fresh
//     local (`const h = await open(p, "r")`, or `const h = openSync(...)`). `.then`,
//     chaining, returning, passing, wrapping, aliasing, destructuring and the callback form
//     are refused. A bound handle is a capability with its own tables.
//   * FORBIDDEN CALLEES. The dialect contains no call to `eval`, `Function`, `import(...)`,
//     `require`, `createRequire`, `Worker`, or a capability-shaped member call on `process`,
//     `globalThis`, `module` or `Reflect`.
//
// **Residual boundary, stated plainly.** This is a static discipline over `scripts/**/*.mjs`.
// It says nothing about what a child process does (a spawned program's writes are that
// program's business), about native addons, or about a runtime that rewrites itself in ways
// no source text shows. It does not read Python or shell — those surfaces have their own
// enforcer in `tests/test_write_discipline.py`.

import { readFileSync } from "node:fs";
import path from "node:path";

export const PRIMITIVE = "scripts/lib/write.mjs";

// Empty, and it stays empty: every shipped site already routes through the primitive, so an
// entry here would be a NEW claim that some site cannot — not a ratchet step.
export const KNOWN = new Set();

const FS_SPECIFIERS = new Set(["node:fs", "node:fs/promises", "fs", "fs/promises"]);

const BASE_MUTATORS = [
  "writeFile", "appendFile", "mkdir", "mkdtemp", "rename", "link", "symlink", "unlink",
  "rm", "rmdir", "chmod", "chown", "lchmod", "lchown", "copyFile", "cp", "truncate",
  "ftruncate", "utimes", "lutimes", "futimes", "write", "writev", "fchmod", "fchown",
  "fdatasync", "fsync", "mkdtempDisposable",
];
export const MUTATORS = new Set([
  ...BASE_MUTATORS,
  ...BASE_MUTATORS.map((n) => `${n}Sync`),
  // `open`/`openSync` are in the floor because they are mutators by default; `classify()`
  // reprieves them ONLY for a read-only literal flag consumed in the accepted binding form.
  "open", "openSync", "createWriteStream",
]);

const BASE_READERS = [
  "readFile", "readdir", "stat", "lstat", "fstat", "realpath", "access", "readlink",
  "opendir", "watch", "createReadStream", "read", "readv", "glob", "statfs", "close",
];
const READERS = new Set([
  ...BASE_READERS,
  ...BASE_READERS.map((n) => `${n}Sync`),
  "existsSync", "constants", "promises", "watchFile", "unwatchFile",
]);

export const HANDLE_MUTATORS = new Set([
  "write", "writev", "writeFile", "appendFile", "truncate", "chmod", "chown", "utimes",
  "createWriteStream", "sync", "datasync",
]);
const HANDLE_READERS = new Set([
  "read", "readv", "readFile", "readLines", "stat", "createReadStream", "close",
  "readableWebStream",
]);

const FORBIDDEN_CALLEES = new Set([
  "eval", "Function", "require", "createRequire", "Worker",
]);
// Modules whose exports ARE capability factories. Any local name bound from one of these —
// under any alias, default or namespace form — is dangerous by BINDING, so
// `import { createRequire as make } from "node:module"` cannot launder it.
const CAPABILITY_MODULES = new Set(["node:module", "module", "node:vm", "vm",
                                    "node:worker_threads", "worker_threads"]);
const FORBIDDEN_OBJECTS = new Set(["process", "globalThis", "module", "Reflect", "global"]);
const BENIGN_HOST_MEMBERS = new Set([
  "exit", "on", "once", "off", "emit", "cwd", "hrtime", "nextTick", "kill", "uptime",
  "memoryUsage", "chdir", "removeListener",
]);

const READ_ONLY_FLAGS = new Set(["r", "rs"]);

const WORD = /[A-Za-z0-9_$]/;
const REGEX_OK_WORDS = new Set([
  "return", "typeof", "case", "in", "of", "delete", "void", "instanceof", "new", "do",
  "else", "yield", "await",
]);

class Refusal extends Error {}

/** The top-level area a checked file belongs to (its `scripts/` or `tests/` root). */
function corpusRootOf(file) {
  const abs = path.resolve(file);
  const parts = abs.split(path.sep);
  for (const marker of ["scripts", "tests"]) {
    const idx = parts.lastIndexOf(marker);
    if (idx !== -1) return parts.slice(0, idx + 1).join(path.sep);
  }
  return path.dirname(abs);
}

/** Tokens: identifiers, punctuation, strings (value kept); templates and regexes elided. */
function tokenize(source) {
  const out = [];
  let i = 0;
  let prev = null;
  const push = (type, value) => { out.push({ type, value }); prev = { type, value }; };
  while (i < source.length) {
    const c = source[i];
    if (c === "/" && source[i + 1] === "/") {
      while (i < source.length && source[i] !== "\n") i += 1;
      continue;
    }
    if (c === "/" && source[i + 1] === "*") {
      const end = source.indexOf("*/", i + 2);
      if (end === -1) throw new Refusal("unterminated block comment");
      i = end + 2;
      continue;
    }
    if (c === "\n" || c === " " || c === "\t" || c === "\r") { i += 1; continue; }
    if (c === '"' || c === "'") {
      let j = i + 1;
      let value = "";
      let escaped = false;
      while (j < source.length && source[j] !== c) {
        if (source[j] === "\\") { escaped = true; value += source[j + 1] ?? ""; j += 2; continue; }
        if (source[j] === "\n") throw new Refusal("unterminated string");
        value += source[j];
        j += 1;
      }
      if (j >= source.length) throw new Refusal("unterminated string");
      i = j + 1;
      out.push({ type: "string", value, escaped });
      prev = { type: "string", value };
      continue;
    }
    if (c === "`") {
      // A template's STATIC parts are inert text, but every `${ … }` substitution is ordinary
      // code and is tokenized as such — eliding it would let `${fs.writeFileSync(p)}` pass.
      let j = i + 1;
      push("template", "");
      while (j < source.length) {
        if (source[j] === "\\") { j += 2; continue; }
        if (source[j] === "`") { j += 1; break; }
        if (source[j] === "$" && source[j + 1] === "{") {
          // hand the substitution back to the main loop by recursing over its source slice
          let depth = 1;
          let k = j + 2;
          while (k < source.length && depth > 0) {
            const ch = source[k];
            if (ch === "\\") { k += 2; continue; }
            if (ch === "`") {                       // nested template: skip to its close
              let d2 = 0;
              k += 1;
              while (k < source.length) {
                if (source[k] === "\\") { k += 2; continue; }
                if (d2 === 0 && source[k] === "`") { k += 1; break; }
                if (source[k] === "$" && source[k + 1] === "{") { d2 += 1; k += 2; continue; }
                if (d2 > 0 && source[k] === "}") { d2 -= 1; }
                k += 1;
              }
              continue;
            }
            if (ch === "{") depth += 1;
            else if (ch === "}") depth -= 1;
            k += 1;
          }
          if (depth > 0) throw new Refusal("unterminated template substitution");
          for (const tok of tokenize(source.slice(j + 2, k - 1))) out.push(tok);
          prev = out[out.length - 1] ?? prev;
          j = k;
          continue;
        }
        j += 1;
      }
      if (j > source.length) throw new Refusal("unterminated template literal");
      i = j;
      continue;
    }
    if (c === "/") {
      // Only positions where a VALUE may begin admit a regex. Everything else is division.
      // `)`/`]`/`}` and an identifier/number end a value; so does a postfix `++`/`--`, which
      // is why the last two tokens are inspected rather than only the last.
      const prev2 = out[out.length - 2] ?? null;
      const postfixUpdate = prev !== null && prev2 !== null
        && prev.type === "punct" && prev2.type === "punct"
        && ((prev.value === "+" && prev2.value === "+")
            || (prev.value === "-" && prev2.value === "-"));
      const regexAllowed = !postfixUpdate && (prev === null
        || (prev.type === "punct" && !")]}".includes(prev.value))
        || (prev.type === "word" && REGEX_OK_WORDS.has(prev.value)));
      if (!regexAllowed) { i += 1; push("punct", "/"); continue; }
      let j = i + 1;
      let inClass = false;
      while (j < source.length) {
        if (source[j] === "\\") { j += 2; continue; }
        if (source[j] === "[") inClass = true;
        else if (source[j] === "]") inClass = false;
        else if (source[j] === "/" && !inClass) break;
        else if (source[j] === "\n") throw new Refusal("unterminated regex");
        j += 1;
      }
      if (j >= source.length) throw new Refusal("unterminated regex");
      j += 1;
      while (j < source.length && WORD.test(source[j])) j += 1;
      i = j;
      push("regex", "");
      continue;
    }
    if (WORD.test(c)) {
      let j = i;
      while (j < source.length && WORD.test(source[j])) j += 1;
      push("word", source.slice(i, j));
      i = j;
      continue;
    }
    push("punct", c);
    i += 1;
  }
  return out;
}

function assertProvenance(spec, escaped, fromFile) {
  // An escaped specifier means the checker's literal and Node's resolved value can differ
  // (`"node:\\x66s"` resolves to node:fs). Refuse rather than compare a wrong string.
  if (escaped) throw new Refusal("import specifier contains escapes");
  if (spec.startsWith("./") || spec.startsWith("../")) {
    // A relative import must land inside the CHECKED corpus — the top-level area the
    // importing file lives in. One that climbs out reaches a module this run never judged,
    // so its exports are unknown provenance and it refuses.
    if (fromFile) {
      const target = path.resolve(path.dirname(path.resolve(fromFile)), spec);
      const area = path.resolve(corpusRootOf(fromFile));
      if (target !== area && !target.startsWith(area + path.sep)) {
        throw new Refusal(`relative import leaves the checked corpus: ${spec}`);
      }
    }
    return;
  }
  if (spec.startsWith("node:")) return;
  if (FS_SPECIFIERS.has(spec)) return;
  throw new Refusal(`import provenance outside the accepted set: ${spec}`);
}

/** First token of each argument of the call whose `(` is at `openIndex`. */
function readArgs(toks, openIndex) {
  const args = [];
  let depth = 0;
  let current = null;
  for (let k = openIndex; k < toks.length; k += 1) {
    const t = toks[k];
    if (t.type === "punct" && "([{".includes(t.value)) {
      depth += 1;
      if (depth === 1) continue;
    }
    if (t.type === "punct" && ")]}".includes(t.value)) {
      depth -= 1;
      if (depth === 0) { if (current) args.push(current); break; }
    }
    if (depth === 1 && t.type === "punct" && t.value === ",") {
      args.push(current ?? { type: "empty", value: "" });
      current = null;
      continue;
    }
    if (depth >= 1 && current === null) current = t;
  }
  return args;
}

/**
 * The local name an accepted `open(...)` result binds to, or null.
 * Accepted: `const NAME = await open(...)` / `const NAME = openSync(...)`, and nothing that
 * continues the expression afterwards.
 */
function acceptedOpenBinding(toks, nameIndex) {
  let k = nameIndex - 1;
  if (toks[k] && toks[k].type === "word" && toks[k].value === "await") k -= 1;
  if (!(toks[k] && toks[k].type === "punct" && toks[k].value === "=")) return null;
  const name = toks[k - 1];
  const decl = toks[k - 2];
  if (!name || name.type !== "word") return null;
  if (!decl || decl.type !== "word" || !["const", "let"].includes(decl.value)) return null;
  let depth = 0;
  for (let j = nameIndex + 1; j < toks.length; j += 1) {
    const t = toks[j];
    if (t.type === "punct" && "([{".includes(t.value)) depth += 1;
    if (t.type === "punct" && ")]}".includes(t.value)) {
      depth -= 1;
      if (depth === 0) {
        const after = toks[j + 1];
        // Any continuation of the expression — `.then`, `["then"]`, a call, a template tag —
        // takes the handle somewhere this checker does not follow, so it refuses.
        // A template token is how a tagged template shows up after the call.
        if (after && (after.type === "template"
            || (after.type === "punct" && ".[(".includes(after.value)))) return null;
        return name.value;
      }
    }
  }
  return null;
}

function classifyModule(source, fromFile) {
  const toks = tokenize(source);
  const caps = new Map();
  const handles = new Set();
  const dangerous = new Set();     // names bound from a capability-factory module
  const importSpans = [];          // [start, end] token ranges of import declarations
  let sawMutator = false;
  const at = (k) => toks[k] ?? { type: "eof", value: "" };

  // --- imports and re-exports -----------------------------------------------------------
  for (let k = 0; k < toks.length; k += 1) {
    const t = at(k);
    if (t.type !== "word") continue;

    if (t.value === "export") {
      let j = k + 1;
      let sawFrom = false;
      while (j < toks.length) {
        const tok = at(j);
        if (tok.type === "punct" && tok.value === ";") break;
        if (tok.type === "word" && tok.value === "from") { sawFrom = true; break; }
        if (tok.type === "word"
            && ["function", "class", "const", "let", "var", "async"].includes(tok.value)) break;
        j += 1;
      }
      if (sawFrom) {
        const spec = at(j + 1);
        if (spec.type !== "string") throw new Refusal("export-from with a non-literal specifier");
        if (FS_SPECIFIERS.has(spec.value)) throw new Refusal("re-export of an fs module");
        assertProvenance(spec.value, spec.escaped, fromFile);
      }
      continue;
    }

    if (t.value !== "import") continue;
    if (at(k + 1).type === "punct" && at(k + 1).value === "(") {
      throw new Refusal("dynamic import()");
    }
    if (at(k + 1).type === "punct" && at(k + 1).value === ".") continue;   // import.meta

    let j = k + 1;
    const named = [];
    let namespaceName = null;
    let defaultName = null;
    let sawFrom = false;
    while (j < toks.length) {
      const tok = at(j);
      if (tok.type === "string") break;
      if (tok.type === "word" && tok.value === "from") { sawFrom = true; j += 1; continue; }
      if (tok.type === "punct" && tok.value === "*") {
        if (!(at(j + 1).type === "word" && at(j + 1).value === "as")) {
          throw new Refusal("unrecognized namespace import form");
        }
        namespaceName = at(j + 2).value;
        j += 3;
        continue;
      }
      if (tok.type === "punct" && tok.value === "{") {
        j += 1;
        while (j < toks.length && !(at(j).type === "punct" && at(j).value === "}")) {
          if (at(j).type === "word") {
            const aliased = at(j + 1).type === "word" && at(j + 1).value === "as";
            named.push([aliased ? at(j + 2).value : at(j).value, at(j).value]);
            j += aliased ? 3 : 1;
            continue;
          }
          j += 1;
        }
        j += 1;
        continue;
      }
      if (tok.type === "word" && !sawFrom && defaultName === null && named.length === 0
          && namespaceName === null) {
        defaultName = tok.value;
        j += 1;
        continue;
      }
      j += 1;
    }
    const spec = at(j);
    if (spec.type !== "string") throw new Refusal("import with a non-literal specifier");
    assertProvenance(spec.value, spec.escaped, fromFile);
    importSpans.push([k, j]);
    if (CAPABILITY_MODULES.has(spec.value)) {
      if (namespaceName) dangerous.add(namespaceName);
      if (defaultName) dangerous.add(defaultName);
      for (const [local] of named) dangerous.add(local);
    }
    if (!FS_SPECIFIERS.has(spec.value)) continue;
    if (namespaceName) caps.set(namespaceName, { kind: "ns" });
    if (defaultName) caps.set(defaultName, { kind: "ns" });
    for (const [local, imported] of named) caps.set(local, { kind: "named", imported });
  }

  /** MUTATOR / READER classification; binds handles for accepted read-only opens. */
  const classify = (name, nameIndex) => {
    if (name === "open" || name === "openSync") {
      const args = readArgs(toks, nameIndex + 1);
      if (args.length >= 3) throw new Refusal("callback-form open");
      const flag = args[1];
      if (flag === undefined) throw new Refusal("open without a resolvable flag");
      if (flag.type !== "string") throw new Refusal("open with an unresolvable flag");
      if (!READ_ONLY_FLAGS.has(flag.value)) return "mutator";
      const bound = acceptedOpenBinding(toks, nameIndex);
      if (bound === null) throw new Refusal("open() result consumed outside the accepted form");
      handles.add(bound);
      return "reader";
    }
    if (MUTATORS.has(name)) return "mutator";
    if (READERS.has(name)) return "reader";
    throw new Refusal(`unknown fs member: ${name}`);
  };

  // --- every use ------------------------------------------------------------------------
  for (let k = 0; k < toks.length; k += 1) {
    const t = at(k);
    if (t.type !== "word") continue;
    const prev = at(k - 1);
    const next = at(k + 1);

    const insideImport = importSpans.some(([a, b]) => k >= a && k <= b);
    if (dangerous.has(t.value) && !insideImport) {
      throw new Refusal(`capability-factory binding used: ${t.value}`);
    }
    if (FORBIDDEN_CALLEES.has(t.value) && !caps.has(t.value) && !insideImport) {
      // ANY appearance refuses — `const e = eval; e(src)` aliases the capability without
      // ever calling the forbidden name in place.
      throw new Refusal(`forbidden construct: ${t.value}`);
      if (prev.type === "punct" && prev.value === ".") {
        throw new Refusal(`indirect ${t.value} reference`);
      }
    }
    if (t.value === "constructor" && prev.type === "punct" && prev.value === ".") {
      // Reaching `.constructor` at all hands out the Function constructor — the indirect
      // eval the rejected tokenizer missed. Not a dialect production, in any position.
      throw new Refusal("indirect constructor reference");
    }
    if (FORBIDDEN_OBJECTS.has(t.value) && next.type === "punct") {
      if (next.value === "[") {
        // A computed member on a host object names something the checker cannot read.
        throw new Refusal(`computed host access: ${t.value}[…]`);
      }
      if (next.value === ".") {
        const member = at(k + 2);
        const called = at(k + 3).type === "punct" && at(k + 3).value === "(";
        if (called && member.type === "word" && !BENIGN_HOST_MEMBERS.has(member.value)) {
          throw new Refusal(`reflective/host call: ${t.value}.${member.value}`);
        }
      }
    }

    if (!caps.has(t.value) && !handles.has(t.value)) continue;
    // A mention INSIDE the import declaration that bound it is a declaration, not a use —
    // decided by exact token span, so `import { readFile as read }` binds cleanly while an
    // object-shorthand `{ readFile }` elsewhere still refuses.
    if (insideImport) continue;
    if (prev.type === "punct" && prev.value === ".") {
      throw new Refusal(`capability reached as a member: .${t.value}`);
    }

    if (next.type === "punct" && next.value === "(") {
      if (handles.has(t.value)) throw new Refusal("handle called directly");
      const cap = caps.get(t.value);
      if (cap.kind !== "named") throw new Refusal("namespace called directly");
      if (classify(cap.imported, k) === "mutator") sawMutator = true;
      continue;
    }
    if (next.type === "punct" && next.value === ".") {
      const member = at(k + 2);
      if (member.type !== "word") throw new Refusal("non-identifier member access");
      if (!(at(k + 3).type === "punct" && at(k + 3).value === "(")) {
        throw new Refusal(`capability member not called: ${t.value}.${member.value}`);
      }
      if (handles.has(t.value)) {
        if (HANDLE_MUTATORS.has(member.value)) { sawMutator = true; k += 3; continue; }
        if (HANDLE_READERS.has(member.value)) { k += 3; continue; }
        throw new Refusal(`unknown FileHandle member: ${member.value}`);
      }
      if (classify(member.value, k + 2) === "mutator") sawMutator = true;
      k += 3;
      continue;
    }
    if (next.type === "punct" && next.value === "[") {
      throw new Refusal("computed member access on a capability");
    }
    throw new Refusal(`capability escapes: ${t.value}`);
  }

  return sawMutator ? "raw-fs-write" : "clean";
}

export function inspect(file) {
  let source;
  try {
    source = readFileSync(file, "utf8");
  } catch (err) {
    return { verdict: "refused", detail: `unreadable: ${err.message}` };
  }
  try {
    return { verdict: classifyModule(source, file), detail: "" };
  } catch (err) {
    if (err instanceof Refusal) return { verdict: "refused", detail: err.message };
    return { verdict: "refused", detail: `internal: ${err.message}` };
  }
}

function main(argv) {
  const files = argv.slice(2);
  if (files.length === 0) {
    process.stderr.write("no-raw-fs-writes: no files given\n");
    return 2;
  }
  let bad = 0;
  let inspected = 0;
  let exempt = 0;
  for (const file of files) {
    const rel = path.relative(process.cwd(), file);
    if (rel === PRIMITIVE || KNOWN.has(rel)) { exempt += 1; continue; }
    inspected += 1;
    const { verdict, detail } = inspect(file);
    if (verdict !== "clean") {
      process.stdout.write(`${rel}: ${verdict}${detail ? ` — ${detail}` : ""}\n`);
      bad += 1;
    }
  }
  if (bad === 0) {
    process.stdout.write(
      `no-raw-fs-writes: ${inspected} module(s) clean, ${exempt} exempt `
      + `(${files.length} given)\n`);
  }
  return bad === 0 ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exit(main(process.argv));
}
