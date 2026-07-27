#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Top-level-await checker for shipped .mjs modules (E1.1 / vibe-11, cc-suite W7 class).
//
// `node --check` **accepts** top-level await in an .mjs file — verified, not assumed — so it cannot
// grade the acceptance criterion. A token grep cannot either: it can't tell a top-level `await` from
// one inside an async function, which every module here legitimately contains.
//
// Two earlier attempts tried to classify arbitrary JavaScript and both had false negatives. No parser
// is available (this repo has no dependencies and Node exposes none), so this checker does not try to
// be complete. It is **sound in one direction**:
//
//     Every ambiguity resolves toward `top-level-await` or `refused`. Nothing resolves toward `clean`.
//
// False negatives are therefore impossible by construction — the only property that matters, since a
// false negative is what let round 1 ship. False positives are possible and are a visible failure the
// author fixes by rewriting the construct. This is a complete specification of the decision
// procedure, which is achievable, rather than of the grammar, which is not.
//
// The accepted dialect:
//
//   * `{` is FUNCTION_BODY only when unambiguous — right after `=>`, or after the `)` whose matching
//     `(` is preceded by a `function` / `async function` header or a method shorthand. Everything
//     else is OTHER: object literals, blocks, class bodies, import/export clauses, destructuring,
//     spread. OTHER is accepted, never refused — but it does not shelter an `await`.
//   * An `await` with no enclosing FUNCTION_BODY is top-level await. That includes one inside a
//     top-level object literal or `if (x) { … }`, both OTHER.
//   * A concise (braceless) arrow body ends at the first `,` `;` `:` `?` at the arrow's depth, at a
//     depth drop, or **at a newline** — ASI makes `const f = x => x\nawait work();` two statements
//     with genuine top-level await, and bounding only at the next `;` would swallow it.
//   * When the lexer cannot decide whether `/` opens a regex, it refuses rather than guessing, since
//     guessing wrong mis-lexes everything after it.

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WORD = /[A-Za-z0-9_$]/;

class Refusal extends Error {}

/** Tokens after which a `/` begins a regex rather than a division. */
function regexCanFollow(previous) {
  if (previous === null) return true;
  if (previous.type === "punct") return !")]}".includes(previous.value);
  if (previous.type === "word") {
    return ["return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw",
      "case", "do", "else", "yield", "await"].includes(previous.value);
  }
  return false;                                   // after a literal, `/` is division
}

/**
 * Reduce source to a token stream, discarding comment and string bodies but **descending into
 * template substitutions**, whose contents are executable code.
 */
function tokenize(source) {
  const tokens = [];
  let index = 0;
  let previous = null;
  const push = (type, value, at) => {
    const token = { type, value, at };
    tokens.push(token);
    previous = token;
    return token;
  };

  const templateStack = [];

  while (index < source.length) {
    const char = source[index];

    if (char === "\n") { push("newline", "\n", index); index += 1; continue; }
    if (char === " " || char === "\t" || char === "\r") { index += 1; continue; }

    if (char === "/" && source[index + 1] === "/") {
      while (index < source.length && source[index] !== "\n") index += 1;
      continue;
    }
    if (char === "/" && source[index + 1] === "*") {
      const end = source.indexOf("*/", index + 2);
      if (end < 0) throw new Refusal("unterminated block comment");
      index = end + 2;
      continue;
    }

    if (char === '"' || char === "'") {
      index += 1;
      while (index < source.length && source[index] !== char) {
        if (source[index] === "\\") index += 1;
        index += 1;
      }
      if (index >= source.length) throw new Refusal("unterminated string");
      index += 1;
      push("literal", "string", index);
      continue;
    }

    if (char === "`") {
      templateStack.push({ depth: 0 });
      index += 1;
      // Scan template chunks; `${` opens real code, which the main loop must see.
      while (index < source.length) {
        if (source[index] === "\\") { index += 2; continue; }
        if (source[index] === "`") { index += 1; templateStack.pop(); push("literal", "template", index); break; }
        if (source[index] === "$" && source[index + 1] === "{") {
          index += 2;
          push("punct", "${", index);
          break;                                   // fall back to the main loop for the substitution
        }
        index += 1;
      }
      continue;
    }

    if (char === "}" && templateStack.length > 0 && templateStack[templateStack.length - 1].depth === 0) {
      // Closing a substitution: resume template scanning.
      index += 1;
      push("punct", "}$", index);
      while (index < source.length) {
        if (source[index] === "\\") { index += 2; continue; }
        if (source[index] === "`") { index += 1; templateStack.pop(); push("literal", "template", index); break; }
        if (source[index] === "$" && source[index + 1] === "{") { index += 2; push("punct", "${", index); break; }
        index += 1;
      }
      continue;
    }

    if (char === "/") {
      if (!regexCanFollow(previous)) { push("punct", "/", index); index += 1; continue; }
      if (previous && previous.type === "punct" && previous.value === ")") {
        throw new Refusal("cannot decide whether `/` after `)` is a regex or a division");
      }
      index += 1;
      let inClass = false;
      while (index < source.length) {
        const c = source[index];
        if (c === "\\") { index += 2; continue; }
        if (c === "[") inClass = true;
        else if (c === "]") inClass = false;
        else if (c === "/" && !inClass) break;
        else if (c === "\n") throw new Refusal("unterminated regex literal");
        index += 1;
      }
      if (index >= source.length) throw new Refusal("unterminated regex literal");
      index += 1;
      while (index < source.length && WORD.test(source[index])) index += 1;
      push("literal", "regex", index);
      continue;
    }

    if (WORD.test(char)) {
      const start = index;
      while (index < source.length && WORD.test(source[index])) index += 1;
      push("word", source.slice(start, index), start);
      continue;
    }

    if (source.startsWith("=>", index)) { push("punct", "=>", index); index += 2; continue; }
    if (templateStack.length > 0 && char === "{") templateStack[templateStack.length - 1].depth += 1;
    if (templateStack.length > 0 && char === "}") templateStack[templateStack.length - 1].depth -= 1;
    push("punct", char, index);
    index += 1;
  }
  return tokens;
}

