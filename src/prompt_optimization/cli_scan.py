"""CLI command handlers for scan."""

from __future__ import annotations
import argparse
import json
import sys
from .cli_support import _load_evaluator, _print_human, _run_scan, iter_text_files


def cmd_scan(args: argparse.Namespace) -> None:
    files = iter_text_files(args.paths, limit=args.limit)
    evaluator = _load_evaluator(args)
    results = _run_scan(files, evaluator, args.seed, args.samples)
    if args.json:
        json.dump({"target": args.target, "backend": args.backend, "synthetic": evaluator.synthetic,
                   "files": results}, sys.stdout, indent=2)
        print()
        return
    _print_human(results, args.target or "VERIFY_PRIOR", synthetic=evaluator.synthetic)


def cmd_plan(args: argparse.Namespace) -> None:
    files = iter_text_files(args.paths, limit=args.limit)
    evaluator = _load_evaluator(args)
    results = _run_scan(files, evaluator, args.seed, args.samples)
    misses = args.seed

    from .metrics import (
        apply_hard_gates,
        pareto_frontier,
        rate_distortion_frontier,
        select_next_experiment,
    )

    valid = [r for r in results if not r.get("error")]
    if not valid:
        print("no scan results to plan over", file=sys.stderr)
        raise SystemExit(1)

    gates = dict(getattr(args, "gate", []) or [])
    passed, blocked = apply_hard_gates(valid, gates, operator=args.gate_op)

    # The synthetic scaffold proposes candidates; a real held-out evaluator must
    # dispose. Nothing here is a production claim unless evaluator.synthetic is
    # False, i.e. a real backend (rubric/callable) produced the numbers.
    if evaluator.synthetic:
        disclaimer = (
            "synthetic scaffold: candidates only — real held-out evaluation "
            "(--backend rubric/callable) disposes before any claim"
        )
    else:
        disclaimer = f"real backend ({evaluator.name}): candidates disposed by held-out judgment"

    if not passed:
        if not args.json:
            print(
                f"no candidate passes the hard gates {gates} "
                f"(operator {args.gate_op}); no supported improvement is claimed."
            )
        if args.json:
            json.dump({
                "synthetic": evaluator.synthetic,
                "backend": args.backend,
                "note": disclaimer,
                "gates": {k: v for k, v in gates.items()},
                "gate_op": args.gate_op,
                "blocked": blocked,
                "supported_improvement": False,
            }, sys.stdout, indent=2)
            print()
        return

    rd = rate_distortion_frontier([{ "tokens": r["tokens"], "distortion": r["distortion"],
                                     "prompt": r["path"] } for r in passed])
    pareto = pareto_frontier(
        passed,
        maximize=("predicted_activation", "reliability"),
        minimize=("tokens", "off_target", "uncertainty"),
    )
    next_exp = select_next_experiment(passed)
    supported = bool(passed) and not evaluator.synthetic

    if args.json:
        json.dump({
            "synthetic": evaluator.synthetic,
            "backend": args.backend,
            "note": disclaimer,
            "gates": {k: v for k, v in gates.items()},
            "gate_op": args.gate_op,
            "blocked": blocked,
            "rate_distortion_frontier": rd,
            "pareto_candidates": pareto,
            "next_experiment": next_exp,
            "cache_misses": misses,
            "supported_improvement": supported,
        }, sys.stdout, indent=2)
        print()
        return

    print(disclaimer)
    print(f"gates ({args.gate_op}): {gates}")
    if blocked:
        print(f"\nblocked by hard gates ({len(blocked)}):")
        for b in blocked:
            print(f"  {b['path']:<48} dist={b['distortion']:.3f} off={b['off_target']:.3f}")
    print("\nrate-distortion frontier (best distortion at each token budget):")
    for pt in rd:
        print(f"  tokens={pt['tokens']:<6} distortion={pt['distortion']:.3f}  <- {pt['prompt']}")
    print(f"\nPareto-non-dominated candidates ({len(pareto)}):")
    for c in pareto:
        print(f"  {c['path']:<48} act={c['predicted_activation']:.3f} "
              f"rel={c['reliability']:.3f} tok={c['tokens']}")
    print("\nrecommended next experiment:")
    print(f"  {next_exp['path']}  (gain x uncertainty = {next_exp['expected_gain'] * next_exp['uncertainty']:.3f})")
    if not supported:
        print("\nNOTE: backend is synthetic — this is a candidate proposal only, not a")
        print("supported improvement claim. Re-run with --backend rubric/callable to dispose.")
