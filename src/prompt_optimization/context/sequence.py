"""Ordered token sequences and attention-based context pooling.

A prompt is turned into a ``TokenSequence`` (position-encoded token embeddings).
Self-attention reduces the sequence to a single normalized contextual embedding,
so the analysis can reason about how *sequences* of tokens land in the behavior
landscape rather than a single summed vector.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from .attention import _projection_weights, sinusoidal_positional_encoding

if TYPE_CHECKING:
    from .cache import ContextCache


def tokenize(text: str) -> list[str]:
    """Deterministic tokenizer-free split; production may inject a real one."""
    return re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)


@dataclass(frozen=True)
class TokenSequence:
    """An ordered list of per-token embedding vectors for one prompt.

    ``embeddings`` has shape ``(n_tokens, d_model)``. ``positions`` gives the
    absolute position of each token, used to look up the sinusoidal encoding.
    """

    tokens: tuple[str, ...]
    embeddings: np.ndarray          # (n, d_model)
    positions: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.tokens:
            raise ValueError("tokens must not be empty")
        n_tokens = len(self.tokens)
        if self.embeddings.ndim != 2 or self.embeddings.shape[0] != n_tokens:
            raise ValueError("embeddings must have shape (n_tokens, d_model)")
        if self.positions and len(self.positions) != n_tokens:
            raise ValueError("positions must match the number of tokens")
        object.__setattr__(self, "positions", tuple(self.positions) or tuple(range(n_tokens)))

    @property
    def d_model(self) -> int:
        return self.embeddings.shape[1]


def _stable_hash(s: str) -> int:
    """Deterministic FNV-1a hash (stable across runs and hash-seed values)."""
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


@lru_cache(maxsize=8192)
def _token_embedding(token: str, d_model: int) -> np.ndarray:
    """Dense content fingerprint for a token.

    Each coordinate carries the sign of a stable hash of ``(coord, token)``, so
    the vector is deterministic and *content-dependent* (unlike seeded random
    vectors, which put every document at roughly the same distance from every
    attractor). Averaging these across a document yields a direction that varies
    with what the file actually contains.
    """
    vec = np.zeros(d_model, dtype=float)
    for d in range(d_model):
        h = _stable_hash(f"{d}:{token}")
        vec[d] = 1.0 if (h & 1) else -1.0
    norm = np.linalg.norm(vec)
    vec = vec / norm if norm > 0 else vec
    vec.setflags(write=False)
    return vec


def default_sequence(text: str, d_model: int = 16, seed: int = 0) -> TokenSequence:
    """Build a token-sequence with deterministic, content-stable embeddings.

    ``d_model`` should be divisible by the head count. Embeddings are a fast,
    model-free function of each token's character content (not a learned model),
    so the same prompt always yields the same tensor and different documents
    yield measurably different pooled vectors.
    """
    if d_model < 1:
        raise ValueError("d_model must be positive")
    tokens = tokenize(text) or [""]
    rows = [_token_embedding(token, d_model) for token in tokens]
    embeddings = np.stack(rows)
    return TokenSequence(tuple(tokens), embeddings.astype(float))


def _attend(x: np.ndarray, wq: np.ndarray, k: np.ndarray, v: np.ndarray, mask=None) -> np.ndarray:
    """Single-head scaled dot-product attention reduce over ``(1, n, d)`` input."""
    d_head = wq.shape[-1]
    q = np.einsum("sd,dhn->hsn", x, wq)[None]
    scores = q @ k.transpose(0, 1, 3, 2) / (d_head**0.5)
    if mask is not None:
        neg_inf = np.finfo(scores.dtype).min
        scores = np.where(mask[None, None, :, :], scores, neg_inf)
    attn = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
    attn = attn / np.sum(attn, axis=-1, keepdims=True)
    out = (attn @ v).transpose(0, 2, 1, 3).reshape(1, x.shape[0], -1)
    return out


def contextual_vector(seq: TokenSequence, cache: "ContextCache | None" = None, *, mask=None) -> np.ndarray:
    """Pool ``seq`` into a single normalized ``(d_model,)`` context vector.

    Uses an *encoder-style* full (or supplied) ``mask`` by default so every
    token pairs against every other token (the ``n``-token relation the analysis
    wants). When a cache is supplied the key/value tensors are shared; only the
    query pass runs here.
    """
    from .cache import ContextCache  # deferred to avoid an import cycle

    d_model = seq.d_model
    heads = cache.num_heads if cache else 4
    if d_model % heads != 0:
        raise ValueError("d_model must be divisible by the head count")
    d_head = d_model // heads

    positions = np.asarray(seq.positions, dtype=int)
    pos_enc = sinusoidal_positional_encoding(max(positions.max() + 1, 1), d_model)
    x = seq.embeddings + pos_enc[positions]

    use_cache = isinstance(cache, ContextCache)
    seed = cache.seed if use_cache else 0

    # Single draw order shared with ContextCache.keys_values, so a cached pass
    # and a from-scratch pass return bit-identical results for the same seed.
    wq = _projection_weights(seed, d_model, heads, d_head)[0]

    if use_cache:
        k, v = cache.keys_values(seq)
    else:
        _, wk, wv = _projection_weights(seed, d_model, heads, d_head)
        k = np.einsum("sd,dhn->hsn", x, wk)[None]
        v = np.einsum("sd,dhn->hsn", x, wv)[None]

    out = _attend(x, wq, k, v, mask)
    mean = out.mean(axis=1)[0]
    return mean / (float(np.linalg.norm(mean)) + 1e-12)


def evaluate_sequence(
    seq: TokenSequence,
    target,
    attractors,
    cache: "ContextCache | None" = None,
    *,
    baseline: np.ndarray | None = None,
    seed: int = 0,
    samples: int = 64,
) -> dict:
    """Score a token-sequence against the attractor basin of a target.

    Reduces the sequence to a normalized contextual vector (via the
    attention/KV-cache path), then runs the standard behavioral metrics over it.
    Returns the same metric dict as ``evaluate`` plus the context vector.
    """
    from ..metrics.basin import Prompt, evaluate

    d_model = seq.d_model
    baseline = np.zeros(d_model) if baseline is None else np.asarray(baseline, dtype=float)
    context = contextual_vector(seq, cache=cache)
    text = seq.tokens[0] if len(seq.tokens) == 1 else " ".join(seq.tokens)
    prompt = Prompt(text, len(seq.tokens), context.astype(float))
    result = evaluate(prompt, target, baseline, attractors, seed=seed, samples=samples)
    result["context_vector"] = context
    return result
