"""Mutation operators for the synthetic search loop.

These are text-level, rule-based transforms, not model-driven rewrites. They
exist so ``search/loop.py`` has something to run end-to-end and so baselines
like ``random_mutation`` are actually runnable — not because a rule-based
transform is claimed to understand skill semantics the way a real
optimizer-model rewrite would. Same honesty convention as
``SyntheticBasinEvaluator``: this is scaffolding, not evidence.
"""
from __future__ import annotations

import re

import numpy as np

from ..contracts import DefectType
from .population import Candidate, new_candidate_id

#: Non-defect operators available to the search loop's baselines.
ALL_MUTATIONS: tuple[str, ...] = ("structural_swap", "compress", "rule_consolidation")

#: Handoff doc's transformation-class taxonomy, tagged per mutation type.
TRANSFORMATION_CLASS = {
    "structural_swap": "refactor",
    "compress": "compression",
    "rule_consolidation": "compression",
    "defect_injection": "reauthoring",
}


def _split_paragraphs(text: str) -> list[str]:
    parts = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    return parts or [text]


def _child(parent: Candidate, text: str, mutation_type: str, *, salt: str = "") -> Candidate:
    return Candidate(
        id=new_candidate_id(text, salt=f"{parent.id}:{mutation_type}:{salt}", prefix=mutation_type[:4]),
        text=text,
        generation=parent.generation + 1,
        parent_ids=(parent.id,),
        mutation_type=mutation_type,
        transformation_class=TRANSFORMATION_CLASS.get(mutation_type, "reauthoring"),
    )


def structural_swap(candidate: Candidate, *, seed: int = 0) -> Candidate:
    """Swap the order of two paragraphs — a control-flow-preserving reorder ("refactor")."""
    paragraphs = _split_paragraphs(candidate.text)
    if len(paragraphs) < 2:
        return _child(candidate, candidate.text, "structural_swap", salt=str(seed))
    rng = np.random.default_rng(seed)
    i, j = rng.choice(len(paragraphs), size=2, replace=False)
    paragraphs[i], paragraphs[j] = paragraphs[j], paragraphs[i]
    return _child(candidate, "\n\n".join(paragraphs), "structural_swap", salt=str(seed))


def compress(candidate: Candidate, *, drop_fraction: float = 0.1, seed: int = 0) -> Candidate:
    """Drop a random fraction of sentences — a crude compression mutation."""
    if not 0 <= drop_fraction < 1:
        raise ValueError("drop_fraction must be in [0, 1)")
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", candidate.text) if s.strip()]
    if len(sentences) < 2:
        return _child(candidate, candidate.text, "compress", salt=str(seed))
    rng = np.random.default_rng(seed)
    keep = max(1, int(round(len(sentences) * (1 - drop_fraction))))
    kept_idx = sorted(rng.choice(len(sentences), size=keep, replace=False))
    return _child(candidate, " ".join(sentences[i] for i in kept_idx), "compress", salt=str(seed))


def rule_consolidation(candidate: Candidate) -> Candidate:
    """Drop exact-duplicate lines — a safe, deterministic consolidation mutation."""
    seen: set[str] = set()
    kept_lines = []
    for line in candidate.text.splitlines():
        key = line.strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        kept_lines.append(line)
    return _child(candidate, "\n".join(kept_lines), "rule_consolidation")


_OPERATORS = {"structural_swap": structural_swap, "compress": compress, "rule_consolidation": rule_consolidation}

_DEFECT_TEXT = {
    DefectType.REDUNDANT: "Note: always double-check your work. Note: always double-check your work.",
    DefectType.CONTRADICTORY: "Always ask for confirmation before any write. Never ask for confirmation before a write.",
    DefectType.IRRELEVANT: "As an aside, the history of the semicolon is a matter of some typographic debate.",
    DefectType.VERBOSE: (
        "In order to proceed with the task at hand, it is important to first consider, at some "
        "length, the various factors that may or may not be relevant to the eventual outcome."
    ),
    DefectType.MISLEADING: "This step is optional and can always be skipped safely.",
    DefectType.UNNECESSARY_STEP: "Before continuing, recompute the value you already computed two steps ago.",
    DefectType.MALFORMED_TRIGGER: "Trigger: when the the user asks, asks for this.",
}


def inject_defect(candidate: Candidate, defect: DefectType) -> Candidate:
    """Append a labeled defect sentence — used by the counterfactual-insertion validation suite."""
    text = candidate.text + "\n\n" + _DEFECT_TEXT[defect]
    return _child(candidate, text, "defect_injection", salt=defect.value)


def random_mutation(candidate: Candidate, *, seed: int = 0, allowed: tuple[str, ...] = ALL_MUTATIONS) -> Candidate:
    """Pick one of ``allowed`` operators uniformly at random.

    Named baseline: ``random_mutation`` — no textual-gradient diagnosis, no
    directed choice of operator.
    """
    if not allowed:
        raise ValueError("allowed must not be empty")
    rng = np.random.default_rng(seed)
    choice = str(rng.choice(list(allowed)))
    if choice == "compress":
        return compress(candidate, seed=seed)
    if choice == "rule_consolidation":
        return rule_consolidation(candidate)
    return structural_swap(candidate, seed=seed)
