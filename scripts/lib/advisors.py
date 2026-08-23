#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Advisor lifecycle for `/vibe-suite:advisor` (E6.1 / vibe-47; F7.1, F7.2).

**One engine, six states.** `add` and `remove` are desired-state edits — a definition file
appears or disappears under `.vibe-suite/agents/` — converged by `reconcile()`, which `init`,
`repair` and `update` also call. Classification is shared (`_classify`) and content-aware: an
advisor is `consistent` only when *both* stores hold exactly the desired registration;
divergent content is `stale-registered`; a target the stores cannot agree on (or a floating or
malformed one) is `invalid-registration`, which converging refuses to guess about.

**Registration is the operator's act (vibe-185 / grill H1b).** A definition is repository content:
`add <name>` (or `add --all`) registers it and STAMPS the sha of its parsed content in the ledger;
a flag-less `reconcile` — init, repair, update, remove's sibling pass — writes only definitions
whose stamp matches their current content, holds and discloses the rest (never-stamped, changed,
or stamp-less registrations), and drops the ledger records of a definition that no longer exists.
`add <name>` preflights and writes only the named definition.

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
# vibe-185 / grill H1b: registration is an explicit operator act. The ledger stamps every
# registered definition with the sha of its parsed content; a flag-less `reconcile` (init /
# repair / update / remove's sibling pass) converges ONLY stamped, unchanged definitions and
# holds everything else — disclosed, never written. `add <name>` (or `add --all`) stamps.
REGISTRATIONS_KEY = "registered"
LEDGER_RECORD_KEYS = (ACCEPTANCES_KEY, REGISTRATIONS_KEY)
REGISTER_ALL = "*"
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


def _scan_definitions(ws):
    """`(defs, unreadable)`: every declared definition that parses, keyed by name, and — keyed by
    file stem — the exception for every `*.md` that does not (a parse failure, a frontmatter name
    that disagrees with the filename, an unreadable file). vibe-185 (round 3): a targeted
    `add <name>` acts on exactly its names, so an unrelated definition it cannot read is
    disclosed and held, never a refusal; the strict loader below is every other caller's."""
    out, unreadable = {}, {}
    agents = Path(ws) / AGENTS_REL
    if agents.is_symlink():
        raise AdvisorError(f"{agents} is a symlink; refusing to read definitions through it")
    if not agents.is_dir():
        return out, unreadable
    for path in sorted(agents.glob("*.md")):
        try:
            defn = parse_definition(path.read_text(encoding="utf-8"), path.name)
            if defn["name"] != path.stem:
                raise AdvisorError(f"{path.name}: frontmatter name {defn['name']!r} does not "
                                   "match the filename; rename one of them")
        except AdvisorError as exc:
            unreadable[path.stem] = exc
            continue
        except UnicodeDecodeError as exc:
            unreadable[path.stem] = AdvisorError(f"{path.name}: not valid UTF-8 ({exc})")
            continue
        except OSError as exc:
            unreadable[path.stem] = AdvisorError(f"{path.name}: cannot be read ({exc})")
            continue
        out[defn["name"]] = defn
    return out, unreadable


def load_definitions(ws):
    """Every declared definition, strictly: the first unreadable file in name order refuses the
    caller with an `AdvisorError` naming it — a parse failure, a frontmatter name that disagrees
    with the filename, invalid UTF-8 (`not valid UTF-8`) or a read failure (`cannot be read`; the
    last two used to propagate raw). `add --all`, `remove`, `list`, init, repair and update read
    this way."""
    out, unreadable = _scan_definitions(ws)
    if unreadable:
        raise unreadable[sorted(unreadable)[0]]
    return out


def _unreadable_report(name, exc):
    return (f"unreadable (held; {exc}; existing store content left unchanged; not converged by an "
            f"explicit add — fix the file, then advisor add {name})")


