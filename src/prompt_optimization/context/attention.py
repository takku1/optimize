"""Token-relation machinery: positional encoding and self-attention.

These give a prompt an ordered, contextual representation in which every token
pairs against every other token (causal: past can inform present, present never
informs past). The key/value tensors produced here are exactly what a KV-cache
holds, so ``ContextCache`` in ``context.cache`` can store and reuse them.
"""
from __future__ import annotations

import numpy as np


def _projection_weights(seed: int, d_model: int, num_heads: int, head_dim: int) -> tuple:
    """Deterministically draw ``(wq, wk, wv)`` projection-weight tensors.

    This is the single source of truth for how projection weights are generated,
    so that a from-scratch attention pass and a KV-cache reuse produce bit-for-bit
    identical results for the same input and seed.
    """
    rng = np.random.default_rng(seed)
    scale = (2.0 / d_model) ** 0.5
    wq = rng.normal(0.0, scale, (d_model, num_heads, head_dim))
    wk = rng.normal(0.0, scale, (d_model, num_heads, head_dim))
    wv = rng.normal(0.0, scale, (d_model, num_heads, head_dim))
    return wq, wk, wv


def sinusoidal_positional_encoding(max_len: int, d_model: int) -> np.ndarray:
    """Standard sinusoidal position table of shape ``(max_len, d_model)``.

    Uses the standard GPT-style alternating sin/cos schedule so that relative
    offsets are easy for attention to learn, and so longer contexts extrapolate
    without retraining.
    """
    if max_len < 1 or d_model < 1:
        raise ValueError("max_len and d_model must be positive")
    position = np.arange(max_len, dtype=float)[:, None]
    div_term = np.exp(np.arange(0, d_model, 2, dtype=float) * (-np.log(10000.0) / d_model))
    table = np.zeros((max_len, d_model), dtype=float)
    table[:, 0::2] = np.sin(position * div_term)
    if d_model > 1:
        table[:, 1::2] = np.cos(position * div_term[: table[:, 1::2].shape[1]])
    return table


def causal_mask(seq_len: int) -> np.ndarray:
    """Boolean ``(seq_len, seq_len)`` mask: True where token ``i`` may attend to ``j``.

    Causal (upper-right False) guards against a token attending to the future.
    """
    if seq_len < 1:
        raise ValueError("seq_len must be positive")
    return np.tril(np.ones((seq_len, seq_len), dtype=bool))


def scaled_dot_product_attention(
    query: np.ndarray,
    key: np.ndarray,
    value: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    temperature: float = 1.0,
) -> np.ndarray:
    """Batched scaled dot-product attention.

    All inputs are ``(batch, seq, head_dim)``. Returns weighted values
    ``(batch, seq, head_dim)``. ``mask`` is a broadcastable ``(seq, seq)``
    boolean (True = allowed). ``temperature`` scales the logits before softmax.
    """
    if query.ndim != 3 or key.ndim != 3 or value.ndim != 3:
        raise ValueError("query, key, value must all be 3-D (batch, seq, head_dim)")
    if query.shape[-1] != key.shape[-1]:
        raise ValueError("query and key must have the same head dimension")
    if key.shape[1] != value.shape[1]:
        raise ValueError("key and value must have the same sequence length")
    if temperature <= 0:
        raise ValueError("temperature must be positive")

    logits = query @ key.transpose(0, 2, 1)  # (batch, seq, seq)
    logits = logits / (float(query.shape[-1]) ** 0.5 * temperature)

    if mask is not None:
        if mask.shape != (query.shape[1], key.shape[1]):
            raise ValueError("mask must be (query_seq, key_seq) and match shapes")
        neg_inf = np.finfo(logits.dtype).min
        logits = np.where(mask[None, :, :], logits, neg_inf)

    weights = _softmax_2d(logits)
    return weights @ value


def multi_head_attention(
    query: np.ndarray,
    key: np.ndarray,
    value: np.ndarray,
    *,
    num_heads: int = 4,
    mask: np.ndarray | None = None,
    seed: int = 0,
    temperature: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Multi-head self-attention over ``(batch, seq, d_model)`` inputs.

    Returns ``(output, attention_weights, (q, k, v))``.
    ``q/k/v`` are ``(batch, heads, seq, head_dim)`` with learned projection
    matrices intialised deterministically; ``output`` is ``(batch, seq, d_model)``.
    ``attention_weights`` is ``(batch, heads, seq, seq)`` with causal masking
    applied when ``mask`` is provided.
    """
    batch, seq, d_model = query.shape
    if key.shape != (batch, seq, d_model) or value.shape != (batch, seq, d_model):
        raise ValueError("query, key, value must share shape (batch, seq, d_model)")
    if d_model % num_heads != 0:
        raise ValueError("d_model must be divisible by num_heads")

    head_dim = d_model // num_heads
    rng = np.random.default_rng(seed)
    scale = (2.0 / d_model) ** 0.5

    wq = rng.normal(0.0, scale, (d_model, num_heads, head_dim))
    wk = rng.normal(0.0, scale, (d_model, num_heads, head_dim))
    wv = rng.normal(0.0, scale, (d_model, num_heads, head_dim))

    q = np.einsum("bsd,dhn->bhsn", query, wq)
    k = np.einsum("bsd,dhn->bhsn", key, wk)
    v = np.einsum("bsd,dhn->bhsn", value, wv)

    # (batch, heads, seq, seq)
    scores = q @ k.transpose(0, 1, 3, 2) / (head_dim**0.5 * temperature)
    if mask is not None:
        if mask.shape != (seq, seq):
            raise ValueError("mask must be (seq, seq)")
        neg_inf = np.finfo(scores.dtype).min
        scores = np.where(mask[None, None, :, :], scores, neg_inf)

    attn = _softmax_2d(scores)  # softmax over last dim
    out = attn @ v  # (batch, heads, seq, head_dim)
    out = out.transpose(0, 2, 1, 3).reshape(batch, seq, d_model)

    return out, attn, (q, k, v)


def _softmax_2d(x: np.ndarray) -> np.ndarray:
    """Numeric-stable softmax over the last axis of any-shaped array."""
    x = x - np.max(x, axis=-1, keepdims=True)
    e = np.exp(x)
    return e / np.sum(e, axis=-1, keepdims=True)
