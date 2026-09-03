"""The persistent, content-addressed skill evolution graph.

Implements the grounded subset of `docs/evolution-graph-research.md`:
a Merkle-DAG-shaped provenance store (no blockchain — see that doc) plus
case-based retrieval over its recorded transitions. Deliberately does not
implement that document's neural-checkpoint stages (world model, learned
ranker/generator, offline RL) — no comparable published system trains those,
and this project has nowhere near enough recorded transitions yet to justify
attempting it. Get retrieval-conditioned proposal working first.
"""

from .models import EVIDENCE_CLASSES, TRAINABILITY_CLASSES, EvaluationRecord, MutationEdge, SkillNode
from .retrieval import RETRIEVABLE_TRAINABILITY, mutation_family_stats, retrieve_similar_transitions
from .store import GraphStore

__all__ = [
    "EVIDENCE_CLASSES",
    "RETRIEVABLE_TRAINABILITY",
    "TRAINABILITY_CLASSES",
    "EvaluationRecord",
    "GraphStore",
    "MutationEdge",
    "SkillNode",
    "mutation_family_stats",
    "retrieve_similar_transitions",
]
