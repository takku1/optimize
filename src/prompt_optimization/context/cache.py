"""A key/value cache (KV-cache analog) for token-context analysis.

Real transformers compute each token's key and value projections once and reuse
them across decoding steps. This mirrors that: a ``ContextCache`` computes the
position-encoded key/value tensors for a ``TokenSequence`` once and memoizes
them, so repeated evaluations that need the same sequence skip the projection
work entirely. A ``misses`` counter records how many sequences were computed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .attention import _projection_weights, sinusoidal_positional_encoding


@dataclass
class ContextCache:
    num_heads: int = 4
    seed: int = 0
    _cache: dict = field(default_factory=dict, repr=False, compare=False)
    misses: int = field(default=0, repr=False, compare=False)

    def _rng_weights(self, d_model: int, d_head: int) -> tuple[np.ndarray, np.ndarray]:
        _, wk, wv = _projection_weights(self.seed, d_model, self.num_heads, d_head)
        return wk, wv

    def keys_values(self, seq) -> tuple[np.ndarray, np.ndarray]:
        """Return the position-encoded ``(k, v)`` tensors for ``seq``.

        Both have shape ``(1, heads, n, d_head)`` and are computed once and
        memoized keyed on the token-embedding bytes.
        """
        # Position is part of the input representation. Keying on embedding
        # bytes alone incorrectly reused projections for equal tokens placed at
        # different absolute positions. Shape/dtype also prevent ambiguous byte
        # layouts from aliasing one another.
        cache_key = (
            seq.embeddings.shape,
            seq.embeddings.dtype.str,
            seq.embeddings.tobytes(),
            tuple(seq.positions),
        )
        if cache_key in self._cache:
            return self._cache[cache_key]
        self.misses += 1

        d_model = seq.d_model
        if d_model % self.num_heads != 0:
            raise ValueError("d_model must be divisible by num_heads")
        d_head = d_model // self.num_heads
        positions = np.asarray(seq.positions, dtype=int)
        pos_enc = sinusoidal_positional_encoding(max(positions.max() + 1, 1), d_model)
        x = seq.embeddings + pos_enc[positions]

        wk, wv = self._rng_weights(d_model, d_head)
        k = np.einsum("sd,dhn->hsn", x, wk)[None]  # (1, heads, n, d_head)
        v = np.einsum("sd,dhn->hsn", x, wv)[None]

        self._cache[cache_key] = (k, v)
        return k, v
