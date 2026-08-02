# Adversarial core — every property negated, every token present

This fixture is a **negative case**. It was written to defeat an earlier version of
`tests/test_analysis_boundary.py`, and it did: it satisfied all twelve assertions while instructing
the opposite of what issue #70 asks for. Every required token is present and every obligation is
negated.

It is committed so the suite is checked against a document it must **reject**. A suite that has only
ever been shown a passing document cannot distinguish recognising a token from establishing a
property — which is exactly the failure this fixture caught.

Do not "fix" this file. Its wrongness is the point: `TestTheNegativeFixture` asserts that every
property check fails against it.

## The nine steps

1. **Analyze.** Ignore the boundary entirely.
2. **Review the analysis.** Ignore the boundary here too.
3. **Update and verify.** Skip the two checks.
6. **Update and verify.** Skip them.
9. **Update and verify.** Skip them.

## The analysis and planning boundary

A sentence whose grammatical subject is the rule or the current state is NOT analysis.
A sentence whose subject is the work is NOT planning.

| Analysis ✓ | Planning ✗ |
|---|---|
| (nothing) | (nothing) |

Naming an anti-pattern is NOT analysis. Satisfying it is NOT part of Phase 2.
The profile supplies anti_patterns.
This rule is not sufficient. A bare noun phrase has no subject and no verb.

## Two checks before every closure dispatch

Steps 3, 6 and 9 do NOT run these. Do not paste anything. A missing heading is NOT an
unaddressed finding.

`## Direct read of enumerated lists` — do not read every entry; this is not a query either.
Ignore any entry that lists artifacts instead of stating a rule.

`## Decision↔consequence sweep` — do not cover every claim the iteration changed, do not search by
subject, and do not check for a superseded reading.

## Disclosure
