"""Generalized transformation taxonomy and deterministic provenance helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass

TRANSFORMATION_FAMILIES = (
    "lexical", "syntactic", "semantic_operationalization", "structural",
    "compression", "reconstruction", "identity",
)

@dataclass(frozen=True)
class Transformation:
    family: str
    operator: str
    token_delta: int
    changed_lines: int
    semantic_claim: str = "unverified"

    def to_dict(self) -> dict[str, object]:
        return {"family": self.family, "operator": self.operator,
                "token_delta": self.token_delta, "changed_lines": self.changed_lines,
                "semantic_claim": self.semantic_claim}

def describe_transformation(parent: str, child: str, mode: str = "") -> Transformation:
    """Classify an edit conservatively; classification is not semantic proof."""
    parent_words, child_words = parent.split(), child.split()
    if parent == child:
        family, operator = "identity", "no_change"
    elif mode in {"complete_rewrite", "reconstruction"}:
        family, operator = "reconstruction", "canonical_rewrite"
    elif len(child_words) < len(parent_words) and len(child_words) <= len(parent_words) * .95:
        family, operator = "compression", "deduplicate_or_reduce"
    elif re.sub(r"\s+", " ", parent).strip() == re.sub(r"\s+", " ", child).strip():
        family, operator = "syntactic", "whitespace_normalization"
    elif mode in {"section_rewrite", "reorganization"}:
        family, operator = "structural", "section_reserialization"
    else:
        family, operator = "syntactic", "controlled_edit"
    changed = sum(a != b for a, b in zip(parent.splitlines(), child.splitlines()))
    changed += abs(len(parent.splitlines()) - len(child.splitlines()))
    return Transformation(family, operator, len(child_words) - len(parent_words), changed)
