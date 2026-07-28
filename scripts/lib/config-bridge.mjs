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

export class ConfigBridgeError extends Error {}

/**
 * Read resolved project configuration for `root`.
 *
 * `config.py:main()` takes the root **positionally** — `root = argv[-1] if not argv[-1]
 * .startswith("-") else "."` — so the path must be the final argument, and the shape it returns is
 * validated here rather than trusted.
 */
export function loadConfig(root = process.cwd(), { python = "python3" } = {}) {
  const result = spawnSync(python, [CONFIG_PY, root], { encoding: "utf8" });

  if (result.error) {
    throw new ConfigBridgeError(`cannot run ${python}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new ConfigBridgeError(
      `config.py exited ${result.status}: ${(result.stderr || "").trim() || "no diagnostic"}`);
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
 * The engine-relevant defaults, with the caller's explicit choices winning.
 *
 * Priority is the suite's documented order: user > `.vibe-suite.md` > tool default. No model default
 * is ever synthesised (P9) — an unset model means the Codex CLI runs whatever it is configured with.
 */
export function resolveDefaults(config, overrides = {}) {
  return {
    sandbox: overrides.sandbox ?? config.sandbox ?? "read-only",
    effort: overrides.effort ?? config.effort ?? "medium",
    model: overrides.model ?? config.model_overrides?.codex ?? null,
  };
}
