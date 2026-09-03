"""A human-judged-rubric backend: real evidence, no network access required.

Reads pre-recorded judgments (produced by a person, or by a real model run the
user carried out separately) from a JSON file keyed by the same display path
``iter_text_files`` produces. This is the cheapest way to plug a genuinely
real held-out evaluation into ``plan`` without this project taking on a
model/API dependency of its own.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import EvaluationResult, Evaluator
from ..metrics import estimate_tokens


class RubricEvaluator(Evaluator):
    """Looks up ``{"score": ..., ...}`` per file from a JSON rubric.

    Rubric file shape::

        {
          "path/to/file.py": {"score": 0.8, "reliability": 0.9, "notes": "..."},
          ...
        }

    Only ``score`` is required; the rest default to values that make the
    candidate look neutral (not falsely reliable) until a real judgment
    supplies them.
    """

    synthetic = False
    name = "rubric"

    def __init__(self, rubric_path: str):
        raw = Path(rubric_path).read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("rubric file must be a JSON object keyed by file path")
        self._by_path = data

    def evaluate(self, path: str, text: str, *, seed: int = 0, samples: int = 64) -> EvaluationResult:
        entry = self._by_path.get(path)
        if entry is None:
            raise KeyError(
                f"no rubric judgment recorded for {path!r}; add an entry to the "
                "rubric file before planning against it"
            )
        score = float(entry["score"])
        tokens = int(entry["tokens"]) if "tokens" in entry else estimate_tokens(text)
        return EvaluationResult(
            tokens=tokens,
            score=score,
            activation=float(entry.get("activation", score)),
            reliability=float(entry.get("reliability", 1.0)),
            off_target=float(entry.get("off_target", 0.0)),
            uncertainty=float(entry.get("uncertainty", 0.0)),
            tier=str(entry.get("tier", "human")),
            metadata={"notes": entry.get("notes", "")},
        )
