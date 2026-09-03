"""Tests for intent contracts and paired behavioral comparison."""
import json
from pathlib import Path

import pytest

from prompt_optimization.contracts import (
    CounterfactualCase,
    DefectType,
    HardInvariant,
    IntentContract,
    ScenarioResult,
    ablation_deltas,
    compare_contract_results,
    counterfactual_detection_rate,
    load_scenarios,
    stratified_utility_report,
)
from prompt_optimization.cli import main


def _contract() -> IntentContract:
    return IntentContract(
        id="hookify-writing-rules-v1",
        outcome="Produce a valid rule that prevents the requested behavior.",
        activation=("user asks to create a hookify rule",),
        hard_invariants=(
            HardInvariant("correct-frontmatter", "Rule has required YAML fields."),
            HardInvariant("tested", "Rule is tested against a positive and negative example."),
        ),
        outputs=(".claude/hookify.<name>.local.md",),
    )


def _row(scenario_id: str, utility: float, *, valid: bool = True, tested: bool = True) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        utility=utility,
        invariants={"correct-frontmatter": valid, "tested": tested},
        costs={"tokens": 100.0},
    )


def test_contract_round_trips_to_json_shape():
    contract = _contract()
    restored = IntentContract.from_dict(json.loads(json.dumps(contract.to_dict())))
    assert restored == contract


def test_reviewed_contract_and_scenario_fixtures_are_loadable():
    root = Path(__file__).parent / "fixtures"
    for contract_path in (root / "contracts").glob("*.json"):
        value = json.loads(contract_path.read_text(encoding="utf-8"))
        contract = IntentContract.from_dict(value)
        scenario_path = root / "scenarios" / f"{contract.id}.json"
        scenarios = load_scenarios(scenario_path)
        assert scenarios
        invariant_ids = {item.id for item in contract.hard_invariants}
        assert all(set(s.expected_invariants) <= invariant_ids for s in scenarios)


def test_compare_accepts_paired_noninferior_candidate():
    baseline = [_row(f"s{i}", 0.7) for i in range(8)]
    candidate = [_row(f"s{i}", 0.8) for i in range(8)]
    report = compare_contract_results(
        _contract(), baseline, candidate, bootstrap_resamples=200, seed=3
    )
    assert report["accepted"] is True
    assert report["utility"]["noninferior"] is True
    assert all(item["passed"] for item in report["hard_invariants"].values())
    assert report["costs"]["tokens"]["delta"] == 0.0


def test_compare_rejects_lost_hard_invariant_even_with_higher_utility():
    baseline = [_row(f"s{i}", 0.5) for i in range(6)]
    candidate = [_row(f"s{i}", 0.95, tested=False) for i in range(6)]
    report = compare_contract_results(_contract(), baseline, candidate, bootstrap_resamples=100)
    assert report["accepted"] is False
    assert report["hard_invariants"]["tested"]["passed"] is False
    assert report["hard_invariants"]["tested"]["status"] == "regression"
    assert report["hard_invariants"]["tested"]["baseline_passed"] is True
    assert report["utility"]["noninferior"] is True


def test_compare_distinguishes_regression_from_a_preexisting_floor_gap():
    # baseline ALSO fails "tested" -- candidate did not cause this, and the
    # report must say so rather than reading as a candidate-caused loss.
    baseline = [_row(f"s{i}", 0.5, tested=False) for i in range(6)]
    candidate = [_row(f"s{i}", 0.6, tested=False) for i in range(6)]
    report = compare_contract_results(_contract(), baseline, candidate, bootstrap_resamples=100)
    assert report["accepted"] is False
    assert report["hard_invariants"]["tested"]["status"] == "floor_not_met"
    assert report["hard_invariants"]["tested"]["baseline_passed"] is False
    # the correct-frontmatter invariant is untouched and should still read as passed
    assert report["hard_invariants"]["correct-frontmatter"]["status"] == "passed"


def test_compare_rejects_regression_using_lower_confidence_bound():
    baseline = [_row(f"s{i}", 0.9) for i in range(10)]
    candidate = [_row(f"s{i}", 0.0) for i in range(10)]
    report = compare_contract_results(
        _contract(), baseline, candidate, noninferiority_margin=0.05, bootstrap_resamples=200
    )
    assert report["accepted"] is False
    assert report["utility"]["noninferior"] is False


def test_compare_rejects_mismatched_scenario_sets():
    with pytest.raises(ValueError, match="scenario sets differ"):
        compare_contract_results(_contract(), [_row("a", 1.0)], [_row("b", 1.0)])


def test_stratified_utility_report_separates_iid_and_ood():
    rows = [
        ScenarioResult("s1", 0.9, {}, metadata={"split": "iid"}),
        ScenarioResult("s2", 0.8, {}, metadata={"split": "iid"}),
        ScenarioResult("s3", 0.3, {}, metadata={"split": "ood"}),
    ]
    report = stratified_utility_report(rows, bootstrap_resamples=100)
    assert report["iid"]["n"] == 2
    assert report["ood"]["n"] == 1
    assert report["iid"]["mean"] > report["ood"]["mean"]


def test_stratified_utility_report_defaults_missing_split_to_unspecified():
    report = stratified_utility_report([ScenarioResult("s1", 0.5, {})], bootstrap_resamples=50)
    assert "unspecified" in report


def test_stratified_utility_report_requires_results():
    with pytest.raises(ValueError):
        stratified_utility_report([])


def test_ablation_deltas_measures_marginal_contribution():
    deltas = ablation_deltas(full_score=0.9, component_scores={"intro": 0.85, "examples": 0.6})
    assert deltas["intro"] == pytest.approx(0.05)
    assert deltas["examples"] == pytest.approx(0.3)


def test_ablation_deltas_requires_components():
    with pytest.raises(ValueError):
        ablation_deltas(0.9, {})


def test_counterfactual_detection_rate_groups_by_defect_type():
    cases = [
        CounterfactualCase("base", DefectType.CONTRADICTORY, "v1", detected=True),
        CounterfactualCase("base", DefectType.CONTRADICTORY, "v2", detected=False),
        CounterfactualCase("base", DefectType.VERBOSE, "v3", detected=True),
    ]
    rates = counterfactual_detection_rate(cases)
    assert rates["contradictory"] == pytest.approx(0.5)
    assert rates["verbose"] == pytest.approx(1.0)


def test_counterfactual_detection_rate_requires_scored_cases():
    with pytest.raises(ValueError):
        counterfactual_detection_rate([CounterfactualCase("base", DefectType.VERBOSE, "v1")])


def test_counterfactual_case_rejects_empty_ids():
    with pytest.raises(ValueError):
        CounterfactualCase("", DefectType.VERBOSE, "v1")


def test_compare_cli_emits_json_report(tmp_path, capsys):
    contract_path = tmp_path / "contract.json"
    results_path = tmp_path / "results.json"
    contract_path.write_text(json.dumps(_contract().to_dict()), encoding="utf-8")
    rows = [_row("s1", 0.8).to_dict(), _row("s2", 0.9).to_dict()]
    results_path.write_text(json.dumps({
        "contract": _contract().id,
        "baseline": [{**row, "utility": row["utility"] - 0.1} for row in rows],
        "candidate": rows,
    }), encoding="utf-8")
    rc = main([
        "compare", "--json", "--bootstrap-resamples", "100",
        "--contract", str(contract_path), "--results", str(results_path),
    ])
    report = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert report["accepted"] is True
    assert report["scenario_count"] == 2
