import numpy as np
import pytest

from prompt_optimization import (causal_deletion_effect, directional_projection,
                                  interaction_effect, shapley_values)


def test_shapley_additive_game():
    def value(coalition):
        return sum({0: 2.0, 1: 3.0, 2: 5.0}[i] for i in coalition)
    np.testing.assert_allclose(shapley_values(3, value), [2, 3, 5])


def test_shapley_detects_synergy():
    def value(coalition):
        return float(4 in coalition) + (3.0 if {0, 1} <= coalition else 0.0)
    result = shapley_values(2, value)
    np.testing.assert_allclose(result, [1.5, 1.5])
    assert interaction_effect(value, 0, 1) == pytest.approx(3.0)


def test_causal_and_directional_helpers():
    assert causal_deletion_effect(.9, .6) == pytest.approx(.3)
    assert directional_projection([2, 0], [1, 0]) == pytest.approx(2.0)
    with pytest.raises(ValueError):
        directional_projection([1, 2], [0, 0])
