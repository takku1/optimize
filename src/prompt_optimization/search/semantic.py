"""Model-free semantic-search primitives.

These operators expose a search space; they do not claim that a replacement is
meaning-preserving. Equivalence is established only by the contract evaluator.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class LexicalVariant:
    source: str
    replacement: str
    specificity: str = "unknown"

    def apply(self, text: str) -> str:
        return re.sub(r"(?<!\w)" + re.escape(self.source) + r"(?!\w)", self.replacement, text, flags=re.IGNORECASE)


def lexical_variants(text: str, replacements: Mapping[str, str]) -> list[str]:
    """Return unique candidates for an explicit terminology map."""
    results: list[str] = []
    for source, replacement in replacements.items():
        candidate = LexicalVariant(source, replacement).apply(text)
        if candidate != text and candidate not in results:
            results.append(candidate)
    return results


def operationalize(text: str, concepts: Mapping[str, str]) -> str:
    """Replace explicitly mapped vague concepts with supplied predicates.

    The mapping is configuration, not inferred meaning. This keeps the core
    deterministic and makes every semantic claim auditable.
    """
    result = text
    for vague, predicate in concepts.items():
        result = re.sub(r"(?<!\w)" + re.escape(vague) + r"(?!\w)", predicate, result, flags=re.IGNORECASE)
    return result
