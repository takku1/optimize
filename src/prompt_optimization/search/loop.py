"""``run_bcso()``: the branching Pareto-evolution search loop.

::

    P_t -> evaluate -> diagnose -> mutate -> C_t
        -> ParetoFilter(P_t ∪ C_t) -> P_{t+1}     [repeat until ΔHV < ε_HV for M checks]
        -> freeze -> S*_δ = argmin L_tok(S) s.t. U_select(S) >= (1-δ_U) U_max,select
        -> unseal D_test once -> G_final

This is a synthetic, non-empirical demonstration harness — same honesty
convention as ``SyntheticBasinEvaluator``: it exercises the full BCSO control
flow end to end, including the ``runs/`` lineage layout, but its default
mutation operators are rule-based text transforms, not a real model rewrite.
It is not evidence that any candidate is actually better; wire in a real
``Evaluator`` (``rubric``/``callable``) for that.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..evaluators import Evaluator
from ..graph import EvaluationRecord, GraphStore, MutationEdge, SkillNode
from ..graph.retrieval import mutation_family_stats
from .archive import archive_hypervolume, is_saturated, select_delta_optimal, update_archive
from .baselines import BaselineConfig, get_baseline
from .mutate import _OPERATORS, random_mutation
from .population import Candidate, seed_population
from .runs import write_archive_snapshot, write_final, write_generation
from .state import SearchState, next_state

DiagnoseFn = Callable[[Candidate, list[dict], tuple[str, ...], int], Candidate]


def _default_diagnose(parent: Candidate, archive_history: list[dict], allowed: tuple[str, ...], seed: int) -> Candidate:
    """Heuristic stand-in for a real textual-gradient diagnosis.

    Picks whichever allowed operator most recently produced the
    best-``U``-scoring archive member, defaulting to the first allowed
    operator with no history yet. A cheap proxy, not an LLM-driven
    failure-mode analysis — pass a real one via ``diagnose_fn``.
    """
    if archive_history:
        best = max(archive_history, key=lambda row: row.get("U", 0.0))
        op_name = best.get("mutation_type")
        if op_name in allowed and op_name in _OPERATORS:
            return _OPERATORS[op_name](parent, seed=seed)
    return _OPERATORS[allowed[0]](parent, seed=seed)


def make_graph_diagnose(store: GraphStore, *, capability_contract_hash: str = "",
                         fallback: DiagnoseFn = _default_diagnose) -> DiagnoseFn:
    """Retrieval-conditioned diagnosis: prefer the operator with the best track record in ``store``.

    This is the FunSearch/AlphaEvolve-shaped step recommended in
    ``docs/evolution-graph-research.md`` — retrieval
    over a real lineage store informing the next proposal, not a trained
    predictor/ranker/generator checkpoint (no comparable published system
    trains one of those, and this project doesn't have remotely enough
    recorded transitions to justify attempting it yet). Falls back to
    ``fallback`` when the store has no relevant history for any allowed
    operator, so an empty graph behaves exactly like the default loop.
    """

    def _graph_diagnose(parent: Candidate, archive_history: list[dict], allowed: tuple[str, ...], seed: int) -> Candidate:
        stats = mutation_family_stats(
            store, capability_contract_hash=capability_contract_hash or None,
        )
        eligible = {family: s for family, s in stats.items() if family in allowed and family in _OPERATORS}
        if not eligible:
            return fallback(parent, archive_history, allowed, seed)
        best_family = max(eligible, key=lambda family: eligible[family]["mean_utility_delta"])
        return _OPERATORS[best_family](parent, seed=seed)

    return _graph_diagnose


def _advance(state: SearchState, *, qualified: bool, saturated: bool) -> SearchState:
    """Cascade ``next_state`` within one checkpoint until it stabilizes or reaches FROZEN."""
    visited: set[SearchState] = set()
    while state not in visited:
        visited.add(state)
        new_state = next_state(state, qualified=qualified, saturated=saturated)
        if new_state == state:
            return state
        state = new_state
        if state == SearchState.FROZEN:
            return state
    return state


def _capped(archive: list[dict], max_size: int | None) -> list[dict]:
    """Truncate the archive to its best-``U`` members, keeping search cost bounded."""
    if max_size is None or len(archive) <= max_size:
        return archive
    return sorted(archive, key=lambda row: row["U"], reverse=True)[:max_size]


def _score(evaluator: Evaluator, candidate: Candidate, *, seed: int) -> dict:
    result = evaluator.evaluate(f"gen{candidate.generation}:{candidate.id}", candidate.text, seed=seed)
    return {
        "id": candidate.id, "U": result.score, "R": result.reliability, "tokens": result.tokens,
        "mutation_type": candidate.mutation_type,
    }


def run_bcso(
    seed_text: str,
    evaluator: Evaluator,
    *,
    baseline: str = "full_bcso",
    utility_min: float = 0.5,
    robustness_min: float = 0.5,
    delta_u: float = 0.02,
    epsilon_hv: float = 0.01,
    saturation_checks: int = 3,
    checkpoint_every: int = 2,
    max_archive_size: int | None = 40,
    run_dir: str | Path | None = None,
    seed: int = 0,
    diagnose_fn: DiagnoseFn | None = None,
    graph_store: GraphStore | None = None,
    capability_contract_hash: str = "",
) -> dict[str, Any]:
    """Run the branching evolutionary search; return a report, the selected candidate, and the archive.

    ``evaluator`` follows the same ``Evaluator`` seam the rest of the CLI
    uses; the default ``synthetic`` backend keeps this a proposer, never a
    disposer, matching ``plan``'s honesty rule. Qualification here checks
    only fitness ``U``/``R`` floors — layering real activation
    precision/recall (:mod:`prompt_optimization.evaluators.activation`) on
    top requires labeled scenario data this generic loop does not assume.

    A non-dominated archive can grow unboundedly when nothing in it
    dominates anything else (every generation doubles the archive under
    ``random_mutation``-style baselines in the worst case), and every
    archive member gets re-evaluated each checkpoint — expensive against a
    real evaluator or a large skill file. ``max_archive_size`` truncates the
    archive to its best-``U`` members after each Pareto filter; set it to
    ``None`` only for small demo texts.

    When ``graph_store`` is given, every candidate this run touches is
    persisted as a :class:`~prompt_optimization.graph.SkillNode`, every
    mutation as a :class:`~prompt_optimization.graph.MutationEdge` with its
    observed ``actual_effect``, and every score as an
    :class:`~prompt_optimization.graph.EvaluationRecord` — this run's
    lineage survives past this one Python process, so a later
    ``make_graph_diagnose`` (this run's or a future one's) can retrieve it.
    """
    if not seed_text.strip():
        raise ValueError("seed_text must not be empty")
    if not 0 <= utility_min <= 1 or not 0 <= robustness_min <= 1:
        raise ValueError("utility_min and robustness_min must be in [0, 1]")
    if not 0 <= delta_u < 1:
        raise ValueError("delta_u must be in [0, 1)")
    if epsilon_hv < 0:
        raise ValueError("epsilon_hv must be non-negative")
    if saturation_checks < 1 or checkpoint_every < 1:
        raise ValueError("saturation_checks and checkpoint_every must be positive")
    if max_archive_size is not None and max_archive_size < 1:
        raise ValueError("max_archive_size must be positive or None")
    config: BaselineConfig = get_baseline(baseline)
    run_path = Path(run_dir) if run_dir is not None else None

    def record(candidate: Candidate, row: dict, *, parent: Candidate | None = None) -> None:
        if graph_store is None:
            return
        now = datetime.now(timezone.utc).isoformat()
        parent_node_hash = candidate_hashes.get(parent.id) if parent is not None else None
        node = SkillNode(
            skill_text=candidate.text, token_count=row["tokens"],
            parent_hashes=(parent_node_hash,) if parent_node_hash is not None else (),
            capability_contract_hash=capability_contract_hash,
            generator=f"search.{candidate.mutation_type}", generation=candidate.generation,
            created_at=now,
        )
        graph_store.put_skill(node)
        if parent is not None and parent_node_hash is not None:
            graph_store.put_mutation(MutationEdge(
                parent_hash=parent_node_hash, child_hash=node.skill_hash,
                mutation_family=candidate.mutation_type,
                actual_effect={
                    "utility_delta": row["U"] - parent_scores[parent.id]["U"],
                    "tokens_delta": row["tokens"] - parent_scores[parent.id]["tokens"],
                },
                created_at=now,
            ))
        graph_store.put_evaluation(EvaluationRecord(
            skill_hash=node.skill_hash, scenario_id=f"search:{baseline}",
            metric_results={"U": row["U"], "R": row["R"], "tokens": row["tokens"]},
            capability_contract_hash=capability_contract_hash,
            evaluator_name=getattr(evaluator, "name", "unknown"),
            trainability="DEVELOPMENT_ONLY" if evaluator.synthetic else "TRAINABLE",
            created_at=now,
        ))
        candidate_hashes[candidate.id] = node.skill_hash
        parent_scores[candidate.id] = row

    candidate_hashes: dict[str, str] = {}
    parent_scores: dict[str, dict] = {}

    candidates = seed_population(seed_text, n=1)
    by_id: dict[str, Candidate] = {c.id: c for c in candidates}
    rows = [_score(evaluator, c, seed=seed) for c in candidates]
    for candidate, row in zip(candidates, rows):
        record(candidate, row)
    if run_path is not None:
        write_generation(run_path, 0, candidates, {r["id"]: r for r in rows})
    archive = _capped(update_archive([], rows) if config.use_pareto_filter else rows, max_archive_size)

    state = next_state(SearchState.BASELINE, qualified=False, saturated=False)  # -> SEARCHING
    hv_history: list[float] = []
    checkpoint = 0
    generation = 0

    def checkpoint_and_advance() -> None:
        nonlocal state, checkpoint
        checkpoint += 1
        hv_history.append(archive_hypervolume(archive, seed=seed))
        if run_path is not None:
            write_archive_snapshot(run_path, checkpoint, [by_id[row["id"]] for row in archive])
        best = max(archive, key=lambda row: row["U"])
        qualified = best["U"] >= utility_min and best["R"] >= robustness_min
        saturated = is_saturated(hv_history, epsilon=epsilon_hv, checks=saturation_checks)
        state = _advance(state, qualified=qualified, saturated=saturated)

    checkpoint_and_advance()

    while state != SearchState.FROZEN and generation < config.max_generations:
        generation += 1
        parents = [by_id[row["id"]] for row in archive]
        children: list[Candidate] = []
        child_parent: dict[str, Candidate] = {}
        for parent in parents:
            if not config.use_mutation:
                continue
            gen_seed = seed + generation
            if config.directed_mutation:
                child = (diagnose_fn or _default_diagnose)(parent, archive, config.allowed_mutations, gen_seed)
            else:
                child = random_mutation(parent, seed=gen_seed, allowed=config.allowed_mutations)
            by_id[child.id] = child
            children.append(child)
            child_parent[child.id] = parent
        if not children:
            break
        child_rows = [_score(evaluator, child, seed=seed) for child in children]
        for child, row in zip(children, child_rows):
            record(child, row, parent=child_parent[child.id])
        if run_path is not None:
            write_generation(run_path, generation, children, {row["id"]: row for row in child_rows})
        archive = _capped(
            update_archive(archive, child_rows) if config.use_pareto_filter else child_rows, max_archive_size,
        )

        if generation % checkpoint_every == 0:
            checkpoint_and_advance()

    if state != SearchState.FROZEN:
        # Search budget exhausted before the saturation gate fired; freeze on
        # the current archive anyway so the run always terminates.
        checkpoint_and_advance()
        state = SearchState.FROZEN

    selected_row = select_delta_optimal(archive, delta_u=delta_u)
    selected = by_id[selected_row["id"]]

    state = next_state(state, qualified=True, saturated=True, tested=True)  # FROZEN -> TESTED
    test_result = evaluator.evaluate(f"final:{selected.id}", selected.text, seed=seed)
    state = next_state(state, qualified=True, saturated=True)  # TESTED -> RELEASED

    report = {
        "baseline": baseline,
        "state": state.value,
        "generations": generation,
        "checkpoints": checkpoint,
        "hv_history": hv_history,
        "selected_id": selected.id,
        "selected_lineage": list(selected.parent_ids),
        "selected_tokens": selected_row["tokens"],
        "selected_utility": selected_row["U"],
        "g_final": test_result.score,
        "archive_size": len(archive),
        "synthetic": evaluator.synthetic,
    }
    if run_path is not None:
        write_final(run_path, selected, report, {"model_id": getattr(evaluator, "name", "unknown")})
    return {"report": report, "selected": selected, "archive": archive}
