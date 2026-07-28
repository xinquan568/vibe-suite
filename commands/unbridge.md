---
description: "Complete teardown of a vibe-suite installation: removes every owned sentinel, block and registration by iterating the shared inventory, restores files from the provenance record, and prunes directories init created. Also clears legacy cc-suite registrations. Asks once before doing any of it. No arguments."
argument-hint: ""
---

# /vibe-suite:unbridge — complete teardown

Removes everything the suite installed and restores what it found. **Nothing user-owned is touched.**

## What to do

### 1. Show what would go, then ask once

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/unbridge.sh" --workspace .
```

Without `--confirm` this changes nothing and exits 3 with the list. Show that list, then ask **one**
AskUserQuestion — and name **both** destructions, because one confirmation covers them:

> Remove every vibe-suite artefact from this project **and** any legacy `cc-suite-*` registrations?

A confirmation that describes one destruction and performs two is not a confirmation.

### 2. On yes

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/unbridge.sh" --workspace . --confirm
```

Report the per-artefact outcome as returned.

## It removes; it does not restore

**Init only ever *adds* owned regions** — a block between markers, a named key, a file it created. It
never rewrites content outside them. So removing those regions **is** the restore, and for a project
nobody edited the result is byte-identical to pre-init by construction.

Nothing is ever written back from the provenance record. That was the design this command started
with, and it was the source of every way it could lose your work: a pre-image cannot tell an
untouched file from an edited one, and a wrong guess overwrites what you wrote. A teardown that only
removes cannot fail that way.

| Situation | What happens |
|---|---|
| a file you owned, with our block in it | the block goes; every other byte stays exactly as it is |
| a file init created, now holding only our block | removed |
| a file init created, now holding something of yours | **kept**, and reported |
| a file that existed before install | never deleted |

The record is still read, for one thing: whether a file existed before install. That is what decides
remove-the-block from remove-the-file.

The suite's own artefacts — `.vibe-suite.md`, the baseline history, `.vibe-suite-state/` — are
removed. Editing the suite's config does not make it yours.

## What it will not do

- **Trust the record.** Every path in it is re-checked against the workspace and refused if it points
  outside, whatever the record says.
- **Prune a directory that is not empty.** `parents_created` records what init made; a user may have
  put files there since.
- **Run without provenance.** With no record there is nothing to restore *from*, and guessing which
  bytes were the user's is exactly the mistake teardown must not make.
