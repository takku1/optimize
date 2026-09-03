"""Model-agnostic hidden-state representation contracts and diagnostics.

This module never loads a model. An adapter may provide tensors from a local
or remote target system; all comparison functions here are deterministic and
do not certify intent or behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

import numpy as np


class RepresentationEncoder(Protocol):
    """Optional system-under-test adapter returning hidden states by layer."""

    def encode(self, text: str) -> "HiddenRepresentation": ...


@dataclass(frozen=True)
class HiddenRepresentation:
    """Token-by-hidden-size tensors, keyed by model layer identifier."""

    layers: Mapping[str, np.ndarray]
    model_id: str = ""

    def __post_init__(self) -> None:
        if not self.layers:
            raise ValueError("layers must not be empty")
        for name, tensor in self.layers.items():
            if np.asarray(tensor).ndim != 2:
                raise ValueError(f"layer {name!r} must have shape (tokens, hidden_size)")

    def pooled(self, layer: str, *, method: str = "mean") -> np.ndarray:
        tensor = np.asarray(self.layers[layer], dtype=float)
        if method == "mean":
            vector = tensor.mean(axis=0)
        elif method == "last":
            vector = tensor[-1]
        else:
            raise ValueError("method must be mean or last")
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    """Return cosine similarity, treating two zero vectors as identical."""
    left, right = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if left.shape != right.shape:
        raise ValueError("vectors must have equal shapes")
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    return 1.0 if denominator == 0 and np.array_equal(left, right) else float(np.dot(left, right) / (denominator or 1.0))


def representation_drift(parent: HiddenRepresentation, child: HiddenRepresentation,
                         *, layer: str, pooling: str = "mean") -> float:
    """Compute 1-cosine drift; this is diagnostic, not a semantic distance."""
    return 1.0 - cosine_similarity(parent.pooled(layer, method=pooling), child.pooled(layer, method=pooling))
