"""Reference-family envelopes: where does a candidate sit among mature skills of its class?

The design doc this module implements warns explicitly against assuming
``z ~ N(mu, Sigma)`` before checking whether a reference population actually
looks Gaussian — a 200-token formatter and a 3,000-token orchestration skill
can both be excellent while having wildly different geometries. This module
measures the reference population first via a real goodness-of-fit test
(``scipy.stats.shapiro``, the validated implementation — not a hand-rolled
normality check) and only offers a Mahalanobis/Gaussian membership score when
that test does not reject normality. The default, always-safe estimator is
the family-conditioned percentile: no distributional assumption at all.
"""
from __future__ import annotations

import numpy as np
from scipy import stats as scipy_stats


def family_conditioned_percentile(point: float, reference_values, *, capability_family: str = "") -> dict:
    """Percentile rank of ``point`` within its family's reference distribution.

    The default, safest estimator — no distributional assumption at all.
    """
    values = np.asarray(reference_values, dtype=float)
    if values.size == 0:
        raise ValueError("reference_values must not be empty")
    percentile = float((values < point).mean() * 100)
    return {
        "method": "family_conditioned_percentile",
        "capability_family": capability_family,
        "percentile": percentile,
        "n_reference": int(values.size),
    }


def knn_distance(point, reference_points, *, k: int = 3) -> dict:
    """Mean Euclidean distance to the ``k`` nearest reference points — an assumption-free density proxy."""
    point_arr = np.asarray(point, dtype=float)
    refs = np.asarray(reference_points, dtype=float)
    if refs.ndim != 2 or refs.shape[1] != point_arr.shape[0]:
        raise ValueError("reference_points must be an (n, d) array matching point's dimension")
    if refs.shape[0] < k:
        raise ValueError(f"need at least k={k} reference points, got {refs.shape[0]}")
    distances = np.linalg.norm(refs - point_arr, axis=1)
    nearest = np.sort(distances)[:k]
    return {"method": "knn_distance", "k": k, "mean_distance": float(nearest.mean()), "n_reference": int(refs.shape[0])}


def goodness_of_fit(reference_points, *, alpha: float = 0.05) -> dict:
    """Per-dimension Shapiro-Wilk normality test — the preregistered check before trusting a Gaussian envelope."""
    refs = np.asarray(reference_points, dtype=float)
    if refs.ndim != 2 or refs.shape[0] < 3:
        raise ValueError("reference_points must be an (n, d) array with n >= 3")
    p_values = [float(scipy_stats.shapiro(refs[:, dim]).pvalue) for dim in range(refs.shape[1])]
    return {"p_values": p_values, "alpha": alpha, "normal_enough": all(p >= alpha for p in p_values)}


def mahalanobis_membership(point, reference_points) -> dict:
    """Mahalanobis distance under an empirical mean/covariance.

    Uses ``numpy.cov`` (the validated covariance estimator) rather than a
    hand-derived formula. Callers should check :func:`goodness_of_fit` first
    and prefer :func:`family_conditioned_percentile` or :func:`knn_distance`
    when it does not clear — see :func:`select_envelope_estimator`.
    """
    point_arr = np.asarray(point, dtype=float)
    refs = np.asarray(reference_points, dtype=float)
    if refs.ndim != 2 or refs.shape[1] != point_arr.shape[0]:
        raise ValueError("reference_points must be an (n, d) array matching point's dimension")
    if refs.shape[0] <= refs.shape[1]:
        raise ValueError("need more reference points than dimensions for a non-singular covariance")
    mean = refs.mean(axis=0)
    covariance = np.cov(refs, rowvar=False)
    inverse_covariance = np.linalg.pinv(covariance)
    delta = point_arr - mean
    distance = float(np.sqrt(delta @ inverse_covariance @ delta.T))
    return {"method": "mahalanobis", "distance": distance, "n_reference": int(refs.shape[0])}


def select_envelope_estimator(reference_points) -> str:
    """Preregistered estimator choice: Gaussian only if goodness-of-fit clears, otherwise assumption-free.

    Returns ``"mahalanobis"``, ``"knn_distance"``, or
    ``"family_conditioned_percentile"`` — chosen from the data by a real
    goodness-of-fit test, never assumed by default.
    """
    refs = np.asarray(reference_points, dtype=float)
    if refs.shape[0] < 3:
        return "family_conditioned_percentile"
    fit = goodness_of_fit(refs)
    if fit["normal_enough"] and refs.shape[0] > refs.shape[1]:
        return "mahalanobis"
    return "knn_distance"
