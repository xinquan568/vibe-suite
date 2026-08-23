#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Bridge sub-operations for `/vibe-suite:bridge` (E2.5 / vibe-22, F1.6).

**Secrets cross by allowlist, not by redaction.** Every `.mcp.json` server `env` *value* is withheld;
variable *names* cross as commented placeholders, which is why `bearer_token_env_var` appears — it
names a variable rather than holding one. A redacted value would still put the secret's shape in a
second file the user did not choose.

**A variable name crosses only if it is one** (grill S5 / vibe-192): the placeholder is a `#` comment
line in the owned block, and a "name" carrying a newline would end the comment and put whatever
follows — a table header, a key, a forged closing marker — into the block as live TOML. A name
outside `[A-Za-z0-9_]` (the portable environment-variable character set) is refused by name before
anything is written, and `.codex/config.toml` is left untouched.

**Three hook namespaces, and this mirrors the third**: not the plugin's own `hooks/hooks.json`, not
the owned `Stop` entry `init` writes, but the *project's* hooks in `.claude/settings.json`.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402

#: The events both tools have. Claude-only events are skipped rather than mirrored into a runtime
#: that would never fire them.
SHARED_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop")

SIDE_FILE = ".codex/hooks.vibe-suite.json"


#: The portable environment-variable character set. A `.mcp.json` env *name* outside it is not
#: mirrored — not quoted, not skipped: the whole mcp mirror is refused by name and nothing is written.
ENV_NAME_RE = re.compile(r"[A-Za-z0-9_]+")


def _refuse_unsafe_env_names(servers):
    """Raise `bridge.BridgeError` naming the first server/variable whose env name is not a name.

    Runs over every server the mirror loop would render — the loop's own exclusions (a `cc-suite-*`
    name, a non-dict spec, our own registration, an advisor-owned entry) apply here first — BEFORE
    any line of the block is rendered, so a refusal leaves `.codex/config.toml` byte-identical,
    never a half-written block. The offending name is shown `repr`-escaped, on one line: it may
    carry the very newline the rule exists to keep out of the file."""
    for name, spec in sorted(servers.items()):
        # the same exclusions as the mirror loop below: a server the loop would never render
        # cannot refuse the leg (an advisor-owned entry has one writer — the advisor path)
        if not isinstance(spec, dict) or name.startswith("cc-suite-") or spec.get("command") == "vibe-suite":
            continue
        if bridge.advisor_owned_entry(spec):
            continue
        env = spec.get("env")
        if not isinstance(env, dict):
            continue
        for var in env:
            if not isinstance(var, str) or not ENV_NAME_RE.fullmatch(var):
                raise bridge.BridgeError(
                    f"mcp: refused — server {name!r} declares an env variable name that is not a "
                    f"name ({var!r}: only [A-Za-z0-9_] may cross into the owned TOML block); "
                    ".codex/config.toml left unchanged")


def _toml_key(name):
    """A TOML key. Bare only for ASCII alphanumerics, `-` and `_`; anything else is a quoted basic
    string escaped by `json.dumps`, whose escaping is a superset of TOML's — so a quote, backslash,
    newline or control character cannot close the key and inject content outside our block."""
    if name and all(c.isascii() and (c.isalnum() or c in "-_") for c in name):
        return name
    return json.dumps(name)


def _toml_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        # TOML has no nan/inf literal; such a value is not mirrored as a number.
        return json.dumps(str(value))
    return json.dumps(str(value))


