---
contract_version: 1
project_id: Roamex
repo_id: example-org/roamex
repo_path: ./codes/roamex
base_branch: main
source_driver: github
id_pattern: '^roam-(\d+)$'
url_regex: '^https://github\.com/example-org/roamex/issues/(\d+)/?$'
branch_template: 'example-org/ai/{id}-{slug}'
gates:
  - 'autoninja -C out/Default chrome'
  - 'out/Default/unit_tests'
gate_mechanics: 'Build before test; a failing build is not a failing test and is reported as such.'
tdd_policy: 'A behavioural change lands with a test that fails without it.'
anti_patterns:
  - 'Editing upstream sources directly instead of through the overlay.'
  - 'Shipping a behavioural change without a flag to turn it off.'
mental_model_refs:
  - 'docs/architecture/overlay.md'
category_extensions:
  step-2: 'overlay-discipline'
  step-8: 'flag-gating'
---

# Roamex — a reference profile

**This profile ships as an example and is not usable.** It names a repository you have not checked out,
which is the point: it shows what a complete profile looks like without pretending to be one you can
run.

It is validated **structurally** — fields, types, domains, regexes. Full validation would need
`./codes/roamex` to exist, and a lint that demanded that would be asking every reader to clone someone
else's project.

Generate your own with `/vibe-suite:issue2pr profile init`.

## What this example is for

Two things a field list cannot show:

- **`gate_mechanics` earns its place here.** The two gate commands do not say that the build must
  precede the test, or that a build failure is a different report from a test failure. That is prose
  because it is judgement, and judgement is what the optional fields carry.
- **`category_extensions` are additive, not replacements.** `overlay-discipline` joins the core
  categories at step 2; it does not displace `correctness`. A profile cannot remove a core category,
  because the core's reviewers rely on them.
