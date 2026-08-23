---
description: "View and set vibe-suite configuration: --show merges the project's .vibe-suite.md with the runtime gate toggles and shows resolved engine defaults; --set changes a runtime toggle (gate on/off, gate model, fail policy). Never writes .vibe-suite.md — that file is yours."
argument-hint: "[--show | --set key=value]"
---

# /vibe-suite:config — view and set suite configuration

Two stores, one view. `.vibe-suite.md` holds the project's settings; three **runtime toggles** live
in the job state. `--show` merges them; `--set` writes only the toggles.

## What to do

**Forward the user's arguments; do not choose the operation yourself.** `$ARGUMENTS` is either
`--show` (or empty, which means `--show`) or `--set key=value`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/config_cli.py" --workspace . ${ARGUMENTS:---show}
```

So `/vibe-suite:config` and `/vibe-suite:config --show` both view; `/vibe-suite:config --set
stop_review_gate=on` sets that one toggle and nothing else. Running a `--set` the user did not ask
for would change their project on a read.

Add `--json` when you need the structured form.

## The three toggles, and why their defaults matter

| Toggle | Default | Why that default |
|---|---|---|
| `stop_review_gate` | **off** | Opt-in (D3). A review gate that switched itself on would block sessions nobody asked it to. |
| `fail_policy` | **open** | A gate that cannot reach a verdict lets the session end. Failing closed is what left cc-suite's sessions unable to finish (W3). |
| `gate.model` | **unset** | P9 forbids a *shipped pin*, not the capability. Set one if you want it; none ships. |

`--show` prints these as values, so an unset model reads `(unset)` rather than vanishing — a default
you cannot see is a default you cannot question.

Accepted for booleans: `on`/`off`, `true`/`false`, `yes`/`no`, `1`/`0`.

## What `--set` will not do

**Write `.vibe-suite.md`.** That file is the user's, and `--set` is scoped to the runtime toggles —
anything else is refused by name rather than silently ignored. To change `effort`, `engine` or
`skip_patterns`, edit the file.

## What `.vibe-suite.md` cannot do

**Set the gate.** The three `gate.*` keys are **store-only** (vibe-186 / grill S2): the project file
is repository content a clone inherits, so it must not be able to switch the Stop-review gate on,
fail it closed, or choose its model. A `gate` block in `.vibe-suite.md` is ignored and `--show`
lists a warning naming the rule; the toggles come from `--set` (and init's explicit opt-in) alone.

**Raise the sandbox silently.** `sandbox: workspace-write` (or `danger-full-access`) in the project
file is honoured, and **noticed**: `--show` lists `notice: sandbox 'workspace-write' in
.vibe-suite.md raises every codex dispatch from this workspace above read-only` under Warnings, and
every codex dispatch prints the same line to stderr. `danger-full-access` still needs
`--confirm-danger` at dispatch.

## Reading the output

- **A fresh project is a complete answer.** With no `.vibe-suite.md` you get schema defaults and the
  toggles' shipped values. That is not an error.
- **Warnings are shown.** An unknown key in `.vibe-suite.md` is reported rather than dropped — it is
  the one signal that a setting you wrote is not being read.
- **An invalid file is reported, not survived.** A config the canonical reader rejects exits non-zero
  with the reason, because a viewer that prints defaults over a broken file would hide it.
