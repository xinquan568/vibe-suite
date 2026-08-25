// SPDX-License-Identifier: ISC
// Shared throwaway-directory helper for the Node test suite (vibe-198 / M32).
//
// 19 of the `tests/node/*.test.mjs` files called `mkdtempSync(path.join(tmpdir(), "…"))` and never
// remove the directory, leaking ~600 dirs into $TMPDIR per full run. `tmpWorkspace()` creates the
// same kind of directory and registers it for synchronous removal at process exit, so a test that
// throws still leaves nothing behind. Removal is idempotent: a directory a test already deleted is
// skipped, never re-raised.
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const created = new Set();
let hooked = false;

function ensureHook() {
  if (hooked) return;
  hooked = true;
  process.on("exit", () => {
    for (const dir of created) {
      try {
        rmSync(dir, { recursive: true, force: true });
      } catch {
        /* already gone — force:true swallows ENOENT, this guards anything else */
      }
    }
  });
}

// Create a `$TMPDIR/<prefix>XXXXXX` directory removed when the process exits. Returns its path.
export function tmpWorkspace(prefix = "vibe-test-") {
  ensureHook();
  const dir = mkdtempSync(path.join(tmpdir(), prefix));
  created.add(dir);
  return dir;
}

// Explicit early removal for a tmpWorkspace() dir a test wants gone before exit (idempotent).
export function dispose(dir) {
  created.delete(dir);
  try {
    rmSync(dir, { recursive: true, force: true });
  } catch {
    /* already gone */
  }
}
