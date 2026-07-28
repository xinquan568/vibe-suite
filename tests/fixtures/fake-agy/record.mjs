// SPDX-License-Identifier: ISC
// Shared strict argv recorder for the fake-agy fixtures (E1.7 / vibe-17).
//
// Same discipline as fake-codex/record.mjs: a fixture that accepts any argv tests the runner
// against an imaginary CLI. This validates the grammar `agy --help` actually documents, so a
// runner that invents a flag fails here instead of in production.

import { writeFileSync } from "node:fs";

const PRINT_OPTIONS = new Set(["--sandbox", "--print", "-p", "--prompt", "--model",
  "--print-timeout", "--mode", "--add-dir"]);
const VALUED = new Set(["--model", "--print-timeout", "--mode", "--add-dir"]);

export function assertArgvContract(argv) {
  if (argv[0] === "--version") {
    if (argv.length !== 1) { fail("`agy --version` takes no further arguments"); }
    return;
  }
  if (argv[0] === "models") {
    if (argv.length !== 1) { fail("only bare `agy models` is modelled"); }
    return;
  }
  let sawPrompt = false;
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("-")) { sawPrompt = true; continue; }
    if (!PRINT_OPTIONS.has(arg)) fail(`'${arg}' is not accepted by agy`);
    if (VALUED.has(arg)) i += 1;                    // consume its value
  }
  if (!sawPrompt) fail("print mode requires a prompt argument");
}

function fail(message) {
  process.stderr.write(`fake-agy: ${message}\n`);
  process.exit(2);
}

export function writeProbe(extra = {}) {
  const argv = process.argv.slice(2);
  const target = process.env.VIBE_TEST_PROBE;
  if (target) writeFileSync(target, JSON.stringify({ argv, ...extra }, null, 2));
  assertArgvContract(argv);
}
