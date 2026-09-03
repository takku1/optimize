"""Candidate representation and lineage for the branching evolutionary search."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """One skill-text candidate in the search population, with lineage.

    Never overwritten: every candidate that ever enters the Pareto archive is
    kept (see ``search/runs.py``), so the final report can walk ``parent_ids``
    back to the seed and answer "why does the final skill look this way."
    """

    id: str
    text: str
    generation: int
    parent_ids: tuple[str, ...] = ()
    mutation_type: str = "seed"
    transformation_class: str = "seed"

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("id must not be empty")
        if not self.text.strip():
            raise ValueError("text must not be empty")
        if self.generation < 0:
            raise ValueError("generation must be non-negative")


def new_candidate_id(text: str, *, salt: str = "", prefix: str = "c") -> str:
    """Deterministic id derived from content + salt.

    A random id (``uuid4``) would make two runs with the same seed produce
    different candidate ids for identical text, breaking the reproducibility
    ``runs/`` lineage output depends on. Hashing content + salt keeps ids
    stable across repeat runs while still letting callers (see
    :mod:`.mutate`) distinguish otherwise-identical candidates via the salt.
    """
    digest = hashlib.sha256(f"{salt}|{text}".encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def seed_population(seed_text: str, *, n: int = 1) -> list[Candidate]:
    """Instantiate the generation-0 seed population (BCSO execution protocol step 1)."""
    if n < 1:
        raise ValueError("n must be positive")
    return [
        Candidate(id=new_candidate_id(seed_text, salt=str(i), prefix="seed"), text=seed_text, generation=0)
        for i in range(n)
    ]
