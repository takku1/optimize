# STATUS

**Current Phase:** Working research scaffold with a drafted preprint (`.specimen/paper/`). Not "notes-only" - `src/prompt_optimization` is a real, tested package (74 tests) with a stdlib CLI, intent contracts, paired behavioral comparison, and preserved CLI runs against real skill files. What it is *not* yet: a system that has optimized any real-world prompt against a real model.

**Active Focus:** Move beyond token-level proposal metrics toward intent-preserving transformation. The real-evaluator seam, `attribute` command, and score-ranked scan are implemented; the new `IntentContract`, paired `compare` command, and reviewed Claude skill scenario seeds establish the behavioral evaluation layer. Real model judgments, held-out runs, and flow-changing rewrite experiments remain future work.

**Architecture Summary:** Three subpackages: `metrics` (synthetic attractor-basin simulation, uncertainty, Pareto/rate-distortion selection, hard gates), `attribution` (Shapley/interaction/directional estimators), `context` (attention-pooled token sequences + KV-cache). `evaluators` is the real-model seam: an `Evaluator` ABC with a `synthetic` flag, a default `SyntheticBasinEvaluator`, plus `RubricEvaluator` and `CallableEvaluator`. `contracts` adds versioned intent specifications, held-out scenarios, paired result validation, hard-invariant gates, and bootstrap non-inferiority comparison.

**Key Decisions:**
- **The real-evaluator seam ships without a built-in network-calling adapter.** Rubric and callable backends let a real judgment enter without this project making API calls on its own initiative.
- **`scan`'s human-readable table sorts by `score`, not `synAlign`.** Embedding similarity is diagnostic, not behavioral performance.
- **Intent is represented as a contract, not a section order.** `IntentContract` records activation, outcomes, hard invariants, state, side effects, outputs, validation, and recovery. `compare` consumes paired scenario observations and applies invariant gates plus a confidence-aware non-inferiority check; it does not make model calls itself.
- **Synthetic scores remain proposal-only.** Real held-out evaluation is required before any improvement claim.
- **Pre-registration and a real multi-model study remain future work.** They require task-population, evaluator, and budget decisions.

**Deprecated/Legacy:** None yet.

**Last Updated:** 2026-08-28
