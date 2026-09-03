"""Γ: declared capability contracts, task taxonomy, maturity, provenance, reference envelopes.

This subpackage holds the BCSO-Bench layer that sits above the behavioral
contract machinery in :mod:`prompt_optimization.contracts`: what a skill
*claims* to do (Γ), how broadly it has been exercised (taxonomy coverage),
what tier of evidence supports it (maturity), what actually produced a given
number (provenance/versioning), and how it compares to mature skills of its
class (reference envelopes).
"""

from .claims import Claim, ClaimResult, all_passed, format_report, verify_claim, verify_claims
from .contract import DEFAULT_AXES, CapabilityContract, coverage_report, load_capability_contract
from .maturity import MaturityTier, classify_maturity
from .promotion import PromotionVerdict, VersionComparison, compare_versions
from .provenance import CURRENT_BENCHMARK_VERSION, BenchmarkVersion, ProvenanceRecord, content_hash
from .reference import (
    family_conditioned_percentile,
    goodness_of_fit,
    knn_distance,
    mahalanobis_membership,
    select_envelope_estimator,
)

__all__ = [
    "CURRENT_BENCHMARK_VERSION",
    "DEFAULT_AXES",
    "BenchmarkVersion",
    "CapabilityContract",
    "Claim",
    "ClaimResult",
    "MaturityTier",
    "PromotionVerdict",
    "ProvenanceRecord",
    "VersionComparison",
    "all_passed",
    "classify_maturity",
    "compare_versions",
    "content_hash",
    "coverage_report",
    "family_conditioned_percentile",
    "format_report",
    "goodness_of_fit",
    "knn_distance",
    "load_capability_contract",
    "mahalanobis_membership",
    "select_envelope_estimator",
    "verify_claim",
    "verify_claims",
]
