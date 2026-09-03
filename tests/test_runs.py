"""Tests for the declarative run pipeline (manifest -> checks -> assemble -> seed).

This pipeline (``prompt_optimization.runs``) is what ``prompt-opt run`` drives
and what produced the project's one real empirical pilot
(``output/claude skills/architectural-reasoning/empirical-run-2026-08-29/``).
It previously had no test coverage at all.
"""
import json
from pathlib import Path

import pytest

from prompt_optimization.contracts import HardInvariant, IntentContract
from prompt_optimization.graph import GraphStore
from prompt_optimization.runs.assemble import assemble, write_assembly
from prompt_optimization.runs.checks import CheckExpressionError, eval_derived, run_checks, write_checks
from prompt_optimization.runs.manifest import RunManifest, load_run_manifest
from prompt_optimization.runs.seed import seed_graph


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------
def test_manifest_paths_resolve_relative_to_the_manifest_file(tmp_path):
    (tmp_path / "sub").mkdir()
    manifest_path = tmp_path / "sub" / "run.json"
    manifest_path.write_text(json.dumps({
        "id": "r1",
        "paths": {"contract": "../contract.json", "graph_dir": "graph"},
    }), encoding="utf-8")
    manifest = load_run_manifest(manifest_path)
    assert manifest.resolve("contract") == (tmp_path / "contract.json").resolve()
    assert manifest.resolve("graph_dir") == (tmp_path / "sub" / "graph").resolve()


def test_manifest_requires_nonempty_id(tmp_path):
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"paths": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty id"):
        load_run_manifest(path)


def test_manifest_rejects_unknown_stage(tmp_path):
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"id": "r1", "stages": {"bogus": {}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported run stage"):
        load_run_manifest(path)


def test_manifest_resolve_unknown_path_raises(tmp_path):
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"id": "r1"}), encoding="utf-8")
    manifest = load_run_manifest(path)
    with pytest.raises(KeyError):
        manifest.resolve("nope")


# ---------------------------------------------------------------------------
# checks: constrained derived-expression evaluator
# ---------------------------------------------------------------------------
def test_eval_derived_basic_boolean_algebra():
    env = {"word_count": 120, "flagged": True}
    assert eval_derived("word_count <= 300 and not flagged", env) is False  # flagged is True
    assert eval_derived("word_count > 300 or flagged", env) is True  # flagged is True
    env_clean = {"word_count": 120, "flagged": False}
    assert eval_derived("word_count <= 300 and not flagged", env_clean) is True
    assert eval_derived("word_count > 300 or flagged", env_clean) is False


@pytest.mark.parametrize("expr", [
    "__import__('os')",
    "word_count.bit_length()",
    "open('x')",
    "word_count; True",
    "word_count[0]",
])
def test_eval_derived_rejects_unsafe_expressions(expr):
    with pytest.raises(CheckExpressionError):
        eval_derived(expr, {"word_count": 1})


def test_eval_derived_rejects_unknown_identifier():
    with pytest.raises(CheckExpressionError, match="unknown field"):
        eval_derived("nope == True", {})


# ---------------------------------------------------------------------------
# checks: run_checks / write_checks
# ---------------------------------------------------------------------------
def _write_transcript(base: Path, version: str, scenario: str, rollout: str, text: str) -> None:
    path = base / version / scenario / f"{rollout}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _checks_manifest(tmp_path: Path, *, rollouts: list[str]) -> RunManifest:
    manifest_path = tmp_path / "run.json"
    manifest_path.write_text(json.dumps({
        "id": "checks-test",
        "paths": {
            "transcripts_dir": "transcripts",
            "deterministic_checks": "deterministic_checks.json",
        },
        "stages": {
            "checks": {
                "versions": ["v1", "v2"],
                "scenarios": ["s1"],
                "rollouts": rollouts,
                "units": {
                    "s1": [
                        {"field": "word_count", "op": "word_count"},
                        {"field": "mentions_bad", "op": "mentions_any", "phrases": ["forbidden phrase"]},
                        {"field": "ok", "op": "derived", "expr": "word_count <= 5 and not mentions_bad"},
                    ],
                },
            },
        },
    }), encoding="utf-8")
    return load_run_manifest(manifest_path)


def test_run_checks_single_rollout_uses_legacy_key(tmp_path):
    _write_transcript(tmp_path / "transcripts", "v1", "s1", "rollout_01", "one two three")
    _write_transcript(tmp_path / "transcripts", "v2", "s1", "rollout_01", "one two three four five six")
    manifest = _checks_manifest(tmp_path, rollouts=["rollout_01"])
    payload = run_checks(manifest)
    assert set(payload["results"]) == {"v1:s1", "v2:s1"}
    assert payload["results"]["v1:s1"]["word_count"] == 3
    assert payload["results"]["v1:s1"]["ok"] is True
    assert payload["results"]["v2:s1"]["ok"] is False  # word_count 6 > 5