def _declared_stems(ws):
    """The file stems of every declared `*.md` under the agents directory, WITHOUT parsing any of
    them — what a caller that only needs to know whether definitions exist (recovery's ignore-block
    decision) may read. The symlinked-directory refusal is the loader's, kept here."""
    agents = Path(ws) / AGENTS_REL
    if agents.is_symlink():
        raise AdvisorError(f"{agents} is a symlink; refusing to read definitions through it")
    if not agents.is_dir():
        return set()
    return {p.stem for p in agents.glob("*.md")}


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
    mode = _record_mode(v for k, v in ledger.items() if k not in LEDGER_RECORD_KEYS)
    bridge.write_atomic(ws, Path(ws) / LEDGER_REL,
                        json.dumps(ledger, indent=2, sort_keys=True) + "\n", mode=mode)


JOURNAL_KEYS = {"schema", "intent", "remove_name", "delete_timeline", "desired_sha",
                "pre_images", "post_images", "prior_baseline", "post_baseline",
                ACCEPTANCES_KEY,   # vibe-184: optional — {"prior": {...}, "post": {...}} acceptance maps
                REGISTRATIONS_KEY}  # vibe-185: optional — {"prior": {...}, "post": {...}} registration stamps


def _valid_image(v):
    """A restorable pre-image record (or None): kind file, string fields, decodable content whose
    sha matches. Shared by the journal validator and the ledger well-formedness check."""
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
    if REGISTRATIONS_KEY in txn and not _valid_registration_maps(txn[REGISTRATIONS_KEY]):
        refuse(f"{REGISTRATIONS_KEY} is not a pair of valid registration maps")
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


_IMAGE_KEYS = frozenset({"path", "kind", "mode", "sha256", "content_b64"})


def _expected_path(recorded, ws, rel):
    """A recorded pre-image path names exactly the workspace file it should: the relative store path
    (a CLI run from the workspace) or the absolute one (a library caller)."""
    p = Path(recorded)
    if p == Path(rel) or p == Path(ws) / rel:
        return True
    try:
        return p.resolve() == (Path(ws) / rel).resolve()
    except (OSError, RuntimeError):
        return False


def _writer_image(v, ws, rel):
    """A file pre-image exactly as `bridge.record_pre_image` writes it for `rel` under `ws`: the five
    fields, kind file, restorable, and the expected path — nothing more, nothing else."""
    return (isinstance(v, dict) and set(v) == _IMAGE_KEYS and v.get("kind") == "file"
            and _valid_image(v) and _expected_path(v["path"], ws, rel))


def ledger_is_well_formed(doc, ws):
    """The advisor ledger exactly as this module writes it: a non-empty dict whose every member is the
    `.mcp.json` pre-image (`_writer_image` for the workspace's store), `danger_accepted` (a valid,
    non-empty acceptance map) or `registered` (a valid, non-empty registration map). What `unbridge`
    requires before deleting the file; a lookalike fails."""
    if not isinstance(doc, dict) or not doc:
        return False
    for key, value in doc.items():
        if key == str(MCP_REL):
            if not _writer_image(value, ws, MCP_REL):
                return False
        elif key == ACCEPTANCES_KEY:
            if not _valid_acceptance_map(value) or not value:
                return False
        elif key == REGISTRATIONS_KEY:
            if not _valid_registration_map(value) or not value:
                return False
        else:
            return False
    return True


def journal_is_well_formed(path, ws):
    """A journal exactly as `_transact` writes it — the fail-closed validator PLUS the intent-dependent
    writer shape: every key present (both record members included), an `apply` journal with a null
    `remove_name`, `delete_timeline` false and pre-images for exactly the two stores, a `remove`
    journal with a valid name, a boolean and a `definition` pre-image under the agents directory,
    every image `_writer_image`-exact for its expected path. What `unbridge` requires before deleting
    a journal; a full-key near-miss fails."""
    try:
        txn = _validated_journal(Path(path))
    except (AdvisorError, OSError):
        return False
    if set(txn) != JOURNAL_KEYS:
        return False
    pre = txn["pre_images"]
    if txn["intent"] == "apply":
        if txn["remove_name"] is not None or txn["delete_timeline"] is not False:
            return False
        if set(pre) != {str(MCP_REL), str(TOML_REL)}:
            return False
    else:
        if set(pre) != {str(MCP_REL), str(TOML_REL), "definition"}:
            return False
        d = pre["definition"]
        if d is not None and not _writer_image(d, ws, AGENTS_REL / f"{txn['remove_name']}.md"):
            return False
    for rel in (MCP_REL, TOML_REL):
        v = pre[str(rel)]
        if v is not None and not _writer_image(v, ws, rel):
            return False
    for key in ("prior_baseline", "post_baseline"):
        v = txn[key]
        if v is not None and not _writer_image(v, ws, MCP_REL):
            return False
    return True


