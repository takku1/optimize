"""Generation-based filesystem layout for a search run: lineage, not overwrite.

::

    runs/<run_id>/
      gen_000/seed.md
      gen_001/candidate_01.md ... scores.json
      archive/pareto_001.md, pareto_002.md, ...
      final/SKILL.md, benchmark.json, provenance.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .population import Candidate


def write_generation(run_dir: str | Path, generation: int, candidates: list[Candidate],
                      scores: dict[str, dict]) -> Path:
    """Write one generation's candidate files plus a ``scores.json`` lineage record."""
    gen_dir = Path(run_dir) / f"gen_{generation:03d}"
    gen_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, candidate in enumerate(candidates, start=1):
        name = "seed.md" if generation == 0 and len(candidates) == 1 else f"candidate_{i:02d}.md"
        (gen_dir / name).write_text(candidate.text, encoding="utf-8")
        row = {
            "id": candidate.id,
            "file": name,
            "parent_ids": list(candidate.parent_ids),
            "mutation_type": candidate.mutation_type,
            "transformation_class": candidate.transformation_class,
        }
        row.update(scores.get(candidate.id, {}))
        rows.append(row)
    (gen_dir / "scores.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return gen_dir


def write_archive_snapshot(run_dir: str | Path, checkpoint: int, archive_candidates: list[Candidate]) -> Path:
    """Write the non-dominated set at one checkpoint as a single readable snapshot file."""
    archive_dir = Path(run_dir) / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    path = archive_dir / f"pareto_{checkpoint:03d}.md"
    combined = "\n\n---\n\n".join(f"# {c.id} ({c.mutation_type})\n\n{c.text}" for c in archive_candidates)
    path.write_text(combined, encoding="utf-8")
    return path


def write_final(run_dir: str | Path, selected: Candidate, benchmark: dict[str, Any],
                 provenance: dict[str, Any]) -> Path:
    """Write the frozen ``S*_δ``, its benchmark report, and run provenance."""
    final_dir = Path(run_dir) / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "SKILL.md").write_text(selected.text, encoding="utf-8")
    (final_dir / "benchmark.json").write_text(json.dumps(benchmark, indent=2), encoding="utf-8")
    (final_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return final_dir
