"""Case-based retrieval over the evolution graph: "have we tried something like this before?"

Per the grounding doc: this is Aamodt & Plaza's case-based reasoning (1994),
not retrieval-augmented generation with embeddings — at the data scale this
project actually has (hundreds, not millions, of transitions), filtering and
ranking by observed outcome is honest and sufficient. No embedding model, no
vector index. Swap in semantic retrieval later only if plain filtering
demonstrably stops working, per the same project's own repeated "get the
simple thing working before reaching for the complex thing" discipline.
"""
from __future__ import annotations

from typing import Any

from .models import MutationEdge
from .store import GraphStore

#: Evaluation trainability classes this project's own optimizer may condition on.
#: AUDIT_PRIVATE/TEST_PRIVATE records are excluded even from retrieval, not just
#: training, so a sealed holdout never leaks into a mutation's rationale.
RETRIEVABLE_TRAINABILITY = ("TRAINABLE", "DEVELOPMENT_ONLY", "RETIRED")


def _evidence_class(edge: MutationEdge) -> str:
    """An edge's ``evidence_class`` (see ``models.EVIDENCE_CLASSES``), defaulting to
    ``OPTIMIZER_TRANSITION`` for records written before this convention existed."""
    return str(edge.provenance.get("evidence_class", "OPTIMIZER_TRANSITION"))


def retrieve_similar_transitions(
    store: GraphStore,
    *,
    mutation_family: str | None = None,
    capability_contract_hash: str | None = None,
    top_k: int = 5,
    evidence_classes: tuple[str, ...] = ("OPTIMIZER_TRANSITION",),
) -> list[MutationEdge]:
    """Retrieve past transitions with an observed effect, ranked by utility delta.

    Filters to mutations whose child skill node matches
    ``capability_contract_hash`` when given (so retrieval never mixes
    capability families), and to a specific ``mutation_family`` when given.
    Only edges with a recorded ``actual_effect["utility_delta"]`` are
    eligible — an edge with no observed outcome yet can't inform a ranking.

    Defaults to ``evidence_classes=("OPTIMIZER_TRANSITION",)``: a mutation
    proposer should be biased by real search transitions, not by a
    deliberately-damaged negative control or a no-skill attribution run —
    those answer "does the benchmark work," not "was this mutation good."
    Pass ``evidence_classes=("OPTIMIZER_TRANSITION", "BENCHMARK_VALIDATION")``
    (or just the latter) to include or inspect validation evidence explicitly.
    """
    if top_k < 1:
        raise ValueError("top_k must be positive")
    edges = [edge for edge in store.iter_mutations() if "utility_delta" in edge.actual_effect]
    edges = [edge for edge in edges if _evidence_class(edge) in evidence_classes]
    if mutation_family is not None:
        edges = [edge for edge in edges if edge.mutation_family == mutation_family]
    if capability_contract_hash is not None:
        eligible_children = {
            node.skill_hash for node in store.iter_skills()
            if node.capability_contract_hash == capability_contract_hash
        }
        edges = [edge for edge in edges if edge.child_hash in eligible_children]
    ranked = sorted(edges, key=lambda edge: edge.actual_effect["utility_delta"], reverse=True)
    return ranked[:top_k]


def mutation_family_stats(
    store: GraphStore, *, capability_contract_hash: str | None = None,
    evidence_classes: tuple[str, ...] = ("OPTIMIZER_TRANSITION",),
) -> dict[str, dict[str, Any]]:
    """Per-mutation-family aggregate: n, mean utility delta, and regression rate.

    The "217 comparable transitions... success rate 73%" style summary a
    retrieval-conditioned proposer should see before choosing an operator.
    Defaults to ``OPTIMIZER_TRANSITION`` evidence only — see
    :func:`retrieve_similar_transitions` for why validation evidence is
    excluded by default rather than silently pooled in.
    """
    edges = [edge for edge in store.iter_mutations() if "utility_delta" in edge.actual_effect]
    edges = [edge for edge in edges if _evidence_class(edge) in evidence_classes]
    if capability_contract_hash is not None:
        eligible_children = {
            node.skill_hash for node in store.iter_skills()
            if node.capability_contract_hash == capability_contract_hash
        }
        edges = [edge for edge in edges if edge.child_hash in eligible_children]

    by_family: dict[str, list[float]] = {}
    for edge in edges:
        by_family.setdefault(edge.mutation_family, []).append(edge.actual_effect["utility_delta"])

    stats = {}
    for family, deltas in by_family.items():
        n = len(deltas)
        stats[family] = {
            "n": n,
            "mean_utility_delta": sum(deltas) / n,
            "regression_rate": sum(1 for d in deltas if d < 0) / n,
        }
    return stats
