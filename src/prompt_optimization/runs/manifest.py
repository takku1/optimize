"""Path-portable declarative run manifest.

A run manifest is a single JSON file, normally ``run.json`` next to the
experiment's outputs. Its ``paths`` are keyed file/directory names whose values
resolve **relative to the manifest file**, so a run directory can be moved or
shared without editing code and without host-specific absolute paths (the
``sys.path.insert`` + ``Z:\\...`` hard-coding that used to live in one-off
scripts).

Stages select which pipeline steps a ``prompt-opt run`` invocation performs:
``checks`` (deterministic transcript checks), ``assemble`` (blinded judges +
checks -> ScenarioResults -> contract/promotion verdict), and ``seed``
(evolution-graph records). A stage is a mapping from stage name to its own
options; an absent stage simply does not run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class RunManifest:
    """Validated, path-portable description of one empirical run."""

    id: str
    source_path: Path
    base_dir: Path
    paths: Mapping[str, Path]
    stages: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def resolve(self, key: str) -> Path:
        """Return an absolute path for a named manifest path (raising if unknown)."""
        if key not in self.paths:
            raise KeyError(f"manifest has no path named {key!r} (have {sorted(self.paths)})")
        return self.paths[key]

    def stage(self, name: str) -> Mapping[str, Any]:
        """Return the options mapping for a stage (empty mapping when undeclared)."""
        opts = self.stages.get(name, {})
        if opts is None:
            return {}
        if not isinstance(opts, Mapping):
            raise ValueError(f"run stage {name!r} must be an object")
        return opts

    def has_stage(self, name: str) -> bool:
        return name in self.stages


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def load_run_manifest(path: str | Path) -> RunManifest:
    """Load and validate a run manifest, resolving all paths against the file's directory.

    Raises :class:`ValueError` for structural problems (non-object, missing or
    empty ``id``, unknown stage names). Path values may be relative (resolved
    against the manifest directory) or absolute; existence is not checked here,
    so a manifest can be authored before its outputs exist.
    """
    manifest_path = Path(path)
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid run manifest {manifest_path}: {exc}") from exc
    raw = _mapping(raw, "run manifest")

    run_id = str(raw.get("id", "")).strip()
    if not run_id:
        raise ValueError("run manifest requires a non-empty id")

    base = manifest_path.resolve().parent
    paths: dict[str, Path] = {}
    for key, value in _mapping(raw.get("paths", {}), "run paths").items():
        key = str(key).strip()
        if not key:
            raise ValueError("run path names must be non-empty")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"run path {key!r} must be a non-empty file/dir path")
        raw_path = Path(value).expanduser()
        paths[key] = (raw_path if raw_path.is_absolute() else (base / raw_path)).resolve()

    stages = _mapping(raw.get("stages", {}), "run stages")
    for stage_name in stages.keys():
        if stage_name not in ("checks", "assemble", "seed"):
            raise ValueError(f"unsupported run stage: {stage_name!r}")

    return RunManifest(
        id=run_id,
        source_path=manifest_path.resolve(),
        base_dir=base,
        paths=paths,
        stages=stages,
        metadata=dict(_mapping(raw.get("metadata", {}), "run metadata")),
    )