def _valid_registration(entry):
    """One registration stamp: the sha of the parsed definition the operator registered, and when."""
    if not isinstance(entry, dict) or set(entry) != {"definition_sha256", "registered_at"}:
        return False
    if not isinstance(entry["definition_sha256"], str) or not _SHA256_RE.match(entry["definition_sha256"]):
        return False
    return isinstance(entry["registered_at"], str) and bool(_ISO_Z_RE.match(entry["registered_at"]))


def _valid_registration_map(m):
    return isinstance(m, dict) and all(
        isinstance(name, str) and NAME_RE.match(name) and _valid_registration(entry) for name, entry in m.items())


def _valid_registration_maps(member):
    """The journal's optional `registered` member: exactly {"prior": map, "post": map}."""
    return (isinstance(member, dict) and set(member) == {"prior", "post"}
            and _valid_registration_map(member["prior"]) and _valid_registration_map(member["post"]))


def _install_record(baseline, member, which, key):
    """Put the journal's `prior` (apply rollback) or `post` (remove roll-forward) map for `key` into
    the ledger dict — or drop the key when that map is empty. A journal without the member (written
    before the member existed) leaves that ledger record untouched."""
    if member is None:
        return
    chosen = member[which]
    if chosen:
        baseline[key] = chosen
    else:
        baseline.pop(key, None)


def _install_records(baseline, txn, which):
    """Both ledger records — the danger acceptances (vibe-184) and the registration stamps
    (vibe-185) — restored (`prior`) or installed (`post`) from the journal together."""
    _install_record(baseline, txn.get(ACCEPTANCES_KEY), which, ACCEPTANCES_KEY)
    _install_record(baseline, txn.get(REGISTRATIONS_KEY), which, REGISTRATIONS_KEY)


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
        _install_records(baseline, txn, "post")   # vibe-184/185: roll the records forward
        _save_ledger(ws, baseline)
        # vibe-185 (round 5): the privacy block stays while any definition file or timeline exists;
        # recovery asks only that (no parsing) — an unreadable definition must not leave a journal
        # pending, and a targeted add of an unrelated name is never refused at recovery.
        _ignore_block(ws, _declared_stems(ws))
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
        _install_records(baseline, txn, "prior")   # vibe-184/185: roll the records back
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
# Registration stamps (vibe-185 / grill H1b)
# --------------------------------------------------------------------------------------------

def registration_state(ledger, name, defn):
    """`registered` — the ledger stamps this exact parsed definition; `changed` — it stamps an
    earlier content of it; `unregistered` — no stamp (never added, or registered before stamps
    existed). Only `registered` definitions converge without an operator naming them."""
    entry = (ledger.get(REGISTRATIONS_KEY) or {}).get(name)
    if not isinstance(entry, dict) or not isinstance(entry.get("definition_sha256"), str):
        return "unregistered"
    return "registered" if entry["definition_sha256"] == definition_sha(defn) else "changed"


