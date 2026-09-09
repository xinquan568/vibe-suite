#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The one executable statement of the engine-resolution ladder (M8 / vibe-221).

Before this module the ladder lived twice: as prose in `commands/shared/model-selection.md`, which every
engine-dispatching command was told to read, and — for sandbox/effort/model only — as six lines in
`scripts/lib/config-bridge.mjs`. Nothing resolved `engine` or `cross_model_audit_engine` in code; the
default engine was stated per command and nowhere else. This module states the ladder once; the CLI
seam is `python3 scripts/config_cli.py resolve-engine`, and the partial keeps the vocabulary.

The ladder, highest first: the caller's explicit choice; the project's `.vibe-suite.md`; the caller's
default. For the model the terminal action is DEFER — `None` here, which the caller turns into *no
model flag at all*, so the engine CLI runs whatever it is configured with (P9: no default model is ever
synthesised). `both` is a composition, not an engine: it expands to Claude plus the resolved
`cross_model_audit_engine`, and the one external constituent is what `model` describes.

A library module: stdlib only, no bootstrap, no `sys.path`, no writes. `config` is passed in by the
program that loaded it (the seam), never imported here, so the reader stays the one reader.
"""

DEFAULT_ENGINE = "claude"
#: The in-session engine: no external process, no model to name.
IN_SESSION = "claude"
#: The one value that is a composition rather than an engine.
COMPOSITION = "both"


class EngineResolutionError(ValueError):
    """A caller mistake: an engine or default outside the schema's domain. Never coerced."""


def _domain(schema_row):
    return tuple(schema_row.domain.split("|"))


def resolve(config, *, engine=None, model=None, default=DEFAULT_ENGINE, engines):
    """Resolve `{engine, cross_model_audit_engine, lanes, model}` for one command invocation.

    `config` is the reader's resolved mapping (`config.load_with_warnings(root)[0]`); `engines` is the
    schema's domain for `engine` (`config.SCHEMA["engine"].domain.split("|")`), passed in so the domain
    has one home. `engine`/`model` are the caller's explicit choices (a `--engine`/`--model` flag);
    `default` is the caller's default when neither the flag nor the project file names an engine.
    """
    engines = tuple(engines)
    if default not in engines:
        raise EngineResolutionError(f"default engine {default!r} is not one of {', '.join(engines)}")
    chosen = engine if engine is not None else (config.get("engine") or default)
    if chosen not in engines:
        raise EngineResolutionError(f"engine {chosen!r} is not one of {', '.join(engines)}")
    cross = config.get("cross_model_audit_engine")
    lanes = [IN_SESSION, cross] if chosen == COMPOSITION else [chosen]
    external = [lane for lane in lanes if lane != IN_SESSION]
    overrides = config.get("model_overrides") or {}
    if external:
        lane = external[0]
        resolved_model = model if model is not None else overrides.get(lane)
    else:
        resolved_model = None          # in-session: there is no model to name
    return {"engine": chosen, "cross_model_audit_engine": cross, "lanes": lanes, "model": resolved_model}
