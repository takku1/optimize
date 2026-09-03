# BCSO-Bench specification

Last verified: 2026-08-29.

This document is the project's north-star spec: it defines the objects, data
splits, metrics, search procedure, and maturity model this codebase
implements, and says plainly which parts are validated code vs. which parts
are still conceptual future work. It supersedes the informal framing in
`docs/research-landscape.md`'s "Intent-preserving transformation" and
"Additional mathematically grounded improvements" sections (kept there for
literature-survey purposes, formalized here). It absorbs and replaces
`updated logic to be deleted.md`, which is no longer part of the repository.

Companion documents: `docs/benchmark-card.md` (scope, reference
corpus, limitations — the release artifact for people) and
`docs/governance.md` (versioning, retirement, contamination policy).

## 1. What is being optimized

A **Skill Program** is `S = (R, τ, Φ, Γ)`:

- `R` — structural paradigm (procedural, decision tree, declarative
  invariants, pseudocode, counterexamples).
- `τ` — activation/scoping policy: when the skill should engage.
- `Φ` — the serialized instruction text, with token cost `L_tok(S) = |Φ|`.
- `Γ` — the **declared capability contract**: what the skill claims to do,
  so the benchmark isn't inferring goals from the same prose it evaluates.
  Implemented as `capability.CapabilityContract` (scope, required/forbidden
  behaviors, success criteria, capability family), which references — rather
  than duplicates — an existing `contracts.IntentContract` (the behavioral/Φ
  layer: activation, outcome, hard invariants, state, side effects, outputs,
  validation, recovery).

A frozen model `M` induces a policy `π_M(y | x, S)` over output traces `y`
given task input `x`. The object of measurement is this policy, not textual
similarity between two versions of `S` — two skills with very different
wording can be behaviorally equivalent, and near-identical wording can behave
very differently under a real model.

## 2. Data hierarchy

Five non-overlapping distributions, evaluated at different frequencies and
with different access rules:

| Split | Used for | Who sees it |
|---|---|---|
| `D_author` | humans designing rubric criteria, failure taxonomies, activation definitions | never fed to the optimizer directly |
| `D_train` | textual failure-gradient diagnosis | the optimizer's diagnosis step |
| `D_fitness` | high-frequency evolutionary selection pressure | every generation |
| `D_select` / `D_audit` | low-frequency checkpoint Pareto-archive selection; `D_audit` is a hidden adversarial suite the optimizer sees only as aggregate pass/fail | every `checkpoint_every` generations |
| `D_test` | one-shot sealed generalization measurement | exactly once, after freeze |

Convention: tag a `Scenario`/`ScenarioResult`'s split via `metadata["split"]`
(additive — no schema change). `search.loop.run_bcso` enforces the
`D_test`-is-sealed-until-freeze rule structurally: it only ever evaluates the
one selected candidate once, after the state machine reaches `FROZEN`.
`D_author` and `D_audit` are process conventions this repo does not yet
automate — see `docs/governance.md`.

## 3. Objective space

Per-trajectory utility projects a multi-attribute score
`Ω = (task_success, correctness, invariant_adherence, calibration)` to a
scalar via a **capability-family-conditioned** weight vector `w_c` — never one
universal `w`. Implemented as `evaluators.profiles.project_utility`, with
`DEFAULT_PROFILES` keyed by family (`reasoning`, `architecture`,
`formatting`, `creative`, `tool_orchestration`, `retrieval`, `workflow`) and
an unweighted fallback for anything undeclared.

Robustness `R` penalizes both across-task variance and within-task rollout
variance (not implemented as a single closed-form penalty here; approximated
operationally via the fitness `R` fed into the search loop and via
`metrics.hierarchical_bootstrap`'s nested uncertainty estimate, which
respects the scenario→variant→rollout nesting a flat bootstrap ignores).

The search's 3D fitness vector is `(U_fitness, R_fitness, -L_tok)` —
maximize quality and robustness, minimize cost — tracked as a Pareto archive
(`search.archive`) rather than collapsed into one weighted sum.

## 4. Task taxonomy and coverage

"We evaluated 32 behavioral cells spanning activation × evidence ×
difficulty × novelty" is a stronger claim than "we tested 500 prompts."
`capability.contract.DEFAULT_AXES` defines nine axes (activation, difficulty,
evidence, novelty, user_intent, context, tool_requirements, failure_mode,
constraint_pressure); scenarios declare their cell via `"axis:value"` tags.
`capability.coverage_report` reports per-axis counts and, importantly, which
cells are *uncovered* — coverage is a shape claim, not a count.

## 5. Metamorphic testing

