# Hierarchical semantic trajectory optimization

This name describes this project's proposed synthesis; it is not an established
term in the literature. The synthesis combines behavior-constrained prompt
optimization, multi-scale edits, bounded tree/evolutionary search, optional
layer-wise representation diagnostics, and auditable transition history.

## Evidence boundary

The optimization target is observable behavior:

```text
B ~ P(B | S, M)
```

For skill `S` and target model/system `M`, choose among candidates that first
pass every hard contract:

```text
maximize    E[U(B)] - α Var[U(B)] - β Cost(S) + γ Robustness(S)
subject to  Pr(contract violation | S) <= ε
```

This is a design objective, not a claim that the current implementation
estimates every term. Raw output entropy is not a quality loss: different
outputs may all be valid. Utility dispersion, lower-tail utility, and
contract-violation probability are the relevant risks. The package implements
hard gates, bootstrap uncertainty, lower-tail summaries, cost, and robustness
primitives, but a defensible probability estimate requires repeated held-out
rollouts.

## Multi-scale mutation and reconciliation

The bounded edit levels are:

```text
token → phrase → sentence → paragraph → section → skill
```

At level `k`:

```text
candidate = reconcile(mutate(parent, k), k)
```

Reconciliation asks whether a local edit makes its surrounding structure
redundant, contradictory, or incomplete. It may expand to the next level only
when measured impact crosses a preregistered threshold:

```text
impact = behavioral_distance(parent, candidate)
       + λ * representation_distance(parent, candidate)

expand when impact > threshold[k]
```

Behavioral distance controls this decision. Representation distance may inform
where to inspect, but cannot certify intent preservation. Atomic Concept Edits
provides direct evidence that interpretable add/remove/replace operations can
support systematic black-box prompt analysis. It does not establish this
project's recursive reconciliation rule, which remains a hypothesis to test.

## Representation trajectory

If a compatible instrumented model exposes hidden states, retain the layer-wise
trajectory instead of immediately collapsing it to one vector:

```text
H(S) = {H[1], H[2], ..., H[L]}
fingerprint(S) = [RSA, CKA, probe scores, selected features, distances]
```

The term *trajectory* means a sequence across network depth and/or controlled
edits. It does not imply temporal recurrence or classical chaotic dynamics.
Use *perturbation amplification* or *trajectory sensitivity* for measured
divergence; do not claim a Lyapunov exponent without establishing the required
dynamical-system assumptions.

This direction is plausible but limited. Melamed et al. found that
GCG-optimized prompts were distinguishable from natural-language prompts using
sparse activations and followed similar representational paths across several
instruction-tuned model families. That evidence concerns a particular class of
discrete optimized prompts; it does not show that every useful natural-language
rewrite has a stable or causally meaningful trajectory. RSA/ReStA can compare
representations, while probing work shows that decoding success can reflect the
probe's capacity rather than a property causally used by the model. Therefore:

```text
latent diagnostic evidence != behavioral truth
```

Any causal claim requires an intervention and a behavioral effect, not just a
separable activation pattern.

## Hybrid search

Use a small population to preserve a few semantic families and bounded local
tree search to explore edits around promising candidates. The beam is a
frontier, not a request to launch one agent per branch; candidate generation
and scoring stay in-process and are capped by an evaluation budget:

```text
population archive
  ├─ candidate A → lexical/phrase branches
  ├─ candidate B → structure/compression branches
  └─ candidate C → reconstruction branches
```

EvoPrompt establishes population-based evolutionary prompt search. PromptAgent
establishes MCTS-style planning over prompt states and edits. Atomic Concept
Edits supplies concept-level mutations with tree exploration. Combining these
ingredients is reasonable, but the hybrid itself must beat simpler baselines in
an ablation; the papers do not validate this exact composition.

A future tree policy may include exploitation, uncertainty, and bounded
novelty:

```text
priority(v) = Q(v)
            + c * sqrt(log(N_parent) / N_v)
            + β * uncertainty(v)
            + η * novelty(v)
```

Novelty should be measured against behavior or an independently validated
representation fingerprint and capped or treated as a separate archive axis.
Otherwise the optimizer can earn reward for meaningless divergence. Novelty
search is established in evolutionary computation, but its use for behavioral
skill optimization is not validated here.

## Evolution graph and learned priors

The target transition record is:

```text
parent and child hashes
mutation level and operator
concept changed and propagation radius
representation delta (optional)
behavioral delta and rollout distribution
contract results, cost, robustness, and provenance
```

The current `GraphStore` records parent/child content, mutation family,
evaluation metrics, contract family, evaluator identity, and trainability. The
additional scale, concept, propagation, trajectory, and distribution fields are
future schema work.

A learned prior could eventually estimate:

```text
Pr(ΔU > 0 | fingerprint(S), operator, level, context)
```

It must not become the promotion judge. Training requires enough real,
independently split transitions; synthetic and benchmark-validation edges must
remain separated. Until then, retrieval statistics are more defensible than a
neural ranker.

## Maturity map

| Component | Status | Research support |
|---|---|---|
| Hard contracts before scalar ranking | Implemented | Project governance/design choice |
| Utility, tail, uncertainty, cost, robustness metrics | Implemented | Standard statistical/optimization primitives |
| Multi-scale bounded mutation | Implemented in hierarchical search | ACE supports atomic edits; exact hierarchy is this project's synthesis |
| Recursive reconciliation/propagation | Prototype API | Not independently validated |
| Population/Pareto search | Implemented | EvoPrompt supports evolutionary prompt search |
| Local tree policy | Design target | PromptAgent and ACE support tree-based prompt exploration |
| Layer-wise trajectory diagnostics | Representation API only | Supported as diagnostic analysis, not truth |
| Novelty-aware selection | Design target | Extrapolated from novelty/quality-diversity search |
| Learned transition prior | Deferred | Requires substantially more real transition data |

## Primary sources

- Melamed, McCabe, and Huang (2025), [Demystifying optimized prompts in
  language models](https://aclanthology.org/2025.emnlp-main.147/).
- Li, Cotterell, and Sachan (2022), [Probing via
  Prompting](https://aclanthology.org/2022.naacl-main.84/).
- Hewitt and Liang (2019), [Designing and Interpreting Probes with Control
  Tasks](https://aclanthology.org/D19-1275/).
- Abnar et al. (2019), [Blackbox Meets Blackbox: Representational Similarity
  and Stability Analysis](https://aclanthology.org/W19-4820/).
- Guo et al. (ICLR 2024), [Connecting Large Language Models with Evolutionary
  Algorithms Yields Powerful Prompt Optimizers](https://arxiv.org/abs/2309.08532).
- Wang et al. (ICLR 2024), [PromptAgent](https://arxiv.org/abs/2310.16427).
- Kalibhat et al. (AISTATS 2026), [Interpreting and Controlling Model Behavior
  via Constitutions for Atomic Concept Edits](https://arxiv.org/abs/2602.00092).
- Li et al. (2023), [Robust Prompt Optimization for Large Language Models
  Against Distribution Shifts](https://arxiv.org/abs/2305.13954).
