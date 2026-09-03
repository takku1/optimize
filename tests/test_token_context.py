"""Tests for token-sequence context and the KV-cache."""
import numpy as np
import pytest

from prompt_optimization.context import (
    ContextCache, TokenSequence, contextual_vector, default_sequence,
    evaluate_sequence, tokenize,
)


def test_tokenize_splits_words_and_punctuation():
    assert tokenize("verify, independently") == ["verify", ",", "independently"]


def test_default_sequence_is_deterministic_and_well_shaped():
    a = default_sequence("re-verify each prior finding", d_model=16)
    b = default_sequence("re-verify each prior finding", d_model=16)
    assert a.embeddings.shape == (len(a.tokens), 16)
    np.testing.assert_array_equal(a.embeddings, b.embeddings)


def test_token_sequence_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        TokenSequence(("a", "b"), np.zeros((3, 4)))  # 3 rows but 2 tokens


def test_token_sequence_defaults_positions():
    seq = default_sequence("one two three", d_model=8)
    assert seq.positions == (0, 1, 2)


def test_contextual_vector_shape_and_normalization():
    seq = default_sequence("verify prior findings are sound", d_model=16)
    vec = contextual_vector(seq)
    assert vec.shape == (16,)
    assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-6)


def test_kv_cache_reuses_precomputed_tensors():
    seq = default_sequence("confirm the prior result independently", d_model=16)
    cache = ContextCache(num_heads=4, seed=0)
    v1 = contextual_vector(seq, cache=cache)
    assert cache.misses == 1
    v2 = contextual_vector(seq, cache=cache)
    assert cache.misses == 1  # cache hit, no recompute
    np.testing.assert_array_equal(v1, v2)


def test_kv_cache_does_not_alias_equal_embeddings_at_different_positions():
    base = default_sequence("one two", d_model=8)
    shifted = TokenSequence(base.tokens, base.embeddings.copy(), positions=(2, 3))
    cache = ContextCache(num_heads=4, seed=0)
    first = cache.keys_values(base)
    second = cache.keys_values(shifted)
    assert cache.misses == 2
    assert not np.array_equal(first[0], second[0])


def test_contextual_vector_is_deterministic_and_cache_consistent():
    seq = default_sequence("isolate the update under a fault boundary", d_model=16)
    cached = contextual_vector(seq, cache=ContextCache(num_heads=4, seed=0))
    uncached = contextual_vector(seq)  # seed 0 inline path
    # A KV-cache must not change the result: reuse == from-scratch.
    np.testing.assert_allclose(cached, uncached, atol=1e-12)
    # Same input + same seed twice is bit-identical.
    np.testing.assert_array_equal(
        contextual_vector(seq, cache=ContextCache(num_heads=4, seed=0)), cached
    )
    np.testing.assert_array_equal(contextual_vector(seq), uncached)


def test_evaluate_sequence_returns_metrics_and_context():
    from prompt_optimization.metrics import make_attractors

    attractors = make_attractors()
    seq = default_sequence("independently confirm the hypothesis", d_model=32)
    cache = ContextCache(num_heads=4, seed=3)
    result = evaluate_sequence(seq, attractors[0], attractors, cache=cache)
    assert "target_activation" in result
    assert "reliability" in result
    assert "context_vector" in result
    assert result["context_vector"].shape == (32,)
    assert result["tokens"] == len(seq.tokens)
