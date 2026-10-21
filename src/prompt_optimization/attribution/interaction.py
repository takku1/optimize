"""Second-order interaction and deletion effects between prompt components."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def interaction_effect(value_fn: Callable[[Any], float], i: int, j: int, context=()) -> float:
    """Second-order inclusion-exclusion synergy/interference effect."""
    if i == j or i < 0 or j < 0:
        raise ValueError("i and j must be distinct non-negative indices")
    base = frozenset(context) - {i, j}
    return float(value_fn(base | {i, j}) - value_fn(base | {i}) - value_fn(base | {j}) + value_fn(base))


def causal_deletion_effect(full_value: float, deleted_value: float) -> float:
    """Positive value means deletion reduced the measured target behavior."""
    return float(full_value - deleted_value)
