"""The default backend: today's synthetic attractor-basin simulation."""
from __future__ import annotations

from .base import EvaluationResult, Evaluator


class SyntheticBasinEvaluator(Evaluator):
    """Wraps ``context.evaluate_sequence`` / ``metrics.basin`` unchanged.

    This is a proposer, not a disposer: its numbers never touch a real model,
    so ``plan`` will not report a supported improvement claim while this
    backend is selected (it is the default).
    """

    synthetic = True
    name = "synthetic"

    def __init__(self, d_model: int = 32, target_name: str | None = None, seed: int = 0,
                 max_tokens: int = 1500):
        from ..context import ContextCache
        from ..metrics import make_attractors

        # contextual_vector runs full (n x n) self-attention with no chunking;
        # at a few thousand tokens the score matrix alone is gigabytes. Cap the
        # sequence length rather than let a large real-world file hang the
        # process (see docs/STATUS.md — found while stress-testing on
        # multi-thousand-token skill files).
        if d_model < 1 or d_model % 4:
            raise ValueError("d_model must be positive and divisible by 4")
        if max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        self.max_tokens = max_tokens
        self.d_model = d_model
        self.attractors = make_attractors(dim=d_model)
        if target_name is None:
            self.target = self.attractors[0]
        else:
            match = [a for a in self.attractors if a.name == target_name]
            if not match:
                raise SystemExit(
                    f"unknown target attractor: {target_name!r}; choose from "
                    f"{[a.name for a in self.attractors]}"
                )
            self.target = match[0]
        self.cache = ContextCache(num_heads=4, seed=seed)

    def evaluate(self, path: str, text: str, *, seed: int = 0, samples: int = 64) -> EvaluationResult:
        from ..context import default_sequence, evaluate_sequence, tokenize

        original_tokens = len(tokenize(text))
        truncated = original_tokens > self.max_tokens
        if truncated:
            text = " ".join(tokenize(text)[: self.max_tokens])

        seq = default_sequence(text, d_model=self.d_model, seed=seed)
        res = evaluate_sequence(seq, self.target, self.attractors, cache=self.cache,
                                seed=seed, samples=samples)
        metadata = {"truncated": True, "original_tokens": original_tokens} if truncated else {}
        return EvaluationResult(
            tokens=int(res.get("tokens", 0)),
            score=float(res.get("score", 0.0)),
            activation=float(res.get("target_activation", 0.0)),
            similarity=float(res.get("similarity", 0.0)),
            reliability=float(res.get("reliability", 0.0)),
            off_target=float(res.get("off_target", 0.0)),
            uncertainty=float(res.get("variance_penalty", 0.0)),
            distortion=float(res.get("distortion", 0.0)),
            metadata=metadata,
        )
