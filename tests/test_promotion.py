"""Tests for iteration-vs-validated-improvement promotion verdicts."""
from prompt_optimization.capability import PromotionVerdict, compare_versions
from prompt_optimization.contracts import HardInvariant, IntentContract, ScenarioResult


def _contract() -> IntentContract:
    return IntentContract(
        id="test-skill-v1",
        outcome="Do the thing correctly.",
        hard_invariants=(HardInvariant("no-invent", "Never invents requirements."),),
    )


def _row(scenario_id: str, utility: float, *, invariant_ok: bool = True) -> ScenarioResult:
    return ScenarioResult(scenario_id=scenario_id, utility=utility, invariants={"no-invent": invariant_ok})


def test_synthetic_backend_never_rises_above_candidate():
    result = compare_versions(
        "v1", 100, {"U": 0.5, "R": 0.5}, "v2", 80, {"U": 0.6, "R": 0.6},
        evaluator_synthetic=True,
    )
    assert result.verdict == PromotionVerdict.CANDIDATE
    assert result.token_delta == -20


def test_missing_contract_scenarios_stays_candidate_even_with_real_backend():
    result = compare_versions(
        "v1", 100, {"U": 0.5, "R": 0.5}, "v2", 80, {"U": 0.6, "R": 0.6},
        evaluator_synthetic=False,
    )
    assert result.verdict == PromotionVerdict.CANDIDATE


def test_real_backend_with_preserved_invariants_and_noninferior_utility_validates():
    baseline = [_row(f"s{i}", 0.7) for i in range(8)]
    candidate = [_row(f"s{i}", 0.75) for i in range(8)]
    result = compare_versions(
        "v1", 100, {"U": 0.7, "R": 0.7}, "v2", 80, {"U": 0.75, "R": 0.72},
        evaluator_synthetic=False,
        contract=_contract(),
        baseline_scenarios=baseline,
        candidate_scenarios=candidate,
        bootstrap_resamples=200,
    )
    assert result.verdict == PromotionVerdict.VALIDATED_IMPROVEMENT
    assert result.pareto_dominant == "candidate"


def test_real_backend_rejects_lost_hard_invariant_even_with_higher_utility():
    baseline = [_row(f"s{i}", 0.5) for i in range(6)]
    candidate = [_row(f"s{i}", 0.95, invariant_ok=False) for i in range(6)]
    result = compare_versions(
        "v1", 100, {"U": 0.5, "R": 0.5}, "v2", 90, {"U": 0.95, "R": 0.9},
        evaluator_synthetic=False,
        contract=_contract(),
        baseline_scenarios=baseline,
        candidate_scenarios=candidate,
        bootstrap_resamples=100,
    )
    assert result.verdict == PromotionVerdict.REJECTED
    assert result.regressed_invariants == ("no-invent",)
    assert result.floor_gap_invariants == ()
    assert "regressed on hard invariant" in result.reasons[0]


def test_real_backend_distinguishes_preexisting_floor_gap_from_regression():
    # both baseline and candidate fail the invariant -- must not read as "candidate lost it"
    baseline = [_row(f"s{i}", 0.5, invariant_ok=False) for i in range(6)]
    candidate = [_row(f"s{i}", 0.55, invariant_ok=False) for i in range(6)]
    result = compare_versions(
        "v1", 100, {"U": 0.5, "R": 0.5}, "v2", 90, {"U": 0.55, "R": 0.5},
        evaluator_synthetic=False,
        contract=_contract(),
        baseline_scenarios=baseline,
        candidate_scenarios=candidate,
        bootstrap_resamples=100,
    )
    assert result.verdict == PromotionVerdict.REJECTED
    assert result.regressed_invariants == ()
    assert result.floor_gap_invariants == ("no-invent",)
    assert any("not a candidate-caused regression" in reason for reason in result.reasons)


def test_real_backend_rejects_when_baseline_pareto_dominates():
    baseline = [_row(f"s{i}", 0.9) for i in range(8)]
    candidate = [_row(f"s{i}", 0.9) for i in range(8)]
    result = compare_versions(
        "v1", 50, {"U": 0.9, "R": 0.9}, "v2", 200, {"U": 0.9, "R": 0.9},
        evaluator_synthetic=False,
        contract=_contract(),
        baseline_scenarios=baseline,
        candidate_scenarios=candidate,
        bootstrap_resamples=100,
    )
    assert result.verdict == PromotionVerdict.REJECTED
    assert result.pareto_dominant == "baseline"


def test_to_dict_round_trips_verdict_as_string():
    result = compare_versions("v1", 10, {"U": 0.5, "R": 0.5}, "v2", 10, {"U": 0.5, "R": 0.5},
                               evaluator_synthetic=True)
    assert result.to_dict()["verdict"] == "candidate"
