import json
import sys
from pathlib import Path

import pytest

from prompt_optimization.cli import main


def test_optimize_cli_can_build_internal_score_from_scenarios(tmp_path, monkeypatch):
    module = tmp_path / "adapter.py"
    module.write_text(
        "def propose(current, feedback, turn): return current\n"
        "def execute(skill, scenario, rollout): return 'context decision'\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    seed = tmp_path / "seed.md"
    seed.write_text("seed", encoding="utf-8")
    scenarios = tmp_path / "scenarios.json"
    scenarios.write_text(json.dumps({"scenarios": [{
        "id": "s1", "request": "do it",
        "metadata": {"success_band": {"required_any_phrases": ["context"]}},
    }]}), encoding="utf-8")
    output = tmp_path / "run"
    assert main(["optimize", str(seed), "--proposal-fn", "adapter:propose",
                 "--executor-fn", "adapter:execute", "--scenario-file", str(scenarios),
                 "--output-dir", str(output), "--max-turns", "1", "--patience", "1"]) == 0
    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert run["selected_score"]["hard_invariants_passed"] is True


def test_optimize_cli_honors_output_paths_from_config(tmp_path, monkeypatch):
    module = tmp_path / "configured_adapter.py"
    module.write_text(
        "def score(text): return {'utility': 1, 'tokens': 1, 'hard_invariants_passed': True}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    seed = tmp_path / "seed.md"
    seed.write_text("seed", encoding="utf-8")
    output = tmp_path / "configured-run"
    proposal = tmp_path / "selected.md"
    config = tmp_path / "run.json"
    config.write_text(json.dumps({
        "seed_file": str(seed),
        "score_fn": "configured_adapter:score",
        "output_dir": str(output),
        "output_file": str(proposal),
        "max_turns": 1,
        "patience": 1,
    }), encoding="utf-8")

    assert main(["optimize", "--config", str(config)]) == 0
    assert (output / "run.json").is_file()
    assert proposal.read_text(encoding="utf-8") == "seed"


def test_optimize_cli_rejects_non_object_config(tmp_path):
    config = tmp_path / "run.json"
    config.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit, match="JSON object"):
        main(["optimize", "--config", str(config)])


def test_optimize_cli_auto_discovers_declarative_spec(tmp_path):
    seed = tmp_path / "skill.md"
    seed.write_text("# Weak\n", encoding="utf-8")
    (tmp_path / "optimization.json").write_text(json.dumps({
        "id": "weak-v1",
        "activation": {"required_all": ["# Weak"]},
        "revision": {"document": "# Strong\n\nVerify behavior."},
        "checks": [{"id": "verification", "kind": "contains", "value": "Verify behavior"}],
    }), encoding="utf-8")
    output = tmp_path / "run"

    assert main(["optimize", str(seed), "--output-dir", str(output),
                 "--max-turns", "2", "--patience", "1"]) == 0

    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert run["selected_score"]["optimization_spec_id"] == "weak-v1"
    assert run["selected_score"]["behavioral_validation_required"] is True
