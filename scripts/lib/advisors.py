#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Advisor lifecycle for `/vibe-suite:advisor` (E6.1 / vibe-47; F7.1, F7.2).

**One engine, six states.** `add` and `remove` are desired-state edits — a definition file
appears or disappears under `.vibe-suite/agents/` — converged by `reconcile()`, which `init`,
`repair` and `update` also call. Classification is shared (`_classify`) and content-aware: an
advisor is `consistent` only when *both* stores hold exactly the desired registration;
divergent content is `stale-registered`; a target the stores cannot agree on (or a floating or
malformed one) is `invalid-registration`, which converging refuses to guess about.

**Identity is the bare name; ownership is structural.** The callable `mcp__<name>__<tool_name>`
requires the server key to *be* the advisor name, so ownership travels inside the entry
(`bridge.ADVISOR_MARKER`, type-exact) and in the `vibe-suite:server:<name>` fence. A name held by
anything unowned — in either store, under any TOML quoting — is a collision to refuse.

**The transaction.** Two records with two lifetimes live under `.vibe-suite-state/`:
`advisor-preimages.json`, the long-lived baseline for eventual byte restoration of the
canonicalizing JSON store; and `advisor-txn.json`, a write-ahead journal present only while a
mutation is in flight. The journal carries both stores' immediate pre-images *and* their computed
post-images, so recovery after a hard crash is deterministic: an interrupted `apply` rolls back
to the pre-images; an interrupted `remove` rolls forward by writing the recorded post-images and
completing the deletions. Both records take the provenance mode discipline — the AND of every
recorded source's mode and 0600 — and the state directory is tightened to 0700 before any
secret-bearing byte lands. `VIBE_ADVISOR_FAIL_AFTER` names hard-crash points (`os._exit`) for the
subprocess test matrix; it exists for tests and does nothing when unset.

**Backend.** Resolution order is fixed: an explicit exact `--pin` (the P9 escape hatch) → the
shipped pin file → while pending, the single exact target the advisor's own registrations
already agree on — never a floating value, never a guess between disagreeing ones.
"""

import base64
import hashlib
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path

import bridge
import mcp_pin

AGENTS_REL = Path(".vibe-suite/agents")
STATE_REL = Path(".vibe-suite-state")
LEDGER_REL = STATE_REL / "advisor-preimages.json"
TXN_REL = STATE_REL / "advisor-txn.json"
MCP_REL = Path(".mcp.json")
TOML_REL = Path(".codex/config.toml")

TIERS = ("opus", "sonnet", "haiku")
PROMPT_MODES = ("append", "replace")
PERMISSION_MODES = ("default", "acceptEdits", "plan", "dontAsk", "auto", "bypassPermissions")
# vibe-184 / grill H1a: a definition is repository content. These modes hand the advisor the
# operator's authority without a prompt, and a cwd/additional_dirs entry outside the workspace
# hands it files the workspace never contained — neither registers without an explicit, logged
# acceptance (`--confirm-danger`, the codex lane's precedent). default/acceptEdits/plan and
# in-workspace directories are unchanged.
DANGEROUS_PERMISSION_MODES = ("dontAsk", "auto", "bypassPermissions")
DANGEROUS_FIELDS = ("permission_mode", "cwd", "additional_dirs")
CONFIRM_DANGER_FLAG = "--confirm-danger"
ACCEPTANCES_KEY = "danger_accepted"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
EFFORTS = ("low", "medium", "high", "max")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
BUDGET_RE = re.compile(r"^\d+(\.\d+)?$")

IGNORE_BLOCK = "advisor-ignore"
IGNORE_BODY = ".vibe-suite/agents/*/timeline/"


class AdvisorError(bridge.BridgeError):
    """Refusal. Nothing has been written."""


def is_owned_entry(entry):
    return bridge.advisor_owned_entry(entry)


def timeline_rel(name):
    return AGENTS_REL / name / "timeline"


def _fail_point(name):
    """Hard-crash injection for the subprocess test matrix — `os._exit` so no guard can run."""
    if os.environ.get("VIBE_ADVISOR_FAIL_AFTER") == name:
        os._exit(9)


# --------------------------------------------------------------------------------------------
# Definition files
# --------------------------------------------------------------------------------------------

def _parse_frontmatter(text, source):
    """The advisor frontmatter subset: scalars, `|` literal blocks, flow lists. Returns
    `(fields, body, kinds)` where kinds records each key's syntactic form, because the schema
    cares: a description must be a literal block, a list field must be a flow list."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AdvisorError(f"{source}: no frontmatter block (--- expected on line 1)")
    fields, kinds, i = {}, {}, 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            body = "\n".join(lines[i + 1:]).lstrip("\n")
            return fields, body, kinds
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
            kinds[key] = "block"
            continue
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            fields[key] = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
            kinds[key] = "list"
        else:
            fields[key] = value.strip("'\"")
            kinds[key] = "scalar"
        i += 1
    raise AdvisorError(f"{source}: frontmatter never closed (missing trailing ---)")


