"""Versioned external benchmark registry and provenance checks."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ExternalBenchmark:
    """A reproducible external benchmark reference, not a result bundle."""

    id: str
    source: Mapping[str, Any]
    cells: tuple[Mapping[str, Any], ...]
    required_comparisons: tuple[str, ...]
    split_policy: Mapping[str, str]
    status: str
    content_hash: str

    def metadata(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.id,
            "benchmark_revision": self.source["revision"],
            "benchmark_license": self.source["license"],
            "benchmark_content_hash": self.content_hash,
            "benchmark_status": self.status,
        }


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"benchmark {name} must be a non-empty string")
    return value.strip()


def load_external_benchmark(path: str | Path) -> ExternalBenchmark:
    """Load and validate a registry entry with stable content hashing."""
    source_path = Path(path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid benchmark registry entry {source_path}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("benchmark registry entry must be an object")

    benchmark_id = _require_string(raw.get("id"), "id")
    source = raw.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("benchmark source must be an object")
    for key in ("name", "url", "revision", "license", "retrieved_at"):
        _require_string(source.get(key), f"source.{key}")
    revision = str(source["revision"])
    if len(revision) < 7 or any(ch not in "0123456789abcdefABCDEF" for ch in revision):
        raise ValueError("benchmark source.revision must be a hexadecimal commit identifier")

    cells = raw.get("registered_cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError("benchmark registered_cells must be a non-empty list")
    seen: set[str] = set()
    for cell in cells:
        if not isinstance(cell, Mapping):
            raise ValueError("each registered benchmark cell must be an object")
        dataset = _require_string(cell.get("dataset"), "cell.dataset")
        if dataset in seen:
            raise ValueError(f"duplicate benchmark dataset cell: {dataset}")
        seen.add(dataset)
        if not isinstance(cell.get("evaluation_n"), int) or cell["evaluation_n"] < 1:
            raise ValueError(f"benchmark cell {dataset!r} needs positive evaluation_n")
        _require_string(cell.get("upstream_manifest"), f"cell[{dataset}].upstream_manifest")

    controls = raw.get("required_comparisons")
    if not isinstance(controls, list) or not controls:
        raise ValueError("benchmark required_comparisons must be a non-empty list")
    required_controls = tuple(_require_string(item, "required comparison") for item in controls)

    split_policy = raw.get("split_policy")
    if not isinstance(split_policy, Mapping):
        raise ValueError("benchmark split_policy must be an object")
    required_splits = ("development", "calibration", "selection", "test")
    for split in required_splits:
        _require_string(split_policy.get(split), f"split_policy.{split}")

    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return ExternalBenchmark(
        id=benchmark_id,
        source=source,
        cells=tuple(cells),
        required_comparisons=required_controls,
        split_policy={key: str(split_policy[key]) for key in required_splits},
        status=_require_string(raw.get("status", "UNSPECIFIED"), "status"),
        content_hash=hashlib.sha256(canonical).hexdigest(),
    )


def to_reference_run_manifest(path: str | Path):
    """Translate a registry entry into a path-portable reference RunManifest.

    The returned manifest has no execution stages by design. A caller must add
    an explicit local stage after checking the upstream environment and model
    endpoint; this prevents a downloaded benchmark from becoming an accidental
    claim-producing run.
    """
    from .runs.manifest import RunManifest

    registry_path = Path(path).resolve()
    benchmark = load_external_benchmark(registry_path)
    root = registry_path.parents[1]
    return RunManifest(
        id=f"{benchmark.id}-reference",
        source_path=registry_path,
        base_dir=registry_path.parent,
        paths={
            "registry": registry_path,
            "upstream_checkout": root / "external" / "MAS-PromptBench",
        },
        stages={},
        metadata={**benchmark.metadata(), "cells": [cell["dataset"] for cell in benchmark.cells]},
    )
