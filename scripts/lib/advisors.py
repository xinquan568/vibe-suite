#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Advisor lifecycle for `/vibe-suite:advisor` (E6.1 / vibe-47; F7.1, F7.2).

**One engine, four states.** `add` and `remove` are desired-state edits — a definition file
appears or disappears under `.vibe-suite/agents/` — followed by `reconcile()`, which converges the
two MCP stores to the definitions. `init`, `repair` and `update` call the same `reconcile`, so
there is exactly one code path that writes an advisor registration, whatever invoked it. Each
advisor is classified `consistent`, `declared-unregistered`, `half-registered`, or
`registered-undeclared`; the first three converge toward registration, the last removes the
orphaned registration and never touches definitions or timelines.

**Identity is the bare name; ownership is structural.** The agent-design skill promises the
callable `mcp__<name>__<tool_name>`, which requires the server key to *be* the advisor name — so
ownership travels inside the entry (`bridge.ADVISOR_MARKER`) on the JSON side and in the
`vibe-suite:server:<name>` fence on the TOML side, and `bridge.owned_names` /
`bridge.toml_owned_names` recognize both. A name held by anything unowned is a collision to
refuse, never to adopt (the `mcp_pin.collision` posture).

**Sentinel-clean means byte-clean where bytes can be promised.** The TOML fence codec is its own
exact inverse. `.mcp.json` writes are canonical (`init_bridge._upsert_json`'s contract), so the
first owned mutation ledgers the file's exact pre-image bytes
(`.vibe-suite-state/advisor-preimages.json`, the install-provenance pattern); a removal that
leaves zero owned entries restores those bytes verbatim when the parsed remainder still matches —
and falls back to the canonical form, reporting the divergence, when the user edited in between.

**Backend.** A registration executes the pinned `claude-octopus`. Resolution order: an explicit
exact `--pin` (the P9 escape hatch, validated by `mcp_pin`'s grammar) → the shipped pin file via
`mcp_pin.resolve_pin` → refusal naming both remedies while the pin is `pending` (E7.1 owns it).
No path floats.
"""

import json
import os
import re
from pathlib import Path

import bridge
import mcp_pin

AGENTS_REL = Path(".vibe-suite/agents")
LEDGER_REL = Path(".vibe-suite-state/advisor-preimages.json")
MCP_REL = Path(".mcp.json")
TOML_REL = Path(".codex/config.toml")

TIERS = ("opus", "sonnet", "haiku")
PROMPT_MODES = ("append", "replace")
PERMISSION_MODES = ("default", "acceptEdits", "plan", "dontAsk", "auto", "bypassPermissions")
EFFORTS = ("low", "medium", "high", "max")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

IGNORE_BLOCK = "advisor-ignore"
IGNORE_BODY = ".vibe-suite/agents/*/timeline/"


class AdvisorError(bridge.BridgeError):
    """Refusal. Nothing has been written."""


def is_owned_entry(entry):
    return bridge.advisor_owned_entry(entry)


def timeline_rel(name):
    return AGENTS_REL / name / "timeline"


# --------------------------------------------------------------------------------------------
# Definition files
# --------------------------------------------------------------------------------------------

def _parse_frontmatter(text, source):
    """The advisor frontmatter subset: scalars, `|` literal blocks, flow lists. No yaml module —
    the runtime is stdlib-only, and the grammar the skill documents needs nothing more."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AdvisorError(f"{source}: no frontmatter block (--- expected on line 1)")
    fields, i = {}, 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            body = "\n".join(lines[i + 1:]).lstrip("\n")
            return fields, body
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if not m:
            raise AdvisorError(f"{source}: unparseable frontmatter line {i + 1}: {line!r}")
        key, value = m.group(1), m.group(2).strip()
        if value == "|":
            block, i = [], i + 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith("  ")):
                if lines[i].strip() == "---":
                    break
                block.append(lines[i][2:] if lines[i].startswith("  ") else "")
                i += 1
            fields[key] = "\n".join(block).rstrip("\n")
            continue
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            fields[key] = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
        else:
            fields[key] = value.strip("'\"")
        i += 1
    raise AdvisorError(f"{source}: frontmatter never closed (missing trailing ---)")


def parse_definition(text, filename):
    """Validate a definition against the agent-design skill's field table; apply exact defaults."""
    stem = filename[:-3] if filename.endswith(".md") else filename
    fields, body = _parse_frontmatter(text, filename)
    name = fields.get("name", stem)
    if not NAME_RE.match(name or ""):
        raise AdvisorError(f"{filename}: advisor name {name!r} is not a valid MCP server key")
    description = (fields.get("description") or "").strip()
    if not description:
        raise AdvisorError(f"{filename}: description is required")
    model = fields.get("model")
    if model is not None and model not in TIERS:
        raise AdvisorError(
            f"{filename}: model {model!r} is not a tier alias {TIERS}; versioned model ids are "
            "banned in shipped artifacts (P9)")
    prompt_mode = fields.get("prompt_mode", "append")
    if prompt_mode not in PROMPT_MODES:
        raise AdvisorError(f"{filename}: prompt_mode {prompt_mode!r} not in {PROMPT_MODES}")
    permission_mode = fields.get("permission_mode", "default")
    if permission_mode not in PERMISSION_MODES:
        raise AdvisorError(f"{filename}: permission_mode {permission_mode!r} not in "
                           f"{PERMISSION_MODES}")
    effort = fields.get("effort")
    if effort is not None and effort not in EFFORTS:
        raise AdvisorError(f"{filename}: effort {effort!r} not in {EFFORTS}")
    try:
        max_turns = int(fields.get("max_turns", 5))
    except ValueError:
        raise AdvisorError(f"{filename}: max_turns must be an integer") from None
    allowed = fields.get("allowed_tools", ["Read", "Grep", "Glob"])
    disallowed = fields.get("disallowed_tools", [])
    if not body.strip():
        raise AdvisorError(f"{filename}: the body (system prompt) is empty")
    return {
        "name": name,
        "description": description,
        "tool_name": fields.get("tool_name", f"{name}_consult"),
        "model": model,
        "allowed_tools": list(allowed),
        "disallowed_tools": list(disallowed),
        "permission_mode": permission_mode,
        "max_turns": max_turns,
        "max_budget_usd": fields.get("max_budget_usd"),
        "effort": effort,
        "cwd": fields.get("cwd", "."),
        "additional_dirs": list(fields.get("additional_dirs", [])),
        "prompt_mode": prompt_mode,
        "body": body,
    }


def load_definitions(ws):
    """Every parsed definition under `.vibe-suite/agents/*.md`, keyed by name."""
    out = {}
    agents = Path(ws) / AGENTS_REL
    if not agents.is_dir():
        return out
    for path in sorted(agents.glob("*.md")):
        defn = parse_definition(path.read_text(encoding="utf-8"), path.name)
        if defn["name"] != path.stem:
            raise AdvisorError(f"{path.name}: frontmatter name {defn['name']!r} does not match "
                               "the filename; rename one of them")
        out[defn["name"]] = defn
    return out


# --------------------------------------------------------------------------------------------
# Backend resolution (D-c)
# --------------------------------------------------------------------------------------------

def resolve_backend(explicit_pin, pin_file=None, pending_file=None):
    """`claude-octopus@<exact>` from an explicit pin, else the shipped pin file, else refusal."""
    if explicit_pin is not None:
        if not mcp_pin._EXACT.match(explicit_pin or ""):
            raise AdvisorError(
                f"--pin {explicit_pin!r} is not an exact version; ranges and tags (latest, ^1.2.0,"
                " 1.x) cannot be boot-verified")
        return mcp_pin.target(explicit_pin)
    try:
        status, value = mcp_pin.resolve_pin(pin_file=pin_file, pending_file=pending_file)
    except mcp_pin.PinError as exc:
        raise AdvisorError(str(exc)) from exc
    if status == "pending":
        raise AdvisorError(
            "the claude-octopus pin is not shipped yet (owner: E7.1). Pass --pin <exact version> "
            "to register advisors now; the zero-flag default activates when E7.1 ships the pin")
    return mcp_pin.target(value)


# --------------------------------------------------------------------------------------------
# Registration content
# --------------------------------------------------------------------------------------------

def _advisor_env(defn):
    env = {
        "CLAUDE_SERVER_NAME": defn["name"],
        "CLAUDE_TOOL_NAME": defn["tool_name"],
        "CLAUDE_DESCRIPTION": defn["description"],
        "CLAUDE_TIMELINE_DIR": str(timeline_rel(defn["name"])),
        "CLAUDE_MAX_TURNS": str(defn["max_turns"]),
        "CLAUDE_ALLOWED_TOOLS": ",".join(defn["allowed_tools"]),
    }
    if defn["prompt_mode"] == "replace":
        env["CLAUDE_SYSTEM_PROMPT"] = defn["body"]
    else:
        env["CLAUDE_APPEND_PROMPT"] = defn["body"]
    if defn["model"]:
        env["CLAUDE_MODEL"] = defn["model"]
    if defn["max_budget_usd"] is not None:
        env["CLAUDE_MAX_BUDGET_USD"] = str(defn["max_budget_usd"])
    if defn["disallowed_tools"]:
        env["CLAUDE_DISALLOWED_TOOLS"] = ",".join(defn["disallowed_tools"])
    if defn["permission_mode"] != "default":
        env["CLAUDE_PERMISSION_MODE"] = defn["permission_mode"]
    if defn["effort"]:
        env["CLAUDE_EFFORT"] = defn["effort"]
    if defn["cwd"] != ".":
        env["CLAUDE_CWD"] = defn["cwd"]
    if defn["additional_dirs"]:
        env["CLAUDE_ADDITIONAL_DIRS"] = ",".join(defn["additional_dirs"])
    return env


def json_entry(defn, target):
    """The exact `.mcp.json` registration: bare-name key's entry, marker included."""
    return {
        "command": "npx",
        "args": ["-y", target],
        "env": _advisor_env(defn),
        bridge.ADVISOR_MARKER_KEY: dict(bridge.ADVISOR_MARKER),
    }


def _toml_key(name):
    if name and all(c.isascii() and (c.isalnum() or c in "-_") for c in name):
        return name
    return json.dumps(name)


def toml_body(defn, target):
    """The exact `.codex/config.toml` block body: `render_body`'s timeout discipline plus env."""
    key = _toml_key(defn["name"])
    lines = [
        f"[mcp_servers.{key}]",
        'command = "npx"',
        f'args = ["-y", "{target}"]',
        "startup_timeout_sec = 60",
        "tool_timeout_sec = 900",
        f"[mcp_servers.{key}.env]",
    ]
    for k, v in sorted(_advisor_env(defn).items()):
        lines.append(f"{k} = {json.dumps(str(v))}")
    return "\n".join(lines)


def _entry_target(entry):
    args = entry.get("args") if isinstance(entry, dict) else None
    if isinstance(args, list) and args and isinstance(args[-1], str) \
            and args[-1].startswith(mcp_pin.PACKAGE + "@"):
        return args[-1]
    return None


# --------------------------------------------------------------------------------------------
# Pre-image ledger (byte restoration for the canonicalizing JSON store)
# --------------------------------------------------------------------------------------------

def _load_ledger(ws):
    path = Path(ws) / LEDGER_REL
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _save_ledger(ws, ledger):
    dest = Path(ws) / LEDGER_REL
    if not ledger:
        bridge.unlink_at(ws, LEDGER_REL)
        return
    bridge.write_atomic(ws, dest, json.dumps(ledger, indent=2, sort_keys=True) + "\n")


# --------------------------------------------------------------------------------------------
# Store writers (module-level so a test can inject a failure)
# --------------------------------------------------------------------------------------------

def _write_json_store(ws, doc):
    canonical = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    bridge.write_atomic(ws, Path(ws) / MCP_REL, canonical)


def _write_toml_store(ws, text):
    bridge.write_atomic(ws, Path(ws) / TOML_REL, text)


# --------------------------------------------------------------------------------------------
# Reconcile — the one engine
# --------------------------------------------------------------------------------------------

def _collision_check(defs, doc, toml_text):
    servers = doc.get("mcpServers", {}) if isinstance(doc, dict) else {}
    for name in defs:
        entry = servers.get(name)
        if entry is not None and not is_owned_entry(entry):
            raise AdvisorError(
                f".mcp.json already has an unowned server named {name!r}; rename the advisor or "
                "remove the conflicting entry — nothing has been written")
        if not bridge.toml_server_has(toml_text, name) and re.search(
                r"^\s*\[mcp_servers\.(?:%s|\"%s\")\]\s*$"
                % (re.escape(name), re.escape(name)), toml_text, re.M):
            raise AdvisorError(
                f".codex/config.toml already has an unfenced server named {name!r}; rename the "
                "advisor or remove the conflicting table — nothing has been written")


def reconcile(ws, pin=None, pin_file=None, pending_file=None):
    """Converge both stores to the definitions. Returns `{name: transition}`.

    Backend resolution is lazy: a run whose advisors are all consistent (or removal-only) never
    needs a pin at all.
    """
    ws = Path(ws)
    defs = load_definitions(ws)
    doc = bridge.load_json(ws / MCP_REL)
    toml_path = ws / TOML_REL
    toml_before = bridge.read_text_verbatim(toml_path)
    _collision_check(defs, doc, toml_before)

    servers = doc.setdefault("mcpServers", {})
    toml_text = toml_before
    report = {}
    target_cache = {}

    def target_for(name):
        if name not in target_cache:
            existing = _entry_target(servers.get(name, {}))
            target_cache[name] = existing or resolve_backend(
                pin, pin_file=pin_file, pending_file=pending_file)
        return target_cache[name]

    for name, defn in defs.items():
        in_json = is_owned_entry(servers.get(name))
        in_toml = bridge.toml_server_has(toml_text, name)
        target = target_for(name)
        desired_entry = json_entry(defn, target)
        desired_body = toml_body(defn, target)
        if in_json and in_toml and servers.get(name) == desired_entry \
                and bridge.text_block_has(toml_text, f"server:{name}"):
            current = bridge.text_block_upsert(toml_text, f"server:{name}", desired_body)
            if current == toml_text:
                report[name] = "consistent"
                continue
        state = ("consistent" if in_json and in_toml
                 else "half-registered" if in_json or in_toml
                 else "declared-unregistered")
        servers[name] = desired_entry
        toml_text = bridge.toml_server_upsert(toml_text, name, desired_body)
        report[name] = f"{state}->registered"

    for name in list(servers):
        if is_owned_entry(servers[name]) and name not in defs:
            del servers[name]
            if bridge.toml_server_has(toml_text, name):
                toml_text = bridge.toml_server_remove(toml_text, name)
            report[name] = "registered-undeclared->removed"
    for name in bridge.toml_owned_names(toml_text):
        if name not in defs and name not in bridge.SENTINEL_LITERALS \
                and not name.startswith(bridge.SENTINEL_PREFIX):
            toml_text = bridge.toml_server_remove(toml_text, name)
            report[name] = "registered-undeclared->removed"

    _apply(ws, doc, toml_before, toml_text, defs)
    return report


def _apply(ws, doc, toml_before, toml_after, defs):
    """Write JSON then TOML; roll the first back on a second-store failure; keep the ledger."""
    mcp_path = ws / MCP_REL
    mcp_before = mcp_path.read_bytes() if mcp_path.is_file() else None
    canonical_after = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    json_changed = mcp_before != canonical_after.encode("utf-8")
    toml_changed = toml_after != toml_before

    ledger = _load_ledger(ws)
    owned_left = bridge.owned_names(doc)

    if json_changed and owned_left and str(MCP_REL) not in ledger and mcp_before is not None:
        ledger[str(MCP_REL)] = bridge.record_pre_image(mcp_path)

    restored = False
    if json_changed and not owned_left and str(MCP_REL) in ledger:
        import base64 as _b64
        pre = ledger[str(MCP_REL)]
        pre_bytes = _b64.b64decode(pre.get("content_b64", ""))
        try:
            pre_doc = json.loads(pre_bytes.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            pre_doc = None
        if pre_doc == doc:
            bridge.write_atomic(ws, mcp_path, pre_bytes)
            restored = True
        else:
            print("advisors: .mcp.json diverged from its pre-image while advisors were "
                  "registered; leaving the canonical form", flush=True)
        del ledger[str(MCP_REL)]

    if json_changed and not restored:
        _write_json_store(ws, doc)
    try:
        if toml_changed:
            _write_toml_store(ws, toml_after)
    except BaseException:
        if json_changed and mcp_before is not None:
            bridge.write_atomic(ws, mcp_path, mcp_before)
        elif json_changed:
            bridge.unlink_at(ws, MCP_REL)
        raise
    _save_ledger(ws, ledger)

    gitignore = ws / ".gitignore"
    existing = bridge.read_text_verbatim(gitignore)
    if defs:
        updated = bridge.text_block_upsert(existing, IGNORE_BLOCK, IGNORE_BODY)
        if updated != existing:
            bridge.write_atomic(ws, gitignore, updated)
    elif bridge.text_block_has(existing, IGNORE_BLOCK):
        updated = bridge.text_block_remove(existing, IGNORE_BLOCK)
        if updated.strip():
            bridge.write_atomic(ws, gitignore, updated)
        else:
            bridge.unlink_at(ws, Path(".gitignore"))


# --------------------------------------------------------------------------------------------
# Lifecycle commands
# --------------------------------------------------------------------------------------------

def add(ws, name, pin=None, plugin_root=None, custom_text=None,
        pin_file=None, pending_file=None):
    """Desired-state edit (definition present) + reconcile. Refuses before writing on collision
    or an unresolvable backend; removes what it created if the second store fails."""
    ws = Path(ws)
    if not NAME_RE.match(name or ""):
        raise AdvisorError(f"advisor name {name!r} is not a valid MCP server key")
    def_path = ws / AGENTS_REL / f"{name}.md"
    created_def = False
    if not def_path.is_file():
        if custom_text is not None:
            text = custom_text
        else:
            root = Path(plugin_root) if plugin_root else Path(__file__).resolve().parent.parent.parent
            preset = root / "templates" / "advisors" / f"{name}.md"
            if not preset.is_file():
                raise AdvisorError(
                    f"no definition at {def_path} and no preset named {name!r}; available presets "
                    "live in templates/advisors/")
            text = preset.read_text(encoding="utf-8")
        parse_definition(text, f"{name}.md")
        bridge.write_atomic(ws, def_path, text)
        created_def = True
    tl = ws / timeline_rel(name)
    created_tl = not tl.exists()
    tl.mkdir(parents=True, exist_ok=True)
    try:
        return reconcile(ws, pin=pin, pin_file=pin_file, pending_file=pending_file)
    except BaseException:
        # Rollback is best-effort and must never mask the refusal it is cleaning up after.
        try:
            if created_tl:
                bridge.remove_tree_at(ws, timeline_rel(name))
                bridge.unlink_at(ws, AGENTS_REL / name)
            if created_def:
                bridge.unlink_at(ws, AGENTS_REL / f"{name}.md")
        except (OSError, bridge.BridgeError):
            pass
        raise


def remove(ws, name, delete_timeline=False, pin=None):
    """Desired-state edit (definition gone, timeline optionally gone) + reconcile."""
    ws = Path(ws)
    if not NAME_RE.match(name or ""):
        raise AdvisorError(f"advisor name {name!r} is not a valid MCP server key")
    def_path = ws / AGENTS_REL / f"{name}.md"
    doc = bridge.load_json(ws / MCP_REL)
    owned = is_owned_entry((doc.get("mcpServers") or {}).get(name))
    if not def_path.is_file() and not owned:
        state = ("an unowned server of that name exists — not ours to remove"
                 if (doc.get("mcpServers") or {}).get(name) is not None
                 else "no such advisor")
        raise AdvisorError(f"remove {name!r}: {state}")
    if def_path.is_file():
        bridge.unlink_at(ws, AGENTS_REL / f"{name}.md")
    if delete_timeline:
        delete_timeline_dir(ws, name)
        try:
            bridge.unlink_at(ws, AGENTS_REL / name)
        except (OSError, bridge.BridgeError):
            pass  # the advisor dir holds user files beyond the timeline; leave them
    report = reconcile(ws, pin=pin)
    report.setdefault(name, "removed")
    return report


def delete_timeline_dir(ws, name):
    """Deletion confined to the exact advisor-timeline shape; anything else is refused."""
    if not NAME_RE.match(name or ""):
        raise bridge.BridgeError(
            f"{name!r} is not an advisor name; timeline deletion takes a bare advisor name")
    return bridge.remove_tree_at(ws, timeline_rel(name))


#: Back-compat alias used by tests and the CLI (`delete_timeline(ws, name)`).
delete_timeline = delete_timeline_dir


def list_advisors(ws):
    """Definitions ⋈ registrations, with a per-advisor state classification."""
    ws = Path(ws)
    defs = load_definitions(ws)
    doc = bridge.load_json(ws / MCP_REL)
    servers = doc.get("mcpServers", {}) if isinstance(doc, dict) else {}
    toml_text = bridge.read_text_verbatim(ws / TOML_REL)
    rows = []
    names = sorted(set(defs) | {n for n in servers if is_owned_entry(servers.get(n))}
                   | {n for n in bridge.toml_owned_names(toml_text)
                      if n not in bridge.SENTINEL_LITERALS
                      and not n.startswith(bridge.SENTINEL_PREFIX)})
    for name in names:
        in_json = is_owned_entry(servers.get(name))
        in_toml = bridge.toml_server_has(toml_text, name)
        if name in defs and in_json and in_toml:
            state = "consistent"
        elif name in defs and not in_json and not in_toml:
            state = "declared-unregistered"
        elif name in defs:
            state = "half-registered"
        else:
            state = "registered-undeclared"
        defn = defs.get(name)
        rows.append({
            "name": name,
            "state": state,
            "model": (defn or {}).get("model"),
            "tool_name": (defn or {}).get("tool_name"),
            "max_turns": (defn or {}).get("max_turns"),
            "max_budget_usd": (defn or {}).get("max_budget_usd"),
            "timeline": str(timeline_rel(name)),
        })
    return rows