/** Decide whether the `{` at `position` opens a function body. Ambiguity is NOT a function body. */
function opensFunctionBody(tokens, position) {
  let cursor = position - 1;
  while (cursor >= 0 && tokens[cursor].type === "newline") cursor -= 1;
  if (cursor < 0) return false;
  const before = tokens[cursor];
  if (before.type === "punct" && before.value === "=>") return true;
  if (!(before.type === "punct" && before.value === ")")) return false;

  // Walk back to the matching `(`, then inspect what precedes it.
  let depth = 0;
  while (cursor >= 0) {
    const token = tokens[cursor];
    if (token.type === "punct" && token.value === ")") depth += 1;
    if (token.type === "punct" && token.value === "(") {
      depth -= 1;
      if (depth === 0) break;
    }
    cursor -= 1;
  }
  if (cursor < 0) return false;
  let head = cursor - 1;
  while (head >= 0 && tokens[head].type === "newline") head -= 1;
  if (head < 0) return false;
  const name = tokens[head];
  if (name.type === "word" && name.value === "function") return true;
  if (name.type === "word") {
    // `async`, `get`, `set` and `static` are contextual keywords — also ordinary identifiers.
    // `async\nfoo()\n{ await x(); }` is an expression statement, a call and a block, not an async
    // method: a newline between keyword and name is a statement boundary. Adjacency is therefore
    // required here, unlike `function`, which cannot stand alone as an expression statement.
    const prior = head - 1;
    if (prior >= 0 && tokens[prior].type === "word"
        && ["function", "async", "get", "set", "static"].includes(tokens[prior].value)) return true;
  }
  return false;                                    // e.g. `foo()\n{ … }` — a call, then a block
}

function inspectSource(source) {
  const tokens = tokenize(source);
  const stack = [];                                // "FN" | "OTHER"
  const arrows = [];                               // open concise-arrow regions

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];

    if (token.type === "newline") {
      // A newline closes any concise arrow region at this depth (ASI).
      while (arrows.length > 0 && arrows[arrows.length - 1].depth >= stack.length) arrows.pop();
      continue;
    }

    if (token.type === "punct") {
      if (token.value === "=>") {
        let ahead = index + 1;
        while (ahead < tokens.length && tokens[ahead].type === "newline") ahead += 1;
        const braced = ahead < tokens.length && tokens[ahead].type === "punct" && tokens[ahead].value === "{";
        if (!braced) arrows.push({ depth: stack.length });
        continue;
      }
      if (token.value === "{" || token.value === "${") {
        stack.push(token.value === "{" && opensFunctionBody(tokens, index) ? "FN" : "OTHER");
        continue;
      }
      if (token.value === "}" || token.value === "}$") {
        stack.pop();
        while (arrows.length > 0 && arrows[arrows.length - 1].depth > stack.length) arrows.pop();
        continue;
      }
      if ([",", ";", ":", "?"].includes(token.value)) {
        while (arrows.length > 0 && arrows[arrows.length - 1].depth >= stack.length) arrows.pop();
        continue;
      }
      continue;
    }

    if (token.type === "word" && token.value === "await") {
      if (arrows.length > 0) {
        throw new Refusal("`await` inside a concise arrow body — rewrite as `=> { return await …; }`");
      }
      if (!stack.includes("FN")) return "top-level-await";
    }
  }
  return "clean";
}

export function inspect(file) {
  let source;
  try {
    source = readFileSync(file, "utf8");
  } catch (error) {
    return { file, verdict: "refused", detail: `unreadable: ${error.message}` };
  }
  try {
    return { file, verdict: inspectSource(source.replace(/^#![^\n]*\n/, "\n")) };
  } catch (error) {
    if (error instanceof Refusal) return { file, verdict: "refused", detail: error.message };
    return { file, verdict: "refused", detail: `checker error: ${error.message}` };
  }
}

function main() {
  const files = process.argv.slice(2);
  if (files.length === 0) {
    process.stderr.write("no-top-level-await: no files given\n");
    process.exit(2);
  }
  const bad = files.map(inspect).filter((result) => result.verdict !== "clean");
  for (const result of bad) {
    process.stderr.write(`${result.file}: ${result.verdict}${result.detail ? ` — ${result.detail}` : ""}\n`);
  }
  if (bad.length > 0) process.exit(1);
  process.stdout.write(`ok: no top-level await in ${files.length} shipped module(s)\n`);
}

// Run only when invoked directly, so the probe suite can import `inspect` without tripping the CLI.
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