def parse_definition(text, filename):
    """Validate against the agent-design skill's field table; enforce the documented types."""
    stem = filename[:-3] if filename.endswith(".md") else filename
    fields, body, kinds = _parse_frontmatter(text, filename)
    for key in ("allowed_tools", "disallowed_tools", "additional_dirs"):
        if key in fields and kinds.get(key) != "list":
            raise AdvisorError(f"{filename}: {key} must be a flow list like [Read, Grep, Glob]")
    for key in ("name", "model", "tool_name", "prompt_mode", "permission_mode", "effort",
                "cwd", "max_turns", "max_budget_usd"):
        if key in fields and kinds.get(key) != "scalar":
            raise AdvisorError(f"{filename}: {key} must be a plain scalar value")
    if "description" in fields and kinds.get("description") != "block":
        raise AdvisorError(f"{filename}: description must be a YAML literal block scalar (|) so "
                           "newlines and <example> tags survive")
    name = fields.get("name", stem)
    if not NAME_RE.match(name or ""):
        raise AdvisorError(f"{filename}: advisor name {name!r} is not a valid MCP server key")
    if "description" not in fields or not (fields["description"] or "").strip():
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
    tool_name = fields.get("tool_name", f"{name}_consult")
    if not NAME_RE.match(tool_name or ""):
        raise AdvisorError(f"{filename}: tool_name {tool_name!r} is not a valid MCP tool name")
    try:
        max_turns = int(fields.get("max_turns", 5))
    except (ValueError, TypeError):
        raise AdvisorError(f"{filename}: max_turns must be an integer") from None
    if max_turns <= 0:
        raise AdvisorError(f"{filename}: max_turns must be positive, got {max_turns}")
    budget = fields.get("max_budget_usd")
    if budget is not None:
        if not isinstance(budget, str) or not BUDGET_RE.match(budget) or float(budget) <= 0:
            raise AdvisorError(f"{filename}: max_budget_usd must be a positive decimal, "
                               f"got {budget!r}")
    if not body.strip():
        raise AdvisorError(f"{filename}: the body (system prompt) is empty")
    return {
        "name": name,
        "description": fields["description"].strip(),
        "tool_name": tool_name,
        "model": model,
        "allowed_tools": list(fields.get("allowed_tools", ["Read", "Grep", "Glob"])),
        "disallowed_tools": list(fields.get("disallowed_tools", [])),
        "permission_mode": permission_mode,
        "max_turns": max_turns,
        "max_budget_usd": budget,
        "effort": effort,
        "cwd": fields.get("cwd", "."),
        "additional_dirs": list(fields.get("additional_dirs", [])),
        "prompt_mode": prompt_mode,
        "body": body,
    }


def load_definitions(ws):
    out = {}
    agents = Path(ws) / AGENTS_REL
    if agents.is_symlink():
        raise AdvisorError(f"{agents} is a symlink; refusing to read definitions through it")
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
# Backend resolution (D-c; frozen order)
# --------------------------------------------------------------------------------------------

def resolve_backend(explicit_pin, pin_file=None, pending_file=None):
    """`claude-octopus@<exact>` from an explicit pin, else the shipped pin file; a `pending`
    state without an explicit pin refuses, naming both remedies."""
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


def _entry_target(entry):
    args = entry.get("args") if isinstance(entry, dict) else None
    if isinstance(args, list) and args and isinstance(args[-1], str) \
            and args[-1].startswith(mcp_pin.PACKAGE + "@"):
        return args[-1]
    return None


def _toml_block_target(toml_text, name):
    """The block's target, `"<unparseable>"` when the block exists but its target is missing,
    malformed, or not a claude-octopus spec — a foreign or unreadable value must surface as
    disagreement, never pass as an agreeing registration."""
    match = bridge._block_re(f"server:{name}", "#", "").search(toml_text)
    if not match:
        return None
    m = re.search(r'args = \["-y", "([^"]+)"\]', match.group(0))
    if not m or not m.group(1).startswith(mcp_pin.PACKAGE + "@"):
        return "<unparseable>"
    return m.group(1)


def _registered_targets(name, servers, toml_text):
    """Every distinct target the advisor's own registrations carry, across both stores."""
    targets = set()
    entry = servers.get(name)
    if is_owned_entry(entry):
        t = _entry_target(entry)
        targets.add(t if t is not None else "<unparseable>")
    t = _toml_block_target(toml_text, name)
    if t is not None:
        targets.add(t)
    return targets


def _target_version(target):
    return target.split("@", 1)[1] if target and "@" in target else None


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


# --------------------------------------------------------------------------------------------
# Records: baseline ledger + write-ahead journal
# --------------------------------------------------------------------------------------------

def _record_mode(entries):
    """The provenance discipline: AND every recorded source's mode with 0600."""
    mode = 0o600
    for entry in entries:
        raw = entry.get("mode") if isinstance(entry, dict) else None
        if isinstance(raw, str) and raw:   # a recorded mode is an octal string, nothing else
            mode &= int(raw, 8)
    return mode


def _load_json_file(path):
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _save_ledger(ws, ledger):
    if not ledger:
        bridge.unlink_at(ws, LEDGER_REL)
        try:
            bridge.unlink_at(ws, STATE_REL)   # rmdir when empty; harmless refusal otherwise
        except (OSError, bridge.BridgeError):
            pass
        return
    # vibe-184: only provenance-image members carry a recorded mode; the acceptance map is keyed
    # by advisor names (NAME_RE admits "mode") and must never be read as one.
    mode = _record_mode(v for k, v in ledger.items() if k != ACCEPTANCES_KEY)
    bridge.write_atomic(ws, Path(ws) / LEDGER_REL,
                        json.dumps(ledger, indent=2, sort_keys=True) + "\n", mode=mode)


