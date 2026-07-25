# Severity — worked examples, effort guidance, and external mappings

Expansion for [`../SKILL.md`](../SKILL.md). The definitions themselves live there, because agents
preload `SKILL.md` in order to apply the scale; this file is for when a judgement is close.

## One example per level

**`[CRITICAL]`** — A hook script passes unquoted user-controlled input to `shell=True`. Every
contributor who runs the hook in a hostile checkout executes whatever the repository author put in
that field. Runs on a normal path, no workaround, immediate.

**`[HIGH]`** — A config reader resolves symlinks before checking whether the target is inside the
project root, so a crafted symlink causes the tool to read and report a file outside it. Reachable,
no user-side workaround — but it requires a specific setup, so it is bounded.

**`[MEDIUM]`** — A duplicate key in a config file silently resolves to the last occurrence. Wrong,
and it will surprise someone, but the effect is contained and a user who notices can reorder the
file. Most correctness findings land here.

**`[LOW]`** — A helper recompiles the same regex on every call inside a loop over a few dozen files.
Measurable but immaterial at current scale; worth fixing when the function is next touched.

**`[GOOD]`** — "Reviewed all twelve command files against the namespace rule; every command is
registered under the `/vibe-suite:` prefix and no stale source-project prefixes remain." A statement
of what was checked and found sound — not "looks fine".

## Choosing between adjacent levels

- **`[CRITICAL]` vs `[HIGH]`** — is it happening on a path that runs in normal use, or does it need
  a specific trigger? Normal path with no workaround is `[CRITICAL]`.
- **`[HIGH]` vs `[MEDIUM]`** — can the user recover? A workaround, an undo, or a contained blast
  radius makes it `[MEDIUM]`. This is the boundary most often got wrong.
- **`[MEDIUM]` vs `[LOW]`** — will anyone actually hit this? Latent hazards on unreachable paths are
  `[LOW]` until something reaches them.

When genuinely torn, pick the **lower** level and say in the tradeoff field why it might warrant the
higher one. Inflation costs more than understatement: it erodes the scale for every later finding.

## Effort estimation

Estimate the fix **and its verification**, not the edit alone. A one-line change requiring a new
test fixture and a CI adjustment is not `[<1 day]`.

| Class | Shape of work |
|---|---|
| `[<1 day]` | Localised change, existing test covers it or one obvious test to add. |
| `[<1 week]` | Several files, or a change needing new test infrastructure. |
| `[<1 month]` | Cross-cutting change, or one requiring a migration for existing users. |
| `[>1 month]` | Architectural. Usually indicates the finding should become its own proposal. |

## External mappings

Two producer-side scales map into this vocabulary. They are **independent** mappings into a shared
target, not a crosswalk between each other — a numeric penalty and a judged level need not
correspond.

### How a mechanical mapping relates to the definitions

**The mapping produces a starting severity; the definition decides the final one.**

This has to be stated, because the two cannot be made perfectly consistent and pretending otherwise
would quietly corrupt the scale. nlpm's mapping is arithmetic: a score crosses 10, the band says
`[HIGH]`. The `[HIGH]` definition is a judgement: *does this materially undermine the artifact's
purpose, in a way a consumer cannot route around?* Some ≥ 10 scores are assembled from deductions —
excessive length, missing examples — that plainly fail that test.

So the procedure is:

1. Apply the mapping. It gives you a **starting** severity, and it is right far more often than not.
2. Check it against the definition.
3. If they disagree, **the definition wins** — and the finding states in one line why the band was
   not followed. For example: *"nlpm scored 12, which bands to `[HIGH]`; recorded `[MEDIUM]` because
   the deductions are length and example-count, and the skill still triggers and applies correctly."*

Adjustments are expected to be uncommon and always downward-justified in writing. An unexplained
departure from the band is severity inflation or deflation, which the anti-patterns forbid.

The band tables below are **unchanged** — this section governs how they are read, not what they say.

### nlpm numeric penalties

| Penalty | Level |
|---|---|
| ≥ 10 | `[HIGH]` |
| 5–9 | `[MEDIUM]` |
| < 5 | `[LOW]` |

**Why ≥ 10 bands to `[HIGH]`.** That range is typically reached when a skill's description will not
trigger when it should, or its structure prevents a consumer from applying it — which satisfies the
`[HIGH]` definition directly. *Typically*, not always: a score can also reach 10 by accumulating
deductions that do not defeat the artifact's purpose. That is exactly the case the procedure above
covers — band first, definition decides, disagreement recorded.

nlpm emits no `[CRITICAL]`: an artifact-quality deduction, however large, does not by itself mean
nothing downstream can rely on the artifact at all. A `[CRITICAL]` on an NL artifact is a judgement a
reviewer makes, not one the penalty table produces.

### cc-suite audit severities

| cc-suite | Level |
|---|---|
| Critical | `[CRITICAL]` |
| High | `[HIGH]` |
| Medium | `[MEDIUM]` |
| Low | `[LOW]` |

A direct correspondence — cc-suite's scale was one of the inputs to this one.

## Machine-readable form

[`schemas/audit-output.schema.json`](../../../schemas/audit-output.schema.json) encodes the contract.
Validate a report with:

```bash
python3 scripts/validate_audit_output.py <report.json>
```

The validator implements only the keyword subset that schema uses and **halts on anything else**, so
a schema change that outruns it fails loudly rather than going unchecked.
