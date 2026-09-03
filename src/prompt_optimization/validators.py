"""Composable, model-free validation and aggregation for candidate outputs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol

from .evaluators import SuccessBand, check_success_band


@dataclass(frozen=True)
class ValidationResult:
    scenario_id: str
    status: str  # passed, failed, unresolved
    evidence: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.status not in {"passed", "failed", "unresolved"}:
            raise ValueError("status must be passed, failed, or unresolved")

    def to_dict(self) -> dict[str, Any]:
        return {"scenario_id": self.scenario_id, "status": self.status,
                "evidence": dict(self.evidence)}


class ScenarioExecutor(Protocol):
    """Provider seam: execute a skill against one scenario and rollout."""

    def __call__(self, skill_text: str, scenario: Any, rollout: int) -> str: ...


def validate_response(text: str, scenario: Any) -> ValidationResult:
    """Run only executable rules declared by ``scenario``.

    A scenario without a success band is unresolved rather than vacuously
    passing. Semantic review can add evidence later without changing this rule.
    """
    scenario_id = str(getattr(scenario, "id", ""))
    metadata = getattr(scenario, "metadata", {}) or {}
    if isinstance(scenario, dict):
        scenario_id = str(scenario.get("id", ""))
        metadata = scenario.get("metadata", {})
    raw_band = metadata.get("success_band") if isinstance(metadata, Mapping) else None
    if not isinstance(raw_band, Mapping):
        return ValidationResult(scenario_id, "unresolved", {"reason": "no executable success_band"})
    checks = check_success_band(text, SuccessBand.from_dict(dict(raw_band)))
    return ValidationResult(scenario_id, "passed" if checks["passed"] else "failed", checks)


def aggregate_validations(results: Iterable[ValidationResult], *, tokens: int = 0) -> dict[str, Any]:
    """Produce a conservative score suitable for optimizer acceptance."""
    rows = list(results)
    if not rows:
        raise ValueError("at least one validation result is required")
    passed = sum(r.status == "passed" for r in rows)
    failed = sum(r.status == "failed" for r in rows)
    unresolved = sum(r.status == "unresolved" for r in rows)
    utility = passed / len(rows)
    return {
        "utility": utility,
        "tokens": tokens,
        "information_density": utility / max(tokens, 1),
        "hard_invariants_passed": failed == 0 and unresolved == 0,
        "passed": passed,
        "failed": failed,
        "unresolved": unresolved,
        "validations": [r.to_dict() for r in rows],
    }


def evaluate_candidate(skill_text: str, scenarios: Iterable[Any], executor: ScenarioExecutor,
                       *, rollouts: int = 1) -> dict[str, Any]:
    """Execute and internally validate one candidate across a scenario matrix."""
    if rollouts < 1:
        raise ValueError("rollouts must be positive")
    scenario_list = list(scenarios)
    if not scenario_list:
        raise ValueError("scenarios must not be empty")
    results: list[ValidationResult] = []
    total_tokens = 0
    for scenario in scenario_list:
        for rollout in range(1, rollouts + 1):
            response = executor(skill_text, scenario, rollout)
            if not isinstance(response, str):
                raise ValueError("scenario executor must return text")
            total_tokens += len(response.split())
            results.append(validate_response(response, scenario))
    return aggregate_validations(results, tokens=total_tokens)


def evaluate_neighborhood(
    skill_text: str,
    scenarios: Iterable[Any],
    executor: ScenarioExecutor,
    variants: Iterable[str] | Callable[[str], Iterable[str]],
    *,
    rollouts: int = 1,
) -> dict[str, Any]:
    """Evaluate a candidate and controlled variants as a robustness bundle.

    Variants are caller-supplied because the library cannot prove that a
    paraphrase preserves meaning. The result exposes mean, worst-case, and
    variance so selection can prefer a stable semantic neighborhood.
    """
    neighborhood = variants(skill_text) if callable(variants) else variants
    texts = [skill_text, *list(neighborhood)]
    if not all(isinstance(text, str) and text.strip() for text in texts):
        raise ValueError("neighborhood variants must be non-empty strings")
    scores = [evaluate_candidate(text, scenarios, executor, rollouts=rollouts) for text in texts]
    utilities = [float(score["utility"]) for score in scores]
    mean = sum(utilities) / len(utilities)
    variance = sum((value - mean) ** 2 for value in utilities) / len(utilities)
    stddev = variance ** 0.5
    return {
        "utility": mean,
        "neighborhood_mean": mean,
        "neighborhood_worst": min(utilities),
        "neighborhood_stddev": stddev,
        "neighborhood_robustness": mean - stddev,
        "information_density": mean / max(sum(int(score["tokens"]) for score in scores) // len(scores), 1),
        "tokens": sum(int(score["tokens"]) for score in scores) // len(scores),
        "hard_invariants_passed": all(score["hard_invariants_passed"] is True for score in scores),
        "neighborhood_size": len(scores),
        "members": scores,
    }
