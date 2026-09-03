"""Cooperative-game Shapley attribution for prompt components."""
from __future__ import annotations

from itertools import permutations

import numpy as np


def shapley_values(n_players: int, value_fn, *, samples: int | None = None, seed: int = 0) -> np.ndarray:
    """Estimate cooperative-game Shapley attribution for prompt components."""
    if n_players < 1:
        raise ValueError("n_players must be positive")
    if samples is not None and samples < 1:
        raise ValueError("samples must be positive when provided")
    if samples is None and n_players <= 10:
        orders = list(permutations(range(n_players)))
    else:
        rng = np.random.default_rng(seed)
        orders = [tuple(rng.permutation(n_players).tolist()) for _ in range(samples or 2048)]
    totals = np.zeros(n_players, dtype=float)
    cache: dict = {}

    def value(coalition):
        coalition = frozenset(coalition)
        if coalition not in cache:
            cache[coalition] = float(value_fn(coalition))
        return cache[coalition]

    for order in orders:
        coalition = frozenset()
        previous = value(coalition)
        for player in order:
            coalition = coalition | {player}
            current = value(coalition)
            totals[player] += current - previous
            previous = current
    return totals / len(orders)
