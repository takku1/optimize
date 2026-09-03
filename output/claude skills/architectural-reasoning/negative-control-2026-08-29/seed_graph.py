"""Seed the evolution graph with this negative-control transition — a null result.

Preserving a failed/null finding is the point: per the original evolution-
graph proposal's own §32, a corpus containing only successful transitions
teaches survivorship bias. This one records honestly that a real defect
injection produced a measured utility_delta of 0.0.
"""
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from prompt_optimization.graph import EvaluationRecord, GraphStore, MutationEdge, SkillNode

RUN_DIR = Path(__file__).parent
GRAPH_DIR = RUN_DIR.parents[1] / "evolution-graph"


def main() -> None:
    candidate_text = Path(r"Z:\archetect\skills\architectural-reasoning\SKILL.md").read_text(encoding="utf-8")
    damaged_text = (RUN_DIR / "damaged-v1_3_0.md").read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat()
    contract_hash = "architectural-reasoning-v1"

    store = GraphStore(GRAPH_DIR)
    candidate_node = SkillNode(skill_text=candidate_text, token_count=844, capability_contract_hash=contract_hash)
    store.put_skill(candidate_node)  # idempotent: already recorded by the empirical-run seed script

    damaged_node = SkillNode(
        skill_text=damaged_text, token_count=830, capability_contract_hash=contract_hash,
        parent_hashes=(candidate_node.skill_hash,), generator="human_negative_control", generation=2,
        benchmark_version="skillbench-0.1", created_at=now,
        provenance={"source": str(RUN_DIR / "damaged-v1_3_0.md"), "defect": "removed re-audit reclassification instruction"},
    )
    store.put_skill(damaged_node)

    store.put_mutation(MutationEdge(
        parent_hash=candidate_node.skill_hash, child_hash=damaged_node.skill_hash,
        mutation_family="defect_injection",
        mutation_description="Replaced the Re-audit bullet's 'distrust prior findings; re-verify each against "
                              "current code; classify resolved, regressed, still open, or new; check whether a "
                              "fix introduced another problem' with the generic 'review the prior audit findings "
                              "and the associated diff'.",
        actual_effect={"utility_delta": 0.0, "tokens_delta": float(830 - 844)},
        optimizer_version="negative-control-2026-08-29",
        created_at=now,
        provenance={
            "finding": "NULL RESULT: benchmark did not detect this defect on scenario 02 "
                       "(reaudit-reclassifies still scored true, utility unchanged to 4 sig figs). "
                       "See REPORT.md -- likely means this invariant is not yet skill-attributable "
                       "on this scenario, not that the defect had no real effect.",
            "report": "output/claude skills/architectural-reasoning/negative-control-2026-08-29/REPORT.md",
        },
    ))

    store.put_evaluation(EvaluationRecord(
        skill_hash=damaged_node.skill_hash, scenario_id="02-reaudit-catches-regression",
        capability_contract_hash=contract_hash, benchmark_version="skillbench-0.1",
        evaluator_name="blinded-judge-plus-deterministic-checks", model_name="general-purpose-agent",
        metric_results={"utility": 0.9675, "invariants": {"reaudit-reclassifies": True, "grounded-evidence": True},
                         "omega": {"task_success": 1.0, "correctness": 0.95, "invariant_adherence": 1.0, "calibration": 0.9}},
        trainability="TRAINABLE",
        created_at=now,
        provenance={"opaque_id": "nc_1cf53d7c", "split": "fitness", "condition": "negative_control"},
    ))

    print(f"seeded {GRAPH_DIR}")
    print(f"skills={sum(1 for _ in store.iter_skills())} "
          f"mutations={sum(1 for _ in store.iter_mutations())} "
          f"evaluations={sum(1 for _ in store.iter_evaluations())}")


if __name__ == "__main__":
    main()
