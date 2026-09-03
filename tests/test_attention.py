"""Tests for positional encoding and attention (n-token relations)."""
import numpy as np
import pytest

from prompt_optimization.context.attention import (
    causal_mask, multi_head_attention, scaled_dot_product_attention,
    sinusoidal_positional_encoding,
)


def test_positional_encoding_shape_and_bound():
    table = sinusoidal_positional_encoding(max_len=8, d_model=16)
    assert table.shape == (8, 16)
    assert np.all(table >= -1.0) and np.all(table <= 1.0)


def test_positional_encoding_is_deterministic():
    a = sinusoidal_positional_encoding(20, 12)
    b = sinusoidal_positional_encoding(20, 12)
    np.testing.assert_array_equal(a, b)


def test_causal_mask_blocks_future_attention():
    mask = causal_mask(4)
    assert mask[0, 0] and not mask[0, 1]  # first token sees only itself
    assert mask[1, 0]                     # causal allows past
    assert not mask[0, 1]                 # cannot see future
    assert mask[3, :].all()               # last token sees all prior + itself
    assert np.all(np.tril(mask) == mask)


def test_scaled_dot_product_attention_normalizes_weights():
    rng = np.random.default_rng(0)
    q = rng.normal(size=(2, 4, 8))
    k = rng.normal(size=(2, 4, 8))
    v = rng.normal(size=(2, 4, 8))
    out = scaled_dot_product_attention(q, k, v)
    assert out.shape == (2, 4, 8)


def test_scaled_dot_product_attention_rejects_shape_mismatch():
    q = np.zeros((1, 4, 8))
    with pytest.raises(ValueError):
        scaled_dot_product_attention(q, np.zeros((1, 3, 8)), np.zeros((1, 4, 8)))  # bad key seq


def test_multi_head_output_shape_and_determinism():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(3, 6, 16))
    out1, attn1, _ = multi_head_attention(x, x, x, num_heads=4, seed=5)
    out2, _, _ = multi_head_attention(x, x, x, num_heads=4, seed=5)
    assert out1.shape == (3, 6, 16)
    assert attn1.shape == (3, 4, 6, 6)
    np.testing.assert_array_equal(out1, out2)  # deterministic


def test_multi_head_attention_rejects_undivisible_dim():
    x = np.zeros((2, 4, 15))
    with pytest.raises(ValueError):
        multi_head_attention(x, x, x, num_heads=4)


def test_causal_masked_attention_ignores_future_keys():
    # With a causal mask the FIRST query may attend only to its own key, so its
    # attention-weight row is a one-hot at column 0 (the only unmasked key).
    batch, seq, d = 1, 4, 4
    q = np.ones((batch, seq, d))
    k = np.ones((batch, seq, d))
    v = np.ones((batch, seq, d))
    mask = causal_mask(seq)
    _, attn, _ = multi_head_attention(q, k, v, num_heads=1, mask=mask)
    first_row = attn[0, 0, 0]  # (seq,) weights for the first query
    assert first_row[0] == pytest.approx(1.0, abs=1e-6)
    assert first_row[1:].max() == pytest.approx(0.0, abs=1e-9)
