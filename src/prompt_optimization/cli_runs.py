"""CLI command handlers for runs."""

from __future__ import annotations
import argparse
import json
import sys


def cmd_run(args: argparse.Namespace) -> None:
    """Drive a declarative experiment run from a path-portable manifest.

    ``--config`` names a ``run.json`` manifest (see
    :mod:`prompt_optimization.runs.manifest`). By default every stage declared
    in the manifest executes in order: ``checks`` -> ``assemble`` -> ``seed``.
    ``--stage`` narrows execution to one stage. Stages write their outputs to
    the manifest's declared paths (deterministic_checks.json,
    final_results.json, and the graph store), all resolved relative to the
    manifest so a run directory stays self-contained and portable.
    """
    from .runs import assemble, checks, load_run_manifest, seed

    manifest = load_run_manifest(args.config)

    stage = args.stage
    if stage is not None and stage not in ("checks", "assemble", "seed"):
        raise SystemExit(f"run: unknown stage {stage!r} (choose checks, assemble, or seed)")
    targets = (stage,) if stage else ("checks", "assemble", "seed")

    ran: dict[str, Any] = {}
    for name in targets:
        if not manifest.has_stage(name):
            if stage is not None:
                raise SystemExit(f"run: manifest {manifest.id} does not declare stage {name!r}")
            continue
        if name == "checks":
            payload = checks.run_checks(manifest)
            out = checks.write_checks(manifest, payload)
            ran["checks"] = {"output": str(out),
                             "entries": len(payload.get("results", {})),
                             "missing": payload.get("meta", {}).get("missing_transcripts", [])}
        elif name == "assemble":
            output = assemble.assemble(manifest)
            out = assemble.write_assembly(manifest, output)
            verdict = output["promotion"]["verdict"]
            ran["assemble"] = {"output": str(out), "promotion_verdict": verdict,
                               "reasons": list(output["promotion"]["reasons"])}
        elif name == "seed":
            final_path = manifest.resolve("final_results").with_suffix(".json")
            import json as _json
            final = _json.loads(final_path.read_text(encoding="utf-8"))
            summary = seed.seed_graph(manifest, final)
            ran["seed"] = summary

    if args.json:
        json.dump(ran, sys.stdout, indent=2)
        print()
    else:
        for name, info in ran.items():
            print(f"[{name}]")
            if name == "checks":
                print(f"  wrote {info['output']} ({info['entries']} entries, "
                      f"{len(info['missing'])} missing transcripts)")
            elif name == "assemble":
                print(f"  wrote {info['output']} -> {info['promotion_verdict']}")
            elif name == "seed":
                counts = info["counts"]
                print(f"  seeded {info['graph_dir']}: skills={counts['skills']} "
                      f"mutations={counts['mutations']} evaluations={counts['evaluations']}")
