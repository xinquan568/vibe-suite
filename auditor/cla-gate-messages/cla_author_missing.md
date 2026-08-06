The vibe-suite auditor prepared fix PRs for this repository, but it is skipping
submission for now.

Repositories owned by **{{OWNER}}** require a signed Contributor License Agreement (CLA),
and CLA checks verify the *author identity* on each commit. This project has a CLA
signature attested, but the repository variables naming the CLA-covered author (the
human contributor's name and email) are not set — so any PR we opened would fail the
owner's CLA check on author identity, wasting maintainer time.

Nothing is lost: the audit findings remain recorded, and this tracking issue stays open.

To re-enable contributions for this repository:

1. Set the repository variables for the CLA-covered author's name and email — they must
   match the identity that signed the CLA.
2. Re-add the contribute-approval label to this issue — the contribute workflow will
   re-run, configure the commit author from those variables, and pick up from here.
