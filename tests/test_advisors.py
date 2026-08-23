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

import hashlib
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
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
        # E7.1: the real tree now ships a default pin, so classification against the
        # default paths would compare content to it. The round-trip contract under test is
        # byte restoration, so the listing pins the same target the add used.
        rows = advisors.list_advisors(ws, pin=PIN)
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
        # vibe-185: a flag-less reconcile HOLDS a definition nobody registered; `add` registers it.
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws, name="declared_only")
        report = advisors.reconcile(ws, pin=PIN)
        self.assertEqual(report["declared_only"],
                         "declared-unregistered (not registered; register with advisor add declared_only)")
        self.assertNotIn("declared_only", json.loads((ws / ".mcp.json").read_text())["mcpServers"])
        report = advisors.add(ws, "declared_only", pin=PIN)
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

    def test_stale_explicit_registration_retargets_to_shipped_default(self):
        # E7.1 (vibe-53) characterization: the pending→shipped transition's advisor consequence.
        # An advisor registered at an older explicit pin, reconciled with no pin argument against
        # a shipped pin file, converges both stores to the shipped default.
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws, name="veteran")
        advisors.add(ws, "veteran", pin="1.0.0")
        with tempfile.TemporaryDirectory() as td:
            shipped = Path(td) / "pin.txt"
            shipped.write_text("2.0.0\n")
            report = advisors.reconcile(ws, pin_file=shipped,
                                        pending_file=Path(td) / "absent.pending")
        self.assertEqual(report["veteran"], "stale-registered->registered")
        doc = json.loads((ws / ".mcp.json").read_text())
        self.assertIn("claude-octopus@2.0.0", json.dumps(doc["mcpServers"]["veteran"]))
        toml = (ws / ".codex" / "config.toml").read_text()
        self.assertIn("claude-octopus@2.0.0", toml)
        self.assertNotIn("claude-octopus@1.0.0", toml)

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


