"""Reusable optimizer policies and declarative configuration support."""

from .declarative import (
    OptimizationSpec,
    apply_revision,
    combine_structural_and_behavioral,
    discover_optimization_spec,
    is_activated,
    load_optimization_spec,
    propose_from_spec,
    score_from_spec,
)

__all__ = [
    "OptimizationSpec", "apply_revision", "combine_structural_and_behavioral",
    "discover_optimization_spec", "is_activated", "load_optimization_spec",
    "propose_from_spec", "score_from_spec",
]
