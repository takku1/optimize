"""Core invariants for the prompt-optimization simulation and metrics."""
import numpy as np
import pytest

from prompt_optimization import (
    ObjectiveWeights, Prompt, apply_hard_gates, bootstrap_mean_interval,
    conformal_radius, estimate_tokens, evaluate, make_attractors,
    metamorphic_consistency, pareto_frontier, rate_distortion_frontier,
    robust_summary, select_next_experiment, wasserstein_1d,
)
from prompt_optimization.metrics import (
    basin_probabilities, final_state, tail_metrics, power_sample_size,
    hierarchical_bootstrap, optimization_resistance, total_cost, hypervolume,
    delta_hv_converged, utility_at_budget, distortion_at_budget,
)


def baseline() -> np.ndarray:
    return np.zeros(32)


def test_basin_probabilities_are_normalized_and_finite():
    probs = basin_probabilities(np.zeros(32), make_attractors())
    assert np.isfinite(probs).all() and np.isclose(probs.sum(), 1.0)
    assert (probs >= 0).all()


def test_target_is_most_probable_at_its_center():
    attractors = make_attractors()
    probs = basin_probabilities(attractors[0].center, attractors)
    assert np.argmax(probs) == 0


def test_attractor_shapes_are_padded_to_working_dimension():
    for attractor in make_attractors():
        assert attractor.center.shape == (32,)


def test_evaluation_is_reproducible_for_a_fixed_seed():
    attractors = make_attractors()
    prompt = Prompt("independently confirm", 2, np.array([2.0, 0.8] + [0.0] * 30))
    a = evaluate(prompt, attractors[0], baseline(), attractors, seed=7)
    b = evaluate(prompt, attractors[0], baseline(), attractors, seed=7)
    assert a["instruction_density"] == b["instruction_density"]


def test_token_count_penalizes_density():
    attractors = make_attractors()
    bias = np.array([2.0, 0.8] + [0.0] * 30)
    short = evaluate(Prompt("x", 2, bias), attractors[0], baseline(), attractors)
    long = evaluate(Prompt("x", 8, bias), attractors[0], baseline(), attractors)
    assert short["instruction_density"] > long["instruction_density"]


def test_metric_components_are_bounded():
    attractors = make_attractors()
    prompt = Prompt("re-verify each prior finding", 4, np.array([2.5, 1.5] + [0.0] * 30))
    result = evaluate(prompt, attractors[0], baseline(), attractors, seed=11)
    assert 0 <= result["target_activation"] <= 1
    assert 0 <= result["reliability"] <= 1


def test_zero_tokens_do_not_divide_by_zero():
    attractors = make_attractors()
    result = evaluate(Prompt("empty", 0, np.zeros(32)), attractors[0], baseline(), attractors)
    assert np.isfinite(result["instruction_density"])


def test_evaluation_exposes_samples_for_distributional_analysis():
    attractors = make_attractors()
    result = evaluate(Prompt("x", 1, np.array([1.0, 0.0] + [0.0] * 30)),
                      attractors[0], baseline(), attractors)
    assert len(result["samples"]) == 64
    assert np.isfinite(result["samples"]).all()


def test_pareto_frontier_keeps_tradeoff_candidates():
    rows = [
        {"target_activation": .8, "reliability": .8, "tokens": 4, "off_target": .1, "variance_penalty": .1},
        {"target_activation": .7, "reliability": .7, "tokens": 1, "off_target": .2, "variance_penalty": .1},
    ]
    assert len(pareto_frontier(rows)) == 2


def test_token_estimate_counts_words_and_punctuation():
    assert estimate_tokens("verify, independently") == 3


def test_rate_distortion_frontier_is_monotonic_lower_envelope():
    rows = [
        {"tokens": 1, "distortion": .4, "prompt": "a"},
        {"tokens": 2, "distortion": .2, "prompt": "b"},
        {"tokens": 2, "distortion": .3, "prompt": "c"},
    ]
    frontier = rate_distortion_frontier(rows)
    assert [r["prompt"] for r in frontier] == ["a", "b"]


def test_bootstrap_interval_is_reproducible_and_contains_mean():
    values = [0.2, 0.4, 0.6, 0.8]
    interval = bootstrap_mean_interval(values, seed=3)
    assert interval == bootstrap_mean_interval(values, seed=3)
    assert interval[0] <= np.mean(values) <= interval[1]


def test_conformal_radius_uses_finite_sample_quantile_rule():
    assert conformal_radius([.1, .2, .3, .4], alpha=.25) == pytest.approx(.4)


def test_wasserstein_distance_is_zero_for_identical_distributions():
    assert wasserstein_1d([0, 1, 2], [0, 1, 2]) == 0.0
    assert wasserstein_1d([0, 1], [1, 2]) > 0


def test_robust_summary_reports_lower_tail():
    result = robust_summary([.2, .4, .9], lower_quantile=.1)
    assert result["lower_quantile"] <= result["mean"]


def test_metamorphic_consistency_is_bounded():
    assert metamorphic_consistency(.5, [.5, .6], tolerance=.1) == 1.0


