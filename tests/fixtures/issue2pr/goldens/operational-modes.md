# Operational modes

The pipeline's nine steps describe **one run**. This reference describes the modes that start, resume,
repeat and enumerate runs: `chain`, `resume`, `iterate` and `list`.

It exists because the core once named these modes in three documents and defined them in none — a
test docstring, the driver contract, and the `argument-hint` a user sees. Naming a capability is not
shipping it.

Each mode answers the same eight questions. A mode that cannot answer all eight is not defined.

<!-- run-status-enum -->
```json
{
  "non_terminal": ["in_progress", "quota_paused"],
  "terminal": ["completed", "stopped_by_max_rounds", "stopped_by_review",
               "stopped_by_analysis_invalid", "failed"]
}
```

<!-- loop-exit-to-status -->
```json
{
  "EXIT_OK": "completed",
  "EXIT_MAX_ROUNDS": "stopped_by_max_rounds",
  "EXIT_CYCLE": "stopped_by_review",
  "EXIT_TOKEN_BUDGET": "quota_paused"
}
```

**The partition is the point.** `resume` continues a run whose status is **non-terminal**; `iterate`
starts a new round on one whose status is **terminal**. Before this block existed, both preconditions
named values the core never declared — `status` appeared exactly once in `SKILL.md`, as an example
value inside the state schema. A precondition that names nothing constrains nothing.

**These lists are normative and exhaustive**, not a description of what past runs happened to write.
`stopped_by_*` is not a wildcard: a new stop reason is a change to this block, not a pattern that
quietly matches. A run carrying a status outside the enum is malformed, and the pipeline says so
rather than guessing which half it belongs to.

**`EXIT_MAX_ROUNDS` maps to `stopped_by_max_rounds`, which is terminal — therefore `iterate`-eligible.**
That closure is what makes the loop's own documented remedy reachable: the core calls exhausting the
cap "a terminal state, not a failure", and a terminal state is exactly what `iterate` requires. Without
the mapping, the commonest reason a round needs iterating had no status that `iterate` would accept.

---

## `chain`

<!-- chain-operations -->
```json
{
  "link_statuses": [
    "pending",
    "running",
    "waiting_merge",
    "iterating",
    "merged",
    "closed_unmerged",
    "failed",
    "skipped"
  ],
  "chain_statuses": {
    "non_terminal": [
      "running",
      "waiting_merge",
      "iterating",
      "paused"
    ],
    "terminal": [
      "complete",
      "stopped"
    ]
  },
  "link_edges": {
    "pending": [
      "running"
    ],
    "running": [
      "waiting_merge",
      "failed",
      "skipped"
    ],
    "waiting_merge": [
      "merged",
      "iterating",
      "closed_unmerged",
      "skipped"
    ],
    "iterating": [
      "waiting_merge",
      "failed"
    ]
  },
  "pause_on_link_terminal_not": "merged",
  "persist_after_every_transition": [
    "chain.json",
    "timeline.md"
  ],
  "events": {
    "link-start": {
      "edge": {
        "from": "pending",
        "to": "running"
      }
    },
    "link-run-outcome": {
      "inputs": {
        "status": [
          "pr_opened",
          "failed"
        ]
      },
      "effects": {
        "pr_opened": {
          "edge": {
            "from": "running",
            "to": "waiting_merge"
          }
        },
        "failed": {
          "edge": {
            "from": "running",
            "to": "failed"
          }
        }
      }
    },
    "skip": {
      "from_any_of": [
        "running",
        "waiting_merge"
      ],
      "to": "skipped",
      "then": "advance",
      "pause_exempt": true
    },
    "babysit-finish": {
      "inputs": {
        "outcome": [
          "pushed",
          "failed"
        ]
      },
      "effects": {
        "pushed": {
          "edge": {
            "from": "iterating",
            "to": "waiting_merge"
          }
        },
        "failed": {
          "edge": {
            "from": "iterating",
            "to": "failed"
          }
        }
      }
    },
    "advance": {
      "next_link": {
        "from": "pending",
        "to": "running"
      },
      "on_last_link": {
        "chain": "complete"
      }
    }
  },
  "babysit_round_semantics": "the 1-based ordinal of the babysit round about to run; it runs while round <= cap",
  "on_link_terminal_chain_status": "paused"
}
```

- **Invocation:** `/vibe-suite:issue2pr chain <issue> <issue> …` (2–10, executed in the given order), or
  `chain --milestone <title>`, or `chain --label <label>`; plus `[--auto-merge] [--stall-hours H]
  [--max-babysit-rounds N]` and the run flags. Management: `chain resume|status|stop|skip`.
