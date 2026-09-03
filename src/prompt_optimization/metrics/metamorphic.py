"""Metamorphic testing: controlled transformations of the same task.

Testing prompts independently misses a whole class of robustness failures.
This module names the transformation applied to a task and checks whether
behavior changed the way it should: a *preserving* transformation (paraphrase,
irrelevant-context injection, reordering, ...) should leave measured utility
roughly unchanged; an *activation-changing* transformation (explicit -> implicit
request, conflicting demand, distractor evidence, ...) should move it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .optimize import metamorphic_consistency


class TransformationKind(str, Enum):
    """Named controlled transformations applied to a reference task."""

    PARAPHRASE = "paraphrase"
    IRRELEVANT_CONTEXT = "irrelevant_context"
    ORDERING = "ordering"
    FORMAT = "format"
    POLITENESS = "politeness"
    VERBOSITY = "verbosity"
    NOISE = "noise"
    EXPLICIT_TO_IMPLICIT = "explicit_to_implicit"
    CONFLICTING_DEMAND = "conflicting_demand"
    DISTRACTOR_EVIDENCE = "distractor_evidence"


#: Transformations expected to leave utility approximately unchanged:
#: U(S, x) ~= U(S, f(x)).
PRESERVING = frozenset({
    TransformationKind.PARAPHRASE,
    TransformationKind.IRRELEVANT_CONTEXT,
    TransformationKind.ORDERING,
    TransformationKind.FORMAT,
    TransformationKind.POLITENESS,
    TransformationKind.VERBOSITY,
    TransformationKind.NOISE,
})

#: Transformations expected to change activation/behavior on purpose:
#: A(S, x) != A(S, g(x)).
ACTIVATION_CHANGING = frozenset({
    TransformationKind.EXPLICIT_TO_IMPLICIT,
    TransformationKind.CONFLICTING_DEMAND,
    TransformationKind.DISTRACTOR_EVIDENCE,
})


@dataclass(frozen=True)
class MetamorphicCase:
    """One transformed variant of a reference task."""

    reference_id: str
    kind: TransformationKind
    variant_id: str

    def __post_init__(self) -> None:
        if not self.reference_id.strip() or not self.variant_id.strip():
            raise ValueError("reference_id and variant_id must not be empty")
        if self.kind not in PRESERVING and self.kind not in ACTIVATION_CHANGING:
            raise ValueError(f"unclassified transformation kind: {self.kind!r}")


def metamorphic_report(
    cases: list[MetamorphicCase],
    reference_values: dict[str, float],
    variant_values: dict[str, float],
    *,
    tolerance: float = 0.05,
    activation_threshold: float = 0.5,
) -> dict:
    """Group cases by transformation kind and score preserving vs. activation-changing behavior.

    Preserving kinds report a consistency fraction via
    :func:`~prompt_optimization.metrics.optimize.metamorphic_consistency`.
    Activation-changing kinds report the fraction of variants whose value
    actually crossed ``activation_threshold`` relative to the reference —
    a case where the transformation failed to move behavior is a robustness
    finding, not a pass.
    """
    if not cases:
        raise ValueError("cases must not be empty")
    by_kind: dict[TransformationKind, list[MetamorphicCase]] = {}
    for case in cases:
        by_kind.setdefault(case.kind, []).append(case)

    report: dict[str, dict] = {}
    for kind, kind_cases in by_kind.items():
        ref_vals = [reference_values[c.reference_id] for c in kind_cases]
        var_vals = [variant_values[c.variant_id] for c in kind_cases]
        if kind in PRESERVING:
            reference_mean = sum(ref_vals) / len(ref_vals)
            report[kind.value] = {
                "type": "preserving",
                "consistency": metamorphic_consistency(reference_mean, var_vals, tolerance=tolerance),
                "n": len(kind_cases),
            }
        else:
            changed = sum(
                1
                for ref, var in zip(ref_vals, var_vals)
                if (ref >= activation_threshold) != (var >= activation_threshold)
            )
            report[kind.value] = {
                "type": "activation_changing",
                "change_rate": changed / len(kind_cases),
                "n": len(kind_cases),
            }
    return report
