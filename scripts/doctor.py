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
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402
import mcp_pin  # noqa: E402
import retired_names  # noqa: E402
import config as config_mod  # noqa: E402
import init_bridge  # noqa: E402

MEMORY_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")

#: `auto_fixable` means one thing: **a no-prompt `/vibe-suite:repair` clears this**. Five checks
#: looked fixable and are not — §7A preserves legacy sources so those findings survive their own fix,
#: row 6 needs a confirmation repair may not obtain, provenance is write-once, and `not-initialised`
#: is cleared only by a command that asks questions. A flag promising what no command delivers is
#: worse than no flag, because the acceptance criterion for E2.3 is exactly this coupling.
#:
#: Checks whose implementation does not exist at this commit. Reported, never omitted — an omitted
#: row is indistinguishable from a passing one.
UNAVAILABLE = (
    ("manifest-vs-disk", "E3.5 (#30) — bin/vibe-check"),
    ("version-coherence", "F4.4 (#30) — marketplace.json carries no version to compare"),
    ("legacy-auditor-data", "§7A row 9 executed 2026-08-13 (E8.5): 1287 files content-address-"
                            "verified; the receipt (.vibe-suite-migration/manifest.sha256 + "
                            "provenance.json) lives on the auditor-data branch, which a "
                            "project-local command does not read"),
)


def safe_json(path, out, check):
    """Parsed JSON, or a finding. A diagnosis that raises on a malformed file reports nothing about
    the rest of the project, which is the opposite of its job."""
    try:
        return bridge.load_json(path), True
    except Exception as exc:
        out.append(finding("[HIGH]", check, f"{Path(path).name} is not readable JSON: {exc}", False))
        return {}, False


def finding(severity, check, text, fixable=False):
    return {"severity": severity, "check": check, "finding": text, "auto_fixable": fixable}


def detect_state(ws):
    """uninitialised | partial | installed. Never raises: a file this cannot parse is a *finding*,
    and a diagnosis that dies before classifying reports nothing at all."""
    provenance = ws / init_bridge.PROVENANCE
    try:
        owned = bool(bridge.inventory_enumerate(ws))
    except Exception:
        owned = True          # unreadable registrations mean something is installed, badly
        return "partial"
    configured = (ws / config_mod.CONFIG_FILENAME).is_file()
    memory = any(bridge.md_block_has(bridge.read_text_verbatim(ws / n), "memory")
                 or bridge.md_block_has(bridge.read_text_verbatim(ws / n), "import")
                 for n in MEMORY_FILES)
    if not (owned or configured or memory or provenance.is_file()):
        return "uninitialised"
    if not provenance.is_file():
        return "partial"
    try:
        record = bridge.load_json(provenance)
    except Exception:
        return "partial"
    # `all()` over an empty list is vacuously true, so the target *set* is checked as well as each
    # entry — a record naming nothing would otherwise read as a complete restore source.
    # Compared by *name*, not absolute path: the record was written under the path init was given,
    # and this command resolves symlinks — on macOS `/var` and `/private/var` name one directory and
    # would never compare equal.
    # Workspace-*relative* paths: basenames let an entry at an unrelated location satisfy the set,
    # and comparing absolutes fails on macOS where `/var` and `/private/var` name one directory.
    def relative(raw):
        try:
            return str(Path(raw).resolve().relative_to(ws))
        except (ValueError, OSError):
            return raw

    expected = set(init_bridge.TARGETS)
    targets = record.get("targets") if isinstance(record, dict) else None
    if (not isinstance(record, dict) or record.get("schema") != bridge.SCHEMA
            or not isinstance(targets, list) or len(targets) != len(expected)
            or not all(init_bridge._valid_target(t) for t in targets)
            or {relative(t["path"]) for t in targets} != expected):
        return "partial"
    return "installed"


#: Sentinels that legitimately live in one store only. Everything else must appear in both.
TOML_ONLY_SENTINELS = (mcp_pin.SERVER_NAME,)