Testing prompts independently misses a class of robustness failures.
`metrics.metamorphic` names controlled transformations of the same task and
classifies each as **preserving** (paraphrase, irrelevant-context injection,
reordering, format/politeness/verbosity change, noise — utility should stay
roughly constant: `U(S,x) ≈ U(S,f(x))`) or **activation-changing** (explicit
→ implicit request, conflicting demand, distractor evidence — behavior
*should* change: `A(S,x) ≠ A(S,g(x))`). `metamorphic_report` scores each
group accordingly rather than forcing every transformation through the same
"did the score stay the same" check.

## 6. Activation quality, separated from utility

Whether a skill *should have* engaged is a different question from *how well*
it performed once engaged, with different asymmetric costs per capability
family (a security-response skill's false negative is usually worse than its
false positive; an architecture-review skill's false positive wastes an
expensive pass). `evaluators.activation` reports precision, recall, and F1
from an explicit confusion matrix, plus a configurable
`cost = c_FP·FP + c_FN·FN` — never a single universal `activation ≥ 0.90`
threshold.

## 7. Evaluator stack and calibration

`evaluators.EvaluationResult.tier` tags a judgment as `"deterministic"`
(schema/invariant checks — should dominate whenever available),
`"model"` (an LLM judge), or `"human"` (arbitration). No default backend in
this repo claims `"human"` except `RubricEvaluator` (real judgments a person
recorded), and `CallableEvaluator` defaults to `"model"` since it typically
wraps a model API — both are overridable per entry/return value.

