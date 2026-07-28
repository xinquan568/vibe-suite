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

## How restore decides

Provenance holds each target's **pre-init** bytes. But that hash cannot detect a later user edit —
init changed the file, so it always differs. The order that works:

1. Remove the owned region.
2. Compare what remains to the pre-image.

| Result | Action |
|---|---|
| identical | the file is byte-identical to pre-init — nothing else to do |
| different | **keep what remains.** The user edited outside our block, and restoring the pre-image would overwrite their work |

A file init *created* is deleted — unless something other than the owned block is now in it, in which
case it is kept and reported. `kind: absent` means delete, and that is where user content is most at
risk.

## What it will not do

- **Trust the record.** Every path in it is re-checked against the workspace and refused if it points
  outside, whatever the record says.
- **Prune a directory that is not empty.** `parents_created` records what init made; a user may have
  put files there since.
- **Run without provenance.** With no record there is nothing to restore *from*, and guessing which
  bytes were the user's is exactly the mistake teardown must not make.
