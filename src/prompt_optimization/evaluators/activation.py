"""Activation quality: precision, recall, and asymmetric cost, kept off the utility score.

A skill either should or should not have engaged for a given task. Folding
that judgment into the same scalar as "how good was the output" hides two
very different failure modes: activating on the wrong task (a false positive,
often expensive because it triggers unnecessary work) and failing to activate
on the right one (a false negative, sometimes the more expensive failure for a
safety-response skill). This module keeps the two separate.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActivationLabel:
    """One task's ground-truth and observed activation decision."""

    task_id: str
    expected: bool
    observed: bool

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")


def activation_confusion(labels: list[ActivationLabel]) -> dict:
    """Raw TP/FP/FN/TN counts behind precision/recall."""
    if not labels:
        raise ValueError("labels must not be empty")
    tp = sum(1 for label in labels if label.expected and label.observed)
    fp = sum(1 for label in labels if not label.expected and label.observed)
    fn = sum(1 for label in labels if label.expected and not label.observed)
    tn = sum(1 for label in labels if not label.expected and not label.observed)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def activation_precision_recall(labels: list[ActivationLabel]) -> dict:
    """Precision, recall, and F1 for activation decisions — never collapsed by default.

    Different skill families have different asymmetric costs (a security
    skill's false negative is usually worse than its false positive; an
    architecture-review skill's false positive wastes an expensive analysis
    pass), so this reports precision and recall side by side rather than
    picking one universal threshold like ``activation >= .90``.
    """
    counts = activation_confusion(labels)
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall and (precision + recall) else 0.0
    return {**counts, "precision": precision, "recall": recall, "f1": f1}


def activation_cost(labels: list[ActivationLabel], *, cost_fp: float = 1.0, cost_fn: float = 1.0) -> dict:
    """Asymmetric activation cost ``C_A = c_FP * FP + c_FN * FN``.

    Set ``cost_fp``/``cost_fn`` per capability family instead of trusting a
    universal precision/recall threshold; the raw counts stay in the result so
    the weighting choice is auditable.
    """
    if cost_fp < 0 or cost_fn < 0:
        raise ValueError("cost_fp and cost_fn must be non-negative")
    counts = activation_confusion(labels)
    cost = cost_fp * counts["fp"] + cost_fn * counts["fn"]
    return {**counts, "cost_fp": cost_fp, "cost_fn": cost_fn, "cost": cost}
