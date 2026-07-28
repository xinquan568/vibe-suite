#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Read-only diagnosis for `/vibe-suite:doctor` (E2.2 / vibe-19, F1.2).

**Nothing here writes.** F1.2 specifies read-only and E2.3 (#20) owns repair, so this module imports
predicates only — `bridge`'s `*_has`/`inventory_enumerate`, `config`'s loader — and never
`bridge.write_atomic` or `Store.set`. A fixture asserts the workspace is byte-identical across a run.

**Findings and capabilities are different things.** A check that cannot run — F4.4 pending #30,
mirror staleness pending E7.2 — is a fact about the installation, not a defect in the project.
`vibe-core` makes `[GOOD]` exclusive, so mixing them would put an unavailable capability in the
findings table and make a clean project unreportable as clean, forever.

**Three initialisation states, deliberately distinguished.** `.vibe-suite-state/` proves nothing on
its own (it holds job records and gate toggles), and an absent `.vibe-suite.md` loads defaults
silently. So *uninitialised*, *partial* and *installed* are told apart on purpose: conflating them
yields either a cascade of missing-component findings on a project nobody set up, or a claim that
repair is safe when provenance cannot support it.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402
import config as config_mod  # noqa: E402
import init_bridge  # noqa: E402

MEMORY_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")

#: Checks whose implementation does not exist at this commit. Reported, never omitted — an omitted
#: row is indistinguishable from a passing one.
UNAVAILABLE = (
    ("manifest-vs-disk", "E3.5 (#30) — bin/vibe-check"),
    ("mirror-staleness", "E7.2 — the hash manifest; E3.5 defers the full check to 'live after E7.2'"),
    ("version-coherence", "F4.4 (#30) — marketplace.json carries no version to compare"),
    ("legacy-auditor-data", "§7A row 9 — migration records completion on the destination branch, "
                            "so a project-local command has no readable receipt"),
)


def finding(severity, check, text, fixable=False):
    return {"severity": severity, "check": check, "finding": text, "auto_fixable": fixable}


def detect_state(ws):
    """uninitialised | partial | installed."""
    provenance = ws / init_bridge.PROVENANCE
    owned = bool(bridge.inventory_enumerate(ws))
    configured = (ws / config_mod.CONFIG_FILENAME).is_file()
    memory = any(bridge.md_block_has(bridge.read_text_verbatim(ws / n), "memory")
                 or bridge.md_block_has(bridge.read_text_verbatim(ws / n), "import")
                 for n in MEMORY_FILES)
    if not (owned or configured or memory or provenance.is_file()):
        return "uninitialised"
    if not provenance.is_file():
        return "partial"
    record = bridge.load_json(provenance)
    # `all()` over an empty list is vacuously true, so the target *set* is checked as well as each
    # entry — a record naming nothing would otherwise read as a complete restore source.
    # Compared by *name*, not absolute path: the record was written under the path init was given,
    # and this command resolves symlinks — on macOS `/var` and `/private/var` name one directory and
    # would never compare equal.
    expected = {Path(rel).name for rel in init_bridge.TARGETS}
    targets = record.get("targets") if isinstance(record, dict) else None
    if (not isinstance(record, dict) or record.get("schema") != bridge.SCHEMA
            or not isinstance(targets, list)
            or not all(init_bridge._valid_target(t) for t in targets)
            or {Path(t["path"]).name for t in targets} != expected):
        return "partial"
    return "installed"


def check_bridge(ws, out):
    names = bridge.inventory_enumerate(ws)
    mcp = bridge.load_json(ws / ".mcp.json")
    toml = bridge.read_text_verbatim(ws / ".codex" / "config.toml")
    if "vibe-mcp" not in names:
        out.append(finding("[HIGH]", "sentinels", "no vibe-mcp registration found", True))
    for name in names:
        # The enumerator unions the two stores, so a name registered in one and missing from the
        # other is invisible unless both are asked separately.
        in_json = bridge.json_server_has(mcp, name)
        in_toml = name in bridge.toml_owned_names(toml)
        if in_json != in_toml:
            where = ".mcp.json" if in_json else ".codex/config.toml"
            out.append(finding("[MEDIUM]", "sentinels",
                               f"{name} is registered only in {where}", True))
    for name in MEMORY_FILES:
        text = bridge.read_text_verbatim(ws / name)
        if text and not (bridge.md_block_has(text, "memory") or bridge.md_block_has(text, "import")):
            out.append(finding("[MEDIUM]", "memory", f"{name} carries no owned block", True))
    hooks = bridge.load_json(ws / ".codex" / "hooks.json")
    for entry in (hooks.get("hooks") or {}).get("Stop") or []:
        if isinstance(entry, dict) and entry.get(f"_{bridge.MARKER}_owned") is not None:
            command = (entry.get("command") or "").split()[0] if entry.get("command") else ""
            # Only an absolute path asserts something about this filesystem. A bare name is the
            # plugin's own dispatch, resolved by the host, and flagging it would fire on every
            # healthy project.
            if command.startswith("/") and not Path(command).exists():
                out.append(finding("[MEDIUM]", "hooks",
                                   f"owned Stop hook command does not resolve: {command}", False))


def check_symlinks(ws, out):
    for rel in init_bridge.TARGETS:
        path = ws / rel
        kind = bridge.classify(path)
        if kind == "symlink":
            out.append(finding("[HIGH]", "symlinks",
                               f"{rel} is a symlink; the installer writes regular files", False))
        elif kind == "other":
            out.append(finding("[HIGH]", "symlinks", f"{rel} is neither a file nor a symlink", False))


def check_pins(ws, out):
    record = bridge.load_json(ws / init_bridge.PROVENANCE)
    recorded = record.get("plugin_version") if isinstance(record, dict) else None
    manifest = bridge.load_json(HERE.parent / ".claude-plugin" / "plugin.json").get("version")
    if recorded and manifest and recorded != manifest:
        out.append(finding("[MEDIUM]", "pins",
                           f"installed under plugin {recorded}; this plugin is {manifest}", True))


def check_config(ws, out):
    if not (ws / config_mod.CONFIG_FILENAME).is_file():
        return
    try:
        config_mod.load(str(ws))
    except Exception as exc:
        out.append(finding("[HIGH]", "config", f"{config_mod.CONFIG_FILENAME} is invalid: {exc}",
                           False))


def check_legacy(ws, out):
    """§7A rows the shipped helpers do not detect read-only.

    `survey.sh` covers rows 4, 7, 8 and 10; the rest are detected by the migrate helpers only as a
    prelude to acting, which a diagnosis must not do.
    """
    if (ws / ".cc-suite.md").is_file() or (ws / ".claude" / "nlpm.local.md").is_file():
        out.append(finding("[LOW]", "legacy-config",
                           "legacy configuration present and ignored; /vibe-suite:init migrates it",
                           True))
    if (ws / ".claude" / "nlpm-reports").is_dir():
        out.append(finding("[LOW]", "legacy-reports",
                           ".claude/nlpm-reports/ present; new reports go to .claude/vibe-reports/",
                           False))
    for candidate in ("codex-toolkit", "cc-suite-state"):
        if (ws / candidate / "config.json").is_file():
            out.append(finding("[LOW]", "legacy-state",
                               f"{candidate}/ holds legacy state; only stopReviewGate migrates",
                               True))
    mcp = bridge.load_json(ws / ".mcp.json")
    toml = bridge.read_text_verbatim(ws / ".codex" / "config.toml")
    legacy = [n for n in (mcp.get("mcpServers") or {}) if n.startswith("cc-suite-")]
    legacy += [n for n in bridge.toml_owned_names(toml) if n.startswith("cc-suite-")]
    if legacy:
        out.append(finding("[MEDIUM]", "legacy-sentinels",
                           f"legacy sentinels still registered: {', '.join(sorted(set(legacy)))}",
                           True))


def check_provenance(ws, state, out):
    if state != "partial":
        return
    if not (ws / init_bridge.PROVENANCE).is_file():
        out.append(finding("[HIGH]", "provenance",
                           "owned artefacts present but no provenance record; "
                           "/vibe-suite:unbridge cannot restore what it does not describe", False))
    else:
        out.append(finding("[HIGH]", "provenance",
                           "the provenance record is malformed, so restore data cannot be trusted; "
                           "unbridge cannot rely on it", False))


def knowledge_capability(out):
    """F8.4's date is plugin-level, beside the skill it describes — a project-local copy would let
    two projects disagree about one shared skill. E6.5 (#48) writes it."""
    root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", HERE.parent))
    for candidate in (root / "skills").glob("*/refreshed.json"):
        record = bridge.load_json(candidate)
        if isinstance(record, dict) and record.get("refreshed"):
            return None
        return finding("[LOW]", "knowledge-freshness",
                       f"{candidate.name} carries no readable date", False)
    return ("knowledge-freshness", "E6.5 (#48) — no refresh date is written yet")


def diagnose(ws):
    ws = Path(ws).resolve()
    state = detect_state(ws)
    findings, capabilities = [], []

    check_legacy(ws, findings)
    if state == "uninitialised":
        # The missing-component cascade is suppressed — every bridge target is expected to be
        # absent. Legacy detection above still ran, because a project holding a legacy store needs
        # that reported precisely *because* it has not been migrated.
        findings.append(finding("[MEDIUM]", "not-initialised",
                                "vibe-suite is not installed here; run /vibe-suite:init", True))
    else:
        check_bridge(ws, findings)
        check_symlinks(ws, findings)
        check_pins(ws, findings)
        check_config(ws, findings)
        check_provenance(ws, state, findings)

    for check, blocked in UNAVAILABLE:
        capabilities.append({"check": check, "status": "unavailable", "blocked_on": blocked})
    knowledge = knowledge_capability(findings)
    if isinstance(knowledge, tuple):
        capabilities.append({"check": knowledge[0], "status": "unavailable",
                             "blocked_on": knowledge[1]})
    elif knowledge:
        findings.append(knowledge)
    capabilities.append({"check": "connectivity", "status": "see-preflight",
                         "blocked_on": "/vibe-suite:preflight owns the normalised lane result; "
                                       "agy's 'available' verdict stays pending behind its gate"})

    if not findings:
        # `[GOOD]` is exclusive: a report containing it contains exactly that one entry.
        findings = [finding("[GOOD]", "all", "no issues found")]
    return {"state": state, "findings": findings, "capabilities": capabilities}


def render(report):
    lines = [f"# vibe-suite doctor — {report['state']}", "", "## Findings", "",
             "| Severity | Check | Finding | Auto-fixable |", "|---|---|---|---|"]
    for f in report["findings"]:
        lines.append(f"| {f['severity']} | {f['check']} | {f['finding']} | "
                     f"{'yes' if f['auto_fixable'] else '—'} |")
    lines += ["", "## Capabilities", "", "| Check | Status | Blocked on |", "|---|---|---|"]
    for c in report["capabilities"]:
        lines.append(f"| {c['check']} | {c['status']} | {c['blocked_on']} |")
    if any(f["auto_fixable"] for f in report["findings"]):
        lines += ["", "Auto-fixable items can be addressed by `/vibe-suite:repair`."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="read-only vibe-suite diagnosis")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = diagnose(args.workspace)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 1 if any(f["severity"] != "[GOOD]" for f in report["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
