#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The mirror inventory — ONE home for the tables the mirror-sync generator renders from and the
`bin/vibe-check --mirrors` checker compares the manifest against (M12 / vibe-220).

Before this module the checker carried a deliberately duplicated copy, held identical to the
generator's tables by a test. The duplication guarded against a corrupted MANIFEST shrinking its own
declarations — a guard that survives sharing, because the checker still compares the manifest to the
table and never trusts the manifest about itself. What sharing removes is the two-handed edit.

A library module: stdlib only, no bootstrap, no `sys.path`, no writes. Programs import it after
`scripts/_bootstrap.py` has put `scripts/lib` on the path.
"""

from pathlib import Path

#: F9.6 set (a): the merge's 19 knowledge skills plus the post-merge additions `auditing`
#: (E4.1) and `roasting` (E4.3) — the 21-skill scope reading recorded in the vibe-54 plan.
KNOWLEDGE = (
    "agent-design", "auditing", "conventions", "conventions-antigravity",
    "conventions-claude", "conventions-codex", "orchestration", "patterns", "roasting",
    "rules", "scoring", "security", "testing", "vibe-core", "vocabulary",
    "writing-agents", "writing-hooks", "writing-plugins", "writing-prompts",
    "writing-rules", "writing-skills",
)
#: User-invocable workflow skills — outside set (a) by scope, not by portability.
WORKFLOW = ("issue2pr", "refine-proposal", "runs-stats")
#: F9.6 set (c): the six roast analysis agents.
ROAST_AGENTS = ("architecture", "edge-cases", "error-handling", "recon", "security",
                "testing")

#: Out-of-mirror destinations copied into the mirror (source → mirror), per the vibe-54
#: frozen analysis's dependency inventory.
COPIED_DEPS = {
    "schemas/audit-output.schema.json": "codex/schemas/audit-output.schema.json",
}
#: commands/shared partials copied under vibe-auditing (set-(a) links rewritten to them).
AUDITING_PARTIALS = ("classify", "discover")

#: Every mandatory generated output beyond the per-set files: source -> mirror. The checker
#: requires each pair recorded exactly; deleting any pair is a finding, not a silent shrink.
GENERATED_OUTPUTS = {
    "commands/roast.md": "codex/skills/vibe-roast/SKILL.md",
    "commands/shared/classify.md": "codex/skills/vibe-auditing/references/classify.md",
    "commands/shared/discover.md": "codex/skills/vibe-auditing/references/discover.md",
    ".claude-plugin/plugin.json": "codex/README.md",
}

#: Slash-command dispositions. `roast` is rewritten to its mirrored identity; every OTHER command
#: is kept literal under the banner note — and "every other command" is read from `commands/*.md`
#: at generation time (`command_stems`), never hand-listed (M12): a hand-held list carried `scan`,
#: which is no command, and omitted fourteen that are. A reference to a name that is neither
#: rewritten nor a command file is a generation error, never a silent pass.
SLASH_REWRITE = {"roast": "$vibe-roast"}


def command_stems(root):
    """The top-level slash commands of the plugin at `root`: `commands/*.md` stems, sorted.
    `commands/shared/` partials are not commands and are not included."""
    return tuple(sorted(p.stem for p in (Path(root) / "commands").glob("*.md")))


def slash_literal(root):
    """The commands kept literal in the mirror: every command file that is not rewritten."""
    return tuple(s for s in command_stems(root) if s not in SLASH_REWRITE)


#: What `bin/vibe-check --mirrors` compares the manifest's declarations and the tree against.
EXPECTED = {
    "knowledge": KNOWLEDGE,
    "workflow": WORKFLOW,
    "roast_agents": ROAST_AGENTS,
    "copied_deps": COPIED_DEPS,
    "generated_outputs": GENERATED_OUTPUTS,
}
