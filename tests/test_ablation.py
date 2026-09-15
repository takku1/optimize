from prompt_optimization.evaluators import load_evaluator
from prompt_optimization.search import run_ablation


def test_ablation_runs_shared_baselines_without_promotion():
    report = run_ablation(
        "# Skill\n\nVerify findings independently.", load_evaluator("synthetic"),
        baselines=("no_skill", "simple_rewrite"), seed=2,
    )
    assert report["baselines"] == ["no_skill", "simple_rewrite"]
    assert set(report["reports"]) == {"no_skill", "simple_rewrite"}
    assert report["promotion_status"] == "NOT_EVALUATED"
