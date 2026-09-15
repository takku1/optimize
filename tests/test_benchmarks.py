from pathlib import Path

import pytest

from prompt_optimization import load_external_benchmark, to_reference_run_manifest


BENCHMARK = Path(__file__).parents[1] / "benchmarks" / "mas-promptbench-v1.json"


def test_external_benchmark_registry_is_reproducible():
    benchmark = load_external_benchmark(BENCHMARK)
    assert benchmark.id == "mas-promptbench-v1"
    assert len(benchmark.cells) == 3
    assert len(benchmark.content_hash) == 64
    assert benchmark.metadata()["benchmark_status"] == "REFERENCE_ONLY"


def test_external_benchmark_rejects_duplicate_cells(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(BENCHMARK.read_text(encoding="utf-8").replace(
        '"dataset": "hotpotqa"', '"dataset": "math"', 1), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate benchmark dataset"):
        load_external_benchmark(path)


def test_registry_translates_to_safe_reference_manifest():
    manifest = to_reference_run_manifest(BENCHMARK)
    assert manifest.id == "mas-promptbench-v1-reference"
    assert manifest.metadata["benchmark_id"] == "mas-promptbench-v1"
    assert not manifest.has_stage("assemble")
