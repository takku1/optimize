"""Content-addressed file store for the evolution graph.

Deliberately boring, per §49 of the grounded proposal ("the next practical
asset is simply a high-quality immutable transition dataset") and the
grounding doc's own read of §42: "SQLite/Postgres + object storage... may be
entirely sufficient." This is one step simpler still — plain hash-named JSON
files, no database dependency — appropriate at the data scale a research
scaffold like this one actually has (hundreds to low thousands of records,
not millions). Swap in a real database later if `iter_*` scans become slow;
nothing above this module should need to change if that happens, since the
`GraphStore` interface would stay the same.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from .models import EvaluationRecord, MutationEdge, SkillNode


class GraphStore:
    """A directory of hash-addressed skills/mutations/evaluations, plus lineage queries."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.skills_dir = self.root / "skills"
        self.mutations_dir = self.root / "mutations"
        self.evaluations_dir = self.root / "evaluations"
        for d in (self.skills_dir, self.mutations_dir, self.evaluations_dir):
            d.mkdir(parents=True, exist_ok=True)

    # -- skills ---------------------------------------------------------

    def put_skill(self, node: SkillNode) -> str:
        """Write a skill node; a no-op if its hash is already present (content-addressed idempotence)."""
        path = self.skills_dir / f"{node.skill_hash}.json"
        if not path.exists():
            path.write_text(json.dumps(node.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return node.skill_hash

    def get_skill(self, skill_hash: str) -> SkillNode:
        path = self.skills_dir / f"{skill_hash}.json"
        if not path.exists():
            raise KeyError(f"no skill node with hash {skill_hash!r}")
        return SkillNode.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def has_skill(self, skill_hash: str) -> bool:
        return (self.skills_dir / f"{skill_hash}.json").exists()

    def iter_skills(self) -> Iterator[SkillNode]:
        for path in sorted(self.skills_dir.glob("*.json")):
            yield SkillNode.from_dict(json.loads(path.read_text(encoding="utf-8")))

    # -- mutations --------------------------------------------------------

    def put_mutation(self, edge: MutationEdge) -> str:
        path = self.mutations_dir / f"{edge.mutation_id}.json"
        if not path.exists():
            path.write_text(json.dumps(edge.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return edge.mutation_id

    def iter_mutations(self) -> Iterator[MutationEdge]:
        for path in sorted(self.mutations_dir.glob("*.json")):
            yield MutationEdge.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def children(self, skill_hash: str) -> list[MutationEdge]:
        return [edge for edge in self.iter_mutations() if edge.parent_hash == skill_hash]

    def parents(self, skill_hash: str) -> list[MutationEdge]:
        return [edge for edge in self.iter_mutations() if edge.child_hash == skill_hash]

    # -- evaluations ------------------------------------------------------

    def put_evaluation(self, record: EvaluationRecord) -> str:
        path = self.evaluations_dir / f"{record.evaluation_id}.json"
        if not path.exists():
            path.write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return record.evaluation_id

    def iter_evaluations(self) -> Iterator[EvaluationRecord]:
        for path in sorted(self.evaluations_dir.glob("*.json")):
            yield EvaluationRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def evaluations_for(self, skill_hash: str) -> list[EvaluationRecord]:
        return [record for record in self.iter_evaluations() if record.skill_hash == skill_hash]

    # -- lineage ------------------------------------------------------------

    def lineage(self, skill_hash: str) -> list[SkillNode]:
        """Walk `parent_hashes` back to a root; returns oldest-first, including `skill_hash` itself.

        Multiple-parent nodes (a merge) follow the first recorded parent only
        — sufficient for "why does this skill look this way," not a full
        ancestry DAG traversal.
        """
        chain = [self.get_skill(skill_hash)]
        seen = {skill_hash}
        current = chain[0]
        while current.parent_hashes:
            parent_hash = current.parent_hashes[0]
            if parent_hash in seen or not self.has_skill(parent_hash):
                break
            current = self.get_skill(parent_hash)
            chain.append(current)
            seen.add(parent_hash)
        return list(reversed(chain))
