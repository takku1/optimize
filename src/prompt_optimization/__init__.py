"""Behavior-constrained prompt and agent-skill optimization toolkit.

The most frequently used analysis primitives are re-exported here. Advanced
evaluation, capability, graph, and search APIs live in their named
subpackages:

- ``prompt_optimization.metrics`` — attractor-basin simulation/evaluation,
  uncertainty quantification, and Pareto/rate-distortion selection.
- ``prompt_optimization.attribution`` — Shapley, interaction, deletion, and
  directional attribution estimators.
- ``prompt_optimization.context`` — token-level attention, sequences and a
  key/value (KV-)cache for order-aware context analysis.
- ``prompt_optimization.evaluators`` — synthetic, rubric, and callable
  evaluator backends.
- ``prompt_optimization.capability`` — capability contracts, maturity,
  provenance, promotion, and verifiable claims.
- ``prompt_optimization.search`` — candidate search and iterative optimization.
- ``prompt_optimization.graph`` — persistent candidate lineage and retrieval.
"""

__version__ = "0.1.0"

from .benchmarks import ExternalBenchmark, load_external_benchmark, to_reference_run_manifest
from .calibration import agreement_report, fleiss_kappa, icc_absolute_agreement

from .metrics import (
    ACTIVATION_CHANGING,
    PRESERVING,
    Attractor,
    MetamorphicCase,
    ObjectiveWeights,
    Prompt,
    TransformationKind,
    apply_hard_gates,
    basin_probabilities,
    basin_probabilities_batch,
    bootstrap_mean_interval,
    conformal_radius,
    delta_hv_converged,
    distortion_at_budget,
    estimate_tokens,
    evaluate,
    final_state,
    hierarchical_bootstrap,
    hypervolume,
    make_attractors,
    metamorphic_consistency,
    metamorphic_report,
    optimization_resistance,
    pareto_frontier,
    power_sample_size,
    rate_distortion_frontier,
    robust_summary,
    select_next_experiment,
    tail_metrics,
    total_cost,
    utility_at_budget,
    wasserstein_1d,
)
from .attribution import (
    causal_deletion_effect,
    directional_projection,
    interaction_effect,
    shapley_values,
)
from .context import (
    ContextCache,
    HiddenRepresentation,
    RepresentationEncoder,
    cosine_similarity,
    TokenSequence,
    causal_mask,
    contextual_vector,
    default_sequence,
    evaluate_sequence,
    multi_head_attention,
    scaled_dot_product_attention,
    sinusoidal_positional_encoding,
    tokenize,
    representation_drift,
)
from .contracts import (
    CounterfactualCase,
    DefectType,
    HardInvariant,
    IntentContract,
    Scenario,
    ScenarioResult,
    ablation_deltas,
    compare_contract_results,
    counterfactual_detection_rate,
    load_comparison_input,
    load_contract,
    load_scenarios,
    stratified_utility_report,
)

__all__ = [
    "ACTIVATION_CHANGING",
    "ExternalBenchmark",
    "agreement_report",
    "PRESERVING",
    "Attractor",
    "CounterfactualCase",
    "DefectType",
    "HardInvariant",
    "IntentContract",
    "ContextCache",
    "HiddenRepresentation",
    "RepresentationEncoder",
    "cosine_similarity",
    "MetamorphicCase",
    "ObjectiveWeights",
    "Prompt",
    "ScenarioResult",
    "Scenario",
    "TokenSequence",
    "representation_drift",
    "TransformationKind",
    "ablation_deltas",
    "apply_hard_gates",
    "basin_probabilities",
    "basin_probabilities_batch",
    "bootstrap_mean_interval",
    "causal_deletion_effect",
    "causal_mask",
    "conformal_radius",
    "contextual_vector",
    "compare_contract_results",
    "counterfactual_detection_rate",
    "default_sequence",
    "delta_hv_converged",
    "directional_projection",
    "distortion_at_budget",
    "estimate_tokens",
    "evaluate",
    "evaluate_sequence",
    "final_state",
    "hierarchical_bootstrap",
    "hypervolume",
    "interaction_effect",
    "make_attractors",
    "metamorphic_consistency",
    "metamorphic_report",
    "multi_head_attention",
    "load_comparison_input",
    "load_contract",
    "load_external_benchmark",
    "to_reference_run_manifest",
    "fleiss_kappa",
    "icc_absolute_agreement",
    "load_scenarios",
    "optimization_resistance",
    "pareto_frontier",
    "power_sample_size",
    "rate_distortion_frontier",
    "robust_summary",
    "scaled_dot_product_attention",
    "select_next_experiment",
    "shapley_values",
    "sinusoidal_positional_encoding",
    "stratified_utility_report",
    "tail_metrics",
    "tokenize",
    "total_cost",
    "utility_at_budget",
    "wasserstein_1d",
]
from .empirical import (
    EmpiricalRun,
    EmpiricalRunConfig,
    EvaluationUnit,
    JudgeRequest,
    JudgeResult,
    SubjectRequest,
    run_empirical,
)

__all__ += [
    "EmpiricalRun",
    "EmpiricalRunConfig",
    "EvaluationUnit",
    "JudgeRequest",
    "JudgeResult",
    "SubjectRequest",
    "run_empirical",
    "ValidationResult",
    "aggregate_validations",
    "validate_response",
    "evaluate_candidate",
    "evaluate_neighborhood",
]

from .validators import ValidationResult, aggregate_validations, evaluate_candidate, evaluate_neighborhood, validate_response
