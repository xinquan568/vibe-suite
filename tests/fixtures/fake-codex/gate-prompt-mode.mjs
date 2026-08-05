#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Stop-gate fixture that records the PUBLISHED prompt file's permissions (vibe-103).
//
// The prompt carries the session diff and the bodies of untracked files, so its mode is a privacy
// property of the shipped hook, not of the write primitive alone. Asserting the primitive's mode
// argument would only prove the caller asked for the right thing; this observes what actually
// landed on disk.
//
// The observation is taken from inside the fixture because that is the one moment the file is
// guaranteed to exist: the hook removes its scratch root after the child returns, so anything
// looking from outside is racing the cleanup rather than reading a fact.

import { readdirSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

function observePrompt() {
  for (const entry of readdirSync(tmpdir())) {
    if (!entry.startsWith("vibe-stop-gate-")) continue;
    const dir = path.join(tmpdir(), entry);
    const prompt = path.join(dir, "prompt.md");
    try {
      return {
        promptMode: (statSync(prompt).mode & 0o777).toString(8),
        scratchMode: (statSync(dir).mode & 0o777).toString(8),
      };
    } catch {
      continue;                       // a root from another run, already cleaned up
    }
  }
  return { promptMode: null, scratchMode: null };
}

async function main() {
  announcePid();
  const stdin = await probeStdin();
  writeProbe({ stdin, fixture: "gate-prompt-mode", ...observePrompt() });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_gate_0103" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "item.completed", item: { type: "agent_message", text: "ALLOW: looks fine" },
  }) + "\n");
  process.stdout.write(JSON.stringify({ type: "turn.completed", usage: {} }) + "\n");
  process.exit(0);
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
