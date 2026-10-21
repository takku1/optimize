"""CLI command handlers for analysis."""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .cli_support import _load_evaluator


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
