from dataclasses import dataclass

import pytest

from prompt_optimization.empirical import (
    EmpiricalRunConfig,
    JudgeResult,
    run_empirical,
)


@dataclass
class Scenario:
    id: str


class Subject:
    batch_isolated = False

    def __init__(self):
        self.batches = []

    def run_batch(self, requests):
        self.batches.append([r.unit.key for r in requests])
        return {r.unit.key: f"answer for {r.unit.scenario_id}" for r in requests}


class Judge:
    batch_isolated = True

    def __init__(self):
        self.batches = []

    def judge_batch(self, requests):
        self.batches.append([r.opaque_id for r in requests])
        return [JudgeResult(r.opaque_id, {"score": 1.0}) for r in requests]


def test_single_run_batches_subjects_by_version_and_blinds_judges():
    subject, judge = Subject(), Judge()
    result = run_empirical(
        versions={"old": "old skill", "new": "new skill"},
        scenarios=[Scenario("a"), Scenario("b")],
        subject_backend=subject,
        judge_backend=judge,
        rubric_for=lambda scenario: {"scenario": scenario.id},
        deterministic_check=lambda unit, text, scenario: {"length": len(text.split())},
        config=EmpiricalRunConfig(seed=7, rollouts=2, judge_batch_size=2, max_workers=1),
    )
    assert len(subject.batches) == 2
    assert all(len(batch) == 4 for batch in subject.batches)
    assert len(judge.batches) == 4
    assert len(result.transcripts) == 8
    assert set(result.judgments) == set(result.blind_map.values())
    assert result.metadata["judge_batch_isolated"] is True
    assert result.metadata["methodological_warning"] is None


def test_shared_context_judging_is_explicitly_marked_as_a_warning():
    subject, judge = Subject(), Judge()
    judge.batch_isolated = False
    result = run_empirical(
        versions={"old": "x"}, scenarios=[Scenario("a")],
        subject_backend=subject, judge_backend=judge,
        rubric_for=lambda _: {},
        config=EmpiricalRunConfig(max_workers=1),
    )
    assert "not independent" in result.metadata["methodological_warning"]


def test_empirical_run_rejects_duplicate_scenario_ids():
    with pytest.raises(ValueError, match="unique"):
        run_empirical(
            versions={"old": "skill"}, scenarios=[Scenario("a"), Scenario("a")],
            subject_backend=Subject(), judge_backend=Judge(), rubric_for=lambda _: {},
        )


def test_empirical_run_rejects_empty_version_text():
    with pytest.raises(ValueError, match="non-empty skill text"):
        run_empirical(
            versions={"old": " "}, scenarios=[Scenario("a")],
            subject_backend=Subject(), judge_backend=Judge(), rubric_for=lambda _: {},
        )


def test_empirical_run_rejects_unknown_subject_output():
    class ExtraSubject(Subject):
        def run_batch(self, requests):
            output = super().run_batch(requests)
            output["unexpected"] = "answer"
            return output

    with pytest.raises(ValueError, match="unknown units"):
        run_empirical(
            versions={"old": "skill"}, scenarios=[Scenario("a")],
            subject_backend=ExtraSubject(), judge_backend=Judge(), rubric_for=lambda _: {},
            config=EmpiricalRunConfig(max_workers=1),
        )
