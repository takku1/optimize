"""Tests for Γ capability contracts, taxonomy coverage, maturity, provenance, reference envelopes."""
import json

import numpy as np
import pytest

from prompt_optimization.capability import (
    CURRENT_BENCHMARK_VERSION,
    BenchmarkVersion,
    CapabilityContract,
    MaturityTier,
    ProvenanceRecord,
    classify_maturity,
    content_hash,
    coverage_report,
    family_conditioned_percentile,
    goodness_of_fit,
    knn_distance,
    load_capability_contract,
    mahalanobis_membership,
    select_envelope_estimator,
)
from prompt_optimization.contracts import Scenario


def _contract(**overrides) -> CapabilityContract:
    defaults = dict(
        contract_id="hookify-writing-rules-v1",
        scope="Author and test hookify rules",
        capability_family="tool_orchestration",
        required_behaviors=("emit valid frontmatter",),
        forbidden_behaviors=("invent an event that doesn't exist",),
        success_criteria=("rule triggers on the positive example",),
    )
    defaults.update(overrides)
    return CapabilityContract(**defaults)


def test_capability_contract_round_trips_to_json_shape():
    contract = _contract()
    restored = CapabilityContract.from_dict(json.loads(json.dumps(contract.to_dict())))
    assert restored == contract


def test_capability_contract_rejects_empty_required_fields():
    with pytest.raises(ValueError):
        _contract(scope="")
    with pytest.raises(ValueError):
        _contract(capability_family="")


def test_load_capability_contract_reads_from_disk(tmp_path):
    path = tmp_path / "gamma.json"
    path.write_text(json.dumps(_contract().to_dict()), encoding="utf-8")
    assert load_capability_contract(path) == _contract()


def _scenario(scenario_id: str, tags: tuple[str, ...]) -> Scenario:
    return Scenario(id=scenario_id, request="do the thing", tags=tags)


def test_coverage_report_counts_tagged_cells():
    scenarios = [
        _scenario("s1", ("activation:positive", "difficulty:easy")),
        _scenario("s2", ("activation:negative", "difficulty:hard")),
    ]
    report = coverage_report(scenarios)
    assert report["n_scenarios"] == 2
    assert report["per_axis_counts"]["activation"]["positive"] == 1
    assert report["per_axis_counts"]["activation"]["negative"] == 1
    assert "ambiguous" in report["uncovered_cells"]["activation"]


def test_coverage_report_fraction_is_between_zero_and_one():
    scenarios = [_scenario("s1", ("activation:positive",))]
    report = coverage_report(scenarios)
    assert 0.0 <= report["coverage_fraction"] <= 1.0


def test_coverage_report_requires_scenarios():
    with pytest.raises(ValueError):
        coverage_report([])


def test_classify_maturity_stops_at_experimental_when_floors_unmet():
    result = classify_maturity({"utility": 0.5})
    assert result["tier"] == MaturityTier.EXPERIMENTAL.value


def test_classify_maturity_reaches_reference_when_everything_clears():
    metrics = {
        "utility": 0.9, "activation_precision": 0.9, "activation_recall": 0.9,
        "robustness": 0.8, "generalization_iid": 0.8, "generalization_ood": 0.8,
        "in_reference_envelope": True, "optimization_resistance": 0.001,
        "cross_model_transfer": 0.8, "independently_reproduced": True,
    }
    result = classify_maturity(metrics)
    assert result["tier"] == MaturityTier.REFERENCE.value
    assert result["reasons"] == []


def test_classify_maturity_stops_at_mature_when_not_saturated():
    metrics = {
        "utility": 0.9, "activation_precision": 0.9, "activation_recall": 0.9,
        "robustness": 0.8, "generalization_iid": 0.8, "generalization_ood": 0.8,
        "in_reference_envelope": True, "optimization_resistance": 0.5,
    }
    result = classify_maturity(metrics)
    assert result["tier"] == MaturityTier.MATURE.value


def test_provenance_record_requires_model_id():
    with pytest.raises(ValueError):
        ProvenanceRecord(model_id="")


def test_current_benchmark_version_is_a_benchmark_version_instance():
    assert isinstance(CURRENT_BENCHMARK_VERSION, BenchmarkVersion)
    assert CURRENT_BENCHMARK_VERSION.to_dict()["task_suite"]


def test_content_hash_is_deterministic_and_order_independent():
    a = content_hash({"x": 1, "y": 2})
    b = content_hash({"y": 2, "x": 1})
    assert a == b
    assert content_hash({"x": 1}) != a


def test_family_conditioned_percentile_ranks_within_distribution():
    result = family_conditioned_percentile(90.0, [10.0, 20.0, 30.0, 100.0])
    assert result["percentile"] == pytest.approx(75.0)


def test_knn_distance_requires_enough_reference_points():
    with pytest.raises(ValueError):
        knn_distance([0.0, 0.0], [[1.0, 1.0]], k=3)


def test_goodness_of_fit_rejects_uniform_random_reference_as_non_normal_or_normal_consistently():
    rng = np.random.default_rng(0)
    reference = rng.normal(size=(30, 2))
    result = goodness_of_fit(reference)
    assert set(result) == {"p_values", "alpha", "normal_enough"}
    assert len(result["p_values"]) == 2


def test_mahalanobis_membership_zero_at_the_mean():
    rng = np.random.default_rng(1)
    reference = rng.normal(size=(20, 2))
    result = mahalanobis_membership(reference.mean(axis=0), reference)
    assert result["distance"] == pytest.approx(0.0, abs=1e-6)


def test_select_envelope_estimator_falls_back_for_small_reference_sets():
    assert select_envelope_estimator([[0.0, 0.0], [1.0, 1.0]]) == "family_conditioned_percentile"
