"""Seed the persistent evolution graph with this run's real transition data.

Converts final_results.json (already-real ScenarioResults + the
compare_versions verdict) into graph records: v1.2.4 as a human-authored root
node, current (v1.3.0) as a human-reauthored child with the real observed
utility/token delta as its actual_effect, and one EvaluationRecord per
(version, scenario) — 8 total, tagged TRAINABLE since these came from a real,
non-synthetic evaluator. This is exactly section 49's "immediate
implementation target" applied to data that already exists rather than
invented for the purpose.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from prompt_optimization.graph import EvaluationRecord, GraphStore, MutationEdge, SkillNode

RUN_DIR = Path(__file__).parent
GRAPH_DIR = RUN_DIR.parents[1] / "evolution-graph"  # output/claude skills/evolution-graph/


def main() -> None:
    final = json.loads((RUN_DIR / "final_results.json").read_text(encoding="utf-8"))
    baseline_text = (Path(r"Z:\archetect\skills\architectural-reasoning\archive\v1.2.4\SKILL.md")
                      .read_text(encoding="utf-8"))
    candidate_text = Path(r"Z:\archetect\skills\architectural-reasoning\SKILL.md").read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat()

    store = GraphStore(GRAPH_DIR)
    contract_hash = "architectural-reasoning-v1"  # the contract id doubles as the family tag here

    baseline_node = SkillNode(
        skill_text=baseline_text, token_count=1651, capability_contract_hash=contract_hash,
        generator="human", generation=0, benchmark_version="skillbench-0.1", created_at=now,
        provenance={"source": r"Z:\archetect\skills\architectural-reasoning\archive\v1.2.4\SKILL.md"},
    )
    store.put_skill(baseline_node)

    candidate_node = SkillNode(
        skill_text=candidate_text, token_count=844, capability_contract_hash=contract_hash,
        parent_hashes=(baseline_node.skill_hash,), generator="human", generation=1,
        benchmark_version="skillbench-0.1", created_at=now,
        provenance={"source": r"Z:\archetect\skills\architectural-reasoning\SKILL.md"},
    )
    store.put_skill(candidate_node)

    promotion = final["promotion"]
    store.put_mutation(MutationEdge(
        parent_hash=baseline_node.skill_hash, child_hash=candidate_node.skill_hash,
        mutation_family="human_reauthoring",
        mutation_description="v1.2.4 -> v1.3.0: separated optimization machinery into a dedicated skill, "
                              "made effort calibration explicit/operational, tightened evidence requirements, "
                              "compressed lens table wording.",
        actual_effect={
            "utility_delta": promotion["hard_invariants_report"]["utility"]["delta_mean"],
            "tokens_delta": float(promotion["token_delta"]),
        },
        optimizer_version="empirical-run-2026-08-29",
        created_at=now,
        provenance={"promotion_verdict": promotion["verdict"], "reasons": promotion["reasons"],
                     "report": "output/claude skills/architectural-reasoning/empirical-run-2026-08-29/REPORT.md"},
    ))

    node_by_version = {"v1_2_4": baseline_node, "v1_3_0": candidate_node}
    for version, scenarios in final["scenario_results"].items():
        node = node_by_version[version]
        for scenario_id, result in scenarios.items():
            store.put_evaluation(EvaluationRecord(
                skill_hash=node.skill_hash, scenario_id=scenario_id,
                capability_contract_hash=contract_hash, benchmark_version="skillbench-0.1",
                evaluator_name="blinded-judge-plus-deterministic-checks", model_name="general-purpose-agent",
                metric_results={"utility": result["utility"], "invariants": result["invariants"],
                                 "omega": result["metadata"]["omega"]},
                trainability="TRAINABLE",  # real, non-synthetic evaluator produced this
                created_at=now,
                provenance={"opaque_id": result["metadata"]["opaque_id"], "split": result["metadata"]["split"]},
            ))

    print(f"seeded {GRAPH_DIR}")
    print(f"skills={sum(1 for _ in store.iter_skills())} "
          f"mutations={sum(1 for _ in store.iter_mutations())} "
          f"evaluations={sum(1 for _ in store.iter_evaluations())}")


if __name__ == "__main__":
    main()