- **Reads:** `runs/_chains/<chain-id>/chain.json` — the durable source of truth — plus live PR state
  via the watcher. The issue list is **frozen at chain start**; issues milestoned or labelled later
  are not picked up.
- **Writes:** `chain.json` and `timeline.md` after **every** transition, because the session may die
  at any point and `chain resume` trusts only that file plus live PR state.
- **Precondition:** no other chain is non-terminal; no `runs/<source-id>-*/` exists for any listed
  issue (chains take no `--force` — drop the issue or archive the run).
- **Refuses:** `--scenario` (auto-detected per link), `--base-branch` (chains stack on the base
  branch by definition), `--force`, `--from-manifest`.
- **Statuses read:** link ∈ `pending | running | waiting_merge | iterating | merged |
  closed_unmerged | failed | skipped`; chain ∈ `running | waiting_merge | iterating | paused |
  complete | stopped`, of which `complete` and `stopped` are terminal.
- **Transitions written:** `pending → running → waiting_merge → {merged | iterating |
  closed_unmerged | failed | skipped}`. The chain **pauses on any link terminal that is not
  `merged`** and never auto-advances past it.
- **Round bounds:** a babysit round is an `iterate` round, capped per link by `max_babysit_rounds`
  (default 3, range 1–5); each such round is separately subject to the run's own review-iteration cap.

### Watcher exit → chain action

The watcher reports; the core decides. `scripts/watch_pr.py` produces exactly these codes, and this
map is what turns each into an action. Exit 3 carries one JSON line on stdout —
`{"at", "author", "author_association", "exit": 3}` — and the chain passes that association to the
driver: only `OWNER`, `MEMBER` or `COLLABORATOR` activity may run a babysit round; anyone else is
notified about, never acted upon, and auto-merge is never re-armed on their account (vibe-188 /
grill H2 part b — on a public repository with `--auto-merge`, anyone who can comment must not be
able to steer an edit that CI then merges).

<!-- watcher-exit-actions -->
```json
{
  "0": {
    "guidance": "fetch the base branch, verify the merge commit is an ancestor of it, surface any post-cursor activity without acting on it, mark the link merged, then start the next link or complete the chain",
    "effect": {
      "requires": [
        "merge_commit",
        "ancestor_verified"
      ],
      "edge": {
        "from": "waiting_merge",
        "to": "merged"
      },
      "then": "advance"
    },
    "result_events": []
  },
  "1": {
    "guidance": "this code and any unmapped exit: re-check PR state by hand; if nothing explains it, pause and notify",
    "effect": {
      "chain": "paused",
      "report": "manual-recheck",
      "catch_all_for_unmapped": true
    },
    "result_events": []
  },
  "2": {
    "guidance": "mark the link closed_unmerged, then pause and notify",
    "effect": {
      "edge": {
        "from": "waiting_merge",
        "to": "closed_unmerged"
      }
    },
    "result_events": []
  },
  "3": {
    "guidance": "classify the activity AND its author: actionable under cap from an OWNER, MEMBER or COLLABORATOR disarms auto-merge and runs a babysit round before re-arming and advancing the cursor; activity from any other author association is notified about only — no babysit round, auto-merge never re-armed on its account, the decision recorded in the timeline, the cursor advanced; a question notifies only; status-noise advances the cursor; beyond the cap's rounds, pause",
    "effect": {
      "requires": [
        "classification",
        "babysit_round",
        "babysit_cap"
      ],
      "author_gate": {
        "applies_to": "actionable",
        "babysit_allowed": [
          "OWNER",
          "MEMBER",
          "COLLABORATOR"
        ],
        "otherwise": {
          "report": "notify-only",
          "link_flag": {
            "auto_merge_rearm": false
          },
          "timeline_note": "non-collaborator activity: notified only; no babysit round; auto-merge NOT re-armed",
          "cursor": "advance",
          "result_events": []
        }
      },
      "by_classification": {
        "question": {
          "report": "notify",
          "writes": []
        },
        "status-noise": {
          "cursor": "advance"
        },
        "actionable_within_cap": {
          "edge": {
            "from": "waiting_merge",
            "to": "iterating"
          },
          "report": "babysit-start"
        },
        "actionable_beyond_cap": {
          "chain": "paused"
        }
      }
    },
    "result_events": [
      "babysit-finish"
    ]
  },
  "4": {
    "guidance": "run a babysit round whose feedback is the failing check log — a check has no author, so the author gate does not apply — with the same disarm, re-arm, cap and cursor handling as exit 3",
    "effect": {
      "as": "3",
      "author_gate": null,
      "timeline_note": "failing-check feedback"
    },
    "result_events": [
      "babysit-finish"
    ]
  },
  "5": {
    "guidance": "notify the heartbeat and re-arm the watcher unchanged — a timeout is not a pause",
    "effect": {
      "report": "re-arm",
      "writes": []
    },
    "result_events": []
  },
  "6": {
    "guidance": "pause and notify; ten consecutive state probes failed, so credentials or the network are the likely cause",
    "effect": {
      "chain": "paused"
    },
    "result_events": []
  },
  "7": {
    "guidance": "squash-merge the PR directly, then handle it as exit 0",
    "effect": {
      "pre_report": "squash-merge",
      "as": "0"
    },
    "result_events": []
  }
}
```

