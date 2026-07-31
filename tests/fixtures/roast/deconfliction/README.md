# Deconfliction fixture — E4.2 (vibe-36)

One seeded defect, contested ownership. `service/client.py` reads configuration with no validation,
no default, and a swallowed `KeyError` that leaves `timeout` unset on the failure path.

The defect is deliberately placed where an architecture reviewer would find it — at a module boundary,
on the path from the entry point — because the question this fixture settles is *which* reviewer owns
it. Per F3.4 `error-handling` is the primary owner of config management; per F3.3 `architecture`
defers config findings to it. `ownership.json` records the expected attribution.

**Two consumers.** `tests/test_roast_agents.py` checks the static half now: the declared owner claims
config and the declared non-owner defers it. E4.3 (#37), the roast orchestrator, has a runtime and can
dispatch both agents against this tree to check the dispatched form. The fixture is shaped so that
issue needs no change to it.
