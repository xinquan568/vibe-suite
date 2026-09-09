// SPDX-License-Identifier: ISC
// Bridge from Node to the one `.vibe-suite.md` reader (E1.1 / vibe-11, depends on E0.5).
//
// `scripts/lib/config.py` states the rule this module exists to obey: *"One reader, because a second
// parser in another language would be two statements of one schema, and this repository has a
// documented history of what happens to a rule stated twice."* It exposes a `--json` CLI precisely
// so non-Python callers need not re-implement the grammar. This runner is one of those callers, so
// it shells out — there is no frontmatter parsing in JavaScript anywhere in this repository, and
// adding some would be the defect the config module warns about.
//
// Fail-closed, matching `config.py` itself: a reader that silently tolerates what it does not
// understand accepts a file nobody has checked. A non-zero exit or unparseable stdout raises rather
// than quietly falling back to defaults, because a wrong sandbox default is a security decision made
// by accident.

import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CONFIG_PY = path.join(HERE, "config.py");
// M8 / vibe-221: the one executable statement of the engine ladder lives behind this CLI.
const CONFIG_CLI_PY = path.join(HERE, "..", "config_cli.py");

/**
 * The bound on the interpreter this bridge shells to (vibe-209 / grill P4).
 *
 * Every Node dispatch that reads configuration comes through here, so an unbounded spawn is a
 * dispatch that can hang forever on a machine where `python3` wedges. The value is the one the
 * issue names; `spawnSync` surfaces a timeout through `result.error`, which the existing branch
 * below already routes to a ConfigBridgeError, so the bound needs no new failure path.
 */
export const CONFIG_TIMEOUT_MS = 30_000;

export class ConfigBridgeError extends Error {}

/**
 * Read resolved project configuration for `root`.
 *
 * `config.py:main()` takes the root **positionally** — `root = argv[-1] if not argv[-1]
 * .startswith("-") else "."` — so the path must be the final argument, and the shape it returns is
 * validated here rather than trusted.
 */
export function loadConfig(root = process.cwd(),
                          { python = "python3", timeoutMs = CONFIG_TIMEOUT_MS } = {}) {
  const result = spawnSync(python, [CONFIG_PY, root], { encoding: "utf8", timeout: timeoutMs });

  if (result.error) {
    throw new ConfigBridgeError(`cannot run ${python}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new ConfigBridgeError(
      `config.py exited ${result.status}: ${(result.stderr || "").trim() || "no diagnostic"}`);
  }

  // vibe-186: the reader's notices — a `sandbox` raised above read-only by `.vibe-suite.md`, a
  // store-only `gate` block ignored — arrive on its stderr with exit 0. They are the operator's to
  // see on dispatch, so they are forwarded verbatim; the JSON contract on stdout is untouched.
  if (result.stderr && result.stderr.trim()) {
    process.stderr.write(result.stderr.endsWith("\n") ? result.stderr : `${result.stderr}\n`);
  }

  let parsed;
  try {
    parsed = JSON.parse(result.stdout);
  } catch (error) {
    throw new ConfigBridgeError(`config.py did not emit JSON: ${error.message}`);
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new ConfigBridgeError("config.py emitted JSON that is not an object");
  }
  return parsed;
}

/**
 * The runner-record defaults — sandbox and effort — with the caller's explicit choices winning.
 *
 * The MODEL is deliberately not here (M8 / vibe-221). Until that change this function carried a
 * second statement of the model rule — the caller's model, else the project's per-engine override,
 * else null — beside the one every command reads; two statements of one rule are the defect class
 * this repository documents. The runners obtain `model` from `resolveModel` below, which asks the one
 * executable statement (`scripts/lib/engine_resolution.py` behind `config_cli.py resolve-engine`).
 */
export function resolveDefaults(config, overrides = {}) {
  return {
    sandbox: overrides.sandbox ?? config.sandbox ?? "read-only",
    effort: overrides.effort ?? config.effort ?? "medium",
  };
}

/**
 * The model for one external lane, from the one statement of the engine ladder (M8 / vibe-221).
 *
 * Spawns `python3 scripts/config_cli.py --workspace <root> resolve-engine --engine <engine>
 * [--model <model>]` — bounded like `loadConfig`, fail-closed like `loadConfig`: a non-zero exit or
 * non-JSON stdout is a ConfigBridgeError, never a silent `null`, because a model chosen by accident
 * is a P9 decision made by accident. `noModel` is the caller's deliberate "the backend's own
 * default" (E1.6): it returns `null` without spawning anything — past the project override, on
 * purpose. `null` means pass no model flag at all.
 *
 * The seam's stdout is one JSON object; its stderr carries the reader's warnings. A caller that has
 * already forwarded those through `loadConfig` in the same dispatch passes `notices: false` so the
 * operator sees each warning once.
 */
export function resolveModel(root = process.cwd(), {
  engine, model = null, noModel = false, notices = true,
  python = "python3", timeoutMs = CONFIG_TIMEOUT_MS,
} = {}) {
  if (noModel) return null;
  if (typeof engine !== "string" || engine === "") {
    throw new ConfigBridgeError("resolveModel needs the lane's engine");
  }
  const args = [CONFIG_CLI_PY, "--workspace", root, "resolve-engine", "--engine", engine];
  if (model !== null && model !== undefined) args.push("--model", String(model));
  const result = spawnSync(python, args, { encoding: "utf8", timeout: timeoutMs });

  if (result.error) {
    throw new ConfigBridgeError(`cannot run ${python}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new ConfigBridgeError(
      `config_cli.py resolve-engine exited ${result.status}: ${(result.stderr || "").trim() || "no diagnostic"}`);
  }
  if (notices && result.stderr && result.stderr.trim()) {
    process.stderr.write(result.stderr.endsWith("\n") ? result.stderr : `${result.stderr}\n`);
  }

  let parsed;
  try {
    parsed = JSON.parse(result.stdout);
  } catch (error) {
    throw new ConfigBridgeError(`config_cli.py resolve-engine did not emit JSON: ${error.message}`);
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed) || !("model" in parsed)) {
    throw new ConfigBridgeError("config_cli.py resolve-engine emitted JSON without a model key");
  }
  return parsed.model ?? null;
}
