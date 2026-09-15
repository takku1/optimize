"""Small, reproducible paired ablations over the shared search boundary."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ..evaluators import Evaluator
from .baselines import BASELINES
from .loop import run_bcso


DEFAULT_ABLATIONS = ("no_skill", "simple_rewrite", "focused", "full_bcso")


def run_ablation(
    seed_text: str,
    evaluator: Evaluator,
    *,
    baselines: Iterable[str] = DEFAULT_ABLATIONS,
    seed: int = 0,
    run_root: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run named strategies sequentially with shared evaluation settings.

    Sequential execution is intentional: it minimizes orchestration overhead,
    makes resource use predictable, and keeps each result independently
    auditable. The function reports comparisons; it does not promote a winner.
    """
    names = tuple(dict.fromkeys(str(name) for name in baselines))
    if not names:
        raise ValueError("baselines must not be empty")
    unknown = sorted(set(names) - set(BASELINES))
    if unknown:
        raise ValueError(f"unknown baselines: {unknown}")
    results: dict[str, Any] = {}
    for name in names:
        run_dir = Path(run_root) / name if run_root is not None else None
        result = run_bcso(seed_text, evaluator, baseline=name, seed=seed, run_dir=run_dir, **kwargs)
        results[name] = result["report"]
    best = max(results, key=lambda name: results[name]["selected_utility"])
    return {
        "baselines": list(names), "seed": seed, "synthetic": evaluator.synthetic,
        "winner_by_selected_utility": best, "reports": results,
        "promotion_status": "NOT_EVALUATED",
    }
