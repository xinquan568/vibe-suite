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

import { readdirSync, readFileSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { announcePid, probeStdin, writeProbe } from "./record.mjs";

/**
 * The prompt file of **this** invocation, identified by a per-run nonce and required to be unique.
 *
 * Two weaker oracles were tried and both could name the wrong file. Taking the first readable
 * `vibe-stop-gate-*` root let a stale or concurrent root answer. Comparing the whole prompt text was
 * no better: this suite builds the same repository state every run, so two invocations produce
 * byte-identical prompts, and the byte cap collapses any two that share a prefix.
 *
 * So the caller seeds a nonce that appears in the *filename* of the changed file — which lands near
 * the top of the prompt, inside `git status --porcelain`, where truncation cannot reach it — and
 * ambiguity is an error rather than a first match, the same rule the loop-bounds extractor learned.
 */
function observePrompt(nonce) {
  const found = [];
  for (const entry of readdirSync(tmpdir())) {
    if (!entry.startsWith("vibe-stop-gate-")) continue;
    const dir = path.join(tmpdir(), entry);
    const prompt = path.join(dir, "prompt.md");
    try {
      if (!readFileSync(prompt, "utf8").includes(nonce)) continue;
      found.push({
        promptMode: (statSync(prompt).mode & 0o777).toString(8),
        scratchMode: (statSync(dir).mode & 0o777).toString(8),
      });
    } catch {
      continue;                       // a root from another run, already cleaned up
    }
  }
  if (found.length !== 1) {
    return { promptMode: null, scratchMode: null, promptMatched: false, candidates: found.length };
  }
  return { ...found[0], promptMatched: true, candidates: 1 };
}

async function main() {
  announcePid();
  const stdin = await probeStdin();
  const nonce = process.env.VIBE_TEST_PROMPT_NONCE ?? "";
  writeProbe({ stdin, fixture: "gate-prompt-mode", ...observePrompt(nonce) });

  process.stdout.write(JSON.stringify({ type: "thread.started", thread_id: "thread_gate_0103" }) + "\n");
  process.stdout.write(JSON.stringify({
    type: "item.completed", item: { type: "agent_message", text: "ALLOW: looks fine" },
  }) + "\n");
  process.stdout.write(JSON.stringify({ type: "turn.completed", usage: {} }) + "\n");
  process.exit(0);
}

main().catch((error) => { process.stderr.write(String(error?.stack ?? error) + "\n"); process.exit(1); });
