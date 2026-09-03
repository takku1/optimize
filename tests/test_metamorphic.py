"""Tests for metamorphic transformation-class reporting."""
import pytest

from prompt_optimization.metrics import MetamorphicCase, TransformationKind, metamorphic_report


def test_preserving_transformation_reports_consistency():
    cases = [MetamorphicCase("ref1", TransformationKind.PARAPHRASE, "var1")]
    report = metamorphic_report(cases, {"ref1": 0.8}, {"var1": 0.82}, tolerance=0.05)
    assert report["paraphrase"]["type"] == "preserving"
    assert report["paraphrase"]["consistency"] == 1.0


def test_activation_changing_transformation_reports_change_rate():
    cases = [MetamorphicCase("ref1", TransformationKind.CONFLICTING_DEMAND, "var1")]
    report = metamorphic_report(cases, {"ref1": 0.2}, {"var1": 0.9}, activation_threshold=0.5)
    assert report["conflicting_demand"]["type"] == "activation_changing"
    assert report["conflicting_demand"]["change_rate"] == 1.0


def test_case_rejects_unclassified_kind_gracefully_via_enum():
    with pytest.raises(ValueError):
        MetamorphicCase("", TransformationKind.PARAPHRASE, "v1")


def test_report_requires_at_least_one_case():
    with pytest.raises(ValueError):
        metamorphic_report([], {}, {})
