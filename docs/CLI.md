# CLI reference

The installed command is `prompt-opt`; `python -m prompt_optimization` is
equivalent. Run `prompt-opt COMMAND --help` for every option.

| Command | Purpose | Evidence level |
|---|---|---|
| `scan` | Score text files with a selected evaluator | Backend-dependent |
| `plan` | Build a Pareto/rate-distortion view and recommend an experiment | Backend-dependent |
| `attribute` | Estimate component contributions with Shapley attribution | Backend-dependent |
| `compare` | Compare paired scenario results against an intent contract | Uses supplied results |
| `search` | Run branching candidate search and optionally persist lineage | Synthetic by default |
| `report` | Assemble coverage, activation, maturity, and provenance data | Uses supplied data |
| `promote` | Classify a candidate as rejected, candidate, or validated | Never validates synthetic-only evidence |
| `graph` | Inspect a persistent evolution graph | Descriptive |
| `verify` | Recompute registered document claims | Determined by claim sources |
| `run` | Drive a declarative `run.json` manifest through `checks` -> `assemble` -> `seed` | Uses supplied transcripts/judge scores |
| `optimize` | Run iterative proposal generation with programmatic scoring | Scorer-dependent |

## Common examples

```bash
prompt-opt scan --json src
prompt-opt plan docs --gate distortion=0.25
prompt-opt attribute README.md --unit paragraph
prompt-opt search SKILL.md --baseline full_bcso --run-dir runs/example
prompt-opt compare --contract contract.json --results results.json --json
prompt-opt promote --baseline old.md --candidate new.md --contract contract.json --results results.json
prompt-opt graph evolution-graph stats
prompt-opt verify output/example/verify_claims.py
prompt-opt run --config runs/example/run.json
prompt-opt run --config runs/example/run.json --stage checks --json
```

`run` replaces the one-off `assemble_results.py`/`deterministic_checks.py`/
`seed_graph.py` scripts used by the first empirical pilot with a single
declarative, path-portable manifest (`prompt_optimization.runs.manifest`). Its
`checks` stage declares deterministic rules per scenario (`word_count`,
`mentions_any`, `count_word`, `count_labels`, and a constrained `derived`
boolean expression over previously computed fields — see
`prompt_optimization.runs.checks` for the rule language); its `assemble` stage
supports any number of rollouts per version/scenario unit, discovered from the
blind map rather than assumed. With K>1 rollouts, an invariant is recorded as
passed for a unit only if every rollout passed it (a hard invariant that holds
"most of the time" hasn't been demonstrated to hold), and the assembled result
additionally reports `utility_hierarchical_interval` — a nested bootstrap over
paired per-rollout utility deltas, which does not understate uncertainty by
treating rollouts nested under a handful of scenarios as independent
observations the way a flat scenario-level bootstrap does.

Iterative optimization accepts either a direct scoring callback or a scenario
executor:

```bash
prompt-opt optimize seed.md --proposal-fn adapter:propose --score-fn adapter:score --output-dir run
prompt-opt optimize seed.md --executor-fn adapter:execute --scenario-file scenarios.json --output-dir run
```

Callback contracts:

- proposal: `propose(current_text, feedback, turn) -> str`
- score: `score(text) -> mapping` containing at least `utility` and `tokens`
- executor: `execute(skill_text, scenario, rollout) -> str`

## Evaluator backends

`scan`, `plan`, `attribute`, `search`, and `promote` share three backends:

- `synthetic` is deterministic research scaffolding. It is useful for testing
  invariants and search control flow, not for behavioral claims.
- `rubric` reads precomputed judgments from `--rubric-file`.
- `callable` invokes `MODULE:FUNC` supplied through `--evaluator-fn`.

The package intentionally ships without a vendor-specific network adapter.
External model or human judgments enter through the rubric/callable seams.