def _name_repeats_a_value(name, env):
    """Whether a server's name carries one of its own env values.

    The name is the one field that must cross for the mirror to mean anything, so it is the one place
    a value comparison is still needed. It is bounded to that server's own env — a small closed set —
    rather than poisoning the whole document, which is what made the general rule unworkable.
    """
    def leaves(node):
        if isinstance(node, dict):
            for v in node.values():
                yield from leaves(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                yield from leaves(v)
        elif node is not None and not isinstance(node, bool):
            yield str(node)

    return any(v and v in name for v in leaves(env))


def mirror_mcp(ws, report):
    """`.mcp.json` → a `config.toml` sentinel block.

    **A server that declares `env` contributes only names.** Its own name and its variable names
    cross; `command` and `args` do not.

    That rule is structural, and it replaces three iterations of trying to *recognise* a secret.
    Recognition cannot work: poisoning every value means a two-character `env` entry like `on`
    withholds every occurrence of those characters and the mirror renders nothing, while any length
    floor lets a genuinely short credential through. Nothing in the input distinguishes a short
    credential from a short flag, so no threshold satisfies both — and case folding, Unicode
    normalisation and encoding variants each add an unbounded space to compare against.

    Declaring `env` is the one signal the file actually gives about which servers handle secrets. A
    server without it is mirrored in full; a server with it is named, and the user is told where the
    rest lives. The guarantee then holds without anyone having to identify a credential.
    """
    doc = bridge.load_json(ws / ".mcp.json")
    servers = doc.get("mcpServers") or {}
    _refuse_unsafe_env_names(servers)   # before the first rendered line: a refusal writes nothing
    lines, reduced = [], 0
    for name, spec in sorted(servers.items()):
        if name.startswith("cc-suite-") or not isinstance(spec, dict):
            continue
        if spec.get("command") == "vibe-suite":
            continue                      # mirroring our own registration would recurse
        if bridge.advisor_owned_entry(spec):
            # Advisors have one writer: the advisor path registers them in BOTH stores in full
            # (E6.1). Mirroring one here would emit a names-only copy of an entry the owner
            # already wrote — a duplicate table or a stripped registration, depending on order.
            continue
        env = spec.get("env")
        declares_env = bool(env)
        if declares_env and _name_repeats_a_value(name, env):
            lines.append("# a server was not mirrored: its name repeats one of its own env values")
            lines.append("")
            reduced += 1
            continue
        lines.append(f"[mcp_servers.{_toml_key(name)}]")
        if declares_env:
            reduced += 1
            lines.append("# this server declares env, so only names are mirrored — see .mcp.json")
        else:
            command = spec.get("command")
            if isinstance(command, str) and command:
                lines.append(f"command = {_toml_scalar(command)}")
            args = spec.get("args")
            if isinstance(args, list):
                scalars = [a for a in args if isinstance(a, (str, int, float, bool))]
                lines.append("args = [" + ", ".join(_toml_scalar(a) for a in scalars) + "]")
                if len(scalars) != len(args):
                    lines.append("# some args were not scalars and were not mirrored")
        names = sorted(k for k in env if isinstance(k, str)) if isinstance(env, dict) else []
        for var in names:
            # The variable's name crosses so the user knows what to set. Its value never does.
            lines.append(f"# env: {var} (value not mirrored — set it in your own environment)")
        lines.append("")
    body = "\n".join(lines).rstrip() or "# no project MCP servers to mirror"
    dest = ws / ".codex" / "config.toml"
    existing = bridge.read_text_verbatim(dest)
    updated = bridge.text_block_upsert(existing, "mcp-mirror", body)
    if updated != existing:
        bridge.write_atomic(ws, dest, updated)
    report.append(f"mcp: mirrored {len(servers)} server(s)"
                  + (f"; {reduced} declare env, so only names crossed" if reduced else ""))


def _side_file_is_ours(side):
    """Whether the hook side file is one we wrote.

    It was treated as owned on its *name*: a pre-existing file there was overwritten, and — worse —
    unlinked outright when the mirror was no longer needed. A symlink is never ours, and neither is
    a document without our stamp.
    """
    if side.is_symlink():
        return False
    if not side.exists():
        return True   # nothing there; we may create it
    doc = bridge.load_json(side)
    return isinstance(doc, dict) and doc.get("vibe_suite_owned") is True


def mirror_hooks(ws, report):
    """The *project's* Claude hooks → `.codex/hooks.json`, preserving the owned entry."""
    settings = bridge.load_json(ws / ".claude" / "settings.json")
    project = settings.get("hooks") or {}
    shared = {e: project[e] for e in SHARED_EVENTS if e in project}
    skipped = sorted(set(project) - set(SHARED_EVENTS))

    dest = ws / ".codex" / "hooks.json"
    doc = bridge.load_json(dest)
    hooks = doc.get("hooks") or {}
    owned = [e for e in hooks.values() for e in (e or [])
             if isinstance(e, dict) and e.get(f"_{bridge.MARKER}_owned") is not None]
    def ours(entry):
        return isinstance(entry, dict) and (
            entry.get(f"_{bridge.MARKER}_owned") is not None
            or entry.get(f"_{bridge.MARKER}_mirrored") is not None)

    # Mirrored entries are marked, so a second run recognises its own work instead of mistaking it
    # for the user's and falling back to a side file it does not need.
    user_content = any(not ours(entry)
                       for entries in hooks.values() for entry in (entries or []))

    marked = {e: [dict(x, **{f"_{bridge.MARKER}_mirrored": 1}) for x in v if isinstance(x, dict)]
              for e, v in shared.items()}
    if user_content:
        # The target is the user's. A side file mirrors without touching what they wrote.
        payload = json.dumps({"hooks": marked, "vibe_suite_owned": True},
                             indent=2, sort_keys=True) + "\n"
        side = ws / SIDE_FILE
        if not _side_file_is_ours(side):
            report.append(f"hooks: {SIDE_FILE} exists and is not ours — left alone, not mirrored")
            return
        if not side.is_file() or side.read_text(encoding="utf-8") != payload:
            bridge.write_atomic(ws, side, payload)
        report.append(f"hooks: {len(shared)} event(s) mirrored to {SIDE_FILE} "
                      "(the target holds your own entries)")
    else:
        side = ws / SIDE_FILE
        if side.is_file() and _side_file_is_ours(side):
            # The fallback existed because the target was the user's; it no longer is. Leaving it
            # behind would let two mirrors drift apart with nothing saying which one is live.
            bridge.unlink_at(ws, SIDE_FILE)
            report.append(f"hooks: removed {SIDE_FILE} — the target is no longer user-owned")
        merged = dict(marked)
        for entries in hooks.values():
            for entry in entries or []:
                if isinstance(entry, dict) and entry.get(f"_{bridge.MARKER}_owned") is not None:
                    merged.setdefault("Stop", []).append(entry)
        # Preserve any top-level key that is not `hooks` — the file is not ours alone.
        out = {k: v for k, v in doc.items() if k != "hooks"}
        out["hooks"] = merged
        updated = json.dumps(out, indent=2, sort_keys=True) + "\n"
        if updated != (dest.read_text(encoding="utf-8") if dest.is_file() else ""):
            bridge.write_atomic(ws, dest, updated)
        report.append(f"hooks: {len(shared)} event(s) mirrored, "
                      f"{len(owned)} owned entr(y/ies) preserved")
    if skipped:
        report.append(f"hooks: skipped Claude-only event(s): {', '.join(skipped)}")


def _open_parent(ws, rel):
    """The audited descent, from the module that owns it.

    This was a second copy of `bridge._open_dir_chain` — and a copy of a safety rule drifts from the
    original, which is how this codebase kept guarding one writer while another went unguarded.
    """
    # `link_skills` runs this as a preflight before `symlink_at` creates the link; on a fresh
    # workspace the preflight is what brings `.claude/skills/` and `.agents/` into existence, and a
    # refusal here skips the link — so the parent chain is created on purpose now that the descent
    # no longer does it implicitly (vibe-179).
    return bridge.open_dir_chain(ws, Path(rel).parent.parts, create=True)


def _link_mirror_skills(ws, report, plugin_root):
    """E7.2 (vibe-54): `.agents/skills` as a REAL directory of per-skill links into the
    plugin's generated `codex/skills` — one-level discovery depth, user entries preserved
    beside ours, ownership per link. The exact legacy owned symlink (`../.claude/skills`)
    is migrated: replaced by the directory form, with per-skill links to
    `../../.claude/skills/<name>` for skills the legacy link previously exposed so nothing
    reachable disappears. Any other `.agents/skills` shape is the user's — refused."""
    mirror = Path(plugin_root) / "codex" / "skills"
    skills_dir = ws / ".agents" / "skills"
    legacy_exposed = []
    if skills_dir.is_symlink():
        if os.readlink(skills_dir) == "../.claude/skills":
            claude_skills = ws / ".claude" / "skills"
            if claude_skills.is_dir():
                legacy_exposed = sorted(p.name for p in claude_skills.iterdir()
                                        if p.is_dir() and p.name != "vibe-suite")
            bridge.unlink_at(ws, ".agents/skills")
            report.append("skills: migrated legacy .agents/skills symlink to directory form")
        else:
            report.append(f"skills: .agents/skills points at {os.readlink(skills_dir)} — "
                          "refused, not replaced")
            return
    bridge.ensure_dir_at(ws, ".agents")
    bridge.ensure_dir_at(ws, ".agents/skills")
    for d in sorted(p for p in mirror.iterdir() if p.is_dir()):
        entry = skills_dir / d.name
        target = d
        if entry.is_symlink():
            if os.readlink(entry) == str(target):
                continue
            report.append(f"skills: .agents/skills/{d.name} points elsewhere — refused")
            continue
        if entry.exists():
            report.append(f"skills: .agents/skills/{d.name} is the user's — refused")
            continue
        bridge.symlink_at(ws, f".agents/skills/{d.name}", target)
        report.append(f"skills: .agents/skills/{d.name} → {target}")
    for name in legacy_exposed:
        entry = skills_dir / name
        if entry.exists() or entry.is_symlink():
            continue
        bridge.symlink_at(ws, f".agents/skills/{name}",
                          Path("../../.claude/skills") / name)
        report.append(f"skills: .agents/skills/{name} → ../../.claude/skills/{name} "
                      "(legacy exposure preserved)")


def link_skills(ws, report, plugin_root):
    """The plugin link leaves the project by design; `.agents/skills` does not. With a
    generated mirror present, `.agents/skills` takes the per-skill directory form
    (see _link_mirror_skills); without one, the legacy whole-tree link stands."""
    if (Path(plugin_root) / "codex" / "skills").is_dir():
        pairs = ((".claude/skills/vibe-suite", Path(plugin_root) / "skills"),)
    else:
        pairs = ((".claude/skills/vibe-suite", Path(plugin_root) / "skills"),
                 (".agents/skills", Path("../.claude/skills")))
    for rel, target in pairs:
        path = ws / rel
        try:
            # Opened as a preflight (and, on a fresh workspace, created): the parent is validated
            # through the audited descent here; `symlink_at` below reopens it through the same
            # descent to create the link.
            parent_fd = _open_parent(ws, rel)
        except bridge.BridgeError as exc:
            report.append(f"skills: {rel} refused — {exc}")
            continue
        if path.is_symlink():
            if os.readlink(path) == str(target):
                report.append(f"skills: {rel} already correct")
                os.close(parent_fd)
                continue
            # A link pointing somewhere else is the user's decision, not ours to overwrite.
            report.append(f"skills: {rel} points at {os.readlink(path)} — refused, not replaced")
            os.close(parent_fd)
            continue
        elif path.exists():
            report.append(f"skills: {rel} is a real path — left alone")
            os.close(parent_fd)
            continue
        os.close(parent_fd)
        try:
            if bridge.symlink_at(ws, rel, target):
                report.append(f"skills: {rel} → {target}")
            else:
                report.append(f"skills: {rel} appeared concurrently — left as it is")
        except (OSError, bridge.BridgeError) as exc:
            report.append(f"skills: {rel} could not be linked ({exc})")
    if (Path(plugin_root) / "codex" / "skills").is_dir():
        try:
            _link_mirror_skills(ws, report, plugin_root)
        except (OSError, bridge.BridgeError) as exc:
            report.append(f"skills: mirror wiring failed ({exc})")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="/vibe-suite:bridge")
    parser.add_argument("subcommand", nargs="?", default="all",
                        choices=["skills", "hooks", "mcp", "mirrors", "all"])
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--plugin-root", default=os.environ.get("CLAUDE_PLUGIN_ROOT", ""))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ws = Path(args.workspace).resolve()

    report, wanted = [], args.subcommand
    try:
        if wanted in ("skills", "all"):
            link_skills(ws, report, args.plugin_root or HERE.parent)
        if wanted in ("hooks", "all"):
            mirror_hooks(ws, report)
        if wanted in ("mcp", "all"):
            mirror_mcp(ws, report)
        if wanted in ("mirrors", "all"):
            # E7.2 (vibe-54): regenerate the plugin's codex/ mirror at the PLUGIN ROOT —
            # never the user workspace. A missing generator or failing run is loud.
            plugin_root = Path(args.plugin_root or HERE.parent)
            gen = plugin_root / "scripts" / "mirror-sync.py"
            if not gen.is_file():
                print(f"error: mirrors: generator not found at {gen}", file=sys.stderr)
                return 1
            proc = subprocess.run(
                [sys.executable, str(gen), "generate", "--root", str(plugin_root)],
                capture_output=True, text=True)
            if proc.returncode != 0:
                print(f"error: mirrors: regeneration failed — {proc.stderr.strip()}",
                      file=sys.stderr)
                return 1
            report.append(f"mirrors: regenerated at {plugin_root} "
                          f"({proc.stdout.strip() or 'ok'})")
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"steps": report}, indent=2) if args.json else "\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