**Exit 5 is a timeout, not a state.** The watcher evaluates it before probing, so the PR's state at
that moment is unobserved. Do not read it as "the PR is still open" — nothing asked.

---

## `resume`

<!-- resume-operations -->
```json
{
  "precondition_partition": "non_terminal",
  "redirect_nonmatching_to": "iterate",
  "writes": [],
  "sequences": {
    "none": [
      1,
      4,
      7
    ],
    "single": [
      1,
      2,
      3,
      4,
      5,
      6,
      7,
      8,
      9
    ],
    "full": [
      1,
      2,
      3,
      4,
      5,
      6,
      7,
      8,
      9
    ]
  }
}
```

- **Invocation:** `/vibe-suite:issue2pr resume <run-id>`.
- **Reads:** `runs/<run-id>/state.json` (an absent file is an error, not an empty run); the effective
  cap, review mode and reviewer backend resolved from their base values plus any recorded overrides
  for `current_round`. The cap's resolution is the core's — see
  [`SKILL.md` § Round bounds](../SKILL.md#round-bounds).
- **Writes:** nothing new — it continues the round already in progress and leaves the status alone.
- **Precondition:** status is `in_progress` or `quota_paused`. A `completed` run is redirected to
  `iterate`; so is a terminal failure. The worktree must exist or be re-materialisable from the
  branch; if branch and worktree are both gone, refuse rather than invent a checkout.
- **Refuses:** `--max-review-rounds` and `--review-mode`. **Both are frozen for the round in
  progress**, because changing them mid-round rewrites the rules a partially-executed loop already
  ran under. To change either, let the round terminate and `iterate`.
- **Statuses read:** `in_progress`, `quota_paused` to continue; `completed` and the terminal failures
  to redirect.
- **Transitions written:** **none.** Resuming is not a state change.
- **Round bounds:** the cap is inherited and frozen; resume never raises it.

A step whose `prompt.md` exists but whose `result.md` does not is **re-run from scratch**. A partial
artifact is not a checkpoint.

---

## `iterate`

<!-- iterate-operations -->
```json
{
  "precondition_partition": "terminal",
  "redirect_nonmatching_to": "resume",
  "creates": "round-<N+1>/",
  "override_records": {
    "review_mode": "review_mode_overrides",
    "reviewer_backend": "reviewer_backend_overrides",
    "max_review_rounds": "max_review_rounds_overrides"
  },
  "override_key_type": "string round number",
  "never_writes": [
    "00-meta.json"
  ],
  "transition": {
    "to": "in_progress",
    "scope": "new-round"
  },
  "flag_rules": {
    "max_review_rounds": {
      "ignored_with_notice_under_modes": [
        "none",
        "single"
      ]
    }
  }
}
```

- **Invocation:** `/vibe-suite:issue2pr iterate <run-id>`, accepting a full run-id or a bare source-id, which
  resolves to the most recent run for that source. Takes `[--review-mode] [--reviewer-backend]
  [--max-review-rounds]`.
- **Reads:** the prior round's frozen artifacts as **read-only** inputs, plus a freshly fetched
  source snapshot and — when the run has a PR — that PR's new comments, reviews and inline comments,
  rendered as a delta.
- **Writes:** `round-<N+1>/`; the per-round override records `review_mode_overrides`,
  `reviewer_backend_overrides` and `max_review_rounds_overrides`, each keyed by the new round number.
  The run-start values they override were written **write-once** to `00-meta.json` at run-start and
  **mirrored** into `state.json` so `resume` reads them without consulting two files.
  **`00-meta.json` is never rewritten** — it records how the run started, and a run that could edit
  its own origin story has no origin story. That is the whole reason for two locations rather than
  one.
- **Precondition:** status is **terminal**. A run still in progress is redirected to `resume`.
- **Refuses:** nothing beyond the run flags it accepts.
- **Statuses read:** the terminal set — `completed`, `stopped_by_max_rounds`,
  `stopped_by_review`, `stopped_by_analysis_invalid`, `failed`. `stopped_by_max_rounds` is the
  one #69 turns on: a round that exhausted its cap is terminal, so it can be iterated at a
  higher one.
- **Transitions written:** terminal → `in_progress`, on the **new** round. The prior round's status
  is history and is not edited.
- **Round bounds:** the cap **inherits**, and an override applies to the new round only, recorded in
  `max_review_rounds_overrides["<N+1>"]`. The domain, its clamp rule and how the effective cap is
  resolved are the core's and are not restated here — see
  [`SKILL.md` § Round bounds](../SKILL.md#round-bounds). Under `--review-mode none` or `single` the
  flag is **ignored with a printed notice**, since those modes run no verify loop for a cap to bound
  and silent acceptance would imply it did something. **This is the documented remedy for a round
  that stopped `EXIT_MAX_ROUNDS`** — iterate at a higher cap rather than re-running into the same
  wall.

The branch and PR are **reused**: no second PR is opened, and later rounds append their changes to
the existing body.

---

## `list`

<!-- list-operations -->
```json
{
  "exclude_prefix": "_",
  "writes": [],
  "order": "last-touched, newest first",
  "columns": [
    "run-id",
    "status",
    "source",
    "current step",
    "effective review mode",
    "round",
    "resume pointer"
  ],
  "column_fields": {
    "run-id": "$dir",
    "status": "status",
    "source": "source_id",
    "current step": "current_step",
    "effective review mode": "$effective_mode",
    "round": "current_round",
    "resume pointer": "$resume_pointer"
  },
  "resume_pointer_unless_status": [
    "completed"
  ]
}
```

- **Invocation:** `/vibe-suite:issue2pr list`.
- **Reads:** every subdirectory of `runs/` **except those whose name begins with an underscore** —
  `_chains`, `_reports`, `_archive` hold chain state, reports and retired runs, not runs. For each,
  `00-meta.json` and `state.json`.
- **Writes:** **none.** `list` is read-only, and nothing it does can change a run.
- **Precondition:** none.
- **Refuses:** nothing.
- **Statuses read:** every member of the enum, unfiltered — a listing that hid failures would be
  worse than no listing.
- **Transitions written:** **none.**
- **Round bounds:** reports the effective review mode and round of each run; it does not resolve caps.

Output is a table sorted by last-touched, newest first, with a `resume` pointer printed for every
run that is not finished.

---

## `manifest`

<!-- manifest-operations -->
```json
{
  "validate_via": "scripts/manifest_entry.py",
  "creates": [
    "run_folder",
    "00-meta.json",
    "state.json"
  ],
  "containment": "run_folder resolves beneath --runs-root",
  "initial_status": "in_progress"
}
```

Programmatic dispatch. An orchestrator supplies every input as JSON instead of a work-item id and the
prompts a normal run would ask; direct human use is not expected. For everyday parallel batching,
`chain` is the mode you want.

- **Invocation:** `/vibe-suite:issue2pr --from-manifest <path>`. Not a subcommand — a flag, because
  it replaces a run's *inputs* rather than selecting a different lifecycle.
- **Reads:** the manifest at `<path>`, validated against
  [`schemas/manifest.schema.json`](../../../schemas/manifest.schema.json); the brief named by
  `subtask.body_path`; the bound profile, for the two checks a schema cannot make.
- **Writes:** the run folder named by `run_folder`, then everything a normal run writes. It
  short-circuits **input gathering only** — the nine steps, their reviews and their bounded loops all
  run unchanged.
- **Precondition:** the document passes the schema **first**, then the profile checks. A manifest
  failing both reports the schema failure, because a profile mismatch on a document that is not a
  manifest is not a useful thing to say.
- **Refuses:** a manifest whose `repos[].id` or `repos[].base_branch` disagrees with the bound
  profile. The schema carries no `const` for either — pinning them would put a project value in a
  project-neutral contract — so the entry path owns both.
- **Statuses read:** none at entry; the run it starts uses the same enum as any other.
- **Transitions written:** the run's own, `in_progress` onward. Manifest mode starts a run; it does
  not add a lifecycle.
- **Round bounds:** the manifest's optional `max_review_iterations` is mapped to the core's
  `max_review_rounds` at the entry path. The manifest keeps the source spelling because renaming a
  specified input property is a change to the contract, not to a port.
