// SPDX-License-Identifier: ISC
// Reading the Stop-gate toggle without spawning an interpreter (vibe-208 / grill P4).
//
// `scripts/lib/store.py` is the resolver, and the hook shells to it on **every** Stop — ~50-150 ms
// of Python start-up per turn end, on every installation, to learn a boolean that is `false` on all
// of them by default (D3: the gate ships disabled). This module answers that one question in Node,
// and defers to the resolver whenever it cannot answer it *safely*.
//
// **Why a direct read is sound at all, and why it was not before.** Since vibe-186 (`40b33a1`) the
// three `gate.*` settings are **store-only**: `store.py:170-179` rebuilds `resolved["gate"]` from the
// runtime store layered over `FRESH`, and `config.py:100-108` ignores a `gate` block in
// `.vibe-suite.md` with a warning naming the rule. The store is therefore the ONE input to this key,
// so reading it directly reproduces the resolver rather than approximating it. Before vibe-186 the
// project file could set the gate, and this module would have been a way for repository content to
// switch the gate off — the grill report that asked for this optimisation also, in the same
// document, reported the flaw that made it unsafe at the time.
//
// **The answer is three-valued, and only one value may skip the spawn.** `Store.overrides()`
// validates every entry under `config` on the way *out*, not just on the way in, so a hand-edited
// file can make the resolver fail in ways that have nothing to do with the toggle. This module
// answers `"disabled"` only for a document the resolver itself would accept; everything else is
// `"defer"`, and the caller spawns Python exactly as before. That asymmetry is the safety argument:
// a `"defer"` costs a process, while a wrong `"disabled"` would silently turn a reported infra
// failure into an invisible one.
//
// **Decoding is strict, deliberately.** `readFileSync(p, "utf8")` substitutes U+FFFD for invalid
// bytes and hands back a perfectly parseable document; `Path.read_text(encoding="utf-8")` raises
// `UnicodeDecodeError`, which `store.py` does not catch, so the resolver exits non-zero and the hook
// reports an infra failure. Lenient decoding here would disagree with the resolver on exactly the
// input where disagreeing is worst.

import { readFileSync } from "node:fs";
import path from "node:path";

import { STATE_DIRNAME } from "./eventlog.mjs";

/** The state file's name, matching `store.py:STATE_FILENAME`. */
export const STATE_FILENAME = "state.json";

/**
 * Mirror of `store.py:SHADOWABLE` — every runtime-shadowable key AND its domain.
 *
 * Kept as a mapping rather than a key list because a changed *domain* is drift too, and
 * `tests/node/stop-gate.test.mjs` parses the Python literal and compares the whole object.
 */
export const SHADOWABLE_DOMAINS = {
  "gate.stop_review_gate": "bool",
  "gate.model": "string",
  "gate.fail_policy": "open|closed",
};

const isPlainObject = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

/** `store.py:_validate`, for one already-known key. */
function inDomain(domain, value) {
  if (domain === "bool") return typeof value === "boolean";
  if (domain === "string") return typeof value === "string";
  return domain.split("|").includes(value);
}

/**
 * `"disabled"` when the gate is provably off, `"defer"` when the resolver must decide.
 *
 * Never throws: every failure to read, decode, parse or validate is a `"defer"`, which is the
 * behaviour the hook had before this module existed.
 */
export function storedGateToggle(workspace) {
  let bytes;
  try {
    bytes = readFileSync(path.join(workspace, STATE_DIRNAME, STATE_FILENAME));
  } catch (error) {
    // A missing store is the fresh install, and `FRESH` makes that `false`. Anything else — a
    // permission error, a directory in the way — is not a statement about the toggle.
    if (error?.code === "ENOENT") return "disabled";
    return "defer";
  }

  let document;
  try {
    // `ignoreBOM: true` is a misleading name: it means "do not TREAT the BOM specially",
    // i.e. keep it in the output. The default STRIPS a leading U+FEFF, and
    // `Path.read_text(encoding="utf-8")` does not — so a BOM-prefixed document parses cleanly
    // in Node while `json.loads` rejects it, and this reader would answer "disabled" for a
    // store the resolver refuses to read. That is the silent allow this module exists to
    // prevent, so the BOM is preserved and `JSON.parse` rejects it exactly as python does.
    document = JSON.parse(
      new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes));
  } catch {
    return "defer";                              // undecodable or unparseable: store.py exits non-zero
  }
  if (!isPlainObject(document)) return "defer";  // store.py: "expected a JSON object at the top level"

  const config = document.config;
  // `store.py:FRESH` makes `gate.stop_review_gate` false when it is not stored, so a document
  // with no `config` member is a positive answer, not an absence of one.
  if (config === undefined) return "disabled";
  if (!isPlainObject(config)) return "defer";    // store.py `_read`: "'config' must be an object"

  // `overrides()` walks EVERY section, so an unknown sibling section makes the resolver fail even
  // when `gate` itself is impeccable. Answering "disabled" for such a store would be answering a
  // question the resolver refuses to answer at all.
  for (const [section, values] of Object.entries(config)) {
    if (!isPlainObject(values)) return "defer";
    for (const [leaf, value] of Object.entries(values)) {
      const domain = SHADOWABLE_DOMAINS[`${section}.${leaf}`];
      if (domain === undefined) return "defer";  // store.py: "not a runtime-shadowable setting"
      if (!inDomain(domain, value)) return "defer";
    }
  }

  // Enabled is a `"defer"` too: the hook still needs `gate.model` and `gate.fail_policy`, and the
  // resolver is what supplies them. This module's whole value is the disabled case.
  return config.gate?.stop_review_gate === true ? "defer" : "disabled";
}
