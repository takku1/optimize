"""Blinded-judge + deterministic assembly into scenario results and a promotion verdict.

This replaces the per-run ``assemble_results.py`` one-off scripts. It reads the
blinded judge map + raw judge scores + the deterministic checks written by the
``checks`` stage, folds them into :class:`~prompt_optimization.contracts.ScenarioResult`
s for a baseline and a candidate skill version, runs the real pipeline
(:func:`~prompt_optimization.contracts.compare_contract_results` then
:func:`~prompt_optimization.capability.compare_versions`), and writes
``final_results.json`` — all driven by the run manifest, with no per-run Python
and no host-specific paths.

The one thing that is not mechanical is *which* invariant a scenario exercises
and which deterministic field overrides the judge for it, so that mapping is
declared per scenario in the manifest ($no interpretation is invented here).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .. import contracts
from ..capability import compare_versions
from ..evaluators import project_utility
from ..metrics.uncertainty import hierarchical_bootstrap
from .manifest import RunManifest

OMEGA_KEYS = ("task_success", "correctness", "invariant_adherence", "calibration")


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} ({path}) is not valid JSON: {exc}") from exc


def _judge_scores(raw_scores: Mapping[str, Any], opaque_id: str) -> Mapping[str, Any]:
    if opaque_id not in raw_scores:
        raise ValueError(f"raw scores has no entry for opaque id {opaque_id!r}")
    judge = raw_scores[opaque_id]
    if not isinstance(judge, Mapping):
        raise ValueError(f"raw score for {opaque_id!r} must be an object")
    for key in ("invariants", "rationale"):
        if key not in judge:
            raise ValueError(f"raw score for {opaque_id!r} missing {key!r}")
    return judge


def _assemble_one(
    version: str,
    scenario: str,
    rollout: str,
    opaque_id: str,
    judge: Mapping[str, Any],
    det: Mapping[str, Any],
    *,
    all_invariant_ids: Sequence[str],
    tested_invariants: Sequence[str],
    deterministic_overrides: Mapping[str, str],
    skill_tokens: int,
    capability_family: str,
) -> tuple[contracts.ScenarioResult, list[dict[str, Any]]]:
    """Build one ScenarioResult, reporting deterministic-vs-judge disagreements."""
    invariants: dict[str, bool] = {}
    disagreements: list[dict[str, Any]] = []
    tested = set(tested_invariants)
    for inv_id in all_invariant_ids:
        if inv_id not in tested:
            invariants[inv_id] = True  # not exercised here -- vacuous pass, not verified
            continue
        judge_value = bool(judge["invariants"].get(inv_id, False))
        det_field = deterministic_overrides.get(inv_id)
        det_value: bool | None = None
        if det_field and det_field in det:
            det_value = bool(det[det_field])
        final_value = det_value if det_value is not None else judge_value
        if det_value is not None and det_value != judge_value:
            disagreements.append({
                "unit": f"{version}:{scenario}:{rollout}",
                "invariant": inv_id,
                "deterministic": det_value,
                "judge": judge_value,
            })
        invariants[inv_id] = final_value

    omega = {key: float(judge.get(key, 0.0)) for key in OMEGA_KEYS}
    projection = project_utility(omega, capability_family)

    result = contracts.ScenarioResult(
        scenario_id=scenario,
        utility=projection["utility"],
        invariants=invariants,
        costs={
            "skill_tokens": float(skill_tokens),
            "response_word_count": float(det.get("word_count", 0)),
        },
        metadata={
            "split": "fitness",
            "opaque_id": opaque_id,
            "omega": omega,
            "rationale": judge.get("rationale", ""),
            "tested_invariants": list(tested_invariants),
        },
    )
    return result, disagreements


def assemble(manifest: RunManifest) -> dict[str, Any]:
    """Run the whole assembly pipeline for the manifest and return the output dict.

    Consumes ``blind_map`` / ``raw_scores`` / ``deterministic_checks`` paths,
    the contract at ``paths.contract``, and the ``assemble`` stage options
    (``baseline``/``candidate`` version-token maps, ``scenarios``, per-scenario
    ``tested_invariants``, ``deterministic_overrides``, ``all_invariant_ids``,
    utility projection and compare params). Returns the same shape that used to
    be written to ``final_results.json``.
    """
    opts = manifest.stage("assemble")
    baseline_entry = opts.get("baseline")
    candidate_entry = opts.get("candidate")
    if not isinstance(baseline_entry, Mapping) or not isinstance(candidate_entry, Mapping):
        raise ValueError("assemble stage requires 'baseline' and 'candidate' objects")
    baseline_name = str(baseline_entry.get("version", ""))
    candidate_name = str(candidate_entry.get("version", ""))
    if not baseline_name or not candidate_name or baseline_name == candidate_name:
        raise ValueError("baseline/candidate require distinct non-empty 'version' values")

    scenarios = [str(s) for s in opts.get("scenarios", ())]
    if not scenarios:
        raise ValueError("assemble stage requires a non-empty 'scenarios' list")
    all_invariant_ids = [str(i) for i in opts.get("all_invariant_ids", ())]
    if not all_invariant_ids:
        raise ValueError("assemble stage requires 'all_invariant_ids'")
    tested_map = {
        str(key): [str(v) for v in (value or ())]
        for key, value in (opts.get("tested_invariants") or {}).items()
    }
    det_overrides = {
        str(key): str(value) for key, value in (opts.get("deterministic_overrides") or {}).items()
    }
    capability_family = str(opts.get("capability_family", "reasoning"))
    compare = opts.get("compare") or {}
    noninferiority_margin = float(compare.get("noninferiority_margin", 0.05))
    seed = int(compare.get("seed", 0))
    bootstrap_resamples = int(compare.get("bootstrap_resamples", 2000))

    blind_map = _load_json(manifest.resolve("blind_map"), "blind map")
    if isinstance(blind_map, Mapping) and "mapping" in blind_map:
        blind_map = blind_map["mapping"]
    if not isinstance(blind_map, Mapping):
        raise ValueError("blind_map must be an object (or an object with a 'mapping' key)")
    raw_scores = _load_json(manifest.resolve("raw_scores"), "raw scores")
    if not isinstance(raw_scores, Mapping):
        raise ValueError("raw_scores must be an object")
    checks_payload = _load_json(manifest.resolve("deterministic_checks"), "deterministic checks")
    deterministic: Mapping[str, Any] = (
        checks_payload.get("results") or {} if isinstance(checks_payload, Mapping) else {}
    )

    def _rollouts_for(name: str, scenario: str) -> list[tuple[str, str]]:
        """Return [(rollout_label, blind_map_key), ...] for one version/scenario unit.

        A unit may have one implicit rollout (legacy key ``name:scenario`` or
        ``name:scenario:rollout_01`` with no siblings) or several explicit
        rollouts (``name:scenario:rollout_01``, ``...:rollout_02``, ...). Every
        rollout actually present in the blind map is included -- K is
        discovered from the data, never assumed.
        """
        exact = f"{name}:{scenario}"
        matches = [k for k in blind_map if k == exact or k.startswith(f"{exact}:")]
        if not matches:
            raise ValueError(f"blind_map has no entry for unit {exact!r}")
        out = []
        for key in sorted(matches):
            rollout = key[len(exact) + 1:] if key != exact else "rollout_01"
            out.append((rollout, key))
        return out

    scores: dict[str, dict[str, Any]] = {baseline_name: {}, candidate_name: {}}
    rollout_scores: dict[str, dict[str, list[contracts.ScenarioResult]]] = {
        baseline_name: {}, candidate_name: {}
    }
    disagreements: list[dict[str, Any]] = []
    for name, entry in ((baseline_name, baseline_entry), (candidate_name, candidate_entry)):
        tokens = int(entry.get("skill_tokens", 0))
        for scenario in scenarios:
            per_rollout: list[contracts.ScenarioResult] = []
            for rollout, unit_key in _rollouts_for(name, scenario):
                opaque_id = blind_map[unit_key]
                judge = _judge_scores(raw_scores, opaque_id)
                det = dict(
                    deterministic.get(f"{name}:{scenario}:{rollout}")
                    or deterministic.get(f"{name}:{scenario}")
                    or {}
                )
                result, disc = _assemble_one(
                    name, scenario, rollout, opaque_id, judge, det,
                    all_invariant_ids=all_invariant_ids,
                    tested_invariants=tested_map.get(scenario, ()),
                    deterministic_overrides=det_overrides,
                    skill_tokens=tokens,
                    capability_family=capability_family,
                )
                per_rollout.append(result)
                disagreements.extend(disc)
            rollout_scores[name][scenario] = per_rollout
            scores[name][scenario] = contracts.aggregate_rollout_results(per_rollout)

    contract = contracts.load_contract(manifest.resolve("contract"))

    baseline_rows = [scores[baseline_name][s] for s in scenarios]
    candidate_rows = [scores[candidate_name][s] for s in scenarios]
    contract_report = contracts.compare_contract_results(
        contract, baseline_rows, candidate_rows,
        noninferiority_margin=noninferiority_margin,
        seed=seed, bootstrap_resamples=bootstrap_resamples,
    )

    utility_hierarchical_interval = None
    rollout_counts = {
        s: (len(rollout_scores[baseline_name][s]), len(rollout_scores[candidate_name][s]))
        for s in scenarios
    }
    if all(b == c and b > 1 for b, c in rollout_counts.values()):
        # Paired per-rollout deltas, nested by scenario -- a more honest
        # uncertainty estimate than the flat scenario-level bootstrap above
        # once K>1, since it doesn't understate variance by treating rollouts
        # nested under 4 scenarios as 4*K independent observations.
        groups = [
            [
                rollout_scores[candidate_name][s][i].utility - rollout_scores[baseline_name][s][i].utility
                for i in range(rollout_counts[s][0])
            ]
            for s in scenarios
        ]
        lower, upper = hierarchical_bootstrap(groups, seed=seed, resamples=bootstrap_resamples)
        utility_hierarchical_interval = {"level": 0.95, "lower": lower, "upper": upper}

    def _fitness(rows: Sequence[contracts.ScenarioResult]) -> dict[str, float]:
        mean_u = sum(r.utility for r in rows) / len(rows)
        # n=4 has no meaningful per-version spread; min-utility is the crude
        # within-version robustness proxy used by the original empirical run.
        return {"U": mean_u, "R": min(r.utility for r in rows)}

    baseline_fit = _fitness(baseline_rows)
    candidate_fit = _fitness(candidate_rows)
    promotion = compare_versions(
        str(baseline_entry.get("id", baseline_name)), int(baseline_entry.get("skill_tokens", 0)),
        baseline_fit,
        str(candidate_entry.get("id", candidate_name)), int(candidate_entry.get("skill_tokens", 0)),
        candidate_fit,
        evaluator_synthetic=False,
        contract=contract,
        baseline_scenarios=baseline_rows,
        candidate_scenarios=candidate_rows,
        noninferiority_margin=noninferiority_margin,
        seed=seed,
        bootstrap_resamples=bootstrap_resamples,
    )

    return {
        "scenario_results": {
            name: {s: r.to_dict() for s, r in rows.items()} for name, rows in scores.items()
        },
        "contract_report": contract_report,
        "promotion": promotion.to_dict(),
        "deterministic_vs_judge_disagreements": disagreements,
        "rollout_counts": {s: rollout_counts[s][0] for s in scenarios},
        "utility_hierarchical_interval": utility_hierarchical_interval,
    }


def write_assembly(manifest: RunManifest, output: dict[str, Any]) -> Path:
    out_path = manifest.resolve("final_results")
    out_path = out_path.with_suffix(".json")
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return out_path
