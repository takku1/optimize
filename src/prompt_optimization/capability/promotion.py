"""Version comparison and promotion verdicts: iteration vs. validated improvement.

A search run, or a hand-authored new version (a skill going from v1.2.4 to
v1.3.0), produces a *candidate* — never automatically an *improvement*. This
module is the explicit boundary between the two. It reuses what already
exists rather than inventing new comparison math: Pareto dominance from
:mod:`prompt_optimization.search.archive`, and hard-invariant + non-
inferiority gating from :func:`prompt_optimization.contracts.compare_contract_results`.
It returns :data:`PromotionVerdict.VALIDATED_IMPROVEMENT` only when a
non-synthetic evaluator disposed of the comparison via both — the same
honesty rule the CLI's ``plan`` command already enforces for
``supported_improvement``, generalized to whole-skill version comparisons.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..contracts import IntentContract, ScenarioResult, compare_contract_results
from ..search.archive import update_archive


class PromotionVerdict(str, Enum):
    #: Nothing has disposed of this yet — a candidate, not evidence of anything.
    CANDIDATE = "candidate"
    #: A non-synthetic evaluator confirmed hard invariants held and utility
    #: was non-inferior (or improved), with the candidate not dominated on cost.
    VALIDATED_IMPROVEMENT = "validated_improvement"
    #: A non-synthetic evaluator found the candidate short of an absolute
    #: floor (see ``regressed_invariants``/``floor_gap_invariants`` for
    #: *which kind* of shortfall — the verdict alone conflates them on
    #: purpose, since both block promotion; use those fields to tell them
    #: apart) or a utility regression beyond the allowed margin.
    REJECTED = "rejected"


@dataclass(frozen=True)
class VersionComparison:
    """The full "is this actually better" report for one baseline/candidate pair."""

    baseline_id: str
    candidate_id: str
    baseline_tokens: int
    candidate_tokens: int
    token_delta: int
    pareto_dominant: str | None  # "baseline" | "candidate" | None (neither dominates)
    hard_invariants_report: dict[str, Any] | None
    verdict: PromotionVerdict
    reasons: tuple[str, ...] = field(default_factory=tuple)
    #: Invariant ids the candidate broke that the baseline actually held —
    #: a real, candidate-caused loss. Distinct from ``floor_gap_invariants``
    #: on purpose: "both fail the same floor" must never render as "the
    #: candidate lost an invariant" (see ``contracts.compare_contract_results``).
    regressed_invariants: tuple[str, ...] = field(default_factory=tuple)
    #: Invariant ids neither version clears — a pre-existing measurement or
    #: skill gap the candidate did not introduce and did not fix.
    floor_gap_invariants: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "candidate_id": self.candidate_id,
            "baseline_tokens": self.baseline_tokens,
            "candidate_tokens": self.candidate_tokens,
            "token_delta": self.token_delta,
            "pareto_dominant": self.pareto_dominant,
            "hard_invariants_report": self.hard_invariants_report,
            "verdict": self.verdict.value,
            "reasons": list(self.reasons),
            "regressed_invariants": list(self.regressed_invariants),
            "floor_gap_invariants": list(self.floor_gap_invariants),
        }


def _pareto_dominant(baseline_id: str, baseline_row: dict, candidate_id: str, candidate_row: dict) -> str | None:
    frontier_ids = {row["id"] for row in update_archive([baseline_row], [candidate_row])}
    if frontier_ids == {candidate_id}:
        return "candidate"
    if frontier_ids == {baseline_id}:
        return "baseline"
    return None


def compare_versions(
    baseline_id: str,
    baseline_tokens: int,
    baseline_fitness: dict[str, float],
    candidate_id: str,
    candidate_tokens: int,
    candidate_fitness: dict[str, float],
    *,
    evaluator_synthetic: bool,
    contract: IntentContract | None = None,
    baseline_scenarios: list[ScenarioResult] | None = None,
    candidate_scenarios: list[ScenarioResult] | None = None,
    noninferiority_margin: float = 0.05,
    seed: int = 0,
    bootstrap_resamples: int = 2000,
) -> VersionComparison:
    """Compare a baseline and a candidate skill version and render a promotion verdict.

    ``baseline_fitness``/``candidate_fitness`` need ``U`` and ``R`` keys (the
    same fitness vector the search loop tracks). Pass a ``contract`` plus
    paired ``baseline_scenarios``/``candidate_scenarios`` (real, externally
    produced observations — see :func:`~prompt_optimization.contracts.compare_contract_results`)
    to get a hard-invariant/non-inferiority verdict; without them the result
    can never rise above :data:`PromotionVerdict.CANDIDATE`, since token
    count and synthetic/fitness scores alone cannot establish that mandatory
    behavior was preserved.
    """
    baseline_row = {"id": baseline_id, "U": baseline_fitness["U"], "R": baseline_fitness["R"], "tokens": baseline_tokens}
    candidate_row = {"id": candidate_id, "U": candidate_fitness["U"], "R": candidate_fitness["R"], "tokens": candidate_tokens}
    dominant = _pareto_dominant(baseline_id, baseline_row, candidate_id, candidate_row)

    reasons: list[str] = []
    hard_invariants_report: dict[str, Any] | None = None
    verdict = PromotionVerdict.CANDIDATE
    regressed: tuple[str, ...] = ()
    floor_gap: tuple[str, ...] = ()

    if evaluator_synthetic:
        reasons.append("backend is synthetic: candidates only, never evidence of improvement")
    elif contract is None or baseline_scenarios is None or candidate_scenarios is None:
        reasons.append("no contract/scenario comparison supplied: token/fitness deltas alone cannot validate behavior")
    else:
        report = compare_contract_results(
            contract, baseline_scenarios, candidate_scenarios,
            noninferiority_margin=noninferiority_margin, seed=seed, bootstrap_resamples=bootstrap_resamples,
        )
        hard_invariants_report = report
        regressed = tuple(sorted(
            inv_id for inv_id, item in report["hard_invariants"].items() if item["status"] == "regression"
        ))
        floor_gap = tuple(sorted(
            inv_id for inv_id, item in report["hard_invariants"].items() if item["status"] == "floor_not_met"
        ))
        if not report["accepted"]:
            verdict = PromotionVerdict.REJECTED
            if regressed:
                reasons.append(f"regressed on hard invariant(s) the baseline held: {list(regressed)}")
            if floor_gap:
                reasons.append(
                    f"pre-existing floor not met by baseline or candidate: {list(floor_gap)} "
                    "(not a candidate-caused regression)"
                )
            if not report["utility"]["noninferior"]:
                reasons.append("utility regression beyond the non-inferiority margin")
        elif dominant == "baseline":
            verdict = PromotionVerdict.REJECTED
            reasons.append("baseline Pareto-dominates the candidate on (U, R, tokens)")
        else:
            verdict = PromotionVerdict.VALIDATED_IMPROVEMENT
            reasons.append("hard invariants held, utility non-inferior, and the candidate is not dominated")

    return VersionComparison(
        baseline_id=baseline_id,
        candidate_id=candidate_id,
        baseline_tokens=baseline_tokens,
        candidate_tokens=candidate_tokens,
        token_delta=candidate_tokens - baseline_tokens,
        pareto_dominant=dominant,
        hard_invariants_report=hard_invariants_report,
        verdict=verdict,
        reasons=tuple(reasons),
        regressed_invariants=regressed,
        floor_gap_invariants=floor_gap,
    )
