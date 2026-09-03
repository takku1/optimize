"""Tests for activation precision/recall/cost, kept separate from utility."""
import pytest

from prompt_optimization.evaluators import ActivationLabel, activation_cost, activation_precision_recall


def _labels():
    return [
        ActivationLabel("t1", expected=True, observed=True),
        ActivationLabel("t2", expected=True, observed=False),
        ActivationLabel("t3", expected=False, observed=True),
        ActivationLabel("t4", expected=False, observed=False),
    ]


def test_precision_recall_match_hand_computed_confusion_matrix():
    result = activation_precision_recall(_labels())
    assert result == {
        "tp": 1, "fp": 1, "fn": 1, "tn": 1,
        "precision": 0.5, "recall": 0.5, "f1": 0.5,
    }


def test_perfect_activation_has_precision_and_recall_of_one():
    labels = [ActivationLabel(f"t{i}", expected=True, observed=True) for i in range(3)]
    result = activation_precision_recall(labels)
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0


def test_activation_cost_weights_false_negatives_separately():
    labels = _labels()
    cost = activation_cost(labels, cost_fp=1.0, cost_fn=5.0)
    assert cost["cost"] == pytest.approx(1.0 * 1 + 5.0 * 1)


def test_activation_cost_rejects_negative_weights():
    with pytest.raises(ValueError):
        activation_cost(_labels(), cost_fp=-1.0)


def test_activation_label_rejects_empty_task_id():
    with pytest.raises(ValueError):
        ActivationLabel("", expected=True, observed=True)


def test_activation_precision_recall_requires_labels():
    with pytest.raises(ValueError):
        activation_precision_recall([])
