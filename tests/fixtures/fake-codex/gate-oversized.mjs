#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Stop-gate fixture whose CONTROLLING verdict is far too large to retain (vibe-274), preceded by an
// earlier verdict that says the opposite. This is the case settled decision 8 exists for: when the
// controlling event cannot be kept, the capture must contain NO parseable completed agent_message,
// so the gate takes its declared no-verdict route instead of surfacing the stale earlier answer.

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, prompt: process.argv.slice(2).at(-1) ?? "", fixture: "gate-oversized" });

  const w = (o) => process.stdout.write(JSON.stringify(o) + "\n");
  w({ type: "thread.started", thread_id: "thread_gate_0274b" });
  // The stale earlier verdict. If it ever reaches the gate, the gate blocks on a superseded answer.
  w({ type: "item.completed", item: { type: "agent_message", text: "BLOCK: superseded by a later review" } });
  for (let i = 0; i < 400; i += 1) {
    w({ type: "item.completed", item: { type: "reasoning", text: "z".repeat(160) } });
  }
  // The controlling verdict, deliberately larger than the whole budget on its own.
  w({ type: "item.completed", item: { type: "agent_message", text: "ALLOW: " + "y".repeat(200_000) } });
  // A nullish-text message AFTER it. This is small enough to retain, so it is what separates the
  // two predicates: it is a completed agent_message (I3 forbids it surviving) but not a controlling
  // one (decision 4 says it displaces no verdict). A suppression boundary drawn with the narrower
  // predicate keeps it.
  w({ type: "item.completed", item: { type: "agent_message", text: null } });
  w({ type: "turn.completed", usage: {} });
  // NOT process.exit(0): this fixture writes more than a pipe buffer, and exit() does not
  // wait for stdout to drain — the stream would be cut mid-line and the runner would see a
  // truncated capture rather than an over-budget one.
  process.exitCode = 0;
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