def check_bridge(ws, out):
    try:
        names = bridge.inventory_enumerate(ws)
    except Exception as exc:
        out.append(finding("[HIGH]", "sentinels", f"registrations are unreadable: {exc}", False))
        names = []
    mcp, _ = safe_json(ws / ".mcp.json", out, "sentinels")
    toml = bridge.read_text_verbatim(ws / ".codex" / "config.toml")
    # grill S4 (vibe-191): no `vibe-suite` binary ships, so no `vibe-mcp` registration is expected
    # and its absence is healthy. One that names the bare `vibe-suite` command is dangling (an
    # earlier revision wrote it; a host would resolve the name on PATH) — repair removes it.
    for rel in init_bridge.dangling_registrations(ws):
        out.append(finding("[MEDIUM]", "sentinels",
                           f"{rel} carries a dangling registration of the bare "
                           f"`{init_bridge.BARE_COMMAND}` command (no such binary ships) — "
                           "repair removes it", True))
    for name in names:
        # The enumerator unions the two stores, so a name registered in one and missing from the
        # other is invisible unless both are asked separately.
        in_json = bridge.json_server_has(mcp, name)
        in_toml = name in bridge.toml_owned_names(toml)
        # Not every sentinel is bidirectional. `vibe-claude-mcp` is the *reverse* server — the pinned
        # package through which Codex delegates back to Claude — so it lives in `.codex/config.toml`
        # alone. Requiring symmetry here would make a successful `/vibe-suite:update` report a defect.
        if name in TOML_ONLY_SENTINELS:
            continue
        if in_json != in_toml:
            where = ".mcp.json" if in_json else ".codex/config.toml"
            out.append(finding("[MEDIUM]", "sentinels",
                               f"{name} is registered only in {where}", True))
    hooks, _ = safe_json(ws / ".codex" / "hooks.json", out, "hooks")
    for name in MEMORY_FILES:
        text = bridge.read_text_verbatim(ws / name)
        if not text:
            out.append(finding("[MEDIUM]", "memory", f"{name} is missing", True))
        elif not (bridge.md_block_has(text, "memory") or bridge.md_block_has(text, "import")):
            out.append(finding("[MEDIUM]", "memory", f"{name} carries no owned block", True))
    if not bridge.text_block_has(bridge.read_text_verbatim(ws / ".gitignore"), "ignore"):
        out.append(finding("[LOW]", "gitignore", ".gitignore carries no owned block", True))
    # grill S4: no owned Stop hook is registered until the binary that would serve it ships, so
    # its absence is healthy; an owned entry that IS present is checked below.
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
    record, ok = safe_json(ws / init_bridge.PROVENANCE, out, "pins")
    if not ok:
        return None
    recorded = record.get("plugin_version") if isinstance(record, dict) else None
    if recorded is None:
        # An install predating this field is not a defect in the project. Reported as a capability
        # by the caller, so a clean older workspace still reaches [GOOD].
        return "no-version-recorded"
    manifest = bridge.load_json(HERE.parent / ".claude-plugin" / "plugin.json").get("version")
    if manifest and recorded != manifest:
        out.append(finding("[MEDIUM]", "pins",
                           f"installed under plugin {recorded}; this plugin is {manifest}", False))


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
                           False))
    # Rows 4, 7, 8 and 10 already have a read-only supplier; reimplementing them would be a second
    # opinion on a question E0.8 already answers.
    survey = HERE / "migrate" / "survey.sh"
    if survey.is_file():
        try:
            result = subprocess.run(["bash", str(survey), "--workspace", str(ws)],
                                    capture_output=True, text=True, timeout=60)
            for item in (json.loads(result.stdout or "{}").get("findings") or []):
                out.append(finding("[LOW]", f"legacy-row-{item['row']}",
                                   f"{item.get('kind', 'detected')}: {item.get('path', '')}".strip(),
                                   False))
        except Exception as exc:
            out.append(finding("[LOW]", "legacy-survey", f"survey did not complete: {exc}", False))
    for candidate in (".cc-suite-state", ".codex-toolkit-state"):
        if (ws / candidate / "state.json").is_file():
            out.append(finding("[LOW]", "legacy-state",
                               f"{candidate}/ holds legacy state; only stopReviewGate migrates",
                               False))
    mcp, _ = safe_json(ws / ".mcp.json", out, "legacy-sentinels")
    toml = bridge.read_text_verbatim(ws / ".codex" / "config.toml")
    legacy = [n for n in (mcp.get("mcpServers") or {}) if n.startswith("cc-suite-")]
    # The vibe-only enumerator cannot see cc-suite names, so TOML headers are read directly.
    legacy += [h.strip().strip('"').strip("'").split(".")[0]
               for h in re.findall(r"^\s*\[mcp_servers\.(.+?)\]\s*$", toml, re.M)
               if h.strip().strip('"').strip("'").startswith("cc-suite-")]
    if legacy:
        out.append(finding("[MEDIUM]", "legacy-sentinels",
                           f"legacy sentinels still registered: "
                           f"{', '.join(sorted(set(legacy)))}; §7A row 6 needs explicit "
                           f"confirmation, so /vibe-suite:init migrates them", False))


