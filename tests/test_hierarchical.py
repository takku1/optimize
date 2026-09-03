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
