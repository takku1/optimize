"""Bounded hierarchical search with adaptive mutation blast radius."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .iterative import IterativeConfig, Score, _better

MUTATION_LEVELS = ("token", "phrase", "sentence", "paragraph", "section", "skill")
Mutator = Callable[[str, str, int], str]
Reconciler = Callable[[str, str, int], str]
ScoreFn = Callable[[str], Score]


@dataclass(frozen=True)
class HierarchicalConfig:
    max_depth: int = len(MUTATION_LEVELS)
    beam_width: int = 3
    expansion_threshold: float = 0.05
    robustness_weight: float = 0.0
    density_weight: float = 0.0
    cost_weight: float = 0.001

    def __post_init__(self) -> None:
        if not 1 <= self.max_depth <= len(MUTATION_LEVELS):
            raise ValueError("max_depth must be within the mutation level range")
        if self.beam_width < 1 or self.expansion_threshold < 0:
            raise ValueError("beam_width must be positive and threshold non-negative")
        if min(self.robustness_weight, self.density_weight, self.cost_weight) < 0:
            raise ValueError("objective weights must be non-negative")


@dataclass
class HierarchicalResult:
    selected_text: str
    selected_score: dict[str, Any]
    radius: int
    explored: list[dict[str, Any]] = field(default_factory=list)


def _utility(score: Mapping[str, Any]) -> float:
    return float(score.get("neighborhood_robustness", score.get("utility", 0.0)))


def _objective(score: Mapping[str, Any], cfg: HierarchicalConfig) -> float:
    utility = float(score.get("utility", 0.0))
    robust = float(score.get("neighborhood_robustness", utility))
    density = float(score.get("information_density", 0.0))
    cost = float(score.get("tokens", 0.0))
    return utility + cfg.robustness_weight * robust + cfg.density_weight * density - cfg.cost_weight * cost


def search_hierarchically(
    seed_text: str,
    score: ScoreFn,
    mutate: Mutator,
    reconcile: Reconciler,
    *,
    config: HierarchicalConfig | None = None,
) -> HierarchicalResult:
    """Search from token to skill scale, expanding radius on measured impact.

    Each candidate is reconciled at its mutation level before scoring. The
    reconciler may rewrite the surrounding context, but the program still
    decides acceptance through hard invariants and the shared objective.
    """
    if not seed_text.strip():
        raise ValueError("seed_text must not be empty")
    cfg = config or HierarchicalConfig()
    objective_config = IterativeConfig(robustness_weight=cfg.robustness_weight,
                                       density_weight=cfg.density_weight,
                                       cost_weight=cfg.cost_weight)
    current_text, current_score = seed_text, dict(score(seed_text))
    frontier: list[tuple[str, dict[str, Any]]] = [(current_text, current_score)]
    radius = 1
    explored: list[dict[str, Any]] = []
    for depth in range(cfg.max_depth):
        level = MUTATION_LEVELS[depth]
        candidates: list[tuple[str, dict[str, Any], float]] = []
        for parent_text, parent_score in frontier:
          for branch in range(cfg.beam_width):
            mutated = mutate(parent_text, level, branch)
            candidate_text = reconcile(mutated, level, depth)
            if not candidate_text.strip():
                raise ValueError(f"empty candidate at level {level}")
            candidate_score = dict(score(candidate_text))
            accepted = _better(candidate_score, parent_score, objective_config)
            impact = abs(_utility(candidate_score) - _utility(parent_score))
            explored.append({"depth": depth, "level": level, "branch": branch,
                             "accepted": accepted, "impact": impact,
                             "score": candidate_score})
            if accepted:
                candidates.append((candidate_text, candidate_score, impact))
        if candidates:
            candidates.sort(key=lambda item: _objective(item[1], cfg), reverse=True)
            frontier = [(text, candidate_score) for text, candidate_score, _ in candidates[:cfg.beam_width]]
            current_text, current_score = frontier[0]
            impact = candidates[0][2]
            if impact >= cfg.expansion_threshold:
                radius = min(depth + 2, cfg.max_depth)
        elif depth + 1 >= radius:
            break
    return HierarchicalResult(current_text, current_score, radius, explored)
