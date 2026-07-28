#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// The /vibe-suite:preflight CLI (E1.3 / vibe-13, implements F1.5).
//
// Canonical call (from `commands/preflight.md`, via ${CLAUDE_PLUGIN_ROOT}):
//
//   node scripts/preflight-cli.mjs [--json]
//
// Prints the engine availability matrix — codex probed live, agy a pending slot until E1.7 — and
// exits: 0 — every probed lane available and no probe degraded to `unknown`; 1 — a probed lane
// unavailable or degraded; 2 — usage. The matrix always prints; the exit code is for scripts.
//
// **Node floor: 18.** No top-level await — `main()` is invoked, not awaited at module scope.

import { buildMatrix, probeAgy, probeCodex } from "./lib/preflight.mjs";
import { agyGate } from "./lib/agy-gate.mjs";

class UsageError extends Error {}

function parseArgs(argv) {
  const options = { json: false };
  for (const arg of argv) {
    if (arg === "--json") options.json = true;
    else throw new UsageError(`unknown argument: ${arg} (preflight takes only --json)`);
  }
  return options;
}

function cell(value) {
  return value === null ? "-" : String(value);
}

function renderText(rows) {
  const lines = [];
  const header = ["ENGINE", "AVAILABLE", "VERSION", "AUTH", "SMOKE", "MODELS", "DETAIL"];
  const table = rows.map((row) => [
    row.engine,
    row.available === null ? "pending" : row.available ? "available" : "unavailable",
    cell(row.version),
    cell(row.auth),
    cell(row.smoke),
    row.models.status === "pending" ? "pending"
      : `${row.models.status} (${row.models.slugs.length})`,
    row.detail,
  ]);
  const widths = header.map((h, i) => Math.max(h.length, ...table.map((r) => r[i].length)));
  const pad = (text, width) => text + " ".repeat(Math.max(0, width - text.length));
  lines.push(header.map((h, i) => pad(h, widths[i])).join("  "));
  for (const row of table) lines.push(row.map((c, i) => pad(c, widths[i])).join("  "));
  for (const row of rows) {
    if (row.models.slugs.length > 0) {
      lines.push("");
      lines.push(`${row.engine} models (${row.models.status}): ${row.models.slugs.join(", ")}`);
    }
  }
  return lines.join("\n");
}

function exitCodeFor(rows) {
  for (const row of rows) {
    if (row.available === null) continue;              // pending never counts against
    if (row.available !== true) return 1;
    // A degraded probe is one that FAILED TO LEARN something knowable. `auth: "unknown"` means that
    // for codex, which exposes its auth mode — but agy exposes none, so `unknown` there is the
    // truthful terminal answer, not a failure to look. Treating them alike would fail a preflight
    // over a fact that cannot be discovered.
    if (row.version === "unknown") return 1;
    if (row.engine !== "agy" && row.auth === "unknown") return 1;
  }
  return 0;
}

async function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    if (!(error instanceof UsageError)) throw error;
    process.stderr.write(`preflight: ${error.message}\n`);
    return 2;
  }

  // Both lanes are probed for real now (E1.7 closed E1.3's deferred agy assertion). The gate is
  // passed in so the agy row can distinguish "unverified" (pending) from "unavailable" (broken).
  const gate = agyGate();
  const rows = buildMatrix([await probeCodex(), await probeAgy({ gate })]);
  if (options.json) {
    process.stdout.write(JSON.stringify({ engines: rows }, null, 2) + "\n");
  } else {
    process.stdout.write(renderText(rows) + "\n");
  }
  return exitCodeFor(rows);
}

main()
  .then((code) => { process.exitCode = code; })
  .catch((error) => {
    process.stderr.write(`preflight: ${error?.stack ?? error}\n`);
    process.exitCode = 1;
  });
