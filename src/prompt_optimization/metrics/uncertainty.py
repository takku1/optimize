"""Uncertainty quantification and distributional summaries.

Statistical primitives here defer to SciPy/NumPy's validated implementations
rather than reimplementing them: there is no elementary closed-form formula
for things like the normal quantile function or the Wasserstein distance, and
a hand-rolled approximation is one more thing this project would have to
validate itself instead of inheriting from a mature, widely-tested library.
Custom code appears only where no such library primitive exists (e.g. the
nested/hierarchical bootstrap below, which composes NumPy's exact resampling
and quantile operations rather than approximating anything).
"""
from __future__ import annotations

import numpy as np
from scipy import stats as scipy_stats
from scipy.special import ndtri


def bootstrap_mean_interval(values, seed: int = 0, resamples: int = 2000, level: float = 0.95,
                             method: str = "percentile") -> tuple[float, float]:
    """Non-parametric uncertainty interval for a measured behavioral metric.

    Backed by ``scipy.stats.bootstrap`` rather than a hand-rolled resampling
    loop. ``method`` defaults to ``"percentile"`` for parity with this
    project's existing call sites (small, sometimes degenerate samples);
    pass ``"BCa"`` for scipy's bias-corrected-and-accelerated interval when
    the sample is large enough for its jackknife step to be stable.
    """
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        raise ValueError("values must not be empty")
    if values.size == 1:
        return float(values[0]), float(values[0])
    result = scipy_stats.bootstrap(
        (values,), np.mean, n_resamples=resamples, confidence_level=level,
        method=method, random_state=np.random.default_rng(seed),
    )
    return float(result.confidence_interval.low), float(result.confidence_interval.high)


def conformal_radius(calibration_errors, alpha: float = 0.1) -> float:
    """Split-conformal finite-sample radius from held-out absolute errors."""
    errors = np.sort(np.asarray(calibration_errors, dtype=float))
    if errors.size == 0 or not 0 < alpha < 1:
        raise ValueError("errors must be non-empty and alpha must be in (0, 1)")
    rank = min(int(np.ceil((errors.size + 1) * (1 - alpha))) - 1, errors.size - 1)
    return float(errors[max(rank, 0)])


def wasserstein_1d(samples_a, samples_b) -> float:
    """Exact 1-Wasserstein (earth-mover) distance via ``scipy.stats.wasserstein_distance``."""
    a, b = np.asarray(samples_a, dtype=float), np.asarray(samples_b, dtype=float)
    if a.size == 0 or b.size == 0:
        raise ValueError("samples must be non-empty")
    return float(scipy_stats.wasserstein_distance(a, b))


def robust_summary(values, lower_quantile: float = 0.1) -> dict:
    """Summarize repeated measurements without optimizing only for the mean."""
    values = np.asarray(values, dtype=float)
    if values.size == 0 or not 0 <= lower_quantile <= 0.5:
        raise ValueError("values must be non-empty and lower_quantile must be in [0, .5]")
    return {
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "lower_quantile": float(np.quantile(values, lower_quantile)),
        "std": float(values.std()),
    }


def tail_metrics(values, q: float = 0.1) -> dict:
    """Mean, ``q``-quantile, and CVaR_q (mean of the worst ``q`` fraction).

    Mean utility hides catastrophic tail failures: a skill averaging .94 but
    failing badly on 8% of cases is not the same as one consistently at .91.
    """
    values = np.asarray(values, dtype=float)
    if values.size == 0 or not 0 < q < 1:
        raise ValueError("values must be non-empty and q must be in (0, 1)")
    sorted_values = np.sort(values)
    cutoff = max(1, int(np.ceil(q * sorted_values.size)))
    worst = sorted_values[:cutoff]
    return {
        "mean": float(values.mean()),
        f"p{int(q * 100)}": float(np.quantile(values, q)),
        f"cvar_{q}": float(worst.mean()),
    }


def power_sample_size(sigma: float, delta_min: float, *, alpha: float = 0.05, power: float = 0.8) -> int:
    """Minimum paired sample size to detect ``delta_min`` at significance ``alpha``.

    Normal-approximation sample-size formula for a one-sample/paired mean test:
    ``n = ((z_(alpha/2) + z_power) * sigma / delta_min) ** 2``, using
    ``scipy.special.ndtri`` (the validated normal quantile primitive scipy's
    own ``norm.ppf`` is built on) rather than a hand-rolled approximation.
    This turns "500 tasks seems large enough" into a stated, falsifiable
    minimum-detectable-effect claim; it is a planning default, not a
    substitute for a real pilot estimate of ``sigma``.
    """
    if sigma <= 0 or delta_min <= 0 or not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("sigma and delta_min must be positive; alpha and power must be in (0, 1)")
    z_alpha = float(ndtri(1 - alpha / 2))
    z_power = float(ndtri(power))
    n = ((z_alpha + z_power) * sigma / delta_min) ** 2
    return int(np.ceil(n))


def hierarchical_bootstrap(groups, seed: int = 0, resamples: int = 2000, level: float = 0.95) -> tuple[float, float]:
    """Nested (two-level) bootstrap interval respecting scenario/rollout structure.

    ``groups`` is a sequence of per-scenario rollout-value sequences (e.g. task
    -> paraphrase -> rollout). A flat :func:`bootstrap_mean_interval` treats
    every rollout as an independent observation, which understates uncertainty
    when rollouts are nested under a much smaller number of scenarios. This
    resamples scenarios with replacement, then resamples rollouts within each
    resampled scenario, before taking the grand mean.

    No single library primitive performs nested/cluster bootstrap, so this
    composes NumPy's exact (not approximated) resampling and quantile
    operations directly, the same building blocks ``scipy.stats.bootstrap``
    itself uses internally for the flat case.
    """
    groups = [np.asarray(g, dtype=float) for g in groups]
    if not groups or any(g.size == 0 for g in groups):
        raise ValueError("groups must be non-empty and each group must contain values")
    rng = np.random.default_rng(seed)
    n_groups = len(groups)
    means = np.empty(resamples, dtype=float)
    for i in range(resamples):
        chosen = rng.integers(0, n_groups, size=n_groups)
        group_means = [
            rng.choice(groups[g], groups[g].size, replace=True).mean() for g in chosen
        ]
        means[i] = float(np.mean(group_means))
    tail = (1.0 - level) / 2.0
    return float(np.quantile(means, tail)), float(np.quantile(means, 1.0 - tail))
