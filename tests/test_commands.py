#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Command-artifact contracts (E1.4 / vibe-14).

Two contracts live here. The **delegate content contract** pins `commands/delegate.md` to the
frozen design — the canonical tagged blocks its own tests execute, the full argument surface, the
resolution ladder's every branch, the provenance wording, the two-mode verification, the fallback
binding, and the confirm-before-danger ordering. It was written before the artifact existed (TDD
RED) and keeps the artifact honest afterwards.

The **AC-6 retired-name scan** guards the D1 renames mechanically: a retired source-project command
name (`implement`, cc-suite's name for what became `/vibe-suite:delegate`) must not appear as a
command reference in any shipped runtime-reachable artifact. The scan matches reference shapes —
`/vibe-suite:implement`, `:implement`, backticked `implement` — never the bare substring, because
"implementation" is legitimate English.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DELEGATE = REPO_ROOT / "commands" / "delegate.md"

# Every shipped runtime-reachable area. tests/ (fixtures + the source manifests that record
# cc-suite's real command names as data) and docs/ are deliberately outside the scan.
SHIPPED_AREAS = ("commands", "agents", "skills", "scripts", "bin", "hooks", "templates",
                 "auditor", "codex", "schemas", ".claude-plugin")

RETIRED_COMMAND_PATTERNS = (
    re.compile(r"/vibe-suite:implement\b"),
    re.compile(r"(?<![\w-]):implement\b"),
    re.compile(r"`implement`"),
)


def _read(path):
    return path.read_text(encoding="utf-8")


class TestDelegateContentContract(unittest.TestCase):
    def setUp(self):
        self.assertTrue(DELEGATE.is_file(),
                        "commands/delegate.md does not exist — the vibe-14 deliverable is missing")
        self.text = _read(DELEGATE)

    def test_frontmatter_and_full_argument_surface(self):
        self.assertTrue(self.text.startswith("---\n"))
        head = self.text[4:self.text.find("\n---", 4)]
        self.assertIn("description:", head)
        self.assertIn("argument-hint:", head)
        for token in ("<plan-file-or-inline>", "--background", "--wait",
                      "--sandbox", "--effort", "--model"):
            self.assertIn(token, head, f"argument-hint must expose the full surface: {token}")

    def test_canonical_blocks_present_and_shaped(self):
        for tag in ("<!-- canonical-dispatch -->", "<!-- canonical-verify -->"):
            self.assertIn(tag, self.text, f"missing tagged block: {tag}")
        dispatch = self.text.split("<!-- canonical-dispatch -->", 1)[1]
        dispatch = dispatch.split("```", 2)[1]
        self.assertIn("--kind delegate", dispatch)
        # Resolved values travel as DATA via env parameters, never textual substitution; the
        # conditional confirmation flag is part of the canonical template, not an ad-hoc addition.
        self.assertIn('--sandbox "${DELEGATE_SANDBOX:-workspace-write}"', dispatch)
        self.assertIn('${DELEGATE_EFFORT:+--effort "$DELEGATE_EFFORT"}', dispatch)
        self.assertIn('${DELEGATE_MODEL:+--model "$DELEGATE_MODEL"}', dispatch)
        self.assertIn("${DELEGATE_CONFIRM_DANGER:+--confirm-danger}", dispatch)
        self.assertIn('"$(cat', dispatch, "the argv-safe quoted transport is the contract")
        self.assertNotIn("--resume", self.text, "delegate never uses resume inheritance")
        verify = self.text.split("<!-- canonical-verify -->", 1)[1].split("```", 2)[1]
        self.assertIn("set -euo pipefail", verify,
                      "every verification command's failure must fail the block")

    def _section(self, start, end):
        return self.text.split(start, 1)[1].split(end, 1)[0]

    def test_resolution_ladder_every_branch(self):
        resolve = self._section("## 2. Resolve", "## 3.")
        # sandbox: user precedence, then delegate's own default — both halves asserted.
        self.assertIn("explicit `--sandbox` flag from the\n  operator, else **`workspace-write`**",
                      resolve)
        self.assertIn("not consulted", resolve.lower(),
                      "unattributable config values must not change privileges")
        self.assertIn("reachable **only** via the operator's explicit `--sandbox` flag", resolve)
        self.assertIn("only after an explicit yes add `--confirm-danger`", resolve)
        # model/effort: BOTH halves of pass-through-or-omit.
        self.assertIn("flags through verbatim", resolve)
        self.assertIn("omit both flags", resolve)

    def test_verification_branches_on_status(self):
        verify_section = self._section("## 5. Verify", "## 6.")
        self.assertIn("verification is only for `completed`", verify_section)
        self.assertIn("`failed` and `timed_out` route to", verify_section)
        self.assertIn("report\nit and stop", verify_section.replace("**", ""),
                      "cancelled is the operator's stop — never the manual fallback")
        self.assertIn("automatic", verify_section, "wait-mode verification is automatic")
        self.assertIn("apply the same `status` branching", verify_section,
                      "background mode branches on status too")
        self.assertIn("operator-invoked", verify_section)

    def test_fallback_covers_no_terminal_event_and_no_header_case(self):
        fallback = self.text.split("## 6.", 1)[1]
        self.assertIn("no terminal event", fallback)
        self.assertIn("**without** the header", fallback)

    def test_confirmation_precedes_danger_flag(self):
        ask = self.text.find("AskUserQuestion")
        confirm = self.text.find("--confirm-danger")
        self.assertGreater(ask, -1, "the in-session confirmation must be named")
        self.assertGreater(confirm, -1, "the runner's danger flag must be named")
        self.assertLess(ask, confirm,
                        "confirmation must be described BEFORE the flag it authorises")

    def test_provenance_never_inferred(self):
        self.assertIn("Provenance:", self.text)
        self.assertIn("unknown — supplied by the operator", self.text)

    def test_two_mode_verification(self):
        self.assertIn("<!-- canonical-verify -->", self.text)
        self.assertIn("operator-invoked", self.text,
                      "background verification is a documented follow-up, not a claimed reawakening")

    def test_fallback_binding(self):
        self.assertIn("unreachable", self.text.lower())
        self.assertIn("/vibe-suite:preflight", self.text)
        self.assertIn("manual fallback", self.text.lower())


class TestRetiredCommandNames(unittest.TestCase):
    """AC-6: retired source-project command names never re-enter shipped artifacts."""

    def test_no_retired_implement_references(self):
        offenders = []
        for area in SHIPPED_AREAS:
            root = REPO_ROOT / area
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix in {".png", ".gif"}:
                    continue
                try:
                    text = _read(path)
                except (UnicodeDecodeError, OSError):
                    continue
                for pattern in RETIRED_COMMAND_PATTERNS:
                    if pattern.search(text):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: {pattern.pattern}")
        self.assertEqual(offenders, [],
                         "retired `implement` command references in shipped artifacts:\n"
                         + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
