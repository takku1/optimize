from types import SimpleNamespace

from prompt_optimization.evaluators import SuccessBand, check_success_band, judge_internally


def test_success_band_supports_distinct_phrase_count():
    band = SuccessBand(required_any_phrases=("context", "decision", "forces"), min_distinct_matches=2)
    result = check_success_band("Context and decision.", band)
    assert result["passed"] is True
    assert result["distinct_required_phrase_matches"] == 2


def test_internal_judge_does_not_claim_semantic_success_without_a_band():
    result = judge_internally("A plausible answer.", SimpleNamespace(metadata={}))
    assert result["status"] == "unresolved"
    assert result["passed"] is None


def test_internal_judge_certifies_only_the_mechanical_band():
    scenario = SimpleNamespace(metadata={"success_band": {"max_words": 3}})
    result = judge_internally("one two", scenario)
    assert result["status"] == "certified"
    assert result["semantic_review_required"] is True
