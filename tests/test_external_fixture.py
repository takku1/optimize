from pathlib import Path

from prompt_optimization.contracts import load_scenarios


def test_context_control_fixture_expands_visible_taxonomy():
    path = Path(__file__).parent / "fixtures" / "scenarios" / "context-optimization-v1.json"
    scenarios = load_scenarios(path)
    assert len(scenarios) == 8
    assert {tag for scenario in scenarios for tag in scenario.tags} >= {
        "context:long", "context:noisy", "failure_mode:goal-drift"
    }
