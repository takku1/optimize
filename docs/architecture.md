# Architecture

## Decision

Reframe the project as a **contract-conditioned empirical optimizer**.

The application, not an LLM, owns the truth of a run: contract extraction,
candidate generation, executable invariants, cost accounting, uncertainty,
candidate acceptance, lineage, and promotion. The core optimizer is model-free:
it does not invoke Claude, Codex, or a model judge. A target-model executor may
be supplied at the outer testing boundary to observe behavior, but it is the
system under test, never the judge or source of truth.

The primary implemented optimization workflow is:

```text
prompt-opt optimize --config run.json
```

Today that command iterates candidate proposals against either a scoring
callback or a scenario executor, stops on convergence/patience, and can write
the selected proposal plus run data. Resumable execution, complete empirical
evidence assembly, and automatic promotion are target architecture described
below, not current CLI behavior.

## What is being optimized

The object is not merely shorter text. A candidate skill `S` is selected by a
constrained rate-distortion objective:

```text
minimize     token_cost(S) + λ_latency latency(S)

subject to   invariant_pass_rate(S, scenario) >= declared floor
             lower_CI(utility(S) - utility(baseline)) >= -δ
             intent_fingerprint_coverage(S) >= γ
             critical_regressions(S) = 0
```

The archive retains candidates that trade utility, robustness, and cost in
different ways. A scalar score is only used for deterministic tie-breaking
after hard gates and Pareto filtering.

### High-leverage semantic representations

The target is a **behaviorally optimal representation**, not the literal center
of a latent space. A vague phrase leaves a broad distribution over possible
interpretations; a useful phrase narrows that distribution with the fewest
conflicting or redundant constraints. Because the optimizer cannot inspect
latent activations, it measures this indirectly through executable behavior.

The search spans:

```text
lexical choice × phrase choice × context × position × structure
```

Specificity is an experimental axis, not a monotonic rule. The implementation
therefore tests explicit lexical alternatives and operational definitions,
rather than assuming that a more technical word is always stronger.

The measurable objective is:

```text
maximize  behavioral_utility
        + α · (neighborhood_mean − neighborhood_stddev)
        + β · (behavioral_utility / token_cost)
        − λ · token_cost
subject to every hard invariant passing
```

The ratio is a proxy for useful information density; it is never allowed to
override hard invariants. A candidate is strong when it constrains behavior
without creating adjective soup, redundancy, or brittle wording.

For candidate `S`, `N(S)` is a declared set of controlled variants. A surface
variant is not silently treated as a semantic paraphrase: equivalence still
requires held-out contract outcomes.

### Tensor-to-intent boundary

When a compatible target-model adapter is available, the run may capture:

```text
H(S) ∈ R^(layers × tokens × hidden_size)
z_l(S) = normalize(mean_pool(H_l(S)))
representation_drift = 1 − cosine(z_l(parent), z_l(candidate))
```

These values describe how the target model represents the text. They do not
decode a unique intent, prove semantic equivalence, or replace executable
validation. Intent is inferred through contract-labelled probes or RSA-style
comparisons only as a diagnostic. Causal interventions such as activation
patching are a later research stage and require strict controls.

## Intent preservation

Intent is represented as an executable `IntentFingerprint`, not as an assumed
neural embedding:

- activation conditions and task scope;
- required outcomes and output shapes;
- hard invariants and forbidden behaviors;
- ownership, state, failure, and recovery requirements;
- reference/degradation rules;
- scenario coverage and expected transformation behavior.

The fingerprint is measured in three layers:

1. **Mechanical:** schemas, phrase/concept rules, file/symbol evidence,
   boundedness, output routing, and declared state transitions.
2. **Behavioral:** repeated held-out scenario rollouts and invariant outcomes.
3. **Representation diagnostic:** optional embedding similarity or, when the
   same open model is available, hidden-state/RSA comparisons.

Layer 3 is never a substitute for layer 2. Similar hidden representations can
be informative without proving equivalent behavior.

## Components

### `contracts`

Versioned capability contracts, intent fingerprints, scenarios, hard invariants,
success bands, and split membership. No model calls.

### `validators`

The authoritative model-free evaluator. Composes executable predicates into
`passed`, `failed`, or `unresolved` results and emits evidence for every result.
An absent predicate is unresolved; it is never vacuous success.

### `representations`

An optional, model-agnostic adapter returns token-by-hidden-size tensors. The
package owns pooling, cosine drift, provenance, and comparison math; it does
not load Claude, Codex, or any vendor model. A representation adapter is part
of the system-under-test boundary, and its output can influence selection only
through a declared soft objective term. Hard contract invariants always win.

