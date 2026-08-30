#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Stop-gate fixture that BLOCKS with a deliberately hostile reason (vibe-208 / grill P4).
//
// The reason a reviewer returns is external text that reaches Claude in a field Claude reads as the
// gate's own instruction — a two-hop relay, diff -> codex -> reason. Three properties of that text
// have to be pinned, and a short well-behaved string pins none of them:
//
//   * an ANSI escape sequence, which the sanitiser must strip;
//   * C0 control characters, which it must flatten to spaces;
//   * a body LONGER than REASON_CAP, which is what distinguishes "clamp then wrap" from "wrap then
//     clamp". With the wrap first, the closing delimiter is what the clamp cuts off, and a frame
//     whose terminator can be truncated away is not a frame.
//
// After the documented chain — strip ANSI, controls to spaces, slice to the cap, trim — the payload
// is exactly 498 "A"s: the two leading controls become the two spaces the cap counts, and the trim
// then removes them.
//
// The structure below mirrors the other gate fixtures. **This file must be mode 0755** — the runner
// execs the binary directly, so a non-executable fixture is recorded as a FAILED job, the hook falls
// open, and every test depending on it becomes meaningless: one fails for the wrong reason and one
// passes for it. That is exactly what happened while this fixture was written, and the exec bit is
// the reason, not the flush or the argv contract.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

const ANSI = "\u001b[31m";              // an SGR sequence the sanitiser must strip
const CONTROLS = "\u0001\u0007";        // C0 controls it must flatten to spaces
const HOSTILE = ANSI + CONTROLS + "A".repeat(600) + "   ";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, prompt: process.argv.slice(2).at(-1) ?? "", fixture: "gate-hostile-reason" });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_gate_0002" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "item.completed", item: { type: "agent_message", text: `BLOCK: ${HOSTILE}` },
  }) + "\n");
  process.stdout.write(JSON.stringify({ type: "turn.completed", usage: {} }) + "\n");
  process.exit(0);
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
