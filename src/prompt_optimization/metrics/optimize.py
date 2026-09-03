"""Optimization-oriented selection: Pareto, rate-distortion, experiment choice."""
from __future__ import annotations

import re

import numpy as np

from .uncertainty import bootstrap_mean_interval


def estimate_tokens(text: str) -> int:
    """Conservative tokenizer-free estimate; production runs should inject a real tokenizer."""
    pieces = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    return max(1, len(pieces))


def rate_distortion_frontier(results: list[dict]) -> list[dict]:
    """Empirical distortion-rate curve: best distortion at or below each budget."""
    frontier = []
    best = float("inf")
    best_prompt = None
    for tokens in sorted({int(r["tokens"]) for r in results}):
        bucket = [r for r in results if int(r["tokens"]) == tokens]
        candidate = min(bucket, key=lambda r: r["distortion"])
        if candidate["distortion"] < best:
            best, best_prompt = float(candidate["distortion"]), candidate["prompt"]
        frontier.append({"tokens": tokens, "distortion": best, "prompt": best_prompt})
    return frontier


def metamorphic_consistency(reference, variants, tolerance: float = 0.0) -> float:
    """Fraction of paired variant scores that remain within a required relation."""
    ref, vals = float(reference), np.asarray(variants, dtype=float)
    if vals.size == 0 or tolerance < 0:
        raise ValueError("variants must be non-empty and tolerance must be non-negative")
    return float(np.mean(np.abs(vals - ref) <= tolerance))


def select_next_experiment(candidates: list[dict]) -> dict:
    """Choose the experiment with highest uncertainty-weighted potential gain."""
    if not candidates:
        raise ValueError("candidates must not be empty")
    return max(candidates, key=lambda c: float(c.get("uncertainty", 0.0)) * float(c.get("expected_gain", 0.0)))


def pareto_frontier(
    results: list[dict],
    maximize=("target_activation", "reliability"),
    minimize=("tokens", "off_target", "variance_penalty"),
) -> list[dict]:
    """Return non-dominated candidates; avoids pretending weights are universal."""
    frontier = []
    for candidate in results:
        dominated = any(
            all(other[k] >= candidate[k] for k in maximize)
            and all(other[k] <= candidate[k] for k in minimize)
            and (
                any(other[k] > candidate[k] for k in maximize)
                or any(other[k] < candidate[k] for k in minimize)
            )
            for other in results
            if other is not candidate
        )
        if not dominated:
            frontier.append(candidate)
    return frontier


def distortion_at_budget(frontier: list[dict], budget: int) -> float:
    """Best (lowest) distortion achievable at or under a token budget on a frontier.

    ``D*(B) = U_max - U*(B)``: the empirical distortion-rate function evaluated
    at ``B``, read off :func:`rate_distortion_frontier`'s output rather than
    re-deriving it, so the frontier stays the single source of truth.
    """
    eligible = [row for row in frontier if int(row["tokens"]) <= budget]
    if not eligible:
        raise ValueError(f"no frontier point at or under budget {budget}")
    return float(min(row["distortion"] for row in eligible))


def utility_at_budget(frontier: list[dict], budget: int) -> float:
    """``U*(B) = 1 - D*(B)``: best achievable utility under a token budget."""
    return 1.0 - distortion_at_budget(frontier, budget)


def optimization_resistance(delta_hv_samples: list[float], *, seed: int = 0, resamples: int = 2000,
                             level: float = 0.95) -> dict:
    """Summarize residual optimizer gain (``Δ_opt``) across multiple search seeds.

    Running the optimizer once and reporting "it improved 0.3%" does not show
    whether that gain is reliable. This reports the mean/std/CI of per-seed
    hypervolume gains, so "10 searches found mean residual gain +0.31%, 95% CI
    [0.08%, 0.54%]" replaces a single anecdotal run.
    """
    values = np.asarray(delta_hv_samples, dtype=float)
    if values.size == 0:
        raise ValueError("delta_hv_samples must be non-empty")
    lower, upper = bootstrap_mean_interval(values, seed=seed, resamples=resamples, level=level)
    return {
        "mean": float(values.mean()),
        "std": float(values.std()),
        "n_seeds": int(values.size),
        "ci": {"level": level, "lower": lower, "upper": upper},
    }