def test_run_checks_multi_rollout_keys_include_rollout_and_report_missing(tmp_path):
    _write_transcript(tmp_path / "transcripts", "v1", "s1", "rollout_01", "short reply")
    _write_transcript(tmp_path / "transcripts", "v1", "s1", "rollout_02", "also a short reply here")
    # v1:s1:rollout_03 and both v2 rollouts are deliberately absent.
    manifest = _checks_manifest(tmp_path, rollouts=["rollout_01", "rollout_02", "rollout_03"])
    payload = run_checks(manifest)
    assert set(payload["results"]) == {"v1:s1:rollout_01", "v1:s1:rollout_02"}
    # 2 versions x 1 scenario x 3 rollouts = 6 units; 2 transcripts exist -> 4 missing.
    assert len(payload["meta"]["missing_transcripts"]) == 4
    out = write_checks(manifest, payload)
    assert json.loads(out.read_text(encoding="utf-8")) == payload


def test_run_checks_requires_versions_and_scenarios(tmp_path):
    manifest_path = tmp_path / "run.json"
    manifest_path.write_text(json.dumps({
        "id": "bad", "paths": {"transcripts_dir": "t", "deterministic_checks": "d.json"},
        "stages": {"checks": {"versions": [], "scenarios": ["s1"]}},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty 'versions'"):
        run_checks(load_run_manifest(manifest_path))


# ---------------------------------------------------------------------------
# assemble: full pipeline with a real contract, K=1 and K=3
# ---------------------------------------------------------------------------
def _contract(tmp_path: Path) -> Path:
    contract = IntentContract(
        id="runs-test-contract",
        outcome="Answer the question.",
        activation=("any request",),
        hard_invariants=(HardInvariant("always-true", "must hold", min_pass_rate=1.0),),
        outputs=(),
    )
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract.to_dict()), encoding="utf-8")
    return path


def _build_run(tmp_path: Path, *, rollouts: list[str], pass_pattern: dict[str, list[bool]]) -> Path:
    """Build a full run directory. ``pass_pattern[f'{version}:{scenario}']`` is
    the per-rollout pass/fail list for invariant 'always-true'."""
    _contract(tmp_path)
    versions = ["baseline", "candidate"]
    scenarios = ["sc1", "sc2"]

    blind_map: dict[str, str] = {}
    raw_scores: dict[str, dict] = {}
    counter = 0
    for version in versions:
        for scenario in scenarios:
            key = f"{version}:{scenario}"
            passes = pass_pattern[key]
            for i, rollout in enumerate(rollouts):
                counter += 1
                opaque = f"opaque-{counter}"
                unit_key = key if len(rollouts) == 1 else f"{key}:{rollout}"
                blind_map[unit_key] = opaque
                raw_scores[opaque] = {
                    "task_success": 0.9, "correctness": 0.9,
                    "invariant_adherence": 1.0 if passes[i] else 0.0, "calibration": 0.8,
                    "invariants": {"always-true": passes[i]},
                    "rationale": "synthetic",
                }

    (tmp_path / "judging").mkdir()
    (tmp_path / "judging" / "blind_map.json").write_text(json.dumps({"mapping": blind_map}), encoding="utf-8")
    (tmp_path / "judging" / "raw_scores.json").write_text(json.dumps(raw_scores), encoding="utf-8")
    (tmp_path / "deterministic_checks.json").write_text(json.dumps({"results": {}}), encoding="utf-8")

    manifest_path = tmp_path / "run.json"
    manifest_path.write_text(json.dumps({
        "id": "assemble-test",
        "paths": {
            "contract": "contract.json",
            "blind_map": "judging/blind_map.json",
            "raw_scores": "judging/raw_scores.json",
            "deterministic_checks": "deterministic_checks.json",
            "final_results": "final_results.json",
        },
        "stages": {
            "assemble": {
                "baseline": {"version": "baseline", "skill_tokens": 100, "id": "baseline-v1"},
                "candidate": {"version": "candidate", "skill_tokens": 80, "id": "candidate-v1"},
                "scenarios": scenarios,
                "all_invariant_ids": ["always-true"],
                "tested_invariants": {"sc1": ["always-true"], "sc2": ["always-true"]},
                "deterministic_overrides": {},
                "compare": {"noninferiority_margin": 0.5, "seed": 1, "bootstrap_resamples": 200},
            },
        },
    }), encoding="utf-8")
    return manifest_path


def test_assemble_single_rollout_all_pass_is_accepted(tmp_path):
    manifest = load_run_manifest(_build_run(
        tmp_path, rollouts=["rollout_01"],
        pass_pattern={
            "baseline:sc1": [True], "baseline:sc2": [True],
            "candidate:sc1": [True], "candidate:sc2": [True],
        },
    ))
    output = assemble(manifest)
    assert output["contract_report"]["accepted"] is True
    assert output["rollout_counts"] == {"sc1": 1, "sc2": 1}
    assert output["utility_hierarchical_interval"] is None
    out_path = write_assembly(manifest, output)
    assert json.loads(out_path.read_text(encoding="utf-8")) == output


def test_assemble_multi_rollout_requires_all_rollouts_to_pass_hard_invariant(tmp_path):
    # candidate:sc1 fails on rollout_02 only -> aggregate invariant must be False,
    # even though 2 of 3 rollouts individually passed.
    manifest = load_run_manifest(_build_run(
        tmp_path, rollouts=["rollout_01", "rollout_02", "rollout_03"],
        pass_pattern={
            "baseline:sc1": [True, True, True], "baseline:sc2": [True, True, True],
            "candidate:sc1": [True, False, True], "candidate:sc2": [True, True, True],
        },
    ))
    output = assemble(manifest)
    candidate_sc1 = output["scenario_results"]["candidate"]["sc1"]
    assert candidate_sc1["invariants"]["always-true"] is False
    assert candidate_sc1["metadata"]["invariant_pass_rate"]["always-true"] == pytest.approx(2 / 3)
    assert output["contract_report"]["hard_invariants"]["always-true"]["passed"] is False
    assert output["contract_report"]["accepted"] is False
    assert output["rollout_counts"] == {"sc1": 3, "sc2": 3}
    assert output["utility_hierarchical_interval"] is not None
    assert output["utility_hierarchical_interval"]["lower"] <= output["utility_hierarchical_interval"]["upper"]


def test_assemble_missing_blind_map_entry_raises(tmp_path):
    manifest_path = _build_run(
        tmp_path, rollouts=["rollout_01"],
        pass_pattern={
            "baseline:sc1": [True], "baseline:sc2": [True],
            "candidate:sc1": [True], "candidate:sc2": [True],
        },
    )
    blind_map_path = tmp_path / "judging" / "blind_map.json"
    payload = json.loads(blind_map_path.read_text(encoding="utf-8"))
    del payload["mapping"]["candidate:sc2"]
    blind_map_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="no entry for unit"):
        assemble(load_run_manifest(manifest_path))


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------
def test_seed_graph_writes_nodes_edge_and_evaluations(tmp_path):
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "baseline.md").write_text("baseline skill text", encoding="utf-8")
    (tmp_path / "skills" / "candidate.md").write_text("candidate skill text", encoding="utf-8")
    final = {
        "promotion": {"verdict": "ACCEPTED", "reasons": [], "hard_invariants_report": {"utility": {"delta_mean": 0.05}}, "token_delta": -20},
        "scenario_results": {
            "baseline": {"sc1": {"utility": 0.7, "invariants": {"a": True}, "metadata": {"omega": {}, "opaque_id": "o1"}}},
            "candidate": {"sc1": {"utility": 0.75, "invariants": {"a": True}, "metadata": {"omega": {}, "opaque_id": "o2"}}},
        },
    }
    manifest_path = tmp_path / "run.json"
    manifest_path.write_text(json.dumps({
        "id": "seed-test",
        "paths": {
            "graph_dir": "graph",
            "final_results": "final_results.json",
            "baseline_skill": "skills/baseline.md",
            "candidate_skill": "skills/candidate.md",
        },
        "stages": {
            "seed": {
                "baseline": "baseline", "candidate": "candidate",
                "versions": {
                    "baseline": {"skill": "baseline_skill", "tokens": 100},
                    "candidate": {"skill": "candidate_skill", "tokens": 80, "generation": 1},
                },
                "mutation": {"family": "human_reauthoring"},
            },
        },
    }), encoding="utf-8")
    manifest = load_run_manifest(manifest_path)
    summary = seed_graph(manifest, final)
    assert summary["counts"] == {"skills": 2, "mutations": 1, "evaluations": 2}
    store = GraphStore(tmp_path / "graph")
    assert store.get_skill(summary["candidate_hash"]).parent_hashes == (summary["baseline_hash"],)
