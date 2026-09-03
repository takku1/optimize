"""Single-run multi-turn, model-free proposal optimization."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .population import Candidate, new_candidate_id
from .transforms import describe_transformation
from .semantic import lexical_variants, operationalize


class ProposalGenerator(Protocol):
    def __call__(self, current_text: str, feedback: Mapping[str, Any], turn: int) -> str: ...


Score = Mapping[str, Any]
ScoreFn = Callable[[str], Score]


def internal_propose(current_text: str, feedback: Mapping[str, Any], turn: int) -> str:
    """Apply one deterministic rewrite operator selected by the run policy."""
    mode = str(feedback.get("proposal_mode", "local_edit"))
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", current_text) if p.strip()]
    if mode == "local_edit":
        return current_text.strip() + ("\n" if not current_text.endswith("\n") else "")
    if mode in {"compression", "compress"}:
        seen: set[str] = set()
        kept: list[str] = []
        for paragraph in paragraphs:
            key = re.sub(r"\s+", " ", paragraph).casefold()
            if key not in seen:
                seen.add(key)
                kept.append(paragraph)
        return "\n\n".join(kept)
    if mode in {"section_rewrite", "reorganization"}:
        return "\n\n".join(paragraphs)
    if mode == "lexical":
        variants = lexical_variants(current_text, feedback.get("lexical_replacements", {}))
        return variants[0] if variants else current_text
    if mode in {"semantic_operationalization", "operationalize"}:
        return operationalize(current_text, feedback.get("operationalizations", {}))
    if mode == "complete_rewrite":
        lines = [re.sub(r"[ \t]+", " ", line.rstrip()) for line in current_text.splitlines()]
        return "\n".join(lines).strip() + "\n"
    return current_text


@dataclass(frozen=True)
class IterativeConfig:
    max_turns: int = 8
    patience: int = 2
    utility_key: str = "utility"
    cost_key: str = "tokens"
    output_dir: str | Path | None = None
    proposal_modes: tuple[str, ...] = (
        "local_edit", "lexical", "semantic_operationalization", "section_rewrite",
        "compression", "complete_rewrite",
    )
    robustness_weight: float = 0.0
    density_weight: float = 0.0
    cost_weight: float = 0.001
    lexical_replacements: Mapping[str, str] = field(default_factory=dict)
    operationalizations: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_turns < 1 or self.patience < 1:
            raise ValueError("max_turns and patience must be positive")
        if min(self.robustness_weight, self.density_weight, self.cost_weight) < 0:
            raise ValueError("objective weights must be non-negative")
        if not self.proposal_modes or any(not mode.strip() for mode in self.proposal_modes):
            raise ValueError("proposal_modes must contain at least one non-empty mode")


@dataclass
class IterativeResult:
    selected: Candidate
    selected_score: dict[str, Any]
    turns: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected.text,
            "selected_id": self.selected.id,
            "selected_score": self.selected_score,
            "turns": self.turns,
            "stop_reason": self.stop_reason,
        }


def _better(candidate: Score, incumbent: Score, cfg: IterativeConfig) -> bool:
    """Maximize robust utility, then information density, then lower cost."""
    if candidate.get("hard_invariants_passed") is not True:
        return False
    if incumbent.get("hard_invariants_passed") is False:
        return True
    def objective(score: Score) -> float:
        utility = float(score.get(cfg.utility_key, 0.0))
        robust = float(score.get("neighborhood_robustness", utility))
        density = float(score.get("information_density", 0.0))
        cost = float(score.get(cfg.cost_key, 0.0))
        return (utility + cfg.robustness_weight * robust
                + cfg.density_weight * density - cfg.cost_weight * cost)
    new_value, old_value = objective(candidate), objective(incumbent)
    if new_value != old_value:
        return new_value > old_value
    return float(candidate.get(cfg.cost_key, float("inf"))) < float(incumbent.get(cfg.cost_key, float("inf")))


def optimize_iteratively(
    seed_text: str,
    score: ScoreFn,
    propose: ProposalGenerator,
    *,
    config: IterativeConfig | None = None,
) -> IterativeResult:
    """Generate/evaluate turns until improvement patience is exhausted.

    Every proposal is evaluated by ``score`` before acceptance.  ``feedback``
    is derived from the program's score and is therefore safe to pass to a
    proposal generator.  Files are written by this function when requested.
    """
    if not seed_text.strip():
        raise ValueError("seed_text must not be empty")
    cfg = config or IterativeConfig()
    current = Candidate(new_candidate_id(seed_text, salt="seed", prefix="seed"), seed_text, 0)
    current_score = dict(score(seed_text))
    turns: list[dict[str, Any]] = []
    stagnant = 0
    _write_turn(cfg, 0, current, current_score, accepted=True)

    for turn in range(1, cfg.max_turns + 1):
        mode = cfg.proposal_modes[(turn - 1) % len(cfg.proposal_modes)]
        feedback = {**current_score, "proposal_mode": mode,
                    "lexical_replacements": dict(cfg.lexical_replacements),
                    "operationalizations": dict(cfg.operationalizations)}
        proposed_text = propose(current.text, feedback, turn)
        if not isinstance(proposed_text, str) or not proposed_text.strip():
            raise ValueError(f"proposal generator returned empty text at turn {turn}")
        proposal = Candidate(
            new_candidate_id(proposed_text, salt=f"turn:{turn}", prefix="proposal"),
            proposed_text, turn, (current.id,), "generated", "reauthoring",
        )
        proposal_score = dict(score(proposed_text))
        accepted = _better(proposal_score, current_score, cfg)
        turns.append({"turn": turn, "candidate_id": proposal.id, "mode": mode,
                      "transformation": describe_transformation(current.text, proposed_text, mode).to_dict(),
                      "accepted": accepted, "score": proposal_score, "feedback": feedback})
        _write_turn(cfg, turn, proposal, proposal_score, accepted=accepted)
        if accepted:
            current, current_score = proposal, proposal_score
            stagnant = 0
        else:
            stagnant += 1
        if stagnant >= cfg.patience:
            return IterativeResult(current, current_score, turns, "patience_exhausted")
    return IterativeResult(current, current_score, turns, "max_turns")


def _write_turn(cfg: IterativeConfig, turn: int, candidate: Candidate,
                score: Mapping[str, Any], *, accepted: bool) -> None:
    if cfg.output_dir is None:
        return
    path = Path(cfg.output_dir) / f"turn_{turn:03d}"
    path.mkdir(parents=True, exist_ok=True)
    (path / "proposal.md").write_text(candidate.text, encoding="utf-8")
    (path / "score.json").write_text(json.dumps({"accepted": accepted, **dict(score)}, indent=2), encoding="utf-8")
