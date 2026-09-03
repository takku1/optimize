import json

import pytest

from prompt_optimization.optimizers import (
    OptimizationSpec,
    apply_revision,
    combine_structural_and_behavioral,
    discover_optimization_spec,
    is_activated,
    score_from_spec,
)


def _spec(**overrides):
    raw = {
        "id": "test-v1",
        "activation": {"required_all": ["# Skill"]},
        "revision": {
            "metadata": {"version": "2.0"},
            "sections": [{
                "heading": "## Contract", "aliases": ["## Advice"],
                "after": "# Skill", "content": "Do A. Verify B.",
            }],
        },
        "checks": [
            {"id": "contract", "kind": "contains_all", "values": ["Do A", "Verify B"],
             "scope": {"section": "## Contract"}, "hard": True, "weight": 2},
            {"id": "bounded", "kind": "max_tokens", "value": 30, "hard": False, "weight": 1},
        ],
        "objective": {"structural_weight": .2, "behavioral_weight": .8},
    }
    raw.update(overrides)
    return OptimizationSpec.from_dict(raw)


def test_generic_activation_revision_and_weighted_scoring():
    source = '---\nmetadata:\n  version: "1.0"\n---\n\n# Skill\n\n## Advice\n\nTry things.\n'
    spec = _spec()

    assert is_activated(spec, source, source_path="skill.md")
    candidate = apply_revision(source, spec)
    result = score_from_spec(candidate, spec)

    assert 'version: "2.0"' in candidate
    assert "## Advice" not in candidate
    assert candidate.count("## Contract") == 1
    assert "<!-- prompt-opt:contract:start -->" in candidate
    assert apply_revision(candidate, spec) == candidate
    assert result["utility"] == 1
    assert result["hard_invariants_passed"] is True
    assert result["evidence_tier"] == "structural_proxy"


def test_document_reconstruction_is_data_not_core_policy():
    spec = _spec(revision={"document": "# Rebuilt\n\nOperational contract."})
    assert apply_revision("# Skill\n\nVague.", spec) == "# Rebuilt\n\nOperational contract.\n"


def test_behavioral_evidence_is_conjunctive_and_dominantly_weighted():
    spec = _spec()
    structural = {"utility": 1, "tokens": 10, "hard_invariants_passed": True}
    behavioral = {"utility": .5, "tokens": 50, "hard_invariants_passed": False}

    result = combine_structural_and_behavioral(structural, behavioral, spec)

    assert result["utility"] == pytest.approx(.6)
    assert result["hard_invariants_passed"] is False
    assert result["evidence_tier"] == "behavioral_execution"


def test_adjacent_spec_discovery_is_local_and_unambiguous(tmp_path):
    seed = tmp_path / "skill.md"
    seed.write_text("x", encoding="utf-8")
    adjacent = tmp_path / "optimization.json"
    adjacent.write_text(json.dumps({}), encoding="utf-8")
    assert discover_optimization_spec(seed) == adjacent

    named = tmp_path / "skill.optimization.json"
    named.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(ValueError, match="multiple adjacent"):
        discover_optimization_spec(seed)


def test_invalid_check_kinds_are_rejected():
    with pytest.raises(ValueError, match="unsupported check kind"):
        _spec(checks=[{"id": "magic", "kind": "understands_metaphor"}])


def test_spec_assets_resolve_locally_and_cannot_escape(tmp_path):
    from prompt_optimization.optimizers import load_optimization_spec

    (tmp_path / "candidate.md").write_text("# Candidate", encoding="utf-8")
    raw = {
        "id": "asset-v1", "activation": {},
        "revision": {"document_file": "candidate.md"},
        "checks": [{"id": "heading", "kind": "contains", "value": "# Candidate"}],
    }
    path = tmp_path / "optimization.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert apply_revision("old", load_optimization_spec(path)) == "# Candidate\n"

    raw["revision"] = {"document_file": "../outside.md"}
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes spec directory"):
        load_optimization_spec(path)
