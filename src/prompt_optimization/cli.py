"""Command-line interface for the prompt-optimization pipeline.

Run against a file, a set of files, or a whole project directory:

    python -m prompt_optimization scan path/to/file.py path/to/dir
    python -m prompt_optimization scan --json /project/src
    python -m prompt_optimization plan /project/docs

The pipeline treats each discoverable text file as a prompt candidate, reduces
its token embedding sequence to a normalized contextual vector (via attention
and a shared KV-cache), and scores it against the behavior-attractor basins.
``scan`` reports per-file metrics; ``plan`` layers Pareto/rate-distortion
selection and a next-experiment recommendation on top of the same corpus scan.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from pathlib import Path

from . import __version__  # noqa: F401  (re-exported for introspection)

# Hidden/derived directories that are noise for a project scan.
_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".benchmarks",
}
_TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".rst", ".toml", ".cfg", ".ini", ".yaml", ".yml",
    ".json", ".csv", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".sh",
    ".rs", ".go", ".java", ".c", ".h", ".cpp", ".hpp", ".sql",
}


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _at_least_two(value: str) -> int:
    parsed = int(value)
    if parsed < 2:
        raise argparse.ArgumentTypeError("must be an integer of at least 2")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("must be finite")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = _finite_float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _unit_float(value: str) -> float:
    parsed = _finite_float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


def _fraction(value: str) -> float:
    parsed = _finite_float(value)
    if not 0 <= parsed < 1:
        raise argparse.ArgumentTypeError("must be in [0, 1)")
    return parsed


def _confidence(value: str) -> float:
    parsed = _finite_float(value)
    if not 0 < parsed < 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1 (exclusive)")
    return parsed


def _model_dimension(value: str) -> int:
    parsed = _positive_int(value)
    if parsed % 4:
        raise argparse.ArgumentTypeError("must be divisible by 4")
    return parsed


def iter_text_files(paths: list[str], *, limit: int | None = None) -> list[tuple[str, str]]:
    """Yield ``(display_path, text)`` for text files under ``paths``.

    Directories are walked recursively; binaries, hidden files, and a known set
    of generated/derived directories are skipped. ``limit`` caps the number of
    files (``None`` for all).
    """
    seen: dict[str, str] = {}
    order: list[tuple[str, str]] = []

    def record(path: Path) -> None:
        if limit is not None and len(order) >= limit:
            return
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        display = path.as_posix()
        if display not in seen:
            seen[display] = text
            order.append((display, text))

    for raw in paths:
        path = Path(raw)
        if not path.exists():
            print(f"warning: path does not exist: {raw}", file=sys.stderr)
            continue
        if path.is_file():
            record(path)
            continue
        for root, dirs, files in path.walk():
            dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS and not d.startswith(".")]
            for fname in sorted(files):
                record(Path(root) / fname)
                if limit is not None and len(order) >= limit:
                    break
            if limit is not None and len(order) >= limit:
                break

    return order


def _run_scan(files: list[tuple[str, str]], evaluator, seed: int, samples: int) -> list[dict]:
    results = []
    for display, text in files:
        if not text.strip():
            continue
        try:
            res = evaluator.evaluate(display, text, seed=seed, samples=samples)
            if res.metadata.get("truncated"):
                print(f"warning: {display} truncated to {res.tokens} of "
                      f"{res.metadata['original_tokens']} tokens (--max-tokens)", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - surface per-file failures
            results.append({
                "path": display, "tokens": 0, "error": str(exc),
                "predicted_activation": 0.0, "score": 0.0, "reliability": 0.0,
            })
            continue
        results.append({
            "path": display,
            "tokens": res.tokens,
            "words": len(text.split()),
            "predicted_activation": round(res.activation, 4),
            "similarity": round(res.similarity, 4),
            "reliability": round(res.reliability, 4),
            "distortion": round(res.distortion, 4),
            "off_target": round(res.off_target, 4),
            "expected_gain": round(res.activation * res.reliability, 4),
            "uncertainty": round(res.uncertainty, 4),
            "score": round(res.score, 4),
            "truncated": bool(res.metadata.get("truncated", False)),
            "original_tokens": res.metadata.get("original_tokens", res.tokens),
        })
    return results


def _print_human(results: list[dict], target_name: str, *, synthetic: bool) -> None:
    print(f"target attractor: {target_name}")
    print(f"{'file':<46}{'tok':>6}{'synAlign':>9}{'act':>7}{'rel':>7}{'score':>9}")
    print("-" * 86)
    for r in sorted(results, key=lambda x: x.get("score", 0.0), reverse=True):
        if r.get("error"):
            print(f"{r['path']:<46}{'ERR':>6}  {r['error']}")
            continue
        mark = "*" if r.get("truncated") else " "
        print(f"{r['path']:<45}{mark}{r['tokens']:>6}{r['similarity']:>9.3f}"
              f"{r['predicted_activation']:>7.3f}{r['reliability']:>7.3f}{r['score']:>9.3f}")
    if any(r.get("truncated") for r in results):
        print("\n* truncated to --max-tokens; score reflects only the first part of the file.")
    print("\nranked by score (not synAlign); synAlign is a diagnostic column only —")
    print("embedding similarity is not behavioral performance.")
    if synthetic:
        print("Synthetic ordering only; it is NOT evidence of behavioral equivalence.")
        print("A real held-out evaluator must dispose before any performance claim.")


def _add_backend_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--backend", choices=("synthetic", "rubric", "callable"), default="synthetic",
                   help="evaluator backend (default: synthetic attractor scaffold)")
    p.add_argument("--rubric-file", default=None,
                   help="JSON file of real judgments, required for --backend rubric")
    p.add_argument("--evaluator-fn", default=None,
                   help="MODULE:FUNC to call for --backend callable")
    p.add_argument("--max-tokens", type=_positive_int, default=1500,
                   help="truncate text to this many tokens before the synthetic "
                        "backend's O(n^2) attention pass (default: 1500)")


def _load_evaluator(args: argparse.Namespace):
    from .evaluators import load_evaluator
    return load_evaluator(
        args.backend,
        d_model=args.d_model,
        target_name=args.target,
        seed=args.seed,
        rubric_file=args.rubric_file,
        evaluator_fn=args.evaluator_fn,
        max_tokens=args.max_tokens,
    )


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


def cmd_attribute(args: argparse.Namespace) -> None:
    import re as _re

    from .attribution import shapley_values

    path = Path(args.path)
    if not path.is_file():
        raise SystemExit(f"not a file: {args.path}")
    text = path.read_text(encoding="utf-8", errors="replace")

    if args.unit == "line":
        units = [ln for ln in text.splitlines() if ln.strip()]
        join = "\n"
    else:
        units = [p for p in _re.split(r"\n\s*\n", text) if p.strip()]
        join = "\n\n"
    if not units:
        raise SystemExit("no non-empty components found to attribute")

    if len(units) > args.max_components:
        n = args.max_components
        buckets: list[list[str]] = [[] for _ in range(n)]
        for i, u in enumerate(units):
            buckets[i * n // len(units)].append(u)
        units = [join.join(b) for b in buckets if b]

    evaluator = _load_evaluator(args)
    display = path.as_posix()

    def value_fn(coalition) -> float:
        included = [units[i] for i in sorted(coalition)]
        sub_text = join.join(included)
        if not sub_text.strip():
            return 0.0
        return evaluator.evaluate(display, sub_text, seed=args.seed, samples=args.samples).score

    # shapley_values runs *exact* permutations whenever samples is None and
    # n_players <= 10 -- at 10 players that's 10! = 3,628,800 evaluator calls.
    # Only let a small, cheap component count go exact by default; force
    # Monte Carlo sampling above that regardless of the library's own
    # threshold (found while stress-testing on real skill files that hung).
    shapley_samples = args.shapley_samples
    if shapley_samples is None and len(units) > 6:
        shapley_samples = 200
    values = shapley_values(len(units), value_fn, samples=shapley_samples, seed=args.seed)
    ranked = sorted(range(len(units)), key=lambda i: values[i], reverse=True)

    if args.json:
        json.dump({
            "path": display,
            "backend": args.backend,
            "synthetic": evaluator.synthetic,
            "unit": args.unit,
            "components": [
                {"index": i, "shapley": round(float(values[i]), 6), "preview": units[i][:80]}
                for i in ranked
            ],
        }, sys.stdout, indent=2)
        print()
        return

    print(f"attribution: {display}  (unit={args.unit}, backend={args.backend}, "
          f"components={len(units)})")
    print(
        "Shapley values are the evaluator's score, averaged over marginal "
        f"contribution across component coalitions; NOT a causal claim about the "
        f"underlying model unless the backend is real (synthetic={evaluator.synthetic})."
    )
    print("-" * 86)
    for i in ranked:
        preview = units[i][:60].replace("\n", " / ")
        print(f"[{i:>3}] {values[i]:>8.4f}  {preview}")


def cmd_compare(args: argparse.Namespace) -> None:
    """Compare paired original/candidate scenario observations."""
    from .contracts import compare_contract_results, load_comparison_input, load_contract

    try:
        contract = load_contract(args.contract)
        input_contract, baseline, candidate = load_comparison_input(args.results)
        if input_contract is not None and input_contract != contract.id:
            raise ValueError(
                f"comparison input contract {input_contract!r} does not match {contract.id!r}"
            )
        report = compare_contract_results(
            contract,
            baseline,
            candidate,
            noninferiority_margin=args.margin,
            seed=args.seed,
            bootstrap_resamples=args.bootstrap_resamples,
            confidence=args.confidence,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"compare failed: {exc}") from exc

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
        return

    decision = "ACCEPTED" if report["accepted"] else "REJECTED"
    utility = report["utility"]
    print(f"{decision}: contract={report['contract_id']} scenarios={report['scenario_count']}")
    print(f"utility delta={utility['delta_mean']:.4f} "
          f"CI[{utility['delta_interval']['lower']:.4f}, {utility['delta_interval']['upper']:.4f}] "
          f"margin={utility['noninferiority_margin']:.4f}")
    print("hard invariants:")
    for invariant_id, result in report["hard_invariants"].items():
        status = "pass" if result["passed"] else "FAIL"
        print(f"  {status}: {invariant_id} "
              f"candidate={result['candidate_pass_rate']:.3f} "
              f"required={result['min_pass_rate']:.3f}")
    if report["costs"]:
        print("cost deltas:")
        for key, result in report["costs"].items():
            print(f"  {key}: {result['delta']:.4f}")


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


def cmd_report(args: argparse.Namespace) -> None:
    """Assemble a BCSO-Bench report: taxonomy coverage, activation P/R, maturity tier, provenance."""
    from .capability import ProvenanceRecord, classify_maturity, coverage_report
    from .contracts import load_scenarios
    from .evaluators import ActivationLabel, activation_precision_recall

    report: dict = {}

    if args.scenarios:
        scenarios = load_scenarios(args.scenarios)
        report["taxonomy_coverage"] = coverage_report(scenarios)

    if args.activation_labels:
        raw = json.loads(Path(args.activation_labels).read_text(encoding="utf-8"))
        labels = [ActivationLabel(**row) for row in raw]
        report["activation"] = activation_precision_recall(labels)

    if args.metrics:
        metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
        report["maturity"] = classify_maturity(metrics)

    if not report:
        raise SystemExit("report needs at least one of --scenarios, --activation-labels, --metrics")

    report["provenance"] = ProvenanceRecord(
        model_id=args.model_id, benchmark_version=args.benchmark_version,
    ).to_dict()

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
        return

    print("BCSO-Bench report")
    print("-" * 40)
    if "taxonomy_coverage" in report:
        coverage = report["taxonomy_coverage"]
        print(f"taxonomy coverage: {coverage['coverage_fraction']:.1%} over {coverage['n_scenarios']} scenarios")
        if coverage["uncovered_cells"]:
            print(f"  uncovered cells: {coverage['uncovered_cells']}")
    if "activation" in report:
        activation = report["activation"]
        print(f"activation: precision={activation['precision']:.3f} recall={activation['recall']:.3f} "
              f"f1={activation['f1']:.3f}")
    if "maturity" in report:
        maturity = report["maturity"]
        print(f"maturity tier: {maturity['tier']}")
        if maturity["reasons"]:
            print(f"  blocked by: {maturity['reasons']}")
    print(f"provenance: model={args.model_id} benchmark_version={args.benchmark_version}")


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


def cmd_promote(args: argparse.Namespace) -> None:
    """Compare a baseline and candidate skill version and render a promotion verdict.

    Never claims VALIDATED_IMPROVEMENT off a synthetic backend or without a
    real paired contract/scenario comparison — see
    ``capability.promotion.compare_versions``.
    """
    from .capability import compare_versions
    from .contracts import load_comparison_input, load_contract

    baseline_path, candidate_path = Path(args.baseline), Path(args.candidate)
    for label, path in (("--baseline", baseline_path), ("--candidate", candidate_path)):
        if not path.is_file():
            raise SystemExit(f"{label} is not a file: {path}")

    evaluator = _load_evaluator(args)
    baseline_text = baseline_path.read_text(encoding="utf-8", errors="replace")
    candidate_text = candidate_path.read_text(encoding="utf-8", errors="replace")
    baseline_result = evaluator.evaluate(str(baseline_path), baseline_text, seed=args.seed, samples=args.samples)
    candidate_result = evaluator.evaluate(str(candidate_path), candidate_text, seed=args.seed, samples=args.samples)

    contract = None
    baseline_scenarios = candidate_scenarios = None
    if args.contract and args.results:
        try:
            contract = load_contract(args.contract)
            input_contract, baseline_scenarios, candidate_scenarios = load_comparison_input(args.results)
            if input_contract is not None and input_contract != contract.id:
                raise ValueError(
                    f"comparison input contract {input_contract!r} does not match {contract.id!r}"
                )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise SystemExit(f"promote failed: {exc}") from exc
    elif args.contract or args.results:
        raise SystemExit("--contract and --results must be supplied together")

    comparison = compare_versions(
        baseline_path.as_posix(), baseline_result.tokens, {"U": baseline_result.score, "R": baseline_result.reliability},
        candidate_path.as_posix(), candidate_result.tokens, {"U": candidate_result.score, "R": candidate_result.reliability},
        evaluator_synthetic=evaluator.synthetic,
        contract=contract,
        baseline_scenarios=baseline_scenarios,
        candidate_scenarios=candidate_scenarios,
        noninferiority_margin=args.margin,
        seed=args.seed,
        bootstrap_resamples=args.bootstrap_resamples,
    )

    if args.json:
        json.dump(comparison.to_dict(), sys.stdout, indent=2)
        print()
        return

    print(f"VERDICT: {comparison.verdict.value}")
    print(f"  {baseline_path.name} -> {candidate_path.name}  "
          f"tokens {comparison.baseline_tokens} -> {comparison.candidate_tokens} "
          f"(delta {comparison.token_delta:+d})")
    print(f"  Pareto dominant: {comparison.pareto_dominant or 'neither (tradeoff)'}")
    for reason in comparison.reasons:
        print(f"  - {reason}")
    if comparison.hard_invariants_report:
        print("  hard invariants:")
        for invariant_id, result in comparison.hard_invariants_report["hard_invariants"].items():
            status = "pass" if result["passed"] else "FAIL"
            print(f"    {status}: {invariant_id}")


def cmd_verify(args: argparse.Namespace) -> None:
    """Check a doc's registered claims against live-recomputed values.

    ``script`` is a normal Python file, kept alongside the doc it checks
    (see e.g. a negative-control run's ``verify_claims.py`` next to its
    ``REPORT.md``): it does its own I/O (GraphStore queries, JSON reads,
    metric recomputation) and defines a module-level ``CLAIMS: list[Claim]``
    pairing each doc assertion with its freshly recomputed value. This
    command loads the script, verifies every claim, prints a pass/fail
    report, and exits non-zero on any failure -- so a doc's factual claims
    can be gated the same way code is gated by tests, instead of trusted
    the way a prose summary has to be. See ``capability.claims`` for why.
    """
    import importlib.util

    from .capability import all_passed, format_report, verify_claims

    script_path = Path(args.script)
    if not script_path.is_file():
        raise SystemExit(f"verify: not a file: {script_path}")

    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"verify: could not load {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    claims = getattr(module, "CLAIMS", None)
    if claims is None:
        raise SystemExit(f"verify: {script_path} does not define a module-level CLAIMS list")

    results = verify_claims(claims)
    print(format_report(results))
    if not all_passed(results):
        raise SystemExit(1)


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prompt-opt",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"prompt-opt {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("paths", nargs="+", help="files or directories to scan")
        p.add_argument("--d-model", type=_model_dimension, default=32,
                       help="embedding dimension (must match attractor dim; default 32)")
        p.add_argument("--target", default=None,
                       help="target attractor name (default: first attractor)")
        p.add_argument("--seed", type=_nonnegative_int, default=0, help="RNG seed")
        p.add_argument("--samples", type=_at_least_two, default=64,
                       help="noisy samples per file for reliability/uncertainty")
        p.add_argument("--limit", type=_positive_int, default=None,
                       help="max number of files to process (default: all)")

    p_scan = sub.add_parser("scan", help="score each file against the target attractor")
    add_common(p_scan)
    _add_backend_args(p_scan)
    p_scan.add_argument("--json", action="store_true", help="emit JSON")
    p_scan.set_defaults(func=cmd_scan)

    def _gate_arg(value: str) -> tuple[str, float]:
        if "=" not in value:
            raise argparse.ArgumentTypeError("gate must be KEY=BOUND, e.g. distortion=0.2")
        key, bound = value.split("=", 1)
        if not key:
            raise argparse.ArgumentTypeError("gate key must not be empty")
        return key, _finite_float(bound)

    p_plan = sub.add_parser("plan", help="pareto/rate-distortion frontier + next experiment")
    add_common(p_plan)
    _add_backend_args(p_plan)
    p_plan.add_argument("--gate", action="append", type=_gate_arg, default=None,
                        metavar="KEY=BOUND",
                        help="mandatory critical constraint (hard gate, not tradeable); repeatable")
    p_plan.add_argument("--gate-op", choices=("max", "min"), default="max",
                        help="pass when value <= BOUND (max) or >= BOUND (min); default max")
    p_plan.add_argument("--json", action="store_true", help="emit JSON")
    p_plan.set_defaults(func=cmd_plan)

    p_attr = sub.add_parser("attribute", help="Shapley attribution of prompt components")
    p_attr.add_argument("path", help="single file to attribute")
    p_attr.add_argument("--unit", choices=("line", "paragraph"), default="line",
                        help="component granularity (default: line)")
    p_attr.add_argument("--max-components", type=_positive_int, default=10,
                        help="merge components down to at most this many (default: 10)")
    p_attr.add_argument("--shapley-samples", type=_positive_int, default=None,
                        help="Monte Carlo permutation samples (default: exact for <=10 components)")
    p_attr.add_argument("--d-model", type=_model_dimension, default=32,
                        help="embedding dimension (must match attractor dim; default 32)")
    p_attr.add_argument("--target", default=None,
                        help="target attractor name (default: first attractor)")
    p_attr.add_argument("--seed", type=_nonnegative_int, default=0, help="RNG seed")
    p_attr.add_argument("--samples", type=_at_least_two, default=64,
                        help="noisy samples per coalition for reliability/uncertainty")
    _add_backend_args(p_attr)
    p_attr.add_argument("--json", action="store_true", help="emit JSON")
    p_attr.set_defaults(func=cmd_attribute)

    p_compare = sub.add_parser(
        "compare", help="compare paired original/candidate scenario results against an intent contract"
    )
    p_compare.add_argument("--contract", required=True, help="IntentContract JSON file")
    p_compare.add_argument("--results", required=True, help="paired baseline/candidate result JSON file")
    p_compare.add_argument("--margin", type=_nonnegative_float, default=0.05,
                           help="allowed lower-bound utility regression (default: 0.05)")
    p_compare.add_argument("--confidence", type=_confidence, default=0.95,
                           help="bootstrap confidence level (default: 0.95)")
    p_compare.add_argument("--bootstrap-resamples", type=_positive_int, default=2000,
                           help="bootstrap resamples for the paired utility interval")
    p_compare.add_argument("--seed", type=_nonnegative_int, default=0, help="RNG seed")
    p_compare.add_argument("--json", action="store_true", help="emit JSON")
    p_compare.set_defaults(func=cmd_compare)

    from .search import BASELINES

    p_search = sub.add_parser(
        "search", help="run the synthetic branching-evolutionary BCSO search loop over one skill file"
    )
    p_search.add_argument("path", help="single skill/prompt file to search from")
    p_search.add_argument("--baseline", choices=sorted(BASELINES), default="full_bcso",
                          help="named baseline strategy (default: full_bcso)")
    p_search.add_argument("--utility-min", type=_unit_float, default=0.5, help="qualification floor on fitness U")
    p_search.add_argument("--robustness-min", type=_unit_float, default=0.5, help="qualification floor on fitness R")
    p_search.add_argument("--delta-u", type=_fraction, default=0.02,
                          help="allowed utility slack for the cheapest-candidate selection rule")
    p_search.add_argument("--epsilon-hv", type=_nonnegative_float, default=0.01,
                          help="relative hypervolume-growth threshold for saturation")
    p_search.add_argument("--saturation-checks", type=_positive_int, default=3,
                          help="consecutive checkpoints below --epsilon-hv required to freeze")
    p_search.add_argument("--checkpoint-every", type=_positive_int, default=2,
                          help="generations between Pareto-archive checkpoints")
    p_search.add_argument("--max-archive-size", type=_nonnegative_int, default=40,
                          help="cap the non-dominated archive to this many candidates (0 for unbounded)")
    p_search.add_argument("--run-dir", default=None,
                          help="write the runs/ generation lineage layout here")
    p_search.add_argument("--graph-dir", default=None,
                          help="persist every candidate/mutation/evaluation into a content-addressed "
                               "evolution graph here (survives past this run — see prompt_optimization.graph)")
    p_search.add_argument("--graph-retrieval", action="store_true",
                          help="with --graph-dir, bias mutation choice toward the operator with the best "
                               "recorded track record in that graph (retrieval-conditioned proposal)")
    p_search.add_argument("--capability-contract-hash", default="",
                          help="tag recorded graph nodes with this Γ hash, scoping retrieval to one capability family")
    p_search.add_argument("--d-model", type=_model_dimension, default=32,
                          help="embedding dimension (must match attractor dim; default 32)")
    p_search.add_argument("--target", default=None, help="target attractor name (default: first attractor)")
    p_search.add_argument("--seed", type=_nonnegative_int, default=0, help="RNG seed")
    p_search.add_argument("--samples", type=_at_least_two, default=64,
                          help="noisy samples per evaluation for reliability/uncertainty")
    _add_backend_args(p_search)
    p_search.add_argument("--json", action="store_true", help="emit JSON")
    p_search.set_defaults(func=cmd_search)

    p_report = sub.add_parser(
        "report", help="assemble a BCSO-Bench report: taxonomy coverage, activation P/R, maturity, provenance"
    )
    p_report.add_argument("--scenarios", default=None, help="Scenario JSON file for taxonomy coverage")
    p_report.add_argument("--activation-labels", default=None,
                          help="JSON list of {task_id, expected, observed} activation labels")
    p_report.add_argument("--metrics", default=None,
                          help="JSON dict of maturity-tier metrics (see capability.classify_maturity)")
    p_report.add_argument("--model-id", default="unspecified", help="provenance: model identifier")
    p_report.add_argument("--benchmark-version", default="0.1.0", help="provenance: benchmark version tag")
    p_report.add_argument("--json", action="store_true", help="emit JSON")
    p_report.set_defaults(func=cmd_report)

    p_promote = sub.add_parser(
        "promote", help="compare a baseline and candidate skill version and render a promotion verdict"
    )
    p_promote.add_argument("--baseline", required=True, help="baseline (old) skill file")
    p_promote.add_argument("--candidate", required=True, help="candidate (new) skill file")
    p_promote.add_argument("--contract", default=None, help="IntentContract JSON file (with --results)")
    p_promote.add_argument("--results", default=None,
                           help="paired baseline/candidate ScenarioResult JSON file (with --contract)")
    p_promote.add_argument("--margin", type=_nonnegative_float, default=0.05,
                           help="allowed lower-bound utility regression (default: 0.05)")
    p_promote.add_argument("--bootstrap-resamples", type=_positive_int, default=2000,
                           help="bootstrap resamples for the paired utility interval")
    p_promote.add_argument("--d-model", type=_model_dimension, default=32,
                           help="embedding dimension (must match attractor dim; default 32)")
    p_promote.add_argument("--target", default=None, help="target attractor name (default: first attractor)")
    p_promote.add_argument("--seed", type=_nonnegative_int, default=0, help="RNG seed")
    p_promote.add_argument("--samples", type=_at_least_two, default=64,
                           help="noisy samples per evaluation for reliability/uncertainty")
    _add_backend_args(p_promote)
    p_promote.add_argument("--json", action="store_true", help="emit JSON")
    p_promote.set_defaults(func=cmd_promote)

    p_graph = sub.add_parser("graph", help="inspect a persistent evolution graph written by search --graph-dir")
    p_graph.add_argument("graph_dir", help="graph directory (the same path passed to search --graph-dir)")
    graph_sub = p_graph.add_subparsers(dest="graph_command", required=True)

    graph_stats = graph_sub.add_parser("stats", help="skill/mutation/evaluation counts + per-family success stats")
    graph_stats.add_argument("--capability-contract-hash", default="",
                             help="scope stats to one capability family's Γ hash")
    graph_stats.add_argument("--json", action="store_true", help="emit JSON")

    graph_lineage = graph_sub.add_parser("lineage", help="print one skill's ancestry back to its root")
    graph_lineage.add_argument("--skill-hash", required=True, help="skill hash to trace")
    graph_lineage.add_argument("--json", action="store_true", help="emit JSON")

    p_graph.set_defaults(func=cmd_graph)

    p_verify = sub.add_parser(
        "verify", help="check a doc's registered claims (a CLAIMS: list[Claim] script) against live-recomputed values"
    )
    p_verify.add_argument("script", help="python script defining a module-level CLAIMS: list[capability.Claim]")
    p_verify.set_defaults(func=cmd_verify)

    p_run = sub.add_parser(
        "run", help="drive a declarative experiment manifest: checks -> assemble -> seed"
    )
    p_run.add_argument("--config", required=True, help="path to a run.json manifest")
    p_run.add_argument("--stage", choices=("checks", "assemble", "seed"), default=None,
                       help="run only one stage (default: all stages declared in the manifest)")
    p_run.add_argument("--json", action="store_true", help="emit JSON")
    p_run.set_defaults(func=cmd_run)

    p_opt = sub.add_parser(
        "optimize", help="run one program-scored, multi-turn proposal optimization"
    )
    p_opt.add_argument("seed_file", nargs="?", help="seed proposal/skill markdown")
    p_opt.add_argument("--config", default=None, help="JSON config for the complete run")
    p_opt.add_argument("--proposal-fn", required=False,
                       help="MODULE:FUNC(current_text, feedback, turn) -> proposed text")
    p_opt.add_argument("--score-fn", required=False,
                       help="MODULE:FUNC(text) -> score mapping with utility/tokens")
    p_opt.add_argument("--executor-fn", required=False,
                       help="MODULE:FUNC(skill_text, scenario, rollout) -> response text")
    p_opt.add_argument("--scenario-file", required=False,
                       help="Scenario fixture used with --executor-fn")
    p_opt.add_argument("--optimization-spec", required=False,
                       help="declarative JSON revision/check spec; auto-discovers an adjacent spec")
    p_opt.add_argument("--rollouts", type=_positive_int, default=None,
                       help="rollouts per scenario when using --executor-fn")
    p_opt.add_argument("--max-turns", type=_positive_int, default=None)
    p_opt.add_argument("--patience", type=_positive_int, default=None)
    p_opt.add_argument("--output-dir", default=None,
                       help="write PROPOSAL.md, run.json, and every turn")
    p_opt.add_argument("--output-file", default=None,
                       help="final proposal path (defaults to OUTPUT_DIR/PROPOSAL.md)")
    p_opt.add_argument("--json", action="store_true", help="emit JSON")
    p_opt.set_defaults(func=cmd_optimize)

    return parser


def _use_utf8_streams() -> None:
    # Scanned files are arbitrary user text and may contain characters (emoji,
    # box-drawing, …) outside a Windows console's cp1252 default. Without this,
    # printing a preview snippet containing one crashes with UnicodeEncodeError
    # partway through output (found running `attribute` on a real skill file
    # with an emoji in it). Some non-file stdout replacements (e.g. pytest's
    # capsys) don't support reconfigure(); that's fine, nothing to fix there.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _use_utf8_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
