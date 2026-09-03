"""Attractor-basin simulation and evaluation.

The model is deliberately a deterministic research scaffold: we measure how a
prompt's latent state lands relative to named behavioral "attractors". It is
not evidence about any production LLM.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Attractor:
    name: str
    center: np.ndarray


@dataclass(frozen=True)
class Prompt:
    text: str
    tokens: int
    embedding_bias: np.ndarray
    nonlinearity: float = 0.0

    def __post_init__(self) -> None:
        if self.tokens < 0:
            raise ValueError("tokens must be non-negative")
        if self.nonlinearity < 0:
            raise ValueError("nonlinearity must be non-negative")


@dataclass(frozen=True)
class ObjectiveWeights:
    """Optional reporting weights; Pareto/rate-distortion remain primary."""

    off_target: float = 0.5
    variance: float = 0.3

    def __post_init__(self) -> None:
        if self.off_target < 0 or self.variance < 0:
            raise ValueError("objective weights must be non-negative")


def make_attractors(dim: int = 32) -> list[Attractor]:
    centers = {
        "VERIFY_PRIOR": (4.0, 0.0),
        "CREATIVE": (-3.0, 3.0),
        "CAUTIOUS": (1.0, -4.0),
        "AUTHORITATIVE": (3.5, 2.5),
        "TRUSTING": (-4.0, -1.5),
    }
    return [Attractor(name, np.pad(np.asarray(x), (0, dim - 2))) for name, x in centers.items()]


def final_state(prompt: Prompt, baseline: np.ndarray) -> np.ndarray:
    raw = prompt.embedding_bias.astype(float, copy=True)
    if raw.shape != baseline.shape:
        raise ValueError("embedding_bias and baseline must have the same shape")
    resonance = 1.0 + prompt.nonlinearity * np.log1p(np.linalg.norm(raw))
    efficiency = 1.0 / (1.0 + 0.15 * max(prompt.tokens - 2, 0))
    return baseline + raw * resonance * efficiency


def _centers(attractors: list[Attractor]) -> np.ndarray:
    return np.stack([a.center for a in attractors])  # (K, D)


def _cosine_distances(states, centers) -> np.ndarray:
    """Cosine distance (1 - cos) from each state to each center.

    ``states`` is ``(B, D)`` and ``centers`` is ``(K, D)``; returns ``(B, K)``.
    Cosine is the natural metric for the unit-normalized context vectors used
    here; Euclidean distance against large-norm centers would compress every
    near-unit vector into a narrow band and destroy discrimination. Zero-norm
    states have no direction, so they get distance 1 to every center (neutral).
    """
    states = np.asarray(states, dtype=float)
    centers = np.asarray(centers, dtype=float)
    s_norm = np.linalg.norm(states, axis=-1, keepdims=True)       # (B, 1)
    c_norm = np.linalg.norm(centers, axis=-1, keepdims=True).T    # (1, K)
    with np.errstate(divide="ignore", invalid="ignore"):
        cos = (states @ centers.T) / (s_norm * c_norm)            # (B, K)
    cos = np.where(np.isfinite(cos), np.clip(cos, -1.0, 1.0), 0.0)
    return 1.0 - cos


def _softmax_distances(distances: np.ndarray, temperature: float) -> np.ndarray:
    """Normalised softmax over distances along the last axis (max-subtracted)."""
    logits = -distances / temperature
    weights = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
    return weights / np.sum(weights, axis=-1, keepdims=True)


def basin_probabilities(state, attractors: list[Attractor], temperature: float = 10.0) -> np.ndarray:
    if not attractors:
        raise ValueError("attractors must not be empty")
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    centers = _centers(attractors)
    state = np.asarray(state, dtype=float).reshape(1, -1)
    distances = _cosine_distances(state, centers)
    return _softmax_distances(distances, temperature)[0]


def basin_probabilities_batch(states, attractors: list[Attractor], temperature: float = 10.0) -> np.ndarray:
    """Vectorized ``basin_probabilities`` over a ``(B, D)`` tensor of states."""
    if not attractors:
        raise ValueError("attractors must not be empty")
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    states = np.asarray(states, dtype=float)
    if states.ndim != 2:
        raise ValueError("states must be a (B, D) tensor")
    centers = _centers(attractors)                     # (K, D)
    distances = _cosine_distances(states, centers)     # (B, K)
    return _softmax_distances(distances, temperature)


def evaluate(
    prompt: Prompt,
    target: Attractor,
    baseline: np.ndarray,
    attractors: list[Attractor],
    seed: int = 0,
    samples: int = 64,
    weights: ObjectiveWeights | None = None,
) -> dict:
    from .uncertainty import wasserstein_1d

    if samples < 2:
        raise ValueError("samples must be >= 2")
    weights = weights or ObjectiveWeights()
    state = final_state(prompt, baseline)
    probs = basin_probabilities(state, attractors)
    target_idx = next(i for i, a in enumerate(attractors) if a.name == target.name)
    rng = np.random.default_rng(seed)
    noisy_states = state + rng.normal(0, 0.15, (samples, state.size))
    baseline_states = baseline + rng.normal(0, 0.15, (samples, baseline.size))
    noisy = basin_probabilities_batch(noisy_states, attractors)[:, target_idx]
    baseline_target = basin_probabilities_batch(baseline_states, attractors)[:, target_idx]

    activation = float(probs[target_idx])
    reliability = float(noisy.mean())
    variance = float(noisy.std())
    competing = np.delete(probs, target_idx)
    off_target = float(competing.max()) if competing.size else 0.0

    target_center = target.center.astype(float)
    s = np.asarray(state, dtype=float)
    s_norm = np.linalg.norm(s)
    t_norm = np.linalg.norm(target_center)
    cosine = float(np.dot(s, target_center) / (s_norm * t_norm)) if s_norm and t_norm else 0.0

    return {
        "prompt": prompt.text,
        "tokens": prompt.tokens,
        "target_activation": activation,
        "similarity": cosine,
        "reliability": reliability,
        "distortion": 1.0 - reliability,
        "off_target": off_target,
        "variance_penalty": variance,
        "distribution_shift": wasserstein_1d(noisy, baseline_target),
        "instruction_density": activation * reliability / max(prompt.tokens, 1),
        "score": activation * reliability
        - weights.off_target * off_target
        - weights.variance * variance,
        "samples": noisy.tolist(),
    }
