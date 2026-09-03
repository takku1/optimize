"""Tests for the persistent, content-addressed evolution graph."""
import pytest

from prompt_optimization.graph import (
    EvaluationRecord,
    GraphStore,
    MutationEdge,
    SkillNode,
    mutation_family_stats,
    retrieve_similar_transitions,
)


def _store(tmp_path) -> GraphStore:
    return GraphStore(tmp_path / "graph")


def test_skill_hash_is_content_addressed_and_stable():
    a = SkillNode(skill_text="hello world", token_count=2)
    b = SkillNode(skill_text="hello world", token_count=2)
    c = SkillNode(skill_text="different text", token_count=2)
    assert a.skill_hash == b.skill_hash
    assert a.skill_hash != c.skill_hash


def test_put_skill_is_idempotent_under_identical_content(tmp_path):
    store = _store(tmp_path)
    node = SkillNode(skill_text="a skill", token_count=2)
    h1 = store.put_skill(node)
    h2 = store.put_skill(node)
    assert h1 == h2
    assert len(list(store.iter_skills())) == 1


def test_get_skill_round_trips(tmp_path):
    store = _store(tmp_path)
    node = SkillNode(skill_text="a skill", token_count=2, generator="human", generation=0)
    store.put_skill(node)
    restored = store.get_skill(node.skill_hash)
    assert restored.skill_text == "a skill"
    assert restored.generator == "human"


