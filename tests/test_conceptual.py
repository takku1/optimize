import pytest

from prompt_optimization.conceptual import ConceptualOperationalization, score_operationalization


def test_conceptual_operationalization_requires_formalism_mapping_and_falsifier():
    value = ConceptualOperationalization.from_dict({
        "source_concept": "butterfly effect through a prompt",
        "inferred_mechanism": "small edits can propagate across representation and behavior",
        "established_formalisms": ["sensitivity analysis", "perturbation propagation"],
        "variable_mapping": {"edit": "input perturbation", "output change": "behavioral distance"},
        "intervention": "apply controlled edits at increasing semantic scales",
        "observable": "paired representation and task-utility deltas",
        "falsifier": "effects do not exceed matched random edits on held-out tasks",
        "epistemic_status": "adapted_analogy",
        "caveats": ["not evidence of classical chaos"],
    })

    result = score_operationalization(value)

    assert result["hard_invariants_passed"] is True
    assert result["semantic_correctness_requires_review"] is True


def test_conceptual_operationalization_rejects_fake_formalization_without_variables():
    with pytest.raises(ValueError, match="variable_mapping"):
        ConceptualOperationalization(
            "laser", "semantic change", ("optics",), {}, "edit", "measure", "null",
            "novel_hypothesis",
        )
