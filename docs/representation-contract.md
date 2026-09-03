# Representation contract

## Purpose

Prompt text can be represented in a target model's hidden-state space, but the
representation is not an inverse encoding of intent. The project uses tensors
to measure candidate stability and generate hypotheses about which wording
changes matter. The executable behavioral contract remains authoritative.

## Data contract

An adapter implements:

```python
encode(text: str) -> HiddenRepresentation
```

`HiddenRepresentation.layers` maps a layer identifier to a two-dimensional
array with shape `(tokens, hidden_size)`. `model_id` records the target system
for provenance. The adapter is optional and is not a judge.

## Derived measurements

For layer `l`, the default pooled vector is:

```text
z_l(S) = normalize(mean(H_l(S), axis=tokens))
```

The current diagnostic drift is:

```text
D_rep(A, B) = 1 − cosine(z_l(A), z_l(B))
```

Mean pooling and last-token pooling are supported. Layer choice and pooling
must be recorded because representations are distributed and layer-dependent.

## Intent inference

The safe chain is:

```text
skill → hidden tensors → pooled representation → contract-labelled probe/RSA
     → hypothesis → behavioral contract test
```

The probe may predict declared features such as output routing, ownership,
failure handling, or scope. A high probe score does not establish that the
feature is causally used; format confounds and spurious correlations must be
tested. Activation patching is reserved for a later controlled experiment.

## Optimization rule

Representation terms are soft:

```text
maximize utility + α·robustness + β·density − λ·cost − δ·D_rep
subject to all hard invariants passing
```

Never select a candidate solely because it is close to the parent's hidden
state. A complete rewrite may have high representation drift and still be the
winner if it preserves the contract and improves measured behavior.

## Evidence classes

- `MECHANICAL`: executable predicates and artifact checks.
- `BEHAVIORAL`: held-out target-system outcomes.
- `REPRESENTATIONAL`: hidden-state geometry or probe/RSA results.

Representational evidence is diagnostic and cannot be promoted to behavioral
evidence by relabeling.

## Research grounding

This design follows hidden-state probing and representational similarity work,
while retaining the caution that probes can recover confounds rather than the
claimed reasoning process.

- https://arxiv.org/abs/2310.00313
- https://arxiv.org/abs/2106.00737
- https://arxiv.org/abs/2309.16042
