"""Tests for evaluator-stack calibration: judge stability and agreement."""
import pytest

from prompt_optimization.evaluators import (
    UNSTABLE_FLAG,
    PairwiseJudgment,
    cohens_kappa,
    generate_blind_ids,
    judge_human_agreement,
    position_consistency,
)


def test_position_consistency_is_perfect_when_winner_never_flips():
    forward = [PairwiseJudgment("c1", ("A", "B"), "A"), PairwiseJudgment("c2", ("A", "B"), "B")]
    reversed_ = [PairwiseJudgment("c1", ("B", "A"), "A"), PairwiseJudgment("c2", ("B", "A"), "B")]
    result = position_consistency(forward, reversed_)
    assert result["consistency"] == 1.0
    assert result["flag"] is None


def test_position_consistency_flags_instability_below_threshold():
    # A judge with pure position bias always picks whichever candidate is
    # shown first, so the *named winner* flips (A -> B) when order reverses.
    forward = [PairwiseJudgment(f"c{i}", ("A", "B"), "A") for i in range(6)]
    reversed_ = [PairwiseJudgment(f"c{i}", ("B", "A"), "B") for i in range(6)]
    result = position_consistency(forward, reversed_)
    assert result["consistency"] == 0.0
    assert result["flag"] == UNSTABLE_FLAG


def test_position_consistency_requires_shared_case_ids():
    with pytest.raises(ValueError):
        position_consistency(
            [PairwiseJudgment("a", ("A", "B"), "A")],
            [PairwiseJudgment("b", ("B", "A"), "A")],
        )


def test_pairwise_judgment_rejects_winner_outside_order():
    with pytest.raises(ValueError):
        PairwiseJudgment("c1", ("A", "B"), "C")


def test_generate_blind_ids_is_reproducible_for_a_fixed_seed():
    units = ["v1_2_4:01", "v1_3_0:01", "v1_2_4:02", "v1_3_0:02"]
    a = generate_blind_ids(units, seed=7)
    b = generate_blind_ids(units, seed=7)
    assert a == b


def test_generate_blind_ids_covers_every_unit_with_unique_opaque_tokens():
    units = ["a", "b", "c"]
    mapping = generate_blind_ids(units, seed=1)
    assert set(mapping.keys()) == set(units)
    assert len(set(mapping.values())) == len(units)


def test_generate_blind_ids_tokens_are_opaque():
    # token content must not encode the unit's own name/identity
    units = ["v1_2_4:01-stop-when-supported", "v1_3_0:01-stop-when-supported"]
    mapping = generate_blind_ids(units, seed=2, prefix="run")
    for unit, token in mapping.items():
        assert token.startswith("run_")
        assert "v1_2_4" not in token and "v1_3_0" not in token
        assert unit not in token


def test_generate_blind_ids_rejects_empty_or_duplicate_units():
    with pytest.raises(ValueError):
        generate_blind_ids([])
    with pytest.raises(ValueError):
        generate_blind_ids(["a", "a"])


def test_judge_human_agreement_reports_perfect_correlation_for_identical_scores():
    result = judge_human_agreement([0.1, 0.5, 0.9], [0.1, 0.5, 0.9])
    assert result["pearson_r"] == pytest.approx(1.0)
    assert result["mae"] == pytest.approx(0.0)


def test_cohens_kappa_is_one_for_identical_labels():
    assert cohens_kappa(["pass", "fail", "pass"], ["pass", "fail", "pass"]) == pytest.approx(1.0)


def test_cohens_kappa_is_near_zero_for_chance_agreement():
    # balanced, independent-looking disagreement pattern
    a = ["pass", "fail", "pass", "fail"]
    b = ["fail", "pass", "fail", "pass"]
    assert cohens_kappa(a, b) < 0
