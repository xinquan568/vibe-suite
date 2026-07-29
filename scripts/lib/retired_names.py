#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The retired-namespace predicate (F1.7 / AC-6).

**No retired command name may appear in any runtime string.** cc-suite's W2 defect was legacy names
surviving in user-facing output after a rename; the suite's answer is a rule with a check behind it.

Scope. AC-6's own set is the four merged-from namespaces. `/vibe:` is retired *separately*, by
D1-revised, and is included here because the rule is about runtime strings rather than about AC-6's
provenance. The repository-wide sweep and its CI enforcement belong to **E7.3** — this module is the
predicate that sweep will call, wired now over the surface E2.6 ships.
"""

import re
from pathlib import Path

#: AC-6's four, plus `/vibe:` per D1-revised.
RETIRED = ("/cc-suite:", "/nlpm:", "/grill:", "/codex-toolkit:", "/vibe:")

#: `/vibe-suite:` is the only survivor, and `/vibe:` is a prefix of nothing — but a naive
#: `"/vibe:" in text` would be wrong the moment a namespace like `/vibe:x` gains a longer sibling.
#: Matching the literal including its colon is what keeps `/vibe-suite:` from being flagged.
_PATTERNS = tuple((n, re.compile(re.escape(n))) for n in RETIRED)

#: Every first-party file whose text can reach a user during `/vibe-suite:update`. Listed rather than
#: globbed: a glob would silently widen to files whose strings are not runtime output, and the point
#: of the check is that its surface is known. Both helpers are included because each can print.
UPDATE_SURFACE = (
    "commands/update.md",
    "scripts/update.py",
    "scripts/lib/mcp_pin.py",
    "scripts/lib/boot_probe.mjs",
)


def scan_text(text):
    """Retired namespaces present in a string. The unit both the doctor check and E7.3 build on."""
    return sorted({name for name, pat in _PATTERNS if pat.search(text)})


def scan_files(root, relatives):
    """``[(relative_path, [names])]`` for files carrying a retired name. Read-only."""
    root = Path(root)
    hits = []
    for rel in relatives:
        path = root / rel
        if not path.is_file():
            continue
        found = scan_text(path.read_text(encoding="utf-8", errors="replace"))
        if found:
            hits.append((rel, found))
    return hits


def scan_update_surface(plugin_root):
    return scan_files(plugin_root, UPDATE_SURFACE)
