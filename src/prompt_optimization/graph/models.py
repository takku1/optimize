"""Content-addressed records for the persistent skill evolution graph.

Per `docs/evolution-graph-research.md`: this is a
Merkle-DAG-shaped provenance store (Git's object model, no different from
what MLflow/DVC already do), not a blockchain — no consensus, no mining, no
tokens. `skill_hash`/`mutation_id`/`evaluation_id` are content hashes
(`capability.provenance.content_hash`), so identity survives filename churn
(``skill2.md``, ``skill-final.md``, ...) and any edit to a past record is
visible as a hash mismatch, never a silent overwrite.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .._hashing import content_hash


@dataclass(frozen=True)
class SkillNode:
    """One concrete skill artifact — a node in the evolution DAG."""

    skill_text: str
    token_count: int
    parent_hashes: tuple[str, ...] = ()
    capability_contract_hash: str = ""
    generator: str = "unknown"
    generation: int = 0
    benchmark_version: str = ""
    created_at: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def skill_hash(self) -> str:
        return content_hash(self.skill_text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_hash": self.skill_hash,
            "skill_text": self.skill_text,
            "token_count": self.token_count,
            "parent_hashes": list(self.parent_hashes),
            "capability_contract_hash": self.capability_contract_hash,
            "generator": self.generator,
            "generation": self.generation,
            "benchmark_version": self.benchmark_version,
            "created_at": self.created_at,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SkillNode":
        return cls(
            skill_text=str(value["skill_text"]),
            token_count=int(value["token_count"]),
            parent_hashes=tuple(value.get("parent_hashes", ())),
            capability_contract_hash=str(value.get("capability_contract_hash", "")),
            generator=str(value.get("generator", "unknown")),
            generation=int(value.get("generation", 0)),
            benchmark_version=str(value.get("benchmark_version", "")),
            created_at=str(value.get("created_at", "")),
            provenance=dict(value.get("provenance", {})),
        )


@dataclass(frozen=True)
class MutationEdge:
    """One transition (§1 of the grounded proposal): the mutation between two skill nodes."""

    parent_hash: str
    child_hash: str
    mutation_family: str
    mutation_description: str = ""
    rationale: str = ""
    predicted_effect: dict[str, float] = field(default_factory=dict)
    actual_effect: dict[str, float] = field(default_factory=dict)
    optimizer_version: str = ""
    created_at: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.parent_hash.strip() or not self.child_hash.strip():
            raise ValueError("parent_hash and child_hash must not be empty")
        if not self.mutation_family.strip():
            raise ValueError("mutation_family must not be empty")

    @property
    def mutation_id(self) -> str:
        return content_hash({"parent_hash": self.parent_hash, "child_hash": self.child_hash,
                              "mutation_family": self.mutation_family, "created_at": self.created_at})

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "parent_hash": self.parent_hash,
            "child_hash": self.child_hash,
            "mutation_family": self.mutation_family,
            "mutation_description": self.mutation_description,
            "rationale": self.rationale,
            "predicted_effect": self.predicted_effect,
            "actual_effect": self.actual_effect,
            "optimizer_version": self.optimizer_version,
            "created_at": self.created_at,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MutationEdge":
        return cls(
            parent_hash=str(value["parent_hash"]),
            child_hash=str(value["child_hash"]),
            mutation_family=str(value["mutation_family"]),
            mutation_description=str(value.get("mutation_description", "")),
            rationale=str(value.get("rationale", "")),
            predicted_effect=dict(value.get("predicted_effect", {})),
            actual_effect=dict(value.get("actual_effect", {})),
            optimizer_version=str(value.get("optimizer_version", "")),
            created_at=str(value.get("created_at", "")),
            provenance=dict(value.get("provenance", {})),
        )


#: Visibility classes (§30 of the grounded proposal) controlling which
#: evaluation records may later feed any learned component. Enforced by
#: convention here (filtered in `retrieval.py`), not by access control.
TRAINABILITY_CLASSES = ("TRAINABLE", "DEVELOPMENT_ONLY", "AUDIT_PRIVATE", "TEST_PRIVATE", "RETIRED")

#: A record's role, tagged in ``provenance["evidence_class"]`` (additive —
#: not a dataclass field, so it costs nothing for existing records that
#: predate this convention). ``BENCHMARK_VALIDATION`` records (no_skill
#: attribution runs, negative/positive controls) answer "does the benchmark
#: measure what it claims to," not "was this mutation good" — mixing the two
#: into one undifferentiated pool of "transitions" would let a benchmark
#: sanity check masquerade as evidence of a real skill improvement, or vice
#: versa. ``retrieve_similar_transitions``/``mutation_family_stats`` should
#: default to ``OPTIMIZER_TRANSITION`` only, unless a caller explicitly asks
#: for validation evidence.
EVIDENCE_CLASSES = ("OPTIMIZER_TRANSITION", "BENCHMARK_VALIDATION")


@dataclass(frozen=True)
class EvaluationRecord:
    """One real evaluation of one skill node against one scenario/rollout."""

    skill_hash: str
    scenario_id: str
    metric_results: dict[str, Any]
    rollout_id: str = "rollout_01"
    capability_contract_hash: str = ""
    benchmark_version: str = ""
    evaluator_name: str = "unknown"
    model_name: str = "unknown"
    raw_output_hash: str = ""
    trainability: str = "TRAINABLE"
    created_at: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.skill_hash.strip() or not self.scenario_id.strip():
            raise ValueError("skill_hash and scenario_id must not be empty")
        if self.trainability not in TRAINABILITY_CLASSES:
            raise ValueError(f"trainability must be one of {TRAINABILITY_CLASSES}, got {self.trainability!r}")

    @property
    def evaluation_id(self) -> str:
        return content_hash({
            "skill_hash": self.skill_hash, "scenario_id": self.scenario_id,
            "rollout_id": self.rollout_id, "created_at": self.created_at,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "skill_hash": self.skill_hash,
            "scenario_id": self.scenario_id,
            "rollout_id": self.rollout_id,
            "capability_contract_hash": self.capability_contract_hash,
            "benchmark_version": self.benchmark_version,
            "evaluator_name": self.evaluator_name,
            "model_name": self.model_name,
            "raw_output_hash": self.raw_output_hash,
            "metric_results": self.metric_results,
            "trainability": self.trainability,
            "created_at": self.created_at,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvaluationRecord":
        return cls(
            skill_hash=str(value["skill_hash"]),
            scenario_id=str(value["scenario_id"]),
            metric_results=dict(value.get("metric_results", {})),
            rollout_id=str(value.get("rollout_id", "rollout_01")),
            capability_contract_hash=str(value.get("capability_contract_hash", "")),
            benchmark_version=str(value.get("benchmark_version", "")),
            evaluator_name=str(value.get("evaluator_name", "unknown")),
            model_name=str(value.get("model_name", "unknown")),
            raw_output_hash=str(value.get("raw_output_hash", "")),
            trainability=str(value.get("trainability", "TRAINABLE")),
            created_at=str(value.get("created_at", "")),
            provenance=dict(value.get("provenance", {})),
        )
