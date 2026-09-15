from prompt_optimization.search import HierarchicalConfig, search_hierarchically


def test_hierarchical_search_reconciles_and_records_levels():
    def score(text):
        return {"utility": 1.0 if "better" in text else 0.0,
                "tokens": len(text.split()), "hard_invariants_passed": "bad" not in text}

    def mutate(text, level, branch):
        return text + (" better" if branch == 0 and level == "token" else "")

    def reconcile(text, level, depth):
        return text + ("\n" if level == "token" else "")

    result = search_hierarchically("seed", score, mutate, reconcile,
                                   config=HierarchicalConfig(max_depth=2, beam_width=2))
    assert "better" in result.selected_text
    assert result.explored[0]["level"] == "token"
    assert result.selected_score["hard_invariants_passed"] is True


def test_hierarchical_search_respects_evaluation_budget():
    calls = []

    def score(text):
        calls.append(text)
        return {"utility": 0.0, "tokens": len(text.split()), "hard_invariants_passed": True}

    result = search_hierarchically(
        "seed", score, lambda text, level, branch: f"{text} {level} {branch}",
        lambda text, level, depth: text,
        config=HierarchicalConfig(max_depth=6, beam_width=3, max_evaluations=5),
    )
    assert len(calls) <= 5
    assert result.selected_text
