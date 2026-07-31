---
contract_version: 1
project_id: minimal
repo_id: minimal-repo
repo_path: ./tests/fixtures/issue2pr/fixture-repo
base_branch: main
source_driver: github
id_pattern: '^m-(\d+)$'
url_regex: '^https://github\.com/acme/minimal/issues/(\d+)/?$'
branch_template: 'acme/ai/{id}'
gates:
  - 'true'
---

# minimal — required fields only

No optional field is present. This is the shape `profile init` emits before any interview answer is
folded in, so a lint that demanded an optional field would block that scaffolder.
