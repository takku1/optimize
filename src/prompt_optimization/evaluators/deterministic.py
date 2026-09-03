"""Pre-registered, mechanically-checkable success criteria for a scenario.

"The effort should be calibrated" is not observable on its own — the first
empirical run (`output/claude skills/architectural-reasoning/
empirical-run-2026-08-29/`) used a 400-word threshold chosen in a throwaway
runner script, after the scenario suite already existed but before any
transcript did. That was good enough to avoid mid-run tuning, but it wasn't
*pre-registered where a reviewer would find it*. ``SuccessBand`` fixes that:
the observable bound lives in the scenario fixture itself
(``Scenario.metadata["success_band"]``), reviewable and versioned alongside
the scenario, and is evaluated deterministically wherever possible per
requirement #5 of that empirical run's own design (deterministic checks
dominate; semantic judgment only for what genuinely requires it).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SuccessBand:
    """An observable, falsifiable expectation on a response's shape."""

    min_words: int | None = None
    max_words: int | None = None
    forbidden_phrases: tuple[str, ...] = ()
    required_any_phrases: tuple[str, ...] = ()
    required_all_phrases: tuple[str, ...] = ()
    min_distinct_matches: int | None = None

    def __post_init__(self) -> None:
        if self.min_words is not None and self.min_words < 0:
            raise ValueError("min_words must be non-negative")
        if self.max_words is not None and self.max_words < 0:
            raise ValueError("max_words must be non-negative")
        if self.min_words is not None and self.max_words is not None and self.min_words > self.max_words:
            raise ValueError("min_words must not exceed max_words")
        if self.min_distinct_matches is not None and self.min_distinct_matches < 0:
            raise ValueError("min_distinct_matches must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_words": self.min_words,
            "max_words": self.max_words,
            "forbidden_phrases": list(self.forbidden_phrases),
            "required_any_phrases": list(self.required_any_phrases),
            "required_all_phrases": list(self.required_all_phrases),
            "min_distinct_matches": self.min_distinct_matches,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SuccessBand":
        return cls(
            min_words=value.get("min_words"),
            max_words=value.get("max_words"),
            forbidden_phrases=tuple(value.get("forbidden_phrases", ())),
            required_any_phrases=tuple(value.get("required_any_phrases", ())),
            required_all_phrases=tuple(value.get("required_all_phrases", ())),
            min_distinct_matches=value.get("min_distinct_matches"),
        )


def check_success_band(text: str, band: SuccessBand) -> dict[str, Any]:
    """Evaluate ``text`` against a pre-registered :class:`SuccessBand`, deterministically.

    Returns every measured quantity alongside the pass/fail verdict, so a
    failure is auditable (*which* bound tripped), not just a boolean.
    """
    words = len(text.split())
    lowered = text.lower()
    violations: list[str] = []

    if band.min_words is not None and words < band.min_words:
        violations.append(f"word_count {words} < min_words {band.min_words}")
    if band.max_words is not None and words > band.max_words:
        violations.append(f"word_count {words} > max_words {band.max_words}")
    present_forbidden = [phrase for phrase in band.forbidden_phrases if phrase.lower() in lowered]
    if present_forbidden:
        violations.append(f"forbidden phrase(s) present: {present_forbidden}")
    if band.required_any_phrases and not any(phrase.lower() in lowered for phrase in band.required_any_phrases):
        violations.append(f"none of the required phrases present: {list(band.required_any_phrases)}")
    required_all_missing = [phrase for phrase in band.required_all_phrases if phrase.lower() not in lowered]
    if required_all_missing:
        violations.append(f"required phrase(s) missing: {required_all_missing}")
    distinct_matches = sum(phrase.lower() in lowered for phrase in band.required_any_phrases)
    if band.min_distinct_matches is not None and distinct_matches < band.min_distinct_matches:
        violations.append(f"distinct required phrase count {distinct_matches} < min_distinct_matches "
                          f"{band.min_distinct_matches}")

    return {
        "word_count": words,
        "distinct_required_phrase_matches": distinct_matches,
        "passed": not violations,
        "violations": violations,
    }
