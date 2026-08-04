#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Advisor lifecycle: ownership, registration content, round-trip, reconciliation (E6.1 / vibe-47).

The acceptance criterion is behavioral — "add→list→remove round-trip leaves both config files
sentinel-clean" — so these tests assert byte identity, not just parsed equality, wherever the
design promises it: always for `.codex/config.toml` (textual fence codec), for canonical
`.mcp.json` pre-images, and for noncanonical pre-images untouched between add and remove (the
pre-image ledger restores the exact bytes). A registration must also be *real*: the entry's
command, args, marker, and environment are pinned exactly, because a round trip of removable
placeholders would pass a naive round-trip test while delivering nothing.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import advisors  # noqa: E402
import bridge  # noqa: E402

PIN = "9.9.9"


def make_ws(mcp=None, toml=None):
    ws = Path(tempfile.mkdtemp(prefix="advisor-ws-"))
    if mcp is not None:
        (ws / ".mcp.json").write_text(mcp, encoding="utf-8")
    if toml is not None:
        (ws / ".codex").mkdir(exist_ok=True)
        (ws / ".codex" / "config.toml").write_text(toml, encoding="utf-8")
    return ws


def defn_text(name="probe_advisor", model="sonnet", extra=""):
    return (
        "---\n"
        "description: |\n"
        f"  Judges {name} things.\n"
        "  <example>\n"
        "  Context: draft done.\n"
        '  user: "Check this?"\n'
        f'  assistant: "I\'ll consult {name}."\n'
        "  </example>\n"
        "  <example>\n"
        "  Context: rename sweep.\n"
        '  user: "Names ok?"\n'
        f'  assistant: "Consulting {name}."\n'
        "  </example>\n"
        f"model: {model}\n"
        "max_turns: 4\n"
        "max_budget_usd: 0.40\n"
        f"{extra}"
        "---\n"
        "\n"
        "Value the smallest true answer.\n"
    )


def add_definition(ws, name="probe_advisor", **kw):
    d = ws / ".vibe-suite" / "agents"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(defn_text(name=name, **kw), encoding="utf-8")


class TestOwnership(unittest.TestCase):
    def test_marker_entry_is_owned_and_enumerated(self):
        doc = {"mcpServers": {
            "my_advisor": {"command": "npx", "_vibe-suite_owned": {"kind": "advisor", "schema": 1}},
            "foreign": {"command": "x"},
        }}
        self.assertTrue(advisors.is_owned_entry(doc["mcpServers"]["my_advisor"]))
        self.assertFalse(advisors.is_owned_entry(doc["mcpServers"]["foreign"]))
        self.assertEqual(bridge.owned_names(doc), ["my_advisor"])

    def test_malformed_marker_is_unowned(self):
        for bad in (1, True, "advisor", {}, {"kind": "advisor"}, {"kind": "other", "schema": 1},
                    {"kind": "advisor", "schema": 2}, None):
            entry = {"command": "npx", "_vibe-suite_owned": bad}
            self.assertFalse(advisors.is_owned_entry(entry), f"marker {bad!r} wrongly owned")
        self.assertEqual(bridge.owned_names(
            {"mcpServers": {"a": {"command": "x", "_vibe-suite_owned": "advisor"}}}), [])

    def test_fenced_toml_name_is_enumerated(self):
        text = ("# user content\n"
                "# >>> vibe-suite:server:my_advisor v1 >>>\n"
                '[mcp_servers.my_advisor]\ncommand = "npx"\n'
                "# <<< vibe-suite:server:my_advisor <<<\n"
                '[mcp_servers.foreign]\ncommand = "y"\n')
        self.assertIn("my_advisor", bridge.toml_owned_names(text))
        self.assertNotIn("foreign", bridge.toml_owned_names(text))

    def test_literal_and_prefix_recognition_unchanged(self):
        doc = {"mcpServers": {"vibe-mcp": {"command": "a"},
                              "vibe-agent:x": {"command": "b"},
                              "plain": {"command": "c"}}}
        self.assertEqual(bridge.owned_names(doc), ["vibe-agent:x", "vibe-mcp"])


class TestDefinitionValidation(unittest.TestCase):
    def test_defaults_applied(self):
        d = advisors.parse_definition(defn_text(), "probe_advisor.md")
        self.assertEqual(d["name"], "probe_advisor")
        self.assertEqual(d["tool_name"], "probe_advisor_consult")
        self.assertEqual(d["allowed_tools"], ["Read", "Grep", "Glob"])
        self.assertEqual(d["max_turns"], 4)
        self.assertEqual(d["prompt_mode"], "append")
        self.assertEqual(d["cwd"], ".")
        self.assertIn("smallest true answer", d["body"])

    def test_versioned_model_id_rejected(self):
        for bad in ("claude-opus-5", "gpt-5", "opus-20250101"):
            with self.assertRaises(advisors.AdvisorError):
                advisors.parse_definition(defn_text(model=bad), "probe_advisor.md")

    def test_invalid_name_and_missing_description_rejected(self):
        with self.assertRaises(advisors.AdvisorError):
            advisors.parse_definition(defn_text(), "bad name!.md")
        no_desc = "---\nmodel: sonnet\n---\nbody\n"
        with self.assertRaises(advisors.AdvisorError):
            advisors.parse_definition(no_desc, "probe_advisor.md")


