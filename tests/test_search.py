"""Tests for the branching evolutionary search loop: state machine, mutation, archive, lineage."""
import json

import pytest

from prompt_optimization.contracts import DefectType
from prompt_optimization.evaluators import load_evaluator
from prompt_optimization.graph import GraphStore
from prompt_optimization.search import (
    BASELINES,
    BaselineConfig,
    Candidate,
    SearchState,
    archive_hypervolume,
    compress,
    get_baseline,
    inject_defect,
    is_saturated,
    make_graph_diagnose,
    new_candidate_id,
    next_state,
    random_mutation,
    rule_consolidation,
    run_bcso,
    seed_population,
    select_delta_optimal,
    structural_swap,
    update_archive,
)

SEED_TEXT = (
    "# Example skill\n\n"
    "Verify each prior finding independently before acting. "
    "Verify each prior finding independently before acting.\n\n"
    "## Details\n\n"
    "This section explains the workflow, including edge cases and recovery steps.\n"
)


def _candidate(text: str = SEED_TEXT, generation: int = 0) -> Candidate:
    return Candidate(id=new_candidate_id(text, salt=str(generation)), text=text, generation=generation)


# --- population -----------------------------------------------------------

def test_candidate_rejects_empty_text():
    with pytest.raises(ValueError):
        Candidate(id="c1", text="", generation=0)


def test_candidate_rejects_negative_generation():
    with pytest.raises(ValueError):
        Candidate(id="c1", text="x", generation=-1)


def test_seed_population_produces_generation_zero_candidates():
    pop = seed_population(SEED_TEXT, n=3)
    assert len(pop) == 3
    assert all(c.generation == 0 for c in pop)
    assert len({c.id for c in pop}) == 3  # distinct ids


# --- mutation ---------------------------------------------------------------

def test_structural_swap_preserves_generation_and_parent_lineage():
    parent = _candidate()
    child = structural_swap(parent, seed=0)
    assert child.generation == parent.generation + 1
    assert child.parent_ids == (parent.id,)
    assert child.mutation_type == "structural_swap"


def test_compress_reduces_or_maintains_sentence_count():
    parent = _candidate()
    child = compress(parent, drop_fraction=0.5, seed=0)
    assert len(child.text) <= len(parent.text)


def test_rule_consolidation_removes_exact_duplicate_lines():
    parent = _candidate("keep this\nkeep this\nunique line")
    child = rule_consolidation(parent)
    assert child.text.count("keep this") == 1
    assert "unique line" in child.text


def test_inject_defect_appends_a_labeled_defect():
    parent = _candidate()
    child = inject_defect(parent, DefectType.CONTRADICTORY)
    assert child.mutation_type == "defect_injection"
    assert len(child.text) > len(parent.text)


def test_random_mutation_is_reproducible_for_a_fixed_seed():
    parent = _candidate()
    a = random_mutation(parent, seed=5)
    b = random_mutation(parent, seed=5)
    assert a.mutation_type == b.mutation_type
    assert a.text == b.text


def test_random_mutation_respects_allowed_operators():
    parent = _candidate()
    child = random_mutation(parent, seed=1, allowed=("rule_consolidation",))
    assert child.mutation_type == "rule_consolidation"


# --- archive ------------------------------------------------------------

def test_update_archive_drops_dominated_candidates():
    archive = [{"id": "a", "U": 0.5, "R": 0.5, "tokens": 10}]
    candidates = [{"id": "b", "U": 0.6, "R": 0.6, "tokens": 5}]  # dominates a
    result = update_archive(archive, candidates)
    assert [row["id"] for row in result] == ["b"]


def test_archive_hypervolume_is_nonnegative_and_zero_for_empty_archive():
    assert archive_hypervolume([]) == 0.0
    hv = archive_hypervolume([{"id": "a", "U": 0.5, "R": 0.5, "tokens": 10}], samples=500)
    assert hv >= 0.0


def test_is_saturated_true_for_flat_history():
    assert is_saturated([1.0, 1.0, 1.0, 1.0], epsilon=0.01, checks=3) is True


