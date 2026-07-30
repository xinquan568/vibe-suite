# vibe-32 worksheet — hand-derived expectations for `/vibe-suite:vocab` + suite registry

Authored BEFORE any shipped file (T0 of the frozen plan). Citations: frozen plan D1–D7,
F4.6, skills/vocabulary/SKILL.md, the proposal's resolved decisions (plan-i1-r1.md:672,
disposition row :469).

## The sweep (re-run at authoring time, case-insensitive, engine semantics)

`grep -riE '\b<term>\b' commands agents` @ worktree HEAD:
implement 0 · utilize 0 · grade 0 · validate 1 · inspect 1 · search 2 · analyze 2 ·
lint 3 · find 5 · list 11.
No drift from the frozen plan's table → the seed set stands (T0 demotion rule unused).

## The registry (complete content, fixed here; sidecar = authoritative tables EXACTLY)

- Scope `operative` = commands/** + agents/**.
- Verbs (canonical; bright-line columns from the skill's table): score, check, test,
  scan, ls, audit, review, delegate. ONLY `delegate` carries a deprecated entry:
  `implement` — warrant: owner-accepted merge rename (plan-i1-r1.md:672; row :469);
  sweep-clean (0 hits).
- nouns.artifact_class (canonical-only): command, agent, skill, rule, hook, manifest,
  frontmatter, artifact. nouns.output_class (canonical-only): finding, violation,
  penalty, score, snapshot, inventory, report, spec. role_nouns: scorer→score,
  checker→check, tester→test, scanner→ls. Evidence paths per row live in the SKILL.md
  tables (D3).
- cross_scope_homonyms {verbs: []}; deferred/rejected [].
- Candidates note (NON-authoritative): lint(3), validate(1), analyze(2), find(5),
  search(2), list(11) — blocked by their sweep counts; listing any authoritatively
  requires migrating those occurrences first.

## Acceptance expectations

- `registry_terms(skills/vocabulary/registry.yaml)` parses; the term table is exactly
  [("implement", "delegate", [commands/**, agents/**])].
- A REAL check_engine run over the repo root (default config → the new .vibe-suite.md)
  exits 0 or 1 with ZERO `r51-drift` issues (other classes are other items' concerns).
- `.vibe-suite.md` loads via config.load_with_warnings with zero warnings; R51 enabled;
  vocabulary_skill contained.
- The five SKILL.md statement edits (D1): each old sentence gone, each new present.

## Fixtures

- `drift/` — six artifacts where "report" and "dossier" compete (three files each) —
  the seeded-synonym clustering case (runtime = the drift agent's judgment lane; the
  fixture and the contract rows are rung-0/1's).
- `init-existing/skills/demo/vocabulary/SKILL.md` — an EXISTING vocabulary skill: the
  overwrite-refusal case (init must refuse naming this path).
- `extract/` — the extractor's own fixture: five artifact classes with KNOWN counts:
  commands/go.md ("wombat wombat quokka"), commands/shared/part.md ("wombat"),
  agents/helper.md ("quokka"), skills/one/SKILL.md ("wombat"), CLAUDE.md ("quokka
  numbat"). Expected (min-count 1, lowercased, sorted -count,term): wombat 4 files 3 ·
  quokka 3 files 3 · numbat 1 files 1 (plus structural words — the test asserts THESE
  three rows' counts and file lists exactly, and --min-count 4 excludes all three).