class TestRegistrationContent(unittest.TestCase):
    def setUp(self):
        self.defn = advisors.parse_definition(defn_text(), "probe_advisor.md")

    def test_json_entry_exact(self):
        entry = advisors.json_entry(self.defn, f"claude-octopus@{PIN}")
        self.assertEqual(entry["command"], "npx")
        self.assertEqual(entry["args"], ["-y", f"claude-octopus@{PIN}"])
        self.assertEqual(entry["_vibe-suite_owned"], {"kind": "advisor", "schema": 1})
        env = entry["env"]
        self.assertEqual(env["CLAUDE_SERVER_NAME"], "probe_advisor")
        self.assertEqual(env["CLAUDE_TOOL_NAME"], "probe_advisor_consult")
        self.assertEqual(env["CLAUDE_MODEL"], "sonnet")
        self.assertEqual(env["CLAUDE_MAX_TURNS"], "4")
        self.assertEqual(env["CLAUDE_MAX_BUDGET_USD"], "0.40")
        self.assertEqual(env["CLAUDE_ALLOWED_TOOLS"], "Read,Grep,Glob")
        self.assertEqual(env["CLAUDE_TIMELINE_DIR"], ".vibe-suite/agents/probe_advisor/timeline")
        self.assertIn("smallest true answer", env["CLAUDE_APPEND_PROMPT"])
        self.assertNotIn("CLAUDE_SYSTEM_PROMPT", env)

    def test_replace_mode_uses_system_prompt(self):
        d = advisors.parse_definition(defn_text(extra="prompt_mode: replace\n"),
                                      "probe_advisor.md")
        env = advisors.json_entry(d, f"claude-octopus@{PIN}")["env"]
        self.assertIn("CLAUDE_SYSTEM_PROMPT", env)
        self.assertNotIn("CLAUDE_APPEND_PROMPT", env)

    def test_toml_block_exact(self):
        body = advisors.toml_body(self.defn, f"claude-octopus@{PIN}")
        self.assertIn('[mcp_servers.probe_advisor]', body)
        self.assertIn('command = "npx"', body)
        self.assertIn(f'args = ["-y", "claude-octopus@{PIN}"]', body)
        self.assertIn("startup_timeout_sec = 60", body)
        self.assertIn("tool_timeout_sec = 900", body)
        self.assertIn('[mcp_servers.probe_advisor.env]', body)
        self.assertIn('CLAUDE_SERVER_NAME = "probe_advisor"', body)


class TestPinResolution(unittest.TestCase):
    def test_explicit_pin_wins_and_is_validated(self):
        self.assertEqual(advisors.resolve_backend("1.2.3"), "claude-octopus@1.2.3")
        for bad in ("latest", "^1.2.0", "1.x", ""):
            with self.assertRaises(advisors.AdvisorError):
                advisors.resolve_backend(bad)

    def test_pending_without_pin_refuses_naming_remedies(self):
        with tempfile.TemporaryDirectory() as td:
            pending = Path(td) / "p.pending"
            pending.write_text("pending\n")
            with self.assertRaises(advisors.AdvisorError) as ctx:
                advisors.resolve_backend(None, pin_file=Path(td) / "p.txt", pending_file=pending)
            msg = str(ctx.exception)
            self.assertIn("--pin", msg)
            self.assertIn("E7.1", msg)

    def test_pin_file_default_path(self):
        with tempfile.TemporaryDirectory() as td:
            pin = Path(td) / "p.txt"
            pin.write_text("2.0.1\n")
            got = advisors.resolve_backend(None, pin_file=pin, pending_file=Path(td) / "nope")
            self.assertEqual(got, "claude-octopus@2.0.1")


CANONICAL_FOREIGN = json.dumps(
    {"mcpServers": {"foreign": {"command": "x"}}}, indent=2, sort_keys=True) + "\n"
NONCANONICAL_FOREIGN = '{ "mcpServers": {\n      "foreign":   {"command":"x"}  } }\n'
TOML_FOREIGN = '# my notes\n[mcp_servers.foreign]\ncommand = "y"\n'


