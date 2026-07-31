# `profile init` fixtures

One repository per detection case, each differing in exactly one way, so a failure names the rule that
broke rather than "something about detection".

| Fixture | What it isolates |
|---|---|
| `ssh-remote` | an `origin` in `git@host:owner/name.git` form |
| `https-remote` | the same repository in `https://host/owner/name.git` form — both must yield one `repo_id` |
| `odd-default-branch` | a default branch that is not `main`; nothing may assume the common name |
| `metachar-name` | a repository name containing a regex metacharacter, which is where an unescaped conversion produces a pattern that compiles and matches the wrong thing |
| `no-gates` | nothing to detect — `gates` must come out empty rather than guessed |
| `node-gates` | a `package.json` whose scripts are real |
| `make-gates` | a `Makefile` whose targets are real |
| `no-remote` | a precondition failure |

These are **not** git repositories on disk; `detect_profile.py` takes the git facts as inputs so that
detection is deterministic and testable without constructing eight real repositories. The git reading
itself is one function with its own test.
