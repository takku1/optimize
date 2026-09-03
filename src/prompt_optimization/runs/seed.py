"""Seed the persistent evolution graph from a run's real final results.

This replaces the per-run ``seed_graph.py`` one-off scripts. It reads a run's
``final_results.json`` (produced by the ``assemble`` stage) plus the actual
skill files declared in the manifest, and writes :class:`SkillNode`,
:class:`MutationEdge`, and :class:`EvaluationRecord` rows into a
:class:`~prompt_optimization.graph.store.GraphStore` — one skill node per
version (baseline as a root, candidate as its child), one mutation edge for the
pair, and one ``EvaluationRecord`` per (version, scenario). All file locations
come from the manifest, so no host-specific paths are hard-coded.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..graph import EvaluationRecord, GraphStore, MutationEdge, SkillNode
from .manifest import RunManifest


def _read_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"could not read {label} ({path}): {exc}") from exc


def seed_graph(manifest: RunManifest, final: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Populate the graph store and return a summary dict.

    ``final`` may be the already-loaded ``final_results.json`` mapping; when
    omitted it is read from the manifest's ``final_results`` path. The manifest
    ``seed`` stage drives the mapping: ``versions`` (baseline/candidate with
    ``skill`` path, ``tokens``, ``generation``), plus store-level fields
    (``graph_dir`` path, ``contract_hash``, ``benchmark_version``,
    ``mutation`` describing the edge).
    """
    opts = manifest.stage("seed")
    if final is None:
        final = json.loads(manifest.resolve("final_results").read_text(encoding="utf-8"))

    graph_dir = manifest.resolve("graph_dir")
    store = GraphStore(graph_dir)
    _ = store  # constructed for side effect of initializing the store layout

    contract_hash = str(opts.get("contract_hash", ""))
    benchmark_version = str(opts.get("benchmark_version", "skillbench-0.1"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    versions = opts.get("versions") or {}
    if not isinstance(versions, Mapping):
        raise ValueError("seed stage requires a 'versions' object")
    baseline_key = opts.get("baseline", "baseline")
    candidate_key = opts.get("candidate", "candidate")
    b_key = str(baseline_key)
    c_key = str(candidate_key)
    if b_key not in versions or c_key not in versions or b_key == c_key:
        raise ValueError(f"seed 'versions' must define distinct {b_key!r} and {c_key!r} entries")

    def _node(key: str) -> tuple[SkillNode, str]:
        entry = versions[key]
        if not isinstance(entry, Mapping):
            raise ValueError(f"seed version {key!r} must be an object")
        skill_path = manifest.resolve(str(entry["skill"]))
        text = _read_text(skill_path, f"seed version {key!r} skill")
        return SkillNode(
            skill_text=text,
            token_count=int(entry.get("tokens", 0)),
            capability_contract_hash=contract_hash,
            generator=str(entry.get("generator", "human")),
            generation=int(entry.get("generation", 0)),
            benchmark_version=benchmark_version,
            created_at=now,
            provenance={"source": str(skill_path), "run_id": manifest.id},
        ), skill_path

    baseline_node, baseline_path = _node(b_key)
    candidate_node, candidate_path = _node(c_key)
    candidate_node = SkillNode(
        skill_text=candidate_node.skill_text,
        token_count=candidate_node.token_count,
        capability_contract_hash=candidate_node.capability_contract_hash,
        parent_hashes=(baseline_node.skill_hash,),
        generator=candidate_node.generator,
        generation=candidate_node.generation,
        benchmark_version=candidate_node.benchmark_version,
        created_at=candidate_node.created_at,
        provenance={"source": str(candidate_path), "run_id": manifest.id},
    )
    store.put_skill(baseline_node)
    store.put_skill(candidate_node)

    promotion = final.get("promotion", {})
    hard_report = promotion.get("hard_invariants_report") or {}
    utility = hard_report.get("utility") or {}
    mutation_cfg = opts.get("mutation") or {}
    store.put_mutation(MutationEdge(
        parent_hash=baseline_node.skill_hash,
        child_hash=candidate_node.skill_hash,
        mutation_family=str(mutation_cfg.get("family", "human_reauthoring")),
        mutation_description=str(mutation_cfg.get("description", "")),
        actual_effect={
            "utility_delta": utility.get("delta_mean", 0.0),
            "tokens_delta": float(promotion.get("token_delta", 0.0)),
        },
        optimizer_version=str(mutation_cfg.get("optimizer_version", manifest.id)),
        created_at=now,
        provenance={
            "promotion_verdict": promotion.get("verdict", ""),
            "reasons": list(promotion.get("reasons", ())),
            "report": str(mutation_cfg.get("report", "")),
        },
    ))

    node_by_version = {b_key: baseline_node, c_key: candidate_node}
    scenario_results = final.get("scenario_results", {})
    for version, scenarios in scenario_results.items():
        node = node_by_version.get(version)
        if node is None:
            continue
        for scenario_id, result in scenarios.items():
            metadata = result.get("metadata", {})
            store.put_evaluation(EvaluationRecord(
                skill_hash=node.skill_hash,
                scenario_id=scenario_id,
                capability_contract_hash=contract_hash,
                benchmark_version=benchmark_version,
                evaluator_name=str(opts.get("evaluator_name", "blinded-judge-plus-deterministic-checks")),
                model_name=str(opts.get("model_name", "general-purpose-agent")),
                metric_results={
                    "utility": result.get("utility"),
                    "invariants": result.get("invariants", {}),
                    "omega": metadata.get("omega", {}),
                },
                trainability=str(opts.get("trainability", "TRAINABLE")),
                created_at=now,
                provenance={
                    "opaque_id": metadata.get("opaque_id", ""),
                    "split": metadata.get("split", "fitness"),
                    "run_id": manifest.id,
                },
            ))

    counts = {
        "skills": sum(1 for _ in store.iter_skills()),
        "mutations": sum(1 for _ in store.iter_mutations()),
        "evaluations": sum(1 for _ in store.iter_evaluations()),
    }
    return {"graph_dir": str(graph_dir), "counts": counts, "baseline_hash": baseline_node.skill_hash,
            "candidate_hash": candidate_node.skill_hash}
