"""The real-evaluator seam: synthetic default plus rubric/callable backends."""
import json
import math

import pytest

from prompt_optimization.evaluators import (
    CallableEvaluator,
    EvaluationResult,
    RubricEvaluator,
    SyntheticBasinEvaluator,
    get_profile,
    load_evaluator,
    project_utility,
)


def test_synthetic_backend_is_the_default_and_marked_synthetic():
    ev = load_evaluator("synthetic")
    assert isinstance(ev, SyntheticBasinEvaluator)
    assert ev.synthetic is True
    result = ev.evaluate("a.py", "verify each prior finding independently")
    assert isinstance(result, EvaluationResult)
    assert result.tokens > 0


def test_synthetic_backend_rejects_unknown_target():
    with pytest.raises(SystemExit):
        load_evaluator("synthetic", target_name="NOPE")


def test_synthetic_backend_truncates_long_text_instead_of_hanging():
    # contextual_vector runs full O(n^2) self-attention with no chunking; a
    # multi-thousand-token file (found via a real skill file during manual
    # testing) must be capped rather than attempted at full size.
    ev = load_evaluator("synthetic", max_tokens=50)
    long_text = "word " * 500
    result = ev.evaluate("a.py", long_text)
    assert result.tokens == 50
    assert result.metadata["truncated"] is True
    assert result.metadata["original_tokens"] == 500


def test_synthetic_backend_does_not_flag_short_text_as_truncated():
    ev = load_evaluator("synthetic", max_tokens=50)
    result = ev.evaluate("a.py", "a short prompt")
    assert result.metadata == {}


def test_rubric_backend_reads_real_judgments_and_is_not_synthetic(tmp_path):
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps({
        "a.py": {"score": 0.9, "reliability": 0.95, "notes": "manual review"},
    }), encoding="utf-8")
    ev = load_evaluator("rubric", rubric_file=str(rubric))
    assert ev.synthetic is False
    result = ev.evaluate("a.py", "text")
    assert result.score == 0.9
    assert result.reliability == 0.95
    assert result.metadata["notes"] == "manual review"


def test_rubric_backend_raises_on_missing_entry(tmp_path):
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps({"a.py": {"score": 0.9}}), encoding="utf-8")
    ev = load_evaluator("rubric", rubric_file=str(rubric))
    with pytest.raises(KeyError):
        ev.evaluate("b.py", "text")


def test_rubric_backend_requires_rubric_file_flag():
    with pytest.raises(SystemExit):
        load_evaluator("rubric")


def test_callable_backend_delegates_to_a_dotted_function():
    import sys
    import types

    module = types.ModuleType("fake_eval_module")
    setattr(module, "my_eval", lambda text: {"score": 0.5, "tokens": len(text.split())})
    sys.modules["fake_eval_module"] = module

    ev = load_evaluator("callable", evaluator_fn="fake_eval_module:my_eval")
    assert ev.synthetic is False
    result = ev.evaluate("a.py", "one two three")
    assert result.score == 0.5
    assert result.tokens == 3


def test_callable_backend_rejects_bad_dotted_path():
    with pytest.raises(ValueError):
        CallableEvaluator("not-a-dotted-path")


def test_callable_backend_requires_evaluator_fn_flag():
    with pytest.raises(SystemExit):
        load_evaluator("callable")


def test_unknown_backend_is_rejected():
    with pytest.raises(SystemExit):
        load_evaluator("nope")


def test_evaluation_result_defaults_to_deterministic_tier():
    result = EvaluationResult(tokens=1, score=0.5)
    assert result.tier == "deterministic"


def test_evaluation_result_rejects_unknown_tier():
    with pytest.raises(ValueError):
        EvaluationResult(tokens=1, score=0.5, tier="oracle")


@pytest.mark.parametrize("field", ["score", "reliability", "uncertainty"])
def test_evaluation_result_rejects_nonfinite_metrics(field):
    values = {"tokens": 1, "score": 0.5, field: math.nan}
    with pytest.raises(ValueError, match="finite"):
        EvaluationResult(**values)


def test_synthetic_backend_rejects_unsafe_dimensions_and_token_caps():
    with pytest.raises(ValueError, match="divisible by 4"):
        SyntheticBasinEvaluator(d_model=6)
    with pytest.raises(ValueError, match="max_tokens"):
        SyntheticBasinEvaluator(max_tokens=0)


def test_rubric_backend_defaults_to_human_tier_and_is_overridable(tmp_path):
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps({
        "a.py": {"score": 0.9},
        "b.py": {"score": 0.7, "tier": "model"},
    }), encoding="utf-8")
    ev = load_evaluator("rubric", rubric_file=str(rubric))
    assert ev.evaluate("a.py", "text").tier == "human"
    assert ev.evaluate("b.py", "text").tier == "model"


def test_callable_backend_defaults_to_model_tier():
    import sys
    import types

    module = types.ModuleType("fake_eval_module_tier")
    setattr(module, "my_eval", lambda text: {"score": 0.5})
    sys.modules["fake_eval_module_tier"] = module
    ev = load_evaluator("callable", evaluator_fn="fake_eval_module_tier:my_eval")
    assert ev.evaluate("a.py", "text").tier == "model"


def test_get_profile_falls_back_to_uniform_for_unknown_family():
    weights = get_profile("some-undeclared-family")
    assert weights == {"task_success": 0.25, "correctness": 0.25, "invariant_adherence": 0.25, "calibration": 0.25}


def test_project_utility_matches_hand_computed_weighted_sum():
    omega = {"task_success": 1.0, "correctness": 1.0, "invariant_adherence": 0.0, "calibration": 0.0}
    result = project_utility(omega, "formatting")
    expected = 0.15 * 1.0 + 0.40 * 1.0 + 0.40 * 0.0 + 0.05 * 0.0
    assert result["utility"] == pytest.approx(expected)
    assert result["weights"]["correctness"] == 0.40


def test_project_utility_rejects_missing_omega_keys():
    with pytest.raises(ValueError):
        project_utility({"task_success": 1.0}, "formatting")