def test_select_delta_optimal_prefers_cheapest_within_margin():
    archive = [
        {"id": "a", "U": 0.9, "R": 0.5, "tokens": 100},
        {"id": "b", "U": 0.89, "R": 0.5, "tokens": 20},
        {"id": "c", "U": 0.5, "R": 0.5, "tokens": 5},
    ]
    selected = select_delta_optimal(archive, delta_u=0.05)
    assert selected["id"] == "b"


def test_select_delta_optimal_handles_nonpositive_max_utility():
    archive = [{"id": "a", "U": -0.1, "R": 0.5, "tokens": 10}, {"id": "b", "U": -0.5, "R": 0.5, "tokens": 1}]
    selected = select_delta_optimal(archive, delta_u=0.02)
    assert selected["id"] == "a"  # only the exact max is eligible when U_max <= 0


def test_select_delta_optimal_requires_nonempty_archive():
    with pytest.raises(ValueError):
        select_delta_optimal([])


# --- state machine --------------------------------------------------------

def test_baseline_always_advances_to_searching():
    assert next_state(SearchState.BASELINE, qualified=False, saturated=False) == SearchState.SEARCHING


def test_searching_stays_searching_until_qualified():
    assert next_state(SearchState.SEARCHING, qualified=False, saturated=False) == SearchState.SEARCHING
    assert next_state(SearchState.SEARCHING, qualified=True, saturated=False) == SearchState.QUALIFIED


def test_saturation_check_freezes_only_when_saturated():
    assert next_state(SearchState.SATURATION_CHECK, qualified=True, saturated=False) == SearchState.SEARCHING
    assert next_state(SearchState.SATURATION_CHECK, qualified=True, saturated=True) == SearchState.FROZEN


def test_frozen_advances_to_tested_then_released():
    assert next_state(SearchState.FROZEN, qualified=True, saturated=True, tested=True) == SearchState.TESTED
    assert next_state(SearchState.TESTED, qualified=True, saturated=True) == SearchState.RELEASED


# --- baselines --------------------------------------------------------

def test_get_baseline_rejects_unknown_name():
    with pytest.raises(ValueError):
        get_baseline("nonexistent")


def test_no_skill_and_original_baselines_do_zero_generations():
    assert BASELINES["no_skill"].max_generations == 0
    assert BASELINES["original"].max_generations == 0


def test_baseline_config_rejects_empty_allowed_mutations_when_mutating():
    with pytest.raises(ValueError):
        BaselineConfig("bad", use_mutation=True, allowed_mutations=())


# --- full loop ------------------------------------------------------------

def test_run_bcso_terminates_and_reaches_released():
    evaluator = load_evaluator("synthetic")
    result = run_bcso(SEED_TEXT, evaluator, baseline="random_mutation", checkpoint_every=2, seed=0)
    assert result["report"]["state"] == "released"
    assert result["report"]["synthetic"] is True
    assert result["selected"].text


def test_run_bcso_is_reproducible_for_a_fixed_seed():
    evaluator = load_evaluator("synthetic")
    a = run_bcso(SEED_TEXT, evaluator, baseline="random_mutation", checkpoint_every=2, seed=3)
    b = run_bcso(SEED_TEXT, evaluator, baseline="random_mutation", checkpoint_every=2, seed=3)
    assert a["report"]["selected_id"] == b["report"]["selected_id"]
    assert a["selected"].text == b["selected"].text


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"checkpoint_every": 0}, "checkpoint_every"),
        ({"saturation_checks": 0}, "saturation_checks"),
        ({"epsilon_hv": -0.1}, "epsilon_hv"),
        ({"delta_u": 1.0}, "delta_u"),
        ({"max_archive_size": 0}, "max_archive_size"),
        ({"utility_min": 1.1}, "utility_min"),
    ],
)
def test_run_bcso_rejects_invalid_search_controls(kwargs, message):
    evaluator = load_evaluator("synthetic")
    with pytest.raises(ValueError, match=message):
        run_bcso(SEED_TEXT, evaluator, **kwargs)


