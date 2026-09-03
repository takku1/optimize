"""The ``Evaluator`` protocol every backend implements."""
from __future__ import annotations

import abc
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvaluationResult:
    """One backend's judgment of one candidate text.

    ``activation`` and ``similarity`` are meaningful for the synthetic
    attractor backend (predicted basin activation, cosine alignment); other
    backends leave them at their defaults and report through ``score`` and
    ``metadata`` instead. ``distortion`` defaults to ``1 - reliability`` when
    not supplied, matching the toy proxy documented in
    ``docs/research-landscape.md``.
    """

    tokens: int
    score: float
    activation: float = 0.0
    similarity: float = 0.0
    reliability: float = 1.0
    off_target: float = 0.0
    uncertainty: float = 0.0
    distortion: float | None = None
    tier: str = "deterministic"
    metadata: dict = field(default_factory=dict)

    #: Dominance order for combining judgments across the evaluator stack:
    #: deterministic checks should win over a model judge, which should win
    #: over an unresolved human arbitration placeholder, whenever more than
    #: one tier scores the same thing. Lower is more authoritative.
    _TIER_RANK = {"deterministic": 0, "model": 1, "human": 2}

    def __post_init__(self) -> None:
        if self.tokens < 0:
            raise ValueError("tokens must be non-negative")
        if self.tier not in self._TIER_RANK:
            raise ValueError(f"tier must be one of {sorted(self._TIER_RANK)}, got {self.tier!r}")
        if self.distortion is None:
            object.__setattr__(self, "distortion", 1.0 - self.reliability)
        numeric = {
            "score": self.score,
            "activation": self.activation,
            "similarity": self.similarity,
            "reliability": self.reliability,
            "off_target": self.off_target,
            "uncertainty": self.uncertainty,
            "distortion": self.distortion,
        }
        if any(not math.isfinite(float(value)) for value in numeric.values()):
            raise ValueError("evaluation metrics must be finite")
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError("reliability must be in [0, 1]")
        if self.off_target < 0 or self.uncertainty < 0:
            raise ValueError("off_target and uncertainty must be non-negative")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")


class Evaluator(abc.ABC):
    """A source of behavioral judgments for candidate prompt text.

    ``synthetic = True`` marks backends whose score never touched a real
    model or human judgment (only the built-in attractor simulation
    qualifies). The CLI uses this flag to decide whether a ``plan`` run may
    report a supported improvement claim.
    """

    synthetic: bool = True
    name: str = "evaluator"

    @abc.abstractmethod
    def evaluate(self, path: str, text: str, *, seed: int = 0, samples: int = 64) -> EvaluationResult:
        """Score ``text`` (sourced from ``path``) and return the judgment."""
        raise NotImplementedError
