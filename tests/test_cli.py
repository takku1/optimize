"""Smoke tests for the CLI (file/project scanning and planning)."""
import json

import pytest

from prompt_optimization.cli import iter_text_files, main


def _write_project(root, files):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
    return root


def test_iter_text_files_skips_ignored_dirs_and_binaries(tmp_path):
    root = _write_project(tmp_path, {
        "src/app.py": "def main(): return 1",
        "src/notes.md": "# hello",
        "src/image.png": b"\x89PNG\r\n\x1a\n",  # binary, not in text suffixes
        ".venv/lib.py": "noise",
        "__pycache__/x.cpython.py": "noise",
    })
    out = iter_text_files([str(root)])
    names = [n for n, _ in out]
    assert any(n.endswith("src/app.py") for n in names)
    assert any(n.endswith("src/notes.md") for n in names)
    assert not any("image" in n for n in names)
    assert not any(".venv" in n for n in names)
    assert not any("__pycache__" in n for n in names)


def test_scan_json_emits_per_file_metrics(tmp_path, capsys):
    root = _write_project(tmp_path, {
        "a.py": "verify the prior hypothesis independently and cite sources",
        "b.md": "improvise a creative alternative approach boldly",
    })
    rc = main(["scan", "--json", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["files"]
    paths = {f["path"] for f in out["files"]}
    assert any(p.endswith("a.py") for p in paths)
    assert any(p.endswith("b.md") for p in paths)


def test_plan_json_lays_out_frontier(tmp_path, capsys):
    root = _write_project(tmp_path, {
        "short.py": "confirm",
        "long.py": "verify each prior finding independently with sources " * 5,
    })
    rc = main(["plan", "--json", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert "rate_distortion_frontier" in out
    assert "next_experiment" in out
    assert out["next_experiment"]["path"]


def test_plan_hard_gates_are_wired_and_block(tmp_path, capsys):
    root = _write_project(tmp_path, {
        "a.py": "verify the prior hypothesis independently and cite sources",
        "b.py": "improvise a creative alternative approach",
    })
    rc = main(["plan", "--json", "--gate", "distortion=0.0", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["gates"] == {"distortion": 0.0}  # --gate actually parsed and applied
    assert out["blocked"] and not out["supported_improvement"]


def test_plan_permissive_gate_yields_frontier(tmp_path, capsys):
    root = _write_project(tmp_path, {"a.py": "verify each prior finding independently"})
    rc = main(["plan", "--json", "--gate", "distortion=10.0", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert not out["blocked"]
    assert out["rate_distortion_frontier"]


def test_unknown_target_fails(tmp_path, capsys):
    root = _write_project(tmp_path, {"a.py": "whatever text content"})
    try:
        main(["scan", "--target", "NOPE", str(root)])
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code != 0


def test_scan_json_reports_backend_and_synthetic_flag(tmp_path, capsys):
    root = _write_project(tmp_path, {"a.py": "verify each prior finding independently"})
    rc = main(["scan", "--json", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["backend"] == "synthetic"
    assert out["synthetic"] is True


def test_scan_human_output_is_ranked_by_score_not_similarity(tmp_path, capsys):
    root = _write_project(tmp_path, {
        "a.py": "verify the prior hypothesis independently and cite sources",
        "b.md": "improvise a creative alternative approach boldly",
    })
    rc = main(["scan", "--json", str(root)])
    scores = {f["path"]: f["score"] for f in json.loads(capsys.readouterr().out)["files"]}

    rc = main(["scan", str(root)])
    lines = capsys.readouterr().out.splitlines()
    printed_order = [ln for ln in lines if any(p in ln for p in scores)]
    ordered_paths = []
    for ln in printed_order:
        for p in scores:
            if p in ln:
                ordered_paths.append(p)
                break
    assert rc == 0
    assert ordered_paths == sorted(scores, key=lambda p: scores[p], reverse=True)


def test_plan_with_rubric_backend_reports_supported_improvement(tmp_path, capsys):
    root = _write_project(tmp_path, {"a.py": "text"})
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps({
        f"{root.as_posix()}/a.py": {"score": 0.9, "reliability": 0.95},
    }), encoding="utf-8")
    rc = main(["plan", "--json", "--backend", "rubric", "--rubric-file", str(rubric),
               "--gate", "distortion=0.5", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["synthetic"] is False
    assert out["supported_improvement"] is True


def test_plan_with_synthetic_backend_never_claims_supported_improvement(tmp_path, capsys):
    root = _write_project(tmp_path, {"a.py": "verify each prior finding independently"})
    rc = main(["plan", "--json", "--gate", "distortion=10.0", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["supported_improvement"] is False


def test_attribute_json_ranks_components_by_shapley_value(tmp_path, capsys):
    f = tmp_path / "a.py"
    f.write_text("verify each prior finding\nimprovise wildly\ncite the sources", encoding="utf-8")
    rc = main(["attribute", "--json", "--unit", "line", str(f)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["synthetic"] is True
    assert len(out["components"]) == 3
    shapleys = [c["shapley"] for c in out["components"]]
    assert shapleys == sorted(shapleys, reverse=True)


def test_attribute_rejects_missing_file(tmp_path):
    missing = tmp_path / "nope.py"
    try:
        main(["attribute", str(missing)])
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code != 0


def test_attribute_never_runs_exact_permutations_above_six_components(tmp_path, monkeypatch):
    # shapley_values runs exact permutations whenever samples is None and
    # n_players <= 10 -- at 10 players that's 10! = 3,628,800 calls. cli.py
    # must force sampling once components exceed 6, regardless of the
    # library's own <=10 threshold (found hanging on a real 485-line skill
    # file before this guard existed).
    f = tmp_path / "a.py"
    f.write_text("\n".join(f"line {i}" for i in range(20)), encoding="utf-8")

    calls = {}

    def spy(n_players, value_fn, *, samples=None, seed=0):
        calls["n_players"] = n_players
        calls["samples"] = samples
        return [0.0] * n_players

    monkeypatch.setattr("prompt_optimization.attribution.shapley_values", spy)
    main(["attribute", "--json", "--unit", "line", "--max-components", "10", str(f)])
    assert calls["n_players"] == 10
    assert calls["samples"] is not None  # sampling forced, not the exact/None path


def test_scan_json_marks_truncated_files(tmp_path, capsys):
    # A file over --max-tokens gets scored on a partial read; JSON consumers
    # need this in-band, not only as a stderr warning (found reviewing real
    # skill files where scan silently scored ~30% of the text).
    root = _write_project(tmp_path, {"a.py": "verify each prior finding independently " * 20})
    rc = main(["scan", "--json", "--max-tokens", "5", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    f = out["files"][0]
    assert f["truncated"] is True
    assert f["tokens"] == 5
    assert f["original_tokens"] > 5


def test_scan_json_does_not_mark_short_files_truncated(tmp_path, capsys):
    root = _write_project(tmp_path, {"a.py": "short text"})
    rc = main(["scan", "--json", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["files"][0]["truncated"] is False


def test_cli_does_not_crash_on_non_cp1252_content(tmp_path):
    # Windows' console/redirect default (cp1252) can't encode arbitrary
    # scanned-file content (e.g. an emoji); printing it used to crash
    # mid-output with UnicodeEncodeError (found running `attribute` on a real
    # skill file containing a warning emoji). main() must reconfigure stdout
    # to tolerate this regardless of what the runtime default is.
    import io

    root = _write_project(tmp_path, {"a.py": "warning ⚠️ emoji content here"})
    fake_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    import sys as _sys
    old_stdout = _sys.stdout
    _sys.stdout = fake_stdout
    try:
        rc = main(["scan", str(root)])
    finally:
        _sys.stdout = old_stdout
    assert rc == 0


def test_search_json_reports_released_state(tmp_path, capsys):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "# Example\n\nVerify each prior finding independently. Verify each prior finding independently.\n",
        encoding="utf-8",
    )
    rc = main(["search", "--json", "--baseline", "compression_only", "--checkpoint-every", "1",
               str(skill)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["state"] == "released"
    assert out["synthetic"] is True
    assert out["selected_text"]


def test_search_writes_run_dir_lineage(tmp_path, capsys):
    skill = tmp_path / "SKILL.md"
    skill.write_text("# Example\n\nDo the thing. Do the thing again.\n", encoding="utf-8")
    run_dir = tmp_path / "runs1"
    rc = main(["search", "--baseline", "no_skill", "--run-dir", str(run_dir), str(skill)])
    capsys.readouterr()
    assert rc == 0
    assert (run_dir / "gen_000" / "seed.md").exists()
    assert (run_dir / "final" / "SKILL.md").exists()


def test_search_rejects_missing_file(tmp_path):
    missing = tmp_path / "nope.md"
    try:
        main(["search", str(missing)])
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code != 0


def test_report_json_combines_activation_and_maturity(tmp_path, capsys):
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps([
        {"task_id": "t1", "expected": True, "observed": True},
        {"task_id": "t2", "expected": False, "observed": False},
    ]), encoding="utf-8")
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({"utility": 0.9, "activation_precision": 0.9, "activation_recall": 0.9}),
                        encoding="utf-8")
    rc = main(["report", "--json", "--activation-labels", str(labels), "--metrics", str(metrics),
               "--model-id", "demo"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["activation"]["precision"] == 1.0
    assert out["maturity"]["tier"] == "qualified"
    assert out["provenance"]["model_id"] == "demo"


def test_report_requires_at_least_one_input():
    try:
        main(["report"])
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code != 0


def test_report_taxonomy_coverage_from_reviewed_fixture(capsys):
    rc = main(["report", "--json", "--scenarios", "tests/fixtures/scenarios/hookify-writing-rules-v1.json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert "taxonomy_coverage" in out
    assert out["taxonomy_coverage"]["n_scenarios"] > 0


@pytest.mark.parametrize(
    "argv",
    [
        ["scan", "--samples", "1", "."],
        ["scan", "--seed", "-1", "."],
        ["scan", "--d-model", "6", "."],
        ["scan", "--max-tokens", "0", "."],
        ["search", "--checkpoint-every", "0", "README.md"],
        ["search", "--epsilon-hv", "nan", "README.md"],
    ],
)
def test_cli_rejects_invalid_numeric_controls(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
