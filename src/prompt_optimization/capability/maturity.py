"""Certification-style maturity tiers, in place of a single PASS/FAIL score.

BCSO-Bench should never claim to have found "the mathematically perfect
prompt" — that's unknowable in the discrete language space. Instead it
reports which preregistered floor of evidence a candidate currently clears:
EXPERIMENTAL -> QUALIFIED -> MATURE -> SATURATED -> PORTABLE -> REFERENCE,
each tier a strictly stronger, cumulative gate than the last.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class MaturityTier(str, Enum):
    EXPERIMENTAL = "experimental"
    QUALIFIED = "qualified"
    MATURE = "mature"
    SATURATED = "saturated"
    PORTABLE = "portable"
    REFERENCE = "reference"


#: Default gate thresholds. Override per capability family via ``thresholds``.
DEFAULT_THRESHOLDS = {
    "utility_min": 0.7,
    "activation_min": 0.7,
    "robustness_min": 0.6,
    "generalization_min": 0.6,
    "optimization_resistance_max": 0.01,
    "cross_model_transfer_min": 0.6,
}


def classify_maturity(metrics: dict[str, Any], *, thresholds: dict[str, float] | None = None) -> dict:
    """Read a metrics dict and return the highest maturity tier it clears, and why it stopped.

    Expected (all optional; a missing key fails that tier's gate rather than
    raising) ``metrics`` keys: ``utility``, ``activation_precision``,
    ``activation_recall``, ``robustness``, ``generalization_iid``,
    ``generalization_ood``, ``in_reference_envelope`` (bool),
    ``optimization_resistance`` (Δ_opt — lower is better, meaning the
    optimizer found less residual gain), ``cross_model_transfer``,
    ``independently_reproduced`` (bool).
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def get(key: str, default: float = float("-inf")) -> float:
        return float(metrics.get(key, default))

    if not (get("utility") >= t["utility_min"]
            and get("activation_precision") >= t["activation_min"]
            and get("activation_recall") >= t["activation_min"]):
        return {"tier": MaturityTier.EXPERIMENTAL.value,
                "reasons": ["did not clear the utility/activation floors"]}

    if not (get("robustness") >= t["robustness_min"]
            and get("generalization_iid") >= t["generalization_min"]
            and get("generalization_ood") >= t["generalization_min"]
            and bool(metrics.get("in_reference_envelope", False))):
        return {"tier": MaturityTier.QUALIFIED.value,
                "reasons": ["did not clear robustness/generalization/reference-envelope gates"]}

    if not (get("optimization_resistance", float("inf")) <= t["optimization_resistance_max"]):
        return {"tier": MaturityTier.MATURE.value,
                "reasons": ["optimizer still finds material improvement (not saturated)"]}

    if not (get("cross_model_transfer") >= t["cross_model_transfer_min"]):
        return {"tier": MaturityTier.SATURATED.value,
                "reasons": ["cross-model transfer not measured or below floor"]}

    if not bool(metrics.get("independently_reproduced", False)):
        return {"tier": MaturityTier.PORTABLE.value,
                "reasons": ["not yet independently reproduced"]}

    return {"tier": MaturityTier.REFERENCE.value, "reasons": []}
