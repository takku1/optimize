"""Directional projection of state/embedding changes onto a target direction."""
from __future__ import annotations

import numpy as np


def directional_projection(delta, target_direction) -> float:
    """Project an observed state/embedding change onto a target direction."""
    delta, direction = np.asarray(delta, dtype=float), np.asarray(target_direction, dtype=float)
    if delta.shape != direction.shape or delta.ndim != 1:
        raise ValueError("delta and target_direction must be same-shaped vectors")
    norm = np.linalg.norm(direction)
    if norm == 0:
        raise ValueError("target_direction must be non-zero")
    return float(np.dot(delta, direction / norm))