class TestRoundTrip(unittest.TestCase):
    def run_round(self, mcp_seed):
        ws = make_ws(mcp=mcp_seed, toml=TOML_FOREIGN)
        add_definition(ws)
        before_mcp = (ws / ".mcp.json").read_bytes()
        before_toml = (ws / ".codex" / "config.toml").read_bytes()
        advisors.add(ws, "probe_advisor", pin=PIN)
        doc = json.loads((ws / ".mcp.json").read_text())
        self.assertIn("probe_advisor", doc["mcpServers"])
        self.assertTrue((ws / ".vibe-suite" / "agents" / "probe_advisor" / "timeline").is_dir())
        rows = advisors.list_advisors(ws)
        self.assertEqual([r["name"] for r in rows], ["probe_advisor"])
        self.assertEqual(rows[0]["state"], "consistent")
        advisors.remove(ws, "probe_advisor", delete_timeline=True)
        return ws, before_mcp, before_toml

    def test_canonical_json_byte_restored(self):
        ws, before_mcp, before_toml = self.run_round(CANONICAL_FOREIGN)
        self.assertEqual((ws / ".mcp.json").read_bytes(), before_mcp)
        self.assertEqual((ws / ".codex" / "config.toml").read_bytes(), before_toml)
        self.assertFalse((ws / ".vibe-suite" / "agents" / "probe_advisor").exists())

    def test_noncanonical_json_byte_restored_when_untouched(self):
        ws, before_mcp, before_toml = self.run_round(NONCANONICAL_FOREIGN)
        self.assertEqual((ws / ".mcp.json").read_bytes(), before_mcp)
        self.assertEqual((ws / ".codex" / "config.toml").read_bytes(), before_toml)

    def test_edited_between_falls_back_to_canonical_semantics(self):
        ws = make_ws(mcp=NONCANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        doc = json.loads((ws / ".mcp.json").read_text())
        doc["mcpServers"]["user_added"] = {"command": "z"}
        (ws / ".mcp.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        advisors.remove(ws, "probe_advisor", delete_timeline=True)
        after = json.loads((ws / ".mcp.json").read_text())
        self.assertEqual(set(after["mcpServers"]), {"foreign", "user_added"})
        self.assertEqual(bridge.owned_names(after), [])

    def test_keep_timeline(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        tl = ws / ".vibe-suite" / "agents" / "probe_advisor" / "timeline"
        (tl / "note.md").write_text("history\n")
        advisors.remove(ws, "probe_advisor", delete_timeline=False)
        self.assertTrue((tl / "note.md").is_file())


class TestTransactionality(unittest.TestCase):
    def test_second_store_failure_rolls_back_first(self):
        ws = make_ws(mcp=NONCANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        before = (ws / ".mcp.json").read_bytes()
        real = advisors._write_toml_store
        try:
            def boom(*a, **k):
                raise bridge.BridgeError("injected failure")
            advisors._write_toml_store = boom
            with self.assertRaises(bridge.BridgeError):
                advisors.add(ws, "probe_advisor", pin=PIN)
        finally:
            advisors._write_toml_store = real
        self.assertEqual((ws / ".mcp.json").read_bytes(), before)
        self.assertFalse((ws / ".vibe-suite" / "agents" / "probe_advisor" / "timeline").exists())


class TestCollisions(unittest.TestCase):
    def test_foreign_name_refused_nothing_written(self):
        for mcp, toml in (
            (json.dumps({"mcpServers": {"probe_advisor": {"command": "x"}}}) + "\n", TOML_FOREIGN),
            (CANONICAL_FOREIGN, '[mcp_servers.probe_advisor]\ncommand = "y"\n'),
        ):
            ws = make_ws(mcp=mcp, toml=toml)
            add_definition(ws)
            before_mcp = (ws / ".mcp.json").read_bytes()
            before_toml = (ws / ".codex" / "config.toml").read_bytes()
            with self.assertRaises(advisors.AdvisorError):
                advisors.add(ws, "probe_advisor", pin=PIN)
            self.assertEqual((ws / ".mcp.json").read_bytes(), before_mcp)
            self.assertEqual((ws / ".codex" / "config.toml").read_bytes(), before_toml)

    def test_owned_re_add_is_idempotent(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        first = (ws / ".mcp.json").read_bytes()
        advisors.add(ws, "probe_advisor", pin=PIN)
        self.assertEqual((ws / ".mcp.json").read_bytes(), first)

    def test_remove_unowned_or_absent_refuses(self):
        ws = make_ws(mcp=json.dumps(
            {"mcpServers": {"foreign": {"command": "x"}}}) + "\n", toml="")
        with self.assertRaises(advisors.AdvisorError):
            advisors.remove(ws, "foreign")
        with self.assertRaises(advisors.AdvisorError):
            advisors.remove(ws, "absent")


class TestReconcile(unittest.TestCase):
    def test_states_classified_and_converged(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws, name="declared_only")
        report = advisors.reconcile(ws, pin=PIN)
        self.assertEqual(report["declared_only"], "declared-unregistered->registered")
        doc = json.loads((ws / ".mcp.json").read_text())
        self.assertIn("declared_only", doc["mcpServers"])
        toml = (ws / ".codex" / "config.toml").read_text()
        self.assertIn("declared_only", toml)

    def test_orphan_registration_removed_definitions_kept(self):
        entry = {"command": "npx", "args": ["-y", f"claude-octopus@{PIN}"],
                 "_vibe-suite_owned": {"kind": "advisor", "schema": 1}, "env": {}}
        ws = make_ws(mcp=json.dumps({"mcpServers": {"orphan": entry}}, indent=2,
                                    sort_keys=True) + "\n", toml="")
        report = advisors.reconcile(ws, pin=PIN)
        self.assertEqual(report["orphan"], "registered-undeclared->removed")
        self.assertEqual(bridge.owned_names(json.loads((ws / ".mcp.json").read_text())), [])

    def test_half_registered_completed(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws, name="halfway")
        advisors.add(ws, "halfway", pin=PIN)
        toml_path = ws / ".codex" / "config.toml"
        text = toml_path.read_text()
        toml_path.write_text(bridge.text_block_remove(text, "server:halfway"))
        report = advisors.reconcile(ws, pin=PIN)
        self.assertEqual(report["halfway"], "half-registered->registered")
        self.assertIn("halfway", toml_path.read_text())

    def test_add_and_remove_route_through_reconcile(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        calls = []
        real = advisors.reconcile
        try:
            def spy(*a, **k):
                calls.append("reconcile")
                return real(*a, **k)
            advisors.reconcile = spy
            advisors.add(ws, "probe_advisor", pin=PIN)
            advisors.remove(ws, "probe_advisor", delete_timeline=True)
        finally:
            advisors.reconcile = real
        self.assertGreaterEqual(len(calls), 2)


class TestTimelineDeletion(unittest.TestCase):
    def test_populated_nested_timeline_removed(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        tl = ws / ".vibe-suite" / "agents" / "probe_advisor" / "timeline"
        (tl / "deep" / "deeper").mkdir(parents=True)
        (tl / "deep" / "deeper" / "log.md").write_text("x")
        advisors.remove(ws, "probe_advisor", delete_timeline=True)
        self.assertFalse(tl.exists())

    def test_outward_symlink_target_survives(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        victim = ws / "precious.txt"
        victim.write_text("keep me\n")
        tl = ws / ".vibe-suite" / "agents" / "probe_advisor" / "timeline"
        (tl / "escape").symlink_to(victim)
        advisors.remove(ws, "probe_advisor", delete_timeline=True)
        self.assertTrue(victim.is_file())
        self.assertFalse(tl.exists())

    def test_non_timeline_rel_refused(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        with self.assertRaises(bridge.BridgeError):
            advisors.delete_timeline(ws, "../../etc")
        with self.assertRaises(bridge.BridgeError):
            advisors.delete_timeline(ws, "not_a_name/..")


class TestGitignoreRule(unittest.TestCase):
    def test_ignore_block_added_and_user_content_preserved(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        (ws / ".gitignore").write_text("node_modules/\n")
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        text = (ws / ".gitignore").read_text()
        self.assertIn("node_modules/", text)
        self.assertIn(".vibe-suite/agents/*/timeline/", text)
        self.assertIn("vibe-suite:advisor-ignore", text)


class TestTemplates(unittest.TestCase):
    TUPLES = {
        "north_star_advisor": ("opus", 5, "0.50"),
        "security_skeptic": ("opus", 5, "0.50"),
        "deletion_advocate": ("sonnet", 5, "0.30"),
        "clarity_reviewer": ("sonnet", 3, "0.20"),
        "simplicity_advocate": ("sonnet", 3, "0.20"),
        "documentation_critic": ("sonnet", 3, "0.20"),
    }
    VALUES = {
        "north_star_advisor": "priorit",
        "security_skeptic": "adversar",
        "deletion_advocate": "delet",
        "clarity_reviewer": "readab",
        "simplicity_advocate": "simpl",
        "documentation_critic": "document",
    }

    def test_six_presets_pinned_to_contract(self):
        tdir = REPO_ROOT / "templates" / "advisors"
        found = sorted(p.stem for p in tdir.glob("*.md"))
        self.assertEqual(found, sorted(self.TUPLES))
        for name, (tier, turns, budget) in self.TUPLES.items():
            text = (tdir / f"{name}.md").read_text(encoding="utf-8")
            d = advisors.parse_definition(text, f"{name}.md")
            self.assertEqual(d["model"], tier, name)
            self.assertEqual(d["max_turns"], turns, name)
            self.assertEqual(f'{d["max_budget_usd"]}', budget, name)
            self.assertEqual(d["allowed_tools"], ["Read", "Grep", "Glob"], name)
            self.assertEqual(text.count("<example>"), 2, name)
            self.assertIn(self.VALUES[name], d["body"].lower(), name)


if __name__ == "__main__":
    unittest.main()


class TestOwnershipExactness(unittest.TestCase):
    """W1 (Step-8 F4): the marker predicate is type-exact — coercible equals are not claims."""

    def test_bool_and_float_schema_are_unowned(self):
        for bad in ({"kind": "advisor", "schema": True}, {"kind": "advisor", "schema": 1.0},
                    {"kind": "advisor", "schema": 1, "extra": 1}, {"schema": 1},
                    {"kind": b"advisor", "schema": 1}):
            entry = {"command": "npx", "_vibe-suite_owned": bad}
            self.assertFalse(advisors.is_owned_entry(entry), f"marker {bad!r} wrongly owned")

    def test_exact_marker_still_owned(self):
        self.assertTrue(advisors.is_owned_entry(
            {"command": "npx", "_vibe-suite_owned": {"kind": "advisor", "schema": 1}}))


class TestTransactionJournal(unittest.TestCase):
    """W2/W3 (Step-8 F1, F2, F3): write-ahead journal, provenance modes, hard-crash recovery."""

    def ws_with(self, mcp, toml=TOML_FOREIGN, mcp_mode=None):
        ws = make_ws(mcp=mcp, toml=toml)
        if mcp_mode is not None:
            os.chmod(ws / ".mcp.json", mcp_mode)
        add_definition(ws)
        return ws

    def test_initialized_workspace_bytes_restored(self):
        vibe_mcp = json.dumps({"mcpServers": {
            "foreign": {"command": "x"},
            "vibe-mcp": {"command": "vibe-suite", "args": []}}}, indent=2, sort_keys=True) + "\n"
        ws = self.ws_with(vibe_mcp)
        before = (ws / ".mcp.json").read_bytes()
        advisors.add(ws, "probe_advisor", pin=PIN)
        advisors.remove(ws, "probe_advisor", delete_timeline=True)
        self.assertEqual((ws / ".mcp.json").read_bytes(), before,
                         "vibe-mcp presence must not block advisor-scoped byte restoration")
        ledger = ws / ".vibe-suite-state" / "advisor-preimages.json"
        self.assertFalse(ledger.exists(), "ledger entry must clear when the last advisor goes")

    def test_journal_and_ledger_modes_derive_from_source(self):
        ws = self.ws_with(NONCANONICAL_FOREIGN, mcp_mode=0o400)
        state = ws / ".vibe-suite-state"
        state.mkdir(exist_ok=True)
        os.chmod(state, 0o755)
        advisors.add(ws, "probe_advisor", pin=PIN)
        self.assertEqual(os.stat(state).st_mode & 0o777, 0o700,
                         "state dir must be tightened before secret-bearing writes")
        ledger = state / "advisor-preimages.json"
        self.assertTrue(ledger.is_file())
        self.assertEqual(os.stat(ledger).st_mode & 0o777, 0o400,
                         "ledger mode must AND source modes with 0600")

    def _crash_cli(self, ws, fail_after, *args):
        env = dict(os.environ, VIBE_ADVISOR_FAIL_AFTER=fail_after)
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "advisor_cli.py"),
             "--workspace", str(ws), *args],
            capture_output=True, text=True, env=env)

    def test_crash_after_json_write_recovers_on_rerun(self):
        ws = self.ws_with(NONCANONICAL_FOREIGN)
        before = (ws / ".mcp.json").read_bytes()
        r = self._crash_cli(ws, "json", "add", "probe_advisor", "--pin", PIN)
        self.assertEqual(r.returncode, 9, r.stderr)
        self.assertTrue((ws / ".vibe-suite-state" / "advisor-txn.json").is_file(),
                        "journal must survive the crash")
        r2 = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "advisor_cli.py"),
             "--workspace", str(ws), "add", "probe_advisor", "--pin", PIN],
            capture_output=True, text=True)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertFalse((ws / ".vibe-suite-state" / "advisor-txn.json").exists())
        doc = json.loads((ws / ".mcp.json").read_text())
        self.assertIn("probe_advisor", doc["mcpServers"])
        advisors.remove(ws, "probe_advisor", delete_timeline=True)
        self.assertEqual((ws / ".mcp.json").read_bytes(), before)

    def test_remove_crash_after_both_stores_rolls_forward(self):
        ws = self.ws_with(NONCANONICAL_FOREIGN)
        advisors.add(ws, "probe_advisor", pin=PIN)
        r = self._crash_cli(ws, "toml", "remove", "probe_advisor", "--delete-timeline")
        self.assertEqual(r.returncode, 9, r.stderr)
        r_list = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "advisor_cli.py"),
             "--workspace", str(ws), "list"], capture_output=True, text=True)
        self.assertEqual(r_list.returncode, 0, r_list.stderr)
        self.assertIn("pending recovery", r_list.stdout,
                      "list must report, never heal, a pending transaction")
        self.assertTrue((ws / ".vibe-suite-state" / "advisor-txn.json").is_file(),
                        "list must leave the journal untouched")
        r2 = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "advisor_cli.py"),
             "--workspace", str(ws), "reconcile"], capture_output=True, text=True)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertFalse((ws / ".vibe-suite" / "agents" / "probe_advisor.md").exists(),
                         "roll-forward must complete the definition deletion")
        self.assertFalse((ws / ".vibe-suite-state" / "advisor-txn.json").exists())
        self.assertEqual(bridge.owned_names(json.loads((ws / ".mcp.json").read_text())), [])

    def test_remove_crash_mid_timeline_walk_completes_on_retry(self):
        ws = self.ws_with(NONCANONICAL_FOREIGN)
        advisors.add(ws, "probe_advisor", pin=PIN)
        tl = ws / ".vibe-suite" / "agents" / "probe_advisor" / "timeline"
        (tl / "deep").mkdir()
        (tl / "deep" / "log.md").write_text("x")
        r = self._crash_cli(ws, "timeline-partial", "remove", "probe_advisor",
                            "--delete-timeline")
        self.assertEqual(r.returncode, 9, r.stderr)
        r2 = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "advisor_cli.py"),
             "--workspace", str(ws), "remove", "probe_advisor", "--delete-timeline"],
            capture_output=True, text=True)
        self.assertEqual(r2.returncode, 0, r2.stderr + r2.stdout)
        self.assertFalse((ws / ".vibe-suite" / "agents" / "probe_advisor").exists())

    def test_pending_add_leaves_zero_residue(self):
        ws = make_ws(mcp=NONCANONICAL_FOREIGN, toml=TOML_FOREIGN)
        before_mcp = (ws / ".mcp.json").read_bytes()
        before_toml = (ws / ".codex" / "config.toml").read_bytes()
        with tempfile.TemporaryDirectory() as td:
            pending = Path(td) / "p.pending"
            pending.write_text("pending\n")
            with self.assertRaises(advisors.AdvisorError):
                advisors.add(ws, "north_star_advisor", plugin_root=REPO_ROOT,
                             pin_file=Path(td) / "p.txt", pending_file=pending)
        self.assertEqual((ws / ".mcp.json").read_bytes(), before_mcp)
        self.assertEqual((ws / ".codex" / "config.toml").read_bytes(), before_toml)
        self.assertFalse((ws / ".vibe-suite" / "agents").exists(), "no definition residue")
        self.assertFalse((ws / ".vibe-suite-state").exists(), "no ledger/journal residue")
        self.assertFalse((ws / ".gitignore").exists(), "no ignore-block residue")


