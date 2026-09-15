import pytest

from prompt_optimization.calibration import agreement_report, fleiss_kappa, icc_absolute_agreement


DIMENSIONS = ("clarity_definition", "problem_value_validity")


def _rows():
    return [
        {"artifact_id": "a", "rater_id": "r1", "clarity_definition": 8, "problem_value_validity": 4, "stage": 5},
        {"artifact_id": "a", "rater_id": "r2", "clarity_definition": 8, "problem_value_validity": 5, "stage": 5},
        {"artifact_id": "b", "rater_id": "r1", "clarity_definition": 3, "problem_value_validity": 2, "stage": 2},
        {"artifact_id": "b", "rater_id": "r2", "clarity_definition": 4, "problem_value_validity": 2, "stage": 2},
        {"artifact_id": "c", "rater_id": "r1", "clarity_definition": 6, "problem_value_validity": 7, "stage": 4},
        {"artifact_id": "c", "rater_id": "r2", "clarity_definition": 6, "problem_value_validity": 6, "stage": 4},
    ]


def test_agreement_report_declares_statistics_and_design():
    report = agreement_report(_rows(), dimensions=DIMENSIONS, bootstrap_resamples=50)
    assert report["design"] == "fully_crossed"
    assert report["dimensions"]["clarity_definition"]["statistic"] == "ICC(2,1)"
    assert report["stage_statistic"] == "Fleiss_kappa"


def test_agreement_requires_complete_crossing():
    with pytest.raises(ValueError, match="fully crossed"):
        agreement_report(_rows()[:-1], dimensions=DIMENSIONS, bootstrap_resamples=0)


def test_perfect_agreement_is_one():
    assert icc_absolute_agreement([[1, 1], [2, 2], [3, 3]]) == pytest.approx(1.0)
    assert fleiss_kappa([["a", "a"], ["b", "b"]]) == pytest.approx(1.0)