def _hold_report(ws, name, defn, state, ledger):
    """The report line for a definition this call does not write. `state` is the classification
    of the stores; the registration state decides the remedy."""
    rstate = registration_state(ledger, name, defn)
    dangerous = ", ".join(f for f, _, _ in dangerous_fields(ws, defn))
    if rstate == "changed":
        line = (f"changed-unconfirmed (held; existing store content left unchanged; re-confirm "
                f"with advisor add {name})")
    elif state == "declared-unregistered" and dangerous and not _accepted(ledger, name, definition_sha(defn)):
        line = (f"danger-unaccepted (not registered; dangerous: {dangerous}; pass "
                f"{CONFIRM_DANGER_FLAG} to advisor add {name})")
        return line
    elif state == "declared-unregistered":
        line = f"declared-unregistered (not registered; register with advisor add {name})"
    else:
        line = (f"unstamped (held; existing store content left unchanged; confirm with "
                f"advisor add {name})")
    if dangerous:
        line += f"; dangerous: {dangerous}"
    return line


def registration_label(ledger, name, defn, in_stores):
    """The four-way registration vocabulary init, `list`, `reconcile` and `doctor` share: `registered`
    (stamp matches the content), `changed` (stamp of an earlier content), `unstamped` (a registration
    the stores hold but the ledger never stamped — written before vibe-185), `unregistered`."""
    rstate = registration_state(ledger, name, defn)
    if rstate != "unregistered":
        return rstate
    return "unstamped" if in_stores else "unregistered"


def listing(ws, pin=None, pin_file=None, pending_file=None):
    """What `init` discloses and `doctor`/`list` draw on: every declared definition with the values
    that decide what a registration would hand the advisor, and whether the operator registered
    it. Read-only; never resolves the backend."""
    ws = Path(ws)
    defs = load_definitions(ws)
    ledger = _load_json_file(ws / LEDGER_REL)
    doc = bridge.load_json(ws / MCP_REL)
    servers = doc.get("mcpServers", {}) if isinstance(doc, dict) else {}
    toml_text = bridge.read_text_verbatim(ws / TOML_REL)
    rows = []
    for name in sorted(defs):
        d = defs[name]
        in_stores = is_owned_entry(servers.get(name)) or bridge.toml_server_has(toml_text, name)
        rows.append({
            "name": name,
            "allowed_tools": list(d["allowed_tools"]),
            "disallowed_tools": list(d["disallowed_tools"]),
            "permission_mode": d["permission_mode"],
            "cwd": d["cwd"],
            "additional_dirs": list(d["additional_dirs"]),
            "prompt_bytes": len(d["body"].encode("utf-8")),
            "model": d["model"],
            "registration": registration_label(ledger, name, d, in_stores),
            "dangerous": [f for f, _, _ in dangerous_fields(ws, d)],
        })
    return rows


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


def danger_gate(ws, defs, confirm_danger=False, now=None, names=None):
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
    # vibe-185: the gate guards WRITES. A definition this call will not register or refresh (an
    # unstamped or changed one held by the registration rule) is disclosed, not refused here.
    for name in sorted(defs if names is None else names):
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


