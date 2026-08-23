#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The operator-tier mode driver (vibe-135): executes the five issue2pr modes'
bookkeeping — the file and state operations `operational-modes.md` specifies — with every
behavior read from that reference's marker-tagged JSON declaration blocks at runtime.
Nothing here is a second statement of a mode rule: a behavior this driver cannot derive
from a declared block is a failure naming the marker and key (exit 4), never a hardcoded
fallback.

**This does not establish that a fresh reading of the markdown reproduces the goldens** —
the nine steps' content stays golden-recorded (`tests/test_loop_bounds.py:342` records why
that boundary is honest); this driver covers the mode wrapper around them. External,
judgment-bearing work (a squash-merge, a babysit round's nine steps) is *reported as the
required next action* and re-enters through declared result events; the driver itself
writes only the declared bookkeeping.

Exit codes: 0 done · 2 refusal (precondition, containment, illegal transition, bad input)
· 4 declaration gap.
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402  — the audited write primitive; nothing here writes directly

REPO_ROOT = HERE.parent
DEFAULT_REFERENCE = (REPO_ROOT / "skills" / "issue2pr" / "references"
                     / "operational-modes.md")


class DeclarationGap(Exception):
    def __init__(self, marker, key):
        super().__init__(f"declaration gap: marker '{marker}' key '{key}' — the mode "
                         "surface does not declare the behavior this operation needs")
        self.marker, self.key = marker, key


class Refusal(Exception):
    pass


class Declarations:
    def __init__(self, reference):
        self.reference = Path(reference)
        try:
            self.text = self.reference.read_text(encoding="utf-8")
        except OSError as exc:
            raise Refusal(f"cannot read the mode surface at {reference}: {exc}")

    def block(self, marker):
        m = re.search(rf"<!-- {re.escape(marker)} -->\n```json\n(.*?)\n```",
                      self.text, re.S)
        if not m:
            raise DeclarationGap(marker, "(entire block)")
        try:
            return json.loads(m.group(1))
        except ValueError:
            raise DeclarationGap(marker, "(unparseable block)")

    def need(self, marker, *keys):
        node = self.block(marker)
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                raise DeclarationGap(marker, ".".join(keys))
            node = node[key]
        return node


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise Refusal(f"cannot read {path}: {exc}")
    except ValueError as exc:
        raise Refusal(f"{path} is not JSON: {exc}")


def dump_json(path, data):
    path = Path(path)
    bridge.write_atomic(path.parent, path,
                        json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def append_text(path, text):
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    bridge.write_atomic(path.parent, path, existing + text)


# --------------------------------------------------------------------------- run modes


def resolve_run(runs_root, run_id):
    run = Path(runs_root) / run_id
    if not (run / "state.json").is_file():
        raise Refusal(f"no run at {run} (state.json missing — an absent file is an "
                      "error, not an empty run)")
    return run


def status_partition(decl, status):
    enum = decl.block("run-status-enum")
    for side in ("terminal", "non_terminal"):
        if side not in enum:
            raise DeclarationGap("run-status-enum", side)
        if status in enum[side]:
            return side
    raise Refusal(f"status {status!r} is outside the declared enum — the run is "
                  "malformed and the pipeline says so rather than guessing")


def mode_iterate(decl, args):
    ops = decl.block("iterate-operations")
    for key in ("precondition_partition", "redirect_nonmatching_to", "creates",
                "override_records", "override_key_type", "never_writes", "transition",
                "flag_rules"):
        if key not in ops:
            raise DeclarationGap("iterate-operations", key)
    run = resolve_run(args.runs_root, args.run_id)
    state = load_json(run / "state.json")
    if status_partition(decl, state.get("status")) != ops["precondition_partition"]:
        raise Refusal(f"iterate needs a {ops['precondition_partition']} run; "
                      f"{state.get('status')!r} is not — use "
                      f"{ops['redirect_nonmatching_to']}")
    new_round = int(state.get("current_round", 1)) + 1
    round_dir = run / ops["creates"].replace("<N+1>", str(new_round)).rstrip("/")
    round_dir.mkdir(exist_ok=False)
    if ops["override_key_type"] == "string round number":
        override_key = str(new_round)
    else:
        raise DeclarationGap("iterate-operations", "override_key_type")
    protected = {(run / name).resolve(): (run / name).read_bytes()
                 for name in ops["never_writes"] if (run / name).is_file()}

    mode_record = ops["override_records"].get("review_mode")
    if mode_record is None:
        raise DeclarationGap("iterate-operations", "override_records.review_mode")
    effective_mode = (state.get(mode_record, {})
                      .get(str(state.get("current_round", 1)))
                      or state.get("review_mode"))
    supplied = {"review_mode": args.review_mode,
                "reviewer_backend": args.reviewer_backend,
                "max_review_rounds": args.max_review_rounds}
    ignored_under = decl.need("iterate-operations", "flag_rules", "max_review_rounds",
                              "ignored_with_notice_under_modes")
    new_mode = args.review_mode or effective_mode
    for flag, value in supplied.items():
        if value is None:
            continue
        if flag == "max_review_rounds" and new_mode in ignored_under:
            print(f"--max-review-rounds: ignored — review-mode '{new_mode}' has no "
                  "verify loop for a cap to bound")
            continue
        record_key = ops["override_records"].get(flag)
        if record_key is None:
            raise DeclarationGap("iterate-operations", f"override_records.{flag}")
        state.setdefault(record_key, {})[override_key] = value
    state["status"] = decl.need("iterate-operations", "transition", "to")
    state["current_round"] = new_round
    dump_json(run / "state.json", state)
    for target, before in protected.items():
        if not target.is_file() or target.read_bytes() != before:
            raise Refusal(f"{target.name} is declared never-written and changed — "
                          "refusing to leave the run in this state")
    print(f"iterate: {args.run_id} -> round {new_round}, status {state['status']}")
    return 0


def mode_resume(decl, args):
    ops = decl.block("resume-operations")
    for key in ("precondition_partition", "redirect_nonmatching_to", "writes",
                "sequences"):
        if key not in ops:
            raise DeclarationGap("resume-operations", key)
    if ops["writes"] != []:
        raise DeclarationGap("resume-operations", "writes")
    run = resolve_run(args.runs_root, args.run_id)
    state = load_json(run / "state.json")
    if status_partition(decl, state.get("status")) != ops["precondition_partition"]:
        raise Refusal(f"resume needs a {ops['precondition_partition']} run; "
                      f"{state.get('status')!r} is terminal — use "
                      f"{ops['redirect_nonmatching_to']}")
    mode = (state.get("review_mode_overrides", {})
            .get(str(state.get("current_round", 1))) or state.get("review_mode"))
    if mode not in ops["sequences"]:
        raise DeclarationGap("resume-operations", f"sequences.{mode}")
    sequence = ops["sequences"][mode]
    current = int(state.get("current_step", 1))
    next_step = current if current in sequence else next(
        (s for s in sequence if s > current), sequence[-1])
    print(f"next step: {next_step} (run {args.run_id}, review-mode {mode}, "
          f"round {state.get('current_round', 1)})")
    return 0


def mode_list(decl, args):
    ops = decl.block("list-operations")
    for key in ("exclude_prefix", "writes", "order", "columns", "column_fields",
                "resume_pointer_unless_status"):
        if key not in ops:
            raise DeclarationGap("list-operations", key)
    if ops["writes"] != []:
        raise DeclarationGap("list-operations", "writes")
    root = Path(args.runs_root)
    rows = []
    for child in root.iterdir() if root.is_dir() else []:
        if not child.is_dir() or child.name.startswith(ops["exclude_prefix"]):
            continue
        state = {}
        try:
            state = load_json(child / "state.json")
        except Refusal:
            pass
        rows.append((child.stat().st_mtime, child.name, state))
    newest_first = "newest" in ops["order"]
    rows.sort(key=lambda r: r[0], reverse=newest_first)
    print(" | ".join(ops["columns"]))
    fields = ops["column_fields"]
    for _mtime, name, state in rows:
        mode = (state.get("review_mode_overrides", {})
                .get(str(state.get("current_round", 1))) or state.get("review_mode", "?"))
        status = state.get("status", "?")
        cells = []
        for column in ops["columns"]:
            source = fields.get(column)
            if source is None:
                raise DeclarationGap("list-operations", f"column_fields.{column}")
            if source == "$dir":
                cells.append(name)
            elif source == "$effective_mode":
                cells.append(str(mode))
            elif source == "$resume_pointer":
                cells.append("" if status in ops["resume_pointer_unless_status"]
                             else f"resume {name}")
            else:
                cells.append(str(state.get(source, "?")))
        print(" | ".join(cells))
    return 0


# --------------------------------------------------------------------------- chain


class Chain:
    def __init__(self, decl, chain_file):
        self.decl = decl
        self.ops = decl.block("chain-operations")
        for key in ("link_statuses", "chain_statuses", "link_edges",
                    "pause_on_link_terminal_not", "persist_after_every_transition",
                    "events"):
            if key not in self.ops:
                raise DeclarationGap("chain-operations", key)
        self.path = Path(chain_file)
        self.data = load_json(self.path)
        self.timeline = self.path.parent / "timeline.md"
        self.pending_lines = []
        self.result_events = None      # vibe-188: set when the applied branch declares its own

    @property
    def link(self):
        return self.data["links"][self.data.get("current_index", 0)]

    def move_link(self, link, to, pause_exempt=False):
        frm = link["status"]
        if to not in self.ops["link_statuses"]:
            raise Refusal(f"{to!r} is not in the declared link vocabulary")
        if to not in self.ops["link_edges"].get(frm, []):
            raise Refusal(f"transition {frm} -> {to} is not a declared edge")
        link["status"] = to
        self.pending_lines.append(f"link {link.get('issue', '?')}: {frm} -> {to}")
        self.persist()
        # The declared blanket rule: a link terminal (no outgoing declared edges) that is
        # not the declared survivor pauses the chain — unless the producing event
        # declares itself exempt (skip). Both the terminal notion and the pause status
        # are declaration-derived.
        survivor = self.ops["pause_on_link_terminal_not"]
        if "on_link_terminal_chain_status" not in self.ops:
            raise DeclarationGap("chain-operations", "on_link_terminal_chain_status")
        pause_status = self.ops["on_link_terminal_chain_status"]
        link_terminal = not self.ops["link_edges"].get(to)
        if link_terminal and to != survivor and not pause_exempt \
                and self.data.get("status") != pause_status:
            self.set_chain(pause_status)

    def set_chain(self, status):
        vocab = (self.ops["chain_statuses"]["non_terminal"]
                 + self.ops["chain_statuses"]["terminal"])
        if status not in vocab:
            raise Refusal(f"{status!r} is not in the declared chain vocabulary")
        self.data["status"] = status
        self.pending_lines.append(f"chain: {status}")
        self.persist()

    def advance(self):
        adv = self.decl.need("chain-operations", "events", "advance")
        idx = self.data.get("current_index", 0)
        if idx + 1 < len(self.data["links"]):
            self.data["current_index"] = idx + 1
            nxt = self.data["links"][idx + 1]
            frm, to = adv["next_link"]["from"], adv["next_link"]["to"]
            if nxt["status"] != frm:
                raise Refusal(f"cannot advance: next link is {nxt['status']!r}, "
                              f"the declared start edge begins at {frm!r}")
            self.move_link(nxt, to)
        else:
            self.set_chain(adv["on_last_link"]["chain"])
            return

    def persist(self):
        for target in self.ops["persist_after_every_transition"]:
            if target == "chain.json":
                dump_json(self.path, self.data)
            elif target == "timeline.md":
                stamp = now_utc()
                append_text(self.timeline,
                            "".join(f"- {stamp} {line}\n" for line in self.pending_lines))
        self.pending_lines = []

    def apply_effect(self, effect, args, notes=()):
        seen_aliases = set()
        while "as" in effect:
            target = effect["as"]
            if target in seen_aliases:
                raise DeclarationGap("watcher-exit-actions",
                                     f"as-cycle through {target!r}")
            seen_aliases.add(target)
            watcher = self.decl.block("watcher-exit-actions")
            if target not in watcher or "effect" not in watcher[target]:
                raise DeclarationGap("watcher-exit-actions", f"{target}.effect")
            merged = dict(watcher[target]["effect"])
            merged.update({k: v for k, v in effect.items() if k != "as"})
            effect = merged
        wrote = False
        for required in effect.get("requires", []):
            value = getattr(args, required, None)
            if value in (None, ""):
                raise Refusal(f"this effect requires --{required.replace('_', '-')}")
            if required in ("babysit_round", "babysit_cap"):
                try:
                    if int(value) < 1:
                        raise ValueError
                except (TypeError, ValueError):
                    raise Refusal(f"--{required.replace('_', '-')} must be an "
                                  "integer >= 1")
        if "requires" in effect and "ancestor_verified" in effect["requires"]:
            if args.ancestor_verified != "true":
                raise Refusal("the merge commit is not verified as an ancestor of the "
                              "base branch; refusing to mark the link merged")
        if "by_classification" in effect:
            cls = args.classification
            if cls == "actionable":
                semantics = self.decl.need("chain-operations", "babysit_round_semantics")
                # The declared semantics: the 1-based ordinal about to run; it runs
                # while round <= cap.
                if "runs while round <= cap" not in semantics:
                    raise DeclarationGap("chain-operations", "babysit_round_semantics")
                # vibe-188: ACTIONABLE activity may run a babysit round only when its author is
                # one of the DECLARED associations; anyone else is notified about, never acted
                # upon, and auto-merge is never re-armed on their account — the decision is
                # recorded. Fail-closed against the declaration: an absent `author_gate` is a
                # gap (exit 4), an explicit null is the declared opt-out (exit 4's alias — a
                # failing check has no author), and every member the gate needs must be present.
                if "author_gate" not in effect:
                    raise DeclarationGap("watcher-exit-actions", "3.effect.author_gate")
                gate = effect["author_gate"]
                if gate is not None:
                    # Every member is validated — shape AND value — before anything persists, so
                    # an unsupported declaration is a gap naming the exact member (exit 4), never
                    # a half-applied branch.
                    G = "3.effect.author_gate"
                    if not isinstance(gate, dict):
                        raise DeclarationGap("watcher-exit-actions", G)
                    if gate.get("applies_to") != "actionable":
                        raise DeclarationGap("watcher-exit-actions", G + ".applies_to")
                    allowed = gate.get("babysit_allowed")
                    if (not isinstance(allowed, list) or not allowed
                            or not all(isinstance(a, str) and a.strip() for a in allowed)):
                        raise DeclarationGap("watcher-exit-actions", G + ".babysit_allowed")
                    otherwise = gate.get("otherwise")
                    if not isinstance(otherwise, dict):
                        raise DeclarationGap("watcher-exit-actions", G + ".otherwise")

                    def _text(value):
                        return isinstance(value, str) and bool(value.strip())

                    def _scalar(value):
                        return value is None or isinstance(value, (bool, int, float, str))

                    flags = otherwise.get("link_flag")
                    events_declared = self.decl.need("chain-operations", "events")
                    checks = (
                        ("report", _text(otherwise.get("report"))),
                        ("link_flag", isinstance(flags, dict) and bool(flags)
                         and all(_text(k) and _scalar(v) for k, v in flags.items())),
                        ("timeline_note", _text(otherwise.get("timeline_note"))),
                        ("cursor", otherwise.get("cursor") == "advance"),
                        ("result_events", isinstance(otherwise.get("result_events"), list)
                         and all(isinstance(e, str) and e in events_declared
                                 for e in otherwise["result_events"])),
                    )
                    for member, ok in checks:
                        if member not in otherwise or not ok:
                            raise DeclarationGap("watcher-exit-actions",
                                                 G + ".otherwise." + member)
                    # The flag must be present (the watcher's exit-3 line carries it); an EMPTY
                    # value means the API supplied none — not a collaborator.
                    if args.author_association is None:
                        raise Refusal("actionable activity requires --author-association "
                                      "(the watcher's exit-3 line carries it)")
                    assoc = args.author_association.strip().upper()
                    if assoc not in [a.upper() for a in allowed]:
                        branch = dict(otherwise)
                        note = branch.pop("timeline_note", None)
                        extra = [f"{note} (author_association={assoc or 'UNKNOWN'})"] if note else []
                        return self.apply_effect(branch, args, list(notes) + extra)
                within = int(args.babysit_round) <= int(args.babysit_cap)
                cls = f"actionable_{'within' if within else 'beyond'}_cap"
            sub = effect["by_classification"].get(cls)
            if sub is None:
                raise DeclarationGap("watcher-exit-actions",
                                     f"by_classification.{cls}")
            return self.apply_effect(sub, args, notes)
        if "pre_report" in effect:
            print(f"required action: {effect['pre_report']}")
        if "edge" in effect:
            link = self.link
            if link["status"] != effect["edge"]["from"]:
                raise Refusal(f"link is {link['status']!r}; the declared effect edge "
                              f"starts at {effect['edge']['from']!r}")
            if args.pr:
                link["pr"] = int(args.pr)   # recorded BEFORE the transition persists
            self.move_link(link, effect["edge"]["to"])
            wrote = True
        if "cursor" in effect:
            if not args.cursor:
                raise Refusal("this effect advances the cursor; pass --cursor")
            self.link["cursor"] = args.cursor
            self.pending_lines.append(f"cursor -> {args.cursor}")
            wrote = True
        if "link_flag" in effect:
            # vibe-188: a declared per-link record (e.g. auto_merge_rearm=false) — persisted in
            # chain.json and named in the timeline, so the decision outlives the session.
            for key, value in effect["link_flag"].items():
                self.link[key] = value
                self.pending_lines.append(f"link flag {key} = {json.dumps(value)}")
            wrote = True
        if "chain" in effect:
            self.set_chain(effect["chain"])
            wrote = True
        if "then" in effect and effect["then"] == "advance":
            self.advance()
            wrote = True
        if "report" in effect:
            print(f"required action: {effect['report']}")
        if "result_events" in effect:
            # vibe-188: a branch may declare its OWN result events (the notify-only branch
            # declares none) — mode_chain awaits these instead of the record's.
            self.result_events = list(effect["result_events"])
        for note in notes:
            self.pending_lines.append(note)
        if self.pending_lines:
            self.persist()
        return 0


def mode_chain(decl, args):
    chain = Chain(decl, args.chain_file)
    if args.event:
        events = decl.need("chain-operations", "events")
        if args.event not in events:
            raise DeclarationGap("chain-operations", f"events.{args.event}")
        ev = events[args.event]
        if args.event == "skip":
            link = chain.link
            if link["status"] not in ev["from_any_of"]:
                raise Refusal(f"skip applies from {ev['from_any_of']}, "
                              f"link is {link['status']!r}")
            chain.move_link(link, ev["to"], pause_exempt=ev.get("pause_exempt", False))
            if ev.get("then") == "advance":
                chain.advance()
            return 0
        if "inputs" in ev:
            (input_name, domain), = ev["inputs"].items()
            value = getattr(args, input_name.replace("-", "_"), None)
            if value not in domain:
                raise Refusal(f"--{input_name} must be one of {domain}")
            return chain.apply_effect(ev["effects"][value], args)
        if "edge" in ev:
            return chain.apply_effect(ev, args)
        raise DeclarationGap("chain-operations", f"events.{args.event}")

    watcher = decl.block("watcher-exit-actions")
    code = str(args.watcher_exit)
    record = watcher.get(code)
    if record is None:
        catch_all = next((r for r in watcher.values()
                          if r.get("effect", {}).get("catch_all_for_unmapped")), None)
        if catch_all is None:
            raise DeclarationGap("watcher-exit-actions", f"{code} (and no catch-all)")
        record = catch_all
    notes = []
    if "timeline_note" in record.get("effect", {}):
        notes.append(record["effect"]["timeline_note"])
    if "result_events" not in record:
        raise DeclarationGap("watcher-exit-actions", f"{code}.result_events")
    events = decl.need("chain-operations", "events")
    for event in record["result_events"]:
        if event not in events:
            raise DeclarationGap("chain-operations", f"events.{event}")
    rc = chain.apply_effect(record["effect"], args, notes)
    # vibe-188: the branch that ran may have declared its own result events (the notify-only
    # branch declares none); those are validated and awaited instead of the record's.
    awaited = record["result_events"] if chain.result_events is None else chain.result_events
    for event in awaited:
        if event not in events:
            raise DeclarationGap("chain-operations", f"events.{event}")
    if awaited:
        print("awaiting result events: " + ", ".join(awaited))
    return rc


# --------------------------------------------------------------------------- manifest


def mode_manifest(decl, args):
    ops = decl.block("manifest-operations")
    for key in ("validate_via", "creates", "containment", "initial_status"):
        if key not in ops:
            raise DeclarationGap("manifest-operations", key)
    entry = REPO_ROOT / ops["validate_via"]
    result = subprocess.run([sys.executable, str(entry), args.manifest,
                             "--profile", args.profile],
                            capture_output=True, text=True, cwd=REPO_ROOT)
    print(f"manifest_entry: exit {result.returncode}")
    if result.returncode != 0:
        raise Refusal(f"{ops['validate_via']} rejected the manifest:\n{result.stderr}")
    settings = json.loads(result.stdout)
    manifest = load_json(args.manifest)

    runs_root = Path(args.runs_root).resolve()
    run_folder = manifest.get("run_folder", "")
    rel = Path(run_folder)
    if rel.parts and rel.parts[0] == "runs":
        rel = Path(*rel.parts[1:])   # the manifest convention is workspace-relative
    run = (runs_root / rel).resolve()
    if "beneath --runs-root" in ops["containment"]:
        try:
            run.relative_to(runs_root)
        except ValueError:
            raise Refusal(f"run_folder {run_folder!r} resolves outside --runs-root "
                          "— containment refused")
        if run == runs_root:
            raise Refusal("run_folder names the runs root itself — refused")
    else:
        raise DeclarationGap("manifest-operations", "containment")
    meta = {"schema_version": 2, "run_id": run.name,
            "source_id": manifest["subtask"]["id"],
            "profile": settings.get("profile", Path(args.profile).stem),
            "scenario": manifest.get("scenario", "auto"),
            "review_mode": manifest.get("review_mode", "full"),
            "max_review_rounds": manifest.get("max_review_iterations", 2),
            "reviewer_backend": manifest.get("reviewer_backend", "codex"),
            "created_at": now_utc(), "from_manifest": str(args.manifest)}
    state = {"schema_version": 2, "run_id": run.name,
             "source_id": manifest["subtask"]["id"],
             "review_mode": meta["review_mode"],
             "max_review_rounds": meta["max_review_rounds"],
             "max_review_rounds_overrides": {}, "review_mode_overrides": {},
             "reviewer_backend_overrides": {},
             "current_step": 1, "current_round": 1,
             "status": ops["initial_status"]}
    # The declared `creates` list drives what is written — remove an entry from the
    # declaration and that artifact is not created (consumption, not presence-checking).
    writers = {"run_folder": lambda: run.mkdir(parents=True, exist_ok=False),
               "00-meta.json": lambda: dump_json(run / "00-meta.json", meta),
               "state.json": lambda: dump_json(run / "state.json", state)}
    for artifact in ops["creates"]:
        writer = writers.get(artifact)
        if writer is None:
            raise DeclarationGap("manifest-operations", f"creates.{artifact}")
        writer()
    print(f"manifest: run folder {run} created, status {ops['initial_status']}")
    return 0


# --------------------------------------------------------------------------- CLI


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="issue2pr_mode_driver",
        description="Deterministic bookkeeping driver for the issue2pr modes; every "
                    "behavior is read from operational-modes.md's declaration blocks.")
    parser.add_argument("mode", choices=("iterate", "resume", "list", "chain",
                                         "manifest"))
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--runs-root")
    parser.add_argument("--reference", default=str(DEFAULT_REFERENCE))
    parser.add_argument("--max-review-rounds", type=int, dest="max_review_rounds")
    parser.add_argument("--review-mode", dest="review_mode")
    parser.add_argument("--reviewer-backend", dest="reviewer_backend")
    parser.add_argument("--chain-file", dest="chain_file")
    parser.add_argument("--watcher-exit", dest="watcher_exit")
    parser.add_argument("--event")
    parser.add_argument("--merge-commit", dest="merge_commit")
    parser.add_argument("--ancestor-verified", dest="ancestor_verified",
                        choices=("true", "false"))
    parser.add_argument("--classification",
                        choices=("actionable", "question", "status-noise"))
    parser.add_argument("--author-association", dest="author_association",
                        help="the triggering activity's GitHub author_association, as the watcher "
                             "printed it (vibe-188); exit 3 requires it")
    parser.add_argument("--babysit-round", dest="babysit_round")
    parser.add_argument("--babysit-cap", dest="babysit_cap")
    parser.add_argument("--cursor")
    parser.add_argument("--outcome", choices=("pushed", "failed"))
    parser.add_argument("--status", choices=("pr_opened", "failed"))
    parser.add_argument("--pr")
    parser.add_argument("--manifest")
    parser.add_argument("--profile")
    args = parser.parse_args(argv)

    try:
        decl = Declarations(args.reference)
        if args.mode == "iterate":
            if not (args.run_id and args.runs_root):
                raise Refusal("iterate needs <run-id> and --runs-root")
            return mode_iterate(decl, args)
        if args.mode == "resume":
            if not (args.run_id and args.runs_root):
                raise Refusal("resume needs <run-id> and --runs-root")
            return mode_resume(decl, args)
        if args.mode == "list":
            if not args.runs_root:
                raise Refusal("list needs --runs-root")
            return mode_list(decl, args)
        if args.mode == "chain":
            if not args.chain_file or (args.watcher_exit is None and not args.event):
                raise Refusal("chain needs --chain-file and one of --watcher-exit or "
                              "--event")
            return mode_chain(decl, args)
        if args.mode == "manifest":
            if not (args.manifest and args.profile and args.runs_root):
                raise Refusal("manifest needs --manifest, --profile and --runs-root")
            return mode_manifest(decl, args)
    except Refusal as exc:
        print(f"issue2pr_mode_driver: {exc}", file=sys.stderr)
        return 2
    except DeclarationGap as exc:
        print(f"issue2pr_mode_driver: {exc}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
