"""Token-level context analysis: attention, sequences, and a KV-cache."""

from .attention import (
    causal_mask,
    multi_head_attention,
    scaled_dot_product_attention,
    sinusoidal_positional_encoding,
)
from .cache import ContextCache
from .sequence import (
    TokenSequence,
    contextual_vector,
    default_sequence,
    evaluate_sequence,
    tokenize,
)
from .representation import HiddenRepresentation, RepresentationEncoder, cosine_similarity, representation_drift

__all__ = [
    "ContextCache",
    "TokenSequence",
    "causal_mask",
    "contextual_vector",
    "default_sequence",
    "evaluate_sequence",
    "multi_head_attention",
    "scaled_dot_product_attention",
    "sinusoidal_positional_encoding",
    "tokenize",
    "HiddenRepresentation",
    "RepresentationEncoder",
    "cosine_similarity",
    "representation_drift",
]
