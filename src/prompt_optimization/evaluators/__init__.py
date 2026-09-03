"""The real-evaluator seam: synthetic optimizer proposes, an ``Evaluator`` disposes.

``prompt_optimization.metrics.basin`` is a deterministic research scaffold: it
never calls a real model. This subpackage is the plug point the paper's
future-work section (Section 9, item 1) describes: a minimal ``Evaluator``
protocol plus concrete backends, wired into the CLI via ``--backend``. The
synthetic backend preserves today's behavior and stays the default; the
``rubric`` and ``callable`` backends are real in the sense that matters here
--- their numbers come from outside the synthetic attractor simulation, not
from ``prompt_optimization.metrics.basin`` --- and a ``plan`` run only reports
``supported_improvement`` when a non-synthetic backend produced it.
"""

from .base import EvaluationResult, Evaluator
from .synthetic import SyntheticBasinEvaluator
from .rubric import RubricEvaluator
from .callable_backend import CallableEvaluator
from .registry import load_evaluator
from .activation import (
    ActivationLabel,
    activation_confusion,
    activation_cost,
    activation_precision_recall,
)
from .calibration import (
    UNSTABLE_FLAG,
    PairwiseJudgment,
    cohens_kappa,
    generate_blind_ids,
    judge_human_agreement,
    position_consistency,
)
from .deterministic import SuccessBand, check_success_band
from .internal_judge import judge_internally
from .profiles import (
    DEFAULT_PROFILES,
    OMEGA_KEYS,
    UNIFORM_PROFILE,
    get_profile,
    project_utility,
)

__all__ = [
    "ActivationLabel",
    "DEFAULT_PROFILES",
    "EvaluationResult",
    "Evaluator",
    "OMEGA_KEYS",
    "PairwiseJudgment",
    "RubricEvaluator",
    "SuccessBand",
    "SyntheticBasinEvaluator",
    "CallableEvaluator",
    "UNIFORM_PROFILE",
    "UNSTABLE_FLAG",
    "activation_confusion",
    "activation_cost",
    "activation_precision_recall",
    "check_success_band",
    "judge_internally",
    "cohens_kappa",
    "generate_blind_ids",
    "get_profile",
    "judge_human_agreement",
    "load_evaluator",
    "position_consistency",
    "project_utility",
]
