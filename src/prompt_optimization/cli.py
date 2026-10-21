"""Command-line parser and public CLI entry point."""

from __future__ import annotations
import argparse
import sys
from . import __version__
from .cli_support import _IGNORED_DIRS, _TEXT_SUFFIXES, _add_backend_args, _at_least_two, _confidence, _finite_float, _fraction, _load_evaluator, _model_dimension, _nonnegative_float, _nonnegative_int, _positive_int, _print_human, _run_scan, _unit_float, iter_text_files
from .cli_scan import cmd_plan, cmd_scan
from .cli_analysis import cmd_attribute, cmd_compare, cmd_promote, cmd_report, cmd_verify
from .cli_evolution import cmd_graph, cmd_optimize, cmd_search
from .cli_runs import cmd_run

__all__ = [
    "__version__", "_IGNORED_DIRS", "_TEXT_SUFFIXES", "_add_backend_args",
    "_at_least_two", "_confidence", "_finite_float", "_fraction",
    "_load_evaluator", "_model_dimension", "_nonnegative_float",
    "_nonnegative_int", "_positive_int", "_print_human", "_run_scan",
    "_unit_float", "iter_text_files", "cmd_attribute", "cmd_compare",
    "cmd_graph", "cmd_optimize", "cmd_plan", "cmd_promote", "cmd_report",
    "cmd_run", "cmd_scan", "cmd_search", "cmd_verify", "build_parser",
    "main",
]


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
    p_search.add_argument("--baseline", choices=sorted(BASELINES), default="focused",
                          help="named baseline strategy (default: focused; use full_bcso for exhaustive search)")
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
    p_search.add_argument("--max-archive-size", type=_nonnegative_int, default=12,
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
