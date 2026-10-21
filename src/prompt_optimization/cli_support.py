"""Shared parsing, file-discovery, and scan helpers for the CLI."""

from __future__ import annotations
import argparse
import math
import sys
from pathlib import Path


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
