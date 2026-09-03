"""Typed contract for turning informal concepts into falsifiable models.

The semantic mapping is supplied by a model or human callback.  The core only
validates provenance, structure, and testability; it never claims that a
keyword substitution understands an analogy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


EPISTEMIC_STATUSES = ("established", "adapted_analogy", "novel_hypothesis")


@dataclass(frozen=True)
class ConceptualOperationalization:
    source_concept: str
    inferred_mechanism: str
    established_formalisms: tuple[str, ...]
    variable_mapping: Mapping[str, str]
    intervention: str
    observable: str
    falsifier: str
    epistemic_status: str
    caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = (
            self.source_concept, self.inferred_mechanism, self.intervention,
            self.observable, self.falsifier,
        )
        if any(not value.strip() for value in required):
            raise ValueError("operationalization fields must be non-empty")
        if not self.established_formalisms:
            raise ValueError("at least one nearest established formalism is required")
        if not self.variable_mapping or any(not str(k).strip() or not str(v).strip()
                                            for k, v in self.variable_mapping.items()):
            raise ValueError("variable_mapping requires concrete non-empty mappings")
        if self.epistemic_status not in EPISTEMIC_STATUSES:
            raise ValueError(f"epistemic_status must be one of {EPISTEMIC_STATUSES}")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ConceptualOperationalization":
        if not isinstance(raw, Mapping):
            raise ValueError("operationalization must be an object")
        formalisms = raw.get("established_formalisms", ())
        caveats = raw.get("caveats", ())
        variables = raw.get("variable_mapping", {})
        if not isinstance(formalisms, (list, tuple)) or not isinstance(caveats, (list, tuple)):
            raise ValueError("formalisms and caveats must be lists")
        if not isinstance(variables, Mapping):
            raise ValueError("variable_mapping must be an object")
        return cls(
            source_concept=str(raw.get("source_concept", "")),
            inferred_mechanism=str(raw.get("inferred_mechanism", "")),
            established_formalisms=tuple(str(item) for item in formalisms),
            variable_mapping={str(k): str(v) for k, v in variables.items()},
            intervention=str(raw.get("intervention", "")),
            observable=str(raw.get("observable", "")),
            falsifier=str(raw.get("falsifier", "")),
            epistemic_status=str(raw.get("epistemic_status", "")),
            caveats=tuple(str(item) for item in caveats),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_concept": self.source_concept,
            "inferred_mechanism": self.inferred_mechanism,
            "established_formalisms": list(self.established_formalisms),
            "variable_mapping": dict(self.variable_mapping),
            "intervention": self.intervention,
            "observable": self.observable,
            "falsifier": self.falsifier,
            "epistemic_status": self.epistemic_status,
            "caveats": list(self.caveats),
        }


def score_operationalization(value: ConceptualOperationalization) -> dict[str, Any]:
    """Score explicit mappings and falsifiability, not scientific correctness."""
    checks = {
        "mechanism_extracted": bool(value.inferred_mechanism.strip()),
        "nearest_formalism_searched": bool(value.established_formalisms),
        "variables_mapped": len(value.variable_mapping) >= 2,
        "intervention_defined": bool(value.intervention.strip()),
        "observable_defined": bool(value.observable.strip()),
        "falsifier_defined": bool(value.falsifier.strip()),
        "epistemic_status_declared": value.epistemic_status in EPISTEMIC_STATUSES,
    }
    utility = sum(checks.values()) / len(checks)
    return {
        "utility": utility,
        "hard_invariants_passed": all(checks.values()),
        "checks": checks,
        "evidence_tier": "formalization_contract",
        "semantic_correctness_requires_review": True,
    }
