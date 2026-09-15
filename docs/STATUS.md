# Project status

Last updated: 2026-09-03.

## Current state

Prompt Optimization is a working alpha-stage Python package with 287 tests and
eleven CLI commands: `scan`, `plan`, `attribute`, `compare`, `search`, `report`,
`promote`, `graph`, `verify`, `run`, and `optimize`. `run` (declarative
manifest -> `checks` -> `assemble` -> `seed`) existed in code but was
undocumented until 2026-09-03 and had zero test coverage until the same date
(see [CLI reference](CLI.md) and `tests/test_runs.py`) — a real gap between
claimed and demonstrated scope that this update closes.

Implemented foundations include:

- intent and capability contracts, scenario schemas, hard invariants, and
  paired non-inferiority comparison;
- deterministic synthetic, rubric, and callable evaluator seams;
- uncertainty, attribution, activation, metamorphic, Pareto, cost, and
  robustness metrics;
- branching and iterative search with candidate lineage and saturation gates;
- a persistent content-addressed evolution graph;
- taxonomy coverage, maturity, provenance, promotion, and document-claim
  verification;
- a programmatic blinded empirical-run orchestrator;
- bounded focused search defaults and a pinned external benchmark registry;
- calibration agreement analysis, sequential paired ablations, and a guarded
  external benchmark launcher. Current outputs are rehearsal-only until an
  independent panel and configured model endpoint are available.

The default synthetic scoring pipeline remains a proposal and control-flow
harness. It is not evidence of real-model improvement.

## Evidence completed

The repository preserves a real-model pilot for the `architectural-reasoning`
skill under
`output/claude skills/architectural-reasoning/empirical-run-2026-08-29/`.
It evaluated four scenarios for two versions with one rollout per condition,
deterministic checks, blinded rubric-grounded judging, and real promotion
logic. The verdict was `REJECTED`: both versions missed the same invariant
floor, although the candidate improved measured utility and token cost.

A follow-up under
`output/claude skills/architectural-reasoning/negative-control-2026-08-29/`
found that both the damaged-skill and no-skill controls passed the targeted
binary invariants. The result identifies insufficient benchmark resolution;
it does not validate the optimizer. Its registered claims can be recomputed
with:

```bash
prompt-opt verify "output/claude skills/architectural-reasoning/negative-control-2026-08-29/verify_claims.py"
```

## Known limitations

- There is no built-in model-provider adapter or multi-model harness.
- Existing real-model evidence uses a small task suite; a `K=3` rollout rerun
  (`empirical-run-2026-09-03-k3`) was launched 2026-09-03 to get the project's
  first within-version variance estimate — see that run's `REPORT.md` once
  complete, and treat any number cited from it before that file exists as
  provisional.
- Human/judge agreement has not been calibrated on a representative labeled
  set.
- The rule-based search operators are not semantic guarantees.
- The small reference corpus cannot support broad generalization claims.
- Some architecture documents describe target design beyond current CLI
  orchestration; the benchmark card is authoritative for demonstrated scope.
- The repository has no version-control history before 2026-09-03 (git was
  never initialized despite the dated `docs/archive/` convention implying it
  should have been); history before that date cannot be reconstructed.

## Next priorities

1. ~~Replace coarse binary invariants with graded checks where negative
   controls show no skill-attributable margin.~~ Done 2026-09-03: the
   `calibrated-effort` band for scenario 01 is now a pre-registered
   `success_band` (max 300 words, forbidden escalation phrases) in
   `tests/fixtures/scenarios/architectural-reasoning-v1.json`, driven through
   `runs.checks`'s declarative rule engine rather than a runner-script
   constant.
2. ~~Add K>1 rollout support, then repeat with multiple rollouts.~~ Done
   2026-09-03: `contracts.aggregate_rollout_results` and `runs.assemble`
   now discover and aggregate any number of rollouts per unit (all-rollouts-
   must-pass for hard invariants, mean utility, a nested/hierarchical
   bootstrap over paired per-rollout deltas). A K=3 rerun of the four
   original scenarios is the first consumer.
3. ~~Integrate the programmatic empirical orchestrator into a resumable,
   artifact-complete CLI workflow.~~ Already existed as `prompt-opt run`;
   was undocumented and untested until 2026-09-03.
4. Independently calibrate the evaluator protocol (a real gap still, distinct
   from #1-3 above): the K=3 rerun's judges are still this project's own
   rubric/design, not an externally validated one.
5. Expand held-out task families before making cross-skill or cross-model
   claims (unchanged — still 53.3% taxonomy coverage).
6. Split the large CLI module as commands acquire more independent behavior
   (unchanged).
7. Find a user of this tool other than its own author — apply BCSO-Bench to a
   skill/prompt this project didn't write, to test whether the problem and
   the tool generalize past one person's workflow.

The proposed hierarchical semantic trajectory optimizer is documented in
[trajectory-optimization.md](trajectory-optimization.md). Its multi-scale
search foundations exist, but layer-wise target-model diagnostics,
novelty-aware selection, richer graph edges, and learned priors are not yet
implemented or validated.

The [benchmark card](benchmark-card.md) is the concise evidence and
limitations record; the [BCSO-Bench specification](bcso-bench.md)
describes the full measurement design.
