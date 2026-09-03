"""Seed the evolution graph with the no_skill attribution control's result.

Companion to seed_graph.py: that script recorded the damaged-skill negative
control (utility_delta 0.0). This records the no_skill (bare model, no skill
text) result for the same scenario -- the follow-up REPORT.md called for to
test whether reaudit-reclassifies is skill-attributable rather than
model-inherent. Both are BENCHMARK_VALIDATION evidence (excluded from
retrieval/mutation_family_stats by default), not OPTIMIZER_TRANSITION.

The no_skill SkillNode uses skill_text="" -- its content hash is stable and
shared by any future no_skill baseline evaluation across scenarios/runs, per
search.baselines.no_skill (BaselineConfig("no_skill", use_mutation=False,
use_pareto_filter=False, max_generations=0)).
"""
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from prompt_optimization.graph import EvaluationRecord, GraphStore, SkillNode

RUN_DIR = Path(__file__).parent
GRAPH_DIR = RUN_DIR.parents[1] / "evolution-graph"


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    contract_hash = "architectural-reasoning-v1"

    store = GraphStore(GRAPH_DIR)

    no_skill_node = SkillNode(
        skill_text="", token_count=0, capability_contract_hash=contract_hash,
        generator="search.baselines.no_skill", generation=0,
        benchmark_version="skillbench-0.1", created_at=now,
        provenance={"note": "bare model, no skill text -- search.baselines.no_skill baseline"},
    )
    store.put_skill(no_skill_node)  # idempotent

    store.put_evaluation(EvaluationRecord(
        skill_hash=no_skill_node.skill_hash, scenario_id="02-reaudit-catches-regression",
        capability_contract_hash=contract_hash, benchmark_version="skillbench-0.1",
        evaluator_name="blinded-judge-plus-deterministic-checks", model_name="general-purpose-agent",
        metric_results={
            "utility": 0.9325,
            "invariants": {"reaudit-reclassifies": True, "grounded-evidence": True},
            "omega": {"task_success": 0.95, "correctness": 0.93, "invariant_adherence": 0.95, "calibration": 0.88},
        },
        trainability="TRAINABLE",
        created_at=now,
        provenance={
            "opaque_id": "ns_b833c1fc",
            "split": "fitness",
            "condition": "no_skill_control",
            "evidence_class": "BENCHMARK_VALIDATION",
            "finding": "no_skill also passes reaudit-reclassifies and grounded-evidence at this scenario's "
                       "binary invariant grain (utility 0.9325 vs. 0.9675 for v1.3.0 -- a real but smaller-than-"
                       "invariant-resolution gap). Confirms these invariants are not currently skill-attributable "
                       "on this scenario. See REPORT.md 'Follow-up: no_skill attribution'.",
            "report": "output/claude skills/architectural-reasoning/negative-control-2026-08-29/REPORT.md",
        },
    ))

    print(f"seeded {GRAPH_DIR}")
    print(f"skills={sum(1 for _ in store.iter_skills())} "
          f"mutations={sum(1 for _ in store.iter_mutations())} "
          f"evaluations={sum(1 for _ in store.iter_evaluations())}")


if __name__ == "__main__":
    main()