def reconcile(ws, pin=None, pin_file=None, pending_file=None, confirm_danger=False,
              register=None, now=None):
    """Converge both stores to the definitions the operator REGISTERED. Returns `{name: transition}`.

    vibe-185: `register` names the definitions this call stamps and registers (`add <name>` passes
    `{name}`; `add --all` passes `REGISTER_ALL`; init / repair / update pass nothing). Every other
    declared definition converges only while the ledger stamps its exact parsed content; an
    unstamped or changed definition is HELD — reported with its remedy, excluded from the collision
    and danger preflights, never written — and a registration nobody owns (`registered-undeclared`)
    is still removed.
    """
    ws = Path(ws)
    bridge.assert_root(ws)
    bridge.pin_root(ws)
    recover(ws)
    # vibe-185 (round 3): a targeted add reads strictly only what it acts on — an unrelated
    # definition that does not parse is held and reported, never a refusal; its records survive.
    # Every other caller (add --all, remove, init, repair, update, list) loads strictly, as before.
    if register and register != REGISTER_ALL:
        defs, unreadable = _scan_definitions(ws)
        unreadable_acting = sorted(set(register) & set(unreadable))
        if unreadable_acting:
            raise unreadable[unreadable_acting[0]]
    else:
        defs, unreadable = load_definitions(ws), {}
    if register == REGISTER_ALL:
        register = set(defs)
    register = set(register or ())
    unknown = sorted(register - set(defs))
    if unknown:
        raise AdvisorError(f"no definition to register for {unknown[0]!r}; nothing has been written")
    ledger = _load_json_file(ws / LEDGER_REL)
    # vibe-185 (round 2): an explicit `add` acts on exactly the names it was given — it never
    # preflights, refuses over, accepts for, or writes an unrelated definition, stamped or not; the
    # flag-less callers act on every stamped, unchanged definition (background convergence).
    explicit = bool(register)
    acting = set(register) if explicit else {
        n for n in defs if registration_state(ledger, n, defs[n]) == "registered"}
    acting_defs = {n: defs[n] for n in acting}
    doc = bridge.load_json(ws / MCP_REL)
    toml_before = bridge.read_text_verbatim(ws / TOML_REL)
    _collision_check(acting_defs, doc, toml_before)
    # vibe-184: a dangerous definition this call would write is refused here — after the collision
    # check, before any classification can write — unless accepted now or previously; the new
    # acceptances ride the same transaction as the registrations they authorise.
    acceptances = danger_gate(ws, defs, confirm_danger=confirm_danger, now=now, names=sorted(acting))

    classified = _classify(ws, defs, doc, toml_before, pin, pin_file, pending_file)
    invalid = {n: d for n, (s_, _, _, d) in classified.items()
               if s_ == "invalid-registration" and n in acting}
    if invalid:
        name, detail = next(iter(invalid.items()))
        raise AdvisorError(
            f"advisor {name!r}: {detail}; pass --pin <exact version> to settle the target — "
            "nothing has been written")

    servers = doc.setdefault("mcpServers", {})
    toml_text = toml_before
    report = {}
    for name, (state, desired_entry, desired_body, _) in classified.items():
        if name in unreadable:
            # vibe-185 (round 3): a declared definition this targeted add could not read — its
            # stores, stamp and acceptance are left exactly as they are.
            report[name] = _unreadable_report(name, unreadable[name])
            continue
        if state == "registered-undeclared":
            if explicit:
                # An explicit add writes only its named definition — an orphaned registration
                # is the flag-less callers' (and remove's) convergence, not this call's.
                report[name] = "registered-undeclared (not converged by an explicit add; run advisor reconcile)"
                continue
            if is_owned_entry(servers.get(name)):
                del servers[name]
            if bridge.toml_server_has(toml_text, name):
                toml_text = bridge.toml_server_remove(toml_text, name)
            report[name] = "registered-undeclared->removed"
        elif name not in acting:
            if explicit and registration_state(ledger, name, defs[name]) == "registered":
                report[name] = "registered (not converged by an explicit add; init/repair/update converge it)"
            else:
                report[name] = _hold_report(ws, name, defs[name], state, ledger)
        elif state == "consistent":
            report[name] = "consistent"
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
    for name in sorted(unreadable):
        report.setdefault(name, _unreadable_report(name, unreadable[name]))
    stamp_at = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registrations = {n: {"definition_sha256": definition_sha(defs[n]), "registered_at": stamp_at}
                     for n in sorted(register)}

    _transact(ws, doc, toml_before, toml_text, defs, acceptances=acceptances,
              registrations=registrations, also_declared=set(unreadable))
    return report