class TestDangerGate(unittest.TestCase):
    """vibe-184 / grill H1a: a definition is repository content. `permission_mode` dontAsk/auto/
    bypassPermissions and a cwd/additional_dirs entry outside the workspace register only after an
    explicit, recorded `--confirm-danger`; the default path and in-workspace directories are
    unchanged; the refusal names the field and the flag and writes nothing; the acceptance rides the
    transaction (journal prior/post maps, ledger); recovery restores or installs it exactly, and an
    in-process rollback restores it too."""

    EMPTY_MCP = '{"mcpServers": {}}\n'
    MODES = ("bypassPermissions", "dontAsk", "auto")

    def _ws(self, extra):
        ws = make_ws(mcp=self.EMPTY_MCP, toml="")
        add_definition(ws, extra=extra)
        return ws

    def _cli(self, ws, *args, fail_after=None):
        env = dict(os.environ)
        if fail_after:
            env["VIBE_ADVISOR_FAIL_AFTER"] = fail_after
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "advisor_cli.py"), "--workspace", str(ws), *args],
            capture_output=True, text=True, env=env)

    def _ledger(self, ws):
        return json.loads((ws / ".vibe-suite-state" / "advisor-preimages.json").read_text())

    # --- refusal: every dangerous mode, through the library and through both CLI entry points ---

    def test_every_dangerous_mode_is_refused_by_add_naming_field_and_flag_and_writes_nothing(self):
        # vibe-185: the gate guards the WRITE — `add <name>` — and a flag-less reconcile, which
        # registers nothing it was not told to, discloses the danger instead of refusing.
        for mode in self.MODES:
            with self.subTest(mode=mode):
                ws = self._ws(f"permission_mode: {mode}\n")
                before_mcp = (ws / ".mcp.json").read_bytes()
                with self.assertRaises(advisors.AdvisorError) as cm:
                    advisors.add(ws, "probe_advisor", pin=PIN)
                msg = str(cm.exception)
                self.assertIn("permission_mode", msg)
                self.assertIn(mode, msg)
                self.assertIn("--confirm-danger", msg, "the refusal names the flag")
                self.assertEqual((ws / ".mcp.json").read_bytes(), before_mcp, "nothing written on refusal")
                self.assertFalse((ws / ".codex" / "config.toml").read_text(encoding="utf-8").strip())
                self.assertFalse((ws / ".vibe-suite-state").exists(), "no state dir, no ledger, no journal on refusal")
                held = advisors.reconcile(ws, pin=PIN)
                self.assertIn("dangerous: permission_mode", held["probe_advisor"], "a flag-less reconcile discloses")
                self.assertIn("--confirm-danger", held["probe_advisor"])
                self.assertEqual((ws / ".mcp.json").read_bytes(), before_mcp, "and writes nothing")
                self.assertFalse((ws / ".vibe-suite-state").exists())

    def test_cli_add_refuses_every_dangerous_mode_with_exit_two_and_cli_reconcile_discloses(self):
        for mode in self.MODES:
            for op in ("add", "add --all"):
                with self.subTest(mode=mode, op=op):
                    ws = self._ws(f"permission_mode: {mode}\n")
                    args = ["add", "probe_advisor", "--pin", PIN] if op == "add" else ["add", "--all", "--pin", PIN]
                    r = self._cli(ws, *args)
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn(f"permission_mode '{mode}'", r.stderr)
                    self.assertIn("--confirm-danger", r.stderr)
                    self.assertEqual(json.loads((ws / ".mcp.json").read_text())["mcpServers"], {}, "nothing registered")
            with self.subTest(mode=mode, op="reconcile"):
                ws = self._ws(f"permission_mode: {mode}\n")
                r = self._cli(ws, "reconcile", "--pin", PIN)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("dangerous: permission_mode", r.stdout)
                self.assertEqual(json.loads((ws / ".mcp.json").read_text())["mcpServers"], {}, "nothing registered")

    # --- acceptance: recorded, sha-bound, durable; CLI reconcile accepts too ---

    def test_the_flag_accepts_registers_and_records_the_acceptance_bound_to_the_definition(self):
        ws = self._ws("permission_mode: bypassPermissions\n")
        r = self._cli(ws, "add", "probe_advisor", "--pin", PIN, "--confirm-danger")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        entry = json.loads((ws / ".mcp.json").read_text())["mcpServers"]["probe_advisor"]
        self.assertEqual(entry["env"]["CLAUDE_PERMISSION_MODE"], "bypassPermissions", "accepted → registered as declared")
        acc = self._ledger(ws)[advisors.ACCEPTANCES_KEY]["probe_advisor"]
        defn = advisors.parse_definition((ws / ".vibe-suite" / "agents" / "probe_advisor.md").read_text(), "probe_advisor.md")
        self.assertEqual(acc["definition_sha256"], advisors.definition_sha(defn), "the acceptance is bound to this exact definition")
        self.assertEqual(acc["fields"], [{"field": "permission_mode", "value": "bypassPermissions",
                                          "reason": "runs the advisor without permission prompts"}])
        self.assertRegex(acc["accepted_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(os.stat(ws / ".vibe-suite-state" / "advisor-preimages.json").st_mode & 0o777, 0o600,
                         "the ledger stays private")

    def test_cli_add_all_with_the_flag_accepts_and_records_and_cli_reconcile_has_no_flag(self):
        ws = self._ws("permission_mode: dontAsk\n")
        self.assertEqual(self._cli(ws, "reconcile", "--pin", PIN, "--confirm-danger").returncode, 2,
                         "vibe-185: acceptance rides the explicit add; reconcile takes no --confirm-danger")
        r = self._cli(ws, "add", "--all", "--pin", PIN, "--confirm-danger")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("probe_advisor: declared-unregistered->registered", r.stdout)
        self.assertEqual(json.loads((ws / ".mcp.json").read_text())["mcpServers"]["probe_advisor"]["env"]["CLAUDE_PERMISSION_MODE"], "dontAsk")
        self.assertIn("probe_advisor", self._ledger(ws)[advisors.ACCEPTANCES_KEY])
        # and a second flag-less CLI reconcile converges on the recorded acceptance
        r2 = self._cli(ws, "reconcile", "--pin", PIN)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("probe_advisor: consistent", r2.stdout)

    def test_an_accepted_definition_converges_flag_less_until_it_changes(self):
        ws = self._ws("permission_mode: auto\n")
        advisors.add(ws, "probe_advisor", pin=PIN, confirm_danger=True)
        # init / repair / update call reconcile with no flag: the recorded acceptance carries it.
        self.assertEqual(advisors.reconcile(ws, pin=PIN), {"probe_advisor": "consistent"})
        # A changed definition (different sha) is a new decision: held by the flag-less reconcile,
        # and the re-confirming add needs the flag again.
        add_definition(ws, extra="permission_mode: auto\nmax_turns: 9\n")
        held = advisors.reconcile(ws, pin=PIN)
        self.assertIn("changed-unconfirmed", held["probe_advisor"])
        with self.assertRaises(advisors.AdvisorError) as cm:
            advisors.add(ws, "probe_advisor", pin=PIN)
        self.assertIn("--confirm-danger", str(cm.exception))
        entry = json.loads((ws / ".mcp.json").read_text())["mcpServers"]["probe_advisor"]
        self.assertEqual(entry["env"]["CLAUDE_MAX_TURNS"], "4", "the registered content is untouched by the refusal")
        advisors.add(ws, "probe_advisor", pin=PIN, confirm_danger=True)
        entry = json.loads((ws / ".mcp.json").read_text())["mcpServers"]["probe_advisor"]
        self.assertEqual(entry["env"]["CLAUDE_MAX_TURNS"], "9", "re-confirmed: re-accepted and re-registered")

    # --- containment: cwd and each additional_dirs entry; tilde / escaping relative / in-workspace absolute / outside absolute ---

    def test_cwd_and_additional_dirs_outside_the_workspace_are_refused_inside_is_not(self):
        ws0 = make_ws(mcp=self.EMPTY_MCP, toml="")
        inside_abs = str(ws0 / "docs")
        outside = {
            ("cwd", "~"): "cwd: '~'\n",
            ("cwd", "../outside"): "cwd: ../outside\n",
            ("cwd", "/etc"): "cwd: /etc\n",
            ("additional_dirs", "~"): "additional_dirs: ['~']\n",
            ("additional_dirs", "../escape"): "additional_dirs: [docs, ../escape]\n",
            ("additional_dirs", "/etc"): "additional_dirs: [/etc]\n",
        }
        for (field, value), extra in outside.items():
            with self.subTest(field=field, value=value):
                ws = self._ws(extra)
                with self.assertRaises(advisors.AdvisorError) as cm:
                    advisors.add(ws, "probe_advisor", pin=PIN)
                msg = str(cm.exception)
                self.assertIn(field, msg)
                self.assertIn(repr(value), msg)
                self.assertIn("outside the workspace", msg)
                self.assertIn("--confirm-danger", msg)
                self.assertEqual(json.loads((ws / ".mcp.json").read_text())["mcpServers"], {})
        # In-workspace values need no flag and record no acceptance: relative, ./relative, and an
        # absolute path INSIDE the workspace (absolute is not dangerous by itself).
        add_definition(ws0, extra=f"cwd: docs\nadditional_dirs: [src, ./tests, {inside_abs}]\n")
        self.assertEqual(advisors.add(ws0, "probe_advisor", pin=PIN), {"probe_advisor": "declared-unregistered->registered"})
        self.assertNotIn(advisors.ACCEPTANCES_KEY, self._ledger(ws0), "no acceptance recorded for a safe definition")
        ws1 = make_ws(mcp=self.EMPTY_MCP, toml="")
        add_definition(ws1, extra=f"cwd: {ws1 / 'docs'}\n")                 # absolute, but INSIDE this workspace
        self.assertEqual(advisors.add(ws1, "probe_advisor", pin=PIN), {"probe_advisor": "declared-unregistered->registered"},
                         "an absolute cwd inside the workspace is not dangerous")

    # --- the flag itself; the unchanged default path ---

    def test_the_flag_is_refused_when_nothing_is_dangerous(self):
        ws = self._ws("")
        with self.assertRaises(advisors.AdvisorError) as cm:
            advisors.add(ws, "probe_advisor", pin=PIN, confirm_danger=True)
        self.assertIn("only meaningful", str(cm.exception))
        self.assertFalse((ws / ".vibe-suite-state").exists(), "nothing written")
        for args in (["add", "probe_advisor", "--pin", PIN, "--confirm-danger"], ["add", "--all", "--pin", PIN, "--confirm-danger"]):
            with self.subTest(args=" ".join(args[:2])):
                r = self._cli(ws, *args)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("only meaningful", r.stderr)

    def test_default_acceptEdits_plan_register_through_add_without_the_flag(self):
        for mode in ("default", "acceptEdits", "plan"):
            with self.subTest(mode=mode):
                ws = self._ws(f"permission_mode: {mode}\n")
                self.assertEqual(advisors.add(ws, "probe_advisor", pin=PIN), {"probe_advisor": "declared-unregistered->registered"})
                env = json.loads((ws / ".mcp.json").read_text())["mcpServers"]["probe_advisor"]["env"]
                self.assertEqual(env.get("CLAUDE_PERMISSION_MODE"), None if mode == "default" else mode)

    # --- remove: acceptance dropped; siblings held, never blocking, never registered ---

    def test_remove_drops_the_acceptance_and_the_ledger_clears_with_the_last_advisor(self):
        ws = self._ws("permission_mode: dontAsk\n")
        advisors.add(ws, "probe_advisor", pin=PIN, confirm_danger=True)
        ledger = ws / ".vibe-suite-state" / "advisor-preimages.json"
        self.assertIn("probe_advisor", self._ledger(ws)[advisors.ACCEPTANCES_KEY])
        report = advisors.remove(ws, "probe_advisor", delete_timeline=True, pin=PIN)
        self.assertEqual(report["probe_advisor"], "removed")
        self.assertNotIn("_warning", report, "removing a dangerous ACCEPTED target needs no flag and converges cleanly")
        self.assertFalse(ledger.exists(), "ledger entry must clear when the last advisor goes — acceptance included")

    def test_removing_one_advisor_neither_blocks_on_nor_registers_a_dangerous_unaccepted_sibling(self):
        ws = make_ws(mcp=self.EMPTY_MCP, toml="")
        add_definition(ws, name="safe_one")
        advisors.add(ws, "safe_one", pin=PIN)
        add_definition(ws, name="risky_one", extra="permission_mode: bypassPermissions\n")   # declared, never accepted
        with self.assertRaises(advisors.AdvisorError):
            advisors.add(ws, "risky_one", pin=PIN)                        # the write-time gate refuses risky_one
        report = advisors.remove(ws, "safe_one", delete_timeline=True, pin=PIN)
        self.assertEqual(report["safe_one"], "removed")
        self.assertIn("danger-unaccepted", report["risky_one"])
        self.assertIn("--confirm-danger", report["risky_one"])
        self.assertNotIn("_warning", report, "vibe-185: the post-removal convergence holds the sibling and reports it — no refusal to warn about")
        servers = json.loads((ws / ".mcp.json").read_text())["mcpServers"]
        self.assertNotIn("safe_one", servers)
        self.assertNotIn("risky_one", servers, "a removal authorises nothing: the dangerous sibling stays unregistered")
        self.assertFalse((ws / ".vibe-suite" / "agents" / "safe_one.md").exists())
        report2 = advisors.remove(ws, "risky_one", delete_timeline=True, pin=PIN)
        self.assertEqual(report2["risky_one"], "removed")
        self.assertNotIn("_warning", report2)

    def test_a_held_sibling_in_a_colliding_state_does_not_block_removal_and_is_left_alone(self):
        # The sibling's name is squatted by an UNOWNED server in .mcp.json (a collision that would
        # refuse a reconcile); it is dangerous and unaccepted, so remove must neither refuse on its
        # account nor touch the squatter.
        ws = make_ws(mcp=json.dumps({"mcpServers": {"risky_one": {"command": "foreign"}}}) + "\n", toml="")
        add_definition(ws, name="safe_one")
        advisors.add(ws, "safe_one", pin=PIN)
        add_definition(ws, name="risky_one", extra="permission_mode: auto\n")
        with self.assertRaises(advisors.AdvisorError):
            advisors.add(ws, "risky_one", pin=PIN, confirm_danger=True)  # the collision refuses the write
        report = advisors.remove(ws, "safe_one", delete_timeline=True, pin=PIN)
        self.assertEqual(report["safe_one"], "removed")
        self.assertIn("danger-unaccepted", report["risky_one"])
        servers = json.loads((ws / ".mcp.json").read_text())["mcpServers"]
        self.assertEqual(servers.get("risky_one"), {"command": "foreign"}, "the squatter is untouched")
        self.assertNotIn("safe_one", servers)

    # --- the transaction: journal maps, fail-closed validation, crash recovery ---

    def test_the_journal_carries_prior_and_post_acceptance_maps_and_a_rolled_back_apply_persists_none(self):
        ws = self._ws("permission_mode: bypassPermissions\n")
        r = self._cli(ws, "add", "probe_advisor", "--pin", PIN, "--confirm-danger", fail_after="json")
        self.assertEqual(r.returncode, 9, "the crash seam fired")
        txn_path = ws / ".vibe-suite-state" / "advisor-txn.json"
        txn = json.loads(txn_path.read_text())
        member = txn[advisors.ACCEPTANCES_KEY]
        self.assertEqual(set(member), {"prior", "post"})
        self.assertEqual(member["prior"], {}, "no acceptance existed before this transaction")
        defn = advisors.parse_definition((ws / ".vibe-suite" / "agents" / "probe_advisor.md").read_text(), "probe_advisor.md")
        self.assertEqual(member["post"]["probe_advisor"]["definition_sha256"], advisors.definition_sha(defn),
                         "the journaled acceptance is sha-bound")
        self.assertEqual(os.stat(txn_path).st_mode & 0o777, 0o600, "the journal keeps the provenance mode")
        self.assertEqual(advisors.recover(ws), {"intent": "apply", "remove_name": None})
        self.assertFalse(txn_path.exists())
        with self.assertRaises(advisors.AdvisorError):
            advisors.add(ws, "probe_advisor", pin=PIN)                    # a rolled-back apply authorised nothing

    def test_an_accepted_apply_that_crashes_after_the_ledger_write_is_rolled_back_acceptance_included(self):
        ws = self._ws("permission_mode: bypassPermissions\n")
        r = self._cli(ws, "add", "probe_advisor", "--pin", PIN, "--confirm-danger", fail_after="baseline")
        self.assertEqual(r.returncode, 9, "the crash seam fired AFTER the stores and the ledger were written")
        ledger = ws / ".vibe-suite-state" / "advisor-preimages.json"
        self.assertIn("probe_advisor", (json.loads(ledger.read_text()).get(advisors.ACCEPTANCES_KEY) or {}),
                      "precondition: the crash left the acceptance on disk")
        self.assertEqual(advisors.recover(ws), {"intent": "apply", "remove_name": None})
        self.assertEqual(json.loads((ws / ".mcp.json").read_text())["mcpServers"], {}, "the registration rolled back")
        self.assertFalse(ledger.exists() and advisors.ACCEPTANCES_KEY in json.loads(ledger.read_text()),
                         "the acceptance rolled back with it: the prior map was empty")
        with self.assertRaises(advisors.AdvisorError):
            advisors.add(ws, "probe_advisor", pin=PIN)                    # and a flag-less add refuses again

    def test_removing_an_accepted_advisor_that_crashes_rolls_forward_acceptance_dropped(self):
        for point in ("json", "toml"):
            with self.subTest(point=point):
                ws = self._ws("permission_mode: dontAsk\n")
                self.assertEqual(self._cli(ws, "add", "probe_advisor", "--pin", PIN, "--confirm-danger").returncode, 0)
                r = self._cli(ws, "remove", "probe_advisor", "--delete-timeline", fail_after=point)
                self.assertEqual(r.returncode, 9, (point, r.stderr))
                r2 = self._cli(ws, "reconcile", "--pin", PIN)               # recovery rolls the removal forward
                self.assertEqual(r2.returncode, 0, (point, r2.stderr))
                self.assertEqual(json.loads((ws / ".mcp.json").read_text())["mcpServers"], {}, point)
                self.assertFalse((ws / ".vibe-suite" / "agents" / "probe_advisor.md").exists(), point)
                self.assertFalse((ws / ".vibe-suite-state" / "advisor-txn.json").exists(), point)
                ledger = ws / ".vibe-suite-state" / "advisor-preimages.json"
                self.assertFalse(ledger.exists() and advisors.ACCEPTANCES_KEY in json.loads(ledger.read_text()),
                                 f"{point}: the stale acceptance is gone after roll-forward")

    # --- the ordinary-exception rollback (no crash): the acceptance map rides it too ---

    def test_an_accepted_apply_whose_ignore_block_raises_after_the_ledger_write_rolls_back_acceptance_included(self):
        ws = self._ws("permission_mode: bypassPermissions\n")
        mcp_before = (ws / ".mcp.json").read_bytes()
        toml_before = (ws / ".codex" / "config.toml").read_bytes()
        with mock.patch.object(advisors, "_ignore_block", side_effect=RuntimeError("injected after the ledger write")):
            with self.assertRaises(RuntimeError):
                advisors.add(ws, "probe_advisor", pin=PIN, confirm_danger=True)
        self.assertEqual((ws / ".mcp.json").read_bytes(), mcp_before, "the registration rolled back in-process")
        self.assertEqual((ws / ".codex" / "config.toml").read_bytes(), toml_before)
        self.assertFalse((ws / ".vibe-suite-state" / "advisor-txn.json").exists(), "the journal is gone")
        ledger = ws / ".vibe-suite-state" / "advisor-preimages.json"
        self.assertFalse(ledger.exists() and advisors.ACCEPTANCES_KEY in json.loads(ledger.read_text()),
                         "the acceptance rolled back with the registration: the prior map was empty")
        with self.assertRaises(advisors.AdvisorError):
            advisors.add(ws, "probe_advisor", pin=PIN)                    # a rolled-back apply authorised nothing
        self.assertEqual(advisors.add(ws, "probe_advisor", pin=PIN, confirm_danger=True),
                         {"probe_advisor": "declared-unregistered->registered"}, "and the workspace is healthy")

    def test_removing_an_accepted_advisor_whose_ignore_block_raises_rolls_back_acceptance_kept(self):
        ws = self._ws("permission_mode: dontAsk\n")
        advisors.add(ws, "probe_advisor", pin=PIN, confirm_danger=True)
        accepted = self._ledger(ws)[advisors.ACCEPTANCES_KEY]
        mcp_before = (ws / ".mcp.json").read_bytes()
        toml_before = (ws / ".codex" / "config.toml").read_bytes()
        with mock.patch.object(advisors, "_ignore_block", side_effect=RuntimeError("injected after the ledger write")):
            with self.assertRaises(RuntimeError):
                advisors.remove(ws, "probe_advisor", delete_timeline=True, pin=PIN)
        self.assertEqual((ws / ".mcp.json").read_bytes(), mcp_before, "the registration is intact")
        self.assertEqual((ws / ".codex" / "config.toml").read_bytes(), toml_before)
        self.assertTrue((ws / ".vibe-suite" / "agents" / "probe_advisor.md").exists(), "the definition was not deleted")
        self.assertFalse((ws / ".vibe-suite-state" / "advisor-txn.json").exists(), "the journal is gone")
        self.assertEqual(self._ledger(ws).get(advisors.ACCEPTANCES_KEY), accepted,
                         "the prior acceptance survived the rolled-back removal")
        self.assertEqual(advisors.reconcile(ws, pin=PIN), {"probe_advisor": "consistent"},
                         "flag-less convergence still holds: the authorisation was kept")
        report = advisors.remove(ws, "probe_advisor", delete_timeline=True, pin=PIN)
        self.assertEqual(report["probe_advisor"], "removed", "and the removal completes afterwards")
        self.assertFalse((ws / ".vibe-suite-state" / "advisor-preimages.json").exists(), "ledger cleared with the last advisor")

    def test_a_dangerous_advisor_named_mode_commits_converges_and_removes(self):
        # the ledger's file mode is derived from its provenance images; the acceptance map is keyed by
        # advisor names, and "mode" is a valid one — it must never be read as a recorded mode
        ws = make_ws(mcp=self.EMPTY_MCP, toml="")
        add_definition(ws, name="mode", extra="permission_mode: bypassPermissions\n")
        self.assertEqual(advisors.add(ws, "mode", pin=PIN, confirm_danger=True), {"mode": "declared-unregistered->registered"})
        ledger = ws / ".vibe-suite-state" / "advisor-preimages.json"
        self.assertIn("mode", self._ledger(ws)[advisors.ACCEPTANCES_KEY], "the acceptance is recorded under the advisor's name")
        self.assertEqual(os.stat(ledger).st_mode & 0o777, 0o600, "the ledger keeps the provenance floor")
        self.assertEqual(advisors.reconcile(ws, pin=PIN), {"mode": "consistent"}, "flag-less convergence holds")
        with mock.patch.object(advisors, "_ignore_block", side_effect=RuntimeError("injected after the ledger write")):
            with self.assertRaises(RuntimeError):
                advisors.remove(ws, "mode", delete_timeline=True, pin=PIN)   # the rollback saves the ledger with the map too
        self.assertIn("mode", self._ledger(ws)[advisors.ACCEPTANCES_KEY], "the rolled-back removal kept the acceptance")
        report = advisors.remove(ws, "mode", delete_timeline=True, pin=PIN)
        self.assertEqual(report["mode"], "removed")
        self.assertFalse(ledger.exists(), "the ledger clears with the last advisor")

    def test_malformed_acceptance_members_are_refused_fail_closed_and_absent_is_compatible(self):
        good = {"definition_sha256": "ab" * 32,
                "fields": [{"field": "permission_mode", "value": "auto", "reason": "r"}],
                "accepted_at": "2026-08-23T00:00:00Z"}
        bad_members = [
            "not a dict",
            {"prior": {}},                                                   # missing post
            {"prior": {}, "post": {}, "extra": {}},
            {"prior": {}, "post": {"probe_advisor": dict(good, definition_sha256="zz")}},
            {"prior": {}, "post": {"probe_advisor": dict(good, fields=[])}},
            {"prior": {}, "post": {"probe_advisor": dict(good, fields=[{"field": "model", "value": "x", "reason": "r"}])}},
            {"prior": {}, "post": {"probe_advisor": dict(good, accepted_at=1234)}},
            {"prior": {}, "post": {"../evil": good}},
            {"prior": {}, "post": {"probe_advisor": dict(good, surprise=True)}},
        ]
        entry = {"path": "x", "kind": "file", "mode": "0o644",
                 "sha256": hashlib.sha256(b"{}\n").hexdigest(),
                 "content_b64": base64.b64encode(b"{}\n").decode()}
        base = {"schema": 1, "intent": "apply", "remove_name": None, "delete_timeline": False,
                "desired_sha": "ab" * 32,
                "pre_images": {".mcp.json": entry, ".codex/config.toml": None},
                "post_images": {".mcp.json": "e30=", ".codex/config.toml": ""},
                "prior_baseline": None, "post_baseline": None}
        for bad in bad_members:
            with self.subTest(bad=str(bad)[:60]):
                ws = make_ws(mcp=self.EMPTY_MCP, toml="")
                state = ws / ".vibe-suite-state"
                state.mkdir()
                (state / "advisor-txn.json").write_text(json.dumps(dict(base, **{advisors.ACCEPTANCES_KEY: bad})))
                with self.assertRaises(advisors.AdvisorError):
                    advisors.recover(ws)
                self.assertTrue((state / "advisor-txn.json").is_file(), "a refused journal is left for inspection")
        # absent member (a journal written before vibe-184) → still recovers
        ws = make_ws(mcp=self.EMPTY_MCP, toml="")
        state = ws / ".vibe-suite-state"
        state.mkdir()
        (state / "advisor-txn.json").write_text(json.dumps(base))
        self.assertEqual(advisors.recover(ws), {"intent": "apply", "remove_name": None})
        # a well-formed member is accepted and its prior map is installed
        ws2 = make_ws(mcp=self.EMPTY_MCP, toml="")
        state2 = ws2 / ".vibe-suite-state"
        state2.mkdir()
        (state2 / "advisor-txn.json").write_text(json.dumps(dict(base, **{advisors.ACCEPTANCES_KEY: {"prior": {"probe_advisor": good}, "post": {}}})))
        self.assertEqual(advisors.recover(ws2), {"intent": "apply", "remove_name": None})
        self.assertEqual(self._ledger(ws2)[advisors.ACCEPTANCES_KEY], {"probe_advisor": good}, "apply recovery restores the PRIOR map")


class TestRegistrationStamp(unittest.TestCase):
    """vibe-185 / grill H1b: registration is an explicit operator act. A flag-less `reconcile` — what
    init / repair / update run — converges only definitions the operator registered (`add <name>` /
    `add --all` stamp the parsed content's sha in the ledger) and whose content is unchanged; a
    never-registered definition is held and disclosed, an edited one is held at its registered
    content until `add <name>` re-confirms and records the new hash; the stamp rides the journal,
    both rollback paths and `remove` exactly like the danger acceptance; `add a` is never refused on
    account of an unrelated declared definition."""

    EMPTY_MCP = '{"mcpServers": {}}\n'

    def _ws(self, *names, extra=None):
        ws = make_ws(mcp=self.EMPTY_MCP, toml="")
        for n in names:
            add_definition(ws, name=n, extra=(extra or {}).get(n, ""))
        return ws

    def _cli(self, ws, *args, fail_after=None):
        env = dict(os.environ)
        if fail_after:
            env["VIBE_ADVISOR_FAIL_AFTER"] = fail_after
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "advisor_cli.py"), "--workspace", str(ws), *args],
            capture_output=True, text=True, env=env)

    def _ledger(self, ws):
        p = ws / ".vibe-suite-state" / "advisor-preimages.json"
        return json.loads(p.read_text()) if p.is_file() else {}

    def _servers(self, ws):
        return json.loads((ws / ".mcp.json").read_text())["mcpServers"]

    def _sha(self, ws, name):
        return advisors.definition_sha(advisors.parse_definition(
            (ws / ".vibe-suite" / "agents" / f"{name}.md").read_text(), f"{name}.md"))

    # --- the rule: a flag-less reconcile registers nothing it was not told to --------------------------

    def test_a_flag_less_reconcile_holds_every_never_registered_definition_and_writes_nothing(self):
        ws = self._ws("alpha_one", "beta_two")
        report = advisors.reconcile(ws, pin=PIN)
        for n in ("alpha_one", "beta_two"):
            self.assertEqual(report[n], f"declared-unregistered (not registered; register with advisor add {n})")
        self.assertEqual(self._servers(ws), {})
        self.assertFalse((ws / ".codex" / "config.toml").read_text().strip())
        self.assertFalse((ws / ".vibe-suite-state").exists(), "no ledger, no journal: nothing was written")
        r = self._cli(ws, "reconcile", "--pin", PIN)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("alpha_one: declared-unregistered (not registered; register with advisor add alpha_one)", r.stdout)

    def test_add_registers_exactly_the_named_definition_and_stamps_it(self):
        ws = self._ws("alpha_one", "beta_two")
        report = advisors.add(ws, "alpha_one", pin=PIN)
        self.assertEqual(report["alpha_one"], "declared-unregistered->registered")
        self.assertEqual(report["beta_two"], "declared-unregistered (not registered; register with advisor add beta_two)")
        self.assertEqual(set(self._servers(ws)), {"alpha_one"}, "exactly alpha_one")
        self.assertNotIn("beta_two", (ws / ".codex" / "config.toml").read_text())
        stamps = self._ledger(ws)[advisors.REGISTRATIONS_KEY]
        self.assertEqual(set(stamps), {"alpha_one"})
        self.assertEqual(stamps["alpha_one"]["definition_sha256"], self._sha(ws, "alpha_one"), "the stamp is the parsed content's sha")
        self.assertRegex(stamps["alpha_one"]["registered_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(os.stat(ws / ".vibe-suite-state" / "advisor-preimages.json").st_mode & 0o777, 0o600)
        self.assertNotIn(advisors.ACCEPTANCES_KEY, self._ledger(ws), "a safe definition records no acceptance")

    def test_cli_add_registers_one_and_cli_add_all_registers_every_declared_definition(self):
        ws = self._ws("alpha_one", "beta_two")
        r = self._cli(ws, "add", "alpha_one", "--pin", PIN)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(set(self._servers(ws)), {"alpha_one"})
        r = self._cli(ws, "add", "--all", "--pin", PIN)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("beta_two: declared-unregistered->registered", r.stdout)
        self.assertEqual(set(self._servers(ws)), {"alpha_one", "beta_two"})
        self.assertEqual(set(self._ledger(ws)[advisors.REGISTRATIONS_KEY]), {"alpha_one", "beta_two"})
        for args in (["add", "--pin", PIN], ["add", "alpha_one", "--all", "--pin", PIN], ["add", "--all", "--custom", "--pin", PIN]):
            with self.subTest(args=" ".join(args)):
                self.assertEqual(self._cli(ws, *args).returncode, 2, "exactly one of <name> or --all; --all never composes a custom definition")
        empty = make_ws(mcp=self.EMPTY_MCP, toml="")
        self.assertEqual(self._cli(empty, "add", "--all", "--pin", PIN).returncode, 2, "--all with nothing declared refuses")
        with self.assertRaises(advisors.AdvisorError):
            advisors.reconcile(ws, pin=PIN, register={"nope"})

    def test_a_stamped_definition_converges_flag_less_when_its_registration_drifts(self):
        ws = self._ws("alpha_one")
        advisors.add(ws, "alpha_one", pin=PIN)
        stamp = self._ledger(ws)[advisors.REGISTRATIONS_KEY]["alpha_one"]
        toml_path = ws / ".codex" / "config.toml"
        toml_path.write_text(bridge.text_block_remove(toml_path.read_text(), "server:alpha_one"))
        self.assertEqual(advisors.reconcile(ws, pin=PIN), {"alpha_one": "half-registered->registered"},
                         "init / repair / update converge what the operator registered")
        self.assertIn("alpha_one", toml_path.read_text())
        self.assertEqual(self._ledger(ws)[advisors.REGISTRATIONS_KEY]["alpha_one"], stamp, "a convergence does not re-stamp")

    def test_an_edited_registered_definition_is_held_until_re_added_and_the_ledger_records_the_new_hash(self):
        ws = self._ws("alpha_one")
        advisors.add(ws, "alpha_one", pin=PIN)
        sha1 = self._ledger(ws)[advisors.REGISTRATIONS_KEY]["alpha_one"]["definition_sha256"]
        add_definition(ws, name="alpha_one", extra="max_turns: 9\n")
        sha2 = self._sha(ws, "alpha_one")
        self.assertNotEqual(sha1, sha2)
        held = advisors.reconcile(ws, pin=PIN)
        self.assertEqual(held["alpha_one"], "changed-unconfirmed (held; existing store content left unchanged; re-confirm with advisor add alpha_one)")
        self.assertEqual(self._servers(ws)["alpha_one"]["env"]["CLAUDE_MAX_TURNS"], "4", "the registered content stays")
        self.assertEqual(self._ledger(ws)[advisors.REGISTRATIONS_KEY]["alpha_one"]["definition_sha256"], sha1, "the stamp is untouched")
        r = self._cli(ws, "reconcile", "--pin", PIN)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("changed-unconfirmed", r.stdout)
        self.assertEqual(advisors.add(ws, "alpha_one", pin=PIN), {"alpha_one": "stale-registered->registered"})
        self.assertEqual(self._servers(ws)["alpha_one"]["env"]["CLAUDE_MAX_TURNS"], "9")
        self.assertEqual(self._ledger(ws)[advisors.REGISTRATIONS_KEY]["alpha_one"]["definition_sha256"], sha2, "the ledger records the new hash")

    def test_add_of_one_definition_is_not_refused_on_account_of_an_unrelated_one(self):
        ws = make_ws(mcp=json.dumps({"mcpServers": {"squat_me": {"command": "foreign"}}}) + "\n", toml="")
        add_definition(ws, name="alpha_one")
        add_definition(ws, name="risky_one", extra="permission_mode: bypassPermissions\n")
        add_definition(ws, name="squat_me")
        report = advisors.add(ws, "alpha_one", pin=PIN)
        self.assertEqual(report["alpha_one"], "declared-unregistered->registered")
        self.assertIn("dangerous: permission_mode", report["risky_one"])
        self.assertIn("--confirm-danger", report["risky_one"])
        self.assertEqual(report["squat_me"], "declared-unregistered (not registered; register with advisor add squat_me)")
        servers = self._servers(ws)
        self.assertIn("alpha_one", servers)
        self.assertNotIn("risky_one", servers)
        self.assertEqual(servers["squat_me"], {"command": "foreign"}, "the squatter is untouched")
        with self.assertRaises(advisors.AdvisorError) as cm:
            advisors.add(ws, "risky_one", pin=PIN)
        self.assertIn("--confirm-danger", str(cm.exception))
        with self.assertRaises(advisors.AdvisorError) as cm:
            advisors.add(ws, "squat_me", pin=PIN)
        self.assertIn("unowned", str(cm.exception))

    def test_a_dangerous_definition_needs_both_records_and_a_change_asks_for_the_flag_again(self):
        ws = self._ws("risky_one", extra={"risky_one": "permission_mode: dontAsk\n"})
        advisors.add(ws, "risky_one", pin=PIN, confirm_danger=True)
        ledger = self._ledger(ws)
        self.assertIn("risky_one", ledger[advisors.ACCEPTANCES_KEY])
        self.assertIn("risky_one", ledger[advisors.REGISTRATIONS_KEY])
        self.assertEqual(ledger[advisors.ACCEPTANCES_KEY]["risky_one"]["definition_sha256"],
                         ledger[advisors.REGISTRATIONS_KEY]["risky_one"]["definition_sha256"], "both bound to the same parsed content")
        self.assertEqual(advisors.reconcile(ws, pin=PIN), {"risky_one": "consistent"})
        add_definition(ws, name="risky_one", extra="permission_mode: dontAsk\nmax_turns: 9\n")
        self.assertIn("changed-unconfirmed", advisors.reconcile(ws, pin=PIN)["risky_one"])
        with self.assertRaises(advisors.AdvisorError):
            advisors.add(ws, "risky_one", pin=PIN)
        self.assertEqual(advisors.add(ws, "risky_one", pin=PIN, confirm_danger=True), {"risky_one": "stale-registered->registered"})

    # --- remove: the stamp is dropped; held siblings are left alone ------------------------------------

    def test_remove_drops_the_stamp_holds_siblings_and_the_ledger_clears_with_the_last_advisor(self):
        ws = self._ws("alpha_one", "beta_two")
        advisors.add(ws, "alpha_one", pin=PIN)
        advisors.add(ws, "beta_two", pin=PIN)
        add_definition(ws, name="beta_two", extra="max_turns: 9\n")            # beta is now changed
        report = advisors.remove(ws, "alpha_one", delete_timeline=True, pin=PIN)
        self.assertEqual(report["alpha_one"], "removed")
        self.assertIn("changed-unconfirmed", report["beta_two"])
        self.assertNotIn("_warning", report)
        stamps = self._ledger(ws)[advisors.REGISTRATIONS_KEY]
        self.assertEqual(set(stamps), {"beta_two"})
        self.assertEqual(self._servers(ws)["beta_two"]["env"]["CLAUDE_MAX_TURNS"], "4", "the held sibling was not refreshed")
        report = advisors.remove(ws, "beta_two", delete_timeline=True, pin=PIN)
        self.assertEqual(report["beta_two"], "removed")
        self.assertFalse((ws / ".vibe-suite-state" / "advisor-preimages.json").exists())

    def test_a_registration_without_a_stamp_is_held_never_refreshed_and_add_adopts_it(self):
        # A registration written before stamps existed: the stores hold it, the ledger does not.
        ws = self._ws("alpha_one")
        advisors.add(ws, "alpha_one", pin=PIN)
        ledger_path = ws / ".vibe-suite-state" / "advisor-preimages.json"
        ledger = json.loads(ledger_path.read_text()); ledger.pop(advisors.REGISTRATIONS_KEY)
        ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
        self.assertEqual(advisors.reconcile(ws, pin=PIN), {"alpha_one": "unstamped (held; existing store content left unchanged; confirm with advisor add alpha_one)"})
        self.assertEqual(advisors.list_advisors(ws, pin=PIN)[0]["registration"], "unstamped", "list says unstamped — the stores hold it, the ledger never stamped it")
        self.assertEqual(advisors.listing(ws)[0]["registration"], "unstamped")
        toml_path = ws / ".codex" / "config.toml"
        toml_path.write_text(bridge.text_block_remove(toml_path.read_text(), "server:alpha_one"))
        advisors.reconcile(ws, pin=PIN)
        self.assertNotIn("alpha_one", toml_path.read_text(), "held: never refreshed")
        self.assertEqual(advisors.add(ws, "alpha_one", pin=PIN), {"alpha_one": "half-registered->registered"})
        self.assertIn("alpha_one", self._ledger(ws)[advisors.REGISTRATIONS_KEY], "add adopts it: stamped at the current content")

    # --- the transaction: the stamp rides the journal, both rollback paths, and recovery ---------------

    def test_the_journal_carries_prior_and_post_stamp_maps_and_a_crashed_add_is_rolled_back_stamp_included(self):
        ws = self._ws("alpha_one")
        r = self._cli(ws, "add", "alpha_one", "--pin", PIN, fail_after="baseline")
        self.assertEqual(r.returncode, 9, "the crash seam fired AFTER the stores and the ledger were written")
        txn = json.loads((ws / ".vibe-suite-state" / "advisor-txn.json").read_text())
        member = txn[advisors.REGISTRATIONS_KEY]
        self.assertEqual(set(member), {"prior", "post"})
        self.assertEqual(member["prior"], {})
        self.assertEqual(member["post"]["alpha_one"]["definition_sha256"], self._sha(ws, "alpha_one"))
        self.assertIn("alpha_one", self._ledger(ws).get(advisors.REGISTRATIONS_KEY, {}), "precondition: the crash left the stamp on disk")
        self.assertEqual(advisors.recover(ws), {"intent": "apply", "remove_name": None})
        self.assertEqual(self._servers(ws), {}, "the registration rolled back")
        self.assertNotIn("alpha_one", self._ledger(ws).get(advisors.REGISTRATIONS_KEY, {}), "the stamp rolled back with it")
        self.assertIn("not registered", advisors.reconcile(ws, pin=PIN)["alpha_one"], "a rolled-back add registered nothing")
        self.assertEqual(advisors.add(ws, "alpha_one", pin=PIN), {"alpha_one": "declared-unregistered->registered"})

    def test_an_add_whose_ignore_block_raises_after_the_ledger_write_rolls_back_stamp_included(self):
        ws = self._ws("alpha_one", "beta_two")
        advisors.add(ws, "alpha_one", pin=PIN)
        before = self._ledger(ws)[advisors.REGISTRATIONS_KEY]
        with mock.patch.object(advisors, "_ignore_block", side_effect=RuntimeError("injected after the ledger write")):
            with self.assertRaises(RuntimeError):
                advisors.add(ws, "beta_two", pin=PIN)
        self.assertEqual(self._ledger(ws)[advisors.REGISTRATIONS_KEY], before, "the prior stamp map is restored in-process")
        self.assertEqual(set(self._servers(ws)), {"alpha_one"})
        self.assertFalse((ws / ".vibe-suite-state" / "advisor-txn.json").exists())
        self.assertIn("not registered", advisors.reconcile(ws, pin=PIN)["beta_two"])

    def test_removing_a_stamped_advisor_that_crashes_rolls_forward_stamp_dropped(self):
        for point in ("json", "toml"):
            with self.subTest(point=point):
                ws = self._ws("alpha_one")
                self.assertEqual(self._cli(ws, "add", "alpha_one", "--pin", PIN).returncode, 0)
                self.assertEqual(self._ledger(ws)[advisors.REGISTRATIONS_KEY]["alpha_one"]["definition_sha256"], self._sha(ws, "alpha_one"),
                                 "precondition: the stamp exists and matches the definition")
                r = self._cli(ws, "remove", "alpha_one", "--delete-timeline", fail_after=point)
                self.assertEqual(r.returncode, 9, (point, r.stderr))
                r2 = self._cli(ws, "reconcile", "--pin", PIN)
                self.assertEqual(r2.returncode, 0, (point, r2.stderr))
                self.assertEqual(self._servers(ws), {}, point)
                self.assertFalse((ws / ".vibe-suite-state" / "advisor-preimages.json").exists(), f"{point}: the stamp is gone with the ledger")

    def test_malformed_stamp_members_are_refused_fail_closed_and_absent_is_compatible(self):
        ws = self._ws("alpha_one")
        r = self._cli(ws, "add", "alpha_one", "--pin", PIN, fail_after="json")
        self.assertEqual(r.returncode, 9)
        txn_path = ws / ".vibe-suite-state" / "advisor-txn.json"
        good = json.loads(txn_path.read_text())
        sha = good[advisors.REGISTRATIONS_KEY]["post"]["alpha_one"]["definition_sha256"]
        bad_members = {
            "not-a-dict": [], "missing-post": {"prior": {}}, "extra-key": {"prior": {}, "post": {}, "x": {}},
            "bad-sha": {"prior": {}, "post": {"alpha_one": {"definition_sha256": "zz", "registered_at": "2026-01-01T00:00:00Z"}}},
            "bad-time": {"prior": {}, "post": {"alpha_one": {"definition_sha256": sha, "registered_at": "yesterday"}}},
            "extra-entry-key": {"prior": {}, "post": {"alpha_one": {"definition_sha256": sha, "registered_at": "2026-01-01T00:00:00Z", "x": 1}}},
            "bad-name": {"prior": {}, "post": {"-bad": {"definition_sha256": sha, "registered_at": "2026-01-01T00:00:00Z"}}},
        }
        for label, member in bad_members.items():
            with self.subTest(member=label):
                txn = dict(good); txn[advisors.REGISTRATIONS_KEY] = member
                txn_path.write_text(json.dumps(txn) + "\n")
                with self.assertRaises(advisors.AdvisorError):
                    advisors.recover(ws)
                self.assertTrue(txn_path.exists(), "a refused journal is left in place")
        txn = dict(good); txn.pop(advisors.REGISTRATIONS_KEY)
        txn_path.write_text(json.dumps(txn) + "\n")
        self.assertEqual(advisors.recover(ws), {"intent": "apply", "remove_name": None}, "an absent member (a pre-vibe-185 journal) still recovers")

    def test_a_remove_whose_ignore_block_raises_keeps_every_stamp_in_process(self):
        ws = self._ws("alpha_one", "beta_two")
        advisors.add(ws, "alpha_one", pin=PIN)
        advisors.add(ws, "beta_two", pin=PIN)
        before = self._ledger(ws)[advisors.REGISTRATIONS_KEY]
        self.assertEqual(set(before), {"alpha_one", "beta_two"}, "precondition: both stamped")
        with mock.patch.object(advisors, "_ignore_block", side_effect=RuntimeError("injected after the ledger write")):
            with self.assertRaises(RuntimeError):
                advisors.remove(ws, "alpha_one", delete_timeline=True, pin=PIN)
        self.assertEqual(self._ledger(ws)[advisors.REGISTRATIONS_KEY], before, "the rolled-back removal kept alpha's stamp and beta's")
        self.assertEqual(set(self._servers(ws)), {"alpha_one", "beta_two"})
        self.assertTrue((ws / ".vibe-suite" / "agents" / "alpha_one.md").exists())
        self.assertEqual(advisors.reconcile(ws, pin=PIN), {"alpha_one": "consistent", "beta_two": "consistent"})

    # --- an explicit add acts on exactly its name: never refused, never accepting, on account of a sibling ---

    def test_add_of_one_definition_ignores_a_stamped_but_problematic_sibling(self):
        ws = self._ws("alpha_one", "beta_two", "gamma_3")
        advisors.add(ws, "beta_two", pin=PIN)                                   # stamped …
        advisors.add(ws, "gamma_3", pin=PIN)
        doc = json.loads((ws / ".mcp.json").read_text())
        doc["mcpServers"]["beta_two"] = {"command": "foreign"}                  # … then squatted (a collision for beta)
        doc["mcpServers"]["gamma_3"]["args"] = ["-y", "claude-octopus@latest"]  # … and gamma's target floats (invalid without a pin)
        (ws / ".mcp.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        report = advisors.add(ws, "alpha_one")                                  # no pin: gamma would be invalid-registration if acted on
        self.assertEqual(report["alpha_one"], "declared-unregistered->registered")
        self.assertIn("alpha_one", self._servers(ws))
        self.assertEqual(self._servers(ws)["beta_two"], {"command": "foreign"}, "the squatter is untouched")
        self.assertEqual(self._servers(ws)["gamma_3"]["args"], ["-y", "claude-octopus@latest"], "gamma is untouched")
        self.assertIn("registered (not converged by an explicit add", report["beta_two"])
        self.assertIn("registered (not converged by an explicit add", report["gamma_3"])

    def test_add_with_the_flag_accepts_only_the_named_definition(self):
        ws = self._ws("alpha_one", "risky_one", extra={"risky_one": "permission_mode: bypassPermissions\n"})
        with self.assertRaises(advisors.AdvisorError) as cm:
            advisors.add(ws, "alpha_one", pin=PIN, confirm_danger=True)         # alpha is safe: the flag is meaningless for it
        self.assertIn("only meaningful", str(cm.exception))
        self.assertFalse((ws / ".vibe-suite-state").exists(), "nothing written: no acceptance for risky_one either")
        advisors.add(ws, "alpha_one", pin=PIN)
        self.assertNotIn(advisors.ACCEPTANCES_KEY, self._ledger(ws))
        advisors.add(ws, "risky_one", pin=PIN, confirm_danger=True)
        self.assertEqual(set(self._ledger(ws)[advisors.ACCEPTANCES_KEY]), {"risky_one"})
        # a stamped dangerous sibling whose acceptance was removed by hand never blocks an unrelated add
        ledger_path = ws / ".vibe-suite-state" / "advisor-preimages.json"
        ledger = json.loads(ledger_path.read_text()); ledger.pop(advisors.ACCEPTANCES_KEY)
        ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
        add_definition(ws, name="gamma_3")
        self.assertEqual(advisors.add(ws, "gamma_3", pin=PIN)["gamma_3"], "declared-unregistered->registered")
        with self.assertRaises(advisors.AdvisorError):
            advisors.reconcile(ws, pin=PIN)                                       # the flag-less caller still refuses the write of risky_one

    def test_add_of_one_definition_leaves_an_unrelated_orphaned_registration_for_the_flag_less_callers(self):
        orphan = {"command": "npx", "args": ["-y", f"claude-octopus@{PIN}"], "env": {},
                  "_vibe-suite_owned": {"kind": "advisor", "schema": 1}}
        ws = make_ws(mcp=json.dumps({"mcpServers": {"orphan_one": orphan}}, indent=2, sort_keys=True) + "\n",
                     toml="# >>> vibe-suite:server:orphan_one v1 >>>\n[mcp_servers.orphan_one]\ncommand = \"npx\"\n# <<< vibe-suite:server:orphan_one <<<\n")
        add_definition(ws, name="alpha_one")
        report = advisors.add(ws, "alpha_one", pin=PIN)
        self.assertEqual(report["alpha_one"], "declared-unregistered->registered")
        self.assertEqual(report["orphan_one"], "registered-undeclared (not converged by an explicit add; run advisor reconcile)")
        self.assertEqual(self._servers(ws)["orphan_one"], orphan, "an explicit add leaves the orphan in .mcp.json")
        self.assertIn("orphan_one", (ws / ".codex" / "config.toml").read_text(), "and in config.toml")
        self.assertEqual(advisors.reconcile(ws, pin=PIN)["orphan_one"], "registered-undeclared->removed", "the flag-less caller removes it")
        self.assertNotIn("orphan_one", self._servers(ws))
        self.assertNotIn("orphan_one", (ws / ".codex" / "config.toml").read_text())

    # --- a definition deleted by hand loses its records; restoring the file is a new registration ---

    def test_deleting_a_definition_by_hand_drops_its_records_and_restoring_it_is_held(self):
        ws = self._ws("alpha_one", "risky_one", extra={"risky_one": "permission_mode: dontAsk\n"})
        advisors.add(ws, "alpha_one", pin=PIN)
        advisors.add(ws, "risky_one", pin=PIN, confirm_danger=True)
        text = (ws / ".vibe-suite" / "agents" / "risky_one.md").read_text()
        (ws / ".vibe-suite" / "agents" / "risky_one.md").unlink()
        report = advisors.reconcile(ws, pin=PIN)
        self.assertEqual(report["risky_one"], "registered-undeclared->removed")
        ledger = self._ledger(ws)
        self.assertNotIn("risky_one", ledger.get(advisors.REGISTRATIONS_KEY, {}), "the stamp went with the definition")
        self.assertNotIn(advisors.ACCEPTANCES_KEY, ledger, "and so did the acceptance")
        (ws / ".vibe-suite" / "agents" / "risky_one.md").write_text(text)      # the identical file comes back
        report = advisors.reconcile(ws, pin=PIN)
        self.assertIn("danger-unaccepted (not registered", report["risky_one"], "held: a new registration, not a resumed one")
        self.assertNotIn("risky_one", self._servers(ws))
        # a record whose definition AND store entries are gone is still dropped (the classifier never visits it)
        advisors.add(ws, "risky_one", pin=PIN, confirm_danger=True)
        (ws / ".vibe-suite" / "agents" / "risky_one.md").unlink()
        doc = json.loads((ws / ".mcp.json").read_text()); del doc["mcpServers"]["risky_one"]
        (ws / ".mcp.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        toml_path = ws / ".codex" / "config.toml"; toml_path.write_text(bridge.text_block_remove(toml_path.read_text(), "server:risky_one"))
        self.assertIn("risky_one", self._ledger(ws)[advisors.REGISTRATIONS_KEY], "precondition: the orphan record is on disk")
        advisors.reconcile(ws, pin=PIN)
        self.assertNotIn("risky_one", self._ledger(ws).get(advisors.REGISTRATIONS_KEY, {}))
        self.assertNotIn(advisors.ACCEPTANCES_KEY, self._ledger(ws))

    # --- add --all gives every advisor its timeline, and a refused bulk add leaves no residue ---

    def test_add_all_creates_every_timeline_and_a_refused_bulk_add_leaves_no_residue(self):
        ws = self._ws("alpha_one", "beta_two", "risky_one", extra={"risky_one": "permission_mode: auto\n"})
        with self.assertRaises(advisors.AdvisorError):
            advisors.add_all(ws, pin=PIN)                                       # refused: risky_one needs the flag
        for n in ("alpha_one", "beta_two", "risky_one"):
            self.assertFalse((ws / ".vibe-suite" / "agents" / n).exists(), f"{n}: no timeline residue after a refused bulk add")
        self.assertEqual(self._servers(ws), {})
        report = advisors.add_all(ws, pin=PIN, confirm_danger=True)
        for n in ("alpha_one", "beta_two", "risky_one"):
            self.assertEqual(report[n], "declared-unregistered->registered")
            self.assertTrue((ws / ".vibe-suite" / "agents" / n / "timeline").is_dir(), f"{n}: timeline created")
        self.assertEqual(set(self._ledger(ws)[advisors.REGISTRATIONS_KEY]), {"alpha_one", "beta_two", "risky_one"})
        # an existing timeline is kept (never recreated) by a later add --all
        (ws / ".vibe-suite" / "agents" / "alpha_one" / "timeline" / "note.md").write_text("history\n")
        advisors.add_all(ws, pin=PIN, confirm_danger=True)
        self.assertTrue((ws / ".vibe-suite" / "agents" / "alpha_one" / "timeline" / "note.md").is_file())

    # --- disclosure: listing and list rows ---------------------------------------------------------------

    def test_listing_and_list_rows_disclose_the_registration_state_and_what_a_registration_would_hand_over(self):
        ws = self._ws("alpha_one", "risky_one", extra={"risky_one": "permission_mode: bypassPermissions\nallowed_tools: [Bash]\ncwd: docs\nadditional_dirs: [src]\n"})
        rows = {r["name"]: r for r in advisors.listing(ws)}
        self.assertEqual(set(rows), {"alpha_one", "risky_one"})
        risky = rows["risky_one"]
        self.assertEqual(risky["allowed_tools"], ["Bash"])
        self.assertEqual(risky["permission_mode"], "bypassPermissions")
        self.assertEqual(risky["cwd"], "docs")
        self.assertEqual(risky["additional_dirs"], ["src"])
        body = advisors.parse_definition((ws / ".vibe-suite" / "agents" / "risky_one.md").read_text(), "risky_one.md")["body"]
        self.assertEqual(risky["prompt_bytes"], len(body.encode("utf-8")))
        self.assertEqual(risky["registration"], "unregistered")
        self.assertEqual(risky["dangerous"], ["permission_mode"])
        self.assertEqual(rows["alpha_one"]["dangerous"], [])
        advisors.add(ws, "alpha_one", pin=PIN)
        self.assertEqual({r["name"]: r["registration"] for r in advisors.listing(ws)}, {"alpha_one": "registered", "risky_one": "unregistered"})
        self.assertEqual({r["name"]: r["registration"] for r in advisors.list_advisors(ws, pin=PIN)}, {"alpha_one": "registered", "risky_one": "unregistered"})
        out = self._cli(ws, "list").stdout
        self.assertIn("registered", out)
        self.assertIn("unregistered", out)


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
        rows = {r["name"]: r for r in advisors.list_advisors(ws, pin=PIN)}
        self.assertEqual(rows["probe_advisor"]["state"], "stale-registered")
        advisors.reconcile(ws, pin=PIN)
        rows = {r["name"]: r for r in advisors.list_advisors(ws, pin=PIN)}
        self.assertEqual(rows["probe_advisor"]["state"], "consistent")
        # TOML-only staleness
        toml_path = ws / ".codex" / "config.toml"
        toml_path.write_text(toml_path.read_text().replace(
            'CLAUDE_MAX_TURNS = "4"', 'CLAUDE_MAX_TURNS = "77"'))
        rows = {r["name"]: r for r in advisors.list_advisors(ws, pin=PIN)}
        self.assertEqual(rows["probe_advisor"]["state"], "stale-registered")

    def test_edited_definition_flips_state(self):
        ws = self._ws()
        add_definition(ws, extra="effort: high\n")
        rows = {r["name"]: r for r in advisors.list_advisors(ws, pin=PIN)}
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
            # journal-point rollback leaves nothing; toml-point rollback also rolls back. vibe-185:
            # the converging reconcile HOLDS the surviving, never-stamped definition — registration
            # is the operator's act — and a second `add` registers it.
            self.assertNotIn("probe_advisor", doc["mcpServers"], point)
            self.assertEqual(self.run_cli(ws, "add", "probe_advisor", "--pin", PIN).returncode, 0, point)
            self.assertIn("probe_advisor", json.loads((ws / ".mcp.json").read_text())["mcpServers"], point)

    def test_stale_update_crash_at_json_and_toml(self):
        # vibe-185: an edited registered definition is HELD by a flag-less reconcile (no write, so no
        # seam fires); the re-confirming `add` is the write that can crash — it rolls back to the
        # registered content, and the next `add` completes.
        for point in ("json", "toml"):
            ws = self.ws()
            self.run_cli(ws, "add", "probe_advisor", "--pin", PIN)
            add_definition(ws, extra="effort: high\n")
            held = self.run_cli(ws, "reconcile", fail_after=point)
            self.assertEqual(held.returncode, 0, (point, held.stderr))
            self.assertIn("changed-unconfirmed", held.stdout, point)
            self.assertIsNone(json.loads((ws / ".mcp.json").read_text())["mcpServers"]["probe_advisor"]["env"].get("CLAUDE_EFFORT"), point)
            r = self.run_cli(ws, "add", "probe_advisor", "--pin", PIN, fail_after=point)
            self.assertEqual(r.returncode, 9, (point, r.stderr))
            r2 = self.run_cli(ws, "reconcile")
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertIsNone(json.loads((ws / ".mcp.json").read_text())["mcpServers"]["probe_advisor"]["env"].get("CLAUDE_EFFORT"),
                              f"{point}: the crashed re-confirmation rolled back to the registered content")
            self.assertEqual(self.run_cli(ws, "add", "probe_advisor", "--pin", PIN).returncode, 0, point)
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


class TestResidueHardening(unittest.TestCase):
    """Round-3 Step-9 iteration 2: the re-verify's four residues."""

    def test_list_valued_name_rejected_cleanly(self):
        with self.assertRaises(advisors.AdvisorError):
            advisors.parse_definition(defn_text(extra="name: [probe_advisor]\n"),
                                      "probe_advisor.md")

    def test_full_key_crafted_journal_refused(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        state = ws / ".vibe-suite-state"
        state.mkdir()
        crafted = {"schema": 1, "intent": "remove", "remove_name": "probe_advisor",
                   "delete_timeline": True, "desired_sha": "ab" * 32,
                   "pre_images": {".mcp.json": {}, ".codex/config.toml": None,
                                  "definition": None},
                   "post_images": {".mcp.json": "e30=", ".codex/config.toml": ""},
                   "prior_baseline": None, "post_baseline": None}
        (state / "advisor-txn.json").write_text(json.dumps(crafted))
        with self.assertRaises(advisors.AdvisorError):
            advisors.recover(ws)
        self.assertTrue((ws / ".vibe-suite" / "agents" / "probe_advisor.md").is_file(),
                        "a crafted journal must not drive deletions")
        crafted["pre_images"][".mcp.json"] = None
        del crafted["pre_images"]["definition"]
        (state / "advisor-txn.json").write_text(json.dumps(crafted))
        with self.assertRaises(advisors.AdvisorError):
            advisors.recover(ws)

    def test_recovery_through_symlink_root_refused(self):
        real = Path(tempfile.mkdtemp(prefix="advisor-real2-"))
        (real / ".vibe-suite-state").mkdir()
        (real / ".vibe-suite-state" / "advisor-txn.json").write_text("{}")
        link = Path(tempfile.mkdtemp(prefix="advisor-link2-")) / "ws"
        link.symlink_to(real)
        with self.assertRaises(bridge.BridgeError):
            advisors.recover(link)


class TestJournalImageIntegrity(unittest.TestCase):
    """Iteration 3: hashes verify against content; None-definition journals cannot delete."""

    def _journal(self, ws, **overrides):
        entry = {"path": str(ws / ".mcp.json"), "kind": "file", "mode": "0o644",
                 "sha256": __import__("hashlib").sha256(b"{}\n").hexdigest(),
                 "content_b64": __import__("base64").b64encode(b"{}\n").decode()}
        base = {"schema": 1, "intent": "remove", "remove_name": "probe_advisor",
                "delete_timeline": False, "desired_sha": "ab" * 32,
                "pre_images": {".mcp.json": entry, ".codex/config.toml": None,
                               "definition": None},
                "post_images": {".mcp.json": "e30=", ".codex/config.toml": ""},
                "prior_baseline": None, "post_baseline": None}
        base.update(overrides)
        return base

    def test_malformed_sha_refused(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        state = ws / ".vibe-suite-state"
        state.mkdir()
        j = self._journal(ws)
        j["pre_images"][".mcp.json"]["sha256"] = "0" * 64
        (state / "advisor-txn.json").write_text(json.dumps(j))
        with self.assertRaises(advisors.AdvisorError):
            advisors.recover(ws)
        j2 = self._journal(ws)
        j2["prior_baseline"] = dict(j2["pre_images"][".mcp.json"], sha256="1" * 64)
        (state / "advisor-txn.json").write_text(json.dumps(j2))
        with self.assertRaises(advisors.AdvisorError):
            advisors.recover(ws)

    def test_none_definition_journal_cannot_delete_a_real_definition(self):
        ws = make_ws(mcp=CANONICAL_FOREIGN, toml=TOML_FOREIGN)
        add_definition(ws)
        state = ws / ".vibe-suite-state"
        state.mkdir()
        (state / "advisor-txn.json").write_text(json.dumps(self._journal(ws)))
        advisors.recover(ws)
        self.assertTrue((ws / ".vibe-suite" / "agents" / "probe_advisor.md").is_file(),
                        "a journal without definition provenance must not delete one")

    def test_list_valued_description_rejected_cleanly(self):
        text = "---\ndescription: [x]\nmodel: sonnet\n---\n\nbody\n"
        with self.assertRaises(advisors.AdvisorError):
            advisors.parse_definition(text, "probe_advisor.md")