An LLM judge is not an oracle: `evaluators.calibration` implements pairwise
position-consistency checking (swap presentation order, see if the *named
winner* — not just the score — flips; flags `EVALUATOR_UNSTABLE` below a
threshold) and judge/human agreement (`Pearson r`, bootstrapped MAE,
Cohen's κ for categorical labels like invariant pass/fail). None of this is
wired to a real judge yet — that requires an actual `rubric`/`callable`
backend run, which is real evidence only when a human or model outside this
codebase produced the numbers.

## 8. Uncertainty and sample-size planning

Every reported mean should carry a confidence interval, computed with
SciPy's validated primitives rather than a hand-rolled approximation
(`metrics.uncertainty` uses `scipy.stats.bootstrap`, `scipy.stats.wasserstein_distance`,
and `scipy.special.ndtri` — see that module's docstring for why: there is no
elementary closed-form formula for e.g. the normal quantile function, so a
hand-written approximation is one more thing this project would have to
validate itself instead of inheriting from a mature, widely-tested library).
`power_sample_size` turns "500 tasks seems large enough" into a stated,
falsifiable minimum-detectable-effect claim from a normal-approximation
formula — a planning default, not a substitute for a real pilot's `sigma`.
`tail_metrics` (p10, CVaR) reports worst-case behavior separately from the
mean, since a skill averaging .94 but catastrophically failing 8% of the time
is not the same as one consistently at .91.

## 9. Rate-distortion frontier

`metrics.rate_distortion_frontier` is the empirical lower envelope of
distortion at each token budget; `utility_at_budget`/`distortion_at_budget`
read `U*(B)`/`D*(B)` off that frontier. This is the primary efficiency
measure — not a single `E = U/L` ratio, which conflates two different
questions ("how good" and "how cheap") into one number that hides the
tradeoff curve.

## 10. The search loop: branching Pareto evolution, not a single chain

`search.loop.run_bcso` implements:

```
P_t → evaluate → diagnose → mutate → C_t
    → ParetoFilter(P_t ∪ C_t) → P_{t+1}     [repeat until ΔHV < ε_HV for M checks]
    → freeze → S*_δ = argmin L_tok(S) s.t. U_select(S) ≥ (1-δ_U) U_max,select
    → unseal D_test once → G_final
```

Two independent gates, not one fuzzy "looks good enough" — see
`search.state.SearchState`:

- **Qualification**: does the best archive member clear the utility/
  robustness floors?
- **Saturation**: has hypervolume growth (`metrics.hypervolume`, a Monte
  Carlo estimate — no closed-form primitive exists for multi-objective
  hypervolume) stayed below `ε_HV` for `M` consecutive checkpoints
  (`metrics.delta_hv_converged`)?

State machine: `BASELINE → SEARCHING → QUALIFIED → SATURATION_CHECK`, which
loops back to `SEARCHING` while not saturated and only advances to `FROZEN`
once both gates clear, then `FROZEN → TESTED` (the one-shot `D_test` run)
`→ RELEASED`.

**Lineage, not overwrite.** Every `search.population.Candidate` that ever
enters the archive is kept — `parent_ids` and `mutation_type` trace back to
the seed. `search.runs` writes this as a filesystem layout:

```
runs/<run_id>/
  gen_000/seed.md
  gen_001/candidate_01.md ... scores.json
  archive/pareto_001.md, pareto_002.md, ...
  final/SKILL.md, benchmark.json, provenance.json
```

**What this is not.** The default mutation operators
(`search.mutate.structural_swap/compress/rule_consolidation`) are rule-based
text transforms, not a model-driven rewrite, and the default "diagnosis" step
(`search.loop._default_diagnose`) is a cheap heuristic (favor whichever
operator most recently produced the best-scoring archive member), not an
LLM-driven failure-mode analysis. Both are pluggable (`diagnose_fn`, or wire
a real `Evaluator`) but ship this way by default for the same reason
`SyntheticBasinEvaluator` does: something runnable end-to-end, honestly
labeled, with zero API calls made on the project's own initiative. A
`search` CLI run is a demonstration of the control flow, not evidence that
any candidate is a better skill.

## 11. Named baselines and optimizer ablations

`search.baselines.BASELINES` gives comparison points required before any
"BCSO helped" claim is credible: `no_skill`, `original`, `simple_rewrite`
(one undirected mutation, no selection), `compression_only`, `random_mutation`,
`evolution_no_gradient` (mutation + Pareto selection, no directed diagnosis),
`textual_gradient` (directed diagnosis, capped generations), and `full_bcso`.
An optimizer ablation is just another `BaselineConfig` with one component
toggled off, diffed against `full_bcso`'s `ΔU`/`ΔL`/`ΔR` — same `runs/`
lineage layout, independently inspectable.

## 12. Ablation and counterfactual insertion

**Ablation** (does a component earn its tokens?): `contracts.ablation_deltas`
is the single-removal special case of Shapley attribution
(`attribution.shapley_values` estimates the full averaged-over-all-coalitions
version) — no new attribution math, just the one-at-a-time arithmetic. A
near-zero delta suggests, but does not prove, a component is safe to cut
(components interact).

**Counterfactual insertion** (the inverse: can defects be detected at all?):
`contracts.DefectType` names seven defect classes (redundant, contradictory,
irrelevant, verbose, misleading, unnecessary step, malformed trigger);
`search.mutate.inject_defect` produces a labeled defective variant;
`contracts.counterfactual_detection_rate` scores whether review caught it.
This validates the *reviewer or optimizer*, not the skill under test.

## 13. Reference envelopes and maturity tiers

**Reference envelope** (where does a candidate sit among mature skills of its
capability family?): `capability.reference` explicitly does not assume
`z ~ N(μ, Σ)`. `goodness_of_fit` runs `scipy.stats.shapiro` (a validated
normality test, not a hand-rolled check) per dimension;
`select_envelope_estimator` only offers the Mahalanobis/Gaussian membership
score when that test doesn't reject normality and there are enough reference
points, otherwise falling back to the always-safe
`family_conditioned_percentile` or `knn_distance` — the estimator is chosen
by the data, never assumed.

**Maturity tiers** (`capability.maturity.classify_maturity`): cumulative
gates — `EXPERIMENTAL → QUALIFIED → MATURE → SATURATED → PORTABLE →
REFERENCE` — replacing a single PASS/FAIL. Each tier requires the previous
one plus one more preregistered floor: utility/activation, then robustness/
generalization/reference-envelope membership, then optimization resistance
(`Δ_opt ≤ ε_opt`), then cross-model transfer, then independent reproduction.
This never claims "the mathematically perfect prompt" — only which
preregistered floor of evidence a candidate currently clears.

## 14. Provenance and versioning

`capability.provenance.ProvenanceRecord` pins the inference environment
(model id/version, temperature, top_p, tool config, system-prompt hash,
context limit, tokenizer, optimizer/judge model, benchmark version) so two
reported numbers are only compared when they're actually comparable.
`BenchmarkVersion` independently versions task suite, rubric, judge profile,
reference corpus, and optimizer protocol; `content_hash` gives a SHA-256
over a canonical JSON serialization for auditable bundle identity. See
`docs/governance.md` for the versioning and retirement policy this
supports.

## 15. What remains explicitly future work

Not faked, not simulated, not claimed: the actual judge-calibration study
against real human labels; the actual power analysis from real pilot data;
real cross-model transfer results; real contamination auditing of a public
task suite; treating any `search` CLI run as empirical evidence of anything.
Each requires either real model access this project deliberately does not
take on its own initiative, or a real reference corpus at a scale this repo
does not yet have (`docs/benchmark-card.md` lists the four reviewed
specimens that exist today). Wiring a real evaluator through the existing
`rubric`/`callable` seam is the bridge from "measurement layer" to
"evidence" — see `docs/STATUS.md` for the current active focus.
