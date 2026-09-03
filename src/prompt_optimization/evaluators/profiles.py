"""Per-capability-family rubric weight profiles.

``u(y, x) = w^T Omega(y, x)`` collapses task success, correctness, invariant
adherence, and calibration into one scalar. A single universal ``w`` is not
defensible across skill families: an architecture-review skill should weight
correctness and invariants heavily, a formatter should weight correctness and
invariant adherence almost exclusively, a creative workflow skill should
weight parsimony/calibration less. This module keeps a small registry of
named weight vectors and always reports the component scores next to the
aggregate so the weighting choice stays visible, not hidden inside one number.
"""
from __future__ import annotations

#: Ω attribute order shared by every profile: task success, correctness,
#: invariant adherence, parsimony/calibration.
OMEGA_KEYS = ("task_success", "correctness", "invariant_adherence", "calibration")

#: Default profiles, keyed by capability family. Weights sum to 1.0.
DEFAULT_PROFILES: dict[str, dict[str, float]] = {
    "reasoning": {"task_success": 0.30, "correctness": 0.35, "invariant_adherence": 0.20, "calibration": 0.15},
    "architecture": {"task_success": 0.25, "correctness": 0.30, "invariant_adherence": 0.30, "calibration": 0.15},
    "formatting": {"task_success": 0.15, "correctness": 0.40, "invariant_adherence": 0.40, "calibration": 0.05},
    "creative": {"task_success": 0.40, "correctness": 0.20, "invariant_adherence": 0.20, "calibration": 0.20},
    "tool_orchestration": {"task_success": 0.30, "correctness": 0.25, "invariant_adherence": 0.35, "calibration": 0.10},
    "retrieval": {"task_success": 0.30, "correctness": 0.35, "invariant_adherence": 0.25, "calibration": 0.10},
    "workflow": {"task_success": 0.30, "correctness": 0.25, "invariant_adherence": 0.30, "calibration": 0.15},
}

#: Fallback used for an undeclared or unknown capability family.
UNIFORM_PROFILE = {key: 1.0 / len(OMEGA_KEYS) for key in OMEGA_KEYS}


def _validate_profile(weights: dict[str, float]) -> None:
    if set(weights) != set(OMEGA_KEYS):
        raise ValueError(f"profile must have exactly the keys {OMEGA_KEYS}, got {sorted(weights)}")
    if any(value < 0 for value in weights.values()):
        raise ValueError("profile weights must be non-negative")
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"profile weights must sum to 1.0, got {total}")


for _weights in DEFAULT_PROFILES.values():
    _validate_profile(_weights)


def get_profile(capability_family: str, *, profiles: dict[str, dict[str, float]] | None = None) -> dict[str, float]:
    """Look up the rubric weight vector for a capability family.

    Falls back to :data:`UNIFORM_PROFILE` for a family with no declared
    profile rather than raising — an undeclared family should read as "no
    editorial weighting applied yet," not crash the report.
    """
    registry = profiles if profiles is not None else DEFAULT_PROFILES
    return dict(registry.get(capability_family, UNIFORM_PROFILE))


def project_utility(omega: dict[str, float], capability_family: str, *,
                     profiles: dict[str, dict[str, float]] | None = None) -> dict:
    """Project a multi-attribute Ω score to scalar utility using a family's rubric profile.

    Returns both the aggregate ``utility`` and the untouched ``components``
    and ``weights`` so the aggregate is always auditable against its inputs.
    """
    if set(omega) != set(OMEGA_KEYS):
        raise ValueError(f"omega must have exactly the keys {OMEGA_KEYS}, got {sorted(omega)}")
    weights = get_profile(capability_family, profiles=profiles)
    utility = sum(weights[key] * float(omega[key]) for key in OMEGA_KEYS)
    return {
        "utility": utility,
        "components": dict(omega),
        "weights": weights,
        "capability_family": capability_family,
    }
