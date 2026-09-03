"""Backend selection: turns CLI flags into an ``Evaluator`` instance."""
from __future__ import annotations

from .base import Evaluator

BACKENDS = ("synthetic", "rubric", "callable")


def load_evaluator(
    backend: str,
    *,
    d_model: int = 32,
    target_name: str | None = None,
    seed: int = 0,
    rubric_file: str | None = None,
    evaluator_fn: str | None = None,
    max_tokens: int = 1500,
) -> Evaluator:
    if backend == "synthetic":
        from .synthetic import SyntheticBasinEvaluator
        return SyntheticBasinEvaluator(d_model=d_model, target_name=target_name, seed=seed,
                                       max_tokens=max_tokens)
    if backend == "rubric":
        if not rubric_file:
            raise SystemExit("--backend rubric requires --rubric-file PATH")
        from .rubric import RubricEvaluator
        return RubricEvaluator(rubric_file)
    if backend == "callable":
        if not evaluator_fn:
            raise SystemExit("--backend callable requires --evaluator-fn MODULE:FUNC")
        from .callable_backend import CallableEvaluator
        return CallableEvaluator(evaluator_fn)
    raise SystemExit(f"unknown backend: {backend!r}; choose from {BACKENDS}")
