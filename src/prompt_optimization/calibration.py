"""Independent rating calibration statistics for the benchmark protocol.

The module intentionally reports estimates and uncertainty; it does not turn
agreement into validity or choose a promotion verdict. Numeric dimensions use
the two-way random-effects absolute-agreement ICC (ICC(2,1)); categorical stage
uses Fleiss' kappa for a fully crossed panel.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

CORE_DIMENSIONS = (
    "clarity_definition", "problem_value_validity", "differentiation",
    "feasibility", "execution_completion", "evidence_validation",
    "risk_exposure", "impact_upside",
)


def _matrix(rows: Sequence[Mapping[str, Any]], key: str) -> np.ndarray:
    artifacts = sorted({str(row.get("artifact_id", "")) for row in rows})
    raters = sorted({str(row.get("rater_id", "")) for row in rows})
    if not artifacts or "" in artifacts or not raters or "" in raters:
        raise ValueError("ratings require non-empty artifact_id and rater_id")
    values = {(str(row["artifact_id"]), str(row["rater_id"])): row.get(key) for row in rows}
    if len(values) != len(rows):
        raise ValueError("each artifact/rater pair must occur once")
    missing = [(a, r) for a in artifacts for r in raters if (a, r) not in values]
    if missing:
        raise ValueError(f"ratings must be fully crossed; missing {missing[0]}")
    try:
        return np.asarray([[float(values[(a, r)]) for r in raters] for a in artifacts], dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"rating values for {key!r} must be numeric") from exc


def icc_absolute_agreement(values: np.ndarray) -> float:
    """Return ICC(2,1), two-way random absolute agreement, single measure."""
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2 or min(matrix.shape) < 2:
        raise ValueError("ICC requires at least two artifacts and two raters")
    n, k = matrix.shape
    grand = matrix.mean()
    row_means = matrix.mean(axis=1)
    col_means = matrix.mean(axis=0)
    ms_rows = k * np.sum((row_means - grand) ** 2) / (n - 1)
    ms_cols = n * np.sum((col_means - grand) ** 2) / (k - 1)
    residual = matrix - row_means[:, None] - col_means[None, :] + grand
    ms_error = np.sum(residual ** 2) / ((n - 1) * (k - 1))
    denominator = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
    return float((ms_rows - ms_error) / denominator) if denominator else 1.0


def fleiss_kappa(labels: Sequence[Sequence[Any]]) -> float:
    """Return Fleiss' kappa for a complete subject-by-rater label matrix."""
    matrix = [list(row) for row in labels]
    if not matrix or min(len(row) for row in matrix) < 2:
        raise ValueError("Fleiss kappa requires at least two subjects and raters")
    raters = len(matrix[0])
    if any(len(row) != raters for row in matrix):
        raise ValueError("all subjects must have the same number of ratings")
    categories = sorted({label for row in matrix for label in row}, key=str)
    proportions = np.asarray([[row.count(category) for category in categories] for row in matrix], dtype=float) / raters
    agreement = (np.sum(proportions ** 2, axis=1) * raters - 1) / (raters - 1)
    p_bar = float(np.mean(agreement))
    p_e = float(np.sum(np.mean(proportions, axis=0) ** 2))
    return float((p_bar - p_e) / (1 - p_e)) if p_e < 1 else 1.0


def _bootstrap_ci(values: np.ndarray, statistic: Any, *, resamples: int, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(resamples):
        indices = rng.integers(0, len(values), size=len(values))
        try:
            estimates.append(float(statistic(values[indices])))
        except ValueError:
            continue
    if not estimates:
        return (float("nan"), float("nan"))
    return tuple(float(x) for x in np.quantile(estimates, [0.025, 0.975]))


def agreement_report(
    rows: Sequence[Mapping[str, Any]], *, dimensions: Sequence[str] = CORE_DIMENSIONS,
    bootstrap_resamples: int = 1000, seed: int = 0,
) -> dict[str, Any]:
    """Compute a calibration report from fully crossed blinded rating rows."""
    if bootstrap_resamples < 0:
        raise ValueError("bootstrap_resamples must be non-negative")
    if not rows:
        raise ValueError("ratings must not be empty")
    artifact_ids = sorted({str(row.get("artifact_id", "")) for row in rows})
    rater_ids = sorted({str(row.get("rater_id", "")) for row in rows})
    dimensions_report: dict[str, Any] = {}
    for offset, dimension in enumerate(dimensions):
        values = _matrix(rows, dimension)
        estimate = icc_absolute_agreement(values)
        ci = _bootstrap_ci(values, icc_absolute_agreement, resamples=bootstrap_resamples, seed=seed + offset)
        dimensions_report[dimension] = {
            "statistic": "ICC(2,1)", "estimate": estimate,
            "ci_95": list(ci), "n_artifacts": values.shape[0], "n_raters": values.shape[1],
        }

    stage_matrix = [[row.get("stage") for row in rows if str(row["artifact_id"]) == artifact]
                    for artifact in artifact_ids]
    if any(any(value is None for value in row) for row in stage_matrix):
        raise ValueError("every rating must include stage for categorical agreement")
    return {
        "n_artifacts": len(artifact_ids), "n_raters": len(rater_ids),
        "design": "fully_crossed", "stage_statistic": "Fleiss_kappa",
        "stage": {"estimate": fleiss_kappa(stage_matrix)},
        "dimensions": dimensions_report,
        "interpretation": "agreement is reliability evidence, not validity evidence",
    }