def _endstate_bytes(doc):
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _transact(ws, doc, toml_before, toml_after, defs,
              intent="apply", remove_name=None, delete_timeline=False, definition_pre=None,
              acceptances=None, registrations=None, also_declared=()):
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
    # vibe-185: the registration stamps, journaled and kept exactly like the acceptances.
    registered_before = dict(baseline.get(REGISTRATIONS_KEY) or {})
    registered_after = dict(registered_before)
    if registrations:
        registered_after.update(registrations)
    if intent == "remove" and remove_name in registered_after:
        del registered_after[remove_name]
    # vibe-185 (round 2): a record whose definition no longer exists — deleted by hand, never
    # through remove — is dropped by every transaction, with its acceptance: restoring the same
    # file later is a new registration, not a resumed one. `defs` is the set of definitions this
    # transaction converges (all declared; for remove, all but the target). Round 3: a declared
    # definition a targeted add could not READ (`also_declared`) still exists — its records are
    # not this transaction's to drop.
    declared = set(defs) | set(also_declared)
    for stale in [n for n in registered_after if n not in declared]:
        del registered_after[stale]
    for stale in [n for n in accepted_after if n not in declared]:
        del accepted_after[stale]
    acceptances_changed = accepted_after != accepted_before
    registrations_changed = registered_after != registered_before
    if not (json_changed or toml_changed or acceptances_changed or registrations_changed) \
            and intent == "apply":
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
    if registered_after:
        post_baseline[REGISTRATIONS_KEY] = registered_after
    else:
        post_baseline.pop(REGISTRATIONS_KEY, None)
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
        REGISTRATIONS_KEY: {"prior": registered_before, "post": registered_after},   # vibe-185
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
            _install_records(restored, journal, "prior")
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
                         confirm_danger=confirm_danger, register={name})
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


def add_all(ws, pin=None, pin_file=None, pending_file=None, confirm_danger=False):
    """`advisor add --all`: register (stamp) every declared definition at once — the explicit bulk
    act the init listing offers. Refuses when nothing is declared."""
    ws = Path(ws)
    bridge.assert_root(ws)
    bridge.pin_root(ws)
    recover(ws)
    defs = load_definitions(ws)
    if not defs:
        raise AdvisorError("no advisor definitions declared under .vibe-suite/agents/; nothing to register")
    # Every registered advisor gets its timeline directory, exactly as a single `add` gives one; a
    # refused bulk add leaves no residue — only the directories this call created are removed.
    # vibe-185 (round 3): every path goes through the audited descent, present or not — a regular
    # file or a symlink at `<name>/timeline` (which `Path.exists()` would have followed) refuses
    # the whole bulk add; presence for rollback ownership is read without following (`lstat_at`).
    created = []
    try:
        for name in sorted(defs):
            tl_rel = timeline_rel(name)
            try:
                absent = bridge.lstat_at(ws, tl_rel) is None
                bridge.ensure_dir_at(ws, tl_rel)
            except bridge.BridgeError as exc:
                raise AdvisorError(
                    f"{name}: timeline path {tl_rel} cannot be created safely ({exc}); "
                    "nothing has been registered") from exc
            if absent:
                created.append(name)
        return reconcile(ws, pin=pin, pin_file=pin_file, pending_file=pending_file,
                         confirm_danger=confirm_danger, register=REGISTER_ALL)
    except BaseException:
        for name in reversed(created):
            try:
                bridge.remove_tree_at(ws, timeline_rel(name))
                bridge.unlink_at(ws, AGENTS_REL / name)
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
    ledger = _load_json_file(ws / LEDGER_REL)
    # vibe-185: a sibling converges through a removal only on the same terms as through
    # reconcile — stamped at its current content; every other declared sibling is held too.
    held = unaccepted_dangerous(ws, defs_after) | {
        k for k, v in defs_after.items() if registration_state(ledger, k, v) != "registered"}
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
            report[other] = _hold_report(ws, other, defs_after[other], state, ledger)
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
    ledger = _load_json_file(ws / LEDGER_REL)
    rows = []
    for name, (state, _, _, detail) in sorted(classified.items()):
        defn = defs.get(name)
        rows.append({
            "name": name,
            "state": state,
            "detail": detail,
            "registration": (registration_label(ledger, name, defn, state != "declared-unregistered")
                             if defn is not None else None),
            "model": (defn or {}).get("model"),
            "tool_name": (defn or {}).get("tool_name"),
            "max_turns": (defn or {}).get("max_turns"),
            "max_budget_usd": (defn or {}).get("max_budget_usd"),
            "timeline": str(timeline_rel(name)),
        })
    return rows
