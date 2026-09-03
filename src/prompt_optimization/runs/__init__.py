"""Declarative experiment runs without ad-hoc per-run scripts.

The empirical pipeline used to require a hand-written Python script per run
(``deterministic_checks.py``, ``assemble_results.py``, ``seed_graph.py``)
that reached back into the package with a ``sys.path.insert`` and hard-coded
host paths. This subpackage replaces that with a single path-portable run
manifest (``prompt-opt run --config run.json``) and the engines that execute
its stages: deterministic checks, blinded-judge + deterministic assembly into
paired scenario results, contract comparison, promotion verdict, and
evolution-graph seeding. Paths in a manifest resolve relative to the manifest
file, so a run directory is self-contained and portable.
"""

from .manifest import RunManifest, load_run_manifest

__all__ = ["RunManifest", "load_run_manifest"]
