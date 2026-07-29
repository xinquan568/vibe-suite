---
name: vocabulary
description: Vocabulary discipline for suite artifacts — canonical/deprecated term semantics, scope and homonym rules, drift detection, and the registry file format.
---

# Vocabulary Discipline

One concept, one name. When writing, reviewing, or naming any artifact — a
command, agent, skill, rule, or workflow — reach for the noun or verb the
registry marks canonical rather than coining a synonym. Synonym drift is what this skill
exists to prevent: two names for the same thing force every reader to prove to
themselves that the names are not two things.

Enforcement wiring: deprecated synonyms are flagged by `/vibe-suite:check` and
penalized by `/vibe-suite:score` (rule R51, below).

## Registry status — read this first

This skill defines the discipline and documents the registry FORMAT. The suite's
registry DATA — the authoritative canonical/deprecated tables and the
machine-readable `registry.yaml` sidecar — does not ship with this skill. That
file is delivered by the vocab tooling stage (E3.7). Until it lands, R51 cannot
fire and remains a documented, disabled capability, and every term table in this
file is a worked example of the semantics, not the suite registry itself.

## Boundary with the conventions skill

- The [conventions](../conventions/SKILL.md) skill owns upstream framework
  terms: hook event names, frontmatter fields, manifest keys.
- This skill owns project-internal domain language.
- Litmus test: a term that comes from Anthropic's documentation belongs to
  conventions; a term that comes from our own corpus belongs here.

## Term lifecycle

Every term the registry knows about is in exactly one of four states:

| State | Meaning | Drift flagging |
|---|---|---|
| canonical | the one name for a concept within its scope | never flagged |
| deprecated | a retired synonym, listed under its canonical term | flagged wherever it appears inside the scope's paths |
| deferred (pending warrant) | passes principles P2–P5, awaiting warrant; names a gap that currently has no word | never flagged — a nameless gap is not a synonym; becomes canonical on first practitioner use |
| rejected (by higher principle) | permanently barred from entry | never entered; warrant cannot reinstate it |

## Canonical/deprecated table semantics

A verb entry records: the canonical term, its deprecated synonym list, its
output (what running the verb produces), a judgment flag (whether the operation
involves judgment or is deterministic), and optional notes. A noun entry
records: canonical, deprecated list, definition. A role-noun entry records:
canonical plus the top-level verb it is paired with.

Two rules give the tables their teeth:

- Retiring a synonym means listing it on the canonical term's deprecated line.
  Never silently remove a term — deprecation is a visible vocabulary act.
- Each deprecated synonym points at exactly which canonical term replaces it,
  with a disambiguation note when two could. Worked examples:
  - `lint`, `validate` → `check` for structural consistency, `score` for quality;
  - `find`, `search`, `list` → `ls`;
  - `analyze` → `score` when the result is quantitative, otherwise the specific
    verb for what is actually being done.

## Scopes and homonyms

The registry declares scopes (principle P1): each scope has an id, a
description, and the path globs it governs. Canonicality is per-scope — a verb
that is canonical in one scope may be meaningless or forbidden in another.

- Using a scope-bound verb in the other scope is a violation: either rename, or
  declare a second scope-specific definition for it.
- The same verb in two scopes with the same identity criterion is a sanctioned
  homonym — a boundary, not a collision — and must be declared in the registry's
  cross-scope homonym table.

Collision rules:

- Same scope, same identity criterion → a real collision: retire one term or
  split the scopes.
- Same identity criterion across scopes → sanctioned homonym; declare it.

## Bright-line disambiguation

When several verbs cluster around one activity, the registry carries a
bright-line table so authors can pick without judgment calls. Worked example —
the evaluation cluster (illustrative; the authoritative version ships with the
E3.7 registry):

| Verb | Deterministic | Judgment | Output | Use when |
|---|---|---|---|---|
| `score` | yes | no | number + penalty list | quality is quantified against a rubric |
| `check` | yes | no | violation list | cross-references and structural consistency |
| `test` | yes | no | pass/fail | actual behavior versus a named spec |
| `scan` | yes | no | findings vs a signature DB | matching a known problem class |
| `audit` | partly | YES | composite report | score + scan + judgment combined |
| `review` | no | YES (human) | comment trail | a human reads and forms an opinion |

The deterministic/judgment split is the identity criterion doing its work: two
verbs may share an output shape, but if one is mechanical and the other requires
an opinion, they are different concepts and both earn a canonical slot.

