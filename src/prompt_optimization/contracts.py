"""Intent contracts and paired behavioral comparison.

The text metrics in :mod:`prompt_optimization.metrics` are useful for proposing
candidates, but they cannot establish that a rewritten skill still behaves as
intended.  This module defines a small, serializable contract and compares
paired scenario results supplied by a human or a real evaluator.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from .metrics import bootstrap_mean_interval


@dataclass(frozen=True)
class HardInvariant:
    """A contract predicate with a minimum acceptable pass rate."""

    id: str
    description: str
    min_pass_rate: float = 1.0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("invariant id must not be empty")
        if not 0.0 <= self.min_pass_rate <= 1.0:
            raise ValueError("min_pass_rate must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "min_pass_rate": self.min_pass_rate,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HardInvariant":
        if not isinstance(value, dict):
            raise ValueError("each hard invariant must be an object")
        return cls(
            id=str(value.get("id", "")),
            description=str(value.get("description", "")),
            min_pass_rate=float(value.get("min_pass_rate", 1.0)),
        )


@dataclass(frozen=True)
class IntentContract:
    """Behavioral specification independent of a skill's section order."""

    id: str
    outcome: str
    schema_version: int = 1
    activation: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    inputs_and_preconditions: tuple[str, ...] = ()
    hard_invariants: tuple[HardInvariant, ...] = ()
    decision_points: tuple[str, ...] = ()
    state: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    validation: tuple[str, ...] = ()
    failure_recovery: tuple[str, ...] = ()
    quality_heuristics: tuple[str, ...] = ()
    examples_and_calibration: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"unsupported intent contract schema: {self.schema_version}")
        if not self.id.strip():
            raise ValueError("contract id must not be empty")
        if not self.outcome.strip():
            raise ValueError("contract outcome must not be empty")
        ids = [item.id for item in self.hard_invariants]
        if len(ids) != len(set(ids)):
            raise ValueError("hard invariant ids must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "outcome": self.outcome,
            "activation": list(self.activation),
            "exclusions": list(self.exclusions),
            "inputs_and_preconditions": list(self.inputs_and_preconditions),
            "hard_invariants": [item.to_dict() for item in self.hard_invariants],
            "decision_points": list(self.decision_points),
            "state": list(self.state),
            "side_effects": list(self.side_effects),
            "outputs": list(self.outputs),
            "validation": list(self.validation),
            "failure_recovery": list(self.failure_recovery),
            "quality_heuristics": list(self.quality_heuristics),
            "examples_and_calibration": list(self.examples_and_calibration),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "IntentContract":
        if not isinstance(value, dict):
            raise ValueError("intent contract must be a JSON object")

        def strings(key: str) -> tuple[str, ...]:
            raw = value.get(key, [])
            if not isinstance(raw, list):
                raise ValueError(f"contract field {key!r} must be a list")
            return tuple(str(item) for item in raw)

        raw_invariants = value.get("hard_invariants", [])
        if not isinstance(raw_invariants, list):
            raise ValueError("hard_invariants must be a list")
        return cls(
            schema_version=int(value.get("schema_version", 1)),
            id=str(value.get("id", "")),
            outcome=str(value.get("outcome", "")),
            activation=strings("activation"),
            exclusions=strings("exclusions"),
            inputs_and_preconditions=strings("inputs_and_preconditions"),
            hard_invariants=tuple(HardInvariant.from_dict(item) for item in raw_invariants),
            decision_points=strings("decision_points"),
            state=strings("state"),
            side_effects=strings("side_effects"),
            outputs=strings("outputs"),
            validation=strings("validation"),
            failure_recovery=strings("failure_recovery"),
            quality_heuristics=strings("quality_heuristics"),
            examples_and_calibration=strings("examples_and_calibration"),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True)
class ScenarioResult:
    """One observed original/candidate result for a held-out scenario."""

    scenario_id: str
    utility: float
    invariants: dict[str, bool]
    costs: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id must not be empty")
        if not math.isfinite(float(self.utility)):
            raise ValueError("utility must be finite")
        if any(not isinstance(value, bool) for value in self.invariants.values()):
            raise ValueError("invariant results must be booleans")
        if any(not math.isfinite(float(value)) for value in self.costs.values()):
            raise ValueError("cost values must be finite")

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "utility": self.utility,
            "invariants": self.invariants,
            "costs": self.costs,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ScenarioResult":
        if not isinstance(value, dict):
            raise ValueError("scenario result must be a JSON object")
        if "utility" not in value and "score" not in value:
            raise ValueError("scenario result requires utility (or score)")
        invariants = value.get("invariants", {})
        costs = value.get("costs", {})
        if not isinstance(invariants, dict) or not isinstance(costs, dict):
            raise ValueError("invariants and costs must be objects")
        utility = value["utility"] if "utility" in value else value.get("score")
        if utility is None:
            raise ValueError("scenario result requires utility (or score)")
        return cls(
            scenario_id=str(value.get("scenario_id", "")),
            utility=float(utility),
            invariants={str(key): item for key, item in invariants.items()},
            costs={str(key): float(item) for key, item in costs.items()},
            metadata=dict(value.get("metadata", {})),
        )


def aggregate_rollout_results(results: Iterable[ScenarioResult]) -> ScenarioResult:
    """Collapse K>=1 same-scenario rollout results into one :class:`ScenarioResult`.

    ``compare_contract_results`` requires exactly one row per scenario_id, so
    multi-rollout evidence (K independent generations of the same
    version/scenario unit) must be reduced to one row before comparison. This
    is that reduction, not a replacement for reporting per-rollout variance
    separately.

    Utility and costs are averaged across rollouts. An invariant is recorded
    as passed only if it passed on *every* rollout -- a hard invariant that
    only holds "most of the time" has not actually been demonstrated to hold,
    so a single-rollout failure fails the aggregate. Each invariant's raw
    per-rollout pass rate is preserved in ``metadata["invariant_pass_rate"]``
    so an all-or-nothing gate never hides a partial result. Per-rollout
    utility values are preserved in ``metadata["rollout_utilities"]`` so a
    caller can run a nested/hierarchical uncertainty estimate afterward.
    """
    rows = list(results)
    if not rows:
        raise ValueError("aggregate_rollout_results requires at least one result")
    scenario_ids = {row.scenario_id for row in rows}
    if len(scenario_ids) != 1:
        raise ValueError(f"all rollouts must share one scenario_id, got {sorted(scenario_ids)}")

    invariant_ids = set()
    for row in rows:
        invariant_ids.update(row.invariants)
    invariants: dict[str, bool] = {}
    pass_rate: dict[str, float] = {}
    for inv_id in invariant_ids:
        votes = [bool(row.invariants.get(inv_id, False)) for row in rows]
        pass_rate[inv_id] = sum(votes) / len(votes)
        invariants[inv_id] = all(votes)

    cost_keys = set()
    for row in rows:
        cost_keys.update(row.costs)
    costs = {key: sum(row.costs.get(key, 0.0) for row in rows) / len(rows) for key in cost_keys}

    utilities = [row.utility for row in rows]
    metadata: dict[str, Any] = {
        "rollout_count": len(rows),
        "rollout_utilities": utilities,
        "invariant_pass_rate": pass_rate,
        "per_rollout_metadata": [row.metadata for row in rows],
    }

    return ScenarioResult(
        scenario_id=rows[0].scenario_id,
        utility=sum(utilities) / len(utilities),
        invariants=invariants,
        costs=costs,
        metadata=metadata,
    )


@dataclass(frozen=True)
class Scenario:
    """A held-out request used to exercise an intent contract."""

    id: str
    request: str
    expected_invariants: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    expected_outcome: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("scenario id must not be empty")
        if not self.request.strip():
            raise ValueError("scenario request must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request": self.request,
            "expected_invariants": list(self.expected_invariants),
            "tags": list(self.tags),
            "preconditions": list(self.preconditions),
            "expected_outcome": self.expected_outcome,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Scenario":
        if not isinstance(value, dict):
            raise ValueError("scenario must be a JSON object")

        def strings(key: str) -> tuple[str, ...]:
            raw = value.get(key, [])
            if not isinstance(raw, list):
                raise ValueError(f"scenario field {key!r} must be a list")
            return tuple(str(item) for item in raw)

        return cls(
            id=str(value.get("id", "")),
            request=str(value.get("request", "")),
            expected_invariants=strings("expected_invariants"),
            tags=strings("tags"),
            preconditions=strings("preconditions"),
            expected_outcome=str(value.get("expected_outcome", "")),
            metadata=dict(value.get("metadata", {})),
        )


def compare_contract_results(
    contract: IntentContract,
    baseline: Iterable[ScenarioResult],
    candidate: Iterable[ScenarioResult],
    *,
    noninferiority_margin: float = 0.05,
    seed: int = 0,
    bootstrap_resamples: int = 2000,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Compare paired scenario results and apply hard contract gates.

    The candidate is accepted only when every declared invariant meets its
    minimum observed pass rate and the lower bootstrap bound of the paired
    utility delta is no worse than ``-noninferiority_margin``.

    Each invariant's report carries a ``status`` distinguishing *why* it
    failed, not just *that* it did: ``"regression"`` means the baseline met
    its floor and the candidate no longer does (a real, candidate-caused
    loss); ``"floor_not_met"`` means the candidate failed a floor the
    baseline never met either (a pre-existing gap, not something the
    candidate broke). Both still block ``accepted`` — the floor is absolute,
    not relative — but only ``"regression"`` should ever be described as the
    candidate having "lost" the invariant. Conflating the two was a real
    finding from this project's first empirical run (2026-08-29,
    `output/claude skills/architectural-reasoning/empirical-run-2026-08-29/REPORT.md`).
    """
    if noninferiority_margin < 0:
        raise ValueError("noninferiority_margin must be non-negative")
    baseline_rows = list(baseline)
    candidate_rows = list(candidate)
    if not baseline_rows or not candidate_rows:
        raise ValueError("baseline and candidate results must be non-empty")

    def index(rows: list[ScenarioResult], label: str) -> dict[str, ScenarioResult]:
        indexed: dict[str, ScenarioResult] = {}
        for row in rows:
            if row.scenario_id in indexed:
                raise ValueError(f"duplicate {label} scenario_id: {row.scenario_id}")
            indexed[row.scenario_id] = row
        return indexed

    base = index(baseline_rows, "baseline")
    cand = index(candidate_rows, "candidate")
    if set(base) != set(cand):
        missing = sorted(set(base) - set(cand))
        extra = sorted(set(cand) - set(base))
        raise ValueError(f"scenario sets differ: missing={missing}, extra={extra}")

    ordered_ids = sorted(base)
    deltas = [cand[sid].utility - base[sid].utility for sid in ordered_ids]
    delta_mean = sum(deltas) / len(deltas)
    delta_interval = bootstrap_mean_interval(
        deltas, seed=seed, resamples=bootstrap_resamples, level=confidence
    )
    utility_noninferior = delta_interval[0] >= -noninferiority_margin

    invariant_report: dict[str, dict[str, Any]] = {}
    invariants_passed = True
    for invariant in contract.hard_invariants:
        base_rate = sum(bool(base[sid].invariants.get(invariant.id, False)) for sid in ordered_ids) / len(ordered_ids)
        cand_rate = sum(bool(cand[sid].invariants.get(invariant.id, False)) for sid in ordered_ids) / len(ordered_ids)
        baseline_passed = base_rate >= invariant.min_pass_rate
        passed = cand_rate >= invariant.min_pass_rate
        invariants_passed = invariants_passed and passed
        if passed:
            status = "passed"
        elif baseline_passed:
            status = "regression"
        else:
            status = "floor_not_met"
        invariant_report[invariant.id] = {
            "description": invariant.description,
            "min_pass_rate": invariant.min_pass_rate,
            "baseline_pass_rate": base_rate,
            "candidate_pass_rate": cand_rate,
            "baseline_passed": baseline_passed,
            "passed": passed,
            "status": status,
        }

    cost_keys = sorted(set().union(*(row.costs.keys() for row in baseline_rows + candidate_rows)))
    costs: dict[str, dict[str, float]] = {}
    for key in cost_keys:
        base_mean = sum(row.costs.get(key, 0.0) for row in baseline_rows) / len(baseline_rows)
        cand_mean = sum(row.costs.get(key, 0.0) for row in candidate_rows) / len(candidate_rows)
        costs[key] = {"baseline_mean": base_mean, "candidate_mean": cand_mean, "delta": cand_mean - base_mean}

    return {
        "contract_id": contract.id,
        "schema_version": contract.schema_version,
        "scenario_count": len(ordered_ids),
        "hard_invariants": invariant_report,
        "utility": {
            "baseline_mean": sum(row.utility for row in baseline_rows) / len(baseline_rows),
            "candidate_mean": sum(row.utility for row in candidate_rows) / len(candidate_rows),
            "delta_mean": delta_mean,
            "delta_interval": {"level": confidence, "lower": delta_interval[0], "upper": delta_interval[1]},
            "noninferiority_margin": noninferiority_margin,
            "noninferior": utility_noninferior,
        },
        "costs": costs,
        "accepted": invariants_passed and utility_noninferior,
    }


def stratified_utility_report(
    results: Iterable[ScenarioResult],
    *,
    split_key: str = "split",
    seed: int = 0,
    bootstrap_resamples: int = 2000,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Report utility mean + CI separately per declared split (e.g. IID vs OOD).

    The split label is read from ``ScenarioResult.metadata[split_key]``
    (``"unspecified"`` when absent) — an additive convention, not a schema
    change. Pooling an in-distribution and a deliberately shifted split
    together can hide a rewrite that generalizes well on familiar tasks but
    fails under real distribution shift; this keeps them apart.
    """
    rows = list(results)
    if not rows:
        raise ValueError("results must not be empty")
    by_split: dict[str, list[float]] = {}
    for row in rows:
        split = str(row.metadata.get(split_key, "unspecified"))
        by_split.setdefault(split, []).append(row.utility)
    report: dict[str, Any] = {}
    for split, values in by_split.items():
        lower, upper = bootstrap_mean_interval(values, seed=seed, resamples=bootstrap_resamples, level=confidence)
        report[split] = {
            "n": len(values),
            "mean": sum(values) / len(values),
            "ci": {"level": confidence, "lower": lower, "upper": upper},
        }
    return report


def ablation_deltas(full_score: float, component_scores: dict[str, float]) -> dict[str, float]:
    """Marginal contribution of each component: ``ΔU_-i = U(S) - U(S \\ {i})``.

    ``component_scores`` maps component id to the measured score of the skill
    with that one component removed (everything else held fixed). This is the
    single-removal special case of Shapley attribution
    (:func:`~prompt_optimization.attribution.shapley_values` estimates the
    full averaged-over-all-coalitions version); no new attribution math is
    needed here, just the arithmetic for a cheaper one-at-a-time sweep. A
    near-zero delta suggests (not proves — components interact) that a
    component may be safe to cut.
    """
    if not component_scores:
        raise ValueError("component_scores must not be empty")
    return {component: full_score - score for component, score in component_scores.items()}


class DefectType(str, Enum):
    """Named defect classes for counterfactual insertion testing.

    The inverse of ablation: deliberately inject a known defect into a mature
    skill and check whether review (human or automated) catches the resulting
    degradation, instead of only ever testing deletion safety.
    """

    REDUNDANT = "redundant"
    CONTRADICTORY = "contradictory"
    IRRELEVANT = "irrelevant"
    VERBOSE = "verbose"
    MISLEADING = "misleading"
    UNNECESSARY_STEP = "unnecessary_step"
    MALFORMED_TRIGGER = "malformed_trigger"


@dataclass(frozen=True)
class CounterfactualCase:
    """One deliberately-defective variant of a mature skill, and whether it was caught."""

    base_id: str
    defect: DefectType
    variant_id: str
    detected: bool | None = None

    def __post_init__(self) -> None:
        if not self.base_id.strip() or not self.variant_id.strip():
            raise ValueError("base_id and variant_id must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_id": self.base_id,
            "defect": self.defect.value,
            "variant_id": self.variant_id,
            "detected": self.detected,
        }


def counterfactual_detection_rate(cases: list[CounterfactualCase]) -> dict[str, float]:
    """Fraction of injected defects detected, grouped by defect type.

    A high detection rate validates the *optimizer or reviewer*, not the
    skill under test — this measures BCSO's ability to recognize skill
    defects (handoff doc's optimizer-validation suite), a separate question
    from whether any particular skill is good.
    """
    scored = [case for case in cases if case.detected is not None]
    if not scored:
        raise ValueError("no scored cases (every case has detected=None)")
    by_defect: dict[str, list[bool]] = {}
    for case in scored:
        by_defect.setdefault(case.defect.value, []).append(bool(case.detected))
    return {defect: sum(flags) / len(flags) for defect, flags in by_defect.items()}


def load_contract(path: str | Path) -> IntentContract:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return IntentContract.from_dict(value)


def load_scenarios(path: str | Path) -> list[Scenario]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = value.get("scenarios") if isinstance(value, dict) else value
    if not isinstance(raw, list):
        raise ValueError("scenario file must contain a list or a scenarios list")
    scenarios = [Scenario.from_dict(item) for item in raw]
    ids = [scenario.id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario ids must be unique")
    return scenarios


def load_comparison_input(path: str | Path) -> tuple[str | None, list[ScenarioResult], list[ScenarioResult]]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("comparison input must be a JSON object")
    def rows(key: str) -> list[ScenarioResult]:
        raw = value.get(key)
        if not isinstance(raw, list):
            raise ValueError(f"comparison input field {key!r} must be a list")
        return [ScenarioResult.from_dict(item) for item in raw]
    return value.get("contract"), rows("baseline"), rows("candidate")
