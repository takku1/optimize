"""Run provenance and benchmark versioning: pin the environment, don't assume it.

A reported number is not comparable to another one unless both the inference
environment and the benchmark version that produced it are recorded — the
same discipline MLPerf enforces with explicit rules, scenarios, and
reproducible execution conditions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .._hashing import content_hash  # noqa: F401  (re-exported; see prompt_optimization.capability)


@dataclass(frozen=True)
class ProvenanceRecord:
    """Everything needed to know what actually produced a reported number."""

    model_id: str
    model_version: str = ""
    temperature: float | None = None
    top_p: float | None = None
    tool_config: dict[str, Any] = field(default_factory=dict)
    system_prompt_hash: str = ""
    context_limit: int | None = None
    tokenizer: str = ""
    optimizer_model: str = ""
    judge_model: str = ""
    benchmark_version: str = ""

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "tool_config": self.tool_config,
            "system_prompt_hash": self.system_prompt_hash,
            "context_limit": self.context_limit,
            "tokenizer": self.tokenizer,
            "optimizer_model": self.optimizer_model,
            "judge_model": self.judge_model,
            "benchmark_version": self.benchmark_version,
        }


@dataclass(frozen=True)
class BenchmarkVersion:
    """Independently-versioned benchmark components.

    Results across incompatible major versions of any one component should
    not be compared directly (see ``docs/governance.md``).
    """

    task_suite: str
    rubric: str
    judge_profile: str
    reference_corpus: str
    optimizer_protocol: str

    def to_dict(self) -> dict[str, str]:
        return {
            "task_suite": self.task_suite,
            "rubric": self.rubric,
            "judge_profile": self.judge_profile,
            "reference_corpus": self.reference_corpus,
            "optimizer_protocol": self.optimizer_protocol,
        }


#: This project's current BCSO-Bench component versions. Bump on any change
#: that would make results incomparable to a prior run.
CURRENT_BENCHMARK_VERSION = BenchmarkVersion(
    task_suite="0.1.0",
    rubric="0.1.0",
    judge_profile="0.1.0",
    reference_corpus="0.1.0",
    optimizer_protocol="0.1.0",
)

