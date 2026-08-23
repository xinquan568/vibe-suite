#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""CLI for `/vibe-suite:advisor` (E6.1 / vibe-47) — add | list | remove | reconcile.

vibe-185: registration is an explicit operator act. `add <name>` (or `add --all`) registers and
stamps the definition; a flag-less `reconcile` — what init / repair / update run — converges only
stamped, unchanged definitions and holds everything else, disclosed and unwritten.

Non-interactive by design: the command doc runs the interview in the host session and calls this
with explicit flags, so every behavior here is scriptable and testable. Exit codes: 0 success,
2 refusal (nothing written on refusal — `advisors.AdvisorError` is raised before any mutation).

`add` resolves the claude-octopus backend per D-c: an explicit exact `--pin` (the P9 escape
hatch), else the shipped pin file, else a refusal naming both remedies while E7.1's pin is
pending. `reconcile` exists for `init` / `/vibe-suite:repair` / `/vibe-suite:update`, which
converge advisor registrations as part of their normal flow.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import advisors  # noqa: E402
import bridge  # noqa: E402


def _plugin_root():
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    return Path(env) if env else Path(__file__).resolve().parent.parent


def _compose_custom(args):
    if not args.description:
        raise advisors.AdvisorError("--custom requires --description")
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else None
    if not body or not body.strip():
        raise advisors.AdvisorError("--custom requires --body-file with a non-empty system prompt")
    desc = "\n".join("  " + line if line else "" for line in args.description.splitlines())
    lines = ["---", "description: |", desc]
    if args.model:
        lines.append(f"model: {args.model}")
    if args.tool_name:
        lines.append(f"tool_name: {args.tool_name}")
    if args.max_turns is not None:
        lines.append(f"max_turns: {args.max_turns}")
    if args.max_budget_usd is not None:
        lines.append(f"max_budget_usd: {args.max_budget_usd}")
    if args.allowed_tools:
        lines.append(f"allowed_tools: [{', '.join(args.allowed_tools.split(','))}]")
    lines += ["---", "", body.rstrip(), ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--workspace", default=".", help="workspace root (default: cwd)")
    sub = parser.add_subparsers(dest="op", required=True)

    p_add = sub.add_parser("add", help="add an advisor from a preset or custom flags, or register declared ones")
    p_add.add_argument("name", nargs="?", help="advisor name (preset name unless --custom; a declared definition to register)")
    p_add.add_argument("--all", dest="register_all", action="store_true",
                       help="register (stamp) every declared definition under .vibe-suite/agents/ — the explicit bulk act after init's listing")
    p_add.add_argument("--custom", action="store_true")
    p_add.add_argument("--pin", help="exact claude-octopus version (P9 escape hatch)")
    p_add.add_argument("--description")
    p_add.add_argument("--model")
    p_add.add_argument("--tool-name", dest="tool_name")
    p_add.add_argument("--max-turns", dest="max_turns", type=int)
    p_add.add_argument("--max-budget-usd", dest="max_budget_usd")
    p_add.add_argument("--allowed-tools", dest="allowed_tools")
    p_add.add_argument("--body-file", dest="body_file")
    p_add.add_argument("--confirm-danger", dest="confirm_danger", action="store_true",
                       help="accept a definition that declares permission_mode dontAsk/auto/"
                            "bypassPermissions or a cwd/additional_dirs entry outside the workspace "
                            "(vibe-184; the acceptance is recorded)")

    p_list = sub.add_parser("list", help="list advisors with their state")
    p_list.add_argument("--json", action="store_true")

    p_rm = sub.add_parser("remove", help="remove an advisor")
    p_rm.add_argument("name")
    group = p_rm.add_mutually_exclusive_group()
    group.add_argument("--delete-timeline", action="store_true")
    group.add_argument("--keep-timeline", action="store_true")

    p_rec = sub.add_parser("reconcile", help="converge REGISTERED definitions (stamped, unchanged) to both stores; held ones are reported")
    p_rec.add_argument("--pin")

    args = parser.parse_args(argv)
    ws = Path(args.workspace)

    try:
        # Recovery runs only from MUTATING entries — `list` stays observational: a pending
        # transaction is reported as state, and healing it is an explicit act of add/remove/
        # reconcile (each of which also recovers internally for library callers).
        if args.op != "list":
            recovered = advisors.recover(ws)
            if recovered:
                print("recovered an interrupted advisor transaction")
            if recovered and args.op == "remove" and recovered.get("intent") == "remove" \
                    and recovered.get("remove_name") == args.name:
                print(f"✓ advisor {args.name!r} removed (completed by recovery)")
                return 0
        elif (ws / advisors.TXN_REL).is_file():
            print("note: an advisor transaction is pending recovery; run "
                  "/vibe-suite:advisor reconcile (or any add/remove) to heal it")
        if args.op == "add":
            if args.register_all == bool(args.name):
                raise advisors.AdvisorError("add takes exactly one of <name> or --all")
            if args.register_all:
                if args.custom:
                    raise advisors.AdvisorError("--all registers declared definitions; it cannot be combined with --custom")
                report = advisors.add_all(ws, pin=args.pin, confirm_danger=args.confirm_danger)
                for name, transition in sorted(report.items()):
                    print(f"{name}: {transition}")
                print("✓ every declared advisor registered into .mcp.json + .codex/config.toml")
            else:
                custom_text = _compose_custom(args) if args.custom else None
                report = advisors.add(ws, args.name, pin=args.pin, plugin_root=_plugin_root(),
                                      custom_text=custom_text, confirm_danger=args.confirm_danger)
                for name, transition in sorted(report.items()):
                    print(f"{name}: {transition}")
                print(f"✓ advisor {args.name!r} bridged into .mcp.json + .codex/config.toml")
            print("Claude picks it up at next session start; Codex on next invocation.")
        elif args.op == "list":
            rows = advisors.list_advisors(ws)
            if args.json:
                print(json.dumps(rows, indent=2))
            elif not rows:
                print("no advisors (add one with /vibe-suite:advisor add <preset|--custom>)")
            else:
                for r in rows:
                    tier = r["model"] or "caller-default"
                    print(f"{r['name']:24} {r['state']:24} {(r.get('registration') or '-'):13} {tier:8} "
                          f"turns={r['max_turns'] or '-'} budget={r['max_budget_usd'] or '-'}")
        elif args.op == "remove":
            report = advisors.remove(ws, args.name, delete_timeline=args.delete_timeline)
            for name, transition in sorted(report.items()):
                print(f"{name}: {transition}")
            kept = "" if args.delete_timeline else \
                f" (timeline kept at {advisors.timeline_rel(args.name)})"
            print(f"✓ advisor {args.name!r} removed{kept}")
            print("Restart Claude so the MCP loader drops the server; Codex sees it immediately.")
        elif args.op == "reconcile":
            report = advisors.reconcile(ws, pin=args.pin)
            if not report:
                print("no advisors declared or registered; nothing to reconcile")
            for name, transition in sorted(report.items()):
                print(f"{name}: {transition}")
    except (advisors.AdvisorError, bridge.BridgeError) as exc:
        print(f"advisor: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
