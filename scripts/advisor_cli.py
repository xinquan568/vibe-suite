#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""CLI for `/vibe-suite:advisor` (E6.1 / vibe-47) — add | list | remove | reconcile.

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

    p_add = sub.add_parser("add", help="add an advisor from a preset or custom flags")
    p_add.add_argument("name", help="advisor name (preset name unless --custom)")
    p_add.add_argument("--custom", action="store_true")
    p_add.add_argument("--pin", help="exact claude-octopus version (P9 escape hatch)")
    p_add.add_argument("--description")
    p_add.add_argument("--model")
    p_add.add_argument("--tool-name", dest="tool_name")
    p_add.add_argument("--max-turns", dest="max_turns", type=int)
    p_add.add_argument("--max-budget-usd", dest="max_budget_usd")
    p_add.add_argument("--allowed-tools", dest="allowed_tools")
    p_add.add_argument("--body-file", dest="body_file")

    p_list = sub.add_parser("list", help="list advisors with their state")
    p_list.add_argument("--json", action="store_true")

    p_rm = sub.add_parser("remove", help="remove an advisor")
    p_rm.add_argument("name")
    group = p_rm.add_mutually_exclusive_group()
    group.add_argument("--delete-timeline", action="store_true")
    group.add_argument("--keep-timeline", action="store_true")

    p_rec = sub.add_parser("reconcile", help="converge registrations to definitions")
    p_rec.add_argument("--pin")

    args = parser.parse_args(argv)
    ws = Path(args.workspace)

    try:
        if args.op == "add":
            custom_text = _compose_custom(args) if args.custom else None
            report = advisors.add(ws, args.name, pin=args.pin, plugin_root=_plugin_root(),
                                  custom_text=custom_text)
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
                    print(f"{r['name']:24} {r['state']:24} {tier:8} "
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