class TestSafeCreationAndPrivacy(unittest.TestCase):
    """W4/W5 (Step-8 F6, F7): descriptor-safe creation; ignore-block retention."""

    def test_symlinked_agents_dir_refused(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        outside = Path(tempfile.mkdtemp(prefix="advisor-outside-"))
        (ws / ".vibe-suite").mkdir()
        (ws / ".vibe-suite" / "agents").symlink_to(outside)
        with self.assertRaises((advisors.AdvisorError, bridge.BridgeError)):
            advisors.add(ws, "north_star_advisor", plugin_root=REPO_ROOT, pin=PIN)
        self.assertEqual(list(outside.iterdir()), [], "nothing may be created outside the ws")

    def test_symlinked_advisor_dir_refused(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        outside = Path(tempfile.mkdtemp(prefix="advisor-outside2-"))
        (ws / ".vibe-suite" / "agents" / "probe_advisor").symlink_to(outside)
        with self.assertRaises((advisors.AdvisorError, bridge.BridgeError)):
            advisors.add(ws, "probe_advisor", pin=PIN)
        self.assertEqual(list(outside.iterdir()), [])

    def test_keep_timeline_retains_ignore_block(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        advisors.remove(ws, "probe_advisor", delete_timeline=False)
        text = (ws / ".gitignore").read_text()
        self.assertIn(".vibe-suite/agents/*/timeline/", text,
                      "kept history must stay private-by-default")

    def test_delete_timeline_of_last_advisor_removes_block(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        advisors.remove(ws, "probe_advisor", delete_timeline=True)
        gi = ws / ".gitignore"
        if gi.exists():
            self.assertNotIn("advisor-ignore", gi.read_text())


class TestTargetAndClassification(unittest.TestCase):
    """W6 (Step-8 F8, F9): resolution order; per-store content classification."""

    def _ws(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        return ws

    def test_explicit_pin_upgrades_existing_target(self):
        ws = self._ws()
        advisors.add(ws, "probe_advisor", pin="8.0.0")
        doc = json.loads((ws / ".mcp.json").read_text())
        self.assertEqual(doc["mcpServers"]["probe_advisor"]["args"],
                         ["-y", "claude-octopus@8.0.0"])

    def test_floating_registered_target_refused(self):
        ws = self._ws()
        doc = json.loads((ws / ".mcp.json").read_text())
        doc["mcpServers"]["probe_advisor"]["args"] = ["-y", "claude-octopus@latest"]
        (ws / ".mcp.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        with tempfile.TemporaryDirectory() as td:
            pending = Path(td) / "p.pending"
            pending.write_text("pending\n")
            with self.assertRaises(advisors.AdvisorError) as ctx:
                advisors.reconcile(ws, pin_file=Path(td) / "p.txt", pending_file=pending)
            self.assertIn("latest", str(ctx.exception))

    def test_stale_content_per_store(self):
        ws = self._ws()
        # JSON-only staleness
        doc = json.loads((ws / ".mcp.json").read_text())
        doc["mcpServers"]["probe_advisor"]["env"]["CLAUDE_MAX_TURNS"] = "99"
        (ws / ".mcp.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        rows = {r["name"]: r for r in advisors.list_advisors(ws)}
        self.assertEqual(rows["probe_advisor"]["state"], "stale-registered")
        advisors.reconcile(ws, pin=PIN)
        rows = {r["name"]: r for r in advisors.list_advisors(ws)}
        self.assertEqual(rows["probe_advisor"]["state"], "consistent")
        # TOML-only staleness
        toml_path = ws / ".codex" / "config.toml"
        toml_path.write_text(toml_path.read_text().replace(
            'CLAUDE_MAX_TURNS = "4"', 'CLAUDE_MAX_TURNS = "77"'))
        rows = {r["name"]: r for r in advisors.list_advisors(ws)}
        self.assertEqual(rows["probe_advisor"]["state"], "stale-registered")

    def test_edited_definition_flips_state(self):
        ws = self._ws()
        add_definition(ws, extra="effort: high\n")
        rows = {r["name"]: r for r in advisors.list_advisors(ws)}
        self.assertEqual(rows["probe_advisor"]["state"], "stale-registered")

    def test_disagreeing_targets_invalid(self):
        ws = self._ws()
        toml_path = ws / ".codex" / "config.toml"
        toml_path.write_text(toml_path.read_text().replace(
            f'claude-octopus@{PIN}', 'claude-octopus@7.7.7'))
        with tempfile.TemporaryDirectory() as td:
            pending = Path(td) / "p.pending"
            pending.write_text("pending\n")
            rows = {r["name"]: r for r in advisors.list_advisors(
                ws, pin_file=Path(td) / "p.txt", pending_file=pending)}
            self.assertEqual(rows["probe_advisor"]["state"], "invalid-registration")


class TestCollisionParsing(unittest.TestCase):
    """W7 (Step-8 F10): quote-aware, whitespace-tolerant TOML collision detection."""

    def test_single_quoted_and_whitespace_headers_collide(self):
        for header in ("[mcp_servers.'probe_advisor']", "[ mcp_servers . probe_advisor ]",
                       '[mcp_servers."probe_advisor"]'):
            ws = make_ws(mcp=CANONICAL_FOREIGN,
                         toml=f'{header}\ncommand = "y"\n')
            add_definition(ws)
            before = (ws / ".codex" / "config.toml").read_bytes()
            with self.assertRaises(advisors.AdvisorError, msg=header):
                advisors.add(ws, "probe_advisor", pin=PIN)
            self.assertEqual((ws / ".codex" / "config.toml").read_bytes(), before, header)

    def test_both_store_collision_refused(self):
        ws = make_ws(
            mcp=json.dumps({"mcpServers": {"probe_advisor": {"command": "x"}}}) + "\n",
            toml='[mcp_servers.probe_advisor]\ncommand = "y"\n')
        add_definition(ws)
        with self.assertRaises(advisors.AdvisorError):
            advisors.add(ws, "probe_advisor", pin=PIN)


class TestFieldValidation(unittest.TestCase):
    """W7 (Step-8 F11): the documented field types are enforced."""

    def test_inline_description_rejected(self):
        text = "---\ndescription: inline scalar\nmodel: sonnet\n---\n\nbody\n"
        with self.assertRaises(advisors.AdvisorError):
            advisors.parse_definition(text, "probe_advisor.md")

    def test_scalar_list_fields_rejected(self):
        with self.assertRaises(advisors.AdvisorError):
            advisors.parse_definition(defn_text(extra="allowed_tools: Read\n"),
                                      "probe_advisor.md")

    def test_bad_tool_name_and_caps_rejected(self):
        for extra in ("tool_name: not a name!\n", "max_turns: 0\n", "max_turns: -3\n",
                      "max_budget_usd: -1\n", "max_budget_usd: free\n"):
            with self.assertRaises(advisors.AdvisorError, msg=extra):
                advisors.parse_definition(defn_text(extra=extra), "probe_advisor.md")

    def test_valid_fields_accepted(self):
        d = advisors.parse_definition(
            defn_text(extra="tool_name: probe_check\nmax_budget_usd: 1.25\n"),
            "probe_advisor.md")
        self.assertEqual(d["tool_name"], "probe_check")
        self.assertEqual(d["max_budget_usd"], "1.25")


class TestCrashMatrix(unittest.TestCase):
    """W2 frozen matrix — every boundary, subprocess os._exit, converging re-run."""

    CLI = [sys.executable, str(REPO_ROOT / "scripts" / "advisor_cli.py")]

    def ws(self):
        ws = make_ws(mcp=NONCANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        return ws

    def run_cli(self, ws, *args, fail_after=None):
        env = dict(os.environ)
        if fail_after:
            env["VIBE_ADVISOR_FAIL_AFTER"] = fail_after
        return subprocess.run([*self.CLI, "--workspace", str(ws), *args],
                              capture_output=True, text=True, env=env)

    def assert_converges(self, ws, before_mcp):
        r = self.run_cli(ws, "reconcile", "--pin", PIN)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((ws / ".vibe-suite-state" / "advisor-txn.json").exists())

    def test_add_crash_at_journal_and_toml(self):
        for point in ("journal", "toml"):
            ws = self.ws()
            before = (ws / ".mcp.json").read_bytes()
            r = self.run_cli(ws, "add", "probe_advisor", "--pin", PIN, fail_after=point)
            self.assertEqual(r.returncode, 9, (point, r.stderr))
            self.assert_converges(ws, before)
            doc = json.loads((ws / ".mcp.json").read_text())
            # journal-point rollback leaves nothing; toml-point rollback also rolls back,
            # and the converging reconcile re-registers from the surviving definition.
            self.assertIn("probe_advisor", doc["mcpServers"])

    def test_stale_update_crash_at_json_and_toml(self):
        for point in ("json", "toml"):
            ws = self.ws()
            self.run_cli(ws, "add", "probe_advisor", "--pin", PIN)
            add_definition(ws, extra="effort: high\n")
            r = self.run_cli(ws, "reconcile", fail_after=point)
            self.assertEqual(r.returncode, 9, (point, r.stderr))
            r2 = self.run_cli(ws, "reconcile")
            self.assertEqual(r2.returncode, 0, r2.stderr)
            doc = json.loads((ws / ".mcp.json").read_text())
            self.assertEqual(doc["mcpServers"]["probe_advisor"]["env"].get("CLAUDE_EFFORT"),
                             "high", point)

    def test_remove_crash_at_json_definition_and_timeline(self):
        for point in ("json", "definition", "timeline"):
            ws = self.ws()
            self.run_cli(ws, "add", "probe_advisor", "--pin", PIN)
            before = (ws / ".mcp.json").read_bytes()
            r = self.run_cli(ws, "remove", "probe_advisor", "--delete-timeline",
                             fail_after=point)
            self.assertEqual(r.returncode, 9, (point, r.stderr))
            r2 = self.run_cli(ws, "reconcile")
            self.assertEqual(r2.returncode, 0, (point, r2.stderr))
            self.assertFalse((ws / ".vibe-suite" / "agents" / "probe_advisor").exists(), point)
            self.assertEqual(
                bridge.owned_names(json.loads((ws / ".mcp.json").read_text())), [], point)

    def test_journal_file_mode_derives_from_source(self):
        ws = self.ws()
        os.chmod(ws / ".mcp.json", 0o400)
        r = self.run_cli(ws, "add", "probe_advisor", "--pin", PIN, fail_after="json")
        self.assertEqual(r.returncode, 9, r.stderr)
        txn = ws / ".vibe-suite-state" / "advisor-txn.json"
        self.assertEqual(os.stat(txn).st_mode & 0o777, 0o400)


class TestJournalValidation(unittest.TestCase):
    """New-finding 1: recovery is fail-closed — an unvalidatable journal drives nothing."""

    def test_bad_journals_refused_without_mutation(self):
        for bad in ({"schema": 99},
                    {"schema": 1, "intent": "explode"},
                    {"schema": 1, "intent": "remove", "remove_name": "x",
                     "delete_timeline": True, "pre_images": {}, "post_images": {}},
                    {"schema": 1, "intent": "remove", "remove_name": "../evil",
                     "delete_timeline": True,
                     "pre_images": {".mcp.json": None, ".codex/config.toml": None},
                     "post_images": {".mcp.json": "e30=", ".codex/config.toml": ""}}):
            ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
            add_definition(ws)
            state = ws / ".vibe-suite-state"
            state.mkdir()
            (state / "advisor-txn.json").write_text(json.dumps(bad))
            before = (ws / ".mcp.json").read_bytes()
            with self.assertRaises(advisors.AdvisorError, msg=bad):
                advisors.recover(ws)
            self.assertEqual((ws / ".mcp.json").read_bytes(), before)
            self.assertTrue((ws / ".vibe-suite" / "agents" / "probe_advisor.md").is_file())
            self.assertTrue((state / "advisor-txn.json").is_file(),
                            "a refused journal must be left for inspection")


class TestRemoveSafety(unittest.TestCase):
    """F5 residue: a refusal caused by another advisor leaves the target fully intact."""

    def test_other_advisors_invalid_registration_preserves_target(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        add_definition(ws, name="other_advisor")
        advisors.add(ws, "other_advisor", pin=PIN)
        toml_path = ws / ".codex" / "config.toml"
        block = bridge._block_re("server:other_advisor", "#", "").search(
            toml_path.read_text()).group(0)
        toml_path.write_text(toml_path.read_text().replace(
            block, block.replace(f'claude-octopus@{PIN}', 'evil-package@1.2.3')))
        with tempfile.TemporaryDirectory() as td:
            pending = Path(td) / "p.pending"
            pending.write_text("pending\n")
            with self.assertRaises(advisors.AdvisorError):
                advisors.remove(ws, "probe_advisor", delete_timeline=True,
                                pin_file=Path(td) / "p.txt", pending_file=pending)
        self.assertTrue((ws / ".vibe-suite" / "agents" / "probe_advisor.md").is_file())
        self.assertTrue((ws / ".vibe-suite" / "agents" / "probe_advisor" / "timeline").is_dir())
        self.assertIn("probe_advisor",
                      json.loads((ws / ".mcp.json").read_text())["mcpServers"])


class TestRootAndTargetSafety(unittest.TestCase):
    def test_symlinked_workspace_root_refused(self):
        real = Path(tempfile.mkdtemp(prefix="advisor-real-"))
        link = Path(tempfile.mkdtemp(prefix="advisor-link-")) / "ws"
        link.symlink_to(real)
        with self.assertRaises(bridge.BridgeError):
            advisors.reconcile(link)

    def test_foreign_toml_target_is_invalid_not_half(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        advisors.add(ws, "probe_advisor", pin=PIN)
        # Strip the JSON side so the TOML block is the only registration, then poison it.
        doc = json.loads((ws / ".mcp.json").read_text())
        del doc["mcpServers"]["probe_advisor"]
        (ws / ".mcp.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        toml_path = ws / ".codex" / "config.toml"
        toml_path.write_text(toml_path.read_text().replace(
            f'claude-octopus@{PIN}', 'evil-package@1.2.3'))
        with tempfile.TemporaryDirectory() as td:
            pending = Path(td) / "p.pending"
            pending.write_text("pending\n")
            rows = {r["name"]: r for r in advisors.list_advisors(
                ws, pin_file=Path(td) / "p.txt", pending_file=pending)}
            self.assertEqual(rows["probe_advisor"]["state"], "invalid-registration")

    def test_pending_declared_unregistered_is_presence_only(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        with tempfile.TemporaryDirectory() as td:
            pending = Path(td) / "p.pending"
            pending.write_text("pending\n")
            rows = {r["name"]: r for r in advisors.list_advisors(
                ws, pin_file=Path(td) / "p.txt", pending_file=pending)}
            self.assertEqual(rows["probe_advisor"]["state"], "declared-unregistered")


class TestScalarFieldKinds(unittest.TestCase):
    """F11 residue: scalar-required fields reject list and block forms."""

    def test_list_valued_scalars_rejected(self):
        for extra in ("cwd: [docs]\n", "model: [sonnet]\n", "max_turns: [5]\n",
                      "tool_name: [x]\n"):
            with self.assertRaises(advisors.AdvisorError, msg=extra):
                advisors.parse_definition(defn_text(extra=extra), "probe_advisor.md")