def hypervolume(points: list[tuple[float, float, float]], reference: tuple[float, float, float], *,
                 samples: int = 20000, seed: int = 0) -> float:
    """Monte Carlo estimate of the 3D hypervolume dominated by ``points`` above ``reference``.

    All three objectives (``U``, ``R``, ``-L_tok``) are maximized. Exact 3D
    hypervolume algorithms exist, but this project already leans on Monte Carlo
    estimation elsewhere (``shapley_values`` for large coalitions); reusing that
    style keeps the estimator simple and easy to audit rather than chasing an
    exact-but-fragile geometric algorithm for a toy search loop.
    """
    pts = np.asarray(points, dtype=float)
    ref = np.asarray(reference, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 3 or ref.shape != (3,):
        raise ValueError("points must be an (n, 3) array-like and reference a 3-tuple")
    if samples < 1:
        raise ValueError("samples must be positive")
    if pts.size == 0:
        return 0.0
    upper = pts.max(axis=0)
    if np.any(upper <= ref):
        return 0.0
    rng = np.random.default_rng(seed)
    box_volume = float(np.prod(upper - ref))
    draws = rng.uniform(ref, upper, size=(samples, 3))
    dominated = np.any(np.all(draws[:, None, :] <= pts[None, :, :], axis=2), axis=1)
    return box_volume * float(dominated.mean())


def delta_hv_converged(hv_history: list[float], *, epsilon: float = 0.01, checks: int = 3) -> bool:
    """Hypervolume-saturation halting rule: true once relative growth stays below ``epsilon``.

    Requires ``checks`` consecutive relative deltas below ``epsilon`` among the
    most recent checkpoint hypervolumes, matching the search loop's low-frequency
    convergence check rather than a single lucky flat step.
    """
    if checks < 1:
        raise ValueError("checks must be positive")
    if epsilon < 0:
        raise ValueError("epsilon must be non-negative")
    if any(not np.isfinite(float(value)) or value < 0 for value in hv_history):
        raise ValueError("hypervolume history must contain finite non-negative values")
    if len(hv_history) < checks + 1:
        return False
    tail = hv_history[-(checks + 1):]
    for previous, current in zip(tail, tail[1:]):
        if previous == 0:
            if current != 0:
                return False
            continue
        if abs((current - previous) / previous) >= epsilon:
            return False
    return True


def total_cost(components: dict[str, float], weights: dict[str, float] | None = None) -> dict:
    """Combine heterogeneous cost components into one operational cost, kept visible.

    A 150-token skill that causes 10,000 extra reasoning tokens is not
    necessarily cheaper than a 350-token skill with concise outputs. Costs stay
    itemized in ``weighted`` so no single scalar hides which term dominates.
    """
    if any(not np.isfinite(float(v)) for v in components.values()):
        raise ValueError("cost component values must be finite")
    weights = weights or {}
    if any(not np.isfinite(float(v)) for v in weights.values()):
        raise ValueError("cost weights must be finite")
    weighted = {key: float(value) * float(weights.get(key, 1.0)) for key, value in components.items()}
    return {"components": dict(components), "weighted": weighted, "total": float(sum(weighted.values()))}


def apply_hard_gates(
    results: list[dict],
    gates: dict[str, float],
    *,
    operator: str = "max",
) -> tuple[list[dict], list[dict]]:
    """Split ``results`` into gated-in vs gated-out on mandatory constraints.

    ``gates`` maps a result key to a bound. With ``operator="max"`` a candidate
    passes only if ``value <= bound``; with ``operator="min"`` only if
    ``value >= bound``. Violations are excluded unconditionally — score cannot
    rescue a candidate that breaks a critical invariant.
    """
    if operator not in ("max", "min"):
        raise ValueError("operator must be 'max' or 'min'")
    if any(not np.isfinite(float(bound)) for bound in gates.values()):
        raise ValueError("gate bounds must be finite")
    passed: list[dict] = []
    blocked: list[dict] = []
    for r in results:
        # A missing or non-finite critical measurement cannot pass a hard gate.
        # Treat it as blocked instead of silently dropping that constraint.
        fails = False
        for key, bound in gates.items():
            if key not in r:
                fails = True
                break
            try:
                value = float(r[key])
            except (TypeError, ValueError):
                fails = True
                break
            if not np.isfinite(value):
                fails = True
                break
            if (value > bound if operator == "max" else value < bound):
                fails = True
                break
        (blocked if fails else passed).append(r)
    return passed, blocked
