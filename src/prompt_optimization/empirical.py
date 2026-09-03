"""One-run orchestration for real empirical prompt evaluations.

This module deliberately does not call a model or provide a model vendor
adapter. It owns the protocol around an optional system-under-test boundary so
an external runner can be measured without changing the benchmark's blinding
and provenance rules.

The optimization is operational rather than statistical: subjects may be
batched by skill version, judges may be submitted as isolated batch items, and
all local checks/assembly happen in one parent run.  A judge backend must
explicitly declare whether its batch items are context-isolated; shared-context
judging is recorded as a methodological compromise instead of being silently
treated as independent evidence.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Protocol

from .evaluators.calibration import generate_blind_ids


@dataclass(frozen=True)
class EvaluationUnit:
    version: str
    scenario_id: str
    rollout: int = 1

    @property
    def key(self) -> str:
        return f"{self.version}:{self.scenario_id}:rollout_{self.rollout:02d}"


@dataclass(frozen=True)
class SubjectRequest:
    unit: EvaluationUnit
    skill_text: str
    scenario: Any


@dataclass(frozen=True)
class JudgeRequest:
    """A blinded request.  It contains no version or baseline/candidate label."""

    opaque_id: str
    scenario: Any
    transcript: str
    rubric: Any


@dataclass(frozen=True)
class JudgeResult:
    opaque_id: str
    score: Mapping[str, Any]


class SubjectBackend(Protocol):
    """Generate transcripts; implementations may process a whole version batch."""

    batch_isolated: bool

    def run_batch(self, requests: list[SubjectRequest]) -> Mapping[str, str]: ...


class JudgeBackend(Protocol):
    """Score a batch while declaring its independence guarantee."""

    batch_isolated: bool

    def judge_batch(self, requests: list[JudgeRequest]) -> Iterable[JudgeResult]: ...


@dataclass
class EmpiricalRunConfig:
    seed: int = 0
    rollouts: int = 1
    subject_batch_size: int = 0  # 0 means one batch per version
    judge_batch_size: int = 1
    max_workers: int = 4
    judge_all: bool = True

    def __post_init__(self) -> None:
        if self.rollouts < 1:
            raise ValueError("rollouts must be positive")
        if self.max_workers < 1 or self.judge_batch_size < 1:
            raise ValueError("max_workers and judge_batch_size must be positive")


@dataclass
class EmpiricalRun:
    """Auditable output of one orchestration run."""

    blind_map: dict[str, str]
    transcripts: dict[str, str]
    judgments: dict[str, Mapping[str, Any]]
    deterministic: dict[str, Mapping[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blind_map": self.blind_map,
            "transcripts": self.transcripts,
            "judgments": self.judgments,
            "deterministic": self.deterministic,
            "metadata": self.metadata,
        }


def _chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    if size <= 0:
        raise ValueError("batch size must be positive")
    for start in range(0, len(items), size):
        yield items[start:start + size]


def run_empirical(
    *,
    versions: Mapping[str, str],
    scenarios: Iterable[Any],
    subject_backend: SubjectBackend,
    judge_backend: JudgeBackend,
    rubric_for: Callable[[Any], Any],
    deterministic_check: Callable[[EvaluationUnit, str, Any], Mapping[str, Any]] | None = None,
    config: EmpiricalRunConfig | None = None,
) -> EmpiricalRun:
    """Execute one complete empirical run.

    ``versions`` maps labels to frozen skill text.  Subject calls are batched
    by version (or by ``subject_batch_size``); judge calls are batched only at
    the backend boundary.  The backend is responsible for making each judge
    item context-isolated when ``batch_isolated`` is true.
    """
    cfg = config or EmpiricalRunConfig()
    scenario_list = list(scenarios)
    if not versions or not scenario_list:
        raise ValueError("versions and scenarios must not be empty")
    if any(not isinstance(text, str) or not text.strip() for text in versions.values()):
        raise ValueError("every version must contain non-empty skill text")
    scenario_ids = [str(s.id) for s in scenario_list]
    if any(not scenario_id for scenario_id in scenario_ids):
        raise ValueError("scenario ids must not be empty")
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("scenario ids must be unique")
    units = [EvaluationUnit(version, str(s.id), rollout)
             for version in versions
             for s in scenario_list
             for rollout in range(1, cfg.rollouts + 1)]
    blind_map = generate_blind_ids([u.key for u in units], seed=cfg.seed)

    # Subjects are intentionally grouped by version: this removes spawn
    # overhead while keeping version treatments separate.
    requests = [SubjectRequest(u, versions[u.version], next(s for s in scenario_list if str(s.id) == u.scenario_id))
                for u in units]
    subject_batches: list[list[SubjectRequest]] = []
    if cfg.subject_batch_size > 0:
        subject_batches = [chunk for version in versions
                           for chunk in _chunks(
                               [r for r in requests if r.unit.version == version],
                               cfg.subject_batch_size,
                           )]
    else:
        subject_batches = [[r for r in requests if r.unit.version == version]
                           for version in versions]

    transcripts: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, cfg.max_workers)) as pool:
        futures = [pool.submit(subject_backend.run_batch, batch) for batch in subject_batches]
        for future in as_completed(futures):
            result = dict(future.result())
            transcripts.update(result)
    missing = [u.key for u in units if u.key not in transcripts]
    if missing:
        raise ValueError(f"subject backend omitted units: {missing}")
    expected_unit_keys = {u.key for u in units}
    extras = sorted(set(transcripts) - expected_unit_keys)
    if extras:
        raise ValueError(f"subject backend returned unknown units: {extras}")

    deterministic: dict[str, Mapping[str, Any]] = {}
    if deterministic_check is not None:
        for request in requests:
            deterministic[request.unit.key] = dict(
                deterministic_check(request.unit, transcripts[request.unit.key], request.scenario)
            )

    judge_requests = [JudgeRequest(blind_map[u.key], next(s for s in scenario_list if str(s.id) == u.scenario_id),
                                   transcripts[u.key], rubric_for(next(s for s in scenario_list if str(s.id) == u.scenario_id)))
                      for u in units]
    judgments: dict[str, Mapping[str, Any]] = {}
    for batch in _chunks(judge_requests, cfg.judge_batch_size):
        for result in judge_backend.judge_batch(batch):
            if result.opaque_id in judgments:
                raise ValueError(f"judge backend returned duplicate id: {result.opaque_id}")
            judgments[result.opaque_id] = dict(result.score)
    missing_judgments = [r.opaque_id for r in judge_requests if r.opaque_id not in judgments]
    if missing_judgments:
        raise ValueError(f"judge backend omitted opaque ids: {missing_judgments}")
    expected_opaque_ids = {request.opaque_id for request in judge_requests}
    extra_judgments = sorted(set(judgments) - expected_opaque_ids)
    if extra_judgments:
        raise ValueError(f"judge backend returned unknown opaque ids: {extra_judgments}")

    return EmpiricalRun(
        blind_map=blind_map,
        transcripts=transcripts,
        judgments=judgments,
        deterministic=deterministic,
        metadata={
            "subject_batch_isolated": bool(subject_backend.batch_isolated),
            "judge_batch_isolated": bool(judge_backend.batch_isolated),
            "subject_batches": len(subject_batches),
            "judge_batches": (len(judge_requests) + cfg.judge_batch_size - 1) // cfg.judge_batch_size,
            "methodological_warning": (
                "judge batches share context; scores are not independent"
                if not judge_backend.batch_isolated else None
            ),
        },
    )
