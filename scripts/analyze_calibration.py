"""Analyze a fully crossed calibration JSONL file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prompt_optimization.calibration import CORE_DIMENSIONS, agreement_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ratings", type=Path, help="JSONL rating rows")
    parser.add_argument("--bootstrap-resamples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.ratings.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = agreement_report(rows, dimensions=CORE_DIMENSIONS,
                              bootstrap_resamples=args.bootstrap_resamples, seed=args.seed)
    report["input"] = str(args.ratings)
    report["evidence_status"] = "REHEARSAL_ONLY" if any(row.get("evidence_status") != "INDEPENDENT" for row in rows) else "INDEPENDENT_PENDING_REVIEW"
    rendered = json.dumps(report, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