### `execution boundary`

When behavioral testing is requested, runs the target system against the scenario
matrix with K rollouts, isolated treatment contexts, deterministic seeds where
supported, timeouts, retries, and resumable unit IDs. This is an explicit
system-under-test boundary; there is no vendor-specific provider in the core.
Every transcript is stored as its own immutable unit.

### `search`

Maintains the candidate population, lineage, Pareto archive, and convergence
state. Proposal operators include local edit, section rewrite, compression,
reorganization, complete rewrite, and recovery from a failed candidate.
Deterministic rewrite operators receive only the current candidate and
program-produced feedback. They can perform local edits, section rewrites,
compression, reorganization, or complete canonical rewrites without an LLM.
The generalized taxonomy records lexical, syntactic, semantic-operationalization,
structural, compression, reconstruction, and identity transitions. A complete
rewrite may look unrelated to its parent when its behavioral contract remains
satisfied.

### `evaluation`

Combines mechanical results, behavioral utility, token/latency cost, bootstrap
uncertainty, neighborhood mean/worst-case/variance, and optional calibrated
semantic review. The semantic reviewer is
advisory unless the contract explicitly declares that no executable validator
exists and promotion requires human or calibrated external arbitration.

### `promotion`

Applies absolute floors, baseline non-inferiority, confidence bounds, split
rules, and regression classification. It cannot validate a synthetic-only run.

### `provenance`

Records hashes for skill text, contracts, scenarios, validators, generator,
target-system configuration when present, tokenizer, seeds, sampling settings,
and every candidate transition.

## One-run lifecycle

```text
freeze inputs
  -> fingerprint + blind units
  -> generate candidate population
  -> execute K subject rollouts
  -> mechanical validation
  -> optional semantic arbitration for unresolved cells
  -> aggregate utility/cost/uncertainty
  -> Pareto archive + regression gates
  -> generate next candidates
  -> stop on patience, budget, or confidence convergence
  -> write final proposal, report, lineage, and provenance
```

The run is resumable after any unit. Existing immutable results are reused by
content-addressed unit ID; retries never duplicate accepted evidence.

## Search policy

Use a diverse bounded population rather than one rewrite chain. Each generation
should include both conservative edits and at least one complete-rewrite slot
when the generator supports it. Candidate acceptance is based on the program's
evaluation bundle, not the generator's explanation.

Default stop conditions are:

- no archive improvement for `patience` generations;
- hard budget reached;
- confidence interval narrow enough for the declared decision; or
- all viable candidates fail a preregistered hard invariant.

### Hierarchical search and reconciliation

The search space is hierarchical rather than a flat synonym loop:

```text
token → phrase → sentence → paragraph → section → skill
```

Each mutation is reconciled at its own level before evaluation. The reconciler
may reshape surrounding context, allowing a high-leverage lexical change to
remove redundancy or reorganize a section. Search is beam-limited so the
branching population remains bounded. The adaptive blast radius expands only
when measured candidate impact crosses its configured threshold; otherwise the
search remains local or terminates.

This combines evolutionary diversity with tree/local search. Run records store
level, branch, impact, acceptance, and score. Future GraphStore history may
provide operator priors analogous to pheromone weights, but learned priors are
not evidence until independently split transition data exists.

The canonical research design for this direction is
[`trajectory-optimization.md`](trajectory-optimization.md). It calls the
synthesis *hierarchical semantic trajectory optimization* while separating
implemented mechanics, diagnostic representation evidence, and unvalidated
future search policies.

## What remains out of scope

A trained neural optimizer, latent-space generator, or learned candidate ranker
is deferred until the graph contains enough real transitions and an independent
train/calibration/test split. A small neural network trained now would mostly
learn lexical shortcuts from too little data; it would not supply a reliable
rewrite or semantic judge. Until then, deterministic operators, executable
contracts, and Pareto selection are the internal engine. Embeddings and hidden
states remain optional diagnostics, never a source of truth.

## Research grounding

The iterative generator/evaluator separation follows OPRO and PromptBreeder;
the compression objective follows rate-distortion work on query-aware prompt
compression. LLM judges remain optional because position bias and other
evaluation artifacts require calibration and should not silently become the
benchmark's truth.

- https://arxiv.org/abs/2309.03409
- https://arxiv.org/abs/2309.16797
- https://arxiv.org/abs/2407.15504
- https://arxiv.org/abs/2406.07791
- https://arxiv.org/abs/2508.05995
