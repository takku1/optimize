"""Tests for pre-registered, mechanically-checkable success bands."""
import pytest

from prompt_optimization.evaluators import SuccessBand, check_success_band


def test_success_band_rejects_inverted_word_bounds():
    with pytest.raises(ValueError):
        SuccessBand(min_words=100, max_words=10)


def test_success_band_rejects_negative_bounds():
    with pytest.raises(ValueError):
        SuccessBand(min_words=-1)
    with pytest.raises(ValueError):
        SuccessBand(max_words=-1)


def test_check_success_band_flags_over_length_response():
    band = SuccessBand(max_words=20)
    result = check_success_band("word " * 30, band)
    assert result["passed"] is False
    assert "max_words" in result["violations"][0]


def test_check_success_band_flags_under_length_response():
    band = SuccessBand(min_words=20)
    result = check_success_band("short response", band)
    assert result["passed"] is False
    assert "min_words" in result["violations"][0]


def test_check_success_band_flags_forbidden_phrase_case_insensitively():
    band = SuccessBand(forbidden_phrases=("Full Architecture",))
    result = check_success_band("escalating to full architecture mode", band)
    assert result["passed"] is False
    assert "forbidden phrase" in result["violations"][0]


def test_check_success_band_requires_at_least_one_required_phrase():
    band = SuccessBand(required_any_phrases=("resolved", "regressed"))
    failing = check_success_band("everything looks fine, no verdict given", band)
    assert failing["passed"] is False
    passing = check_success_band("the finding is Resolved as of this diff", band)
    assert passing["passed"] is True


def test_check_success_band_passes_clean_text_with_no_constraints():
    result = check_success_band("anything at all", SuccessBand())
    assert result["passed"] is True
    assert result["violations"] == []


def test_success_band_round_trips_through_dict():
    band = SuccessBand(min_words=1, max_words=300, forbidden_phrases=("x",), required_any_phrases=("y",))
    restored = SuccessBand.from_dict(band.to_dict())
    assert restored == band
