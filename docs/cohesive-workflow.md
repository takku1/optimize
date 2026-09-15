# Cohesive optimization workflow

This is the load-bearing workflow for the project. Synthetic search,
representation signals, external benchmark inputs, and optional model
execution are supporting parts, not alternate sources of truth.

```text
freeze contract + benchmark revision
  -> assign development / calibration / selection / sealed-test splits
  -> generate bounded candidates from a small parent frontier
  -> execute the target system with immutable unit IDs
  -> run mechanical checks first
  -> aggregate repeated rollouts and uncertainty
  -> keep only hard-gate-passing Pareto candidates
  -> stop on budget, patience, or convergence
  -> unseal the test split once
  -> compare baseline and negative controls
  -> write report, lineage, provenance, and promotion verdict
```

## Ownership boundaries

| Layer | Authoritative responsibility | Must not do |
|---|---|---|
| Contract | Define intent, required behavior, forbidden behavior, and hard floors | Infer success from similarity or prose quality |
| Scenario registry | Version tasks, IDs, split membership, and contamination status | Mix exposed development tasks into sealed test |
| Executor | Run the target system and preserve raw transcripts | Judge its own output or rewrite evidence |
| Mechanical validator | Recompute executable checks and emit evidence | Treat missing checks as passing |
| Judge/calibrator | Apply a frozen rubric to unresolved qualities | Override hard executable failures silently |
| Aggregator | Compute paired utility, robustness, cost, and uncertainty | Treat nested rollouts or raters as independent |
| Search | Propose bounded candidates and preserve lineage | Promote candidates or use explanations as proof |
| Promotion | Apply floors, non-inferiority, regression, and provenance gates | Validate synthetic-only results |

## External benchmark boundary

`benchmarks/mas-promptbench-v1.json` registers the first external reference at
a pinned upstream revision. It is deliberately a manifest, not a claim that
upstream scores are automatically valid for this project. A future adapter
should translate one upstream cell into the local `RunManifest`, attach task
and scorer hashes, and retain the original evaluator output.

The first useful study is one cell each from mathematics, multi-hop QA, and
repository repair, with identical model settings, budget, and paired baseline.
Report per-cell deltas and the hierarchical aggregate; never publish only the
best cell.

## Evidence ladder

1. Synthetic tests establish implementation invariants.
2. External manifests establish reproducible task identity.
3. Calibration establishes rater/judge reliability and rubric coverage.
4. Paired held-out runs establish task-conditional behavioral differences.
5. Independent replication establishes transport beyond the author's setup.
6. Outcome studies establish whether optimization improves real decisions or work.

Adding code or documentation advances infrastructure, not empirical evidence.
The benchmark card and promotion logic must continue to report those levels
separately.

## Research basis

The bounded reflective/evolutionary direction is consistent with OPRO and
Promptbreeder, but their reported gains do not validate this implementation.
MAS-PromptBench is useful because it separates optimizer, topology, dataset,
and team-size conditions while freezing evaluation IDs. The measurement design
follows the AERA/APA/NCME validity framework: score interpretation and use need
evidence, not just a coherent rubric. Numeric rater agreement must declare the
exact ICC model, type, and agreement definition; categorical judgments need an
appropriate multi-rater statistic and explicit limitations.

Primary references: [OPRO](https://arxiv.org/abs/2309.03409),
[Promptbreeder](https://arxiv.org/abs/2309.16797),
[MAS-PromptBench](https://arxiv.org/abs/2606.23664),
[AERA/APA/NCME Standards](https://www.apa.org/science/programs/testing/standards?clearcache=true),
[Koo and Li on ICC selection](https://pubmed.ncbi.nlm.nih.gov/27330520/), and
[Hallgren on inter-rater reliability](https://pmc.ncbi.nlm.nih.gov/articles/PMC3402032/).
