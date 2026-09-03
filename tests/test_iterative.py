import pytest

from prompt_optimization.search import IterativeConfig, describe_transformation, internal_propose, optimize_iteratively
from prompt_optimization.search import lexical_variants, operationalize


def test_internal_proposer_and_transformation_metadata_are_deterministic():
    text = "A  sentence.\n\nA sentence."
    candidate = internal_propose(text, {"proposal_mode": "compression"}, 1)
    assert candidate == "A  sentence."
    record = describe_transformation(text, candidate, "compression")
    assert record.family == "compression"
    assert record.token_delta < 0


def test_explicit_lexical_and_operational_variants_are_auditable():
    assert lexical_variants("Use good boundaries.", {"good": "authoritative"}) == [
        "Use authoritative boundaries."
    ]
    assert operationalize("Use good boundaries.", {"good boundaries": "one authoritative owner per state"}) == \
        "Use one authoritative owner per state."


def test_internal_proposer_uses_run_terminology_configuration():
    result = internal_propose(
        "Use good boundaries.",
        {"proposal_mode": "lexical", "lexical_replacements": {"good": "authoritative"}},
        1,
    )
    assert result == "Use authoritative boundaries."


def test_iterative_optimizer_accepts_only_program_scored_improvements():
    proposals = iter(["seed improved", "seed improved improved", "worse", "worse"])

    def score(text):
        return {"utility": text.count("improved"), "tokens": len(text.split()),
                "hard_invariants_passed": "worse" not in text}

    result = optimize_iteratively(
        "seed", score, lambda current, feedback, turn: next(proposals),
        config=IterativeConfig(max_turns=4, patience=2),
    )
    assert result.selected.text == "seed improved improved"
    assert result.stop_reason == "patience_exhausted"


def test_iterative_optimizer_stops_after_max_turns():
    result = optimize_iteratively(
        "seed", lambda text: {"utility": 1, "tokens": 1, "hard_invariants_passed": True},
        lambda current, feedback, turn: current,
        config=IterativeConfig(max_turns=2, patience=9),
    )
    assert result.stop_reason == "max_turns"
    assert len(result.turns) == 2


def test_iterative_config_rejects_empty_proposal_modes():
    with pytest.raises(ValueError, match="proposal_modes"):
        IterativeConfig(proposal_modes=())
