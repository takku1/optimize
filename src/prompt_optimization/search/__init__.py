"""Synthetic branching-evolutionary search loop over skill text.

Same honesty convention as :mod:`prompt_optimization.evaluators.synthetic`:
everything here is a proposer, never a disposer. Wire a real ``Evaluator``
(``rubric``/``callable``) into :func:`run_bcso` for anything that should
count as evidence.
"""

from .archive import archive_hypervolume, is_saturated, select_delta_optimal, update_archive
from .baselines import BASELINES, BaselineConfig, get_baseline
from .loop import make_graph_diagnose, run_bcso
from .mutate import ALL_MUTATIONS, compress, inject_defect, random_mutation, rule_consolidation, structural_swap
from .population import Candidate, new_candidate_id, seed_population
from .runs import write_archive_snapshot, write_final, write_generation
from .state import SearchState, next_state
from .iterative import IterativeConfig, IterativeResult, internal_propose, optimize_iteratively
from .transforms import Transformation, describe_transformation
from .semantic import LexicalVariant, lexical_variants, operationalize
from .hierarchical import HierarchicalConfig, HierarchicalResult, MUTATION_LEVELS, search_hierarchically
from .ablation import DEFAULT_ABLATIONS, run_ablation

__all__ = [
    "ALL_MUTATIONS",
    "BASELINES",
    "BaselineConfig",
    "Candidate",
    "SearchState",
    "archive_hypervolume",
    "compress",
    "get_baseline",
    "inject_defect",
    "is_saturated",
    "make_graph_diagnose",
    "new_candidate_id",
    "next_state",
    "random_mutation",
    "rule_consolidation",
    "run_bcso",
    "seed_population",
    "select_delta_optimal",
    "structural_swap",
    "update_archive",
    "write_archive_snapshot",
    "write_final",
    "write_generation",
    "IterativeConfig",
    "IterativeResult",
    "internal_propose",
    "optimize_iteratively",
    "Transformation",
    "describe_transformation",
    "LexicalVariant",
    "lexical_variants",
    "operationalize",
    "HierarchicalConfig",
    "HierarchicalResult",
    "MUTATION_LEVELS",
    "search_hierarchically",
    "DEFAULT_ABLATIONS",
    "run_ablation",
]
