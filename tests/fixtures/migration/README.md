# §7A migration fixtures (E2.8 / vibe-25, AC-5)

One directory per §7A row. Each holds only the *legacy* artefacts a project would already have;
the harness copies a row into a scratch workspace, runs the real `/vibe-suite:init`, and asserts
that row's contract.

The property common to rows 1-3 is that **the legacy original is untouched** — migration reads
it and writes elsewhere. That is what "legacy byte-identical" in AC-5 means, and it is why these
fixtures are inputs rather than expected-output trees.
