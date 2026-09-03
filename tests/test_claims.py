"""Tests for capability.claims: checking doc assertions against live-recomputed values."""
import pytest

from prompt_optimization.capability import Claim, all_passed, format_report, verify_claim, verify_claims


def test_numeric_claim_passes_within_tolerance():
    claim = Claim(description="utility", doc="REPORT.md", expected=0.9675, actual=0.96751, tolerance=1e-3)
    result = verify_claim(claim)
    assert result.passed
    assert result.delta == pytest.approx(1e-5, abs=1e-6)


def test_numeric_claim_fails_outside_tolerance():
    claim = Claim(description="utility", doc="REPORT.md", expected=0.9675, actual=0.93, tolerance=1e-3)
    result = verify_claim(claim)
    assert not result.passed
    assert result.delta == pytest.approx(0.0375, abs=1e-6)


def test_bool_claim_does_not_use_numeric_tolerance():
    # True == 1 and False == 0 in Python; a naive numeric branch would treat
    # this as a passing numeric comparison with delta 1.0. Bools must compare
    # by identity, not slip into the int/float tolerance branch.
    claim = Claim(description="reaudit-reclassifies", doc="REPORT.md", expected=True, actual=False, tolerance=5.0)
    result = verify_claim(claim)
    assert not result.passed
    assert result.delta is None


def test_bool_claim_passes_on_match():
    claim = Claim(description="grounded-evidence", doc="REPORT.md", expected=True, actual=True)
    assert verify_claim(claim).passed


def test_non_numeric_claim_compares_by_equality():
    claim = Claim(description="verdict", doc="REPORT.md", expected="REJECTED", actual="REJECTED")
    assert verify_claim(claim).passed
    claim2 = Claim(description="verdict", doc="REPORT.md", expected="REJECTED", actual="ACCEPTED")
    assert not verify_claim(claim2).passed


def test_verify_claims_preserves_order_and_all_passed():
    claims = [
        Claim(description="a", doc="d", expected=1, actual=1),
        Claim(description="b", doc="d", expected=2, actual=2),
    ]
    results = verify_claims(claims)
    assert [r.claim.description for r in results] == ["a", "b"]
    assert all_passed(results)


def test_all_passed_false_on_any_failure():
    claims = [
        Claim(description="a", doc="d", expected=1, actual=1),
        Claim(description="b", doc="d", expected=2, actual=3),
    ]
    assert not all_passed(verify_claims(claims))


def test_format_report_flags_failures_and_counts():
    claims = [
        Claim(description="a", doc="d", expected=1, actual=1),
        Claim(description="b", doc="d", expected=2, actual=3),
    ]
    report = format_report(verify_claims(claims))
    assert "1/2 claims verified" in report
    assert "[PASS]" in report
    assert "[FAIL]" in report
