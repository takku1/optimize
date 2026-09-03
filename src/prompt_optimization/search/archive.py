"""Pareto archive maintenance and hypervolume-based convergence checking.

``P_t -> evaluate -> ParetoFilter(P_t ∪ C_t) -> P_{t+1}`` — the branching
half of the search loop. Rows here are plain dicts (``id``, ``U``, ``R``,
``tokens``) keyed to a :class:`~prompt_optimization.search.population.Candidate`
by id; the archive never mutates or discards a `Candidate`'s lineage, it only
tracks which ids are currently non-dominated.
"""
from __future__ import annotations

from ..metrics import delta_hv_converged, hypervolume, pareto_frontier


def update_archive(archive: list[dict], candidates: list[dict]) -> list[dict]:
    """``ParetoFilter(P_t ∪ C_t)``: merge and keep only the non-dominated set.

    Each row must have ``id``, ``U`` (fitness utility), ``R`` (fitness
    robustness), and ``tokens``.
    """
    merged = {row["id"]: row for row in [*archive, *candidates]}.values()
    return pareto_frontier(list(merged), maximize=("U", "R"), minimize=("tokens",))


def archive_hypervolume(archive: list[dict], *, reference_ur: tuple[float, float] = (0.0, 0.0),
                         samples: int = 5000, seed: int = 0) -> float:
    """3D hypervolume of the archive with respect to ``(U, R, -tokens)``, all maximized."""
    if not archive:
        return 0.0
    points = [(row["U"], row["R"], -row["tokens"]) for row in archive]
    max_tokens = max(row["tokens"] for row in archive)
    reference = (reference_ur[0], reference_ur[1], -max_tokens - 1)
    return hypervolume(points, reference, samples=samples, seed=seed)


def is_saturated(hv_history: list[float], *, epsilon: float = 0.01, checks: int = 3) -> bool:
    """Halting rule: hypervolume growth has stayed below ``epsilon`` for ``checks`` checkpoints."""
    return delta_hv_converged(hv_history, epsilon=epsilon, checks=checks)


def select_delta_optimal(archive: list[dict], *, delta_u: float = 0.02) -> dict:
    """``S*_δ = argmin L_tok(S)`` s.t. ``U_select(S) >= (1 - δ_U) * U_max,select``.

    The freeze-time selection rule: among archive members within ``delta_u``
    of the best observed utility, pick the cheapest one.
    """
    if not archive:
        raise ValueError("archive must not be empty")
    if not 0 <= delta_u < 1:
        raise ValueError("delta_u must be in [0, 1)")
    u_max = max(row["U"] for row in archive)
    # The relative margin (1 - delta_u) * U_max only shrinks the threshold
    # below U_max when U_max is positive; a non-positive U_max (this
    # project's synthetic evaluator is not bounded to [0, 1]) falls back to
    # requiring the exact max so at least one row is always eligible.
    threshold = (1 - delta_u) * u_max if u_max > 0 else u_max
    eligible = [row for row in archive if row["U"] >= threshold]
    return min(eligible, key=lambda row: row["tokens"])
