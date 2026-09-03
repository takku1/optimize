"""Named baseline strategies for comparing against full BCSO.

An industry benchmark needs comparison systems, not just "BCSO improved the
skill" in isolation. Each baseline is a restricted configuration of the same
:func:`~prompt_optimization.search.loop.run_bcso` state machine, so a run's
``runs/`` lineage output stays directly comparable across baselines —
optimizer ablations are just another named (or ad hoc) ``BaselineConfig``.
"""
from __future__ import annotations

from dataclasses import dataclass

from .mutate import ALL_MUTATIONS


@dataclass(frozen=True)
class BaselineConfig:
    """One point in the "how much of BCSO is turned on" space."""

    name: str
    use_mutation: bool = True
    use_pareto_filter: bool = True
    directed_mutation: bool = True
    allowed_mutations: tuple[str, ...] = ALL_MUTATIONS
    max_generations: int = 1

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.max_generations < 0:
            raise ValueError("max_generations must be non-negative")
        if self.use_mutation and not self.allowed_mutations:
            raise ValueError("allowed_mutations must not be empty when use_mutation is True")


BASELINES: dict[str, BaselineConfig] = {
    "no_skill": BaselineConfig("no_skill", use_mutation=False, use_pareto_filter=False, max_generations=0),
    "original": BaselineConfig("original", use_mutation=False, use_pareto_filter=False, max_generations=0),
    "simple_rewrite": BaselineConfig(
        "simple_rewrite", use_mutation=True, use_pareto_filter=False, directed_mutation=False, max_generations=1,
    ),
    "compression_only": BaselineConfig(
        "compression_only", use_mutation=True, use_pareto_filter=True, directed_mutation=False,
        allowed_mutations=("compress",), max_generations=5,
    ),
    "random_mutation": BaselineConfig(
        "random_mutation", use_mutation=True, use_pareto_filter=True, directed_mutation=False, max_generations=10,
    ),
    "evolution_no_gradient": BaselineConfig(
        "evolution_no_gradient", use_mutation=True, use_pareto_filter=True, directed_mutation=False,
        max_generations=10,
    ),
    "textual_gradient": BaselineConfig(
        "textual_gradient", use_mutation=True, use_pareto_filter=True, directed_mutation=True, max_generations=10,
    ),
    "full_bcso": BaselineConfig(
        "full_bcso", use_mutation=True, use_pareto_filter=True, directed_mutation=True, max_generations=25,
    ),
}


def get_baseline(name: str) -> BaselineConfig:
    if name not in BASELINES:
        raise ValueError(f"unknown baseline {name!r}; choose from {sorted(BASELINES)}")
    return BASELINES[name]
