from types import SimpleNamespace

from prompt_optimization.validators import aggregate_validations, evaluate_candidate, evaluate_neighborhood, validate_response


def test_missing_mechanical_spec_is_unresolved():
    result = validate_response("anything", SimpleNamespace(id="s1", metadata={}))
    assert result.status == "unresolved"


def test_aggregate_requires_all_cases_to_be_resolved_and_passed():
    passed = validate_response("context decision", SimpleNamespace(
        id="s1", metadata={"success_band": {"required_any_phrases": ["context"]}}
    ))
    unresolved = validate_response("anything", SimpleNamespace(id="s2", metadata={}))
    score = aggregate_validations([passed, unresolved], tokens=12)
    assert score["utility"] == 0.5
    assert score["hard_invariants_passed"] is False
    assert score["unresolved"] == 1


def test_evaluate_candidate_executes_each_scenario_and_rollout():
    scenarios = [SimpleNamespace(id="a", metadata={"success_band": {"max_words": 3}})]
    calls = []

    def executor(skill, scenario, rollout):
        calls.append((skill, scenario.id, rollout))
        return "one two"

    score = evaluate_candidate("skill", scenarios, executor, rollouts=2)
    assert len(calls) == 2
    assert score["utility"] == 1.0
    assert score["hard_invariants_passed"] is True


def test_evaluate_neighborhood_reports_stability_metrics():
    scenarios = [SimpleNamespace(id="a", metadata={"success_band": {"max_words": 3}})]

    def executor(skill, scenario, rollout):
        return "one two" if skill != "fragile" else "one two three four"

    score = evaluate_neighborhood("stable", scenarios, executor, ["stable variant", "fragile"])
    assert score["neighborhood_size"] == 3
    assert score["neighborhood_mean"] == 2 / 3
    assert score["neighborhood_worst"] == 0
    assert score["neighborhood_stddev"] > 0
    assert score["hard_invariants_passed"] is False
