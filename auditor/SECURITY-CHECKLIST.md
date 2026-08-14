# F10.1 security checklist — operator sign-off before the first external audit

This file is the durable record the `auditor-integration-test` unit tier verifies. The
pipeline scaffolds it UNCHECKED and refuses to go green until the operator has attested
every row and signed the line at the bottom — checking these boxes is a human act the
pipeline can only verify, never perform. Check a row by editing `[ ]` to `[x]`; sign by
replacing the placeholder name and date on the `Signed-off-by:` line (the verifier
requires an ISO date, `YYYY-MM-DD`).

- [x] **PAT scope** — the contribution `PAT_TOKEN` (when contribution is enabled) is
  minimum-scope: public-repo fork/PR only, no org, no admin, no packages.
- [x] **Rotation doc** — the PAT's rotation procedure and cadence are written down where
  the operator will find them (secret name, owner, rotation interval, revocation path).
- [x] **Injection separation** — audited third-party content reaches every model step as
  data, never instructions (the prompts' data-not-instructions framing), and the
  contribution surface is patch-only with the path allowlist enforced before apply.
- [x] **Audit token scope** — `CLAUDE_CODE_OAUTH_TOKEN` is present in the repository's
  Actions secrets and scoped to this repository only.
- [x] **No secret egress** — no workflow writes a secret value into the tree, an
  artifact, or a log (the tiers echo names and verdicts, never values).

Signed-off-by: Eric Y. Liu 2026-08-14
