"""CLI command handlers for evolution."""

from __future__ import annotations
import argparse
import importlib
import json
import sys
from pathlib import Path
from .cli_support import _load_evaluator


def cmd_search(args: argparse.Namespace) -> None:
    """Run the synthetic branching-evolutionary search loop over one skill file.

    Same honesty rule as the rest of this CLI: with the default ``synthetic``
    backend, this is a proposer, never a disposer. Nothing printed here is
    evidence that the selected candidate is actually a better skill.
    """
    from .search import make_graph_diagnose, run_bcso

    path = Path(args.path)
    if not path.is_file():
        raise SystemExit(f"not a file: {args.path}")
    seed_text = path.read_text(encoding="utf-8", errors="replace")
    if not seed_text.strip():
        raise SystemExit(f"file is empty: {args.path}")

    evaluator = _load_evaluator(args)
    max_archive_size = args.max_archive_size if args.max_archive_size > 0 else None

    graph_store = None
    diagnose_fn = None
    if args.graph_dir:
        from .graph import GraphStore
        graph_store = GraphStore(args.graph_dir)
        if args.graph_retrieval:
            diagnose_fn = make_graph_diagnose(graph_store, capability_contract_hash=args.capability_contract_hash)

    result = run_bcso(
        seed_text, evaluator,
        baseline=args.baseline,
        utility_min=args.utility_min,
        robustness_min=args.robustness_min,
        delta_u=args.delta_u,
        epsilon_hv=args.epsilon_hv,
        saturation_checks=args.saturation_checks,
        checkpoint_every=args.checkpoint_every,
        max_archive_size=max_archive_size,
        run_dir=args.run_dir,
        seed=args.seed,
        diagnose_fn=diagnose_fn,
        graph_store=graph_store,
        capability_contract_hash=args.capability_contract_hash,
    )
    report = result["report"]

    if args.json:
        json.dump({**report, "selected_text": result["selected"].text}, sys.stdout, indent=2)
        print()
        return

    print(f"SYNTHETIC search over {path} (baseline={report['baseline']}, backend={args.backend})")
    print("this is a candidate proposal only — not evidence of real improvement")
    print(f"state={report['state']}  generations={report['generations']}  checkpoints={report['checkpoints']}")
    print(f"selected candidate: {report['selected_id']}  "
          f"tokens={report['selected_tokens']}  utility={report['selected_utility']:.4f}")
    print(f"lineage: {' <- '.join(report['selected_lineage']) or '(seed)'}")
    print(f"G_final (one-shot test score) = {report['g_final']:.4f}")
    if args.run_dir:
        print(f"runs/ lineage written to {args.run_dir}")


def cmd_graph(args: argparse.Namespace) -> None:
    """Inspect a persistent evolution graph written by ``search --graph-dir``."""
    from .graph import GraphStore, mutation_family_stats

    store = GraphStore(args.graph_dir)

    if args.graph_command == "stats":
        stats = mutation_family_stats(store, capability_contract_hash=args.capability_contract_hash or None)
        payload = {
            "skills": sum(1 for _ in store.iter_skills()),
            "mutations": sum(1 for _ in store.iter_mutations()),
            "evaluations": sum(1 for _ in store.iter_evaluations()),
            "mutation_family_stats": stats,
        }
        if args.json:
            json.dump(payload, sys.stdout, indent=2)
            print()
            return
        print(f"skills={payload['skills']}  mutations={payload['mutations']}  evaluations={payload['evaluations']}")
        for family, row in sorted(stats.items(), key=lambda kv: kv[1]["mean_utility_delta"], reverse=True):
            print(f"  {family:<20} n={row['n']:<4} mean_utility_delta={row['mean_utility_delta']:+.4f} "
                  f"regression_rate={row['regression_rate']:.2f}")
        return

    if args.graph_command == "lineage":
        if not args.skill_hash:
            raise SystemExit("lineage requires --skill-hash")
        try:
            chain = store.lineage(args.skill_hash)
        except KeyError as exc:
            raise SystemExit(f"graph lineage failed: {exc}") from exc
        if args.json:
            json.dump([node.to_dict() for node in chain], sys.stdout, indent=2)
            print()
            return
        for node in chain:
            print(f"{node.skill_hash[:12]}  gen={node.generation}  generator={node.generator}  "
                  f"tokens={node.token_count}")
        return

    raise SystemExit(f"unknown graph subcommand: {args.graph_command!r}")


