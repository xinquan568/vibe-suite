---
contract_version: 1
project_id: fixture
repo_id: fixture-repo
repo_path: ./tests/fixtures/issue2pr/fixture-repo
base_branch: trunk
source_driver: github
id_pattern: '^fx-(\d+)$'
url_regex: '^https://github\.com/acme/fixture-repo/issues/(\d+)/?$'
branch_template: 'acme/ai/{id}-{slug}'
gates:
  - 'make lint'
  - 'make test'
---

# fixture — a profile that exists to be validated

Every field above is a **target-project** value. None of them may appear in the core, and all of them
appear here, which is what makes this file usable as the forbidden-set source.
