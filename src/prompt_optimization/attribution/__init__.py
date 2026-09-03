"""Model-agnostic attribution and latent-direction estimators.

These utilities operate on user-supplied value functions or vectors. They do not
assume access to hidden activations and therefore work for black-box APIs.
"""

from .shapley import shapley_values
from .interaction import causal_deletion_effect, interaction_effect
from .direction import directional_projection

__all__ = [
    "shapley_values",
    "interaction_effect",
    "causal_deletion_effect",
    "directional_projection",
]