def test_get_skill_raises_for_unknown_hash(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(KeyError):
        store.get_skill("does-not-exist")


def test_mutation_edge_rejects_empty_hashes():
    with pytest.raises(ValueError):
        MutationEdge(parent_hash="", child_hash="x", mutation_family="compress")
    with pytest.raises(ValueError):
        MutationEdge(parent_hash="x", child_hash="y", mutation_family="")


def test_children_and_parents_query(tmp_path):
    store = _store(tmp_path)
    parent = SkillNode(skill_text="parent", token_count=1)
    child = SkillNode(skill_text="child", token_count=1, parent_hashes=(parent.skill_hash,))
    store.put_skill(parent)
    store.put_skill(child)
    edge = MutationEdge(parent_hash=parent.skill_hash, child_hash=child.skill_hash, mutation_family="compress")
    store.put_mutation(edge)
    assert [e.child_hash for e in store.children(parent.skill_hash)] == [child.skill_hash]
    assert [e.parent_hash for e in store.parents(child.skill_hash)] == [parent.skill_hash]


def test_lineage_walks_back_to_root(tmp_path):
    store = _store(tmp_path)
    s0 = SkillNode(skill_text="s0", token_count=1, generation=0)
    store.put_skill(s0)
    s1 = SkillNode(skill_text="s1", token_count=1, generation=1, parent_hashes=(s0.skill_hash,))
    store.put_skill(s1)
    s2 = SkillNode(skill_text="s2", token_count=1, generation=2, parent_hashes=(s1.skill_hash,))
    store.put_skill(s2)
    lineage = store.lineage(s2.skill_hash)
    assert [n.skill_text for n in lineage] == ["s0", "s1", "s2"]


def test_evaluation_record_rejects_invalid_trainability():
    with pytest.raises(ValueError):
        EvaluationRecord(skill_hash="h", scenario_id="s1", metric_results={}, trainability="NOT_A_CLASS")


def test_evaluations_for_filters_by_skill(tmp_path):
    store = _store(tmp_path)
    a = EvaluationRecord(skill_hash="hash-a", scenario_id="s1", metric_results={"utility": 0.5}, created_at="t1")
    b = EvaluationRecord(skill_hash="hash-b", scenario_id="s1", metric_results={"utility": 0.9}, created_at="t1")
    store.put_evaluation(a)
    store.put_evaluation(b)
    assert [r.skill_hash for r in store.evaluations_for("hash-a")] == ["hash-a"]


def test_retrieve_similar_transitions_ranks_by_utility_delta(tmp_path):
    store = _store(tmp_path)
    good = MutationEdge(parent_hash="p", child_hash="c1", mutation_family="compress",
                         actual_effect={"utility_delta": 0.10}, created_at="t1")
    bad = MutationEdge(parent_hash="p", child_hash="c2", mutation_family="compress",
                        actual_effect={"utility_delta": -0.05}, created_at="t2")
    unmeasured = MutationEdge(parent_hash="p", child_hash="c3", mutation_family="compress", created_at="t3")
    for edge in (bad, good, unmeasured):
        store.put_mutation(edge)
    ranked = retrieve_similar_transitions(store, mutation_family="compress")
    assert [e.child_hash for e in ranked] == ["c1", "c2"]  # unmeasured excluded, best first


def test_retrieve_similar_transitions_respects_top_k(tmp_path):
    store = _store(tmp_path)
    for i in range(10):
        store.put_mutation(MutationEdge(parent_hash="p", child_hash=f"c{i}", mutation_family="compress",
                                         actual_effect={"utility_delta": float(i)}, created_at=f"t{i}"))
    ranked = retrieve_similar_transitions(store, mutation_family="compress", top_k=3)
    assert len(ranked) == 3
    assert ranked[0].child_hash == "c9"


def test_mutation_family_stats_reports_regression_rate(tmp_path):
    store = _store(tmp_path)
    deltas = [0.1, 0.2, -0.05, -0.1]
    for i, delta in enumerate(deltas):
        store.put_mutation(MutationEdge(parent_hash="p", child_hash=f"c{i}", mutation_family="compress",
                                         actual_effect={"utility_delta": delta}, created_at=f"t{i}"))
    stats = mutation_family_stats(store)
    assert stats["compress"]["n"] == 4
    assert stats["compress"]["regression_rate"] == pytest.approx(0.5)


def test_retrieve_similar_transitions_excludes_benchmark_validation_evidence_by_default(tmp_path):
    store = _store(tmp_path)
    store.put_mutation(MutationEdge(parent_hash="p", child_hash="c1", mutation_family="compress",
                                     actual_effect={"utility_delta": 0.9}, created_at="t1",
                                     provenance={"evidence_class": "BENCHMARK_VALIDATION"}))
    store.put_mutation(MutationEdge(parent_hash="p", child_hash="c2", mutation_family="compress",
                                     actual_effect={"utility_delta": 0.1}, created_at="t2"))
    ranked = retrieve_similar_transitions(store, mutation_family="compress")
    assert [e.child_hash for e in ranked] == ["c2"]  # validation evidence excluded, even though it scores higher


def test_retrieve_similar_transitions_can_include_validation_evidence_explicitly(tmp_path):
    store = _store(tmp_path)
    store.put_mutation(MutationEdge(parent_hash="p", child_hash="c1", mutation_family="compress",
                                     actual_effect={"utility_delta": 0.9}, created_at="t1",
                                     provenance={"evidence_class": "BENCHMARK_VALIDATION"}))
    ranked = retrieve_similar_transitions(store, mutation_family="compress",
                                           evidence_classes=("OPTIMIZER_TRANSITION", "BENCHMARK_VALIDATION"))
    assert [e.child_hash for e in ranked] == ["c1"]


def test_mutation_family_stats_excludes_benchmark_validation_evidence_by_default(tmp_path):
    store = _store(tmp_path)
    store.put_mutation(MutationEdge(parent_hash="p", child_hash="c1", mutation_family="defect_injection",
                                     actual_effect={"utility_delta": -0.5}, created_at="t1",
                                     provenance={"evidence_class": "BENCHMARK_VALIDATION"}))
    stats = mutation_family_stats(store)
    assert "defect_injection" not in stats


def test_mutation_family_stats_treats_untagged_edges_as_optimizer_transitions(tmp_path):
    store = _store(tmp_path)
    store.put_mutation(MutationEdge(parent_hash="p", child_hash="c1", mutation_family="compress",
                                     actual_effect={"utility_delta": 0.2}, created_at="t1"))
    stats = mutation_family_stats(store)
    assert stats["compress"]["n"] == 1


def test_mutation_family_stats_filters_by_capability_contract(tmp_path):
    store = _store(tmp_path)
    a_child = SkillNode(skill_text="a", token_count=1, capability_contract_hash="famA")
    b_child = SkillNode(skill_text="b", token_count=1, capability_contract_hash="famB")
    store.put_skill(a_child)
    store.put_skill(b_child)
    store.put_mutation(MutationEdge(parent_hash="p", child_hash=a_child.skill_hash, mutation_family="compress",
                                     actual_effect={"utility_delta": 0.5}, created_at="t1"))
    store.put_mutation(MutationEdge(parent_hash="p", child_hash=b_child.skill_hash, mutation_family="compress",
                                     actual_effect={"utility_delta": -0.9}, created_at="t2"))
    stats = mutation_family_stats(store, capability_contract_hash="famA")
    assert stats["compress"]["n"] == 1
    assert stats["compress"]["mean_utility_delta"] == pytest.approx(0.5)