JOURNAL_KEYS = {"schema", "intent", "remove_name", "delete_timeline", "desired_sha",
                "pre_images", "post_images", "prior_baseline", "post_baseline",
                ACCEPTANCES_KEY}   # vibe-184: optional — {"prior": {...}, "post": {...}} acceptance maps


def _validated_journal(txn_path):
    """Fail-closed: a journal recovery cannot fully trust must never drive deletions. Every
    field is checked for presence and type; unknown schemas and unknown keys refuse."""
    try:
        txn = json.loads(txn_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AdvisorError(f"{txn_path} is unreadable ({exc}); refusing to guess at recovery — "
                           "inspect and remove it by hand") from exc
    def refuse(why):
        raise AdvisorError(f"{txn_path}: {why}; refusing recovery — inspect and remove it by hand")
    if not isinstance(txn, dict) or set(txn) - JOURNAL_KEYS:
        refuse("unknown journal shape")
    if txn.get("schema") != 1:
        refuse(f"unknown journal schema {txn.get('schema')!r}")
    if txn.get("intent") not in ("apply", "remove"):
        refuse(f"unknown intent {txn.get('intent')!r}")
    def _valid_image(v):
        if v is None:
            return True
        if not isinstance(v, dict) or v.get("kind") != "file":
            return False
        if not all(isinstance(v.get(k), str) for k in ("path", "mode", "sha256", "content_b64")):
            return False
        try:
            raw = base64.b64decode(v["content_b64"], validate=True)
            int(v["mode"], 8)
        except Exception:
            return False
        return hashlib.sha256(raw).hexdigest() == v["sha256"]

    pre = txn.get("pre_images")
    if not isinstance(pre, dict) or set(pre) - {str(MCP_REL), str(TOML_REL), "definition"} \
            or str(MCP_REL) not in pre or str(TOML_REL) not in pre \
            or not all(_valid_image(v) for v in pre.values()):
        refuse("pre_images do not cover both stores with restorable entries")
    if not isinstance(txn.get("desired_sha"), str) \
            or not re.fullmatch(r"[0-9a-f]{64}", txn["desired_sha"]):
        refuse("desired_sha is not a sha256 hex digest")
    for key in ("prior_baseline", "post_baseline"):
        if not _valid_image(txn.get(key)):
            refuse(f"{key} is not a restorable pre-image record")
    post = txn.get("post_images")
    if not isinstance(post, dict) or set(post) != {str(MCP_REL), str(TOML_REL)} \
            or not isinstance(post.get(str(MCP_REL)), str) \
            or not isinstance(post.get(str(TOML_REL)), str):
        refuse("post_images do not cover both stores")
    try:
        base64.b64decode(post[str(MCP_REL)], validate=True)
    except Exception:
        refuse("post_images are not decodable")
    if ACCEPTANCES_KEY in txn and not _valid_acceptance_maps(txn[ACCEPTANCES_KEY]):
        refuse(f"{ACCEPTANCES_KEY} is not a pair of valid acceptance maps")
    if txn["intent"] == "remove":
        if not NAME_RE.match(txn.get("remove_name") or ""):
            refuse(f"remove journal names no valid advisor ({txn.get('remove_name')!r})")
        if not isinstance(txn.get("delete_timeline"), bool):
            refuse("remove journal carries no boolean delete_timeline")
        if "definition" not in pre:
            refuse("remove journal carries no definition provenance")
    return txn


def _valid_acceptance(entry):
    """One recorded acceptance: the definition sha it is bound to, the fields it covers, when."""
    if not isinstance(entry, dict) or set(entry) != {"definition_sha256", "fields", "accepted_at"}:
        return False
    if not isinstance(entry["definition_sha256"], str) or not _SHA256_RE.match(entry["definition_sha256"]):
        return False
    fields = entry["fields"]
    if not isinstance(fields, list) or not fields:
        return False
    for f in fields:
        if not isinstance(f, dict) or set(f) != {"field", "value", "reason"}:
            return False
        if f["field"] not in DANGEROUS_FIELDS or not all(isinstance(f[k], str) for k in ("value", "reason")):
            return False
    return isinstance(entry["accepted_at"], str) and bool(_ISO_Z_RE.match(entry["accepted_at"]))


def _valid_acceptance_map(m):
    return isinstance(m, dict) and all(
        isinstance(name, str) and NAME_RE.match(name) and _valid_acceptance(entry) for name, entry in m.items())


def _valid_acceptance_maps(member):
    """The journal's optional `danger_accepted` member: exactly {"prior": map, "post": map}."""
    return (isinstance(member, dict) and set(member) == {"prior", "post"}
            and _valid_acceptance_map(member["prior"]) and _valid_acceptance_map(member["post"]))


def _install_acceptances(baseline, member, which):
    """Put the journal's `prior` (apply rollback) or `post` (remove roll-forward) acceptance map into
    the ledger dict — or drop the key when that map is empty. A journal without the member (written
    before vibe-184) leaves the ledger's acceptances untouched."""
    if member is None:
        return
    chosen = member[which]
    if chosen:
        baseline[ACCEPTANCES_KEY] = chosen
    else:
        baseline.pop(ACCEPTANCES_KEY, None)


def recover(ws):
    """Heal an interrupted transaction. Returns the journal's `{"intent", "remove_name"}` when
    one was found and resolved, else None — callers can tell *what* recovery completed.

    `apply` rolls back: both stores and the baseline entry return to their journaled pre-state.
    `remove` rolls forward: the recorded post-images and post-baseline are applied (idempotent)
    and the deletions complete. The journal is deleted **last**, after every fallible step, so an
    interrupted recovery is itself recoverable.
    """
    ws = Path(ws)
    bridge.assert_root(ws)
    bridge.pin_root(ws)
    txn_path = ws / TXN_REL
    if not txn_path.is_file():
        return None
    txn = _validated_journal(txn_path)
    pre = txn.get("pre_images", {})

    def restore(rel, entry):
        if entry is None:
            bridge.unlink_at(ws, Path(rel))
        else:
            bridge.write_atomic(ws, ws / rel, base64.b64decode(entry.get("content_b64", "")))

    if txn.get("intent") == "remove":
        post = txn["post_images"]
        bridge.write_atomic(ws, ws / MCP_REL, base64.b64decode(post[str(MCP_REL)]))
        bridge.write_atomic(ws, ws / TOML_REL, post[str(TOML_REL)])
        name = txn["remove_name"]
        if pre.get("definition") is not None:
            # None provenance means no definition existed when the journal was written; a
            # deletion the record cannot vouch for is refused by omission.
            bridge.unlink_at(ws, AGENTS_REL / f"{name}.md")
        if txn["delete_timeline"]:
            bridge.remove_tree_at(ws, timeline_rel(name))
            try:
                bridge.unlink_at(ws, AGENTS_REL / name)
            except (OSError, bridge.BridgeError):
                pass
        baseline = _load_json_file(ws / LEDGER_REL)
        post_base = txn.get("post_baseline")
        if post_base is None:
            baseline.pop(str(MCP_REL), None)
        else:
            baseline[str(MCP_REL)] = post_base
        _install_acceptances(baseline, txn.get(ACCEPTANCES_KEY), "post")   # vibe-184: roll forward
        _save_ledger(ws, baseline)
        _ignore_block(ws, load_definitions(ws))
        bridge.unlink_at(ws, TXN_REL)
    else:
        for rel in (str(MCP_REL), str(TOML_REL)):
            restore(rel, pre.get(rel))
        baseline = _load_json_file(ws / LEDGER_REL)
        prior = txn.get("prior_baseline")
        if prior is None:
            baseline.pop(str(MCP_REL), None)
        else:
            baseline[str(MCP_REL)] = prior
        _install_acceptances(baseline, txn.get(ACCEPTANCES_KEY), "prior")   # vibe-184: roll back
        _save_ledger(ws, baseline)
        bridge.unlink_at(ws, TXN_REL)
    return {"intent": txn.get("intent"), "remove_name": txn.get("remove_name")}


# --------------------------------------------------------------------------------------------
# Classification — the one function list, doctor and reconcile share
# --------------------------------------------------------------------------------------------

def _classify(ws, defs, doc, toml_text, pin=None, pin_file=None, pending_file=None):
    """`{name: (state, desired_entry, desired_body, detail)}`; desired_* are None when the state
    needs no content (presence-only) or cannot be computed (invalid-registration)."""
    servers = doc.get("mcpServers", {}) if isinstance(doc, dict) else {}
    out = {}
    names = sorted(set(defs)
                   | {n for n in servers if is_owned_entry(servers.get(n))}
                   | {n for n in bridge.toml_owned_names(toml_text)
                      if n not in bridge.SENTINEL_LITERALS
                      and not n.startswith(bridge.SENTINEL_PREFIX)})
    for name in names:
        in_json = is_owned_entry(servers.get(name))
        in_toml = bridge.toml_server_has(toml_text, name)
        defn = defs.get(name)
        if defn is None:
            out[name] = ("registered-undeclared", None, None, None)
            continue
        if not in_json and not in_toml:
            out[name] = ("declared-unregistered", None, None, None)
            continue
        # A content comparison needs a target: explicit pin → shipped pin → the single exact
        # target the registrations agree on. Disagreement, floating, malformed → invalid.
        try:
            target = resolve_backend(pin, pin_file=pin_file, pending_file=pending_file)
        except AdvisorError:
            registered = _registered_targets(name, servers, toml_text)
            versions = {_target_version(t) for t in registered}
            if len(registered) == 1:
                only = next(iter(registered))
                version = _target_version(only)
                if version and mcp_pin._EXACT.match(version):
                    target = only
                else:
                    out[name] = ("invalid-registration", None, None,
                                 f"registered target {only!r} is not an exact version")
                    continue
            elif not registered:
                out[name] = ("invalid-registration", None, None,
                             "no readable target in either registration")
                continue
            else:
                out[name] = ("invalid-registration", None, None,
                             f"registrations disagree: {sorted(registered)} "
                             f"({sorted(v for v in versions if v)})")
                continue
        desired_entry = json_entry(defn, target)
        desired_body = toml_body(defn, target)
        json_ok = in_json and servers.get(name) == desired_entry
        toml_ok = in_toml and bridge.text_block_upsert(
            toml_text, f"server:{name}", desired_body) == toml_text
        if json_ok and toml_ok:
            out[name] = ("consistent", desired_entry, desired_body, None)
        elif in_json and in_toml:
            out[name] = ("stale-registered", desired_entry, desired_body, None)
        else:
            out[name] = ("half-registered", desired_entry, desired_body, None)
    return out


# --------------------------------------------------------------------------------------------
# Danger gate (vibe-184 / grill H1a)
# --------------------------------------------------------------------------------------------

def _outside_workspace(ws, raw):
    """True when `raw` (a cwd or additional_dirs entry, `~` expanded, anchored at the workspace when
    relative) resolves outside the workspace — `bridge.assert_inside`'s realpath containment."""
    expanded = os.path.expanduser(str(raw))
    candidate = Path(expanded) if os.path.isabs(expanded) else Path(ws) / expanded
    try:
        bridge.assert_inside(ws, candidate)
    except bridge.BridgeError:
        return True
    return False


def dangerous_fields(ws, defn):
    """The fields of `defn` that need an explicit acceptance: `[(field, value, reason)]`."""
    out = []
    if defn["permission_mode"] in DANGEROUS_PERMISSION_MODES:
        out.append(("permission_mode", defn["permission_mode"],
                    "runs the advisor without permission prompts"))
    if _outside_workspace(ws, defn["cwd"]):
        out.append(("cwd", defn["cwd"], "resolves outside the workspace"))
    for entry in defn["additional_dirs"]:
        if _outside_workspace(ws, entry):
            out.append(("additional_dirs", entry, "resolves outside the workspace"))
    return out


def definition_sha(defn):
    """A stable digest of the parsed definition — the identity an acceptance is bound to."""
    canon = json.dumps(defn, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _accepted(ledger, name, sha):
    entry = (ledger.get(ACCEPTANCES_KEY) or {}).get(name)
    return isinstance(entry, dict) and entry.get("definition_sha256") == sha


def danger_gate(ws, defs, confirm_danger=False, now=None):
    """Refuse — before anything is written — every definition that declares a dangerous field
    unless it is accepted, and return the acceptances this transaction must record.

    A field is accepted when `confirm_danger` is passed now, or when the ledger already holds an
    acceptance for this exact definition (same sha) — a flag-less `reconcile` from init/repair/
    update then converges an advisor the operator accepted once; a changed definition needs the
    flag again. Passing the flag when nothing is dangerous is refused, like `--confirm-danger` on
    the codex lane. Returns `{name: acceptance}` for the NEW acceptances (empty when none).
    """
    ledger = _load_json_file(Path(ws) / LEDGER_REL)
    new_acceptances = {}
    dangerous_seen = False
    for name in sorted(defs):
        fields = dangerous_fields(ws, defs[name])
        if not fields:
            continue
        dangerous_seen = True
        sha = definition_sha(defs[name])
        if _accepted(ledger, name, sha):
            continue
        if not confirm_danger:
            field, value, reason = fields[0]
            raise AdvisorError(
                f"{name}: {field} {value!r} {reason}; pass {CONFIRM_DANGER_FLAG} to accept it "
                f"(the acceptance is recorded) — nothing has been written")
        new_acceptances[name] = {
            "definition_sha256": sha,
            "fields": [{"field": f, "value": str(v), "reason": r} for f, v, r in fields],
            "accepted_at": now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    if confirm_danger and not dangerous_seen:
        raise AdvisorError(
            f"{CONFIRM_DANGER_FLAG} is only meaningful when a definition declares a dangerous field "
            "(permission_mode dontAsk/auto/bypassPermissions, or a cwd/additional_dirs entry outside "
            "the workspace) — none does; nothing has been written")
    return new_acceptances


def unaccepted_dangerous(ws, defs):
    """The names in `defs` that declare a dangerous field without a recorded acceptance — what
    `remove` must leave untouched (never register, refresh, or refuse over) while it removes
    something else."""
    ledger = _load_json_file(Path(ws) / LEDGER_REL)
    return {name for name in defs
            if dangerous_fields(ws, defs[name]) and not _accepted(ledger, name, definition_sha(defs[name]))}


# --------------------------------------------------------------------------------------------
# Reconcile — the one engine
# --------------------------------------------------------------------------------------------

def _collision_check(defs, doc, toml_text):
    servers = doc.get("mcpServers", {}) if isinstance(doc, dict) else {}
    tables = set(bridge.toml_table_names(toml_text))
    for name in defs:
        entry = servers.get(name)
        if entry is not None and not is_owned_entry(entry):
            raise AdvisorError(
                f".mcp.json already has an unowned server named {name!r}; rename the advisor or "
                "remove the conflicting entry — nothing has been written")
        if name in tables and not bridge.toml_server_has(toml_text, name):
            raise AdvisorError(
                f".codex/config.toml already has an unfenced server named {name!r}; rename the "
                "advisor or remove the conflicting table — nothing has been written")


def reconcile(ws, pin=None, pin_file=None, pending_file=None, confirm_danger=False):
    """Converge both stores to the definitions. Returns `{name: transition}`."""
    ws = Path(ws)
    bridge.assert_root(ws)
    bridge.pin_root(ws)
    recover(ws)
    defs = load_definitions(ws)
    doc = bridge.load_json(ws / MCP_REL)
    toml_before = bridge.read_text_verbatim(ws / TOML_REL)
    _collision_check(defs, doc, toml_before)
    # vibe-184: a dangerous definition is refused here — after the collision check, before any
    # classification can write — unless accepted now or previously; the new acceptances ride the
    # same transaction as the registrations they authorise.
    acceptances = danger_gate(ws, defs, confirm_danger=confirm_danger)

    classified = _classify(ws, defs, doc, toml_before, pin, pin_file, pending_file)
    invalid = {n: d for n, (s, _, _, d) in classified.items() if s == "invalid-registration"}
    if invalid:
        name, detail = next(iter(invalid.items()))
        raise AdvisorError(
            f"advisor {name!r}: {detail}; pass --pin <exact version> to settle the target — "
            "nothing has been written")

    servers = doc.setdefault("mcpServers", {})
    toml_text = toml_before
    report = {}
    for name, (state, desired_entry, desired_body, _) in classified.items():
        if state == "consistent":
            report[name] = "consistent"
        elif state == "registered-undeclared":
            if is_owned_entry(servers.get(name)):
                del servers[name]
            if bridge.toml_server_has(toml_text, name):
                toml_text = bridge.toml_server_remove(toml_text, name)
            report[name] = "registered-undeclared->removed"
        else:
            if desired_entry is None:
                # Presence-only classification carries no content; a write needs it, so the
                # target resolves here — and a pending pin with no --pin refuses (D-c).
                target = resolve_backend(pin, pin_file=pin_file, pending_file=pending_file)
                desired_entry = json_entry(defs[name], target)
                desired_body = toml_body(defs[name], target)
            servers[name] = desired_entry
            toml_text = bridge.toml_server_upsert(toml_text, name, desired_body)
            report[name] = f"{state}->registered"

    _transact(ws, doc, toml_before, toml_text, defs, acceptances=acceptances)
    return report


def _endstate_bytes(doc):
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _transact(ws, doc, toml_before, toml_after, defs,
              intent="apply", remove_name=None, delete_timeline=False, definition_pre=None,
              acceptances=None):
    """Journal → JSON → TOML → baseline → ignore-block, with rollback (apply) or the journal left
    for roll-forward (remove — the caller finishes deletions and cleanup)."""
    ws = Path(ws)
    mcp_path = ws / MCP_REL
    mcp_before = mcp_path.read_bytes() if mcp_path.is_file() else None
    baseline = _load_json_file(ws / LEDGER_REL)
    prior_baseline = baseline.get(str(MCP_REL))

    advisors_left = [n for n, e in (doc.get("mcpServers") or {}).items()
                     if bridge.advisor_owned_entry(e)]
    restore_bytes = None
    if not advisors_left and prior_baseline is not None:
        pre_bytes = base64.b64decode(prior_baseline.get("content_b64", ""))
        try:
            pre_doc = json.loads(pre_bytes.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            pre_doc = None
        if pre_doc == doc:
            restore_bytes = pre_bytes
        else:
            print("advisors: .mcp.json diverged from its pre-image while advisors were "
                  "registered; leaving the canonical form", flush=True)

    try:
        before_doc = json.loads(mcp_before.decode("utf-8")) if mcp_before else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        before_doc = None
    if restore_bytes is not None:
        mcp_final = restore_bytes
    elif before_doc == doc and mcp_before is not None:
        # Semantically unchanged: never canonicalize a file this transaction does not alter —
        # the user's formatting is theirs until an advisor mutation actually touches the store.
        mcp_final = mcp_before
    else:
        mcp_final = _endstate_bytes(doc)
    json_changed = mcp_before != mcp_final
    toml_changed = toml_after != toml_before
    # vibe-184: the acceptance maps before and after this transaction — journaled whole, so that
    # recovery can restore (apply) or install (remove) them exactly; kept in the ledger.
    accepted_before = dict(baseline.get(ACCEPTANCES_KEY) or {})
    accepted_after = dict(accepted_before)
    if acceptances:
        accepted_after.update(acceptances)
    if intent == "remove" and remove_name in accepted_after:
        del accepted_after[remove_name]
    acceptances_changed = accepted_after != accepted_before
    if not (json_changed or toml_changed or acceptances_changed) and intent == "apply":
        _ignore_block(ws, defs)
        return

    # The state directory is brought into existence by the primitive whose job that is; tightening
    # its mode no longer creates it as a side effect (vibe-179).
    bridge.ensure_dir_at(ws, STATE_REL)
    bridge.secure_dir(ws, STATE_REL)
    pre_images = {
        str(MCP_REL): bridge.record_pre_image(mcp_path) if mcp_before is not None else None,
        str(TOML_REL): (bridge.record_pre_image(ws / TOML_REL)
                        if (ws / TOML_REL).is_file() else None),
    }
    if intent == "remove":
        pre_images["definition"] = definition_pre  # None = already gone (timeline-only retry)
    post_baseline = dict(baseline)
    if advisors_left and json_changed and str(MCP_REL) not in post_baseline \
            and mcp_before is not None:
        post_baseline[str(MCP_REL)] = pre_images[str(MCP_REL)]
    if not advisors_left:
        post_baseline.pop(str(MCP_REL), None)
    if accepted_after:
        post_baseline[ACCEPTANCES_KEY] = accepted_after
    else:
        post_baseline.pop(ACCEPTANCES_KEY, None)
    journal = {
        "schema": 1, "intent": intent, "remove_name": remove_name,
        "delete_timeline": delete_timeline,
        "desired_sha": hashlib.sha256(
            "".join(sorted(defs)).encode("utf-8")).hexdigest(),
        "pre_images": pre_images,
        "post_images": {str(MCP_REL): base64.b64encode(mcp_final).decode("ascii"),
                        str(TOML_REL): toml_after},
        "prior_baseline": prior_baseline,
        "post_baseline": post_baseline.get(str(MCP_REL)),
        ACCEPTANCES_KEY: {"prior": accepted_before, "post": accepted_after},   # vibe-184
    }
    mode = _record_mode(pre_images.values())
    bridge.write_atomic(ws, ws / TXN_REL, json.dumps(journal) + "\n", mode=mode)
    _fail_point("journal")

    try:
        if json_changed:
            bridge.write_atomic(ws, mcp_path, mcp_final)
        _fail_point("json")
        if toml_changed:
            _write_toml_store(ws, toml_after)
        _fail_point("toml")
        _save_ledger(ws, post_baseline)
        _fail_point("baseline")
        _ignore_block(ws, defs)
    except BaseException:
        if True:  # both intents roll back in-process: the destructive tail has not run yet
            if mcp_before is not None:
                bridge.write_atomic(ws, mcp_path, mcp_before)
            elif json_changed:
                bridge.unlink_at(ws, MCP_REL)
            if toml_changed and (ws / TOML_REL).is_file():
                bridge.write_atomic(ws, ws / TOML_REL, toml_before)
            restored = _restore_baseline(ws, prior_baseline)
            # vibe-184: the ledger was written with the post-transaction acceptance map before
            # `_ignore_block` could raise — the in-process rollback restores the journaled prior
            # map exactly as `recover` does, so a rolled-back apply authorises nothing and a
            # failed remove keeps what it had.
            _install_acceptances(restored, journal[ACCEPTANCES_KEY], "prior")
            _save_ledger(ws, restored)
            bridge.unlink_at(ws, TXN_REL)
        raise
    if intent == "apply":
        bridge.unlink_at(ws, TXN_REL)


def _restore_baseline(ws, prior):
    baseline = _load_json_file(Path(ws) / LEDGER_REL)
    if prior is None:
        baseline.pop(str(MCP_REL), None)
    else:
        baseline[str(MCP_REL)] = prior
    return baseline


def _ignore_block(ws, defs):
    """The privacy rule: the ignore block stays while definitions exist **or any timeline
    directory survives** — a kept history must stay private-by-default."""
    ws = Path(ws)
    timelines = list((ws / AGENTS_REL).glob("*/timeline")) if (ws / AGENTS_REL).is_dir() else []
    existing = bridge.read_text_verbatim(ws / ".gitignore")
    if defs or timelines:
        updated = bridge.text_block_upsert(existing, IGNORE_BLOCK, IGNORE_BODY)
        if updated != existing:
            bridge.write_atomic(ws, ws / ".gitignore", updated)
    elif bridge.text_block_has(existing, IGNORE_BLOCK):
        updated = bridge.text_block_remove(existing, IGNORE_BLOCK)
        if updated.strip():
            bridge.write_atomic(ws, ws / ".gitignore", updated)
        else:
            bridge.unlink_at(ws, Path(".gitignore"))


def _write_toml_store(ws, text):
    bridge.write_atomic(ws, Path(ws) / TOML_REL, text)


# --------------------------------------------------------------------------------------------
# Lifecycle commands
# --------------------------------------------------------------------------------------------

def add(ws, name, pin=None, plugin_root=None, custom_text=None,
        pin_file=None, pending_file=None, confirm_danger=False):
    """Preflight everything fallible — backend included — before creating anything."""
    ws = Path(ws)
    bridge.assert_root(ws)
    bridge.pin_root(ws)
    recover(ws)
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
        # The backend must resolve BEFORE anything is created: a pending pin with no --pin
        # refuses with zero residue — no definition, no timeline, no state directory.
        resolve_backend(pin, pin_file=pin_file, pending_file=pending_file)
        bridge.write_atomic(ws, def_path, text)
        created_def = True
    tl_rel = timeline_rel(name)
    created_tl = not (ws / tl_rel).exists()
    try:
        bridge.ensure_dir_at(ws, tl_rel)
        return reconcile(ws, pin=pin, pin_file=pin_file, pending_file=pending_file,
                         confirm_danger=confirm_danger)
    except BaseException:
        try:
            if created_tl:
                bridge.remove_tree_at(ws, tl_rel)
                bridge.unlink_at(ws, AGENTS_REL / name)
            if created_def:
                bridge.unlink_at(ws, AGENTS_REL / f"{name}.md")
                try:
                    bridge.unlink_at(ws, AGENTS_REL)
                    bridge.unlink_at(ws, AGENTS_REL.parent)
                except (OSError, bridge.BridgeError):
                    pass
        except (OSError, bridge.BridgeError):
            pass
        raise


def remove(ws, name, delete_timeline=False, pin=None, pin_file=None, pending_file=None):
    """Preflight → two-store transaction → definition → timeline, journaled for roll-forward."""
    ws = Path(ws)
    bridge.assert_root(ws)
    bridge.pin_root(ws)
    recover(ws)
    if not NAME_RE.match(name or ""):
        raise AdvisorError(f"advisor name {name!r} is not a valid MCP server key")
    def_path = ws / AGENTS_REL / f"{name}.md"
    doc = bridge.load_json(ws / MCP_REL)
    owned = is_owned_entry((doc.get("mcpServers") or {}).get(name))
    timeline_residue = (ws / timeline_rel(name)).is_dir()
    if not def_path.is_file() and not owned and not timeline_residue:
        state = ("an unowned server of that name exists — not ours to remove"
                 if (doc.get("mcpServers") or {}).get(name) is not None
                 else "no such advisor")
        raise AdvisorError(f"remove {name!r}: {state}")

    # Preflight the full desired plan with the target excluded, before any destructive step.
    defs = load_definitions(ws)
    definition_pre = bridge.record_pre_image(def_path) if def_path.is_file() else None
    defs_after = {k: v for k, v in defs.items() if k != name}
    toml_before = bridge.read_text_verbatim(ws / TOML_REL)
    # vibe-184: a removal authorises nothing. Another advisor whose definition is dangerous and
    # not yet accepted is HELD: excluded from the collision and invalid-registration preflights
    # (neither may block this removal on its account), never registered or refreshed below, and
    # reported; the post-removal convergence says the same in its warning.
    held = unaccepted_dangerous(ws, defs_after)
    _collision_check({k: v for k, v in defs_after.items() if k not in held}, doc, toml_before)
    classified = _classify(ws, defs_after, doc, toml_before, pin, pin_file, pending_file)
    for other, (state, _, _, detail) in classified.items():
        if other in held:
            continue
        if state == "invalid-registration":
            raise AdvisorError(
                f"advisor {other!r}: {detail}; pass --pin <exact version> to settle the target — "
                f"nothing has been removed")

    servers = doc.setdefault("mcpServers", {})
    toml_text = toml_before
    report = {}
    for other, (state, desired_entry, desired_body, _) in classified.items():
        if other in held:
            report[other] = (f"danger-unaccepted (not converged; pass {CONFIRM_DANGER_FLAG} to "
                             "advisor reconcile)")
            continue
        if state == "consistent":
            continue
        if state == "registered-undeclared":
            if is_owned_entry(servers.get(other)):
                del servers[other]
            if bridge.toml_server_has(toml_text, other):
                toml_text = bridge.toml_server_remove(toml_text, other)
            report[other] = "registered-undeclared->removed"
            continue
        if desired_entry is None:
            target = resolve_backend(pin, pin_file=pin_file, pending_file=pending_file)
            desired_entry = json_entry(defs_after[other], target)
            desired_body = toml_body(defs_after[other], target)
        servers[other] = desired_entry
        toml_text = bridge.toml_server_upsert(toml_text, other, desired_body)
        report[other] = f"{state}->registered"
    if is_owned_entry(servers.get(name)):
        del servers[name]
    if bridge.toml_server_has(toml_text, name):
        toml_text = bridge.toml_server_remove(toml_text, name)

    _transact(ws, doc, toml_before, toml_text, defs_after,
              intent="remove", remove_name=name, delete_timeline=delete_timeline,
              definition_pre=definition_pre)
    if def_path.is_file():
        bridge.unlink_at(ws, AGENTS_REL / f"{name}.md")
    _fail_point("definition")
    if delete_timeline:
        if os.environ.get("VIBE_ADVISOR_FAIL_AFTER") == "timeline-partial":
            # Simulate an interruption after deletion has begun: remove one leaf, then die.
            tl = ws / timeline_rel(name)
            for leaf in sorted(tl.rglob("*")):
                if leaf.is_file():
                    bridge.unlink_at(ws, leaf.relative_to(ws))
                    break
            os._exit(9)
        delete_timeline_dir(ws, name)
        try:
            bridge.unlink_at(ws, AGENTS_REL / name)
        except (OSError, bridge.BridgeError):
            pass  # the advisor dir holds user files beyond the timeline; leave them
    _fail_point("timeline")
    bridge.unlink_at(ws, TXN_REL)
    # A final pass through the shared engine converges the end-state artifacts the deletions
    # changed after the transaction (the ignore block once the last timeline is gone) and keeps
    # add and remove on one lifecycle path. Best-effort: the removal itself has already
    # succeeded, so a convergence refusal is reported, never raised over a completed removal.
    try:
        report.update(reconcile(ws, pin=pin, pin_file=pin_file, pending_file=pending_file))
    except (AdvisorError, bridge.BridgeError) as exc:
        report["_warning"] = f"post-removal convergence deferred: {exc}"
    report[name] = "removed"
    return report


def delete_timeline_dir(ws, name):
    """Deletion confined to the exact advisor-timeline shape; anything else is refused."""
    if not NAME_RE.match(name or ""):
        raise bridge.BridgeError(
            f"{name!r} is not an advisor name; timeline deletion takes a bare advisor name")
    return bridge.remove_tree_at(ws, timeline_rel(name))


#: Back-compat alias used by tests and the CLI.
delete_timeline = delete_timeline_dir


def list_advisors(ws, pin=None, pin_file=None, pending_file=None):
    """Definitions ⋈ registrations with content-aware state classification (read-only)."""
    ws = Path(ws)
    defs = load_definitions(ws)
    doc = bridge.load_json(ws / MCP_REL)
    toml_text = bridge.read_text_verbatim(ws / TOML_REL)
    classified = _classify(ws, defs, doc, toml_text, pin, pin_file, pending_file)
    rows = []
    for name, (state, _, _, detail) in sorted(classified.items()):
        defn = defs.get(name)
        rows.append({
            "name": name,
            "state": state,
            "detail": detail,
            "model": (defn or {}).get("model"),
            "tool_name": (defn or {}).get("tool_name"),
            "max_turns": (defn or {}).get("max_turns"),
            "max_budget_usd": (defn or {}).get("max_budget_usd"),
            "timeline": str(timeline_rel(name)),
        })
    return rows
