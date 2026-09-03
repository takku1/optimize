"""Γ: the declared capability contract a skill claims to satisfy.

A benchmark cannot evaluate a skill against its own prose without circularity
— it first needs to know what the skill claims to do. ``CapabilityContract``
records that declaration and wraps an existing
:class:`~prompt_optimization.contracts.IntentContract` (the behavioral/Φ
layer) by id rather than duplicating it, adding ``scope``,
``required_behaviors``, ``forbidden_behaviors``, ``success_criteria``, and the
``capability_family`` that :mod:`prompt_optimization.evaluators.profiles`
uses to pick a rubric weight profile.

This module also implements hierarchical task-taxonomy coverage measurement:
"32 behavioral cells spanning activation x evidence x difficulty x novelty"
is a stronger benchmark claim than a raw task count, because it says
something about the *shape* of what was tested, not just how much.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CapabilityContract:
    """Γ = (scope, required_behaviors, forbidden_behaviors, success_criteria, capability_family)."""

    contract_id: str
    scope: str
    capability_family: str
    required_behaviors: tuple[str, ...] = ()
    forbidden_behaviors: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.contract_id.strip():
            raise ValueError("contract_id must not be empty")
        if not self.scope.strip():
            raise ValueError("scope must not be empty")
        if not self.capability_family.strip():
            raise ValueError("capability_family must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "scope": self.scope,
            "capability_family": self.capability_family,
            "required_behaviors": list(self.required_behaviors),
            "forbidden_behaviors": list(self.forbidden_behaviors),
            "success_criteria": list(self.success_criteria),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CapabilityContract":
        if not isinstance(value, dict):
            raise ValueError("capability contract must be a JSON object")

        def strings(key: str) -> tuple[str, ...]:
            raw = value.get(key, [])
            if not isinstance(raw, list):
                raise ValueError(f"field {key!r} must be a list")
            return tuple(str(item) for item in raw)

        return cls(
            contract_id=str(value.get("contract_id", "")),
            scope=str(value.get("scope", "")),
            capability_family=str(value.get("capability_family", "")),
            required_behaviors=strings("required_behaviors"),
            forbidden_behaviors=strings("forbidden_behaviors"),
            success_criteria=strings("success_criteria"),
            metadata=dict(value.get("metadata", {})),
        )


def load_capability_contract(path: str | Path) -> CapabilityContract:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return CapabilityContract.from_dict(value)


#: The default hierarchical task-taxonomy axes (BCSO-Bench design doc §3).
DEFAULT_AXES: dict[str, tuple[str, ...]] = {
    "activation": ("positive", "negative", "ambiguous"),
    "difficulty": ("easy", "moderate", "hard", "compositional"),
    "evidence": ("complete", "partial", "conflicting", "misleading"),
    "novelty": ("familiar", "compositional", "ood"),
    "user_intent": ("explicit", "implicit", "adversarial"),
    "context": ("short", "long", "noisy"),
    "tool_requirements": ("none", "optional", "mandatory"),
    "failure_mode": ("hallucination", "overreach", "omission", "excess_work"),
    "constraint_pressure": ("compatible", "conflicting", "impossible"),
}


def _parse_axis_tags(tags: Iterable[str]) -> dict[str, str]:
    """Read ``"axis:value"`` tags into a dict; untagged freeform tags are ignored."""
    parsed: dict[str, str] = {}
    for tag in tags:
        axis, sep, value = str(tag).partition(":")
        if sep:
            parsed[axis] = value
    return parsed


def coverage_report(scenarios, axes: dict[str, tuple[str, ...]] | None = None) -> dict:
    """Which taxonomy cells are covered by ``scenarios``, not just how many exist.

    Reads axis assignments from each scenario's ``tags`` using the
    ``"axis:value"`` convention (e.g. ``"difficulty:hard"``) — additive, no
    schema change to :class:`~prompt_optimization.contracts.Scenario`.
    Scenarios missing a tag for a given axis simply don't count toward it.
    """
    axes = axes or DEFAULT_AXES
    scenarios = list(scenarios)
    if not scenarios:
        raise ValueError("scenarios must not be empty")
    per_axis: dict[str, dict[str, int]] = {axis: {value: 0 for value in values} for axis, values in axes.items()}
    for scenario in scenarios:
        tagged = _parse_axis_tags(getattr(scenario, "tags", ()))
        for axis, values in axes.items():
            value = tagged.get(axis)
            if value in per_axis[axis]:
                per_axis[axis][value] += 1
    uncovered = {axis: [value for value, count in counts.items() if count == 0]
                 for axis, counts in per_axis.items()}
    uncovered = {axis: values for axis, values in uncovered.items() if values}
    total_cells = sum(len(values) for values in axes.values())
    covered_cells = sum(1 for counts in per_axis.values() for count in counts.values() if count > 0)
    return {
        "n_scenarios": len(scenarios),
        "per_axis_counts": per_axis,
        "uncovered_cells": uncovered,
        "coverage_fraction": covered_cells / total_cells if total_cells else 0.0,
    }