def cmd_optimize(args: argparse.Namespace) -> None:
    """Run proposal generation and programmatic scoring to convergence."""
    from .search import IterativeConfig, internal_propose, optimize_iteratively
    from .contracts import load_scenarios
    from .validators import evaluate_candidate
    from .optimizers import (
        combine_structural_and_behavioral,
        discover_optimization_spec,
        load_optimization_spec,
        propose_from_spec,
        score_from_spec,
    )

    def load_fn(spec: str):
        module_name, sep, function_name = spec.partition(":")
        if not sep:
            raise SystemExit(f"callable must be MODULE:FUNC: {spec}")
        try:
            loaded = getattr(importlib.import_module(module_name), function_name)
        except (ImportError, AttributeError) as exc:
            raise SystemExit(f"could not load callable {spec}: {exc}") from exc
        if not callable(loaded):
            raise SystemExit(f"configured object is not callable: {spec}")
        return loaded

    config = {}
    if args.config:
        try:
            config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"optimize: invalid config: {exc}") from exc
        if not isinstance(config, dict):
            raise SystemExit("optimize: config must be a JSON object")
    seed_file = args.seed_file or config.get("seed_file")
    proposal_spec = args.proposal_fn or config.get("proposal_fn")
    score_spec = args.score_fn or config.get("score_fn")
    executor_spec = args.executor_fn or config.get("executor_fn")
    scenario_file = args.scenario_file or config.get("scenario_file")
    optimization_spec_path = args.optimization_spec or config.get("optimization_spec")
    if not seed_file:
        raise SystemExit("optimize requires seed_file")
    seed_path = Path(seed_file)
    if not seed_path.is_file():
        raise SystemExit(f"seed file is not a file: {seed_path}")
    if optimization_spec_path is None:
        try:
            optimization_spec_path = discover_optimization_spec(seed_path)
        except ValueError as exc:
            raise SystemExit(f"optimize: {exc}") from exc
    try:
        optimization_spec = load_optimization_spec(optimization_spec_path) if optimization_spec_path else None
    except ValueError as exc:
        raise SystemExit(f"optimize: {exc}") from exc
    if not score_spec and not (executor_spec and scenario_file) and optimization_spec is None:
        raise SystemExit(
            "optimize requires score_fn, executor_fn+scenario_file, or an adjacent optimization spec"
        )
    if score_spec and optimization_spec is not None:
        raise SystemExit("optimize: score_fn and optimization_spec are alternative structural scorers")
    if executor_spec and scenario_file:
        scenarios = load_scenarios(scenario_file)
        executor = load_fn(executor_spec)
        rollouts = args.rollouts if args.rollouts is not None else int(config.get("rollouts", 1))
        if optimization_spec is None:
            score_fn = lambda text: evaluate_candidate(text, scenarios, executor, rollouts=rollouts)  # noqa: E731
        else:
            def score_fn(text):
                structural = score_from_spec(text, optimization_spec)
                behavioral = evaluate_candidate(text, scenarios, executor, rollouts=rollouts)
                return combine_structural_and_behavioral(structural, behavioral, optimization_spec)
    elif optimization_spec is not None:
        score_fn = lambda text: score_from_spec(text, optimization_spec)  # noqa: E731
    else:
        score_fn = load_fn(score_spec)
    if proposal_spec:
        proposal_fn = load_fn(proposal_spec)
    elif optimization_spec is not None:
        proposal_fn = propose_from_spec(optimization_spec, seed_path)
    else:
        proposal_fn = internal_propose
    output_dir = args.output_dir or config.get("output_dir")
    output_file_spec = args.output_file or config.get("output_file")
    result = optimize_iteratively(
        seed_path.read_text(encoding="utf-8", errors="replace"),
        score_fn, proposal_fn,
        config=IterativeConfig(
            max_turns=args.max_turns if args.max_turns is not None else int(config.get("max_turns", 8)),
            patience=args.patience if args.patience is not None else int(config.get("patience", 2)),
            output_dir=output_dir,
            robustness_weight=float(config.get("robustness_weight", 0.0)),
            density_weight=float(config.get("density_weight", 0.0)),
            cost_weight=float(config.get("cost_weight", 0.001)),
            lexical_replacements=dict(config.get("lexical_replacements", {})),
            operationalizations=dict(config.get("operationalizations", {})),
        ),
    )
    if output_dir:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        output_file = Path(output_file_spec) if output_file_spec else output / "PROPOSAL.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(result.selected.text, encoding="utf-8")
        (output / "run.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    if args.json:
        json.dump(result.to_dict(), sys.stdout, indent=2)
        print()
    else:
        print(f"selected={result.selected.id} stop_reason={result.stop_reason} turns={len(result.turns)}")
        if result.selected_score.get("behavioral_validation_required") is True:
            print("evidence=structural_proxy; held-out target-model execution is still required")
        if output_dir:
            print(f"final proposal: {output_file}")
