#!/usr/bin/env node
// SPDX-License-Identifier: ISC
//
// Boot-and-handshake probe for the pinned reverse-MCP server (E2.6 / vibe-23, F1.7).
//
// Spawns the pinned package exactly as `.codex/config.toml` will, sends one MCP `initialize` over
// newline-delimited JSON-RPC, and requires a well-formed `serverInfo` back. Semver compliance does
// not imply the package boots on this machine, which is the whole point of verifying a pin.
//
// Two things this does NOT do, both deliberate:
//   * it does not kill only the direct child — `npx` spawns descendants, so the process *group* is
//     signalled and its disappearance confirmed before returning;
//   * it does not echo third-party output verbatim — a hostile package could otherwise inject a
//     retired command name into our stream and fail the suite's own AC-6 check.
//
// Seam: VIBE_SUITE_MCP_BIN replaces `npx` for tests. The fake must *respond*; a probe test that
// passes only where the real binary is absent measures the environment, not the code.
//
// Usage: node boot_probe.mjs <package@version>     Exit: 0 ok, 1 handshake failed/timed out.

import { spawn } from "node:child_process";

const target = process.argv[2];
const TIMEOUT_MS = Number(process.env.VIBE_SUITE_PROBE_TIMEOUT_MS) || 30000;
const BIN = process.env.VIBE_SUITE_MCP_BIN || "npx";

if (!target) {
  console.error("boot_probe: a package@version argument is required");
  process.exit(1);
}

const INIT = JSON.stringify({
  jsonrpc: "2.0", id: 1, method: "initialize",
  params: {
    protocolVersion: "2024-11-05", capabilities: {},
    clientInfo: { name: "vibe-suite-boot-probe", version: "0.0.1" },
  },
});

// `detached` puts the child in its own process group so descendants are reachable.
const child = spawn(BIN, ["-y", target], { stdio: ["pipe", "pipe", "pipe"], detached: true });

let buf = "", errBuf = "", settled = false;

/** Third-party text, bounded and stripped of anything that could pose as our own output. */
function sanitize(text) {
  return String(text).replace(/[\x00-\x1f\x7f]/g, " ").replace(/\s+/g, " ").trim().slice(0, 200);
}

/** Signal the group, then confirm it is gone rather than assuming SIGTERM was honoured. */
async function reap() {
  const pgid = child.pid;
  if (pgid === undefined) return;
  const gone = () => { try { process.kill(-pgid, 0); return false; } catch { return true; } };
  try { process.kill(-pgid, "SIGTERM"); } catch { return; }
  for (let i = 0; i < 40; i++) {
    if (gone()) return;
    await new Promise((r) => setTimeout(r, 25));
  }
  try { process.kill(-pgid, "SIGKILL"); } catch { /* already gone */ }
  for (let i = 0; i < 40; i++) {
    if (gone()) return;
    await new Promise((r) => setTimeout(r, 25));
  }
}

async function finish(code, message) {
  if (settled) return;
  settled = true;
  clearTimeout(timer);
  await reap();
  if (code === 0) {
    console.log(`ok ${message}`);
  } else {
    console.error(`failed ${message}`);
    if (errBuf.trim()) console.error(`  server output: ${sanitize(errBuf)}`);
  }
  process.exit(code);
}

const timer = setTimeout(
  () => finish(1, `${target} did not respond within ${TIMEOUT_MS}ms`), TIMEOUT_MS);

child.on("error", (err) => finish(1, `could not spawn ${BIN}: ${sanitize(err.message)}`));
child.on("exit", (code, signal) =>
  finish(1, `${target} exited before responding (code=${code}, signal=${signal})`));
child.stderr.on("data", (c) => { errBuf = (errBuf + c.toString()).slice(-4096); });

child.stdout.on("data", (chunk) => {
  buf += chunk.toString();
  let nl;
  while ((nl = buf.indexOf("\n")) !== -1) {
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch { continue; }  // banner lines are not an error
    if (msg.jsonrpc !== "2.0" || msg.id !== 1) continue;
    if (msg.result?.serverInfo?.name) {
      const { name, version } = msg.result.serverInfo;
      finish(0, `${target} booted; server reports ${sanitize(name)}@${sanitize(version ?? "?")}`);
      return;
    }
    if (msg.error) {
      finish(1, `${target} returned an MCP error: ${sanitize(JSON.stringify(msg.error))}`);
      return;
    }
  }
});

child.stdin.write(INIT + "\n");