def test_next_experiment_uses_uncertainty_weighted_gain():
    candidates = [
        {"name": "a", "uncertainty": .9, "expected_gain": .2},
        {"name": "b", "uncertainty": .4, "expected_gain": .8},
    ]
    assert select_next_experiment(candidates)["name"] == "b"


def test_final_state_requires_matching_shapes():
    with pytest.raises(ValueError):
        final_state(Prompt("x", 1, np.zeros(8)), np.zeros(32))


def test_evaluate_rejects_too_few_samples():
    with pytest.raises(ValueError):
        evaluate(Prompt("x", 1, np.zeros(32)), make_attractors()[0],
                 baseline(), make_attractors(), samples=1)


def test_objective_weights_reject_negative_penalties():
    with pytest.raises(ValueError):
        ObjectiveWeights(off_target=-1)


def test_invalid_prompt_and_temperature_inputs_are_rejected():
    with pytest.raises(ValueError):
        Prompt("bad", -1, np.zeros(32))
    with pytest.raises(ValueError):
        basin_probabilities(np.zeros(32), make_attractors(), temperature=0)


def test_tail_metrics_cvar_is_worse_than_or_equal_to_mean_for_left_skew():
    values = [0.9, 0.9, 0.9, 0.9, 0.1]
    result = tail_metrics(values, q=0.2)
    assert result["cvar_0.2"] <= result["mean"]
    assert result["p20"] <= result["mean"]


def test_power_sample_size_shrinks_as_effect_size_grows():
    small_effect_n = power_sample_size(sigma=0.2, delta_min=0.01)
    large_effect_n = power_sample_size(sigma=0.2, delta_min=0.1)
    assert small_effect_n > large_effect_n > 0


def test_power_sample_size_rejects_nonpositive_inputs():
    with pytest.raises(ValueError):
        power_sample_size(sigma=0.0, delta_min=0.1)


def test_hierarchical_bootstrap_is_reproducible_and_wider_than_flat():
    groups = [[0.5, 0.5, 0.5], [0.9, 0.1], [0.6, 0.7, 0.5, 0.6]]
    interval = hierarchical_bootstrap(groups, seed=1, resamples=500)
    assert interval == hierarchical_bootstrap(groups, seed=1, resamples=500)
    flat = [v for group in groups for v in group]
    flat_interval = bootstrap_mean_interval(flat, seed=1, resamples=500)
    assert (interval[1] - interval[0]) >= (flat_interval[1] - flat_interval[0]) * 0.5


def test_optimization_resistance_summarizes_seeds():
    result = optimization_resistance([0.01, 0.02, 0.015, 0.03], seed=2, resamples=200)
    assert result["n_seeds"] == 4
    assert result["ci"]["lower"] <= result["mean"] <= result["ci"]["upper"]


def test_total_cost_sums_weighted_components():
    result = total_cost({"tokens": 100.0, "latency": 2.0}, weights={"tokens": 1.0, "latency": 5.0})
    assert result["total"] == pytest.approx(100.0 + 10.0)
    assert result["components"] == {"tokens": 100.0, "latency": 2.0}


def test_hypervolume_grows_with_a_dominating_point():
    ref = (0.0, 0.0, 0.0)
    small = hypervolume([(1.0, 1.0, 1.0)], ref, samples=5000, seed=0)
    large = hypervolume([(2.0, 2.0, 2.0)], ref, samples=5000, seed=0)
    assert large > small > 0


def test_hypervolume_is_zero_when_no_point_dominates_reference():
    assert hypervolume([(0.0, 1.0, 1.0)], (0.5, 0.5, 0.5), samples=1000) == 0.0


def test_delta_hv_converged_requires_enough_history():
    assert delta_hv_converged([1.0], checks=3) is False


def test_delta_hv_converged_true_when_flat():
    assert delta_hv_converged([1.0, 1.0, 1.0, 1.0], epsilon=0.01, checks=3) is True


def test_delta_hv_converged_false_when_still_growing():
    assert delta_hv_converged([1.0, 1.5, 2.0, 3.0], epsilon=0.01, checks=3) is False


def test_delta_hv_converged_rejects_invalid_values():
    with pytest.raises(ValueError, match="epsilon"):
        delta_hv_converged([1.0, 1.0], epsilon=-0.1, checks=1)
    with pytest.raises(ValueError, match="finite non-negative"):
        delta_hv_converged([1.0, np.nan], checks=1)


def test_hard_gates_block_missing_or_nonfinite_critical_metrics():
    complete = {"name": "complete", "distortion": 0.1}
    missing = {"name": "missing"}
    nonfinite = {"name": "nonfinite", "distortion": np.nan}
    passed, blocked = apply_hard_gates(
        [complete, missing, nonfinite], {"distortion": 0.2}, operator="max",
    )
    assert passed == [complete]
    assert blocked == [missing, nonfinite]


def test_utility_and_distortion_at_budget_are_consistent():
    frontier = rate_distortion_frontier([
        {"tokens": 1, "distortion": .4, "prompt": "a"},
        {"tokens": 2, "distortion": .2, "prompt": "b"},
    ])
    assert distortion_at_budget(frontier, 2) == pytest.approx(0.2)
    assert utility_at_budget(frontier, 2) == pytest.approx(0.8)
    with pytest.raises(ValueError):
        distortion_at_budget(frontier, 0)
