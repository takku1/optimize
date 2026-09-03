"""Combine blinded judge scores + deterministic checks into ScenarioResults,
then run the real pipeline: compare_contract_results -> capability.compare_versions.

Run once, after all 8 transcripts and all 8 judge scores are recorded and the
blind map has been revealed. No skill file is modified by this script.
"""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from prompt_optimization.contracts import ScenarioResult, compare_contract_results, load_contract
from prompt_optimization.capability import compare_versions
from prompt_optimization.evaluators.profiles import project_utility

RUN_DIR = Path(__file__).parent
ALL_INVARIANT_IDS = (
    "grounded-evidence", "calibrated-effort", "reaudit-reclassifies",
    "lens-grounded-in-force", "no-gratuitous-rewrite",
)
SCENARIOS = (
    "01-stop-when-supported",
    "02-reaudit-catches-regression",
    "03a-lens-wording-security",
    "03b-lens-wording-sociotechnical",
)
SCENARIO_TESTED_INVARIANTS = {
    "01-stop-when-supported": ("calibrated-effort", "grounded-evidence"),
    "02-reaudit-catches-regression": ("reaudit-reclassifies", "grounded-evidence"),
    "03a-lens-wording-security": ("lens-grounded-in-force",),
    "03b-lens-wording-sociotechnical": ("lens-grounded-in-force",),
}
SKILL_TOKENS = {"v1_2_4": 1651, "v1_3_0": 844}  # from `prompt-opt scan --max-tokens 100000`


def main() -> None:
    blind_map = json.loads((RUN_DIR / "judging" / "blind_map.json").read_text(encoding="utf-8"))["mapping"]
    raw_scores = json.loads((RUN_DIR / "judging" / "raw_scores.json").read_text(encoding="utf-8"))
    deterministic = json.loads((RUN_DIR / "deterministic_checks.json").read_text(encoding="utf-8"))

    # unit key "v1_2_4:01-stop-when-supported:rollout_01" -> opaque id -> score
    unit_to_opaque = blind_map
    opaque_to_score = raw_scores

    scenario_results = {"v1_2_4": {}, "v1_3_0": {}}
    final_invariants_report = {}

    for version in ("v1_2_4", "v1_3_0"):
        for scenario in SCENARIOS:
            unit_key = f"{version}:{scenario}:rollout_01"
            opaque_id = unit_to_opaque[unit_key]
            judge = opaque_to_score[opaque_id]
            det = deterministic.get(f"{version}:{scenario}", {})

            tested = SCENARIO_TESTED_INVARIANTS[scenario]
            invariants = {}
            for inv_id in ALL_INVARIANT_IDS:
                if inv_id not in tested:
                    invariants[inv_id] = True  # not exercised by this scenario -- vacuous pass, not verified
                    continue
                judge_value = bool(judge["invariants"][inv_id])
                det_value = None
                if inv_id == "calibrated-effort" and "calibrated_effort_deterministic" in det:
                    det_value = bool(det["calibrated_effort_deterministic"])
                if inv_id == "reaudit-reclassifies" and "reaudit_reclassifies_deterministic_proxy" in det:
                    det_value = bool(det["reaudit_reclassifies_deterministic_proxy"])
                # deterministic check wins when available (req #5); record any disagreement
                final_value = det_value if det_value is not None else judge_value
                if det_value is not None and det_value != judge_value:
                    final_invariants_report.setdefault("disagreements", []).append(
                        {"unit": unit_key, "invariant": inv_id, "deterministic": det_value, "judge": judge_value}
                    )
                invariants[inv_id] = final_value

            omega = {
                "task_success": judge["task_success"],
                "correctness": judge["correctness"],
                "invariant_adherence": judge["invariant_adherence"],
                "calibration": judge["calibration"],
            }
            projection = project_utility(omega, "reasoning")

            result = ScenarioResult(
                scenario_id=scenario,
                utility=projection["utility"],
                invariants=invariants,
                costs={
                    "skill_tokens": float(SKILL_TOKENS[version]),
                    "response_word_count": float(det.get("word_count", 0)),
                },
                metadata={
                    "split": "fitness",
                    "opaque_id": opaque_id,
                    "omega": omega,
                    "rationale": judge["rationale"],
                    "tested_invariants": list(tested),
                },
            )
            scenario_results[version][scenario] = result

    contract = load_contract(RUN_DIR.parents[3] / "tests" / "fixtures" / "contracts" / "architectural-reasoning-v1.json")

    baseline_rows = [scenario_results["v1_2_4"][s] for s in SCENARIOS]
    candidate_rows = [scenario_results["v1_3_0"][s] for s in SCENARIOS]

    contract_report = compare_contract_results(
        contract, baseline_rows, candidate_rows,
        noninferiority_margin=0.05, seed=2026829, bootstrap_resamples=2000,
    )

    baseline_u = sum(r.utility for r in baseline_rows) / len(baseline_rows)
    baseline_r = min(r.utility for r in baseline_rows)  # crude within-version spread proxy for R at n=4
    candidate_u = sum(r.utility for r in candidate_rows) / len(candidate_rows)
    candidate_r = min(r.utility for r in candidate_rows)

    promotion = compare_versions(
        "architectural-reasoning-v1_2_4", SKILL_TOKENS["v1_2_4"], {"U": baseline_u, "R": baseline_r},
        "architectural-reasoning-v1_3_0", SKILL_TOKENS["v1_3_0"], {"U": candidate_u, "R": candidate_r},
        evaluator_synthetic=False,
        contract=contract,
        baseline_scenarios=baseline_rows,
        candidate_scenarios=candidate_rows,
        noninferiority_margin=0.05,
        seed=2026829,
        bootstrap_resamples=2000,
    )

    out = {
        "scenario_results": {
            version: {s: r.to_dict() for s, r in rows.items()} for version, rows in scenario_results.items()
        },
        "contract_report": contract_report,
        "promotion": promotion.to_dict(),
        "deterministic_vs_judge_disagreements": final_invariants_report.get("disagreements", []),
    }
    (RUN_DIR / "final_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"promotion_verdict": promotion.verdict.value, "reasons": promotion.reasons}, indent=2))
    print(f"wrote {RUN_DIR / 'final_results.json'}")


if __name__ == "__main__":
    main()
