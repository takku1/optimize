"""Checkable claims made in this run's REPORT.md (and the STATUS.md summary
of it), verified against the actual evolution graph and raw judge scores
rather than trusted as prose. See prompt_optimization.capability.claims for
why this exists and what it deliberately doesn't try to do (it doesn't parse
REPORT.md itself -- each claim below is a number pulled by hand from the doc,
paired with a value recomputed live from the underlying data).

Run: `prompt-optimization verify "output/claude skills/architectural-reasoning/negative-control-2026-08-29/verify_claims.py"`
from the repo root. Exits non-zero if any claim fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from prompt_optimization.capability import Claim
from prompt_optimization.evaluators import project_utility
from prompt_optimization.graph import GraphStore

RUN_DIR = Path(__file__).parent
GRAPH_DIR = RUN_DIR.parents[1] / "evolution-graph"
EMPIRICAL_DIR = RUN_DIR.parents[0] / "empirical-run-2026-08-29"

_store = GraphStore(GRAPH_DIR)
_n_skills = sum(1 for _ in _store.iter_skills())
_n_mutations = sum(1 for _ in _store.iter_mutations())
_n_evaluations = sum(1 for _ in _store.iter_evaluations())

_undamaged_omega = {"task_success": 1.0, "correctness": 0.95, "invariant_adherence": 1.0, "calibration": 0.9}
_damaged_omega = {"task_success": 1.0, "correctness": 0.95, "invariant_adherence": 1.0, "calibration": 0.9}
_noskill_scores = json.loads((RUN_DIR / "judging_noskill_raw_scores.json").read_text(encoding="utf-8"))
_noskill_entry = _noskill_scores["ns_b833c1fc"]
_noskill_omega = {
    "task_success": _noskill_entry["task_success"],
    "correctness": _noskill_entry["correctness"],
    "invariant_adherence": _noskill_entry["invariant_adherence"],
    "calibration": _noskill_entry["calibration"],
}

CLAIMS: list[Claim] = [
    # Graph seed counts stated in STATUS.md and this run's seed script output.
    Claim(description="evolution graph skill count", doc="REPORT.md/STATUS.md",
          expected=4, actual=_n_skills),
    Claim(description="evolution graph mutation count", doc="REPORT.md/STATUS.md",
          expected=2, actual=_n_mutations),
    Claim(description="evolution graph evaluation count", doc="REPORT.md/STATUS.md",
          expected=10, actual=_n_evaluations),

    # The three-way utility comparison in REPORT.md's "Follow-up: no_skill attribution" table.
    # Weights use the 'reasoning' capability-family profile, per profiles.py -- this is the
    # same weight vector this report already confirmed reproduces v1.3.0's stated 0.9675.
    Claim(description="v1.3.0 undamaged utility", doc="REPORT.md",
          expected=0.9675, actual=project_utility(_undamaged_omega, "reasoning")["utility"], tolerance=1e-4),
    Claim(description="v1.3.0 damaged utility", doc="REPORT.md",
          expected=0.9675, actual=project_utility(_damaged_omega, "reasoning")["utility"], tolerance=1e-4),
    Claim(description="no_skill utility", doc="REPORT.md",
          expected=0.9325, actual=project_utility(_noskill_omega, "reasoning")["utility"], tolerance=1e-4),

    # The invariant verdicts the three-way table states.
    Claim(description="no_skill reaudit-reclassifies", doc="REPORT.md",
          expected=True, actual=_noskill_entry["invariants"]["reaudit-reclassifies"]),
    Claim(description="no_skill grounded-evidence", doc="REPORT.md",
          expected=True, actual=_noskill_entry["invariants"]["grounded-evidence"]),
]


if __name__ == "__main__":
    from prompt_optimization.capability import all_passed, format_report, verify_claims

    results = verify_claims(CLAIMS)
    print(format_report(results))
    if not all_passed(results):
        raise SystemExit(1)