def test_run_bcso_selected_lineage_traces_back_to_a_seed_candidate():
    evaluator = load_evaluator("synthetic")
    result = run_bcso(SEED_TEXT, evaluator, baseline="compression_only", checkpoint_every=2, seed=0)
    selected = result["selected"]
    assert selected.generation == 0 or selected.parent_ids


def test_no_skill_baseline_never_mutates():
    evaluator = load_evaluator("synthetic")
    result = run_bcso(SEED_TEXT, evaluator, baseline="no_skill", seed=0)
    assert result["selected"].text == SEED_TEXT
    assert result["report"]["generations"] == 0


def test_run_bcso_rejects_empty_seed_text():
    evaluator = load_evaluator("synthetic")
    with pytest.raises(ValueError):
        run_bcso("   ", evaluator)


def test_run_bcso_records_skills_mutations_and_evaluations_when_given_a_graph_store(tmp_path):
    store = GraphStore(tmp_path / "graph")
    evaluator = load_evaluator("synthetic")
    run_bcso(SEED_TEXT, evaluator, baseline="compression_only", checkpoint_every=1, seed=0,
             graph_store=store, capability_contract_hash="fam-x")
    assert len(list(store.iter_skills())) >= 1
    assert len(list(store.iter_mutations())) >= 1
    assert len(list(store.iter_evaluations())) >= 1
    node = next(store.iter_skills())
    assert node.capability_contract_hash == "fam-x"


def test_run_bcso_graph_skill_nodes_carry_parent_hashes_for_lineage_walk(tmp_path):
    store = GraphStore(tmp_path / "graph")
    evaluator = load_evaluator("synthetic")
    run_bcso(SEED_TEXT, evaluator, baseline="compression_only", checkpoint_every=1, seed=0, graph_store=store)
    nodes_with_parents = [n for n in store.iter_skills() if n.parent_hashes]
    assert nodes_with_parents, "at least one recorded child node should carry its parent's hash"
    child = nodes_with_parents[0]
    lineage = store.lineage(child.skill_hash)
    assert len(lineage) >= 2
    assert lineage[-1].skill_hash == child.skill_hash
    assert lineage[0].generation == 0


def test_run_bcso_graph_records_are_tagged_development_only_for_synthetic_backend(tmp_path):
    store = GraphStore(tmp_path / "graph")
    evaluator = load_evaluator("synthetic")
    run_bcso(SEED_TEXT, evaluator, baseline="compression_only", checkpoint_every=1, seed=0, graph_store=store)
    trainabilities = {record.trainability for record in store.iter_evaluations()}
    assert trainabilities == {"DEVELOPMENT_ONLY"}


def test_run_bcso_without_graph_store_records_nothing(tmp_path):
    store = GraphStore(tmp_path / "graph")
    evaluator = load_evaluator("synthetic")
    run_bcso(SEED_TEXT, evaluator, baseline="compression_only", checkpoint_every=1, seed=0)
    assert list(store.iter_skills()) == []


def test_make_graph_diagnose_falls_back_when_store_has_no_relevant_history(tmp_path):
    store = GraphStore(tmp_path / "graph")
    evaluator = load_evaluator("synthetic")
    diagnose = make_graph_diagnose(store)
    result = run_bcso(SEED_TEXT, evaluator, baseline="textual_gradient", checkpoint_every=1, seed=0,
                       diagnose_fn=diagnose)
    assert result["report"]["state"] == "released"


def test_run_bcso_writes_generation_lineage_and_final_layout(tmp_path):
    evaluator = load_evaluator("synthetic")
    run_dir = tmp_path / "run1"
    result = run_bcso(SEED_TEXT, evaluator, baseline="random_mutation", checkpoint_every=2, seed=0,
                       run_dir=run_dir)
    assert (run_dir / "gen_000" / "seed.md").exists()
    assert (run_dir / "final" / "SKILL.md").read_text(encoding="utf-8") == result["selected"].text
    benchmark = json.loads((run_dir / "final" / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["selected_id"] == result["report"]["selected_id"]
    assert (run_dir / "archive").exists()
    gen1_scores = json.loads((run_dir / "gen_001" / "scores.json").read_text(encoding="utf-8"))
    assert all("parent_ids" in row and "mutation_type" in row for row in gen1_scores)