## Warrant discipline

A term enters the registry only with warrant — evidence that the name is needed.
There are four warrant types (principle P6): literary, user, structural, and
domain.

- Literary warrant means the term already appears in at least one artifact in
  the corpus today. Every listed term must carry it, and it is verified by the
  extraction tooling delivered with E3.7 — rerun the extraction after any add or
  rename.
- Entry bar: a term already in use enters on literary warrant alone; a brand-new
  coinage needs a user, structural, or domain warrant.
- Precedence: warrant is checked last. It is an entry requirement, not a veto
  override — a term that fails one of the higher principles P1–P5 cannot be
  rescued by any amount of warrant.

## Drift detection

### R51 — canonical-term enforcement

- Opt-in, disabled by default. Enable via `rule_overrides.R51.enabled: true` in
  the suite's project config (`.vibe-suite.md`).
- Penalty: -2 per occurrence of a deprecated synonym, capped at -10 per file.
  Disabled means zero penalty, always.
- Prerequisites: a `vocabulary_skill:` setting pointing at a vocabulary skill
  that has a `registry.yaml` sidecar. If either is missing, R51 cannot fire and
  the scorer emits an advisory note instead.
- Deferred terms are exempt from R51 flagging — they are not synonyms.
- Readers: only the check and score paths read the registry, and only while R51
  is enabled.

### Registry-free companion: the drift scan

A judgment-based drift scan clusters likely-synonymous nouns and verbs across a
corpus with no registry at all. Its output is advisory only — no penalty. Use it
on projects that have not adopted R51 yet, or alongside R51 as a periodic check
that the registry is still exhaustive. It ships as its own command/agent path in
the vocab tooling stage (E3.7).

## registry.yaml — format

Role: `registry.yaml` is the machine-readable sidecar to the human-readable
canonical tables. The two are kept in sync; on conflict, the human-readable
source wins. Provenance: the registry is hand-maintained — the extraction
tooling emits a term-frequency table only, not the canonical/deprecated split
(automatic regeneration is future work).

Schema — six top-level keys:

| Key | Shape |
|---|---|
| `scopes` | list of `{id, description, paths[]}` — P1 scope declarations mapping each scope to its path globs |
| `cross_scope_homonyms` | `{verbs: [..]}` — verbs sanctioned to exist in more than one scope |
| `verbs` | map keyed by scope id; each entry `{canonical, deprecated[], output, judgment(bool), notes?}` — R51 flags deprecated-synonym occurrences within that scope's paths |
| `deferred_pending_warrant` | list of `{verb, scope?, proposed_for, p2_p5_pass, needed_warrant}` — becomes canonical on first practitioner use; never flagged deprecated |
| `rejected_by_higher_principle` | list of `{verb, scope, blocker_principle, blocker}` — never entered; warrant cannot reinstate |
| `nouns` | subkeys `artifact_class[]` and `output_class[]` with entries `{canonical, deprecated[], definition}`, plus `role_nouns[]` with entries `{canonical, paired_verb}` |

The three noun classes:

- **Artifact-class nouns** name the rigid file kinds that survive state changes:
  `command`, `agent`, `skill`, `rule`, `hook`, `manifest`, `frontmatter`, with
  `artifact` as the umbrella for any NL file.
- **Output-class nouns** name what operations produce: a `finding` (one detected
  problem), a `violation` (a finding from a cross-reference check), a `penalty`
  (the points one finding subtracts), a `score`, a `snapshot`, an `inventory`,
  a `report`, a `spec`.
- **Role nouns** are worker names paired with a top-level verb — a `scorer`
  performs `score`, a `checker` performs `check`. They are implementation roles,
  never top-level verbs themselves.

## Extension procedure

Five steps, in order:

1. Add a term only with warrant — one of the four types above.
2. Rerun the literary-warrant extraction (vocab tooling, E3.7) so the frequency
   summary reflects the change; rerun it again after any rename.
3. Slot the term into the right table: scope verb, artifact-class noun,
   output-class noun, or role noun.
4. Cite at least one file path as corpus evidence for the entry.
5. To retire a synonym, list it under the canonical term's deprecated line —
   never silently drop it. Deprecation is a visible vocabulary act.

## Related skills

- Framework-defined terms: [conventions](../conventions/SKILL.md).
- The quality-rule catalog that hosts R51: [rules](../rules/SKILL.md).
- Penalty tables and calibration: [scoring](../scoring/SKILL.md).
