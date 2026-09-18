# ADR-0004 — Authoritative job records must carry the ownership stamp

**Date:** 2026-09-18 · **Issue:** [#302](https://github.com/xinquan568/vibe-suite/issues/302) (the decision) · [#261](https://github.com/xinquan568/vibe-suite/issues/261) (the gap it closes)

## Status

Accepted.

## Context

Every record the jobs store *creates* — `createRecord`'s canonical and every candidate slot a writer stages — has carried an
ownership stamp, `{"_vibe-suite_owned": {"kind": "job-scratch", "schema": 1}}`, since `554be10` (vibe-103). That is not
the same as every record on disk being stamped: a legacy slot recovered by `rollForward` or by `readCanonical`'s self-heal
was republished byte for byte, so a stamped store could produce an unstamped canonical at any later date. Deletion has
proven that stamp from the start: compaction and prune remove a slot only through `unlinkOwned`, which refuses an
unstamped file. Reads did not prove it. #261 made the three authoritative slot reads — the self-heal in `readCanonical`,
`rollForward`, and `commit`'s own read before publication — refuse a symlink, and declared the remaining gap: an
unstamped **regular** file whose `jobId` and `version` matched its name was still read as the authority. That left the
store believing a record it would never clean.

Requiring the stamp on reads rejects every record written before `554be10`, and it raised a migration question the
issue posed as three options: grandfather (accept unstamped on read, stamp on write), migrate (an offline converter and a
store version gate), or cut over (require the stamp; refuse the rest). The decision was taken after a two-round
design discussion (analysis by Claude Fable 5.1; second opinion by GPT-6 Astra, the reviewer backend's default model
on 2026-09-18) and pinned on the issue.

## Decision

**Cut over — an explicit pre-release compatibility break at `0.0.1`.**

1. Every authoritative read proves the stamp: the three slot reads **and the canonical** (`readPublished`, and
   `readCanonicalRaw` where `commit` confirms against the canonical). The canonical is included because
   `readCanonical` returns it whenever no slot exists or its version reaches the highest slot; enforcing slots only would
   leave every fully committed legacy job readable.
2. One observation per read, on one handle: a regular file (a FIFO is refused without being opened), parseable JSON, a
   stamp of kind `job-scratch` and the current schema, and — at `commit` — the identity of the slot that observation saw.
   The raw bytes of that observation are what `commit` publishes.
3. A record that fails is **refused, never deleted, never auto-stamped**. The refusal names its cause — no stamp, a stamp
   of another kind, an unsupported schema, unparseable, wrong identity — and says what to do: quiesce writers, preserve
   the canonical and every slot, quarantine the job or recover it offline. A missing stamp is reported as missing; it does
   not prove a pre-`554be10` origin.
4. The failure is local to the job. A listing keeps every healthy record and reports the refused one with its reason;
   the CLI exits non-zero when a listing contains one. Prune reports a foreign record as **blocked** with the file in
   `leftovers` — the category it used before, when `entomb` refused the same file after the read — and keeps `invalid`
   for records that are ours but broken. A validly marked (mid-prune) job stays "no record (pruned)" to readers
   whatever now sits at its path. A prune marker that cannot be inspected on a read is itself a refusal with the
   same guidance — the canonical's own refusal when one was already observed — never a raw error, never one
   the self-heal can swallow, and in a listing only that job's row; so is a directory at a job's canonical path
   that cannot be inspected.
5. A refusal raised inside `commit` carries the refusal flag, so the best-effort self-heal in `readCanonical` cannot
   swallow it and hand a caller a healthy-looking record.

## Consequences

- **Compatibility.** A workspace whose `.vibe-suite-state/jobs/` holds records that predate `554be10` (2026-08-05) — or
  canonicals that a later recovery republished from such records, which carry no stamp whatever their date — sees those
  jobs refused with the message above until an operator quarantines or recovers them. No such workspace
  was found on the maintainer's machine; the plugin is `0.0.1` and unreleased; the README's upgrading note carries the
  procedure. This is a bounded, documented break made before any release, not a maintained migration path.
- **Why not grandfather.** The read/delete mismatch would be permanent: an unstamped record would stay believed by
  reads and untouchable by deletes.
- **Why not migrate.** An offline, quiesced converter is feasible, but a stamp it adds cannot prove a legacy file's
  origin, and maintaining a converter without demonstrated demand is unnecessary at `0.0.1`.
- **What this does not do.** The stamp is a public marker, not a secret: a same-uid actor who can write a well-formed
  record can write a stamped one. This is defence in depth and internal consistency, not a privilege boundary — exactly
  as `scripts/lib/write.mjs` and `fsafe.py` declare. No store version marker is added. Prune's and compaction's
  ownership rules are unchanged. Node has no `openat`, so the guarantee remains "refuses the state observed", with the
  post-observation window still open.
