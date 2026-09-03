"""A backend that delegates to a user-supplied Python callable.

This is the general-purpose seam: point ``--evaluator-fn`` at
``mymodule:my_eval`` and ``my_eval(text: str) -> dict`` can call a real model
API, run a task harness, or shell out to anything else. This project does not
ship an OpenAI/Anthropic adapter itself --- that would mean making network
calls and spending the user's API budget on their behalf without being asked
--- but this is where such an adapter plugs in.
"""
from __future__ import annotations

import importlib

from .base import EvaluationResult, Evaluator
from ..metrics import estimate_tokens


class CallableEvaluator(Evaluator):
    synthetic = False
    name = "callable"

    def __init__(self, dotted_path: str):
        module_name, sep, func_name = dotted_path.partition(":")
        if not sep or not module_name or not func_name:
            raise ValueError(
                "--evaluator-fn must be MODULE:FUNC, e.g. mymodule:my_eval"
            )
        module = importlib.import_module(module_name)
        try:
            self._fn = getattr(module, func_name)
        except AttributeError as exc:
            raise ValueError(f"{module_name!r} has no attribute {func_name!r}") from exc
        if not callable(self._fn):
            raise ValueError(f"{dotted_path!r} does not resolve to a callable")

    def evaluate(self, path: str, text: str, *, seed: int = 0, samples: int = 64) -> EvaluationResult:
        out = self._fn(text)
        if isinstance(out, EvaluationResult):
            return out
        if not isinstance(out, dict) or "score" not in out:
            raise ValueError(
                "evaluator function must return an EvaluationResult or a dict "
                "containing at least 'score'"
            )
        score = float(out["score"])
        tokens = int(out["tokens"]) if "tokens" in out else estimate_tokens(text)
        return EvaluationResult(
            tokens=tokens,
            score=score,
            activation=float(out.get("activation", score)),
            reliability=float(out.get("reliability", 1.0)),
            off_target=float(out.get("off_target", 0.0)),
            uncertainty=float(out.get("uncertainty", 0.0)),
            tier=str(out.get("tier", "model")),
            metadata=dict(out.get("metadata", {})),
        )