def check_mirror_staleness(plugin_root, findings, capabilities):
    """E7.2 (vibe-54): live when the plugin ships its hash manifest; the absent-manifest
    state stays a capability row (an installation fact, not a defect). Read-only — the
    comparison is delegated to the one reader, bin/vibe-check --mirrors."""
    import subprocess
    plugin_root = Path(plugin_root)
    if not (plugin_root / "codex" / "MIRROR-MANIFEST.json").is_file():
        capabilities.append({"check": "mirror-staleness", "status": "unavailable",
                             "blocked_on": "the plugin ships no codex/MIRROR-MANIFEST.json — "
                                           "regenerate via /vibe-suite:bridge mirrors"})
        return
    try:
        proc = subprocess.run(
            [sys.executable, str(plugin_root / "bin" / "vibe-check"), str(plugin_root),
             "--mirrors"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        findings.append(finding("[HIGH]", "mirror-staleness",
                                f"mirror check could not run: {exc}", False))
        return
    if proc.returncode == 0:
        return
    detail = (proc.stdout or proc.stderr or "").strip().replace("\n", "; ")[:400]
    findings.append(finding(
        "[HIGH]", "mirror-staleness",
        f"the codex/ mirror disagrees with its manifest: {detail} — regenerate via "
        "/vibe-suite:bridge mirrors (or python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/"
        "mirror-sync.py\" generate --root \"${CLAUDE_PLUGIN_ROOT}\")", False))


def check_retired_names(plugin_root, out):
    """F1.7: no retired command name may appear in any runtime string.

    Read-only, and scoped to the surface E2.6 ships — the sweep over the whole corpus, plus its CI
    enforcement, is E7.3's. A predicate nothing calls is not a delivered check, so this runs here.
    """
    for rel, names in retired_names.scan_update_surface(plugin_root):
        out.append(finding("[MEDIUM]", "retired-names",
                           f"{rel} carries retired namespaces: {', '.join(names)}", False))


def check_advisors(ws, out):
    """Advisor registration state (E6.1; vibe-185). A stamped definition whose registration drifted
    is auto-fixable — a no-prompt `/vibe-suite:repair` runs the same flag-less `reconcile` — but a
    definition the operator never registered, registered before stamps existed, or edited since
    registering needs the operator: `/vibe-suite:advisor add <name>`. An unreadable inventory and
    an invalid registration need a human."""
    import advisors
    try:
        for row in advisors.list_advisors(ws):
            registration = row.get("registration")
            if registration == "changed":
                out.append(finding("[MEDIUM]", "advisor-state",
                                   f"advisor '{row['name']}' changed since it was registered; it is held, "
                                   "its store content left unchanged — re-confirm with "
                                   f"/vibe-suite:advisor add {row['name']}", False))
                continue
            if registration == "unregistered" and row["state"] == "declared-unregistered":
                out.append(finding("[LOW]", "advisor-state",
                                   f"advisor '{row['name']}' is declared but not registered; register it "
                                   f"with /vibe-suite:advisor add {row['name']} (init never registers)", False))
                continue
            if registration == "unstamped":
                out.append(finding("[MEDIUM]", "advisor-state",
                                   f"advisor '{row['name']}' is unstamped (registered without a registration "
                                   "stamp, before vibe-185); it is held, its store content left unchanged — "
                                   f"confirm it with /vibe-suite:advisor add {row['name']}", False))
                continue
            if row["state"] == "consistent":
                continue
            if row["state"] == "invalid-registration":
                out.append(finding("[HIGH]", "advisor-state",
                                   f"advisor '{row['name']}' is invalid-registration "
                                   f"({row.get('detail')}); repair cannot guess a target — pass "
                                   "--pin via /vibe-suite:advisor, or fix the registration",
                                   False))
                continue
            out.append(finding("[MEDIUM]", "advisor-state",
                               f"advisor '{row['name']}' is {row['state']}; "
                               "/vibe-suite:repair reconciles registrations to definitions",
                               True))
    except bridge.BridgeError as exc:
        out.append(finding("[HIGH]", "advisor-state",
                           f"advisor inventory unreadable: {exc}", False))


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


PROSE_FRESHNESS = re.compile(r"\*\*Spec freshness:\*\*.*?(\d{4}-\d{2}-\d{2})")


def _valid_refresh_date(value):
    """Exactly the dashed YYYY-MM-DD calendar form. fromisoformat alone also admits
    YYYYMMDD, so the regex pins the shape and fromisoformat rejects impossible dates."""
    if not (isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _staler_path(skill_md, refreshed):
    """F8.4: recommend whichever of the two refresh paths is staler. The comparison is the
    record date against the overlay's canonical prose line (spec-sync's pinned format);
    an unparseable prose line degrades to no recommendation rather than a guess."""
    try:
        match = PROSE_FRESHNESS.search(skill_md.read_text(encoding="utf-8"))
    except OSError:
        match = None
    if not match:
        return "—"
    prose = match.group(1)
    if prose < refreshed:
        return f"staler path: /vibe-suite:spec-sync (prose {prose} < record {refreshed})"
    if refreshed < prose:
        return (f"staler path: /vibe-suite:refresh-knowledge "
                f"(record {refreshed} < prose {prose})")
    return "—"


def knowledge_capability(out):
    """F8.4's date is plugin-level, beside the skill it describes — a project-local copy would let
    two projects disagree about one shared skill. /vibe-suite:refresh-knowledge (E6.5/#51)
    writes it. Returns a capability row (has "status") for the no-record and valid states,
    a finding for every malformed record, and diagnose routes by shape."""
    root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", HERE.parent))
    for candidate in (root / "skills").glob("*/refreshed.json"):
        try:
            record = bridge.load_json(candidate)
        except Exception:
            record = None
        refreshed = record.get("refreshed") if isinstance(record, dict) else None
        if not _valid_refresh_date(refreshed):
            return finding("[LOW]", "knowledge-freshness",
                           f"{candidate.name} carries no readable date", False)
        return {"check": "knowledge-freshness", "status": f"refreshed {refreshed}",
                "blocked_on": _staler_path(candidate.parent / "SKILL.md", refreshed)}
    return {"check": "knowledge-freshness", "status": "unavailable",
            "blocked_on": "never refreshed — /vibe-suite:refresh-knowledge (E6.5/#51) "
                          "writes skills/<skill>/refreshed.json"}


def diagnose(ws):
    ws = Path(ws).resolve()
    state = detect_state(ws)
    findings, capabilities, pin_status = [], [], None

    check_legacy(ws, findings)
    if state == "uninitialised":
        # The missing-component cascade is suppressed — every bridge target is expected to be
        # absent. Legacy detection above still ran, because a project holding a legacy store needs
        # that reported precisely *because* it has not been migrated.
        findings.append(finding("[MEDIUM]", "not-initialised",
                                "vibe-suite is not installed here; run /vibe-suite:init", False))
    else:
        check_bridge(ws, findings)
        check_symlinks(ws, findings)
        pin_status = check_pins(ws, findings)
        check_config(ws, findings)
        check_provenance(ws, state, findings)
        check_advisors(ws, findings)
    check_retired_names(HERE.parent, findings)

    if state != "uninitialised" and pin_status == "no-version-recorded":
        capabilities.append({"check": "pins", "status": "unavailable",
                             "blocked_on": "this workspace was installed before provenance "
                                           "recorded a plugin version"})
    for check, blocked in UNAVAILABLE:
        capabilities.append({"check": check, "status": "unavailable", "blocked_on": blocked})
    check_mirror_staleness(
        Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or HERE.parent),
        findings, capabilities)
    knowledge = knowledge_capability(findings)
    if isinstance(knowledge, dict) and "status" in knowledge:
        capabilities.append(knowledge)
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
