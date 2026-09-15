"""Run the local sequential ablation over one prompt/skill artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prompt_optimization.evaluators import load_evaluator
from prompt_optimization.search import DEFAULT_ABLATIONS, run_ablation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--backend", choices=("synthetic", "rubric", "callable"), default="synthetic")
    parser.add_argument("--rubric-file", default=None)
    parser.add_argument("--evaluator-fn", default=None)
    parser.add_argument("--baseline", action="append", dest="baselines", choices=DEFAULT_ABLATIONS)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--run-root", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    text = args.path.read_text(encoding="utf-8", errors="replace")
    evaluator = load_evaluator(args.backend, rubric_file=args.rubric_file, evaluator_fn=args.evaluator_fn)
    report = run_ablation(text, evaluator, baselines=tuple(args.baselines or DEFAULT_ABLATIONS),
                          seed=args.seed, run_root=args.run_root)
    report["evidence_status"] = "SYNTHETIC_REHEARSAL" if evaluator.synthetic else "EXTERNAL_EVALUATOR_PENDING_REVIEW"
    rendered = json.dumps(report, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
