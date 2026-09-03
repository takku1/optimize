"""Evaluator calibration: judge stability and judge/human agreement.

An LLM judge is not an oracle — position bias, verbosity bias, and other
documented evaluator quirks mean a search process can end up optimizing
quirks in its own judge instead of real quality. This module measures whether
a judge (or evaluator backend) can be trusted before its numbers drive
selection, rather than assuming validity by default.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from ..metrics import bootstrap_mean_interval

#: Sentinel used to mark a comparison whose winner flips under presentation
#: order too often to trust, instead of silently reporting a number.
UNSTABLE_FLAG = "EVALUATOR_UNSTABLE"


@dataclass(frozen=True)
class PairwiseJudgment:
    """One judge call comparing two candidates in a stated presentation order."""

    case_id: str
    order: tuple[str, str]
    winner: str

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        if self.winner not in self.order:
            raise ValueError("winner must be one of the two candidates in order")


def position_consistency(
    forward: list[PairwiseJudgment],
    reversed_: list[PairwiseJudgment],
    *,
    min_consistency: float = 0.8,
    min_cases: int = 4,
) -> dict:
    """Fraction of cases where swapping presentation order didn't flip the winner.

    Pairs each ``forward`` judgment (A, B) with the matching ``reversed_``
    judgment (B, A) by ``case_id``. A judge free of position bias names the
    same candidate regardless of which slot it was shown in. Below
    ``min_consistency`` (with at least ``min_cases`` observations), the result
    is flagged :data:`UNSTABLE_FLAG` rather than trusted at face value.
    """
    fwd_by_case = {j.case_id: j for j in forward}
    rev_by_case = {j.case_id: j for j in reversed_}
    shared = sorted(set(fwd_by_case) & set(rev_by_case))
    if not shared:
        raise ValueError("forward and reversed_ share no case_id")
    agreements = []
    for case_id in shared:
        f, r = fwd_by_case[case_id], rev_by_case[case_id]
        if set(f.order) != set(r.order):
            raise ValueError(f"case {case_id!r} does not compare the same two candidates")
        agreements.append(f.winner == r.winner)
    consistency = sum(agreements) / len(agreements)
    unstable = consistency < min_consistency and len(agreements) >= min_cases
    return {
        "n_cases": len(agreements),
        "consistency": consistency,
        "flag": UNSTABLE_FLAG if unstable else None,
    }


def generate_blind_ids(units: list[str], *, seed: int = 0, prefix: str = "run") -> dict[str, str]:
    """Assign each unit (e.g. a transcript path, a ``version:scenario`` key) an opaque id.

    Reproducible (same ``units`` + ``seed`` -> same mapping) but the id
    carries no information about input order or content, so a judge given
    only the id cannot infer which treatment produced a transcript. The
    mapping itself should stay sealed (unread) until after judging is
    complete — see ``docs/governance.md``'s blinding guidance.
    """
    if not units:
        raise ValueError("units must not be empty")
    if len(set(units)) != len(units):
        raise ValueError("units must be unique")
    rng = np.random.default_rng(seed)
    tokens = [f"{prefix}_{hashlib.sha256(f'{seed}:{i}'.encode('utf-8')).hexdigest()[:8]}" for i in range(len(units))]
    shuffled_units = [units[i] for i in rng.permutation(len(units))]
    return dict(zip(shuffled_units, tokens))


def judge_human_agreement(judge_scores, human_scores, *, seed: int = 0, resamples: int = 2000,
                           level: float = 0.95) -> dict:
    """Pearson correlation and mean absolute error between a judge and human scores.

    Bootstraps a confidence interval on the mean absolute error so "the judge
    tracks humans" is a reported, uncertain quantity rather than an assumption.
    """
    judge = np.asarray(judge_scores, dtype=float)
    human = np.asarray(human_scores, dtype=float)
    if judge.shape != human.shape or judge.size < 2:
        raise ValueError("judge_scores and human_scores must be equal-length with at least 2 items")
    correlation = float(np.corrcoef(judge, human)[0, 1]) if np.std(judge) and np.std(human) else float("nan")
    abs_errors = np.abs(judge - human)
    mae_lower, mae_upper = bootstrap_mean_interval(abs_errors, seed=seed, resamples=resamples, level=level)
    return {
        "pearson_r": correlation,
        "mae": float(abs_errors.mean()),
        "mae_ci": {"level": level, "lower": mae_lower, "upper": mae_upper},
        "n": int(judge.size),
    }


def cohens_kappa(labels_a, labels_b) -> float:
    """Unweighted Cohen's kappa for categorical inter-rater agreement (e.g. invariant pass/fail).

    Chance-corrected agreement between two raters (two judges, or a judge and
    a human) on a categorical label — 0 is chance-level agreement, 1 is
    perfect agreement, negative values are worse than chance.
    """
    a, b = list(labels_a), list(labels_b)
    if len(a) != len(b) or not a:
        raise ValueError("labels_a and labels_b must be equal-length and non-empty")
    categories = sorted(set(a) | set(b), key=str)
    index = {category: i for i, category in enumerate(categories)}
    n = len(a)
    confusion = np.zeros((len(categories), len(categories)))
    for x, y in zip(a, b):
        confusion[index[x], index[y]] += 1
    observed_agreement = float(np.trace(confusion) / n)
    row_margin = confusion.sum(axis=1) / n
    col_margin = confusion.sum(axis=0) / n
    expected_agreement = float(np.sum(row_margin * col_margin))
    if expected_agreement == 1.0:
        return 1.0
    return (observed_agreement - expected_agreement) / (1 - expected_agreement)
